import Foundation
import Speech

/// A test seam around the inventory, not an app-global reference counter.
struct ReservationInventory: Sendable {
    var supportedLocale: @Sendable (Locale) async -> Locale?
    var reservedLocales: @Sendable () async -> [Locale]
    var maximum: @Sendable () async -> Int
    var reserve: @Sendable (Locale) async throws -> Bool
    var release: @Sendable (Locale) async throws -> Bool
    var isInstalled: @Sendable (Locale) async -> Bool = { _ in false }
}

struct STTFailure: LocalizedError, Sendable {
    let code: String
    let message: String
    var errorDescription: String? { "[\(code)] \(message)" }

    static func framework(_ code: String, _ message: String, _ error: Error) -> STTFailure {
        let native = error as NSError
        return STTFailure(code: code, message: "\(message): \(native.localizedDescription) (\(native.domain), code \(native.code))")
    }

    static func reservationCode(for error: Error) -> String? {
        let native = error as NSError
        guard native.domain == SFSpeechErrorDomain else { return nil }
        switch native.code {
        case SFSpeechError.Code.tooManyAssetLocalesAllocated.rawValue: return "reservation_capacity"
        case SFSpeechError.Code.cannotAllocateUnsupportedLocale.rawValue: return "unsupported_locale"
        default: return nil
        }
    }
}

func sameSpeechLocale(_ first: Locale, _ second: Locale) -> Bool {
    first.identifier.replacingOccurrences(of: "_", with: "-").lowercased()
        == second.identifier.replacingOccurrences(of: "_", with: "-").lowercased()
}

/// Installation policy seam: offline callers never create an installation
/// request (which itself can reserve locales), not merely skip its download.
func ensureSpeechAssets(
    requireInstalled: Bool,
    installed: () async -> Bool,
    install: () async throws -> Void
) async throws {
    if await installed() { return }
    if requireInstalled {
        throw STTFailure(code: "assets_not_installed", message: "Required Apple speech assets are not installed; no installation request or download was attempted")
    }
    try Task.checkCancellation()
    try await install()
    guard await installed() else {
        throw STTFailure(code: "asset_installation", message: "Apple speech assets remain uninstalled")
    }
}

/// Shield the complete inventory/release/readback phase from caller cancellation.
/// The detached task is ALWAYS joined; the gate stays held until it completes.
func cleanupReservation(owned: Locale?, before: [Locale], inventory: ReservationInventory) async -> [STTFailure] {
    await Task.detached {
        var failures: [STTFailure] = []
        let remaining = await inventory.reservedLocales()
        let unexpected = remaining.filter { !before.contains($0) && $0 != owned }
        if !unexpected.isEmpty {
            failures.append(STTFailure(code: "reservation_ownership", message:
                "Unexpected supporting reservations appeared during setup/work: \(unexpected.map(\.identifier).joined(separator: ", ")). Retained ambiguous entries; inspect --inventory-status before recovery"))
        }
        if let owned {
            do {
                if !(try await inventory.release(owned)) {
                    failures.append(STTFailure(code: "reservation_cleanup", message: "Release returned false for owned supporting locale \(owned.identifier)"))
                }
            } catch {
                failures.append(STTFailure.framework("reservation_cleanup", "Could not release owned supporting locale \(owned.identifier)", error))
            }
            let after = await inventory.reservedLocales()
            let unexpectedAfter = after.filter { !before.contains($0) && $0 != owned }
            if !unexpectedAfter.isEmpty,
               Set(unexpectedAfter.map(\.identifier)) != Set(unexpected.map(\.identifier)) {
                failures.append(STTFailure(code: "reservation_ownership", message:
                    "Unexpected reservations appeared during release/readback: \(unexpectedAfter.map(\.identifier).joined(separator: ", ")). Retained ambiguous entries; no retry or reset was attempted"))
            }
            if after.contains(owned) && !failures.contains(where: { $0.code == "reservation_cleanup" }) {
                failures.append(STTFailure(code: "reservation_cleanup", message: "Owned supporting locale \(owned.identifier) is still reserved after cleanup; no retry was attempted"))
            }
            if !before.allSatisfy({ after.contains($0) }) {
                failures.append(STTFailure(code: "reservation_cleanup", message: "Pre-existing reservation state changed during cleanup; no reset was attempted"))
            }
        }
        return failures
    }.value
}

