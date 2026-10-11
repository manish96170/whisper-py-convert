"""Alignment interface (PLAN.md Phase 7: "Add a future alignment
interface that can consume generated speech and text to produce word
timings, without pretending TTS inherently supplies them.").

`AVSpeechSynthesizer` never reports word-level timing for synthesized
speech (`mac_speech.tts.SpeakResult`/`SynthesizeResult` intentionally
have no per-word timestamps — see docs/tts-engine.md). This module
provides an explicit, honestly-labeled *approximation*: run the
synthesized audio back through STT and use its own recognized word
timestamps as a stand-in for alignment. This is not phoneme-level
forced alignment, and the recognized text is not guaranteed to exactly
match the original input (STT can mis-hear words, especially short
ones or homophones) — callers that need guaranteed-correct word-to-text
mapping should not rely on this alone.
"""

from __future__ import annotations

from .stt.models import Transcript
from .stt.client import transcribe_json


def align_via_stt_roundtrip(
    audio_path: str,
    *,
    engine_name: str = "auto",
    language: str | None = None,
) -> Transcript:
    """Approximates word-level timing for a synthesized audio file by
    transcribing it with the STT adapter. The returned `Transcript`'s
    words are STT's own recognized words and timestamps — not the
    original TTS input text, and not verified to match it word-for-word.
    This is the only alignment mechanism this toolkit provides; it is
    deliberately not labeled "forced alignment," which implies matching
    against known reference text at the phoneme level."""
    return transcribe_json(audio_path, engine_name=engine_name, language=language)
