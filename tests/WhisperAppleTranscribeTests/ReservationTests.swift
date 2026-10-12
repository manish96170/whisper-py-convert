import Foundation
import Darwin
import Speech
import Testing
@testable import WhisperAppleTranscribe

private func XCTAssertEqual<T: Equatable>(_ actual: T, _ expected: T, _ message: String = "",
                                        sourceLocation: SourceLocation = #_sourceLocation) {
    #expect(actual == expected, Comment(rawValue: message), sourceLocation: sourceLocation)
}
private func XCTAssertTrue(_ value: Bool, _ message: String = "",
                          sourceLocation: SourceLocation = #_sourceLocation) {
    #expect(value, Comment(rawValue: message), sourceLocation: sourceLocation)
}
private func XCTFail(_ message: String = "Unexpected outcome",
                     sourceLocation: SourceLocation = #_sourceLocation) {
    Issue.record(Comment(rawValue: message), sourceLocation: sourceLocation)
}

private enum FixtureError: Error { case primary, cleanup, reserve }

private actor FakeInventory {
    var locales: [Locale]
    var supported: Locale? = Locale(identifier: "en-US")
    var supporting = Locale(identifier: "en_US")
    var limit = 2
    var reserveError = false
    var releaseError = false
    var releaseResult = true
    var released: [Locale] = []
    var reserveCalls = 0

    init(existing: [Locale] = []) { locales = existing }
    func configure(supported: Locale?, supporting: Locale, limit: Int = 2) {
        self.supported = supported; self.supporting = supporting; self.limit = limit
    }
    func fail(reserve: Bool = false, release: Bool = false, releaseResult: Bool = true) {
        reserveError = reserve; releaseError = release; self.releaseResult = releaseResult
    }
    func getSupported() -> Locale? { supported }
    func getLocales() -> [Locale] { locales }
    func getLimit() -> Int { limit }
    func getReleased() -> [Locale] { released }
    func getReserveCalls() -> Int { reserveCalls }
    func addUnexpectedReservation() { locales.append(Locale(identifier: "de-DE")) }
    func reserve(_ locale: Locale) throws -> Bool {
        reserveCalls += 1
        if reserveError { throw FixtureError.reserve }
        if locales.contains(supporting) { return false }
        if locales.count >= limit {
            throw NSError(domain: SFSpeechErrorDomain, code: SFSpeechError.Code.tooManyAssetLocalesAllocated.rawValue)
        }
        locales.append(supporting)
        return true
    }
    func release(_ locale: Locale) throws -> Bool {
        released.append(locale)
        if releaseError { throw FixtureError.cleanup }
        if !releaseResult { return false }
        locales.removeAll { $0 == locale }
        return true
    }
    nonisolated var operations: ReservationInventory {
        ReservationInventory(
            supportedLocale: { _ in await self.getSupported() },
            reservedLocales: { await self.getLocales() },
            maximum: { await self.getLimit() },
            reserve: { try await self.reserve($0) },
            release: { try await self.release($0) }
        )
    }
}

struct ReservationTests {
    @Test func testReservationErrorClassificationAlsoAppliesToInstallationRequests() {
        for (code, expected) in [
            (SFSpeechError.Code.tooManyAssetLocalesAllocated.rawValue, "reservation_capacity"),
            (SFSpeechError.Code.cannotAllocateUnsupportedLocale.rawValue, "unsupported_locale")
        ] {
            let error = NSError(domain: SFSpeechErrorDomain, code: code,
                                userInfo: [NSLocalizedDescriptionKey: "Opaque localized message"])
            XCTAssertEqual(STTFailure.reservationCode(for: error), expected)
            XCTAssertEqual(STTFailure.reservationCode(for: NSError(domain: "OtherDomain", code: code)), nil)
        }
        XCTAssertEqual(STTFailure.reservationCode(for: FixtureError.primary), nil)
    }

    @Test func testNewReservationReleasesActualVariantOnly() async throws {
        let existing = Locale(identifier: "fr-FR")
        let fake = FakeInventory(existing: [existing])
        let result = try await withReservation(requested: Locale(identifier: "en-GB"), inventory: fake.operations, warning: { _ in XCTFail() }) { locale in
            XCTAssertEqual(locale.identifier, "en-US")
            return "transcript"
        }
        XCTAssertEqual(result, "transcript")
        let remaining = await fake.getLocales()
        let released = await fake.getReleased()
        XCTAssertEqual(remaining, [existing])
        XCTAssertEqual(released, [Locale(identifier: "en_US")])
    }

    @Test func testAlreadyReservedFalseIsReusedAndNotReleased() async throws {
        let locale = Locale(identifier: "en_US")
        let fake = FakeInventory(existing: [locale])
        _ = try await withReservation(requested: locale, inventory: fake.operations, warning: { _ in XCTFail() }) { _ in 1 }
        let remaining = await fake.getLocales()
        let released = await fake.getReleased()
        XCTAssertEqual(remaining, [locale])
        XCTAssertTrue(released.isEmpty)
    }

