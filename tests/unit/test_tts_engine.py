"""Unit tests for mac_speech.tts.engine.

Subprocess calls are mocked throughout — these tests never spawn the real
native binary or produce audio, per PLAN.md section 8.1 ("Mock
subprocesses ... for failure and timeout paths.").
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.native_protocol import PROTOCOL_VERSION
from mac_speech.tts import engine


def _fake_process(stdout: str, stderr: str = "", returncode: int = 0) -> MagicMock:
    process = MagicMock()
    process.communicate.return_value = (stdout, stderr)
    process.returncode = returncode
    process.pid = 12345
    return process


def test_resolve_binary_raises_engine_not_found(monkeypatch):
    monkeypatch.setattr(engine, "find_tts_binary", lambda: None)
    with pytest.raises(MacSpeechError) as excinfo:
        engine.resolve_binary()
    assert excinfo.value.code == ErrorCode.ENGINE_NOT_FOUND
    assert excinfo.value.remedy is not None


def test_resolve_binary_returns_path(monkeypatch, tmp_path):
    fake = tmp_path / "mac-speech-tts"
    fake.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_tts_binary", lambda: fake)
    assert engine.resolve_binary() == fake


def test_run_operation_success(monkeypatch, tmp_path):
    fake_binary = tmp_path / "mac-speech-tts"
    fake_binary.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_tts_binary", lambda: fake_binary)

    response = {
        "status": "ok",
        "protocol_version": 1,
        "result": {"voices": [], "count": 0},
        "error": None,
    }
    with patch.object(
        subprocess, "Popen", return_value=_fake_process(json.dumps(response))
    ):
        result = engine.run_operation("voices")
    assert result == {"voices": [], "count": 0}


def test_run_operation_builds_expected_command(monkeypatch, tmp_path):
    fake_binary = tmp_path / "mac-speech-tts"
    fake_binary.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_tts_binary", lambda: fake_binary)

    response = {"status": "ok", "protocol_version": 1, "result": {}, "error": None}
    captured = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        return _fake_process(json.dumps(response))

    with patch.object(subprocess, "Popen", side_effect=fake_popen):
        engine.run_operation(
            "save",
            text="hello",
            voice="v1",
            language="en-US",
            rate=0.5,
            output_path="/tmp/out.wav",
            format="wav",
            force=True,
            timeout=30,
        )
    command = captured["command"]
    assert command[0] == str(fake_binary)
    assert command[1] == "save"
    assert "--voice" in command and "v1" in command
    assert "--language" in command and "en-US" in command
    assert "--rate" in command and "0.5" in command
    assert "--output" in command and "/tmp/out.wav" in command
    assert "--format" in command and "wav" in command
    assert "--force" in command
    assert "--timeout" in command and "30" in command
    assert command[-1] == "hello"


def test_run_operation_native_error_maps_to_mac_speech_error(monkeypatch, tmp_path):
    fake_binary = tmp_path / "mac-speech-tts"
    fake_binary.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_tts_binary", lambda: fake_binary)

    response = {
        "status": "error",
        "protocol_version": 1,
        "result": None,
        "error": {
            "code": "output_exists",
            "message": "already there",
            "remedy": "use --force",
        },
    }
    with patch.object(
        subprocess, "Popen", return_value=_fake_process(json.dumps(response))
    ):
        with pytest.raises(MacSpeechError) as excinfo:
            engine.run_operation("save", text="hi", output_path="/tmp/out.wav")
    assert excinfo.value.code == ErrorCode.OUTPUT_EXISTS
    assert excinfo.value.remedy == "use --force"


def test_run_operation_unknown_native_error_code_maps_to_internal_error(
    monkeypatch, tmp_path
):
    fake_binary = tmp_path / "mac-speech-tts"
    fake_binary.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_tts_binary", lambda: fake_binary)

    response = {
        "status": "error",
        "protocol_version": 1,
        "result": None,
        "error": {"code": "something_new_and_unmapped", "message": "???"},
    }
    with patch.object(
        subprocess, "Popen", return_value=_fake_process(json.dumps(response))
    ):
        with pytest.raises(MacSpeechError) as excinfo:
            engine.run_operation("voices")
    assert excinfo.value.code == ErrorCode.INTERNAL_ERROR


def test_run_operation_invalid_json_raises_native_process_error(monkeypatch, tmp_path):
    fake_binary = tmp_path / "mac-speech-tts"
    fake_binary.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_tts_binary", lambda: fake_binary)

    with patch.object(
        subprocess, "Popen", return_value=_fake_process("not json at all")
    ):
        with pytest.raises(MacSpeechError) as excinfo:
            engine.run_operation("voices")
    assert excinfo.value.code == ErrorCode.NATIVE_PROCESS_ERROR


def test_run_operation_empty_output_raises_native_process_error(monkeypatch, tmp_path):
    fake_binary = tmp_path / "mac-speech-tts"
    fake_binary.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_tts_binary", lambda: fake_binary)

    with patch.object(
        subprocess, "Popen", return_value=_fake_process("", returncode=1)
    ):
        with pytest.raises(MacSpeechError) as excinfo:
            engine.run_operation("voices")
    assert excinfo.value.code == ErrorCode.NATIVE_PROCESS_ERROR


@pytest.mark.parametrize("status,returncode", [("ok", 0), ("error", 3)])
@pytest.mark.parametrize("version", [-1, 0, PROTOCOL_VERSION + 1, 999])
def test_run_operation_protocol_version_mismatch(
    monkeypatch, tmp_path, status, returncode, version
):
    fake_binary = tmp_path / "mac-speech-tts"
    fake_binary.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_tts_binary", lambda: fake_binary)

    response = {
        "status": status,
        "protocol_version": version,
        "result": {"voices": []},
        "error": {"code": "output_exists", "message": "already there"},
    }
    process = _fake_process(json.dumps(response), returncode=returncode)
    with patch.object(subprocess, "Popen", return_value=process):
        with pytest.raises(MacSpeechError) as excinfo:
            engine.run_operation("voices")
    assert excinfo.value.code == ErrorCode.PROTOCOL_VERSION_MISMATCH
    assert excinfo.value.exit_code == 5
    assert f"version {version}" in excinfo.value.message
    assert f"wrapper protocol version {PROTOCOL_VERSION}" in excinfo.value.message
    assert "same source checkout or release" in excinfo.value.remedy
    assert "./install.sh tts" in excinfo.value.remedy


@pytest.mark.parametrize("status,returncode", [("ok", 0), ("error", 3)])
@pytest.mark.parametrize(
    "version", [None, "1", "invalid", "", 1.0, 1.9, True, False, [], {}]
)
def test_run_operation_rejects_malformed_version(
    monkeypatch, status, returncode, version
):
    monkeypatch.setattr(engine, "find_tts_binary", lambda: Path("/mock/mac-speech-tts"))
    response = {
        "status": status,
        "protocol_version": version,
        "result": {"voices": []},
        "error": {"code": "output_exists", "message": "already there"},
    }
    process = _fake_process(json.dumps(response), returncode=returncode)
    with patch.object(subprocess, "Popen", return_value=process):
        with pytest.raises(MacSpeechError) as excinfo:
            engine.run_operation("voices")
    assert excinfo.value.code == ErrorCode.PROTOCOL_VERSION_MISMATCH
    assert excinfo.value.exit_code == 5
    assert "must be an integer" in excinfo.value.message
    assert "same source checkout or release" in excinfo.value.remedy


@pytest.mark.parametrize("status,returncode", [("ok", 0), ("error", 3)])
def test_run_operation_rejects_missing_version(monkeypatch, status, returncode):
    monkeypatch.setattr(engine, "find_tts_binary", lambda: Path("/mock/mac-speech-tts"))
    response = {
        "status": status,
        "result": {"voices": []},
        "error": {"code": "output_exists", "message": "already there"},
    }
    process = _fake_process(json.dumps(response), returncode=returncode)
    with patch.object(subprocess, "Popen", return_value=process):
        with pytest.raises(MacSpeechError) as excinfo:
            engine.run_operation("voices")
    assert excinfo.value.code == ErrorCode.PROTOCOL_VERSION_MISMATCH
    assert "missing required protocol_version" in excinfo.value.message
    assert "same source checkout or release" in excinfo.value.remedy


@pytest.mark.parametrize("payload", [None, [], "response", 1, True])
def test_run_operation_rejects_non_object_response(monkeypatch, payload):
    monkeypatch.setattr(engine, "find_tts_binary", lambda: Path("/mock/mac-speech-tts"))
    with patch.object(
        subprocess, "Popen", return_value=_fake_process(json.dumps(payload))
    ):
        with pytest.raises(MacSpeechError) as excinfo:
            engine.run_operation("voices")
    assert excinfo.value.code == ErrorCode.NATIVE_PROCESS_ERROR
    assert "expected an object" in excinfo.value.message


@pytest.mark.parametrize(
    "remedy", [None, "Use the native engine's migration instructions."]
)
def test_run_operation_native_version_error_has_remedy(monkeypatch, remedy):
    monkeypatch.setattr(engine, "find_tts_binary", lambda: Path("/mock/mac-speech-tts"))
    response = {
        "status": "error",
        "protocol_version": PROTOCOL_VERSION,
        "result": None,
        "error": {
            "code": "protocol_version_mismatch",
            "message": "incompatible",
            "remedy": remedy,
        },
    }
    process = _fake_process(json.dumps(response), returncode=5)
    with patch.object(subprocess, "Popen", return_value=process):
        with pytest.raises(MacSpeechError) as excinfo:
            engine.run_operation("voices")
    assert excinfo.value.code == ErrorCode.PROTOCOL_VERSION_MISMATCH
    assert excinfo.value.message == "incompatible"
    if remedy:
        assert excinfo.value.remedy == remedy
    else:
        assert "same source checkout or release" in excinfo.value.remedy


def test_run_operation_timeout_kills_process(monkeypatch, tmp_path):
    fake_binary = tmp_path / "mac-speech-tts"
    fake_binary.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_tts_binary", lambda: fake_binary)

    process = MagicMock()
    process.pid = 1
    process.communicate.side_effect = subprocess.TimeoutExpired(
        cmd="mac-speech-tts", timeout=5
    )

    with patch.object(subprocess, "Popen", return_value=process):
        with pytest.raises(MacSpeechError) as excinfo:
            engine.run_operation("speak", text="hi", timeout=5)
    assert excinfo.value.code == ErrorCode.TIMEOUT
    process.kill.assert_called_once()


def test_run_operation_uses_stdin_for_long_text(monkeypatch, tmp_path):
    fake_binary = tmp_path / "mac-speech-tts"
    fake_binary.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_tts_binary", lambda: fake_binary)

    long_text = "word " * (engine.STDIN_TRANSPORT_THRESHOLD_CHARS // 4)
    response = {"status": "ok", "protocol_version": 1, "result": {}, "error": None}
    captured = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["stdin"] = kwargs.get("stdin")
        return _fake_process(json.dumps(response))

    with patch.object(subprocess, "Popen", side_effect=fake_popen):
        engine.run_operation("speak", text=long_text)

    assert "--stdin" in captured["command"]
    assert long_text not in captured["command"]
    assert captured["stdin"] == subprocess.PIPE


# --- PID-file-based process control ----------------------------------------


def test_pid_file_path_respects_env_override(monkeypatch, tmp_path):
    override = tmp_path / "custom.pid"
    monkeypatch.setenv(engine.PID_FILE_ENV_VAR, str(override))
    assert engine._pid_file_path() == override


def test_read_tracked_pid_returns_none_when_no_file(monkeypatch, tmp_path):
    monkeypatch.setenv(engine.PID_FILE_ENV_VAR, str(tmp_path / "missing.pid"))
    assert engine.read_tracked_pid() is None


def test_read_tracked_pid_cleans_up_stale_file(monkeypatch, tmp_path):
    pid_file = tmp_path / "tts.pid"
    pid_file.write_text("999999")
    monkeypatch.setenv(engine.PID_FILE_ENV_VAR, str(pid_file))
    monkeypatch.setattr(engine, "_process_is_alive", lambda pid: False)

    assert engine.read_tracked_pid() is None
    assert not pid_file.exists()


def test_read_tracked_pid_returns_pid_when_alive(monkeypatch, tmp_path):
    pid_file = tmp_path / "tts.pid"
    pid_file.write_text("4242")
    monkeypatch.setenv(engine.PID_FILE_ENV_VAR, str(pid_file))
    monkeypatch.setattr(engine, "_process_is_alive", lambda pid: True)

    assert engine.read_tracked_pid() == 4242


def test_send_control_signal_raises_when_nothing_tracked(monkeypatch, tmp_path):
    monkeypatch.setenv(engine.PID_FILE_ENV_VAR, str(tmp_path / "missing.pid"))
    with pytest.raises(MacSpeechError) as excinfo:
        engine.send_control_signal(15)
    assert excinfo.value.code == ErrorCode.ENGINE_NOT_FOUND


def test_send_control_signal_sends_signal_to_tracked_pid(monkeypatch, tmp_path):
    pid_file = tmp_path / "tts.pid"
    pid_file.write_text("4242")
    monkeypatch.setenv(engine.PID_FILE_ENV_VAR, str(pid_file))
    monkeypatch.setattr(engine, "_process_is_alive", lambda pid: True)

    sent = {}
    monkeypatch.setattr(
        engine.os, "kill", lambda pid, sig: sent.update(pid=pid, sig=sig)
    )
    engine.send_control_signal(15)
    assert sent == {"pid": 4242, "sig": 15}


def test_run_operation_writes_and_removes_pid_file_when_tracking(monkeypatch, tmp_path):
    fake_binary = tmp_path / "mac-speech-tts"
    fake_binary.write_text("#!/bin/sh\n")
    monkeypatch.setattr(engine, "find_tts_binary", lambda: fake_binary)
    pid_file = tmp_path / "tts.pid"
    monkeypatch.setenv(engine.PID_FILE_ENV_VAR, str(pid_file))

    response = {"status": "ok", "protocol_version": 1, "result": {}, "error": None}
    seen_during_call = {}

    def fake_popen(command, **kwargs):
        process = _fake_process(json.dumps(response))

        def communicate(*a, **k):
            seen_during_call["pid_file_existed"] = pid_file.is_file()
            seen_during_call["pid_file_contents"] = (
                pid_file.read_text() if pid_file.is_file() else None
            )
            return process.communicate.return_value

        process.communicate.side_effect = communicate
        return process

    with patch.object(subprocess, "Popen", side_effect=fake_popen):
        engine.run_operation("speak", text="hi", track_pid=True)

    assert seen_during_call["pid_file_existed"] is True
    assert seen_during_call["pid_file_contents"] == "12345"
    assert not pid_file.exists()  # removed after the process finished


def test_pid_cleanup_does_not_mask_cancellation(monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "resolve_binary", lambda: tmp_path / "mock-engine")
    monkeypatch.setenv(engine.PID_FILE_ENV_VAR, str(tmp_path / "tracked.pid"))
    failure = KeyboardInterrupt()
    process = _fake_process("")
    process.communicate.side_effect = failure
    monkeypatch.setattr(engine.subprocess, "Popen", lambda *args, **kwargs: process)

    def denied(path):
        raise PermissionError("synthetic PID cleanup failure")

    monkeypatch.setattr(engine, "_remove_pid_file", denied)
    with pytest.raises(KeyboardInterrupt) as error:
        engine.run_operation("speak", text="Public sample.", track_pid=True)
    assert error.value is failure
    process.kill.assert_called_once()
    process.wait.assert_called_once_with(timeout=10)


def test_pid_cleanup_after_success_is_structured(monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "resolve_binary", lambda: tmp_path / "mock-engine")
    monkeypatch.setenv(engine.PID_FILE_ENV_VAR, str(tmp_path / "tracked.pid"))
    process = _fake_process(json.dumps({"status": "ok", "protocol_version": 1, "result": {}}))
    monkeypatch.setattr(engine.subprocess, "Popen", lambda *args, **kwargs: process)

    def denied(path):
        raise PermissionError("synthetic PID cleanup failure")

    monkeypatch.setattr(engine, "_remove_pid_file", denied)
    with pytest.raises(MacSpeechError) as error:
        engine.run_operation("speak", text="Public sample.", track_pid=True)
    assert error.value.code == ErrorCode.INTERNAL_ERROR


def test_failed_pid_warning_does_not_mask_cancellation(monkeypatch, tmp_path):
    from mac_speech import logging_utils

    monkeypatch.setattr(engine, "resolve_binary", lambda: tmp_path / "mock-engine")
    monkeypatch.setenv(engine.PID_FILE_ENV_VAR, str(tmp_path / "tracked.pid"))
    failure = KeyboardInterrupt()
    process = _fake_process("")
    process.communicate.side_effect = failure
    monkeypatch.setattr(engine.subprocess, "Popen", lambda *args, **kwargs: process)

    def denied(path):
        raise PermissionError("synthetic PID cleanup failure")

    def unavailable(message):
        raise BrokenPipeError("synthetic disconnected stderr")

    monkeypatch.setattr(engine, "_remove_pid_file", denied)
    monkeypatch.setattr(logging_utils, "diagnostic", unavailable)
    with pytest.raises(KeyboardInterrupt) as error:
        engine.run_operation("speak", text="Public sample.", track_pid=True)
    assert error.value is failure
