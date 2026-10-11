"""Transcript -> SRT rendering (supports PLAN.md Phase 11's pipeline).

Mirrors `whisper-py-convert.py`'s own `srt_timestamp()`/`render_srt()`
format exactly (comma millisecond separator, same cue numbering), so
output is interchangeable with that tool's SRT files — but operates on
a `mac_speech.stt.models.Transcript` object directly (e.g. one produced
by `mac_speech.align`), which a pipeline stage needs and the existing
script's CLI-only rendering does not expose as a reusable function.
"""

from __future__ import annotations

from .models import Transcript


def _srt_timestamp(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def transcript_to_srt(transcript: Transcript, *, word_timestamps: bool = False) -> str:
    cues: list[tuple[float, float, str]] = []
    for segment in transcript.segments:
        if word_timestamps and segment.words:
            cues.extend((word.start, word.end, word.text) for word in segment.words if word.text)
        elif segment.text:
            cues.append((segment.start, segment.end, segment.text))
    return "\n".join(
        f"{index}\n{_srt_timestamp(start)} --> {_srt_timestamp(end)}\n{text}\n"
        for index, (start, end, text) in enumerate(cues, 1)
    )
