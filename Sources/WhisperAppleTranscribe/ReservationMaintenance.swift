import Foundation

struct ReservationMaintenanceCommand: Sendable {
    let action: String
    let target: String?
    let dryRun: Bool

    private init(action: String, target: String?, dryRun: Bool) {
        self.action = action
        self.target = target
        self.dryRun = dryRun
    }

    /// Only this explicit command family can release pre-existing reservations.
    /// All argument checks finish before any framework mutation.
    static func parse(_ arguments: [String]) throws -> Self? {
        guard arguments.contains("--reservation-maintenance") else { return nil }
        var action: String?
        var target: String?
        var confirmation: String?
        var confirmUnused = false
        var dryRun = false
        var allowDefault = false
        var index = 0
        var seen: Set<String> = []
        while index < arguments.count {
            let flag = arguments[index]
            guard seen.insert(flag).inserted else { throw invalid("Duplicate maintenance option: \(flag)") }
            switch flag {
            case "--reservation-maintenance", "--reserved-locale", "--confirm-release":
                index += 1
                guard index < arguments.count, !arguments[index].hasPrefix("--") else { throw invalid("Missing value for \(flag)") }
                switch flag {
                case "--reservation-maintenance": action = arguments[index]
                case "--reserved-locale": target = arguments[index]
                default: confirmation = arguments[index]
                }
            case "--confirm-unused": confirmUnused = true
            case "--dry-run": dryRun = true
            case "--allow-default-release": allowDefault = true
            default: throw invalid("Unknown maintenance option: \(flag); no audio, wildcards or release-all are accepted")
            }
            index += 1
        }
        guard let action, ["inspect", "release"].contains(action) else { throw invalid("Maintenance action must be inspect or release") }
        if action == "inspect" {
            guard target == nil, confirmation == nil, !confirmUnused, !allowDefault else { throw invalid("inspect accepts no release options") }
            return Self(action: action, target: nil, dryRun: true)
        }
        guard let target, !target.isEmpty,
              !target.contains(where: { $0.isWhitespace || $0 == "*" || $0 == "?" || $0 == "," }) else {
            throw invalid("release requires one exact --reserved-locale from the inventory")
        }
        if confirmation == nil {
            guard !confirmUnused, !allowDefault else { throw invalid("Unconfirmed release options are invalid; preview changes nothing") }
            return Self(action: action, target: target, dryRun: true)
        }
        guard confirmation == target, confirmUnused, !dryRun else {
            throw invalid("Release requires matching --confirm-release and --confirm-unused, without --dry-run")
        }
        if sameSpeechLocale(Locale(identifier: target), Locale(identifier: "en-US")) && !allowDefault {
            throw invalid("The default en_US reservation requires additional --allow-default-release confirmation")
        }
        return Self(action: action, target: target, dryRun: false)
    }

    private static func invalid(_ message: String) -> STTFailure {
        STTFailure(code: "reservation_maintenance", message: message)
    }
}

struct ReservationSnapshot: Encodable, Sendable {
    let reserved_locales: [String]
    let maximum_reserved_locales: Int
    /// Exact installed asset status, not a nearby-region fallback.
    let installed_assets: [String: Bool]
}

struct ReservationMaintenanceReport: Encodable, Sendable {
    let action: String
    let target: String?
    let dry_run: Bool
    let release_attempted: Bool
    let release_reported: Bool?
    let verified: Bool
    let before: ReservationSnapshot
    let after: ReservationSnapshot?
    let warning: String
}

private func snapshot(_ locales: [Locale], inventory: ReservationInventory, additional: Locale? = nil) async -> ReservationSnapshot {
    var installed: [String: Bool] = [:]
    for locale in locales + (additional.map { [$0] } ?? []) {
        if installed[locale.identifier] == nil {
            installed[locale.identifier] = await inventory.isInstalled(locale)
        }
    }
    return await ReservationSnapshot(reserved_locales: locales.map(\.identifier).sorted(),
                                     maximum_reserved_locales: inventory.maximum(), installed_assets: installed)
}

/// Caller holds ReservationGate across preview, action, readback and reporting.
/// The real API is nonthrowing; the throwing inventory seam covers framework
/// failures without retries/rollback. This function never reserves or installs.
func maintainReservation(_ command: ReservationMaintenanceCommand, inventory: ReservationInventory) async throws -> ReservationMaintenanceReport {
    try Task.checkCancellation()
    let locales = await inventory.reservedLocales()
    let before = await snapshot(locales, inventory: inventory)
    let warning = "Release unsubscribes dependent speech assets and can affect offline availability. Confirm the target is unused and old/non-cooperating STT invocations are stopped. No downloads, automatic rollback or release-all."
    let target = command.target
    let matches = locales.filter { $0.identifier == target }
    if command.dryRun {
        if let target, matches.count != 1 {
            throw STTFailure(code: "reservation_maintenance", message: "\(target) is not one exact current reserved locale; use inspect, not equivalent-locale guessing")
        }
        return ReservationMaintenanceReport(action: command.action, target: target, dry_run: true,
            release_attempted: false, release_reported: nil, verified: true, before: before, after: nil, warning: warning)
    }
    guard let target, matches.count <= 1 else {
        throw STTFailure(code: "reservation_maintenance", message: "Ambiguous maintenance target; no release was attempted")
    }
    if matches.isEmpty {
        // Cannot prove whether this is a repeat, a typo or an alias. Refuse it
        // without mutation instead of claiming a verified exact-target release.
        throw STTFailure(code: "reservation_maintenance", message: "\(target) is not one exact current reserved locale; inspect before confirming a target. No release was attempted")
    }
    try Task.checkCancellation()
    let actual = matches[0]
    // Once the confirmed mutation is admitted, cancellation cannot abandon its
    // release/readback phase. ALWAYS await the independent task before unlocking.
    return try await Task.detached {
        let released: Bool
        do { released = try await inventory.release(actual) }
        catch { throw STTFailure.framework("reservation_maintenance", "Targeted release failed; no retry or reset was attempted", error) }
        let afterLocales = await inventory.reservedLocales()
        let after = await snapshot(afterLocales, inventory: inventory, additional: actual)
        let expected = before.reserved_locales.filter { $0 != target }
        // false is legitimate if a non-cooperating client already removed it.
        // Both true/false require this readback, not an English-message guess.
        let verified = after.reserved_locales == expected
        return ReservationMaintenanceReport(action: command.action, target: target, dry_run: false,
            release_attempted: true, release_reported: released, verified: verified, before: before, after: after, warning: warning)
    }.value
}
