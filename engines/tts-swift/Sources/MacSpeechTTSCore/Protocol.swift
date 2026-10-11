import Foundation

/// Must stay in sync with `PROTOCOL_VERSION` in
/// python/mac_speech/native_protocol.py. See docs/protocol.md.
public let protocolVersion = 1

public struct ErrorPayload: Codable {
    public let code: String
    public let message: String
    public let remedy: String?
}

/// Placeholder `result` type for error responses, where `result` is always
/// null. A concrete type is still needed to satisfy `Response<T>`'s generic
/// constraint.
public struct EmptyResult: Codable {}

public struct VoiceInfo: Codable {
    public let identifier: String
    public let name: String
    public let language: String
    public let quality: String
    public let gender: String
    public let is_personal_voice: Bool
    public let is_novelty_voice: Bool
}

public struct VoicesResult: Codable {
    public let voices: [VoiceInfo]
    public let count: Int
}

public struct PersonalVoiceStatusResult: Codable {
    /// One of "not_determined", "denied", "unsupported", "authorized", or
    /// "unknown". See `personalVoiceAuthorizationStatusString()` in
    /// Voices.swift and docs/tts-engine.md for what each value means and
    /// why this engine only reports status rather than requesting it.
    public let authorization_status: String
}

public struct SpeakResult: Codable {
    public let completed: Bool
    public let stopped_early: Bool
    public let voice_identifier: String
    public let language: String
    public let sentence_count: Int
    public let text_length: Int
}

public struct SaveResult: Codable {
    public let output_path: String
    public let format: String
    public let sample_rate: Double
    public let channels: Int
    public let bit_depth: Int
    public let duration_seconds: Double
    public let file_size_bytes: Int
    public let sentence_count: Int
    public let voice_identifier: String
    public let language: String
}

public struct Response<T: Codable>: Codable {
    public let status: String
    public let protocol_version: Int
    public let result: T?
    public let error: ErrorPayload?
}

/// Prints exactly one JSON document to stdout and returns the process exit
/// code to use. Never calls `exit()` itself — only `main.swift` does that —
/// so this stays safe to call from tests without terminating the process.
public func emitSuccess<T: Codable>(_ result: T) -> Int32 {
    printJSON(Response(status: "ok", protocol_version: protocolVersion, result: result, error: nil))
    return 0
}

public func emitError(_ error: AppError) -> Int32 {
    let payload = ErrorPayload(code: error.code.rawValue, message: error.message, remedy: error.remedy)
    printJSON(Response<EmptyResult>(status: "error", protocol_version: protocolVersion, result: nil, error: payload))
    return error.code.exitCode
}

private func printJSON<T: Codable>(_ response: Response<T>) {
    guard let data = try? JSONEncoder().encode(response), let json = String(data: data, encoding: .utf8) else {
        diagnostic("Failed to encode JSON response.")
        return
    }
    print(json)
    fflush(stdout)
}
