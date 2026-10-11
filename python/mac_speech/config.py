"""Configuration precedence for mac_speech.

Precedence (highest wins): explicit CLI flag > environment variable > built-in
default. No configuration file is read in this phase, and nothing here
requires network access or credentials — only ``os.environ`` is consulted.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

TTS_BINARY_ENV_VAR = "MAC_SPEECH_TTS_BINARY"
WHISPER_PY_CONVERT_BIN_ENV_VAR = "WHISPER_PY_CONVERT_BIN"


@dataclass(frozen=True)
class Config:
    tts_binary_override: str | None
    whisper_py_convert_bin_override: str | None


def load_config() -> Config:
    return Config(
        tts_binary_override=os.environ.get(TTS_BINARY_ENV_VAR, "").strip() or None,
        whisper_py_convert_bin_override=os.environ.get(WHISPER_PY_CONVERT_BIN_ENV_VAR, "").strip() or None,
    )
