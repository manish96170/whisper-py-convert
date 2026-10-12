import Foundation
import Speech
import Testing
@testable import WhisperAppleTranscribe

private actor SetupInventory {
    var locales: [Locale]
    var ready = false
    var cached = false
    var capacityError = false
    var reserveCount = 0
    var releaseCount = 0
    var removeExistingOnReserve = false
    init(existing: [String] = ["en_US"], cached: Bool = false, ready: Bool = false) {
        locales = existing.map { Locale(identifier: $0) }; self.cached = cached; self.ready = ready
    }
    func getLocales() -> [Locale] { locales }
    func isReady() -> Bool { ready }
    func markInstalled() { ready = true }
    func failCapacity() { capacityError = true }
    func loseExistingOnReserve() { removeExistingOnReserve = true }
    func counts() -> (Int, Int) { (reserveCount, releaseCount) }
    func reserve(_ locale: Locale) throws -> Bool {
        reserveCount += 1
        if capacityError { throw NSError(domain: SFSpeechErrorDomain, code: SFSpeechError.Code.tooManyAssetLocalesAllocated.rawValue) }
        if locales.contains(locale) { return false }
        if removeExistingOnReserve { locales.removeAll { $0.identifier == "en_US" } }
        locales.append(locale)
        if cached { ready = true }
        return true
    }
    func release(_ locale: Locale) -> Bool {
        releaseCount += 1; locales.removeAll { $0 == locale }; ready = false; return true
    }
    nonisolated var operations: ReservationInventory {
        ReservationInventory(supportedLocale: { _ in Locale(identifier: "fr_FR") },
            reservedLocales: { await self.getLocales() }, maximum: { 7 },
            reserve: { try await self.reserve($0) }, release: { await self.release($0) },
            isInstalled: { _ in await self.isReady() })
    }
}

