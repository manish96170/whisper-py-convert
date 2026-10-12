import Foundation
import Testing
@testable import WhisperAppleTranscribe

private enum AnalysisError: Error { case analyzer, results }
private final class InputCount: @unchecked Sendable {
    private let lock = NSLock()
    private var value = 0
    func increment() { lock.lock(); value += 1; lock.unlock() }
    func get() -> Int { lock.lock(); defer { lock.unlock() }; return value }
}
private actor Events {
    var stopped = false
    var drained = false
    func stop() { stopped = true }
    func drain() { drained = true }
    func snapshot() -> (Bool, Bool) { (stopped, drained) }
}

struct AnalysisLifecycleTests {
    @Test func firstInputEventOccursOnlyWhenIteratorReadsAndOnlyOnce() async throws {
        let count = InputCount()
        let stream = AsyncStream<Int> { continuation in
            continuation.yield(1); continuation.yield(2); continuation.finish()
        }
        let inputs = ObservedAnalyzerInputs(base: stream, onFirstInput: { count.increment() })
        #expect(count.get() == 0)
        var values: [Int] = []
        for try await value in inputs { values.append(value) }
        #expect(values == [1, 2] && count.get() == 1)
    }

    @Test func analyzerFailureStopsAndDrainsCollectorBeforeReturning() async {
        let events = Events()
        let results = Task<Int, Error> {
            while !(await events.snapshot().0) { await Task.yield() }
            await events.drain()
            return 1
        }
        do {
            _ = try await collectResults(results, stop: AnalyzerStop(stop: { await events.stop() })) {
                throw AnalysisError.analyzer
            }
            Issue.record("Expected analysis failure")
        } catch AnalysisError.analyzer {} catch { Issue.record("Wrong primary error: \(error)") }
        let (stopped, drained) = await events.snapshot()
        #expect(stopped && drained)
    }

    @Test func resultFailureStopsAnalysisWithoutMaskingError() async {
        let events = Events()
        let results = Task<Int, Error> { throw AnalysisError.results }
        do {
            _ = try await collectResults(results, stop: AnalyzerStop(stop: { await events.stop() })) {}
            Issue.record("Expected result failure")
        } catch AnalysisError.results {} catch { Issue.record("Wrong primary error: \(error)") }
        let (stopped, _) = await events.snapshot()
        #expect(stopped)
    }

    @Test func cancellationThatReturnsNormallyStillStopsAndDrains() async {
        let events = Events()
        let results = Task<Int, Error> {
            while !(await events.snapshot().0) { await Task.yield() }
            await events.drain()
            return 1
        }
        let operation = Task {
            try await collectResults(results, stop: AnalyzerStop(stop: { await events.stop() })) {
                // Match Apple's documented early-return (not throw) behavior.
                while !Task.isCancelled { await Task.yield() }
            }
        }
        operation.cancel()
        do { _ = try await operation.value; Issue.record("Cancelled partial result escaped") }
        catch is CancellationError {} catch { Issue.record("Unexpected error: \(error)") }
        let (stopped, drained) = await events.snapshot()
        #expect(stopped && drained)
    }

    @Test func successFinishesCollectionWithoutUnnecessaryStop() async throws {
        let events = Events()
        let result = try await collectResults(Task<Int, Error> { 42 }, stop: AnalyzerStop(stop: { await events.stop() })) {}
        #expect(result == 42)
        let (stopped, _) = await events.snapshot()
        #expect(!stopped)
    }

    @Test func cancellationAtCompletionJoinsDelayedStop() async {
        let events = Events()
        let stop = AnalyzerStop(stop: {
            try? await Task.sleep(for: .milliseconds(100))
            await events.stop()
        })
        let operation = Task {
            try await collectResults(Task<Int, Error> { 42 }, stop: stop, beforeCompleting: {
                await events.drain() // deterministic final-check/handler-exit seam
                while !Task.isCancelled { await Task.yield() }
            }) {}
        }
        while !(await events.snapshot().1) { await Task.yield() }
        operation.cancel()
        do { _ = try await operation.value; Issue.record("Expected cancellation") }
        catch is CancellationError {} catch { Issue.record("\(error)") }
        let (stopped, _) = await events.snapshot()
        #expect(stopped, "The delayed stop must have been joined before returning")
    }
}
