import Foundation
import Speech

/// Opt-in evidence that analyzeSequence actually requested a real input element,
/// not just that its admission boundary was reached. Default output is unchanged.
struct ObservedAnalyzerInputs<Base: AsyncSequence & Sendable>: AsyncSequence, Sendable {
    typealias Element = Base.Element
    let base: Base
    let onFirstInput: @Sendable () -> Void
    struct AsyncIterator: AsyncIteratorProtocol {
        var iterator: Base.AsyncIterator
        let onFirstInput: @Sendable () -> Void
        var observed = false
        mutating func next() async throws -> Element? {
            let value = try await iterator.next()
            if value != nil && !observed { observed = true; onFirstInput() }
            return value
        }
    }
    func makeAsyncIterator() -> AsyncIterator {
        AsyncIterator(iterator: base.makeAsyncIterator(), onFirstInput: onFirstInput)
    }
}

/// A cancellation handler may initiate the framework stop while analysis is
/// suspended. The error path awaits this SAME task before draining results and
/// releasing assets; it is not fire-and-forget cleanup.
final class AnalyzerStop: @unchecked Sendable {
    private let lock = NSLock()
    private let action: @Sendable () async -> Void
    private var task: Task<Void, Never>?
    private var closed = false

    init(stop: @escaping @Sendable () async -> Void) { action = stop }
    convenience init(_ analyzer: SpeechAnalyzer) {
        self.init(stop: { await analyzer.cancelAndFinishNow() })
    }

    func request() {
        lock.lock()
        defer { lock.unlock() }
        guard !closed, task == nil else { return }
        let action = action
        task = Task.detached { await action() }
    }

    private func snapshot(close: Bool) -> Task<Void, Never>? {
        lock.lock()
        defer { lock.unlock() }
        if close { closed = true }
        return task
    }

    func stopAndWait() async {
        request()
        await snapshot(close: false)?.value
    }

    /// Atomically closes handler admission and joins any previously initiated
    /// stop, including cancellation racing with successful collection.
    func finish() async {
        await snapshot(close: true)?.value
    }
}

/// Shared production/test lifetime seam: failures and cancellation must stop
/// analysis AND drain the owned result collector before the reservation ends.
func collectResults<T: Sendable>(
    _ resultsTask: Task<T, Error>,
    stop: AnalyzerStop,
    beforeCompleting: () async -> Void = {},
    analyze: () async throws -> Void
) async throws -> T {
    do {
        let result = try await withTaskCancellationHandler {
            try Task.checkCancellation()
            try await analyze()
            let collected = try await resultsTask.value
            // analyzeSequence may return early on cancellation without throwing.
            try Task.checkCancellation()
            await beforeCompleting()
            return collected
        } onCancel: { stop.request() }
        await stop.finish()
        try Task.checkCancellation()
        return result
    } catch {
        stop.request()
        await stop.finish()
        resultsTask.cancel()
        _ = await resultsTask.result
        if Task.isCancelled || error is CancellationError { throw CancellationError() }
        throw error
    }
}
