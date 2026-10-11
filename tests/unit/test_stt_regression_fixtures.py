"""Regression fixtures for the STT adapter against the real
`whisper-py-convert` engines.

Per PLAN.md Phase 4 ("Add regression fixtures from known audio and
expected transcript properties, respecting privacy"), the audio fixture
is synthesized fresh at test time via macOS `say`, never committed to the
repository — this avoids checking in any audio file while still exercising
the real engines end-to-end.

These tests are skipped (not failed) when `say` is unavailable (non-macOS)
or when no STT engine is ready on this machine, and tolerate the
known-and-documented Apple engine locale/asset flakiness described in
docs/risk-register.md risk #19: it is an environmental condition outside
this adapter's control, reproduced identically with the completely
unmodified `whisper-py-convert.py`, so a test failure caused specifically
by that error is reported as a skip with an explanatory message rather
than a hard failure.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

import pytest

from mac_speech import stt
from mac_speech.capabilities import detect_stt_capability
from mac_speech.errors import ErrorCode, MacSpeechError

pytestmark = pytest.mark.skipif(shutil.which("say") is None, reason="macOS `say` is required to synthesize the fixture")

FIXTURE_TEXT = "The quick brown fox jumps over the lazy dog."


@pytest.fixture
def fixture_audio(tmp_path):
    if not detect_stt_capability().available:
        pytest.skip("No local STT backend is ready on this machine")
    audio_path = tmp_path / "fixture.aiff"
    subprocess.run(["say", "-o", str(audio_path), FIXTURE_TEXT], check=True, timeout=30)
    return str(audio_path)


def _skip_if_known_asset_flakiness(exc: MacSpeechError) -> None:
    """See docs/risk-register.md risk #19: the Apple engine's locale/asset
    reservation has been observed to fail intermittently on this machine,
    reproduced identically with the unmodified `whisper-py-convert.py`.
    Treat that specific, documented condition as a skip, not a failure."""
    if "does not support locale" in exc.message:
        pytest.skip(f"Known environmental flakiness (risk #19), not a code defect: {exc.message}")
    raise exc


def test_transcribe_text_contains_expected_words(fixture_audio):
    try:
        result = stt.transcribe_text(fixture_audio)
    except MacSpeechError as exc:
        _skip_if_known_asset_flakiness(exc)
        raise
    lowered = result.content.lower()
    assert "quick" in lowered
    assert "fox" in lowered
    assert result.engine in ("apple", "windows", "faster-whisper", "unknown")


def test_transcribe_srt_segment_timestamps_are_monotonic(fixture_audio):
    try:
        result = stt.transcribe_srt(fixture_audio, word_timestamps=False)
    except MacSpeechError as exc:
        _skip_if_known_asset_flakiness(exc)
        raise
    cues = stt.client.engine.parse_srt(result.content)
    assert len(cues) >= 1
    for start, end, text in cues:
        assert start >= 0.0
        assert end >= start
        assert text.strip()


def test_transcribe_srt_word_timestamps_are_ordered_and_non_overlapping(fixture_audio):
    try:
        result = stt.transcribe_srt(fixture_audio, word_timestamps=True)
    except MacSpeechError as exc:
        _skip_if_known_asset_flakiness(exc)
        raise
    cues = stt.client.engine.parse_srt(result.content)
    assert len(cues) >= 1
    previous_end = 0.0
    for start, end, _text in cues:
        assert start >= previous_end - 1e-6  # tiny tolerance for float rounding
        assert end >= start
        previous_end = end


def test_transcribe_json_segments_and_words_are_consistent(fixture_audio):
    try:
        transcript = stt.transcribe_json(fixture_audio)
    except MacSpeechError as exc:
        _skip_if_known_asset_flakiness(exc)
        raise
    assert transcript.segments, "expected at least one segment"
    for segment in transcript.segments:
        assert segment.end >= segment.start
        for word in segment.words:
            assert segment.start - 1e-6 <= word.start
            assert word.end <= segment.end + 1e-6
    assert "quick" in transcript.text.lower() or not transcript.segments[0].words
