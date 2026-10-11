"""Private, atomic output publication; no network or optional dependencies.

Destinations are regular files in trusted parent directories. Publication
is file-wise, not a transaction spanning audio/manifest/subtitle files.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from .errors import ErrorCode, MacSpeechError


def _output_exists() -> MacSpeechError:
    return MacSpeechError(
        code=ErrorCode.OUTPUT_EXISTS,
        message="Output already exists; it was not overwritten.",
        remedy="Choose a fresh output path or explicitly request force replacement.",
    )


def check_output_path(path: Path, *, force: bool = False) -> None:
    """Reject existing non-regular entries, including dangling symlinks."""
    try:
        entry = path.lstat()
    except FileNotFoundError:
        return
    except (OSError, ValueError) as exc:
        raise MacSpeechError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="Cannot inspect the requested output path.",
            remedy="Choose a valid path in a writable local directory.",
        ) from exc
    if not stat.S_ISREG(entry.st_mode):
        raise MacSpeechError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="Output must not be a symlink, directory, or special file.",
            remedy="Choose a new regular-file output path, including when using force.",
        )
    if not force:
        raise _output_exists()


def publish_staged_file(
    temporary: Path, target: Path, *, force: bool = False,
    expected_identity: tuple[int, int] | None = None,
) -> None:
    """Publish an owned, fully written file on the same filesystem.

    Create-if-absent uses hard links; replacement uses atomic rename. Never
    truncate an existing inode or follow a destination symlink. A racing
    destination entry remains intact unless replacement was explicit.
    The caller remains responsible for cleaning its temporary file on failure.
    """
    check_output_path(target, force=force)
    if expected_identity is not None:
        try:
            current = target.lstat()
        except OSError as exc:
            raise _checkpoint_changed() from exc
        if (current.st_dev, current.st_ino) != expected_identity:
            raise _checkpoint_changed()
    try:
        if force:
            os.replace(temporary, target)
        else:
            os.link(temporary, target)
            temporary.unlink()
    except FileExistsError as exc:
        raise _output_exists() from exc
    except OSError as exc:
        raise MacSpeechError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Could not atomically publish the output file.",
            remedy="Check parent permissions and same-filesystem hard-link support; use a local directory.",
        ) from exc


def _checkpoint_changed() -> MacSpeechError:
    return MacSpeechError(
        code=ErrorCode.OUTPUT_EXISTS,
        message="Workflow checkpoint ownership changed; the other entry was not overwritten.",
        remedy="Use a new basename and do not replace another writer's checkpoint.",
    )


def _write_text(
    path: Path, content: str, *, force: bool = False,
    expected_identity: tuple[int, int] | None = None,
) -> tuple[int, int]:
    check_output_path(path, force=force)
    temporary: Path | None = None
    completed = False
    try:
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            entry = os.fstat(handle.fileno())
            identity = (entry.st_dev, entry.st_ino)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        publish_staged_file(temporary, path, force=force, expected_identity=expected_identity)
        completed = True
    except (OSError, UnicodeError, ValueError) as exc:
        raise MacSpeechError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Could not write the UTF-8 output file.",
            remedy="Check the destination's parent directory and filesystem permissions.",
        ) from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as exc:
                # Never mask the primary write/publication failure. If only
                # cleanup failed after publication, report it without removing
                # the completed output or leaking a raw filesystem exception.
                if completed:
                    raise MacSpeechError(
                        code=ErrorCode.INTERNAL_ERROR,
                        message="Output was published but temporary-file cleanup failed.",
                    ) from exc
    return identity


def atomic_write_text(path: Path, content: str, *, force: bool = False) -> Path:
    """Write private UTF-8 text, refusing replacement unless explicitly forced."""
    _write_text(path, content, force=force)
    return path


def atomic_write_checkpoint(
    path: Path, content: str, *, force: bool = False,
    expected_identity: tuple[int, int] | None = None,
) -> tuple[int, int]:
    """Return the published inode identity for ordinary checkpoint ownership.

    The identity check detects intervening replacement, not a hostile actor
    racing the final check/rename or editing the inode in place. Parents must
    remain trusted and consumers must not independently mutate a live run.
    """
    return _write_text(path, content, force=force, expected_identity=expected_identity)
