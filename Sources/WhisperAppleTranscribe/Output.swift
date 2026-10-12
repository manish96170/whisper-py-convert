import Darwin
import Foundation

/// Diagnostics must never hold a reservation/gate on an unread stderr pipe.
/// One bounded nonblocking attempt; drop unwritten bytes on backpressure/error.
func writeDiagnostic(_ data: Data, descriptor: Int32 = STDERR_FILENO) {
    let originalFlags = fcntl(descriptor, F_GETFL)
    guard originalFlags >= 0, fcntl(descriptor, F_SETFL, originalFlags | O_NONBLOCK) == 0 else { return }
    defer { _ = fcntl(descriptor, F_SETFL, originalFlags) }
    guard !data.isEmpty else { return }
    data.withUnsafeBytes { buffer in
        _ = Darwin.write(descriptor, buffer.baseAddress!, min(data.count, 16_384))
    }
}

/// Bounded, cancellation-aware stdout publication. A stopped pipe reader must
/// not hold reservations forever. No detached writer survives the operation.
func writeOutput(_ data: Data, descriptor: Int32 = STDOUT_FILENO) async throws {
    let originalFlags = fcntl(descriptor, F_GETFL)
    guard originalFlags >= 0, fcntl(descriptor, F_SETFL, originalFlags | O_NONBLOCK) == 0 else {
        throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO)
    }
    defer { _ = fcntl(descriptor, F_SETFL, originalFlags) }
    var offset = 0
    while offset < data.count {
        try Task.checkCancellation()
        let written = data.withUnsafeBytes { buffer in
            Darwin.write(descriptor, buffer.baseAddress!.advanced(by: offset), min(data.count - offset, 16_384))
        }
        if written > 0 { offset += written; continue }
        if written < 0 && errno == EINTR { continue }
        if written < 0 && (errno == EAGAIN || errno == EWOULDBLOCK) {
            try await Task.sleep(for: .milliseconds(25))
            continue
        }
        throw POSIXError(POSIXErrorCode(rawValue: written == 0 ? EIO : errno) ?? .EIO)
    }
    try Task.checkCancellation()
}
