import Foundation

/// Stable error codes shared with the Python wrapper's `ErrorCode` enum
/// (python/mac_speech/errors.py). Keep the raw string values identical on
/// both sides of the protocol; see docs/protocol.md.
public enum ErrorCode: String, Codable, Sendable {
    case invalidArgument = "invalid_argument"
    case outputExists = "output_exists"
    case engineNotFound = "engine_not_found"
    case unsupportedPlatform = "unsupported_platform"
    case protocolVersionMismatch = "protocol_version_mismatch"
    case nativeProcessError = "native_process_error"
    case timeout = "timeout"
    case notImplemented = "not_implemented"
    case internalError = "internal_error"

    /// Must stay in sync with `EXIT_CODE_BY_ERROR` in
    /// python/mac_speech/errors.py.
    public var exitCode: Int32 {
        switch self {
        case .invalidArgument: return 2
        case .outputExists: return 3
        case .engineNotFound: return 4
        case .unsupportedPlatform: return 4
        case .protocolVersionMismatch: return 5
        case .nativeProcessError: return 6
        case .timeout: return 124
        case .notImplemented: return 10
        case .internalError: return 1
        }
    }
}

public struct AppError: Error {
    public let code: ErrorCode
    public let message: String
    public let remedy: String?

    public init(code: ErrorCode, message: String, remedy: String? = nil) {
        self.code = code
        self.message = message
        self.remedy = remedy
    }

    public static func invalidArgument(_ message: String, remedy: String? = nil) -> AppError {
        AppError(code: .invalidArgument, message: message, remedy: remedy)
    }

    public static func outputExists(_ message: String, remedy: String? = nil) -> AppError {
        AppError(code: .outputExists, message: message, remedy: remedy)
    }

    public static func timeout(_ message: String, remedy: String? = nil) -> AppError {
        AppError(code: .timeout, message: message, remedy: remedy)
    }

    public static func internalError(_ message: String, remedy: String? = nil) -> AppError {
        AppError(code: .internalError, message: message, remedy: remedy)
    }
}
