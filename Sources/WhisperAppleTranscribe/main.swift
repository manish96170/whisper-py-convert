import AVFoundation
import Darwin
import Foundation
import Speech

enum AppError: LocalizedError {
    case missingInput
    case inputNotFound(String)
    case unsupportedLocale(String)
    case unavailable

    var errorDescription: String? {
        switch self {
        case .missingInput:
            return "An audio/video input path is required."
        case .inputNotFound(let path):
            return "Input file does not exist: \(path)"
        case .unsupportedLocale(let language):
            return "Apple SpeechTranscriber does not support locale: \(language)"
        case .unavailable:
            return "Apple SpeechTranscriber is unavailable on this Mac or macOS version."
        }
    }
}

struct Options {
    let input: URL
    let language: String
}

func printUsage() {
    FileHandle.standardError.write(Data("""
    Usage: whisper-py-convert-apple [--language en-US] recording.mp3

    Transcribes audio or video locally with Apple's macOS SpeechTranscriber.
    Apple speech assets are downloaded and managed by macOS when needed.
    The transcript is written to stdout; diagnostics are written to stderr.
    """.utf8))
}

func parseOptions() throws -> Options? {
    var language = "en-US"
    var inputPath: String?
    var arguments = Array(CommandLine.arguments.dropFirst())

    while !arguments.isEmpty {
        let argument = arguments.removeFirst()
        switch argument {
        case "-h", "--help":
            printUsage()
            return nil
        case "--language":
            guard !arguments.isEmpty else { throw AppError.unsupportedLocale("missing --language value") }
            language = arguments.removeFirst()
        default:
            guard inputPath == nil else { throw AppError.missingInput }
            inputPath = argument
        }
    }

    guard let inputPath else { throw AppError.missingInput }
    let url = URL(fileURLWithPath: inputPath).standardizedFileURL
    guard FileManager.default.fileExists(atPath: url.path) else {
        throw AppError.inputNotFound(url.path)
    }
    return Options(input: url, language: language)
}

func diagnostic(_ message: String) {
    FileHandle.standardError.write(Data((message + "\n").utf8))
}

@main
struct WhisperAppleTranscribe {
    static func main() async {
        do {
            guard let options = try parseOptions() else { return }

            guard SpeechTranscriber.isAvailable else { throw AppError.unavailable }
            let requestedLocale = Locale(identifier: options.language)
            guard let locale = await SpeechTranscriber.supportedLocale(equivalentTo: requestedLocale) else {
                throw AppError.unsupportedLocale(options.language)
            }

            let transcriber = SpeechTranscriber(locale: locale, preset: .transcription)
            let modules: [any SpeechModule] = [transcriber]
            let assetStatus = await AssetInventory.status(forModules: modules)
            if assetStatus != .installed {
                diagnostic("Installing Apple speech assets for \(locale.identifier)...")
                if let request = try await AssetInventory.assetInstallationRequest(supporting: modules) {
                    try await request.downloadAndInstall()
                }
            }

            let asset = AVURLAsset(url: options.input)
            let provider = try await AssetInputSequenceProvider.provider(
                from: asset,
                compatibleWith: modules
            )
            let analyzer = SpeechAnalyzer(
                modules: modules,
                options: SpeechAnalyzer.Options(
                    priority: .userInitiated,
                    modelRetention: .whileInUse
                )
            )

            let resultsTask = Task { () throws -> String in
                var results: [String] = []
                for try await result in transcriber.results {
                    let text = String(result.text.characters).trimmingCharacters(in: .whitespacesAndNewlines)
                    if !text.isEmpty {
                        results.append(text)
                    }
                }
                return results.joined(separator: "\n")
            }

            _ = try await analyzer.analyzeSequence(provider.analyzerInputs)
            try await analyzer.finalizeAndFinishThroughEndOfInput()
            let transcript = try await resultsTask.value
            if !transcript.isEmpty {
                print(transcript)
            }
        } catch {
            diagnostic("Error: \(error.localizedDescription)")
            Foundation.exit(EXIT_FAILURE)
        }
    }
}
