import Foundation

public struct Options {
    public var operation: String
    public var text: String?
    public var readTextFromStdin: Bool
    public var voiceIdentifier: String?
    public var language: String?
    public var rate: Double?
    public var format: String
    public var outputPath: String?
    public var force: Bool
    public var timeoutSeconds: Double
}

public let supportedOperations = ["voices", "speak", "save", "personal-voice-status"]
private let defaultFormat = "wav"
/// Per-sentence timeout for `save`, total timeout for `speak`. Generous
/// relative to the per-sentence durations observed during Phase 2
/// discovery (roughly 10-12 seconds for a ~25-30 word sentence).
public let defaultTimeoutSeconds = 120.0

public func parseArguments(_ arguments: [String]) throws -> Options {
    var remaining = arguments
    guard !remaining.isEmpty else {
        throw AppError.invalidArgument(
            "An operation is required.",
            remedy: "Usage: mac-speech-tts <voices|speak|save> [options] [text]"
        )
    }
    let operation = remaining.removeFirst()
    guard supportedOperations.contains(operation) else {
        throw AppError.invalidArgument(
            "Unknown operation '\(operation)'.",
            remedy: "Supported operations: \(supportedOperations.joined(separator: ", "))."
        )
    }

    var text: String?
    var readTextFromStdin = false
    var voiceIdentifier: String?
    var language: String?
    var rate: Double?
    var format = defaultFormat
    var outputPath: String?
    var force = false
    var timeoutSeconds = defaultTimeoutSeconds

    while !remaining.isEmpty {
        let argument = remaining.removeFirst()
        switch argument {
        case "--voice":
            voiceIdentifier = try takeValue(&remaining, for: argument)
        case "--language":
            language = try takeValue(&remaining, for: argument)
        case "--rate":
            let raw = try takeValue(&remaining, for: argument)
            guard let parsed = Double(raw) else {
                throw AppError.invalidArgument("--rate must be a number between 0.0 and 1.0, got '\(raw)'.")
            }
            rate = parsed
        case "--format":
            format = try takeValue(&remaining, for: argument)
        case "--output":
            outputPath = try takeValue(&remaining, for: argument)
        case "--force":
            force = true
        case "--stdin":
            readTextFromStdin = true
        case "--timeout":
            let raw = try takeValue(&remaining, for: argument)
            guard let parsed = Double(raw), parsed > 0 else {
                throw AppError.invalidArgument("--timeout must be a positive number of seconds, got '\(raw)'.")
            }
            timeoutSeconds = parsed
        default:
            guard text == nil else {
                throw AppError.invalidArgument("Unexpected extra argument '\(argument)'.")
            }
            text = argument
        }
    }

    if let rate, !(0.0...1.0).contains(rate) {
        throw AppError.invalidArgument("--rate must be between 0.0 and 1.0, got \(rate).")
    }
    guard supportedAudioFormats.contains(format) else {
        throw AppError.invalidArgument(
            "Unsupported --format '\(format)'.",
            remedy: "Supported formats: \(supportedAudioFormats.joined(separator: ", "))."
        )
    }
    if operation == "save" && outputPath == nil {
        throw AppError.invalidArgument("--output is required for the 'save' operation.")
    }
    if operation != "voices" && operation != "personal-voice-status" {
        if text == nil && !readTextFromStdin {
            throw AppError.invalidArgument(
                "Text is required.",
                remedy: "Pass it as an argument, or use --stdin to read it from standard input."
            )
        }
        if text != nil && readTextFromStdin {
            throw AppError.invalidArgument("Pass text as an argument or use --stdin, not both.")
        }
    }

    return Options(
        operation: operation,
        text: text,
        readTextFromStdin: readTextFromStdin,
        voiceIdentifier: voiceIdentifier,
        language: language,
        rate: rate,
        format: format,
        outputPath: outputPath,
        force: force,
        timeoutSeconds: timeoutSeconds
    )
}

private func takeValue(_ remaining: inout [String], for flag: String) throws -> String {
    guard !remaining.isEmpty else {
        throw AppError.invalidArgument("\(flag) requires a value.")
    }
    return remaining.removeFirst()
}

/// Resolves the final text to synthesize: from the positional argument, or
/// by reading all of stdin when `--stdin` was passed. Handles empty input
/// explicitly rather than letting an empty utterance silently produce zero
/// audio (PLAN.md section 5.3: "Handle Unicode text, long text, and empty
/// input.").
public func resolveText(_ options: Options) throws -> String {
    let raw: String
    if let text = options.text {
        raw = text
    } else if options.readTextFromStdin {
        let data = FileHandle.standardInput.readDataToEndOfFile()
        raw = String(data: data, encoding: .utf8) ?? ""
    } else {
        raw = ""
    }
    guard !raw.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
        throw AppError.invalidArgument("Text must not be empty.")
    }
    return raw
}
