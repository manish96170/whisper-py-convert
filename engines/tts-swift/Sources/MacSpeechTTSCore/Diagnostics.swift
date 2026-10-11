import Foundation

/// Writes a diagnostic/progress line to stderr, never stdout — stdout is
/// reserved for exactly one JSON response document per invocation, mirroring
/// the convention documented in ../../../docs/protocol.md and used by the
/// existing `whisper-py-convert-apple` binary.
public func diagnostic(_ message: String) {
    FileHandle.standardError.write(Data((message + "\n").utf8))
}
