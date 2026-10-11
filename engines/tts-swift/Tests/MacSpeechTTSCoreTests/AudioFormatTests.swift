import AVFoundation
import Testing
@testable import MacSpeechTTSCore

@Suite struct AudioFormatTests {
    @Test func wavSpec() throws {
        let spec = try audioFormatSpec(named: "wav")
        #expect(spec.fileExtension == "wav")
        #expect(spec.sampleRate == 22_050.0)
        #expect(spec.channels == 1)
        #expect(spec.bitDepth == 16)
        #expect(spec.settings[AVLinearPCMIsBigEndianKey] as? Bool == false)
    }

    @Test func aiffSpecIsBigEndian() throws {
        let spec = try audioFormatSpec(named: "aiff")
        #expect(spec.fileExtension == "aiff")
        #expect(spec.settings[AVLinearPCMIsBigEndianKey] as? Bool == true)
    }

    @Test func cafSpecIsFloat32() throws {
        let spec = try audioFormatSpec(named: "caf")
        #expect(spec.bitDepth == 32)
        #expect(spec.settings[AVLinearPCMIsFloatKey] as? Bool == true)
    }

    @Test func unsupportedFormatThrows() {
        expectAppError(.invalidArgument) { try audioFormatSpec(named: "mp3") }
    }
}
