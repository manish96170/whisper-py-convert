import AVFoundation
import Testing
@testable import MacSpeechTTSCore

/// These tests exercise the real `AVSpeechSynthesizer` API end-to-end
/// (voice discovery, file synthesis) and therefore run only on macOS with
/// real system voices — consistent with PLAN.md Phase 2's requirement for
/// "integration tests for voice discovery and file output."
///
/// There is deliberately no automated integration test for `speak`'s live
/// playback path: it would produce audible sound every time `swift test`
/// runs. `speak`'s stop/pause/resume signal behavior was verified manually
/// during Phase 2 discovery and is documented in docs/tts-engine.md; the
/// shared per-sentence synthesis logic it depends on (`splitIntoSentences`,
/// `resolveVoice`) is covered by the tests below and in SentencesTests.swift.
@Suite struct IntegrationTests {
    @Test func listVoicesReturnsAtLeastOneVoice() {
        let result = listVoices(languageFilter: nil)
        #expect(result.count > 0)
        #expect(result.voices.count == result.count)
    }

    @Test func resolveVoiceDefaultSucceeds() throws {
        let voice = try resolveVoice(identifier: nil, language: nil)
        #expect(!voice.identifier.isEmpty)
    }

    /// Verifies the read-only status check completes immediately and
    /// returns one of the documented values — it must never hang the way
    /// `requestPersonalVoiceAuthorization`'s completion handler was found
    /// to during Phase 5 discovery (see docs/tts-engine.md).
    @Test func personalVoiceAuthorizationStatusStringReturnsADocumentedValue() {
        let status = personalVoiceAuthorizationStatusString()
        #expect(["not_determined", "denied", "unsupported", "authorized", "unknown"].contains(status))
    }

    @Test func resolveVoiceUnknownIdentifierThrows() {
        expectAppError(.invalidArgument) {
            try resolveVoice(identifier: "com.example.not-a-real-voice", language: nil)
        }
    }

    @Test func saveProducesAPlayableFile() throws {
        let tempDir = try makeTempDirectory()
        defer { try? FileManager.default.removeItem(at: tempDir) }
        let outputPath = tempDir.appendingPathComponent("short.wav").path

        let options = saveOptions(text: "Short integration test phrase.", outputPath: outputPath)
        let result = try runSave(options)

        #expect(FileManager.default.fileExists(atPath: result.output_path))
        #expect(result.duration_seconds > 0)
        #expect(result.file_size_bytes > 0)

        let readBack = try AVAudioFile(forReading: URL(fileURLWithPath: result.output_path))
        #expect(readBack.fileFormat.sampleRate == 22_050.0)
        #expect(readBack.length > 0)
    }

    /// Regression test for a Phase 2 discovery finding: `AVAudioFile`
    /// infers its *container* from the destination URL's file extension,
    /// not from `formatSpec.settings`. Writing to a temp path ending in a
    /// generic ".tmp" suffix silently produced a CAF container inside a
    /// file later moved to a ".wav" name — `AVAudioFile(forReading:)`
    /// alone does not catch this, since it can read a mislabeled CAF file
    /// just fine. Checking the real container magic bytes is the only way
    /// to catch a mismatch between the declared format and the file on
    /// disk.
    @Test func saveWritesTheDeclaredContainerNotJustTheDeclaredSampleFormat() throws {
        let tempDir = try makeTempDirectory()
        defer { try? FileManager.default.removeItem(at: tempDir) }

        let wavPath = tempDir.appendingPathComponent("container.wav").path
        let wavResult = try runSave(saveOptions(text: "Container check.", outputPath: wavPath))
        #expect(try magicBytes(of: wavResult.output_path, count: 4) == Array("RIFF".utf8))

        let aiffPath = tempDir.appendingPathComponent("container.aiff").path
        let aiffResult = try runSave(saveOptions(text: "Container check.", outputPath: aiffPath, format: "aiff"))
        #expect(try magicBytes(of: aiffResult.output_path, count: 4) == Array("FORM".utf8))

        let cafPath = tempDir.appendingPathComponent("container.caf").path
        let cafResult = try runSave(saveOptions(text: "Container check.", outputPath: cafPath, format: "caf"))
        #expect(try magicBytes(of: cafResult.output_path, count: 4) == Array("caff".utf8))
    }

