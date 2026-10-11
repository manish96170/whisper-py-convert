// swift-tools-version: 6.4

import PackageDescription

// This is a separate SwiftPM package, deliberately not merged into the
// root `Package.swift` that builds the existing `whisper-py-convert-apple`
// STT binary. See docs/decisions/ADR-001-repository-and-module-boundaries.md
// for why TTS lives in its own build graph, and docs/platform-support.md for
// why its minimum macOS version (13.0) is intentionally lower than the STT
// target's (27.0): AVSpeechSynthesizer's file-synthesis API only requires
// macOS 13+, and this package must not inherit a stricter requirement just
// because it shares a repository with the STT engine.
let package = Package(
    name: "mac-speech-tts",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "mac-speech-tts", targets: ["MacSpeechTTS"])
    ],
    targets: [
        .target(name: "MacSpeechTTSCore"),
        .executableTarget(name: "MacSpeechTTS", dependencies: ["MacSpeechTTSCore"]),
        .testTarget(name: "MacSpeechTTSCoreTests", dependencies: ["MacSpeechTTSCore"]),
    ]
)