    @Test func testUnsupportedDoesNotReserveOrRelease() async {
        let fake = FakeInventory()
        await fake.configure(supported: nil, supporting: Locale(identifier: "en_US"))
        do {
            _ = try await withReservation(requested: Locale(identifier: "zz"), inventory: fake.operations, warning: { _ in }) { _ in XCTFail(); return 0 }
            XCTFail()
        } catch let error as STTFailure { XCTAssertEqual(error.code, "unsupported_locale") }
        catch { XCTFail("\(error)") }
        let calls = await fake.getReserveCalls()
        let released = await fake.getReleased()
        XCTAssertEqual(calls, 0)
        XCTAssertTrue(released.isEmpty)
    }

    @Test func testCapacityIsConfigurableAndIncludesFrameworkError() async {
        for maximum in [1, 3, 7] {
            let fake = FakeInventory(existing: (0..<maximum).map { Locale(identifier: "fr-\($0)") })
            await fake.configure(supported: Locale(identifier: "en-US"), supporting: Locale(identifier: "en_US"), limit: maximum)
            do {
                _ = try await withReservation(requested: Locale(identifier: "en-US"), inventory: fake.operations, warning: { _ in }) { _ in XCTFail(); return 0 }
                XCTFail()
            } catch let error as STTFailure {
                XCTAssertEqual(error.code, "reservation_capacity")
                XCTAssertTrue(error.message.contains("\(maximum)/\(maximum)"))
                XCTAssertTrue(error.message.contains("code"))
            } catch { XCTFail("\(error)") }
            let released = await fake.getReleased()
            XCTAssertTrue(released.isEmpty)
        }
    }

    @Test func testOtherReservationErrorIsNotUnsupported() async {
        let fake = FakeInventory()
        await fake.fail(reserve: true)
        do {
            _ = try await withReservation(requested: Locale(identifier: "en-US"), inventory: fake.operations, warning: { _ in }) { _ in XCTFail(); return 0 }
            XCTFail()
        } catch let error as STTFailure { XCTAssertEqual(error.code, "reservation_failed") }
        catch { XCTFail("\(error)") }
        let released = await fake.getReleased()
        XCTAssertTrue(released.isEmpty)
    }

    @Test func testEveryLaterFailureReleasesOwnedReservationAndPreservesError() async {
        // All these stages execute inside the same production lifetime boundary.
        for stage in ["installation", "provider", "analysis", "results", "encoding", "output"] {
            let fake = FakeInventory()
            do {
                _ = try await withReservation(requested: Locale(identifier: "en-US"), inventory: fake.operations, warning: { _ in XCTFail(stage) }) { _ -> Int in throw FixtureError.primary }
                XCTFail(stage)
            } catch FixtureError.primary {} catch { XCTFail("\(stage): \(error)") }
            let remaining = await fake.getLocales()
            let released = await fake.getReleased()
            XCTAssertTrue(remaining.isEmpty, stage)
            XCTAssertEqual(released.count, 1, stage)
        }
    }

    @Test func testBorrowedReservationOnFailureIsNotReleased() async {
        let fake = FakeInventory(existing: [Locale(identifier: "en_US")])
        do {
            _ = try await withReservation(requested: Locale(identifier: "en-US"), inventory: fake.operations, warning: { _ in }) { _ -> Int in throw FixtureError.primary }
        } catch {}
        let released = await fake.getReleased()
        XCTAssertTrue(released.isEmpty)
    }

    @Test func testCleanupFailureDoesNotMaskPrimaryFailure() async {
        for throwsError in [false, true] {
            let fake = FakeInventory()
            await fake.fail(release: throwsError, releaseResult: false)
            var warnings: [String] = []
            do {
                _ = try await withReservation(requested: Locale(identifier: "en-US"), inventory: fake.operations, warning: { warnings.append($0) }) { _ -> Int in throw FixtureError.primary }
                XCTFail()
            } catch FixtureError.primary {} catch { XCTFail("\(error)") }
            XCTAssertEqual(warnings.count, 1)
            XCTAssertTrue(warnings[0].contains("reservation_cleanup"))
        }
    }

    @Test func testCleanupFalseAfterSuccessIsReported() async {
        let fake = FakeInventory()
        await fake.fail(releaseResult: false)
        do {
            _ = try await withReservation(requested: Locale(identifier: "en-US"), inventory: fake.operations, warning: { _ in }) { _ in 1 }
            XCTFail()
        } catch let error as STTFailure { XCTAssertEqual(error.code, "reservation_cleanup") }
        catch { XCTFail("\(error)") }
    }

