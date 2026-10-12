import Darwin
import Foundation

/// Serialize cooperating CLI processes across all locales. flock is held until
/// analyzer/results, output and awaited reservation cleanup have completed.
/// Never unlink the lock file (doing so creates independent locks for waiters).
final class ReservationGate {
    private let descriptor: Int32

    init(directory: URL = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/whisper-py-convert")) throws {
        try FileManager.default.createDirectory(at: directory.deletingLastPathComponent(), withIntermediateDirectories: true)
        // mkdir applies the private mode atomically. Foundation's post-create
        // attribute update exposes a transient non-private directory to peers.
        guard mkdir(directory.path, 0o700) == 0 || errno == EEXIST else {
            throw STTFailure(code: "reservation_coordination", message: "Cannot create reservation lock directory (errno \(errno))")
        }
        var directoryInfo = stat()
        guard lstat(directory.path, &directoryInfo) == 0,
              directoryInfo.st_mode & S_IFMT == S_IFDIR,
              directoryInfo.st_uid == getuid(), directoryInfo.st_mode & 0o077 == 0 else {
            throw STTFailure(code: "reservation_coordination", message: "Reservation lock directory must be an owned private directory: \(directory.path)")
        }
        let path = directory.appendingPathComponent("apple-stt-reservations.lock").path
        let fd = open(path, O_CREAT | O_RDWR | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else {
            throw STTFailure(code: "reservation_coordination", message: "Cannot open reservation lock (errno \(errno))")
        }
        var info = stat()
        guard fstat(fd, &info) == 0, info.st_mode & S_IFMT == S_IFREG,
              info.st_uid == getuid(), info.st_mode & 0o077 == 0, info.st_nlink == 1 else {
            close(fd)
            throw STTFailure(code: "reservation_coordination", message: "Reservation lock must be an owned private regular file")
        }
        descriptor = fd
    }

    func acquire() async throws {
        while true {
            try Task.checkCancellation()
            if flock(descriptor, LOCK_EX | LOCK_NB) == 0 { return }
            guard errno == EWOULDBLOCK || errno == EINTR else {
                throw STTFailure(code: "reservation_coordination", message: "Cannot acquire reservation lock (errno \(errno))")
            }
            try await Task.sleep(for: .milliseconds(50))
        }
    }

    func unlock() { flock(descriptor, LOCK_UN) }
    deinit { close(descriptor) }
}
