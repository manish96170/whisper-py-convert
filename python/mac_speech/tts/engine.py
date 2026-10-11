"""Subprocess engine wrapper for the native `mac-speech-tts` binary.

This is the only module that spawns TTS subprocesses. It owns binary
discovery (via `mac_speech.capabilities.find_tts_binary`), building the
native CLI's argv, timeout/cancellation handling, JSON parsing, protocol
version checking, and mapping native error payloads to `MacSpeechError`.

PID-file-based process control (`send_control_signal`) exists so a
*separate* process invocation — the `mac-speech tts stop/pause/resume`
CLI commands — can control a `speak()` call that is running in another
process (e.g. backgrounded or started from a different terminal). A
`speak()` call running in the current foreground process group can
already be stopped/paused/resumed with ordinary POSIX job control
(Ctrl+C / Ctrl+Z / `fg`) without this, because the native engine installs
its own signal handlers — see docs/tts-engine.md.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from ..capabilities import find_tts_binary
from ..errors import ErrorCode, MacSpeechError
from ..logging_utils import diagnostic
from ..native_protocol import (
    NativeResponse,
    ProtocolVersionError,
    check_protocol_version,
)

DEFAULT_TIMEOUT_SECONDS = 120.0

_PROTOCOL_VERSION_REMEDY = (
    "Install the Python wrapper and native TTS binary from the same source checkout or release. "
    "For a source checkout, run `python -m pip install -e .` and `./install.sh tts`. "
    "Check MAC_SPEECH_TTS_BINARY and PATH for an older binary."
)

# Text longer than this is piped to the native process's stdin instead of
# passed as an argv value, to stay well clear of OS command-line length
# limits for long narration scripts. This is an internal transport detail;
# callers of speak()/synthesize_to_file() never need to think about it.
STDIN_TRANSPORT_THRESHOLD_CHARS = 4_000

PID_FILE_ENV_VAR = "MAC_SPEECH_TTS_PID_FILE"


def resolve_binary() -> Path:
    binary = find_tts_binary()
    if binary is None:
        raise MacSpeechError(
            code=ErrorCode.ENGINE_NOT_FOUND,
            message="Native TTS engine (mac-speech-tts) was not found.",
            remedy=(
                "Run ./install.sh on macOS, build it directly with "
                "`swift build --package-path engines/tts-swift --configuration release`, "
                "or set MAC_SPEECH_TTS_BINARY to a built binary. "
                "Run `mac-speech doctor` for details."
            ),
        )
    return binary


def _build_command(
    binary: Path,
    operation: str,
    *,
    text: str | None,
    use_stdin: bool,
    voice: str | None,
    language: str | None,
    rate: float | None,
    output_path: str | None,
    format: str | None,
    force: bool,
    timeout: float,
) -> list[str]:
    command = [str(binary), operation]
    if voice:
        command += ["--voice", voice]
    if language:
        command += ["--language", language]
    if rate is not None:
        command += ["--rate", str(rate)]
    if output_path:
        command += ["--output", output_path]
    if format:
        command += ["--format", format]
    if force:
        command.append("--force")
    command += ["--timeout", str(timeout)]
    if use_stdin:
        command.append("--stdin")
    elif text is not None:
        command.append(text)
    return command


def run_operation(
    operation: str,
    *,
    text: str | None = None,
    voice: str | None = None,
    language: str | None = None,
    rate: float | None = None,
    output_path: str | None = None,
    format: str | None = None,
    force: bool = False,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    track_pid: bool = False,
) -> dict[str, Any]:
    """Runs one `mac-speech-tts` invocation to completion and returns its
    `result` payload as a plain dict. Raises `MacSpeechError` for every
    failure mode: missing engine, a native-reported error, invalid JSON,
    a protocol version mismatch, or a process timeout.
    """
    binary = resolve_binary()
    use_stdin = text is not None and len(text) > STDIN_TRANSPORT_THRESHOLD_CHARS
    command = _build_command(
        binary,
        operation,
        text=text,
        use_stdin=use_stdin,
        voice=voice,
        language=language,
        rate=rate,
        output_path=output_path,
        format=format,
        force=force,
        timeout=timeout,
    )

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if use_stdin else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    pid_file = _pid_file_path() if track_pid else None
    if pid_file is not None:
        _write_pid_file(pid_file, process.pid)

    # A small grace period beyond the native engine's own --timeout: the
    # native process is expected to time out and exit on its own first;
    # this is a defense-in-depth backstop, not the primary mechanism.
    try:
        stdout_data, stderr_data = process.communicate(
            input=text if use_stdin else None, timeout=timeout + 10
        )
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise MacSpeechError(
            code=ErrorCode.TIMEOUT,
            message=f"mac-speech-tts did not exit within {timeout + 10:.0f} seconds; it was terminated.",
        )
    finally:
        if pid_file is not None:
            _remove_pid_file(pid_file)

    for line in (stderr_data or "").splitlines():
        diagnostic(f"[mac-speech-tts] {line}")

    return _parse_response(stdout_data, exit_code=process.returncode)


def _parse_response(stdout_data: str, *, exit_code: int) -> dict[str, Any]:
    if not stdout_data or not stdout_data.strip():
        raise MacSpeechError(
            code=ErrorCode.NATIVE_PROCESS_ERROR,
            message=f"mac-speech-tts produced no output (exit code {exit_code}).",
        )
    try:
        payload = json.loads(stdout_data)
    except json.JSONDecodeError as exc:
        raise MacSpeechError(
            code=ErrorCode.NATIVE_PROCESS_ERROR,
            message=f"mac-speech-tts returned invalid JSON: {exc}",
        ) from exc

    if not isinstance(payload, dict):
        raise MacSpeechError(
            code=ErrorCode.NATIVE_PROCESS_ERROR,
            message="mac-speech-tts returned invalid JSON response: expected an object.",
        )

    try:
        response = NativeResponse.from_dict(payload)
        check_protocol_version(response)
    except ProtocolVersionError as exc:
        raise MacSpeechError(
            code=ErrorCode.PROTOCOL_VERSION_MISMATCH,
            message=str(exc),
            remedy=_PROTOCOL_VERSION_REMEDY,
        ) from exc

    if response.status != "ok":
        error = response.error or {}
        try:
            code = ErrorCode(error.get("code", "internal_error"))
        except ValueError:
            code = ErrorCode.INTERNAL_ERROR
        remedy = error.get("remedy")
        if code == ErrorCode.PROTOCOL_VERSION_MISMATCH and not remedy:
            remedy = _PROTOCOL_VERSION_REMEDY
        raise MacSpeechError(
            code=code,
            message=error.get("message", "mac-speech-tts reported an unknown error."),
            remedy=remedy,
        )

    return response.result or {}


# --- PID-file-based process control -----------------------------------


def _pid_file_path() -> Path:
    override = os.environ.get(PID_FILE_ENV_VAR, "").strip()
    if override:
        return Path(override)
    cache_dir = Path(
        os.environ.get("XDG_CACHE_HOME", "").strip() or (Path.home() / ".cache")
    )
    return cache_dir / "mac-speech" / "tts.pid"


def _write_pid_file(path: Path, pid: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid), encoding="utf-8")


def _remove_pid_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else; treat as alive
    return True


def read_tracked_pid() -> int | None:
    """Returns the PID of a `speak()` call tracked via the PID file, or
    `None` if there isn't one or it is stale (process no longer running —
    in which case the stale file is cleaned up)."""
    path = _pid_file_path()
    if not path.is_file():
        return None
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None
    if not _process_is_alive(pid):
        _remove_pid_file(path)
        return None
    return pid


def send_control_signal(sig: int) -> None:
    pid = read_tracked_pid()
    if pid is None:
        raise MacSpeechError(
            code=ErrorCode.ENGINE_NOT_FOUND,
            message="No running `mac-speech tts speak` process was found.",
            remedy="Start one with `mac-speech tts speak <text>` first.",
        )
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        _remove_pid_file(_pid_file_path())
        raise MacSpeechError(
            code=ErrorCode.ENGINE_NOT_FOUND,
            message="The tracked `speak` process is no longer running.",
        )
