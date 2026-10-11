"""Cooperative native cancellation without real voice/model/network access."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from unittest.mock import Mock

import pytest

from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.tts import engine


def test_pre_cancelled_operation_does_not_resolve_or_spawn(monkeypatch):
    stop = threading.Event()
    stop.set()
    resolve = Mock(side_effect=AssertionError("engine lookup must not happen"))
    monkeypatch.setattr(engine, "resolve_binary", resolve)
    with pytest.raises(MacSpeechError) as error:
        engine.run_operation("save", text="public", cancel_event=stop)
    assert error.value.code == ErrorCode.CANCELLED
    resolve.assert_not_called()


def test_cancellable_communication_uses_one_full_exchange():
    process = Mock()
    process.communicate.return_value = ("result", "")
    result = engine._communicate_cancellable(process, "long private input", 10, threading.Event())
    assert result == ("result", "")
    process.communicate.assert_called_once_with(input="long private input", timeout=10)


def test_real_delayed_reader_receives_all_long_stdin_and_eof():
    process = subprocess.Popen(
        [sys.executable, "-c", "import sys,time; time.sleep(0.35); text=sys.stdin.read(); print(len(text))"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        stdout, stderr = engine._communicate_cancellable(process, "x" * 200_000, 5, threading.Event())
        assert stdout.strip() == "200000" and not stderr
        assert process.poll() == 0
    finally:
        if process.poll() is None:
            engine._kill_and_reap(process)
        else:
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe is not None:
                    pipe.close()


def test_cooperative_event_kills_and_reaps_real_synthetic_child(tmp_path, monkeypatch):
    binary = tmp_path / "synthetic-engine"
    ready = tmp_path / "child.pid"
    binary.write_text(
        f"#!{sys.executable}\nimport os,pathlib,time\n"
        f"pathlib.Path({str(ready)!r}).write_text(str(os.getpid()))\n"
        "time.sleep(60)\n"
    )
    binary.chmod(0o700)
    monkeypatch.setattr(engine, "resolve_binary", lambda: binary)
    stop = threading.Event()
    original = subprocess.Popen
    children = []

    def spawn(*args, **kwargs):
        process = original(*args, **kwargs)
        children.append(process)
        stop.set()
        return process

    monkeypatch.setattr(engine.subprocess, "Popen", spawn)
    try:
        with pytest.raises(MacSpeechError) as error:
            engine.run_operation("save", text="public", cancel_event=stop)
        assert error.value.code == ErrorCode.CANCELLED
        assert children[0].poll() is not None
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)


def test_completed_scene_is_not_reclassified_when_event_arrives_after_completion():
    stop = threading.Event()
    process = Mock()

    def completed(**kwargs):
        stop.set()
        return json.dumps({"status": "ok"}), ""

    process.communicate.side_effect = completed
    stdout, stderr = engine._communicate_cancellable(process, None, 10, stop)
    assert json.loads(stdout)["status"] == "ok"
