import Testing
@testable import MacSpeechTTSCore

/// Asserts that `body` throws an `AppError` with the given code, recording
/// a failure (rather than crashing) if it throws something else or
/// doesn't throw at all.
func expectAppError<T>(_ code: ErrorCode, _ body: () throws -> T) {
    do {
        _ = try body()
        Issue.record("expected AppError(.\(code)) to be thrown, but no error was thrown")
    } catch let error as AppError {
        #expect(error.code == code)
    } catch {
        Issue.record("expected AppError(.\(code)), got \(error)")
    }
}

@Suite struct OptionsTests {
    @Test func missingOperationIsInvalidArgument() {
        expectAppError(.invalidArgument) { try parseArguments([]) }
    }

    @Test func unknownOperationIsInvalidArgument() {
        expectAppError(.invalidArgument) { try parseArguments(["dance"]) }
    }

    @Test func voicesOperationDoesNotRequireText() throws {
        let options = try parseArguments(["voices"])
        #expect(options.operation == "voices")
        #expect(options.text == nil)
    }

    @Test func personalVoiceStatusOperationDoesNotRequireText() throws {
        let options = try parseArguments(["personal-voice-status"])
        #expect(options.operation == "personal-voice-status")
        #expect(options.text == nil)
    }

    @Test func speakRequiresTextOrStdin() {
        expectAppError(.invalidArgument) { try parseArguments(["speak"]) }
    }

    @Test func speakAcceptsPositionalText() throws {
        let options = try parseArguments(["speak", "hello there"])
        #expect(options.text == "hello there")
        #expect(options.readTextFromStdin == false)
    }

    @Test func textAndStdinTogetherIsRejected() {
        expectAppError(.invalidArgument) { try parseArguments(["speak", "hello", "--stdin"]) }
    }

    @Test func saveRequiresOutput() {
        expectAppError(.invalidArgument) { try parseArguments(["save", "hello"]) }
    }

    @Test func saveWithOutputParsesCleanly() throws {
        let options = try parseArguments(["save", "hello", "--output", "/tmp/out.wav"])
        #expect(options.outputPath == "/tmp/out.wav")
        #expect(options.format == "wav")
    }

    @Test func rateOutOfRangeIsRejected() {
        expectAppError(.invalidArgument) { try parseArguments(["speak", "hi", "--rate", "1.5"]) }
    }

    @Test func rateNotANumberIsRejected() {
        expectAppError(.invalidArgument) { try parseArguments(["speak", "hi", "--rate", "fast"]) }
    }

    @Test func unsupportedFormatIsRejected() {
        expectAppError(.invalidArgument) { try parseArguments(["save", "hi", "--output", "/tmp/o", "--format", "mp3"]) }
    }

    @Test func flagMissingValueIsRejected() {
        expectAppError(.invalidArgument) { try parseArguments(["speak", "hi", "--voice"]) }
    }

    @Test func forceFlagParses() throws {
        let options = try parseArguments(["save", "hi", "--output", "/tmp/o.wav", "--force"])
        #expect(options.force == true)
    }

    @Test func timeoutMustBePositive() {
        expectAppError(.invalidArgument) { try parseArguments(["speak", "hi", "--timeout", "0"]) }
        expectAppError(.invalidArgument) { try parseArguments(["speak", "hi", "--timeout", "-5"]) }
    }

    @Test func resolveTextRejectsWhitespaceOnly() {
        let options = Options(
            operation: "speak", text: "   ", readTextFromStdin: false, voiceIdentifier: nil,
            language: nil, rate: nil, format: "wav", outputPath: nil, force: false,
            timeoutSeconds: defaultTimeoutSeconds
        )
        expectAppError(.invalidArgument) { try resolveText(options) }
    }
}