/// Call only while holding the cross-process gate, through body AND cleanup.
/// Existing reservations are borrowed and never released. A newly created
/// reservation is identified by the actual inventory delta, not the input tag.
func withReservation<T>(
    requested: Locale,
    inventory: ReservationInventory,
    requireInstalled: Bool = false,
    requireExactLocale: Bool = false,
    requireNewReservation: Bool = false,
    event: (String, Locale) -> Void = { _, _ in },
    warning: (String) -> Void,
    body: (Locale) async throws -> T
) async throws -> T {
    try Task.checkCancellation()
    guard let supported = await inventory.supportedLocale(requested) else {
        throw STTFailure(code: "unsupported_locale", message: "Apple SpeechTranscriber does not support locale: \(requested.identifier)")
    }
    if requireExactLocale && !sameSpeechLocale(requested, supported) {
        throw STTFailure(code: "locale_substitution", message: "Requested \(requested.identifier) resolved to \(supported.identifier); exact-locale validation refused")
    }
    if requireInstalled {
        guard await inventory.isInstalled(supported) else {
            throw STTFailure(code: "assets_not_installed", message: "Apple speech assets for \(supported.identifier) are not installed; no reservation or download was attempted")
        }
    }
    let before = await inventory.reservedLocales()
    let acquired: Bool
    do {
        acquired = try await inventory.reserve(supported)
    } catch is CancellationError {
        throw CancellationError()
    } catch {
        let current = await inventory.reservedLocales()
        let maximum = await inventory.maximum()
        let code = STTFailure.reservationCode(for: error) ?? "reservation_failed"
        throw STTFailure.framework(
            code,
            "Could not reserve \(supported.identifier); inventory has \(current.count)/\(maximum) reservations. Existing reservations were not removed",
            error
        )
    }
    var owned: Locale?
    if acquired {
        let after = await inventory.reservedLocales()
        let added = after.filter { !before.contains($0) }
        guard added.count == 1 else {
            // No documented way to identify ownership if a non-cooperating
            // client changes this app's inventory concurrently. Fail closed.
            throw STTFailure(code: "reservation_ownership", message: "Reservation succeeded but its supporting asset locale could not be uniquely identified. Retained reservations; inspect --inventory-status before any manual recovery")
        }
        owned = added[0]
        event("acquired", added[0])
    }

    let outcome: Result<T, Error>
    do {
        try Task.checkCancellation()
        if requireNewReservation && !acquired {
            throw STTFailure(code: "new_reservation_required", message: "\(supported.identifier) was already reserved; borrowed reuse is not newly-owned cleanup evidence")
        }
        outcome = .success(try await body(supported))
    } catch {
        outcome = .failure(error)
    }
    let cleanupFailures = await cleanupReservation(owned: owned, before: before, inventory: inventory)
    if let owned, cleanupFailures.isEmpty { event("released", owned) }
    let finalOutcome: Result<T, Error>
    if case .success = outcome, Task.isCancelled {
        finalOutcome = .failure(CancellationError())
    } else {
        finalOutcome = outcome
    }
    if let cleanupFailure = cleanupFailures.first {
        switch finalOutcome {
        case .success:
            for additional in cleanupFailures.dropFirst() { warning(additional.localizedDescription) }
            throw cleanupFailure
        case .failure:
            for failure in cleanupFailures { warning(failure.localizedDescription) }
        }
    }
    return try finalOutcome.get()
}
