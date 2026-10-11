"""Unit tests for mac_speech.capabilities.

These tests monkeypatch the module's internal probe functions so results
are deterministic across machines, except for the explicit end-to-end shape
test, which only asserts structure (not availability) so it stays valid
regardless of what is actually built on the host running the tests.
"""

from __future__ import annotations

import mac_speech.capabilities as capabilities


def test_detect_platform_reports_apple_silicon_macos(monkeypatch):
    monkeypatch.setattr(capabilities.sys, "platform", "darwin")
    monkeypatch.setattr(capabilities.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(capabilities.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(capabilities.platform, "mac_ver", lambda: ("27.0.1", ("", "", ""), ""))
    monkeypatch.setattr(capabilities.platform, "python_version", lambda: "3.11.3")

    info = capabilities.detect_platform()
    assert info.os_name == "Darwin"
    assert info.machine == "arm64"
    assert info.is_apple_silicon is True
    assert info.os_version == "27.0.1"


def test_detect_platform_reports_non_apple_silicon(monkeypatch):
    monkeypatch.setattr(capabilities.sys, "platform", "linux")
    monkeypatch.setattr(capabilities.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(capabilities.platform, "system", lambda: "Linux")
    monkeypatch.setattr(capabilities.platform, "release", lambda: "6.1.0")
    monkeypatch.setattr(capabilities.platform, "python_version", lambda: "3.11.3")

    info = capabilities.detect_platform()
    assert info.is_apple_silicon is False
    assert info.os_version == "6.1.0"


def test_stt_capability_available_when_apple_binary_found(monkeypatch, tmp_path):
    fake_binary = tmp_path / "whisper-py-convert-apple"
    fake_binary.write_text("#!/bin/sh\n")
    fake_binary.chmod(0o755)
    monkeypatch.setattr(capabilities, "find_apple_stt_binary", lambda: fake_binary)
    monkeypatch.setattr(capabilities, "find_windows_stt_binary", lambda: None)
    monkeypatch.setattr(capabilities, "_faster_whisper_version", lambda: None)

    status = capabilities.detect_stt_capability()
    assert status.available is True
    assert status.details["apple_binary"] == str(fake_binary)
    assert status.details["supported_output_formats"] == ["text", "srt", "json"]


def test_stt_capability_unavailable_when_nothing_found(monkeypatch):
    monkeypatch.setattr(capabilities, "find_apple_stt_binary", lambda: None)
    monkeypatch.setattr(capabilities, "find_windows_stt_binary", lambda: None)
    monkeypatch.setattr(capabilities, "_faster_whisper_version", lambda: None)

    status = capabilities.detect_stt_capability()
    assert status.available is False
    assert status.reason is not None
    assert status.install_hint is not None


def test_tts_capability_unavailable_when_binary_missing(monkeypatch):
    monkeypatch.setattr(capabilities, "find_tts_binary", lambda: None)

    status = capabilities.detect_tts_capability()
    assert status.available is False
    assert status.reason is not None
    assert status.install_hint is not None


def test_tts_capability_available_when_binary_present(monkeypatch, tmp_path):
    fake_binary = tmp_path / "mac-speech-tts"
    fake_binary.write_text("#!/bin/sh\n")
    fake_binary.chmod(0o755)
    monkeypatch.setattr(capabilities, "find_tts_binary", lambda: fake_binary)

    status = capabilities.detect_tts_capability()
    assert status.available is True
    assert status.details["binary"] == str(fake_binary)


def test_tts_binary_override_via_env_var(monkeypatch, tmp_path):
    fake_binary = tmp_path / "custom-tts"
    fake_binary.write_text("#!/bin/sh\n")
    fake_binary.chmod(0o755)
    monkeypatch.setenv("MAC_SPEECH_TTS_BINARY", str(fake_binary))

    found = capabilities.find_tts_binary()
    assert found == fake_binary


def test_tts_binary_override_ignored_when_not_executable(monkeypatch, tmp_path):
    fake_binary = tmp_path / "custom-tts-not-executable"
    fake_binary.write_text("#!/bin/sh\n")
    # Deliberately not chmod +x.
    monkeypatch.setenv("MAC_SPEECH_TTS_BINARY", str(fake_binary))

    found = capabilities.find_tts_binary()
    assert found is None


def test_detect_capabilities_end_to_end_shape():
    report = capabilities.detect_capabilities()
    names = {c.name for c in report.capabilities}
    assert names == {"stt", "tts"}
    as_dict = report.to_dict()
    assert as_dict["schema_version"] == 1
    assert "platform" in as_dict
    assert isinstance(as_dict["capabilities"], list)
