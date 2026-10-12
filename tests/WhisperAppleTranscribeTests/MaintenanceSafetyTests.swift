import Foundation
import Testing
@testable import WhisperAppleTranscribe

private actor SafetyInventory {
    var locales: [Locale]
    var installed = true
    var supported = Locale(identifier: "en_CA")
    var releaseReturns = true
    var removeTarget = true
    var removeOther = false
    var delayRelease = false
    var loseOnReserve = false
    var loseOnRelease = false
    var addOnRelease: String?
    var released: [String] = []
    var reserves = 0
    var releasesFinished = 0
    var cancelledDuringRelease: [Bool] = []
    init(_ identifiers: [String] = ["en_US", "en_CA"]) { locales = identifiers.map { Locale(identifier: $0) } }
    func configure(installed: Bool = true, supported: String = "en_CA", result: Bool = true,
                   remove: Bool = true, removeOther: Bool = false, delay: Bool = false,
                   loseOnReserve: Bool = false, loseOnRelease: Bool = false, addOnRelease: String? = nil) {
        self.installed = installed; self.supported = Locale(identifier: supported)
        releaseReturns = result; removeTarget = remove; self.removeOther = removeOther; delayRelease = delay
        self.loseOnReserve = loseOnReserve; self.loseOnRelease = loseOnRelease; self.addOnRelease = addOnRelease
    }
    func getLocales() -> [Locale] { locales }
    func getInstalled() -> Bool { installed }
    func getSupported() -> Locale { supported }
    func counts() -> (Int, Int, Int) { (reserves, released.count, releasesFinished) }
    func cancellationFlags() -> [Bool] { cancelledDuringRelease }
    func targets() -> [String] { released }
    func reserve(_ locale: Locale) -> Bool {
        reserves += 1
        if loseOnReserve { installed = false }
        if locales.contains(locale) { return false }
        locales.append(locale); return true
    }
    func release(_ locale: Locale) async throws -> Bool {
        released.append(locale.identifier)
        cancelledDuringRelease.append(Task.isCancelled)
        // Simulate a framework which DOES observe task cancellation.
        try Task.checkCancellation()
        if delayRelease { try await Task.sleep(for: .milliseconds(100)) }
        if removeTarget { locales.removeAll { $0 == locale } }
        if removeOther { locales.removeAll { $0.identifier == "en_US" } }
        if loseOnRelease { installed = false }
        if let addOnRelease { locales.append(Locale(identifier: addOnRelease)) }
        releasesFinished += 1
        return releaseReturns
    }
    nonisolated var operations: ReservationInventory {
        ReservationInventory(supportedLocale: { _ in await self.getSupported() },
            reservedLocales: { await self.getLocales() }, maximum: { 7 },
            reserve: { await self.reserve($0) }, release: { try await self.release($0) },
            isInstalled: { _ in await self.getInstalled() })
    }
}

private func command(_ arguments: [String]) throws -> ReservationMaintenanceCommand {
    let parsed = try ReservationMaintenanceCommand.parse(["--reservation-maintenance"] + arguments)
    return try #require(parsed)
}
private func confirmed(_ target: String = "en_CA") throws -> ReservationMaintenanceCommand {
    try command(["release", "--reserved-locale", target, "--confirm-release", target, "--confirm-unused"])
}

