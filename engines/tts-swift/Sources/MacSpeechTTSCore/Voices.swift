import AVFoundation

public func listVoices(languageFilter: String?) -> VoicesResult {
    let allVoices = AVSpeechSynthesisVoice.speechVoices()
    let filtered: [AVSpeechSynthesisVoice]
    if let languageFilter {
        filtered = allVoices.filter {
            $0.language == languageFilter || $0.language.hasPrefix(languageFilter + "-")
        }
    } else {
        filtered = allVoices
    }
    let infos = filtered.map { voice in
        VoiceInfo(
            identifier: voice.identifier,
            name: voice.name,
            language: voice.language,
            quality: qualityName(voice.quality),
            gender: genderName(voice.gender),
            is_personal_voice: isPersonalVoice(voice),
            is_novelty_voice: isNoveltyVoice(voice)
        )
    }
    return VoicesResult(voices: infos, count: infos.count)
}

// `AVSpeechSynthesisVoice.voiceTraits` requires macOS 14+; this package's
// minimum deployment target is macOS 13 (see Package.swift), so these
// traits are reported as `false` on macOS 13 rather than failing to build
// or crashing at runtime.
private func isPersonalVoice(_ voice: AVSpeechSynthesisVoice) -> Bool {
    if #available(macOS 14.0, *) {
        return voice.voiceTraits.contains(.isPersonalVoice)
    }
    return false
}

private func isNoveltyVoice(_ voice: AVSpeechSynthesisVoice) -> Bool {
    if #available(macOS 14.0, *) {
        return voice.voiceTraits.contains(.isNoveltyVoice)
    }
    return false
}

private func qualityName(_ quality: AVSpeechSynthesisVoiceQuality) -> String {
    switch quality {
    case .default: return "default"
    case .enhanced: return "enhanced"
    case .premium: return "premium"
    @unknown default: return "unknown"
    }
}

private func genderName(_ gender: AVSpeechSynthesisVoiceGender) -> String {
    switch gender {
    case .unspecified: return "unspecified"
    case .male: return "male"
    case .female: return "female"
    @unknown default: return "unknown"
    }
}

/// Reads (never requests) the current Personal Voice authorization
/// status. `AVSpeechSynthesizer.personalVoiceAuthorizationStatus`
/// requires macOS 14+ — guarded here since this package's deployment
/// floor is macOS 13 (see Package.swift); reports `"unsupported"` on
/// macOS 13, which is an accurate practical outcome even though it
/// conflates "API unavailable" with the API's own `.unsupported` case.
/// Verified during Phase 5 to return instantly on macOS 14+ rather than
/// hanging, from this compiled, unsigned binary specifically (not just a
/// `swift -e` script, which has no explicit deployment-target floor and
/// would not have caught this availability requirement).
///
/// There is deliberately no `requestPersonalVoiceAuthorization` wrapper
/// here: that call's completion handler was verified during Phase 5 to
/// never fire from this bare command-line binary, most likely because it
/// has no app bundle/`Info.plist` and therefore no
/// `NSPersonalVoiceUsageDescription` for the system to show in an
/// authorization prompt. Per PLAN.md Phase 5 ("avoid depending on
/// private APIs... Document that availability and use are controlled by
/// Apple and system settings"), this engine only *reports* status; it
/// never implies it can request, create, or extract a Personal Voice
/// itself. See docs/tts-engine.md.
public func personalVoiceAuthorizationStatusString() -> String {
    if #available(macOS 14.0, *) {
        switch AVSpeechSynthesizer.personalVoiceAuthorizationStatus {
        case .notDetermined: return "not_determined"
        case .denied: return "denied"
        case .unsupported: return "unsupported"
        case .authorized: return "authorized"
        @unknown default: return "unknown"
        }
    }
    return "unsupported"
}

/// Resolves a voice honestly: an explicit `--voice` identifier or
/// `--language` locale that does not match a real, installed voice is
/// reported as `invalid_argument`, not silently substituted. With neither
/// option, the system's default voice for the current locale is used.
public func resolveVoice(identifier: String?, language: String?) throws -> AVSpeechSynthesisVoice {
    if let identifier {
        guard let voice = AVSpeechSynthesisVoice(identifier: identifier) else {
            throw AppError.invalidArgument(
                "No voice found with identifier '\(identifier)'.",
                remedy: "Run `mac-speech-tts voices` to list available identifiers."
            )
        }
        return voice
    }
    if let language {
        guard let voice = AVSpeechSynthesisVoice(language: language) else {
            throw AppError.invalidArgument(
                "No voice found for language '\(language)'.",
                remedy: "Run `mac-speech-tts voices` to list available languages."
            )
        }
        return voice
    }
    if let defaultVoice = AVSpeechSynthesisVoice(language: nil) {
        return defaultVoice
    }
    guard let fallback = AVSpeechSynthesisVoice.speechVoices().first else {
        throw AppError(
            code: .unsupportedPlatform,
            message: "No speech voices are available on this system.",
            remedy: "Check System Settings > Accessibility > Spoken Content, or install additional voices."
        )
    }
    return fallback
}
