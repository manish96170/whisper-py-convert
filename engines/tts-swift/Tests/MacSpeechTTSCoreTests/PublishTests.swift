import Foundation
import AVFoundation
import Darwin
import Testing
@testable import MacSpeechTTSCore

@Suite struct PublishTests {
    @Test func publishesCompletedFileAndCleansTemporary() throws {
        let directory = try publicationDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let temporary = directory.appendingPathComponent("staged.wav")
        let final = directory.appendingPathComponent("final.wav")
        try Data("complete synthetic bytes".utf8).write(to: temporary)
        try publishAudioFile(temporary, to: final, force: false)
        #expect(try Data(contentsOf: final) == Data("complete synthetic bytes".utf8))
        #expect(!FileManager.default.fileExists(atPath: temporary.path))
        let attributes = try FileManager.default.attributesOfItem(atPath: final.path)
        #expect((attributes[.posixPermissions] as? NSNumber)?.intValue == 0o600)
    }

    @Test func preservesOutputCreatedBeforePublication() throws {
        let directory = try publicationDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let temporary = directory.appendingPathComponent("staged.wav")
        let final = directory.appendingPathComponent("final.wav")
        try Data("our audio".utf8).write(to: temporary)
        // The other writer appears after synthesis/preflight but before
        // publication: the old finalizer would silently delete it.
        try Data("other writer".utf8).write(to: final)
        expectAppError(.outputExists) { try publishAudioFile(temporary, to: final, force: false) }
        #expect(try Data(contentsOf: final) == Data("other writer".utf8))
        #expect(try Data(contentsOf: temporary) == Data("our audio".utf8))
    }

    @Test func forceReplacesEntryWithoutMutatingExistingHardLink() throws {
        let directory = try publicationDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let temporary = directory.appendingPathComponent("staged.wav")
        let final = directory.appendingPathComponent("final.wav")
        let kept = directory.appendingPathComponent("kept.wav")
        try Data("old audio".utf8).write(to: final)
        try FileManager.default.linkItem(at: final, to: kept)
        try Data("new audio".utf8).write(to: temporary)
        try publishAudioFile(temporary, to: final, force: true)
        #expect(try Data(contentsOf: final) == Data("new audio".utf8))
        #expect(try Data(contentsOf: kept) == Data("old audio".utf8))
        #expect(!FileManager.default.fileExists(atPath: temporary.path))
    }

    @Test func danglingSymlinkIsNotClobberedWithoutForce() throws {
        let directory = try publicationDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let temporary = directory.appendingPathComponent("staged.wav")
        let final = directory.appendingPathComponent("final.wav")
        let absent = directory.appendingPathComponent("absent.wav")
        try FileManager.default.createSymbolicLink(at: final, withDestinationURL: absent)
        try Data("new audio".utf8).write(to: temporary)
        expectAppError(.invalidArgument) { try publishAudioFile(temporary, to: final, force: false) }
        #expect(try FileManager.default.destinationOfSymbolicLink(atPath: final.path) == absent.path)
        #expect(!FileManager.default.fileExists(atPath: absent.path))
    }

    @Test func forceDoesNotFollowSymlinkTarget() throws {
        let directory = try publicationDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let temporary = directory.appendingPathComponent("staged.wav")
        let final = directory.appendingPathComponent("final.wav")
        let kept = directory.appendingPathComponent("kept.wav")
        try Data("keep target".utf8).write(to: kept)
        try FileManager.default.createSymbolicLink(at: final, withDestinationURL: kept)
        try Data("new audio".utf8).write(to: temporary)
        expectAppError(.invalidArgument) { try publishAudioFile(temporary, to: final, force: true) }
        #expect(try FileManager.default.destinationOfSymbolicLink(atPath: final.path) == kept.path)
        #expect(try Data(contentsOf: kept) == Data("keep target".utf8))
    }

    @Test func failedForceDoesNotRemoveDestinationDirectory() throws {
        let directory = try publicationDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let temporary = directory.appendingPathComponent("staged.wav")
        let final = directory.appendingPathComponent("destination")
        try FileManager.default.createDirectory(at: final, withIntermediateDirectories: false)
        let kept = final.appendingPathComponent("keep.txt")
        try Data("keep data".utf8).write(to: kept)
        try Data("new audio".utf8).write(to: temporary)
        expectAppError(.invalidArgument) { try publishAudioFile(temporary, to: final, force: true) }
        #expect(try Data(contentsOf: kept) == Data("keep data".utf8))
        #expect(FileManager.default.fileExists(atPath: temporary.path))
    }

    @Test func forceRefusesFifoEntry() throws {
        let directory = try publicationDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let temporary = directory.appendingPathComponent("staged.wav")
        let final = directory.appendingPathComponent("fifo.wav")
        #expect(Darwin.mkfifo(final.path, 0o600) == 0)
        try Data("new audio".utf8).write(to: temporary)
        expectAppError(.invalidArgument) { try publishAudioFile(temporary, to: final, force: true) }
        var entry = stat()
        #expect(Darwin.lstat(final.path, &entry) == 0)
        #expect(entry.st_mode & S_IFMT == S_IFIFO)
    }

    @Test func reservedStagingIsPrivateBeforeAndAfterAVFoundationOpen() throws {
        let directory = try publicationDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let staging = try createAudioStagingFile(in: directory, extension: "wav")
        let folderAttributes = try FileManager.default.attributesOfItem(atPath: staging.directory.path)
        #expect((folderAttributes[.posixPermissions] as? NSNumber)?.intValue == 0o700)
        try validateAudioStagingFile(staging)
        let format = try audioFormatSpec(named: "wav")
        var audio: AVAudioFile? = try AVAudioFile(forWriting: staging.file, settings: format.settings)
        #expect(audio != nil)
        try validateAudioStagingFile(staging)
        audio = nil
        try validateAudioStagingFile(staging)
    }

    @Test func forceRefusesUnixSocketEntry() throws {
        let directory = try publicationDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let temporary = directory.appendingPathComponent("staged.wav")
        let final = directory.appendingPathComponent("sock")
        let descriptor = Darwin.socket(AF_UNIX, SOCK_STREAM, 0)
        try #require(descriptor >= 0)
        defer { _ = Darwin.close(descriptor) }
        var address = sockaddr_un()
        address.sun_family = sa_family_t(AF_UNIX)
        address.sun_len = UInt8(MemoryLayout<sockaddr_un>.size)
        let name = final.path.utf8CString.map { UInt8(bitPattern: $0) }
        try #require(name.count <= MemoryLayout.size(ofValue: address.sun_path))
        withUnsafeMutableBytes(of: &address.sun_path) { buffer in
            buffer.copyBytes(from: name)
        }
        let bound = withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.bind(descriptor, $0, socklen_t(MemoryLayout<sockaddr_un>.size))
            }
        }
        try #require(bound == 0)
        try Data("new audio".utf8).write(to: temporary)
        expectAppError(.invalidArgument) { try publishAudioFile(temporary, to: final, force: true) }
        var entry = stat()
        #expect(Darwin.lstat(final.path, &entry) == 0)
        #expect(entry.st_mode & S_IFMT == S_IFSOCK)
    }
}

private func publicationDirectory() throws -> URL {
    let path = FileManager.default.temporaryDirectory.appendingPathComponent("pub-\(UUID().uuidString.prefix(8))")
    try FileManager.default.createDirectory(at: path, withIntermediateDirectories: false)
    return path
}
