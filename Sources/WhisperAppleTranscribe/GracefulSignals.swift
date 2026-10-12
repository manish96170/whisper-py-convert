import Darwin
import Dispatch

/// Signals request cooperative cancellation; the entry point awaits the task
/// (including cleanup) before exit. SIGKILL/power loss cannot run this path.
final class GracefulSignals {
    private var sources: [DispatchSourceSignal] = []

    init(cancel: @escaping @Sendable () -> Void) {
        for number in [SIGINT, SIGTERM] {
            signal(number, SIG_IGN)
            let source = DispatchSource.makeSignalSource(signal: number, queue: .global())
            source.setEventHandler(handler: cancel)
            source.resume()
            sources.append(source)
        }
        // A broken stdout pipe must throw rather than terminate before cleanup.
        signal(SIGPIPE, SIG_IGN)
    }

    deinit { for source in sources { source.cancel() } }
}
