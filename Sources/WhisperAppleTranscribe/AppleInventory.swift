import Foundation
import Speech

let appleInventory = ReservationInventory(
    supportedLocale: { await SpeechTranscriber.supportedLocale(equivalentTo: $0) },
    reservedLocales: { await AssetInventory.reservedLocales },
    maximum: { AssetInventory.maximumReservedLocales },
    reserve: { try await AssetInventory.reserve(locale: $0) },
    release: { await AssetInventory.release(reservedLocale: $0) }
)

private struct InventoryStatus: Encodable {
    let available: Bool
    let supported_locale: String?
    let installed: Bool
    let reserved_locales: [String]
    let maximum_reserved_locales: Int

    enum CodingKeys: String, CodingKey {
        case available, supported_locale, installed, reserved_locales, maximum_reserved_locales
    }
    func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        try values.encode(available, forKey: .available)
        try values.encode(supported_locale, forKey: .supported_locale)
        try values.encode(installed, forKey: .installed)
        try values.encode(reserved_locales, forKey: .reserved_locales)
        try values.encode(maximum_reserved_locales, forKey: .maximum_reserved_locales)
    }
}

/// Read-only, in THIS executable's identity. Never installs/reserves/releases.
func inventoryStatus(language: String) async throws {
    let available = SpeechTranscriber.isAvailable
    let supported = available ? await SpeechTranscriber.supportedLocale(equivalentTo: Locale(identifier: language)) : nil
    var installed = false
    if let supported {
        installed = await AssetInventory.status(forModules: [SpeechTranscriber(locale: supported, preset: .transcription)]) == .installed
    }
    let status = await InventoryStatus(
        available: available, supported_locale: supported?.identifier, installed: installed,
        reserved_locales: AssetInventory.reservedLocales.map(\.identifier).sorted(),
        maximum_reserved_locales: AssetInventory.maximumReservedLocales
    )
    try await writeOutput(JSONEncoder().encode(status) + Data("\n".utf8))
}
