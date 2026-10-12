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
    writeDiagnostic(Data("""
    Usage: whisper-py-convert-apple [options] recording.mp3

    Options:
      --language en-US       Speech locale (default: en-US)
      --format text|json     Output format (default: text)
      --timestamp-mode none|segment|word  JSON timing detail (default: segment)
      --inventory-status     Read-only locale/assets/reservations JSON (no input)

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

func diagnostic(_ message: String, output: FileHandle = .standardError) {
    // Closed OR backpressured stderr must not mask errors or delay cleanup.
    writeDiagnostic(Data((message + "\n").utf8), descriptor: output.fileDescriptor)
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
        let operation = Task { try await run() }
        let signals = GracefulSignals { operation.cancel() }
        defer { withExtendedLifetime(signals) {} }
        do {
            try await operation.value
        } catch is CancellationError {
            diagnostic("Error: [cancelled] Apple transcription cancelled; cleanup was awaited (see any cleanup warnings).")
            Foundation.exit(130)
        } catch {
            diagnostic("Error: \(error.localizedDescription)")
            Foundation.exit(EXIT_FAILURE)
        }
    }

    static func run() async throws {
        if CommandLine.arguments.contains("--inventory-status") {
            let args = Array(CommandLine.arguments.dropFirst())
            var language = "en-US"
            var index = 0
            while index < args.count {
                switch args[index] {
                case "--inventory-status": break
                case "--language":
                    index += 1
                    guard index < args.count else { throw AppError.unsupportedLocale("missing --language value") }
                    language = args[index]
                default: throw AppError.invalidFormat("--inventory-status accepts only --language")
                }
                index += 1
            }
            try await inventoryStatus(language: language)
            return
        }
        guard let options = try parseOptions() else { return }
        guard SpeechTranscriber.isAvailable else { throw AppError.unavailable }
        let gate = try ReservationGate()
        try await gate.acquire()
        defer { gate.unlock() }
        try await withReservation(requested: Locale(identifier: options.language), inventory: appleInventory,
                                  warning: { diagnostic("Warning: \($0)") }) { locale in
            if locale.identifier.replacingOccurrences(of: "_", with: "-").lowercased()
                != options.language.replacingOccurrences(of: "_", with: "-").lowercased() {
                diagnostic("Using supported Apple speech locale \(locale.identifier) for requested \(options.language).")
            }
            try await transcribe(options, locale: locale)
        }
    }

    static func transcribe(_ options: Options, locale: Locale) async throws {
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
        do {
            let assetStatus = await AssetInventory.status(forModules: modules)
            if assetStatus != .installed {
                diagnostic("Installing Apple speech assets for \(locale.identifier)...")
                if let request = try await AssetInventory.assetInstallationRequest(supporting: modules) {
                    try await request.downloadAndInstall()
                }
                guard await AssetInventory.status(forModules: modules) == .installed else {
                    throw STTFailure(code: "asset_installation", message: "Apple speech assets are not installed for \(locale.identifier)")
                }
            }
        } catch is CancellationError { throw CancellationError() }
        catch {
            // Installation-request creation can itself perform reservation.
            // Preserve its typed capacity/unsupported errors rather than
            // incorrectly reporting every failure as a download failure.
            let code = STTFailure.reservationCode(for: error) ?? "asset_installation"
            throw STTFailure.framework(code, "Apple speech asset installation failed", error)
        }
        try Task.checkCancellation()

        let asset = AVURLAsset(url: options.input)
        let provider: AssetInputSequenceProvider
        do { provider = try await AssetInputSequenceProvider.provider(from: asset, compatibleWith: modules) }
        catch is CancellationError { throw CancellationError() }
        catch { throw STTFailure.framework("transcription_failed", "Apple media provider setup failed", error) }
        let analyzer = SpeechAnalyzer(
            modules: modules,
            options: SpeechAnalyzer.Options(priority: .userInitiated, modelRetention: .whileInUse)
        )
        let stop = AnalyzerStop(analyzer)

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

        let segments: [OutputSegment]
        do {
            segments = try await collectResults(resultsTask, stop: stop) {
                let lastSample = try await analyzer.analyzeSequence(provider.analyzerInputs)
                try Task.checkCancellation()
                if let lastSample {
                    try await analyzer.finalizeAndFinish(through: lastSample)
                } else {
                    // Finishing-through-end can wait for input that never began.
                    await stop.stopAndWait()
                }
            }
        } catch {
            if Task.isCancelled || error is CancellationError { throw CancellationError() }
            throw STTFailure.framework("transcription_failed", "Apple analysis/result collection failed", error)
        }
        try Task.checkCancellation()
        do {
            if options.format == "json" {
                let data = try JSONEncoder().encode(OutputTranscript(segments: segments))
                try await writeOutput(data + Data("\n".utf8))
            } else {
                try await writeOutput(Data((segments.map(\.text).joined(separator: "\n") + "\n").utf8))
            }
        } catch is CancellationError { throw CancellationError() }
        catch { throw STTFailure.framework("output_failed", "Could not encode/write transcript", error) }
    }
}
