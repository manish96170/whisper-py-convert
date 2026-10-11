"""Offline smoke harness helpers; real clean-wheel/native checks run separately."""

from __future__ import annotations

import importlib.util
import wave
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "smoke_core", Path(__file__).resolve().parents[2] / "scripts" / "smoke_core.py"
)
assert SPEC is not None and SPEC.loader is not None
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


@pytest.mark.parametrize("event", ["socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"])
def test_network_audit_rejects_network_operations(event):
    with pytest.raises(PermissionError):
        smoke.deny_python_network(event, ())


def test_network_audit_permits_non_network_operations():
    smoke.deny_python_network("open", ())


def test_cli_smoke_captures_machine_output():
    code, payload = smoke.invoke_cli(["version", "--json"])
    assert code == 0 and payload["protocol_version"] == 1


def test_verify_wav_rejects_empty_audio(tmp_path):
    path = tmp_path / "empty.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(22050)
    with pytest.raises(AssertionError, match="no audio frames"):
        smoke.verify_wav(path)


def test_engine_free_smoke_accepts_actionable_missing_stt(monkeypatch):
    from mac_speech.stt import engine

    monkeypatch.setattr(engine, "find_apple_stt_binary", lambda: None)
    report = smoke.run_checks(native_tts=False, require_noneditable=False)
    assert report["ok"] is True
    assert "no transcription/model download" in report["stt"]
