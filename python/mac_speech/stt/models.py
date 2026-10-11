"""Typed models for the STT adapter.

`Word`, `Segment`, and `Transcript` deliberately mirror the shape already
used internally by `whisper-py-convert.py` (its own `Word`/`Segment`/
`Transcript` dataclasses) — not by importing them (see
docs/decisions/ADR-001-repository-and-module-boundaries.md: "never
importing or forking whisper-py-convert.py internals"), but by
independently reproducing the same, already-stable shape so that parsing
either the Apple binary's native JSON or a rendered SRT file produces
consistent results.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Word:
    text: str
    start: float
    end: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Segment:
    text: str
    start: float
    end: float
    words: list[Word] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "start": self.start, "end": self.end, "words": [w.to_dict() for w in self.words]}


@dataclass
class Transcript:
    segments: list[Segment]
    engine: str

    @property
    def text(self) -> str:
        body = "\n".join(segment.text.strip() for segment in self.segments if segment.text.strip()).strip()
        return body + "\n" if body else ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "text": self.text,
            "segments": [s.to_dict() for s in self.segments],
        }


@dataclass
class TranscribeResult:
    """Result of a `text`/`srt` transcription — content exactly as the
    existing `whisper-py-convert` tool would have produced it, plus which
    engine it resolved to (parsed from that tool's own "Engine: X"
    stderr line, which it already prints today)."""

    engine: str
    format: str  # "text" | "srt"
    content: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