    @Test func saveRefusesToOverwriteExistingFileByDefault() throws {
        let tempDir = try makeTempDirectory()
        defer { try? FileManager.default.removeItem(at: tempDir) }
        let outputPath = tempDir.appendingPathComponent("exists.wav").path
        FileManager.default.createFile(atPath: outputPath, contents: Data("placeholder".utf8))

        let options = saveOptions(text: "Should not overwrite.", outputPath: outputPath)
        expectAppError(.outputExists) { try runSave(options) }
        let remainingData = try Data(contentsOf: URL(fileURLWithPath: outputPath))
        #expect(remainingData == Data("placeholder".utf8))
    }

    @Test func saveWithForceOverwritesExistingFile() throws {
        let tempDir = try makeTempDirectory()
        defer { try? FileManager.default.removeItem(at: tempDir) }
        let outputPath = tempDir.appendingPathComponent("overwrite.wav").path
        FileManager.default.createFile(atPath: outputPath, contents: Data("placeholder".utf8))

        var options = saveOptions(text: "This should overwrite the placeholder.", outputPath: outputPath)
        options.force = true
        let result = try runSave(options)
        #expect(result.file_size_bytes > "placeholder".utf8.count)
    }

    @Test func saveWithMismatchedExtensionIsRejected() throws {
        let tempDir = try makeTempDirectory()
        defer { try? FileManager.default.removeItem(at: tempDir) }
        let outputPath = tempDir.appendingPathComponent("mismatch.aiff").path

        let options = saveOptions(text: "Mismatched extension test.", outputPath: outputPath, format: "wav")
        expectAppError(.invalidArgument) { try runSave(options) }
    }

    @Test func saveAppendsCanonicalExtensionWhenOmitted() throws {
        let tempDir = try makeTempDirectory()
        defer { try? FileManager.default.removeItem(at: tempDir) }
        let outputPathWithoutExtension = tempDir.appendingPathComponent("no-extension").path

        let options = saveOptions(text: "Append extension test.", outputPath: outputPathWithoutExtension)
        let result = try runSave(options)
        #expect(result.output_path.hasSuffix(".wav"))
    }

    /// Regression test for the Phase 2 discovery finding documented in
    /// docs/tts-engine.md: a single multi-sentence `AVSpeechUtterance`
    /// passed to `AVSpeechSynthesizer.write()` silently stopped producing
    /// real speech after the first sentence, while still returning a
    /// plausible-length tail of (silent) audio. If sentence-level chunking
    /// ever regresses, this test should fail because the combined duration
    /// would collapse toward roughly one sentence's duration instead of
    /// the sum of all three.
    @Test func saveSynthesizesEveryQueuedSentenceNotJustTheFirst() throws {
        let sentenceA = "The quick brown fox jumps over the lazy dog near the riverbank every single morning before the sun fully rises above the eastern hills."
        let sentenceB = "Local speech synthesis on Apple Silicon runs entirely offline once the system voices are installed, which means no audio or text ever leaves this machine during a normal narration task."
        let sentenceC = "This paragraph exists only to measure whether a longer passage of text is spoken in full, without being silently truncated partway through by the synthesizer or the file writer."

        let tempDir = try makeTempDirectory()
        defer { try? FileManager.default.removeItem(at: tempDir) }

        func duration(for text: String, name: String) throws -> Double {
            let options = saveOptions(text: text, outputPath: tempDir.appendingPathComponent(name).path)
            return try runSave(options).duration_seconds
        }

        let durationA = try duration(for: sentenceA, name: "a.wav")
        let durationB = try duration(for: sentenceB, name: "b.wav")
        let durationC = try duration(for: sentenceC, name: "c.wav")
        let combinedDuration = try duration(for: "\(sentenceA) \(sentenceB) \(sentenceC)", name: "combined.wav")

        let sumOfParts = durationA + durationB + durationC
        #expect(
            combinedDuration > sumOfParts * 0.7,
            "combined save duration (\(combinedDuration)s) looks truncated relative to its parts (sum \(sumOfParts)s) — the per-sentence chunking workaround may have regressed"
        )
    }
}

private func saveOptions(text: String, outputPath: String, format: String = "wav") -> Options {
    Options(
        operation: "save",
        text: text,
        readTextFromStdin: false,
        voiceIdentifier: nil,
        language: nil,
        rate: nil,
        format: format,
        outputPath: outputPath,
        force: false,
        timeoutSeconds: 30
    )
}

private func makeTempDirectory() throws -> URL {
    let url = FileManager.default.temporaryDirectory.appendingPathComponent("mac-speech-tts-tests-\(UUID().uuidString)")
    try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    return url
}

private func magicBytes(of path: String, count: Int) throws -> [UInt8] {
    let handle = try FileHandle(forReadingFrom: URL(fileURLWithPath: path))
    defer { try? handle.close() }
    return Array(handle.readData(ofLength: count))
}
