#!/usr/bin/env python3
"""Example: using mac_speech.tts directly from a Python script.

Run from the repository root after setting up the venv (see
python/README.md):

    .venv/bin/python examples/tts_python_script.py

This never requires the STT package/binary — only mac_speech.tts and a
built native TTS engine (see docs/tts-engine.md).
"""

from __future__ import annotations

import sys

from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.tts import list_voices, speak, synthesize_to_file


def main() -> int:
    try:
        voices = list_voices(language="en-US")
    except MacSpeechError as exc:
        print(f"Could not list voices: {exc.message}", file=sys.stderr)
        if exc.remedy:
            print(exc.remedy, file=sys.stderr)
        return exc.exit_code

    print(f"Found {len(voices)} en-US voices; using the first one: {voices[0].identifier if voices else 'default'}")

    # Speak a short phrase through the default audio output. This blocks
    # until finished. If this script is itself run in a terminal's
    # foreground, Ctrl+C/Ctrl+Z/`fg` work transparently (see
    # docs/tts-engine.md) — no extra code is needed for that case.
    try:
        result = speak("Hello from the mac speech toolkit Python example.")
        print(f"Spoke {result.sentence_count} sentence(s); completed={result.completed}")
    except MacSpeechError as exc:
        print(f"speak() failed: {exc.message}", file=sys.stderr)
        return exc.exit_code

    # Synthesize to a file. synthesize_to_file() never overwrites an
    # existing file unless force=True.
    output_path = "examples/output/narration.wav"
    try:
        save_result = synthesize_to_file(
            "This narration was synthesized to a file by the example script.",
            output_path=output_path,
            force=True,
        )
    except MacSpeechError as exc:
        if exc.code is ErrorCode.ENGINE_NOT_FOUND:
            print(f"Native TTS engine not found: {exc.remedy}", file=sys.stderr)
        else:
            print(f"synthesize_to_file() failed: {exc.message}", file=sys.stderr)
        return exc.exit_code

    print(f"Saved {save_result.duration_seconds:.2f}s of {save_result.format} audio to {save_result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
