"""Public TTS client functions.

Importing this module never requires the native engine to be built, a
model, or network access — only *calling* these functions does. A
missing engine raises `MacSpeechError(code=ErrorCode.ENGINE_NOT_FOUND)`
with an actionable remedy.
"""

from __future__ import annotations

import signal

from . import engine
from .models import SpeakResult, SynthesizeResult, Voice

DEFAULT_TIMEOUT_SECONDS = engine.DEFAULT_TIMEOUT_SECONDS


def list_voices(*, language: str | None = None, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> list[Voice]:
    """Lists voices the native engine actually reports right now — never a
    hard-coded list (PLAN.md Phase 3: "Ensure voice listing uses actual
    engine capabilities rather than hard-coded assumptions."). Entries
    with `is_personal_voice=True` are only ever present when Apple's own
    API already considers them available and authorized for this process
    — this function never implies it can create, extract, or unlock a
    Personal Voice itself; see `personal_voice_status()` and
    docs/tts-engine.md."""
    result = engine.run_operation("voices", language=language, timeout=timeout)
    return [Voice.from_dict(voice) for voice in result.get("voices", [])]


def personal_voice_status(*, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Reports (never requests) the current Personal Voice authorization
    status for this process: one of `"not_determined"`, `"denied"`,
    `"unsupported"`, `"authorized"`, or `"unknown"`.

    There is deliberately no function here to *request* authorization —
    Phase 5 discovery found that `AVSpeechSynthesizer
    .requestPersonalVoiceAuthorization`'s completion handler never fires
    from this bare command-line engine (most likely because it has no
    app bundle/`Info.plist`, and therefore no
    `NSPersonalVoiceUsageDescription` for the system to show a prompt
    from). Authorization must happen some other way (e.g. a properly
    bundled app, or because the user has already set up and used
    Personal Voice elsewhere on this Mac) — this function only reports
    whatever the system already decided. See docs/tts-engine.md."""
    result = engine.run_operation("personal-voice-status", timeout=timeout)
    return result.get("authorization_status", "unknown")


def speak(
    text: str,
    *,
    voice: str | None = None,
    rate: float | None = None,
    language: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    track_for_control: bool = True,
) -> SpeakResult:
    """Speaks `text` through the default audio output, blocking until it
    finishes or is interrupted.

    Standard POSIX job control works transparently when this runs as a
    terminal's foreground process: Ctrl+C stops, Ctrl+Z pauses, `fg`
    resumes, because the native engine installs its own signal handlers
    and this function does not change the process group (see
    docs/tts-engine.md). `stop()`/`pause()`/`resume()` in this module are
    for controlling a `speak()` call from a *different* process — pass
    `track_for_control=False` to skip writing the PID file (for example,
    when running many short, unrelated `speak()` calls concurrently where
    cross-process control is not needed and would race on one PID file).
    """
    result = engine.run_operation(
        "speak",
        text=text,
        voice=voice,
        rate=rate,
        language=language,
        timeout=timeout,
        track_pid=track_for_control,
    )
    return SpeakResult.from_dict(result)


def synthesize_to_file(
    text: str,
    *,
    output_path: str,
    voice: str | None = None,
    rate: float | None = None,
    language: str | None = None,
    format: str = "wav",
    force: bool = False,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> SynthesizeResult:
    """Synthesizes `text` to an audio file at `output_path`. Raises
    `MacSpeechError(code=ErrorCode.OUTPUT_EXISTS)` if the file already
    exists and `force` is not set — this function never overwrites
    silently."""
    result = engine.run_operation(
        "save",
        text=text,
        voice=voice,
        rate=rate,
        language=language,
        output_path=output_path,
        format=format,
        force=force,
        timeout=timeout,
    )
    return SynthesizeResult.from_dict(result)


def stop() -> None:
    """Stops a `speak()` call tracked via its PID file."""
    engine.send_control_signal(signal.SIGTERM)


def pause() -> None:
    """Pauses a `speak()` call tracked via its PID file."""
    engine.send_control_signal(signal.SIGTSTP)


def resume() -> None:
    """Resumes a paused `speak()` call tracked via its PID file."""
    engine.send_control_signal(signal.SIGCONT)
