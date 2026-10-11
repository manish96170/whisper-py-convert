import Testing
@testable import MacSpeechTTSCore

@Suite struct ErrorsTests {
    @Test func exitCodesMatchPythonMapping() {
        // Must stay in sync with EXIT_CODE_BY_ERROR in python/mac_speech/errors.py.
        #expect(ErrorCode.invalidArgument.exitCode == 2)
        #expect(ErrorCode.outputExists.exitCode == 3)
        #expect(ErrorCode.engineNotFound.exitCode == 4)
        #expect(ErrorCode.unsupportedPlatform.exitCode == 4)
        #expect(ErrorCode.protocolVersionMismatch.exitCode == 5)
        #expect(ErrorCode.nativeProcessError.exitCode == 6)
        #expect(ErrorCode.timeout.exitCode == 124)
        #expect(ErrorCode.cancelled.exitCode == 130)
        #expect(ErrorCode.notImplemented.exitCode == 10)
        #expect(ErrorCode.internalError.exitCode == 1)
    }

    @Test func rawValuesMatchPythonErrorCodeStrings() {
        #expect(ErrorCode.invalidArgument.rawValue == "invalid_argument")
        #expect(ErrorCode.outputExists.rawValue == "output_exists")
        #expect(ErrorCode.engineNotFound.rawValue == "engine_not_found")
        #expect(ErrorCode.unsupportedPlatform.rawValue == "unsupported_platform")
        #expect(ErrorCode.protocolVersionMismatch.rawValue == "protocol_version_mismatch")
        #expect(ErrorCode.nativeProcessError.rawValue == "native_process_error")
        #expect(ErrorCode.timeout.rawValue == "timeout")
        #expect(ErrorCode.cancelled.rawValue == "cancelled")
        #expect(ErrorCode.notImplemented.rawValue == "not_implemented")
        #expect(ErrorCode.internalError.rawValue == "internal_error")
    }
}