    @Test func testCooperativeCancellationAwaitsRelease() async throws {
        let fake = FakeInventory()
        let task = Task {
            try await withReservation(requested: Locale(identifier: "en-US"), inventory: fake.operations, warning: { _ in XCTFail() }) { _ in
                try await Task.sleep(for: .seconds(30))
            }
        }
        while await fake.getLocales().isEmpty { await Task.yield() }
        task.cancel()
        do { try await task.value; XCTFail() } catch is CancellationError {} catch { XCTFail("\(error)") }
        let remaining = await fake.getLocales()
        let released = await fake.getReleased()
        XCTAssertTrue(remaining.isEmpty)
        XCTAssertEqual(released.count, 1)
    }

    @Test func testConcurrentSameLocaleIsSerializedThroughCleanup() async throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let fake = FakeInventory()
        let run: @Sendable () async throws -> Void = {
            let gate = try ReservationGate(directory: directory)
            try await gate.acquire()
            defer { gate.unlock() }
            try await withReservation(requested: Locale(identifier: "en-US"), inventory: fake.operations, warning: { _ in XCTFail() }) { _ in
                let current = await fake.getLocales()
                XCTAssertEqual(current.count, 1)
                try await Task.sleep(for: .milliseconds(100))
                let stillInUse = await fake.getLocales()
                XCTAssertEqual(stillInUse.count, 1)
            }
        }
        async let first: Void = run()
        async let second: Void = run()
        _ = try await (first, second)
        let remaining = await fake.getLocales()
        let released = await fake.getReleased()
        XCTAssertTrue(remaining.isEmpty)
        XCTAssertEqual(released.count, 2)
    }

    @Test func testCancelledWaiterDoesNotAcquireOrReleaseInventory() async throws {
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: directory) }
        let owner = try ReservationGate(directory: directory)
        try await owner.acquire()
        defer { owner.unlock() }
        let waiter = Task {
            let gate = try ReservationGate(directory: directory)
            try await gate.acquire()
            gate.unlock()
        }
        waiter.cancel()
        do { try await waiter.value; XCTFail() } catch is CancellationError {} catch { XCTFail("\(error)") }
    }

    @Test func testStructuredUnsupportedAllocationErrorIsNotCapacity() async {
        let fake = FakeInventory()
        var operations = fake.operations
        operations.reserve = { _ in
            throw NSError(domain: SFSpeechErrorDomain, code: SFSpeechError.Code.cannotAllocateUnsupportedLocale.rawValue,
                          userInfo: [NSLocalizedDescriptionKey: "Non-English framework description"])
        }
        do {
            _ = try await withReservation(requested: Locale(identifier: "en-US"), inventory: operations, warning: { _ in }) { _ in XCTFail(); return 0 }
            XCTFail()
        } catch let error as STTFailure {
            XCTAssertEqual(error.code, "unsupported_locale")
            XCTAssertTrue(error.message.contains("Non-English framework description"))
        } catch { XCTFail("\(error)") }
        let released = await fake.getReleased()
        XCTAssertTrue(released.isEmpty)
    }

    @Test func testFullInventoryDoesNotMisclassifyOtherFrameworkFailure() async {
        let fake = FakeInventory(existing: [Locale(identifier: "fr-FR"), Locale(identifier: "de-DE")])
        await fake.fail(reserve: true)
        do {
            _ = try await withReservation(requested: Locale(identifier: "en-US"), inventory: fake.operations, warning: { _ in }) { _ in 0 }
            XCTFail()
        } catch let error as STTFailure { XCTAssertEqual(error.code, "reservation_failed") }
        catch { XCTFail("\(error)") }
    }

    @Test func testAmbiguousSuccessfulAcquisitionNeverReleasesUnrelatedState() async {
        let existing = Locale(identifier: "fr-FR")
        let fake = FakeInventory(existing: [existing])
        var operations = fake.operations
        // A non-cooperating inventory mutation makes the owned delta unknowable.
        operations.reserve = { _ in true }
        do {
            _ = try await withReservation(requested: Locale(identifier: "en-US"), inventory: operations, warning: { _ in }) { _ in XCTFail(); return 0 }
            XCTFail()
        } catch let error as STTFailure { XCTAssertEqual(error.code, "reservation_ownership") }
        catch { XCTFail("\(error)") }
        let remaining = await fake.getLocales()
        let released = await fake.getReleased()
        XCTAssertEqual(remaining, [existing])
        XCTAssertTrue(released.isEmpty)
    }

    @Test func testCleanupThrowAfterSuccessIsReported() async {
        let fake = FakeInventory()
        await fake.fail(release: true)
        do {
            _ = try await withReservation(requested: Locale(identifier: "en-US"), inventory: fake.operations, warning: { _ in }) { _ in 1 }
            XCTFail()
        } catch let error as STTFailure { XCTAssertEqual(error.code, "reservation_cleanup") }
        catch { XCTFail("\(error)") }
    }

    @Test func testInstallationReservationMutationIsReportedWithoutReleasingUnknownEntries() async {
        for stage in ["request-creation", "download", "success"] {
            let fake = FakeInventory()
            var warnings: [String] = []
            do {
                _ = try await withReservation(requested: Locale(identifier: "en-US"), inventory: fake.operations, warning: { warnings.append($0) }) { _ in
                    await fake.addUnexpectedReservation()
                    if stage != "success" { throw FixtureError.primary }
                    return 0
                }
                XCTFail(stage)
            } catch FixtureError.primary {
                XCTAssertEqual(warnings.count, 1, stage)
                XCTAssertTrue(warnings[0].contains("reservation_ownership"), stage)
            } catch let error as STTFailure {
                XCTAssertEqual(stage, "success")
                XCTAssertEqual(error.code, "reservation_ownership")
            } catch { XCTFail("\(stage): \(error)") }
            let remaining = await fake.getLocales()
            let released = await fake.getReleased()
            XCTAssertEqual(remaining, [Locale(identifier: "de-DE")], stage)
            XCTAssertEqual(released, [Locale(identifier: "en_US")], stage)
        }
    }

    @Test func testStalledOutputCancellationReleasesOwnedReservation() async throws {
        var descriptors: [Int32] = [0, 0]
        guard pipe(&descriptors) == 0 else { XCTFail(); return }
        defer { close(descriptors[0]); close(descriptors[1]) }
        let fake = FakeInventory()
        let writer = descriptors[1]
        let operation = Task {
            try await withReservation(requested: Locale(identifier: "en-US"), inventory: fake.operations, warning: { _ in XCTFail() }) { _ in
                try await writeOutput(Data(repeating: 65, count: 1_000_000), descriptor: writer)
            }
        }
        while await fake.getLocales().isEmpty { await Task.yield() }
        try await Task.sleep(for: .milliseconds(100))
        operation.cancel()
        do { try await operation.value; XCTFail() } catch is CancellationError {} catch { XCTFail("\(error)") }
        let remaining = await fake.getLocales()
        let released = await fake.getReleased()
        XCTAssertTrue(remaining.isEmpty)
        XCTAssertEqual(released.count, 1)
    }

    @Test func testBrokenDiagnosticDoesNotMaskPrimaryErrorOrCleanup() async {
        signal(SIGPIPE, SIG_IGN)
        var descriptors: [Int32] = [0, 0]
        guard pipe(&descriptors) == 0 else { XCTFail(); return }
        close(descriptors[0])
        let output = FileHandle(fileDescriptor: descriptors[1], closeOnDealloc: true)
        let fake = FakeInventory()
        await fake.fail(releaseResult: false)
        do {
            _ = try await withReservation(requested: Locale(identifier: "en-US"), inventory: fake.operations,
                                          warning: { diagnostic($0, output: output) }) { _ -> Int in throw FixtureError.primary }
            XCTFail()
        } catch FixtureError.primary {} catch { XCTFail("\(error)") }
        let released = await fake.getReleased()
        XCTAssertEqual(released.count, 1)
    }

    @Test func testFullOpenDiagnosticPipeDoesNotBlockOwnedCleanup() async {
        var descriptors: [Int32] = [0, 0]
        guard pipe(&descriptors) == 0 else { XCTFail(); return }
        defer { close(descriptors[0]); close(descriptors[1]) }
        let writer = descriptors[1]
        let originalFlags = fcntl(writer, F_GETFL)
        _ = fcntl(writer, F_SETFL, originalFlags | O_NONBLOCK)
        let padding = Data(repeating: 65, count: 65_536)
        while padding.withUnsafeBytes({ Darwin.write(writer, $0.baseAddress!, $0.count) }) > 0 {}
        _ = fcntl(writer, F_SETFL, originalFlags)
        let output = FileHandle(fileDescriptor: writer, closeOnDealloc: false)
        // Darwin reports additional internal flags after pipe writes. Check
        // the configurable nonblocking bit at the diagnostic boundary.
        let flagsBeforeDiagnostic = fcntl(writer, F_GETFL)
        let fake = FakeInventory()
        await fake.fail(releaseResult: false)
        do {
            _ = try await withReservation(requested: Locale(identifier: "en-US"), inventory: fake.operations,
                                          warning: { diagnostic($0, output: output) }) { _ -> Int in throw FixtureError.primary }
            XCTFail()
        } catch FixtureError.primary {} catch { XCTFail("\(error)") }
        let released = await fake.getReleased()
        XCTAssertEqual(released.count, 1)
        XCTAssertEqual(fcntl(writer, F_GETFL) & O_NONBLOCK, flagsBeforeDiagnostic & O_NONBLOCK)
    }
}
