"""Unit tests for mac_speech.stt.engine.

Subprocess calls are mocked throughout — these tests never spawn the real
`whisper-py-convert`/`whisper-py-convert-apple` processes, per PLAN.md
section 8.1. The real engines are exercised manually (see
docs/risk-register.md risk #19 for a known environmental flakiness in the
Apple engine's locale/asset reservation on this machine, unrelated to
this adapter's code).
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.stt import engine


def _fake_result(stdout: str = "", stderr: str = "", returncode: int = 0) -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


def test_resolve_whisper_py_convert_raises_engine_not_found(monkeypatch):
    monkeypatch.setattr(engine, "find_whisper_py_convert", lambda: None)
    with pytest.raises(MacSpeechError) as excinfo:
        engine.resolve_whisper_py_convert()
    assert excinfo.value.code == ErrorCode.ENGINE_NOT_FOUND


def test_run_text_or_srt_success_parses_engine_line(monkeypatch, tmp_path):
    script = tmp_path / "whisper-py-convert.py"
    script.write_text("# fake\n")
    monkeypatch.setattr(engine, "find_whisper_py_convert", lambda: script)

    result = _fake_result(stdout="Hello world.\n", stderr="Engine: apple\n")
    with patch.object(subprocess, "run", return_value=result) as run:
        transcribe_result = engine.run_text_or_srt("recording.mp3", output_format="text")

    assert transcribe_result.engine == "apple"
    assert transcribe_result.format == "text"
    assert transcribe_result.content == "Hello world.\n"
    command = run.call_args.args[0]
    assert command[1] == str(script)
    assert command[-1] == "recording.mp3"


def test_run_text_or_srt_builds_srt_word_ts_flags(monkeypatch, tmp_path):
    script = tmp_path / "whisper-py-convert.py"
    script.write_text("# fake\n")
    monkeypatch.setattr(engine, "find_whisper_py_convert", lambda: script)
    result = _fake_result(stdout="1\n00:00:00,000 --> 00:00:01,000\nHi\n", stderr="Engine: apple\n")

    with patch.object(subprocess, "run", return_value=result) as run:
        engine.run_text_or_srt(
            "r.mp3", output_format="srt", word_ts=True, model="small.en", language="en-US"
        )
    command = run.call_args.args[0]
    assert "--srt" in command
    assert "--word-ts" in command
    assert "--seg-ts" not in command
    assert "--model" in command and "small.en" in command
    assert "--language" in command and "en-US" in command


def test_run_text_or_srt_input_not_found(monkeypatch, tmp_path):
    script = tmp_path / "whisper-py-convert.py"
    script.write_text("# fake\n")
    monkeypatch.setattr(engine, "find_whisper_py_convert", lambda: script)
    result = _fake_result(stderr="Input file does not exist or is not a file: x.mp3", returncode=1)

    with patch.object(subprocess, "run", return_value=result):
        with pytest.raises(MacSpeechError) as excinfo:
            engine.run_text_or_srt("x.mp3", output_format="text")
    assert excinfo.value.code == ErrorCode.INPUT_NOT_FOUND


def test_run_text_or_srt_engine_unavailable(monkeypatch, tmp_path):
    script = tmp_path / "whisper-py-convert.py"
    script.write_text("# fake\n")
    monkeypatch.setattr(engine, "find_whisper_py_convert", lambda: script)
    result = _fake_result(stderr="Apple Speech backend is not built. Run ./install.sh", returncode=1)

    with patch.object(subprocess, "run", return_value=result):
        with pytest.raises(MacSpeechError) as excinfo:
            engine.run_text_or_srt("x.mp3", output_format="text", engine="apple")
    assert excinfo.value.code == ErrorCode.ENGINE_NOT_FOUND


def test_run_text_or_srt_generic_failure(monkeypatch, tmp_path):
    script = tmp_path / "whisper-py-convert.py"
    script.write_text("# fake\n")
    monkeypatch.setattr(engine, "find_whisper_py_convert", lambda: script)
    result = _fake_result(stderr="something unexpected went wrong", returncode=1)

    with patch.object(subprocess, "run", return_value=result):
        with pytest.raises(MacSpeechError) as excinfo:
            engine.run_text_or_srt("x.mp3", output_format="text")
    assert excinfo.value.code == ErrorCode.NATIVE_PROCESS_ERROR


def test_run_text_or_srt_timeout(monkeypatch, tmp_path):
    script = tmp_path / "whisper-py-convert.py"
    script.write_text("# fake\n")
    monkeypatch.setattr(engine, "find_whisper_py_convert", lambda: script)

    with patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd="x", timeout=5)):
        with pytest.raises(MacSpeechError) as excinfo:
            engine.run_text_or_srt("x.mp3", output_format="text", timeout=5)
    assert excinfo.value.code == ErrorCode.TIMEOUT


# --- SRT parsing -------------------------------------------------------------

def test_parse_srt_segment_level():
    content = "1\n00:00:00,000 --> 00:00:02,460\nThis is a local transcription test.\n"
    cues = engine.parse_srt(content)
    assert cues == [(0.0, 2.46, "This is a local transcription test.")]


def test_parse_srt_word_level_multiple_cues():
    content = (
        "1\n00:00:00,000 --> 00:00:00,300\nThis\n"
        "\n"
        "2\n00:00:00,300 --> 00:00:00,540\nis\n"
    )
    cues = engine.parse_srt(content)
    assert cues == [(0.0, 0.3, "This"), (0.3, 0.54, "is")]


def test_parse_srt_empty_content_returns_no_cues():
    assert engine.parse_srt("") == []


def test_parse_srt_timestamp_invalid_raises():
    with pytest.raises(ValueError):
        engine._parse_srt_timestamp("not-a-timestamp")


# --- JSON / engine resolution -------------------------------------------------

def test_resolve_engine_for_json_apple_explicit_missing_binary(monkeypatch):
    monkeypatch.setattr(engine, "find_apple_stt_binary", lambda: None)
    with pytest.raises(MacSpeechError) as excinfo:
        engine._resolve_engine_for_json("apple")
    assert excinfo.value.code == ErrorCode.ENGINE_NOT_FOUND


def test_resolve_engine_for_json_auto_prefers_apple(monkeypatch, tmp_path):
    fake = tmp_path / "whisper-py-convert-apple"
    monkeypatch.setattr(engine, "find_apple_stt_binary", lambda: fake)
    monkeypatch.setattr(engine, "find_windows_stt_binary", lambda: None)
    assert engine._resolve_engine_for_json("auto") == "apple"


def test_resolve_engine_for_json_auto_falls_back_to_faster_whisper(monkeypatch):
    monkeypatch.setattr(engine, "find_apple_stt_binary", lambda: None)
    monkeypatch.setattr(engine, "find_windows_stt_binary", lambda: None)
    assert engine._resolve_engine_for_json("auto") == "faster-whisper"


def test_run_apple_json_parses_segments_and_words(monkeypatch, tmp_path):
    fake_binary = tmp_path / "whisper-py-convert-apple"
    fake_binary.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_apple_stt_binary", lambda: fake_binary)

    payload = (
        '{"segments": [{"text": "Hello world.", "start": 0.0, "end": 1.0, '
        '"words": [{"text": "Hello", "start": 0.0, "end": 0.5}, {"text": "world.", "start": 0.5, "end": 1.0}]}]}'
    )
    result = _fake_result(stdout=payload, stderr="")
    with patch.object(subprocess, "run", return_value=result):
        transcript = engine._run_apple_json("r.mp3", language=None, timeout=30)

    assert transcript.engine == "apple"
    assert len(transcript.segments) == 1
    assert transcript.segments[0].text == "Hello world."
    assert len(transcript.segments[0].words) == 2
    assert transcript.text == "Hello world.\n"


def test_run_apple_json_invalid_json_raises(monkeypatch, tmp_path):
    fake_binary = tmp_path / "whisper-py-convert-apple"
    fake_binary.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_apple_stt_binary", lambda: fake_binary)
    result = _fake_result(stdout="not json", stderr="")
    with patch.object(subprocess, "run", return_value=result):
        with pytest.raises(MacSpeechError) as excinfo:
            engine._run_apple_json("r.mp3", language=None, timeout=30)
    assert excinfo.value.code == ErrorCode.NATIVE_PROCESS_ERROR


def test_run_windows_text_only_wraps_as_single_segment(monkeypatch, tmp_path):
    fake_binary = tmp_path / "whisper-py-convert-windows.exe"
    fake_binary.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_windows_stt_binary", lambda: fake_binary)
    result = _fake_result(stdout="Hello from Windows.\n", stderr="")
    with patch.object(subprocess, "run", return_value=result):
        transcript = engine._run_windows_text_only("r.wav", timeout=30)

    assert transcript.engine == "windows"
    assert len(transcript.segments) == 1
    assert transcript.segments[0].text == "Hello from Windows."
    assert transcript.segments[0].words == []
    assert transcript.segments[0].start == 0.0 and transcript.segments[0].end == 0.0


def test_run_windows_text_only_empty_text_has_no_segments(monkeypatch, tmp_path):
    fake_binary = tmp_path / "whisper-py-convert-windows.exe"
    fake_binary.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_windows_stt_binary", lambda: fake_binary)
    result = _fake_result(stdout="   \n", stderr="")
    with patch.object(subprocess, "run", return_value=result):
        transcript = engine._run_windows_text_only("r.wav", timeout=30)
    assert transcript.segments == []


def test_run_faster_whisper_json_builds_one_segment_from_words(monkeypatch):
    srt_content = (
        "1\n00:00:00,000 --> 00:00:00,300\nThis\n"
        "\n"
        "2\n00:00:00,300 --> 00:00:00,540\nis\n"
    )
    from mac_speech.stt.models import TranscribeResult

    monkeypatch.setattr(
        engine, "run_text_or_srt",
        lambda *a, **k: TranscribeResult(engine="faster-whisper", format="srt", content=srt_content),
    )
    transcript = engine._run_faster_whisper_json("r.mp3", model=None, language=None, timeout=30)
    assert transcript.engine == "faster-whisper"
    assert len(transcript.segments) == 1
    assert len(transcript.segments[0].words) == 2
    assert transcript.segments[0].start == 0.0
    assert transcript.segments[0].end == 0.54


def test_run_faster_whisper_json_no_words_returns_empty_transcript(monkeypatch):
    from mac_speech.stt.models import TranscribeResult

    monkeypatch.setattr(
        engine, "run_text_or_srt",
        lambda *a, **k: TranscribeResult(engine="faster-whisper", format="srt", content=""),
    )
    transcript = engine._run_faster_whisper_json("r.mp3", model=None, language=None, timeout=30)
    assert transcript.segments == []


def test_run_json_dispatches_by_resolved_engine(monkeypatch):
    monkeypatch.setattr(engine, "_resolve_engine_for_json", lambda requested: "windows")
    monkeypatch.setattr(engine, "_run_windows_text_only", lambda path, timeout: "windows-result")
    assert engine.run_json("r.mp3") == "windows-result"
