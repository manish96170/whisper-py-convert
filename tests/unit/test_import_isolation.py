"""Verify mac_speech can be imported without a TTS model, a built native
binary, cloud credentials, or network access (PLAN.md Phase 1 acceptance
criteria), and that calling a TTS/STT function without a usable engine
still fails cleanly rather than crashing (Phase 3/4).

Runs in a subprocess so module-level import side effects would be caught
even if some other test already imported the package in-process.
"""

from __future__ import annotations

import subprocess
import sys


def test_import_mac_speech_has_no_side_effects():
    result = subprocess.run(
        [sys.executable, "-c", "import mac_speech; import mac_speech.tts; import mac_speech.stt"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


def test_tts_functions_raise_engine_not_found_cleanly_when_binary_missing(monkeypatch):
    """TTS is implemented as of Phase 3, so these no longer raise
    NOT_IMPLEMENTED. This verifies that a missing native engine still
    fails cleanly with an actionable error rather than a crash, without
    spawning a real subprocess or making any sound."""
    import mac_speech.tts as tts
    from mac_speech.errors import ErrorCode, MacSpeechError

    monkeypatch.setattr(tts.engine, "resolve_binary", lambda: (_ for _ in ()).throw(
        MacSpeechError(code=ErrorCode.ENGINE_NOT_FOUND, message="not found", remedy="build it")
    ))

    for call in (
        lambda: tts.list_voices(),
        lambda: tts.speak("hello"),
        lambda: tts.synthesize_to_file("hello", output_path="out.aiff"),
    ):
        try:
            call()
        except MacSpeechError as exc:
            assert exc.code is ErrorCode.ENGINE_NOT_FOUND
        else:
            raise AssertionError("expected MacSpeechError to be raised")


def test_stt_transcribe_raises_engine_not_found_cleanly_when_script_missing(monkeypatch):
    """STT's text/srt/json paths are implemented as of Phase 4, so this no
    longer raises NOT_IMPLEMENTED. This verifies that a missing
    `whisper-py-convert` script still fails cleanly with an actionable
    error rather than a crash, without spawning a real subprocess."""
    import mac_speech.stt as stt
    from mac_speech.errors import ErrorCode, MacSpeechError

    monkeypatch.setattr(
        stt.engine,
        "resolve_whisper_py_convert",
        lambda: (_ for _ in ()).throw(
            MacSpeechError(code=ErrorCode.ENGINE_NOT_FOUND, message="not found", remedy="install it")
        ),
    )

    try:
        stt.transcribe("recording.m4a")
    except MacSpeechError as exc:
        assert exc.code is ErrorCode.ENGINE_NOT_FOUND
    else:
        raise AssertionError("expected MacSpeechError to be raised")
