"""Unit tests for mac_speech.config."""

from __future__ import annotations

from mac_speech.config import TTS_BINARY_ENV_VAR, WHISPER_PY_CONVERT_BIN_ENV_VAR, load_config


def test_tts_binary_override_defaults_to_none(monkeypatch):
    monkeypatch.delenv(TTS_BINARY_ENV_VAR, raising=False)
    assert load_config().tts_binary_override is None


def test_tts_binary_override_reads_env_var(monkeypatch):
    monkeypatch.setenv(TTS_BINARY_ENV_VAR, "/tmp/fake-tts-binary")
    assert load_config().tts_binary_override == "/tmp/fake-tts-binary"


def test_tts_binary_override_strips_whitespace_and_treats_blank_as_unset(monkeypatch):
    monkeypatch.setenv(TTS_BINARY_ENV_VAR, "   ")
    assert load_config().tts_binary_override is None


def test_whisper_py_convert_bin_override_defaults_to_none(monkeypatch):
    monkeypatch.delenv(WHISPER_PY_CONVERT_BIN_ENV_VAR, raising=False)
    assert load_config().whisper_py_convert_bin_override is None


def test_whisper_py_convert_bin_override_reads_env_var(monkeypatch):
    monkeypatch.setenv(WHISPER_PY_CONVERT_BIN_ENV_VAR, "/tmp/fake-whisper-py-convert")
    assert load_config().whisper_py_convert_bin_override == "/tmp/fake-whisper-py-convert"
