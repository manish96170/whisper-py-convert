import Foundation
import Speech

/// A test seam around the inventory, not an app-global reference counter.
struct ReservationInventory: Sendable {
    var supportedLocale: @Sendable (Locale) async -> Locale?
    var reservedLocales: @Sendable () async -> [Locale]
    var maximum: @Sendable () async -> Int
    var reserve: @Sendable (Locale) async throws -> Bool
    var release: @Sendable (Locale) async throws -> Bool
}

struct STTFailure: LocalizedError {
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

/// Call only while holding the cross-process gate, through body AND cleanup.
/// Existing reservations are borrowed and never released. A newly created
/// reservation is identified by the actual inventory delta, not the input tag.
func withReservation<T>(
    requested: Locale,
    inventory: ReservationInventory,
    warning: (String) -> Void,
    body: (Locale) async throws -> T
) async throws -> T {
    try Task.checkCancellation()
    guard let supported = await inventory.supportedLocale(requested) else {
        throw STTFailure(code: "unsupported_locale", message: "Apple SpeechTranscriber does not support locale: \(requested.identifier)")
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
    }

    let outcome: Result<T, Error>
    do {
        try Task.checkCancellation()
        outcome = .success(try await body(supported))
    } catch {
        outcome = .failure(error)
    }
    // Await cleanup even when the caller is cancelled. Apple release itself
    // is nonthrowing; the throwing seam also tests preservation of primary errors.
    var cleanupFailures: [Error] = []
    let remaining = await inventory.reservedLocales()
    let unexpected = remaining.filter { !before.contains($0) && $0 != owned }
    if !unexpected.isEmpty {
        // Installation-request creation itself can reserve missing locales.
        // For our one explicitly reserved transcriber it must not introduce
        // extra entries. Do not silently leak or guess ownership if it does.
        cleanupFailures.append(STTFailure(code: "reservation_ownership", message:
            "Unexpected supporting reservations appeared during setup/work: \(unexpected.map(\.identifier).joined(separator: ", ")). Retained ambiguous entries; inspect --inventory-status before recovery"))
    }
    if let owned {
        do {
            if !(try await inventory.release(owned)) {
                cleanupFailures.append(STTFailure(code: "reservation_cleanup", message: "Release returned false for owned supporting locale \(owned.identifier)"))
            }
        } catch {
            cleanupFailures.append(STTFailure.framework("reservation_cleanup", "Could not release owned supporting locale \(owned.identifier)", error))
        }
    }
    if let cleanupFailure = cleanupFailures.first {
        switch outcome {
        case .success:
            for additional in cleanupFailures.dropFirst() { warning(additional.localizedDescription) }
            throw cleanupFailure
        case .failure:
            for failure in cleanupFailures { warning(failure.localizedDescription) }
        }
    }
    return try outcome.get()
}
