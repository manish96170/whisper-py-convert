// swift-tools-version: 6.4

import PackageDescription

let package = Package(
    name: "whisper-py-convert-apple",
    platforms: [.macOS(.v27)],
    products: [
        .executable(name: "whisper-py-convert-apple", targets: ["WhisperAppleTranscribe"])
    ],
    targets: [
        .executableTarget(name: "WhisperAppleTranscribe")
    ]
)
