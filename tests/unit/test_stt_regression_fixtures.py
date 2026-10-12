"""Regression fixtures for the STT adapter against the real
`whisper-py-convert` engines.

Per PLAN.md Phase 4 ("Add regression fixtures from known audio and
expected transcript properties, respecting privacy"), the audio fixture
is synthesized fresh at test time via macOS `say`, never committed to the
repository — this avoids checking in any audio file while still exercising
the real engines end-to-end.

Native execution requires MAC_SPEECH_TEST_APPLE_STT=1. A read-only inventory
probe checks the selected locale (MAC_SPEECH_TEST_APPLE_LOCALE, default en-US)
before synthesis or transcription. Missing platform/tools/API/installed assets
are prerequisites, not failures; diagnostic and transcription errors on a
provisioned opted-in machine are failures, including risk #19 regressions.
These tests never download assets or select an engine automatically. The
legacy text/SRT entrypoint must discover the same built binary as the probe.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from mac_speech import stt
from mac_speech import capabilities

FIXTURE_TEXT = "The quick brown fox jumps over the lazy dog."


def _require_apple_stt() -> str:
    """Skip only genuine prerequisites, without reserving/downloading assets."""
    if os.environ.get("MAC_SPEECH_TEST_APPLE_STT") != "1":
        pytest.skip("Native Apple STT requires MAC_SPEECH_TEST_APPLE_STT=1")
    if sys.platform != "darwin":
        pytest.skip("Native Apple STT requires macOS")
    if shutil.which("say") is None:
        pytest.skip("macOS `say` is required to synthesize the fixture")
    override = os.environ.get("MAC_SPEECH_TEST_APPLE_BINARY")
    binary = Path(override) if override else capabilities.find_apple_stt_binary()
    if binary is None:
        pytest.skip("Built Apple STT binary is required")
    language = os.environ.get("MAC_SPEECH_TEST_APPLE_LOCALE", "en-US")
    response = subprocess.run(
        [str(binary), "--inventory-status", "--language", language],
        capture_output=True, text=True, check=True, timeout=30,
    )
    try:
        status = json.loads(response.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"Apple STT --inventory-status returned invalid JSON: {exc}")
    if not isinstance(status, dict):
        pytest.fail("Apple STT --inventory-status must return a JSON object")
    if (
        type(status.get("available")) is not bool
        or "supported_locale" not in status
        or (status["supported_locale"] is not None and not isinstance(status["supported_locale"], str))
        or type(status.get("installed")) is not bool
        or not isinstance(status.get("reserved_locales"), list)
        or not all(isinstance(locale, str) for locale in status["reserved_locales"])
        or type(status.get("maximum_reserved_locales")) is not int
    ):
        pytest.fail("Apple STT --inventory-status returned malformed inventory fields")
    if not status["available"]:
        pytest.skip("Apple STT API is unavailable")
    if status["supported_locale"] is None:
        pytest.skip(f"Apple STT locale {language} is unsupported")
    if not status["installed"]:
        pytest.skip(f"Apple STT assets for {language} are not installed; no download attempted")
    return language


@pytest.fixture
def apple_locale(tmp_path, monkeypatch):
    language = _require_apple_stt()
    override = os.environ.get("MAC_SPEECH_TEST_APPLE_BINARY")
    binary = Path(override) if override else capabilities.find_apple_stt_binary()
    assert binary is not None
    script = capabilities.find_whisper_py_convert()
    if script is None:
        pytest.skip("Legacy whisper-py-convert script is required for text/SRT compatibility")
    # The legacy script deliberately has no binary override. A disposable,
    # unchanged copy with a sibling symlink selects this exact executable for
    # text/SRT as well as direct JSON, without replacing installed binaries.
    scratch_script = tmp_path / "whisper-py-convert.py"
    shutil.copyfile(script, scratch_script)
    (tmp_path / "whisper-py-convert-apple").symlink_to(binary.resolve())
    monkeypatch.setattr(stt.client.engine, "find_apple_stt_binary", lambda: binary)
    monkeypatch.setattr(stt.client.engine, "find_whisper_py_convert", lambda: scratch_script)
    return language


@pytest.fixture
def fixture_audio(tmp_path, apple_locale):
    audio_path = tmp_path / "fixture.aiff"
    subprocess.run(["say", "-o", str(audio_path), FIXTURE_TEXT], check=True, timeout=30)
    return str(audio_path)


def test_transcribe_text_contains_expected_words(fixture_audio, apple_locale):
    result = stt.transcribe_text(fixture_audio, engine_name="apple", language=apple_locale)
    lowered = result.content.lower()
    assert "quick" in lowered
    assert "fox" in lowered
    assert result.engine == "apple"


def test_transcribe_srt_segment_timestamps_are_monotonic(fixture_audio, apple_locale):
    result = stt.transcribe_srt(
        fixture_audio, word_timestamps=False, engine_name="apple", language=apple_locale,
    )
    cues = stt.client.engine.parse_srt(result.content)
    assert len(cues) >= 1
    for start, end, text in cues:
        assert start >= 0.0
        assert end >= start
        assert text.strip()


def test_transcribe_srt_word_timestamps_are_ordered_and_non_overlapping(fixture_audio, apple_locale):
    result = stt.transcribe_srt(
        fixture_audio, word_timestamps=True, engine_name="apple", language=apple_locale,
    )
    cues = stt.client.engine.parse_srt(result.content)
    assert len(cues) >= 1
    previous_end = 0.0
    for start, end, _text in cues:
        assert start >= previous_end - 1e-6  # tiny tolerance for float rounding
        assert end >= start
        previous_end = end


def test_transcribe_json_segments_and_words_are_consistent(fixture_audio, apple_locale):
    transcript = stt.transcribe_json(fixture_audio, engine_name="apple", language=apple_locale)
    assert transcript.segments, "expected at least one segment"
    for segment in transcript.segments:
        assert segment.end >= segment.start
        for word in segment.words:
            assert segment.start - 1e-6 <= word.start
            assert word.end <= segment.end + 1e-6
    assert "quick" in transcript.text.lower() or not transcript.segments[0].words
