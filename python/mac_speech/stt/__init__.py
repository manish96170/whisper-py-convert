"""STT adapter: transcribe audio/video files using the existing
`whisper-py-convert` engines (Apple SpeechAnalyzer, Windows AI Speech,
faster-whisper).

This never imports or forks `whisper-py-convert.py` — see
`../../docs/decisions/ADR-001-repository-and-module-boundaries.md`.
Importing this package never requires a built native binary, a
downloaded model, or network access — only *calling* these functions
does. A missing engine raises
`MacSpeechError(code=ErrorCode.ENGINE_NOT_FOUND)` with an actionable
remedy.
"""

from __future__ import annotations

from .client import transcribe, transcribe_json, transcribe_srt, transcribe_text, transcribe_webvtt
from .models import Segment, Transcript, TranscribeResult, Word

__all__ = [
    "transcribe",
    "transcribe_text",
    "transcribe_srt",
    "transcribe_webvtt",
    "transcribe_json",
    "TranscribeResult",
    "Transcript",
    "Segment",
    "Word",
]
