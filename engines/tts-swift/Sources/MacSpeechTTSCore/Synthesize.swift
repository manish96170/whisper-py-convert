import AVFoundation
import Foundation

/// Validates and normalizes the `--output` path against the chosen audio
/// format's canonical extension. The extension is never used to *infer*
/// the format (PLAN.md section 5.1) — it is appended when absent, or
/// validated for an exact match when present, so a mismatched extension
/// cannot silently produce a mislabeled or corrupted file (see
/// docs/tts-engine.md for the mismatched-settings corruption this guards
/// against).
func resolveOutputURL(_ path: String, formatSpec: AudioFormatSpec) throws -> URL {
    var url = URL(fileURLWithPath: path).standardizedFileURL
    let ext = url.pathExtension.lowercased()
    if ext.isEmpty {
        url = url.appendingPathExtension(formatSpec.fileExtension)
    } else if ext != formatSpec.fileExtension {
        throw AppError.invalidArgument(
            "--output extension '.\(ext)' does not match --format \(formatSpec.name) (expected '.\(formatSpec.fileExtension)').",
            remedy: "Use a matching extension, or omit the extension and let mac-speech-tts append '.\(formatSpec.fileExtension)'."
        )
    }
    return url
}

/// Synthesizes `text` to an audio file, one sentence at a time.
///
/// Two Phase 2 findings shape this implementation and must not be
/// "simplified" away without re-verifying against docs/tts-engine.md:
///
/// 1. `AVSpeechSynthesizer.write(_:toBufferCallback:)`, given a single
///    multi-sentence `AVSpeechUtterance`, silently stops producing real
///    speech after the first sentence on this macOS version while still
///    emitting a plausible-length tail of audio. Synthesizing one sentence
///    per fresh `AVSpeechSynthesizer`/`AVSpeechUtterance` and concatenating
///    the output is the verified workaround — this is not optional
///    "chunking for long text", it is required for correctness on *any*
///    multi-sentence input.
/// 2. `AVAudioFile` does not reliably finalize/flush its header via
///    implicit scope-exit deinit; the handle must be explicitly set to
///    `nil` after writing completes, or the file's declared duration/size
///    can read as zero despite real audio data being present on disk.
public func runSave(_ options: Options) throws -> SaveResult {
    let text = try resolveText(options)
    let voice = try resolveVoice(identifier: options.voiceIdentifier, language: options.language)
    let formatSpec = try audioFormatSpec(named: options.format)
    guard let outputPathString = options.outputPath else {
        throw AppError.invalidArgument("--output is required for the 'save' operation.")
    }
    let finalURL = try resolveOutputURL(outputPathString, formatSpec: formatSpec)

    if FileManager.default.fileExists(atPath: finalURL.path) && !options.force {
        throw AppError.outputExists(
            "Output file already exists: \(finalURL.path)",
            remedy: "Choose a different --output path, or pass --force to overwrite."
        )
    }

    let sentences = splitIntoSentences(text)
    guard !sentences.isEmpty else {
        throw AppError.invalidArgument("Text must not be empty.")
    }

    // Write to a hidden sibling temp file in the same directory so the
    // final move is same-filesystem and effectively atomic, and never
    // partially overwrites the destination on failure (PLAN.md section
    // 5.3: "Write temporary files and atomically finalize them where
    // practical."). The temp name must still end in the format's real
    // extension — AVAudioFile infers its container from the URL's
    // extension, and a generic ".tmp" suffix was found during Phase 2
    // testing to silently make it write a CAF container regardless of
    // `formatSpec.settings`, mislabeling the final file.
    let directory = finalURL.deletingLastPathComponent()
    let baseName = finalURL.deletingPathExtension().lastPathComponent
    let tempName = ".\(baseName).mac-speech-tts-\(ProcessInfo.processInfo.globallyUniqueString).tmp.\(formatSpec.fileExtension)"
    let tempURL = directory.appendingPathComponent(tempName)

    var audioFile: AVAudioFile?
    var totalFrames: Int64 = 0

    func cleanupTemp() {
        audioFile = nil
        try? FileManager.default.removeItem(at: tempURL)
    }

    for sentence in sentences {
        let synthesizer = AVSpeechSynthesizer()
        let utterance = AVSpeechUtterance(string: sentence)
        utterance.voice = voice
        if let rate = options.rate {
            utterance.rate = Float(rate)
        }

        var finished = false
        var writeError: Error?

        synthesizer.write(utterance) { buffer in
            guard let pcmBuffer = buffer as? AVAudioPCMBuffer else { return }
            if pcmBuffer.frameLength == 0 {
                finished = true
                return
            }
            do {
                if audioFile == nil {
                    audioFile = try AVAudioFile(forWriting: tempURL, settings: formatSpec.settings)
                }
                try audioFile?.write(from: pcmBuffer)
                totalFrames += Int64(pcmBuffer.frameLength)
            } catch {
                writeError = error
                finished = true
            }
        }

        // Bounded run-loop pump, not a raw semaphore wait: a Phase 0
        // probe showed `DispatchSemaphore.wait()` hangs indefinitely if
        // the completion callback is never invoked. This loop always
        // terminates at `deadline` even in that failure mode.
        let deadline = Date().addingTimeInterval(options.timeoutSeconds)
        while !finished && Date() < deadline {
            RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.05))
        }

        if let writeError {
            cleanupTemp()
            throw AppError(
                code: .nativeProcessError,
                message: "Failed writing audio data: \(writeError.localizedDescription)"
            )
        }
        if !finished {
            cleanupTemp()
            throw AppError.timeout(
                "Synthesis timed out after \(options.timeoutSeconds) seconds on sentence: \"\(sentence.prefix(60))\""
            )
        }
    }

    // Explicitly release the AVAudioFile so it finalizes/flushes its
    // header before we read it back or move it — see finding #2 above.
    audioFile = nil

    guard totalFrames > 0 else {
        cleanupTemp()
        throw AppError(code: .nativeProcessError, message: "Synthesis produced no audio output.")
    }

    do {
        if FileManager.default.fileExists(atPath: finalURL.path) {
            try FileManager.default.removeItem(at: finalURL)
        }
        try FileManager.default.moveItem(at: tempURL, to: finalURL)
    } catch {
        cleanupTemp()
        throw AppError(code: .nativeProcessError, message: "Failed to finalize output file: \(error.localizedDescription)")
    }

    var fileSize = 0
    if let attributes = try? FileManager.default.attributesOfItem(atPath: finalURL.path),
       let size = attributes[.size] as? Int {
        fileSize = size
    }

    return SaveResult(
        output_path: finalURL.path,
        format: formatSpec.name,
        sample_rate: formatSpec.sampleRate,
        channels: formatSpec.channels,
        bit_depth: formatSpec.bitDepth,
        duration_seconds: Double(totalFrames) / formatSpec.sampleRate,
        file_size_bytes: fileSize,
        sentence_count: sentences.count,
        voice_identifier: voice.identifier,
        language: voice.language
    )
}

