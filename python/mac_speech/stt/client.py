"""Public STT client functions.

Importing this module never requires a built native binary, a downloaded
faster-whisper model, or network access — only *calling* these functions
does. A missing engine raises
`MacSpeechError(code=ErrorCode.ENGINE_NOT_FOUND)` with an actionable
remedy.
"""

from __future__ import annotations

from ..errors import ErrorCode, MacSpeechError
from . import engine
from .models import TranscribeResult, Transcript
from .webvtt import srt_to_webvtt

DEFAULT_TIMEOUT_SECONDS = engine.DEFAULT_TIMEOUT_SECONDS


def transcribe_text(
    path: str,
    *,
    engine_name: str = "auto",
    model: str | None = None,
    language: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> TranscribeResult:
    """Plain-text transcription — shells out to the existing
    `whisper-py-convert` entrypoint and returns its output exactly as
    produced."""
    return engine.run_text_or_srt(
        path, output_format="text", engine=engine_name, model=model, language=language, timeout=timeout
    )


def transcribe_srt(
    path: str,
    *,
    word_timestamps: bool = False,
    engine_name: str = "auto",
    model: str | None = None,
    language: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> TranscribeResult:
    """SRT transcription — shells out to the existing `whisper-py-convert`
    entrypoint with `--srt` and returns its output exactly as produced."""
    return engine.run_text_or_srt(
        path,
        output_format="srt",
        engine=engine_name,
        model=model,
        language=language,
        word_ts=word_timestamps,
        seg_ts=not word_timestamps,
        timeout=timeout,
    )


def transcribe_json(
    path: str,
    *,
    engine_name: str = "auto",
    model: str | None = None,
    language: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Transcript:
    """Structured transcription with segments/words. Full fidelity on the
    Apple engine (native multi-segment JSON); a best-effort single-segment
    approximation on faster-whisper (derived from a word-level SRT) and on
    the Windows engine (plain text only, no real timing) — see
    `Transcript.engine` and docs/tts-engine.md-equivalent notes in
    `mac_speech/stt/engine.py` for exactly what each engine actually
    supports."""
    return engine.run_json(path, engine=engine_name, model=model, language=language, timeout=timeout)


def transcribe_webvtt(
    path: str,
    *,
    word_timestamps: bool = False,
    engine_name: str = "auto",
    model: str | None = None,
    language: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> TranscribeResult:
    """WebVTT transcription: gets SRT from the existing `whisper-py-convert`
    entrypoint, then reformats it to WebVTT (`.vtt`) — a lossless,
    non-semantic conversion (see `mac_speech.stt.webvtt`)."""
    srt_result = transcribe_srt(
        path,
        word_timestamps=word_timestamps,
        engine_name=engine_name,
        model=model,
        language=language,
        timeout=timeout,
    )
    return TranscribeResult(engine=srt_result.engine, format="webvtt", content=srt_to_webvtt(srt_result.content))


def transcribe(
    path: str,
    *,
    output_format: str = "text",
    engine_name: str = "auto",
    model: str | None = None,
    language: str | None = None,
    word_timestamps: bool = False,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> TranscribeResult | Transcript:
    """Convenience dispatcher matching the shape sketched in PLAN.md
    section 4.2: `transcribe(path, output_format="json")`. Prefer the
    explicit `transcribe_text`/`transcribe_srt`/`transcribe_json`/
    `transcribe_webvtt` for a stable return type in typed code."""
    if output_format == "text":
        return transcribe_text(path, engine_name=engine_name, model=model, language=language, timeout=timeout)
    if output_format == "srt":
        return transcribe_srt(
            path,
            word_timestamps=word_timestamps,
            engine_name=engine_name,
            model=model,
            language=language,
            timeout=timeout,
        )
    if output_format == "webvtt":
        return transcribe_webvtt(
            path,
            word_timestamps=word_timestamps,
            engine_name=engine_name,
            model=model,
            language=language,
            timeout=timeout,
        )
    if output_format == "json":
        return transcribe_json(path, engine_name=engine_name, model=model, language=language, timeout=timeout)
    raise MacSpeechError(
        code=ErrorCode.INVALID_ARGUMENT,
        message=f"Unsupported output_format '{output_format}'.",
        remedy="Use 'text', 'srt', 'webvtt', or 'json'.",
    )