struct MaintenanceSafetyTests {
    @Test func ownershipEventsUseActualLocaleAndConfirmJoinedCleanupEvenOnBodyFailure() async throws {
        let fake = SafetyInventory(["en_US"])
        var events: [String] = []
        do {
            _ = try await withReservation(requested: Locale(identifier: "en-CA"), inventory: fake.operations,
                requireNewReservation: true, event: { phase, actual in events.append("\(phase):\(actual.identifier)") },
                warning: { _ in Issue.record("Unexpected cleanup warning") }) { _ -> Int in throw POSIXError(.EIO) }
            Issue.record("Expected primary failure")
        } catch let error as POSIXError { #expect(error.code == .EIO) }
        #expect(events == ["acquired:en_CA", "released:en_CA"])
        let counts = await fake.counts(); #expect(counts.2 == 1)
    }

    @Test func inspectionAndUnconfirmedReleaseAreReadOnly() async throws {
        let fake = SafetyInventory()
        for request in [try command(["inspect"]), try command(["release", "--reserved-locale", "en_CA"]),
                        try command(["release", "--reserved-locale", "en_CA", "--dry-run"])] {
            let report = try await maintainReservation(request, inventory: fake.operations)
            #expect(report.dry_run && report.verified && !report.release_attempted)
            #expect(report.before.maximum_reserved_locales == 7)
            #expect(report.before.installed_assets["en_CA"] == true)
        }
        let counts = await fake.counts(); #expect(counts.0 == 0 && counts.1 == 0)
    }

    @Test(arguments: [
        ["release"], ["release", "--reserved-locale", "*"],
        ["release", "--reserved-locale", "en_CA,en_GB"], ["inspect", "--all"],
        ["inspect", "recording.aiff"], ["inspect", "--language", "en-US"],
        ["release", "--reserved-locale", "en_CA", "--confirm-release", "en_CA"],
        ["release", "--reserved-locale", "en_CA", "--confirm-release", "en_US", "--confirm-unused"],
        ["release", "--reserved-locale", "en_US", "--confirm-release", "en_US", "--confirm-unused"],
        ["release", "--reserved-locale", "en_CA", "--confirm-release", "en_CA", "--confirm-unused", "--dry-run"],
        ["inspect", "--reservation-maintenance", "inspect"]
    ]) func invalidOrUnconfirmedMutationOptionsAreRejected(arguments: [String]) {
        #expect(throws: STTFailure.self) { try command(arguments) }
    }

    @Test func defaultNeedsExtraExplicitConfirmation() throws {
        let request = try command(["release", "--reserved-locale", "en_US", "--confirm-release", "en_US",
                                   "--confirm-unused", "--allow-default-release"])
        #expect(!request.dryRun && request.target == "en_US")
    }

    @Test func confirmedReleaseOnlyRemovesExactTargetAndVerifiesReadback() async throws {
        let fake = SafetyInventory()
        let report = try await maintainReservation(confirmed(), inventory: fake.operations)
        #expect(report.release_reported == true && report.verified)
        #expect(report.after?.reserved_locales == ["en_US"])
        #expect(report.after?.installed_assets["en_CA"] == true)
        let targets = await fake.targets(); #expect(targets == ["en_CA"])
        let counts = await fake.counts(); #expect(counts.0 == 0 && counts.1 == 1)
    }

    @Test func regionalAliasesAreNotMaintenanceSelectors() async throws {
        let fake = SafetyInventory()
        do {
            _ = try await maintainReservation(command(["release", "--reserved-locale", "en-CA"]), inventory: fake.operations)
            Issue.record("Equivalent spelling must not silently select a release target")
        } catch let error as STTFailure { #expect(error.code == "reservation_maintenance") }
        let alias = try command(["release", "--reserved-locale", "en-US", "--confirm-release", "en-US",
                                 "--confirm-unused", "--allow-default-release"])
        do {
            _ = try await maintainReservation(alias, inventory: fake.operations)
            Issue.record("Confirmed alias is still not an exact selector")
        } catch let error as STTFailure { #expect(error.code == "reservation_maintenance") }
        let counts = await fake.counts(); #expect(counts.1 == 0)
    }

    @Test func repeatAbsentTargetRefusesWithoutAnotherReleaseAttempt() async throws {
        let fake = SafetyInventory()
        _ = try await maintainReservation(confirmed(), inventory: fake.operations)
        do {
            _ = try await maintainReservation(confirmed(), inventory: fake.operations)
            Issue.record("Absent target cannot be claimed as verified release history")
        } catch let error as STTFailure { #expect(error.code == "reservation_maintenance") }
        let counts = await fake.counts(); #expect(counts.1 == 1)
    }

    @Test func releaseFalseRequiresReadbackAndDoesNotRetry() async throws {
        for remove in [false, true] {
            let fake = SafetyInventory()
            await fake.configure(result: false, remove: remove)
            let report = try await maintainReservation(confirmed(), inventory: fake.operations)
            #expect(report.release_reported == false)
            #expect(report.verified == remove)
            let counts = await fake.counts(); #expect(counts.1 == 1)
        }
    }

    @Test func releaseTrueButRetainedTargetIsVerificationFailure() async throws {
        let fake = SafetyInventory()
        await fake.configure(remove: false)
        let report = try await maintainReservation(confirmed(), inventory: fake.operations)
        #expect(!report.verified)
    }

    @Test func nonTargetMutationIsReportedNotRepaired() async throws {
        let fake = SafetyInventory()
        await fake.configure(removeOther: true)
        let report = try await maintainReservation(confirmed(), inventory: fake.operations)
        #expect(!report.verified && report.after?.reserved_locales == [])
        let counts = await fake.counts(); #expect(counts.0 == 0 && counts.1 == 1)
    }

    @Test func assetLossIsReportedWithoutReserveOrInstallation() async throws {
        let fake = SafetyInventory()
        await fake.configure(loseOnRelease: true)
        let report = try await maintainReservation(confirmed(), inventory: fake.operations)
        #expect(report.before.installed_assets["en_CA"] == true)
        #expect(report.after?.installed_assets["en_CA"] == false)
        let counts = await fake.counts(); #expect(counts.0 == 0)
    }

    @Test func extraReservationDuringOwnedReleaseFailsClosedAndPreservesPrimary() async throws {
        for primaryFails in [false, true] {
            let fake = SafetyInventory(["en_US"])
            await fake.configure(addOnRelease: "en_GB")
            var warnings: [String] = []
            do {
                _ = try await withReservation(requested: Locale(identifier: "en-CA"), inventory: fake.operations,
                    warning: { warnings.append($0) }) { _ in
                    if primaryFails { throw POSIXError(.EIO) }
                    return 0
                }
                Issue.record("Unexpected post-release inventory must be reported")
            } catch let error as POSIXError {
                #expect(primaryFails && error.code == .EIO)
                #expect(warnings.count == 1 && warnings[0].contains("en_GB"))
            } catch let error as STTFailure {
                #expect(!primaryFails && error.code == "reservation_ownership")
                #expect(error.message.contains("en_GB"))
            }
            let remaining = await fake.getLocales()
            #expect(remaining.map(\.identifier).sorted() == ["en_GB", "en_US"])
            let counts = await fake.counts(); #expect(counts.1 == 1)
        }
    }

    @Test func assetLossDuringReserveRefusesInstallationAndReleasesOwnedLocale() async throws {
        let fake = SafetyInventory(["en_US"])
        await fake.configure(loseOnReserve: true)
        var installCalls = 0
        do {
            try await withReservation(requested: Locale(identifier: "en-CA"), inventory: fake.operations,
                requireInstalled: true, warning: { _ in Issue.record("Unexpected cleanup warning") }) { _ in
                try await ensureSpeechAssets(requireInstalled: true, installed: { await fake.getInstalled() },
                                             install: { installCalls += 1 })
            }
            Issue.record("Expected post-acquisition offline refusal")
        } catch let error as STTFailure { #expect(error.code == "assets_not_installed") }
        #expect(installCalls == 0)
        let remaining = await fake.getLocales(); #expect(remaining.map(\.identifier) == ["en_US"])
        let counts = await fake.counts(); #expect(counts.0 == 1 && counts.1 == 1 && counts.2 == 1)
    }

    @Test func cancelledCallerStillJoinsNonCancelledOwnedCleanup() async throws {
        let fake = SafetyInventory([])
        await fake.configure(delay: true)
        let operation = Task {
            try await withReservation(requested: Locale(identifier: "en-CA"), inventory: fake.operations,
                                      warning: { _ in Issue.record("Unexpected cleanup failure") }) { _ in
                try await Task.sleep(for: .seconds(30))
            }
        }
        while await fake.getLocales().isEmpty { await Task.yield() }
        operation.cancel()
        do { try await operation.value; Issue.record("Expected cancellation") }
        catch is CancellationError {}
        let flags = await fake.cancellationFlags(); #expect(flags == [false])
        let counts = await fake.counts(); #expect(counts.2 == 1)
        let remaining = await fake.getLocales(); #expect(remaining.isEmpty)
    }

    @Test func cancellationDuringSuccessfulCleanupIsReportedAfterJoining() async throws {
        let fake = SafetyInventory([])
        await fake.configure(delay: true)
        let operation = Task {
            try await withReservation(requested: Locale(identifier: "en-CA"), inventory: fake.operations,
                                      warning: { _ in Issue.record("Unexpected cleanup failure") }) { _ in 42 }
        }
        while await fake.counts().1 == 0 { await Task.yield() }
        operation.cancel()
        do { _ = try await operation.value; Issue.record("Late cancellation must not escape as success") }
        catch is CancellationError {}
        let counts = await fake.counts(); #expect(counts.2 == 1)
        let remaining = await fake.getLocales(); #expect(remaining.isEmpty)
    }

    @Test func maintenanceAdmissionFinishesReadbackEvenIfCallerIsCancelled() async throws {
        let fake = SafetyInventory()
        await fake.configure(delay: true)
        let request = try confirmed()
        let operation = Task { try await maintainReservation(request, inventory: fake.operations) }
        while await fake.counts().1 == 0 { await Task.yield() }
        operation.cancel()
        let report = try await operation.value
        #expect(report.verified && report.after?.reserved_locales == ["en_US"])
        let flags = await fake.cancellationFlags(); #expect(flags == [false])
        let counts = await fake.counts(); #expect(counts.2 == 1)
    }

    @Test func offlineGuardRefusesBeforeAcquiringAnything() async throws {
        let fake = SafetyInventory([])
        await fake.configure(installed: false)
        do {
            _ = try await withReservation(requested: Locale(identifier: "en-CA"), inventory: fake.operations,
                requireInstalled: true, warning: { _ in }) { _ in Issue.record("Body must not run"); return 0 }
            Issue.record("Expected offline refusal")
        } catch let error as STTFailure { #expect(error.code == "assets_not_installed") }
        let counts = await fake.counts(); #expect(counts.0 == 0 && counts.1 == 0)
    }

    @Test func strictLocaleRefusesNearbyRegionButAcceptsIdentifierSpelling() async throws {
        let fake = SafetyInventory()
        await fake.configure(supported: "en_US")
        do {
            _ = try await withReservation(requested: Locale(identifier: "en-CA"), inventory: fake.operations,
                requireExactLocale: true, warning: { _ in }) { _ in 0 }
            Issue.record("Expected region refusal")
        } catch let error as STTFailure { #expect(error.code == "locale_substitution") }
        let counts = await fake.counts(); #expect(counts.0 == 0)
        #expect(sameSpeechLocale(Locale(identifier: "en-CA"), Locale(identifier: "en_CA")))
    }

    @Test func requireNewRejectsBorrowedReuseWithoutReleasingIt() async throws {
        let fake = SafetyInventory()
        do {
            _ = try await withReservation(requested: Locale(identifier: "en-CA"), inventory: fake.operations,
                requireNewReservation: true, warning: { _ in }) { _ in Issue.record("Borrowed test must not run"); return 0 }
            Issue.record("Expected borrowed refusal")
        } catch let error as STTFailure { #expect(error.code == "new_reservation_required") }
        let counts = await fake.counts(); #expect(counts.1 == 0)
    }

    @Test func noDownloadGuardNeverCreatesInstallationRequest() async throws {
        var installCalls = 0
        do {
            try await ensureSpeechAssets(requireInstalled: true, installed: { false }, install: { installCalls += 1 })
            Issue.record("Expected missing assets")
        } catch let error as STTFailure { #expect(error.code == "assets_not_installed") }
        #expect(installCalls == 0)
        try await ensureSpeechAssets(requireInstalled: true, installed: { true }, install: { installCalls += 1 })
        #expect(installCalls == 0)
    }

    @Test func optionalValidationFlagsPreserveDefaultAndEveryEnglishRegion() throws {
        for region in ["en-US", "en-CA", "en-GB", "en-AU", "en-IN"] {
            let parsed = try parseOptions(arguments: ["--language", region, "/dev/null"])
            let options = try #require(parsed)
            #expect(options.language == region)
            #expect(!options.requireInstalledAssets && !options.requireExactLocale && !options.requireNewReservation)
        }
        let parsedDefaults = try parseOptions(arguments: ["/dev/null"])
        let defaults = try #require(parsedDefaults)
        #expect(defaults.language == "en-US" && defaults.format == "text")
        let parsedValidation = try parseOptions(arguments: ["--require-installed-assets", "--require-exact-locale", "--require-new-reservation", "/dev/null"])
        let validation = try #require(parsedValidation)
        #expect(validation.requireInstalledAssets && validation.requireExactLocale && validation.requireNewReservation)
    }
}
