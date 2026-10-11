import Darwin
import Foundation

func validateAudioOutput(_ destination: URL, force: Bool) throws {
    var entry = stat()
    if Darwin.lstat(destination.path, &entry) != 0 {
        let failure = errno
        if failure == ENOENT { return }
        throw AppError.invalidArgument("Cannot inspect the audio output entry.")
    }
    guard entry.st_mode & S_IFMT == S_IFREG else {
        throw AppError.invalidArgument("Audio output must not be a symlink, directory, or special file, even with --force.")
    }
    if !force {
        throw AppError.outputExists("Audio output already exists.", remedy: "Choose a new path or explicitly pass --force.")
    }
}

struct AudioStagingFile {
    let directory: URL
    let file: URL
    let device: dev_t
    let inode: ino_t
}

/// The private directory also prevents other users opening a descriptor
/// during AVFoundation setup. Reserve the extension-preserving file at
/// 0600, then verify AVFoundation has kept that inode before writing speech.
func createAudioStagingFile(in parent: URL, extension fileExtension: String) throws -> AudioStagingFile {
    let directory = parent.appendingPathComponent(".mac-speech-tts-\(UUID().uuidString)")
    guard Darwin.mkdir(directory.path, 0o700) == 0 else {
        throw AppError(code: .nativeProcessError, message: "Could not create private audio staging directory.")
    }
    let file = directory.appendingPathComponent("audio.\(fileExtension)")
    let descriptor = Darwin.open(file.path, O_CREAT | O_EXCL | O_RDWR, 0o600)
    guard descriptor >= 0 else {
        _ = Darwin.rmdir(directory.path)
        throw AppError(code: .nativeProcessError, message: "Could not reserve private audio staging file.")
    }
    var entry = stat()
    let inspected = Darwin.fstat(descriptor, &entry)
    let closed = Darwin.close(descriptor)
    guard inspected == 0, closed == 0 else {
        _ = Darwin.unlink(file.path)
        _ = Darwin.rmdir(directory.path)
        throw AppError(code: .nativeProcessError, message: "Could not inspect/close audio staging reservation.")
    }
    return AudioStagingFile(directory: directory, file: file, device: entry.st_dev, inode: entry.st_ino)
}

func validateAudioStagingFile(_ staging: AudioStagingFile) throws {
    var entry = stat()
    guard Darwin.lstat(staging.file.path, &entry) == 0,
          entry.st_dev == staging.device, entry.st_ino == staging.inode,
          entry.st_mode & S_IFMT == S_IFREG, entry.st_mode & 0o777 == 0o600 else {
        throw AppError(code: .nativeProcessError, message: "Audio writer did not preserve its private staging reservation.")
    }
}

/// Publish a fully closed audio file without a check-then-delete race.
/// Both paths must be on the same filesystem. No partial-copy fallback:
/// a filesystem that cannot link atomically must fail closed.
func publishAudioFile(_ temporary: URL, to destination: URL, force: Bool) throws {
    try validateAudioOutput(destination, force: force)
    try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: temporary.path)
    if force {
        // POSIX rename replaces the directory entry atomically, not its
        // symlink target, and leaves the old file intact if rename fails.
        guard Darwin.rename(temporary.path, destination.path) == 0 else {
            throw AppError(code: .nativeProcessError, message: "Could not atomically replace audio output (errno \(errno)).")
        }
    } else {
        // link is an atomic create-if-absent, unlike an existence check
        // followed by moveItem/removeItem. A late concurrent writer wins
        // without having its completed file removed by this invocation.
        guard Darwin.link(temporary.path, destination.path) == 0 else {
            let failure = errno
            if failure == EEXIST {
                throw AppError.outputExists(
                    "Audio output already exists.",
                    remedy: "Choose a new output path, or explicitly pass --force."
                )
            }
            throw AppError(
                code: .nativeProcessError,
                message: "Could not atomically publish audio output (errno \(failure)).",
                remedy: "Use a writable local destination supporting same-filesystem hard links."
            )
        }
        guard Darwin.unlink(temporary.path) == 0 else {
            throw AppError(code: .nativeProcessError, message: "Audio was published but temporary-file cleanup failed.")
        }
    }
}
