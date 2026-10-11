"""Typed models for the TTS client, mirroring the native engine's JSON
result shapes exactly (field-for-field):
``engines/tts-swift/Sources/MacSpeechTTSCore/Protocol.swift`` and
``docs/protocol.md``. Keep field names identical on both sides.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Voice:
    identifier: str
    name: str
    language: str
    quality: str
    gender: str
    is_personal_voice: bool
    is_novelty_voice: bool

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Voice":
        return cls(**{field: payload[field] for field in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SpeakResult:
    completed: bool
    stopped_early: bool
    voice_identifier: str
    language: str
    sentence_count: int
    text_length: int

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SpeakResult":
        return cls(**{field: payload[field] for field in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SynthesizeResult:
    output_path: str
    format: str
    sample_rate: float
    channels: int
    bit_depth: int
    duration_seconds: float
    file_size_bytes: int
    sentence_count: int
    voice_identifier: str
    language: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SynthesizeResult":
        return cls(**{field: payload[field] for field in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
