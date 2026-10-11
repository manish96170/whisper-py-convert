"""SRT <-> WebVTT conversion (PLAN.md Phase 7: "Add optional WebVTT
support if required by target workflows").

WebVTT is what HTML5 `<track>` elements and most web-based video editors
expect; SRT is what `whisper-py-convert` and this toolkit produce by
default. The conversion is a thin, lossless reformatting — no timing or
text is reinterpreted.
"""

from __future__ import annotations

from .engine import parse_srt


def srt_to_webvtt(srt_content: str) -> str:
    """Converts SRT content (as produced by `whisper-py-convert.py`'s
    `render_srt()`) to WebVTT. WebVTT uses `.` instead of `,` as the
    millisecond separator and requires a `WEBVTT` header line; cue index
    numbers are dropped (optional in WebVTT, omitted here for brevity)."""
    cues = parse_srt(srt_content)
    lines = ["WEBVTT", ""]
    for start, end, text in cues:
        lines.append(f"{_webvtt_timestamp(start)} --> {_webvtt_timestamp(end)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _webvtt_timestamp(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
