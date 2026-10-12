import Foundation

struct AssetSetupCommand: Sendable {
    let language: String
    let confirmation: String?

    static func parse(_ arguments: [String]) throws -> Self? {
        guard arguments.contains("--install-assets") else { return nil }
        var language = "en-US"
        var confirmation: String?
        var seen: Set<String> = []
        var index = 0
        while index < arguments.count {
            let option = arguments[index]
            guard seen.insert(option).inserted else { throw invalid("Duplicate asset setup option: \(option)") }
            switch option {
            case "--install-assets": break
            case "--language", "--confirm-download":
                index += 1
                guard index < arguments.count, !arguments[index].hasPrefix("--") else { throw invalid("Missing \(option) value") }
                if option == "--language" { language = arguments[index] } else { confirmation = arguments[index] }
            default: throw invalid("Asset setup accepts only --language and --confirm-download; no audio or release options")
            }
            index += 1
        }
        return Self(language: language, confirmation: confirmation)
    }

    private static func invalid(_ message: String) -> STTFailure {
        STTFailure(code: "asset_installation", message: message)
    }
}

struct AssetSetupReport: Encodable, Sendable {
    let requested_locale: String
    let supported_locale: String
    let preview: Bool
    let installed_before: Bool
    let installed_after: Bool
    let installation_request_used: Bool
    let retained_actual_locale: String?
    let reserved_locales: [String]
    let maximum_reserved_locales: Int
    let warning: String
}

/// Explicit user setup intent, not a transcription lifetime. Preview is read-only.
/// Confirmed success deliberately retains a reservation to keep assets subscribed.
/// Failures/cancellation clean up only new, uniquely established ownership.
func setupSpeechAssets(_ command: AssetSetupCommand, inventory: ReservationInventory,
                       warning: (String) -> Void,
                       publish: (AssetSetupReport) async throws -> Void = { _ in },
                       install: (Locale) async throws -> Bool) async throws -> AssetSetupReport {
    try Task.checkCancellation()
    guard let supported = await inventory.supportedLocale(Locale(identifier: command.language)) else {
        throw STTFailure(code: "unsupported_locale", message: "Apple speech assets do not support requested locale \(command.language)")
    }
    let before = await inventory.reservedLocales()
    let wasInstalled = await inventory.isInstalled(supported)
    let note = "Explicit setup may download missing Apple models and retains the supporting reservation on success. Capacity is device-specific; no other reservations are evicted."
    if command.confirmation == nil {
        let report = await AssetSetupReport(requested_locale: command.language, supported_locale: supported.identifier,
            preview: true, installed_before: wasInstalled, installed_after: wasInstalled,
            installation_request_used: false, retained_actual_locale: nil,
            reserved_locales: before.map(\.identifier).sorted(), maximum_reserved_locales: inventory.maximum(), warning: note)
        try await publish(report)
        return report
    }
    guard let confirmation = command.confirmation,
          sameSpeechLocale(Locale(identifier: confirmation), supported) else {
        throw STTFailure(code: "asset_installation", message: "Confirm the displayed supported locale exactly with --confirm-download \(supported.identifier); no reservation or download was attempted")
    }
    try Task.checkCancellation()
    let acquired: Bool
    do { acquired = try await inventory.reserve(supported) }
    catch is CancellationError { throw CancellationError() }
    catch { throw STTFailure.framework(STTFailure.reservationCode(for: error) ?? "reservation_failed", "Could not reserve assets for explicit setup; no download started", error) }
    let afterReserve = await inventory.reservedLocales()
    let delta = afterReserve.filter { !before.contains($0) }
    guard (acquired && delta.count == 1) || (!acquired && delta.isEmpty) else {
        throw STTFailure(code: "reservation_ownership", message: "Setup reservation ownership is ambiguous; state retained, no download or reset attempted")
    }
    let owned = acquired ? delta[0] : nil
    do {
        let expected = Set((before + (owned.map { [$0] } ?? [])).map(\.identifier))
        guard Set(afterReserve.map(\.identifier)) == expected else {
            throw STTFailure(code: "reservation_ownership", message: "Pre-existing reservation state changed during setup acquisition; no installer was invoked")
        }
        try Task.checkCancellation()
        var requestedInstall = false
        if !(await inventory.isInstalled(supported)) { requestedInstall = try await install(supported) }
        guard await inventory.isInstalled(supported) else {
            throw STTFailure(code: "asset_installation", message: "Explicit setup did not make \(supported.identifier) ready")
        }
        let after = await inventory.reservedLocales()
        guard Set(after.map(\.identifier)) == expected else {
            throw STTFailure(code: "reservation_ownership", message: "Unexpected reservation state after setup; no automatic correction attempted")
        }
        let maximum = await inventory.maximum()
        try Task.checkCancellation()
        let report = AssetSetupReport(requested_locale: command.language, supported_locale: supported.identifier,
            preview: false, installed_before: wasInstalled, installed_after: true,
            installation_request_used: requestedInstall, retained_actual_locale: owned?.identifier,
            reserved_locales: after.map(\.identifier).sorted(), maximum_reserved_locales: maximum, warning: note)
        // Explicit retention commits only after reporting and cancellation checks.
        try await publish(report)
        try Task.checkCancellation()
        return report
    } catch {
        for failure in await cleanupReservation(owned: owned, before: before, inventory: inventory) {
            warning(failure.localizedDescription)
        }
        if error is CancellationError { throw CancellationError() }
        if let failure = error as? STTFailure { throw failure }
        throw STTFailure.framework(STTFailure.reservationCode(for: error) ?? "asset_installation", "Explicit asset setup failed", error)
    }
}
