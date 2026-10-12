"""Platform-independent mocked checks for the opt-in native STT fixtures."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from mac_speech.errors import ErrorCode, MacSpeechError


_SPEC = importlib.util.spec_from_file_location(
    "stt_regression_fixtures", Path(__file__).with_name("test_stt_regression_fixtures.py"),
)
assert _SPEC is not None and _SPEC.loader is not None
fixtures = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fixtures)


@pytest.fixture
def native(monkeypatch):
    monkeypatch.setenv("MAC_SPEECH_TEST_APPLE_STT", "1")
    monkeypatch.delenv("MAC_SPEECH_TEST_APPLE_LOCALE", raising=False)
    monkeypatch.delenv("MAC_SPEECH_TEST_APPLE_BINARY", raising=False)
    monkeypatch.setattr(fixtures.sys, "platform", "darwin")
    monkeypatch.setattr(fixtures.shutil, "which", Mock(return_value="/usr/bin/say"))
    discovery = Mock(return_value=Path("/mock/whisper-py-convert-apple"))
    monkeypatch.setattr(fixtures.capabilities, "find_apple_stt_binary", discovery)
    status = {
        "available": True, "supported_locale": "en-US", "installed": True,
        "reserved_locales": ["fr-FR"], "maximum_reserved_locales": 1,
    }
    run = Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps(status), ""))
    monkeypatch.setattr(fixtures.subprocess, "run", run)
    return status, run, discovery


@pytest.mark.parametrize("opt_in", [None, "0", "true", "yes"])
def test_native_requires_exact_opt_in(monkeypatch, native, opt_in):
    if opt_in is None:
        monkeypatch.delenv("MAC_SPEECH_TEST_APPLE_STT")
    else:
        monkeypatch.setenv("MAC_SPEECH_TEST_APPLE_STT", opt_in)
    with pytest.raises(pytest.skip.Exception, match="MAC_SPEECH_TEST_APPLE_STT=1"):
        fixtures._require_apple_stt()
    native[1].assert_not_called()
    native[2].assert_not_called()


@pytest.mark.parametrize("missing", ["platform", "say", "binary"])
def test_missing_environment_prerequisite_skips(monkeypatch, native, missing):
    if missing == "platform":
        monkeypatch.setattr(fixtures.sys, "platform", "linux")
    elif missing == "say":
        fixtures.shutil.which.return_value = None
    else:
        native[2].return_value = None
    with pytest.raises(pytest.skip.Exception):
        fixtures._require_apple_stt()
    native[1].assert_not_called()


@pytest.mark.parametrize("language", [None, "en-GB"])
def test_inventory_is_read_only_and_uses_selected_locale(monkeypatch, native, language):
    if language is not None:
        monkeypatch.setenv("MAC_SPEECH_TEST_APPLE_LOCALE", language)
    selected = language or "en-US"
    assert fixtures._require_apple_stt() == selected
    native[1].assert_called_once_with(
        ["/mock/whisper-py-convert-apple", "--inventory-status", "--language", selected],
        capture_output=True, text=True, check=True, timeout=30,
    )


@pytest.mark.parametrize("field,value,reason", [
    ("available", False, "API is unavailable"),
    ("supported_locale", None, "is unsupported"),
    ("installed", False, "are not installed"),
])
def test_inventory_prerequisite_skips(native, field, value, reason):
    status, run, _ = native
    status[field] = value
    run.return_value.stdout = json.dumps(status)
    with pytest.raises(pytest.skip.Exception, match=reason):
        fixtures._require_apple_stt()


@pytest.mark.parametrize("stdout", ["not JSON", "[]", "null", "{}"])
def test_bad_inventory_json_fails(native, stdout):
    native[1].return_value.stdout = stdout
    with pytest.raises(pytest.fail.Exception, match="inventory-status"):
        fixtures._require_apple_stt()


@pytest.mark.parametrize("field,value", [
    ("available", 1), ("installed", "false"), ("supported_locale", 123),
    ("reserved_locales", "en-US"), ("reserved_locales", [None]),
    ("maximum_reserved_locales", True), ("maximum_reserved_locales", "1"),
])
def test_malformed_inventory_fields_fail(native, field, value):
    status, run, _ = native
    status[field] = value
    run.return_value.stdout = json.dumps(status)
    with pytest.raises(pytest.fail.Exception, match="malformed inventory fields"):
        fixtures._require_apple_stt()


@pytest.mark.parametrize("error", [
    subprocess.CalledProcessError(1, ["--inventory-status"], stderr="diagnostic failed"),
    subprocess.TimeoutExpired(["--inventory-status"], 30),
    OSError("binary could not execute"),
])
def test_inventory_execution_errors_are_not_skips(native, error):
    native[1].side_effect = error
    with pytest.raises(type(error)):
        fixtures._require_apple_stt()


@pytest.mark.parametrize("test_name,method,options", [
    ("test_transcribe_text_contains_expected_words", "transcribe_text", {}),
    ("test_transcribe_srt_segment_timestamps_are_monotonic", "transcribe_srt", {"word_timestamps": False}),
    ("test_transcribe_srt_word_timestamps_are_ordered_and_non_overlapping", "transcribe_srt", {"word_timestamps": True}),
    ("test_transcribe_json_segments_and_words_are_consistent", "transcribe_json", {}),
])
def test_transcription_errors_propagate_with_explicit_apple_and_locale(monkeypatch, test_name, method, options):
    error = MacSpeechError(code=ErrorCode.NATIVE_PROCESS_ERROR, message="does not support locale en-GB")
    transcribe = Mock(side_effect=error)
    monkeypatch.setattr(fixtures.stt, method, transcribe)
    with pytest.raises(MacSpeechError) as caught:
        getattr(fixtures, test_name)("/mock/fixture.aiff", "en-GB")
    assert caught.value is error
    transcribe.assert_called_once_with(
        "/mock/fixture.aiff", engine_name="apple", language="en-GB", **options,
    )
