import AVFoundation
import Foundation

/// A fully explicit, verified audio container/codec specification.
///
/// `PLAN.md` section 5.1 requires documenting codec/container behavior
/// rather than inferring a format solely from a filename extension. During
/// Phase 2 discovery, writing PCM settings that did not match the chosen
/// container (e.g. big-endian samples into a `.wav` file) silently produced
/// a file with a correct-looking header but zero audio data. To make that
/// mistake structurally impossible, every supported `--format` maps to one
/// fixed, tested settings dictionary here, and the output path's extension
/// is validated against it (see `resolveOutputURL` in Synthesize.swift)
/// rather than used to infer the format.
public struct AudioFormatSpec {
    public let name: String
    public let fileExtension: String
    public let settings: [String: Any]
    public let sampleRate: Double
    public let channels: Int
    public let bitDepth: Int
}

public let supportedAudioFormats = ["wav", "aiff", "caf"]

public func audioFormatSpec(named name: String) throws -> AudioFormatSpec {
    switch name {
    case "wav":
        // Linear PCM, little-endian, 16-bit — the most portable choice,
        // verified with `afinfo`/`file` during Phase 2 discovery.
        return AudioFormatSpec(
            name: "wav",
            fileExtension: "wav",
            settings: [
                AVFormatIDKey: kAudioFormatLinearPCM,
                AVSampleRateKey: 22_050.0,
                AVNumberOfChannelsKey: 1,
                AVLinearPCMBitDepthKey: 16,
                AVLinearPCMIsFloatKey: false,
                AVLinearPCMIsBigEndianKey: false,
            ],
            sampleRate: 22_050.0,
            channels: 1,
            bitDepth: 16
        )
    case "aiff":
        // Linear PCM, big-endian, 16-bit — AIFF's native byte order.
        return AudioFormatSpec(
            name: "aiff",
            fileExtension: "aiff",
            settings: [
                AVFormatIDKey: kAudioFormatLinearPCM,
                AVSampleRateKey: 22_050.0,
                AVNumberOfChannelsKey: 1,
                AVLinearPCMBitDepthKey: 16,
                AVLinearPCMIsFloatKey: false,
                AVLinearPCMIsBigEndianKey: true,
            ],
            sampleRate: 22_050.0,
            channels: 1,
            bitDepth: 16
        )
    case "caf":
        // 32-bit float — the synthesizer's native sample representation,
        // for callers that want to avoid any bit-depth reduction.
        return AudioFormatSpec(
            name: "caf",
            fileExtension: "caf",
            settings: [
                AVFormatIDKey: kAudioFormatLinearPCM,
                AVSampleRateKey: 22_050.0,
                AVNumberOfChannelsKey: 1,
                AVLinearPCMBitDepthKey: 32,
                AVLinearPCMIsFloatKey: true,
                AVLinearPCMIsBigEndianKey: false,
            ],
            sampleRate: 22_050.0,
            channels: 1,
            bitDepth: 32
        )
    default:
        throw AppError.invalidArgument(
            "Unsupported --format '\(name)'.",
            remedy: "Supported formats: \(supportedAudioFormats.joined(separator: ", "))."
        )
    }
}