/// Tracks completion/cancellation across a queue of per-sentence
/// utterances submitted to one `AVSpeechSynthesizer`. `speak()` is called
/// once per sentence on the *same* synthesizer instance, which plays them
/// back-to-back via its own internal queue — unlike `write()`, direct
/// playback was verified during Phase 2 discovery to handle multi-sentence
/// text correctly, but sentences are still queued individually here for
/// consistent behavior and clean stop/pause/resume semantics.
final class SpeakCoordinator: NSObject, AVSpeechSynthesizerDelegate {
    let totalCount: Int
    var completedCount = 0
    var cancelled = false
    var finished = false

    init(totalCount: Int) {
        self.totalCount = totalCount
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        completedCount += 1
        if completedCount >= totalCount {
            finished = true
        }
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        cancelled = true
        finished = true
    }
}

/// Speaks `text` through the default audio output, blocking until it
/// finishes or is interrupted.
///
/// Process-lifecycle contract (verified empirically during Phase 2 — see
/// docs/tts-engine.md): this process installs signal handlers via
/// `DispatchSource` (the Apple-recommended, async-signal-safe pattern,
/// rather than a raw C signal handler) and first disarms the default
/// disposition with `signal(sig, SIG_IGN)`:
///   - SIGINT or SIGTERM -> stop immediately (`stopSpeaking(at: .immediate)`)
///   - SIGTSTP -> pause (`pauseSpeaking`); the process keeps running and is
///     not suspended by the kernel, because installing a handler for
///     SIGTSTP supersedes the default stop action.
///   - SIGCONT -> resume (`continueSpeaking`)
/// A caller (the future Python wrapper, Phase 3) controls a running
/// `speak` invocation by sending these signals to its process ID.
public func runSpeak(_ options: Options) throws -> SpeakResult {
    let text = try resolveText(options)
    let voice = try resolveVoice(identifier: options.voiceIdentifier, language: options.language)
    let sentences = splitIntoSentences(text)
    guard !sentences.isEmpty else {
        throw AppError.invalidArgument("Text must not be empty.")
    }

    let synthesizer = AVSpeechSynthesizer()
    let coordinator = SpeakCoordinator(totalCount: sentences.count)
    synthesizer.delegate = coordinator

    signal(SIGINT, SIG_IGN)
    signal(SIGTERM, SIG_IGN)
    signal(SIGTSTP, SIG_IGN)
    signal(SIGCONT, SIG_IGN)

    var signalSources: [DispatchSourceSignal] = []
    func trap(_ sig: Int32, _ action: @escaping () -> Void) {
        let source = DispatchSource.makeSignalSource(signal: sig, queue: .main)
        source.setEventHandler(handler: action)
        source.resume()
        signalSources.append(source)
    }

    trap(SIGINT) {
        diagnostic("Received stop signal (SIGINT); stopping speech.")
        synthesizer.stopSpeaking(at: .immediate)
        coordinator.cancelled = true
        coordinator.finished = true
    }
    trap(SIGTERM) {
        diagnostic("Received stop signal (SIGTERM); stopping speech.")
        synthesizer.stopSpeaking(at: .immediate)
        coordinator.cancelled = true
        coordinator.finished = true
    }
    trap(SIGTSTP) {
        diagnostic("Paused.")
        _ = synthesizer.pauseSpeaking(at: .word)
    }
    trap(SIGCONT) {
        diagnostic("Resumed.")
        _ = synthesizer.continueSpeaking()
    }

    for sentence in sentences {
        let utterance = AVSpeechUtterance(string: sentence)
        utterance.voice = voice
        if let rate = options.rate {
            utterance.rate = Float(rate)
        }
        synthesizer.speak(utterance)
    }

    let deadline = Date().addingTimeInterval(options.timeoutSeconds)
    while !coordinator.finished && Date() < deadline {
        RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.05))
    }
    signalSources.forEach { $0.cancel() }

    if !coordinator.finished {
        synthesizer.stopSpeaking(at: .immediate)
        throw AppError.timeout("Speaking timed out after \(options.timeoutSeconds) seconds.")
    }

    return SpeakResult(
        completed: !coordinator.cancelled,
        stopped_early: coordinator.cancelled,
        voice_identifier: voice.identifier,
        language: voice.language,
        sentence_count: sentences.count,
        text_length: text.count
    )
}
