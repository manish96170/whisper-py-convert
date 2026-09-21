import AVFoundation
import Darwin
import Foundation
import Speech

enum TimestampMode: String {
    case none
    case segment
    case word
}

struct Options {
    let input: URL
    let language: String
    let format: String
    let timestampMode: TimestampMode
}

struct OutputWord: Codable {
    let text: String
    let start: Double
    let end: Double
}

struct OutputSegment: Codable {
    let text: String
    let start: Double
    let end: Double
    let words: [OutputWord]
}

struct OutputTranscript: Codable {
    let segments: [OutputSegment]
}

enum AppError: LocalizedError {
    case missingInput
    case inputNotFound(String)
    case invalidFormat(String)
    case unsupportedLocale(String)
    case unavailable

    var errorDescription: String? {
        switch self {
        case .missingInput: return "An audio/video input path is required."
        case .inputNotFound(let path): return "Input file does not exist: \(path)"
        case .invalidFormat(let format): return "Unsupported output format: \(format)"
        case .unsupportedLocale(let language): return "Apple SpeechTranscriber does not support locale: \(language)"
        case .unavailable: return "Apple SpeechTranscriber is unavailable on this Mac or macOS version."
        }
    }
}

func printUsage() {
    FileHandle.standardError.write(Data("""
    Usage: whisper-py-convert-apple [options] recording.mp3

    Options:
      --language en-US       Speech locale (default: en-US)
      --format text|json     Output format (default: text)
      --timestamp-mode none|segment|word  JSON timing detail (default: segment)

    The transcript is written to stdout; diagnostics are written to stderr.
    """.utf8))
}

func parseOptions() throws -> Options? {
    var language = "en-US"
    var format = "text"
    var timestampMode = TimestampMode.segment
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
        case "--format":
            guard !arguments.isEmpty else { throw AppError.invalidFormat("missing --format value") }
            format = arguments.removeFirst()
        case "--timestamp-mode":
            guard !arguments.isEmpty, let mode = TimestampMode(rawValue: arguments.removeFirst()) else {
                throw AppError.invalidFormat("timestamp mode must be none, segment, or word")
            }
            timestampMode = mode
        default:
            guard inputPath == nil else { throw AppError.missingInput }
            inputPath = argument
        }
    }

    guard let inputPath else { throw AppError.missingInput }
    guard format == "text" || format == "json" else { throw AppError.invalidFormat(format) }
    let url = URL(fileURLWithPath: inputPath).standardizedFileURL
    guard FileManager.default.fileExists(atPath: url.path) else { throw AppError.inputNotFound(url.path) }
    return Options(input: url, language: language, format: format, timestampMode: timestampMode)
}

func diagnostic(_ message: String) {
    FileHandle.standardError.write(Data((message + "\n").utf8))
}

func seconds(_ time: CMTime) -> Double {
    let value = CMTimeGetSeconds(time)
    return value.isFinite && value >= 0 ? value : 0
}

func timedWords(from attributed: AttributedString) -> [OutputWord] {
    var words: [OutputWord] = []
    for run in attributed.runs {
        let slice = attributed[run.range]
        let text = String(slice.characters).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, let range = slice.audioTimeRange else { continue }
        words.append(OutputWord(text: text, start: seconds(range.start), end: seconds(range.end)))
    }
    return words
}

@main
struct WhisperAppleTranscribe {
    static func main() async {
        do {
            guard let options = try parseOptions() else { return }
            guard SpeechTranscriber.isAvailable else { throw AppError.unavailable }
            let locale = Locale(identifier: options.language)

            let transcriber: SpeechTranscriber
            if options.timestampMode == .word {
                transcriber = SpeechTranscriber(
                    locale: locale,
                    transcriptionOptions: [],
                    reportingOptions: [],
                    attributeOptions: [.audioTimeRange]
                )
            } else {
                transcriber = SpeechTranscriber(locale: locale, preset: .transcription)
            }
            let modules: [any SpeechModule] = [transcriber]
            guard try await AssetInventory.reserve(locale: locale) else {
                throw AppError.unsupportedLocale(options.language)
            }
            let assetStatus = await AssetInventory.status(forModules: modules)
            if assetStatus != .installed {
                diagnostic("Installing Apple speech assets for \(locale.identifier)...")
                if let request = try await AssetInventory.assetInstallationRequest(supporting: modules) {
                    try await request.downloadAndInstall()
                }
            }

            let asset = AVURLAsset(url: options.input)
            let provider = try await AssetInputSequenceProvider.provider(from: asset, compatibleWith: modules)
            let analyzer = SpeechAnalyzer(
                modules: modules,
                options: SpeechAnalyzer.Options(priority: .userInitiated, modelRetention: .whileInUse)
            )

            let resultsTask = Task { () throws -> [OutputSegment] in
                var segments: [OutputSegment] = []
                for try await result in transcriber.results {
                    let text = String(result.text.characters).trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !text.isEmpty else { continue }
                    let words = options.timestampMode == .word ? timedWords(from: result.text) : []
                    segments.append(OutputSegment(
                        text: text,
                        start: seconds(result.range.start),
                        end: seconds(result.range.end),
                        words: words
                    ))
                }
                return segments
            }

            _ = try await analyzer.analyzeSequence(provider.analyzerInputs)
            try await analyzer.finalizeAndFinishThroughEndOfInput()
            let segments = try await resultsTask.value
            if options.format == "json" {
                let data = try JSONEncoder().encode(OutputTranscript(segments: segments))
                print(String(decoding: data, as: UTF8.self))
            } else {
                print(segments.map(\.text).joined(separator: "\n"))
            }
        } catch {
            diagnostic("Error: \(error.localizedDescription)")
            Foundation.exit(EXIT_FAILURE)
        }
    }
}
