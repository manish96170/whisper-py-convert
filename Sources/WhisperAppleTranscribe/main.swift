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
    let requireInstalledAssets: Bool
    let requireExactLocale: Bool
    let requireNewReservation: Bool
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
      --require-installed-assets  Refuse installation requests/downloads
      --require-exact-locale  Refuse regional locale substitution
      --require-new-reservation  Refuse borrowed reuse (validation only)
      --no-asset-download     Reservation-first cached check (also the normal default)

    Asset setup (no audio; explicit network consent only):
      --install-assets --language fr-FR    Read-only setup preview
      --install-assets --language fr-FR --confirm-download fr_FR
      Confirmed setup may download Apple models and retains their reservation.

    Maintenance (no audio; same executable identity and reservation lock):
      --reservation-maintenance inspect
      --reservation-maintenance release --reserved-locale EXACT [--dry-run]
      Release requires --confirm-release EXACT --confirm-unused
      Default en_US additionally requires --allow-default-release
      Releasing assets may affect availability; no downloads or release-all.

    The transcript is written to stdout; diagnostics are written to stderr.
    """.utf8))
}

func parseOptions(arguments supplied: [String] = Array(CommandLine.arguments.dropFirst())) throws -> Options? {
    var language = "en-US"
    var format = "text"
    var timestampMode = TimestampMode.segment
    var inputPath: String?
    var arguments = supplied
    var requireInstalled = false
    var requireExact = false
    var requireNew = false

    while !arguments.isEmpty {
        let argument = arguments.removeFirst()
        switch argument {
        case "-h", "--help":
            printUsage()
            return nil
        case "--language":
            guard !arguments.isEmpty else { throw AppError.unsupportedLocale("missing --language value") }
            language = arguments.removeFirst()
        case "--require-installed-assets": requireInstalled = true
        case "--require-exact-locale": requireExact = true
        case "--require-new-reservation": requireNew = true
        case "--no-asset-download": break // All transcription paths now forbid downloads.
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
    return Options(input: url, language: language, format: format, timestampMode: timestampMode,
                   requireInstalledAssets: requireInstalled, requireExactLocale: requireExact,
                   requireNewReservation: requireNew)
}

func diagnostic(_ message: String, output: FileHandle = .standardError) {
    // Closed OR backpressured stderr must not mask errors or delay cleanup.
    writeDiagnostic(Data((message + "\n").utf8), descriptor: output.fileDescriptor)
}

/// Opt-in validation diagnostics only; never includes audio paths or transcript.
func validationEvent(_ phase: String, locale: String? = nil) {
    var event = ["phase": phase]
    if let locale { event["actual_locale"] = locale }
    if let data = try? JSONEncoder().encode(event) {
        diagnostic("Validation: " + String(decoding: data, as: UTF8.self))
    }
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
        if let setup = try AssetSetupCommand.parse(Array(CommandLine.arguments.dropFirst())) {
            guard SpeechTranscriber.isAvailable else { throw AppError.unavailable }
            let gate = try ReservationGate()
            try await gate.acquire()
            defer { gate.unlock() }
            _ = try await setupSpeechAssets(setup, inventory: appleInventory,
                warning: { diagnostic("Warning: \($0)") },
                publish: { report in try await writeOutput(JSONEncoder().encode(report) + Data("\n".utf8)) }) { locale in
                let modules: [any SpeechModule] = [SpeechTranscriber(locale: locale, preset: .transcription)]
                if let request = try await AssetInventory.assetInstallationRequest(supporting: modules) {
                    diagnostic("Explicitly requested Apple asset setup for \(locale.identifier); missing models may be downloaded.")
                    try await request.downloadAndInstall()
                    return true
                }
                return false
            }
            return
        }
        if let maintenance = try ReservationMaintenanceCommand.parse(Array(CommandLine.arguments.dropFirst())) {
            guard SpeechTranscriber.isAvailable else { throw AppError.unavailable }
            let gate = try ReservationGate()
            try await gate.acquire()
            defer { gate.unlock() }
            let report = try await maintainReservation(maintenance, inventory: appleInventory)
            try await writeOutput(JSONEncoder().encode(report) + Data("\n".utf8))
            guard report.verified else {
                throw STTFailure(code: "reservation_maintenance", message: "Release verification failed; inspect the reported inventory. No retry, reset or download was attempted")
            }
            return
        }
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
            let gate = try ReservationGate()
            try await gate.acquire()
            defer { gate.unlock() }
            try await inventoryStatus(language: language)
            return
        }
        guard let options = try parseOptions() else { return }
        guard SpeechTranscriber.isAvailable else { throw AppError.unavailable }
        let gate = try ReservationGate()
        try await gate.acquire()
        defer { gate.unlock() }
        try await withReservation(requested: Locale(identifier: options.language), inventory: appleInventory,
                                  requireInstalled: options.requireInstalledAssets,
                                  requireExactLocale: options.requireExactLocale,
                                  requireNewReservation: options.requireNewReservation,
                                  event: { phase, actual in
                                      if options.requireNewReservation { validationEvent(phase, locale: actual.identifier) }
                                  },
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
            // No implicit network activity during transcription, including a
            // readiness race after the Python wrapper's read-only preflight.
            try await ensureSpeechAssets(requireInstalled: true, installed: {
                await AssetInventory.status(forModules: modules) == .installed
            }, install: {
                throw STTFailure(code: "assets_not_installed", message: "No automatic installation is permitted during transcription")
            })
        } catch is CancellationError { throw CancellationError() }
        catch let failure as STTFailure {
            if failure.code == "assets_not_installed" {
                throw STTFailure(code: failure.code, message: "Apple assets for \(locale.identifier) are not ready. No transcription or download started. Preview this executable with --install-assets --language \(locale.identifier); explicitly approve setup with --confirm-download \(locale.identifier), then retry.")
            }
            throw failure
        }
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
        // Admission boundary only: cancellation can still prevent analyzer entry.
        if options.requireNewReservation { validationEvent("analysis-entry") }
        do {
            segments = try await collectResults(resultsTask, stop: stop) {
                let reportInputs = options.requireNewReservation
                let inputs = ObservedAnalyzerInputs(base: provider.analyzerInputs, onFirstInput: {
                    if reportInputs { validationEvent("analysis-input") }
                })
                let lastSample = try await analyzer.analyzeSequence(inputs)
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
        if options.requireNewReservation { validationEvent("analysis-finished") }
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
