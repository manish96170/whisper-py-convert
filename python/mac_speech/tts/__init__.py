"""TTS client: list voices, speak text, and synthesize audio files using
the native `mac-speech-tts` engine (`engines/tts-swift/`).

Importing this package never requires the native engine to be built, a
model, or network access — only *calling* these functions does. A missing
engine raises `MacSpeechError(code=ErrorCode.ENGINE_NOT_FOUND)` with an
actionable remedy (see `mac-speech doctor` and docs/tts-engine.md).
"""

from __future__ import annotations

from .client import list_voices, pause, personal_voice_status, resume, speak, stop, synthesize_to_file
from .models import SpeakResult, SynthesizeResult, Voice

__all__ = [
    "list_voices",
    "personal_voice_status",
    "speak",
    "synthesize_to_file",
    "stop",
    "pause",
    "resume",
    "SpeakResult",
    "SynthesizeResult",
    "Voice",
]