struct AssetSetupTests {
    @Test func reportOutputFailureCleansNewSetupReservation() async throws {
        let fake = SetupInventory(cached: true)
        do {
            _ = try await setupSpeechAssets(AssetSetupCommand(language: "fr-FR", confirmation: "fr_FR"),
                inventory: fake.operations, warning: { _ in }, publish: { _ in throw POSIXError(.EBADF) }) { _ in false }
            Issue.record("Expected report failure")
        } catch let error as STTFailure { #expect(error.code == "asset_installation") }
        let counts = await fake.counts(); #expect(counts.1 == 1)
        let remaining = await fake.getLocales(); #expect(remaining.map(\.identifier) == ["en_US"])
    }

    @Test func cancellationDuringPublicationCleansNewSetupReservation() async throws {
        let fake = SetupInventory(cached: true)
        let operation = Task {
            try await setupSpeechAssets(AssetSetupCommand(language: "fr-FR", confirmation: "fr_FR"),
                inventory: fake.operations, warning: { _ in }, publish: { _ in try await Task.sleep(for: .seconds(30)) }) { _ in false }
        }
        while await fake.counts().0 == 0 { await Task.yield() }
        operation.cancel()
        do { _ = try await operation.value; Issue.record("Expected cancellation") } catch is CancellationError {}
        let counts = await fake.counts(); #expect(counts.1 == 1)
    }

    @Test func changedExistingStateStopsBeforeInstallerAndCleansKnownNewLocale() async throws {
        let fake = SetupInventory(); await fake.loseExistingOnReserve()
        var installCalls = 0
        do {
            _ = try await setupSpeechAssets(AssetSetupCommand(language: "fr-FR", confirmation: "fr_FR"),
                inventory: fake.operations, warning: { _ in }) { _ in installCalls += 1; return true }
            Issue.record("Expected state refusal")
        } catch let error as STTFailure { #expect(error.code == "reservation_ownership") }
        #expect(installCalls == 0)
        let counts = await fake.counts(); #expect(counts.1 == 1)
    }
    @Test func setupPreviewIsReadOnlyAndDisplaysResolvedLocale() async throws {
        let fake = SetupInventory()
        var installCalls = 0
        let report = try await setupSpeechAssets(AssetSetupCommand(language: "fr", confirmation: nil),
            inventory: fake.operations, warning: { _ in }) { _ in installCalls += 1; return true }
        #expect(report.preview && !report.installed_after && report.supported_locale == "fr_FR")
        #expect(installCalls == 0)
        let counts = await fake.counts(); #expect(counts.0 == 0 && counts.1 == 0)
    }

    @Test func explicitConfirmationMustMatchResolvedLocale() async throws {
        let fake = SetupInventory()
        do {
            _ = try await setupSpeechAssets(AssetSetupCommand(language: "fr", confirmation: "en_US"),
                inventory: fake.operations, warning: { _ in }) { _ in Issue.record("No install"); return true }
            Issue.record("Expected confirmation refusal")
        } catch let error as STTFailure { #expect(error.code == "asset_installation") }
        let counts = await fake.counts(); #expect(counts.0 == 0 && counts.1 == 0)
    }

    @Test func cachedSetupUsesReservationOnlyAndRetainsExplicitPin() async throws {
        let fake = SetupInventory(cached: true)
        let report = try await setupSpeechAssets(AssetSetupCommand(language: "fr-FR", confirmation: "fr_FR"),
            inventory: fake.operations, warning: { _ in }) { _ in Issue.record("Cached setup must not install"); return true }
        #expect(report.installed_after && !report.installation_request_used && report.retained_actual_locale == "fr_FR")
        #expect(report.reserved_locales == ["en_US", "fr_FR"])
        let counts = await fake.counts(); #expect(counts.0 == 1 && counts.1 == 0)
    }

    @Test func explicitSetupInvokesInstallerOnlyAfterConsentAndRetainsAssets() async throws {
        let fake = SetupInventory()
        var installCalls = 0
        let report = try await setupSpeechAssets(AssetSetupCommand(language: "fr-FR", confirmation: "fr-FR"),
            inventory: fake.operations, warning: { _ in }) { _ in installCalls += 1; await fake.markInstalled(); return true }
        #expect(installCalls == 1 && report.installation_request_used && report.installed_after)
        let counts = await fake.counts(); #expect(counts.1 == 0)
    }

    @Test func setupFailureCleansOnlyNewOwnedReservationAndPreservesError() async throws {
        let fake = SetupInventory()
        do {
            _ = try await setupSpeechAssets(AssetSetupCommand(language: "fr-FR", confirmation: "fr_FR"),
                inventory: fake.operations, warning: { _ in Issue.record("Unexpected cleanup warning") }) { _ in throw POSIXError(.EIO) }
            Issue.record("Expected setup failure")
        } catch let error as STTFailure { #expect(error.code == "asset_installation" && error.message.contains("code")) }
        let remaining = await fake.getLocales(); #expect(remaining.map(\.identifier) == ["en_US"])
        let counts = await fake.counts(); #expect(counts.1 == 1)
    }

    @Test func setupFailureDoesNotReleaseBorrowedPin() async throws {
        let fake = SetupInventory(existing: ["en_US", "fr_FR"])
        do {
            _ = try await setupSpeechAssets(AssetSetupCommand(language: "fr-FR", confirmation: "fr_FR"),
                inventory: fake.operations, warning: { _ in }) { _ in throw CancellationError() }
            Issue.record("Expected cancellation")
        } catch is CancellationError {}
        let counts = await fake.counts(); #expect(counts.1 == 0)
    }

    @Test func fullCapacityStopsBeforeInstaller() async throws {
        let fake = SetupInventory(); await fake.failCapacity()
        do {
            _ = try await setupSpeechAssets(AssetSetupCommand(language: "fr-FR", confirmation: "fr_FR"),
                inventory: fake.operations, warning: { _ in }) { _ in Issue.record("No download at capacity"); return true }
            Issue.record("Expected capacity failure")
        } catch let error as STTFailure { #expect(error.code == "reservation_capacity") }
        let counts = await fake.counts(); #expect(counts.1 == 0)
    }

    @Test func temporaryReservationCanExposeCachedAssetsWithoutInstallAndThenCleanUp() async throws {
        let fake = SetupInventory(cached: true)
        #expect(await fake.isReady() == false)
        var installCalls = 0
        try await withReservation(requested: Locale(identifier: "fr-FR"), inventory: fake.operations,
            requireExactLocale: true, requireNewReservation: true, warning: { _ in Issue.record("No warning") }) { _ in
            try await ensureSpeechAssets(requireInstalled: true, installed: { await fake.isReady() },
                                         install: { installCalls += 1 })
        }
        #expect(installCalls == 0)
        let counts = await fake.counts(); #expect(counts.0 == 1 && counts.1 == 1)
        let remaining = await fake.getLocales(); #expect(remaining.map(\.identifier) == ["en_US"])
    }

    @Test func temporaryMissingAssetsRefuseInstallerAfterReserveAndCleanUp() async throws {
        let fake = SetupInventory()
        var installCalls = 0
        do {
            try await withReservation(requested: Locale(identifier: "fr-FR"), inventory: fake.operations,
                requireNewReservation: true, warning: { _ in }) { _ in
                try await ensureSpeechAssets(requireInstalled: true, installed: { await fake.isReady() },
                                             install: { installCalls += 1 })
            }
            Issue.record("Expected readiness refusal")
        } catch let error as STTFailure { #expect(error.code == "assets_not_installed") }
        #expect(installCalls == 0)
        let counts = await fake.counts(); #expect(counts.1 == 1)
    }

    @Test(arguments: [["--install-assets", "recording.aiff"], ["--install-assets", "--confirm-download"],
                       ["--install-assets", "--install-assets"], ["--install-assets", "--reservation-maintenance", "release"]])
    func setupParserRejectsMixedOrIncompleteCommands(arguments: [String]) {
        #expect(throws: STTFailure.self) { try AssetSetupCommand.parse(arguments) }
    }
}
