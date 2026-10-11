import Foundation

public func printUsage() {
    diagnostic("""
    Usage: mac-speech-tts <voices|speak|save|personal-voice-status> [options] [text]

    Operations:
      voices                   List available voices as one JSON document
      speak <text>             Speak text through the default audio output
      save <text> --output P   Synthesize text to an audio file
      personal-voice-status    Report (never request) Personal Voice authorization status

    Options:
      --voice <identifier>     Voice identifier (default: system default voice)
      --language <locale>      BCP-47 locale, used to pick a voice if --voice is omitted
      --rate <0.0-1.0>         Speech rate (default: AVSpeechUtterance's own default)
      --format wav|aiff|caf    Output container for `save` (default: wav)
      --output <path>          Required for `save`
      --force                  Overwrite an existing output file
      --stdin                  Read text from standard input instead of an argument
      --timeout <seconds>      Safety timeout: per-sentence for `save`, total for `speak` (default: 120)

    While `speak` is running, send signals to this process to control it:
      SIGINT or SIGTERM  stop immediately
      SIGTSTP            pause
      SIGCONT            resume

    This engine never requests Personal Voice authorization (it has no
    app bundle/Info.plist for the system to show a usage-description
    prompt from); it only reports whatever status the system already
    has. See docs/tts-engine.md.

    Exactly one JSON document is written to stdout per invocation;
    diagnostics are written to stderr. See ../../../docs/protocol.md.
    """)
}

public func run(arguments: [String]) -> Int32 {
    if arguments.isEmpty {
        printUsage()
        return ErrorCode.invalidArgument.exitCode
    }
    if arguments.first == "-h" || arguments.first == "--help" {
        printUsage()
        return 0
    }

    do {
        let options = try parseArguments(arguments)
        switch options.operation {
        case "voices":
            return emitSuccess(listVoices(languageFilter: options.language))
        case "speak":
            return emitSuccess(try runSpeak(options))
        case "save":
            return emitSuccess(try runSave(options))
        case "personal-voice-status":
            return emitSuccess(PersonalVoiceStatusResult(authorization_status: personalVoiceAuthorizationStatusString()))
        default:
            throw AppError.invalidArgument("Unknown operation '\(options.operation)'.")
        }
    } catch let error as AppError {
        return emitError(error)
    } catch {
        return emitError(AppError.internalError(error.localizedDescription))
    }
}
