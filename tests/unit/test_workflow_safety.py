"""Managed workspace safety with mocked engines and real local filesystem I/O."""

from __future__ import annotations

import json
import inspect
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from mac_speech import artifacts, logging_utils, workflow
from mac_speech.cli import main
from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.stt.models import Segment, Transcript
from mac_speech.tts.models import SynthesizeResult
from mac_speech.tts import engine as tts_engine


def transcript():
    return Transcript(engine="apple", segments=[Segment(text="Hello.", start=0, end=1)])


def synthesize(text, *, output_path, **kwargs):
    Path(output_path).write_bytes(b"synthetic local audio")
    return SynthesizeResult(
        output_path=output_path, format="wav", sample_rate=22050.0, channels=1,
        bit_depth=16, duration_seconds=1, file_size_bytes=21, sentence_count=1,
        voice_identifier="public-test-voice", language="en-US",
    )


@pytest.fixture
def engine(monkeypatch):
    synth = Mock(side_effect=synthesize)
    monkeypatch.setattr(workflow, "synthesize_to_file", synth)
    monkeypatch.setattr(workflow, "align_via_stt_roundtrip", lambda *args, **kwargs: transcript())
    return synth


@pytest.mark.parametrize("basename", ["../outside", "a/b", "a\\b", "/outside", "", " ", ".", "..", "a\nb", "a\0b"])
def test_bad_basename_is_rejected_before_directory_or_speech(tmp_path, engine, basename):
    directory = tmp_path / "not-created"
    with pytest.raises(MacSpeechError) as error:
        workflow.run_narration_pipeline("Hello.", output_dir=str(directory), basename=basename)
    assert error.value.code == ErrorCode.INVALID_ARGUMENT
    assert not directory.exists()
    engine.assert_not_called()


@pytest.mark.parametrize("basename", ["scene-01", "café scene", ".scene"])
def test_valid_basename_remains_in_canonical_workspace(tmp_path, engine, basename):
    result = workflow.run_narration_pipeline("Hello.", output_dir=str(tmp_path), basename=basename)
    assert result.ok
    assert all(Path(stage.output_path).parent == tmp_path.resolve() for stage in result.stages if stage.output_path)


@pytest.mark.parametrize("suffix", ["wav", "srt", "workflow.json"])
def test_existing_output_is_preserved_before_any_engine_invocation(tmp_path, engine, suffix):
    target = tmp_path / f"narration.{suffix}"
    target.write_bytes(b"keep original")
    with pytest.raises(MacSpeechError) as error:
        workflow.run_narration_pipeline("Hello.", output_dir=str(tmp_path), persist_manifest=True)
    assert error.value.code == ErrorCode.OUTPUT_EXISTS
    assert target.read_bytes() == b"keep original"
    engine.assert_not_called()


@pytest.mark.parametrize("force", [False, True])
@pytest.mark.parametrize("suffix", ["wav", "srt", "workflow.json"])
def test_managed_symlink_is_never_followed(tmp_path, engine, force, suffix):
    outside = tmp_path / "outside.txt"
    outside.write_text("keep")
    target = tmp_path / f"narration.{suffix}"
    target.symlink_to(outside)
    with pytest.raises(MacSpeechError) as error:
        workflow.run_narration_pipeline("Hello.", output_dir=str(tmp_path), force=force)
    assert error.value.code == ErrorCode.INVALID_ARGUMENT
    assert outside.read_text() == "keep" and target.is_symlink()
    engine.assert_not_called()


def test_force_is_propagated_to_audio_subtitles_and_manifest(tmp_path, engine):
    for suffix in ("wav", "srt", "workflow.json"):
        (tmp_path / f"narration.{suffix}").write_bytes(b"old")
    result = workflow.run_narration_pipeline("Hello.", output_dir=str(tmp_path), force=True, persist_manifest=True)
    assert result.ok
    assert engine.call_args.kwargs["force"] is True
    assert "Hello." in (tmp_path / "narration.srt").read_text()
    assert json.loads((tmp_path / "narration.workflow.json").read_text())["ok"]
    assert not (tmp_path / ".narration.workflow.lock").exists()


def test_checkpoint_precedes_speech_and_success_survives_alignment_failure(tmp_path, engine, monkeypatch):
    manifest = tmp_path / "narration.workflow.json"

    def save(text, **kwargs):
        initial = json.loads(manifest.read_text())
        assert initial["ok"] is False and initial["stages"] == []
        assert (tmp_path / ".narration.workflow.lock").exists()
        return synthesize(text, **kwargs)

    def fail(*args, **kwargs):
        saved = json.loads(manifest.read_text())
        assert [stage["name"] for stage in saved["stages"]] == ["synthesize"]
        raise RuntimeError("synthetic alignment failure")

    engine.side_effect = save
    monkeypatch.setattr(workflow, "align_via_stt_roundtrip", fail)
    result = workflow.run_narration_pipeline("Hello.", output_dir=str(tmp_path), persist_manifest=True)
    assert not result.ok
    assert (tmp_path / "narration.wav").read_bytes() == b"synthetic local audio"
    assert json.loads(manifest.read_text())["stages"][-1]["status"] == "failed"
    assert not (tmp_path / ".narration.workflow.lock").exists()
    assert manifest.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("force", [False, True])
def test_existing_claim_is_not_removed_or_bypassed(tmp_path, engine, force):
    marker = tmp_path / ".narration.workflow.lock"
    marker.write_text("unverified marker")
    with pytest.raises(MacSpeechError) as error:
        workflow.run_narration_pipeline("Hello.", output_dir=str(tmp_path), force=force)
    assert error.value.code == ErrorCode.OUTPUT_EXISTS
    assert marker.read_text() == "unverified marker"
    engine.assert_not_called()


def test_another_workflow_cannot_enter_an_active_claim(tmp_path, engine):
    def save(text, **kwargs):
        with pytest.raises(MacSpeechError) as error:
            workflow.run_narration_pipeline("Other.", output_dir=str(tmp_path), force=True)
        assert error.value.code == ErrorCode.OUTPUT_EXISTS
        return synthesize(text, **kwargs)

    engine.side_effect = save
    assert workflow.run_narration_pipeline("Hello.", output_dir=str(tmp_path), align=False).ok
    assert not (tmp_path / ".narration.workflow.lock").exists()


def test_claim_cleanup_on_interrupt_retains_pending_manifest(tmp_path, engine):
    engine.side_effect = KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        workflow.run_narration_pipeline("Hello.", output_dir=str(tmp_path), persist_manifest=True)
    assert not (tmp_path / ".narration.workflow.lock").exists()
    assert json.loads((tmp_path / "narration.workflow.json").read_text())["ok"] is False


def test_manifest_and_subtitle_helpers_require_explicit_replacement(tmp_path):
    path = tmp_path / "checkpoint.json"
    manifest = workflow.new_manifest("Hello.")
    manifest.write(path)
    before = path.read_bytes()
    with pytest.raises(MacSpeechError) as error:
        manifest.write(path)
    assert error.value.code == ErrorCode.OUTPUT_EXISTS and path.read_bytes() == before
    manifest.write(path, force=True)
    srt = tmp_path / "narration.srt"
    srt.write_text("keep")
    assert workflow.stage_render_srt(transcript(), output_path=str(srt)).status == "failed"
    assert srt.read_text() == "keep"
    assert workflow.stage_render_srt(transcript(), output_path=str(srt), force=True).status == "success"


def test_sidecar_helper_does_not_overwrite_or_follow_links(tmp_path):
    audio = tmp_path / "narration.wav"
    audio.write_bytes(b"data")
    manifest = artifacts.build_manifest(audio, operation="tts_save")
    sidecar = artifacts.write_manifest(manifest, audio)
    previous = sidecar.read_bytes()
    with pytest.raises(MacSpeechError):
        artifacts.write_manifest(manifest, audio)
    assert sidecar.read_bytes() == previous
    artifacts.write_manifest(manifest, audio, force=True)


def test_cli_traversal_is_a_structured_error_without_speech(tmp_path, engine, capsys):
    assert main(["workflow", "narrate", "Hello.", "--basename", "../outside", "--output-dir", str(tmp_path), "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_argument"
    engine.assert_not_called()


def test_cli_keeps_existing_manifest_instead_of_recording_new_failure(tmp_path, engine, capsys):
    existing = tmp_path / "narration.workflow.json"
    existing.write_text("keep old checkpoint")
    assert main(["workflow", "narrate", "Hello.", "--output-dir", str(tmp_path), "--no-align", "--json"]) == 3
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "output_exists"
    assert existing.read_text() == "keep old checkpoint"
    engine.assert_not_called()


def test_foreign_checkpoint_replacement_is_not_overwritten(tmp_path, engine):
    checkpoint = tmp_path / "narration.workflow.json"

    def save(text, **kwargs):
        other = tmp_path / "other-checkpoint.json"
        other.write_text("keep foreign checkpoint")
        other.replace(checkpoint)
        return synthesize(text, **kwargs)

    engine.side_effect = save
    with pytest.raises(MacSpeechError) as error:
        workflow.run_narration_pipeline("Hello.", output_dir=str(tmp_path), align=False, persist_manifest=True)
    assert error.value.code == ErrorCode.OUTPUT_EXISTS
    assert checkpoint.read_text() == "keep foreign checkpoint"
    assert (tmp_path / "narration.wav").exists()
    assert not (tmp_path / ".narration.workflow.lock").exists()


@pytest.mark.parametrize("cleanup", ["unlink", "close"])
@pytest.mark.parametrize("failure", [KeyboardInterrupt(), MacSpeechError(code=ErrorCode.TIMEOUT, message="primary timeout")])
def test_cleanup_does_not_mask_original_failure(tmp_path, monkeypatch, cleanup, failure):
    paths = workflow.prepare_workflow_paths(str(tmp_path), align=False)
    if cleanup == "unlink":
        original = Path.unlink

        def denied(path, *args, **kwargs):
            if path == paths.lock:
                raise PermissionError("synthetic cleanup failure")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", denied)
    else:
        original_close = os.close

        def close_then_fail(descriptor):
            original_close(descriptor)
            raise OSError("synthetic close failure after closing the owned descriptor")

        monkeypatch.setattr(workflow.os, "close", close_then_fail)
    with pytest.raises(type(failure)) as error:
        with workflow._claim_workflow(paths):
            raise failure
    assert error.value is failure


def test_cleanup_failure_after_success_is_a_structured_error(tmp_path, monkeypatch):
    paths = workflow.prepare_workflow_paths(str(tmp_path), align=False)
    original = Path.unlink

    def denied(path, *args, **kwargs):
        if path == paths.lock:
            raise PermissionError("synthetic cleanup failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", denied)
    with pytest.raises(MacSpeechError) as error:
        with workflow._claim_workflow(paths):
            pass
    assert error.value.code == ErrorCode.INTERNAL_ERROR
    assert paths.lock.exists()


def test_real_synthetic_child_is_reaped_before_cancellation_releases_claim(tmp_path, monkeypatch):
    # The real child is harmless: it only waits and would write synthetic
    # bytes if explicitly released. Raising KeyboardInterrupt in the
    # Python communicate path models SIGINT sent to the parent only.
    binary = tmp_path / "synthetic-engine"
    ready = tmp_path / "child.pid"
    release = tmp_path / "release-child"
    binary.write_text(
        f"#!{sys.executable}\n"
        "import os,pathlib,sys,time\n"
        "output=pathlib.Path(sys.argv[sys.argv.index('--output')+1])\n"
        f"pathlib.Path({str(ready)!r}).write_text(str(os.getpid()))\n"
        f"while not pathlib.Path({str(release)!r}).exists(): time.sleep(0.01)\n"
        "output.write_bytes(b'synthetic late writer')\n"
    )
    binary.chmod(0o700)
    monkeypatch.setattr(tts_engine, "resolve_binary", lambda: binary)
    original = subprocess.Popen
    children = []

    def spawn(*args, **kwargs):
        child = original(*args, **kwargs)
        children.append(child)

        def interrupted(*args, **kwargs):
            deadline = time.monotonic() + 10
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert ready.exists(), "Synthetic child did not start"
            raise KeyboardInterrupt

        child.communicate = interrupted
        return child

    monkeypatch.setattr(tts_engine.subprocess, "Popen", spawn)
    try:
        with pytest.raises(KeyboardInterrupt):
            workflow.run_narration_pipeline("Public sample.", output_dir=str(tmp_path), align=False, persist_manifest=True)
        assert children[0].poll() is not None
        assert not (tmp_path / ".narration.workflow.lock").exists()
        release.write_text("release")
        assert not (tmp_path / "narration.wav").exists()
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)


def test_unconfirmed_native_termination_retains_claim(tmp_path, monkeypatch):
    process = Mock()
    process.communicate.side_effect = subprocess.TimeoutExpired("synthetic engine", 1)
    process.wait.side_effect = subprocess.TimeoutExpired("synthetic engine", 10)
    monkeypatch.setattr(tts_engine, "resolve_binary", lambda: tmp_path / "mock-engine")
    monkeypatch.setattr(tts_engine.subprocess, "Popen", lambda *args, **kwargs: process)
    with pytest.raises(MacSpeechError) as error:
        workflow.run_narration_pipeline("Public sample.", output_dir=str(tmp_path), align=False, persist_manifest=True)
    assert error.value.code == ErrorCode.TIMEOUT
    assert getattr(error.value, "_mac_speech_native_unconfirmed", False)
    assert (tmp_path / ".narration.workflow.lock").exists()
    assert "termination could not be confirmed" in str(error.value)
    with pytest.raises(MacSpeechError) as busy:
        workflow.run_narration_pipeline("Other.", output_dir=str(tmp_path), align=False, force=True)
    assert busy.value.code == ErrorCode.OUTPUT_EXISTS


@pytest.mark.skipif(sys.platform == "win32", reason="Parent-only POSIX SIGINT regression")
def test_parent_only_sigint_reaps_child_before_claim_release(tmp_path):
    binary = tmp_path / "synthetic-engine"
    ready = tmp_path / "child.pid"
    release = tmp_path / "release-child"
    binary.write_text(
        f"#!{sys.executable}\n"
        "import os,pathlib,sys,time\n"
        "output=pathlib.Path(sys.argv[sys.argv.index('--output')+1])\n"
        f"pathlib.Path({str(ready)!r}).write_text(str(os.getpid()))\n"
        f"while not pathlib.Path({str(release)!r}).exists(): time.sleep(0.01)\n"
        "output.write_bytes(b'synthetic late writer')\n"
    )
    binary.chmod(0o700)
    harness = (
        "import os,pathlib\n"
        "from mac_speech import workflow\n"
        "from mac_speech.tts import engine\n"
        f"engine.resolve_binary=lambda:pathlib.Path({str(binary)!r})\n"
        "try:\n"
        f" workflow.run_narration_pipeline('Public sample.',output_dir={str(tmp_path)!r},align=False,persist_manifest=True)\n"
        "except KeyboardInterrupt:\n"
        f" child=int(pathlib.Path({str(ready)!r}).read_text())\n"
        " try: os.kill(child,0)\n"
        " except ProcessLookupError: pass\n"
        " else: raise AssertionError('Native child was not reaped')\n"
        " print('cancelled-and-reaped')\n"
        "else: raise AssertionError('Parent SIGINT did not cancel')\n"
    )
    parent = subprocess.Popen([sys.executable, "-c", harness], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and parent.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready.exists(), "Synthetic native child did not start"
        os.kill(parent.pid, signal.SIGINT)  # Not its process group or child.
        stdout, stderr = parent.communicate(timeout=15)
        assert parent.returncode == 0, stderr
        assert "cancelled-and-reaped" in stdout
        assert not (tmp_path / ".narration.workflow.lock").exists()
        assert not (tmp_path / "narration.wav").exists()
    finally:
        if parent.poll() is None:
            parent.kill()
        parent.wait(timeout=10)
        # A failed regression must not leak the known synthetic writer.
        if ready.exists():
            try:
                os.kill(int(ready.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.parametrize("when", ["after-construction", "during-construction"])
@pytest.mark.parametrize("broken_diagnostics", [False, True])
def test_acquisition_interrupt_never_frees_a_live_writer_claim(tmp_path, monkeypatch, when, broken_diagnostics):
    # No voice/audio API: use an actual waiting Python child to exercise
    # acquisition, including a constructor that raises after creating it.
    monkeypatch.setattr(tts_engine, "resolve_binary", lambda: tmp_path / "synthetic-engine")
    original = subprocess.Popen
    children = []
    interrupted = KeyboardInterrupt()
    if broken_diagnostics:
        def unavailable(message):
            raise BrokenPipeError("synthetic disconnected stderr")
        monkeypatch.setattr(logging_utils, "diagnostic", unavailable)

    def spawn(*args, **kwargs):
        child = original([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        children.append(child)
        if when == "during-construction":
            raise interrupted
        return child

    monkeypatch.setattr(tts_engine.subprocess, "Popen", spawn)
    lines, first = inspect.getsourcelines(tts_engine.run_operation)
    target = next(first + index for index, line in enumerate(lines) if line.strip() == "if pid_file is not None:")
    previous_trace = sys.gettrace()

    def trace(frame, event, argument):
        if when == "after-construction" and event == "line" and frame.f_code is tts_engine.run_operation.__code__ and frame.f_lineno == target:
            raise interrupted
        return trace

    try:
        if when == "after-construction":
            sys.settrace(trace)
        with pytest.raises(KeyboardInterrupt) as error:
            workflow.run_narration_pipeline("Public sample.", output_dir=str(tmp_path), align=False, persist_manifest=True)
        assert error.value is interrupted
        if when == "after-construction":
            assert children[0].poll() is not None
            assert not (tmp_path / ".narration.workflow.lock").exists()
        else:
            assert getattr(interrupted, "_mac_speech_native_unconfirmed", False)
            assert (tmp_path / ".narration.workflow.lock").exists()
    finally:
        sys.settrace(previous_trace)
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)


def test_unconfirmed_oserror_tag_survives_claim_wrapping(tmp_path):
    paths = workflow.prepare_workflow_paths(str(tmp_path), align=False)
    failure = OSError("synthetic writer cleanup unconfirmed")
    setattr(failure, "_mac_speech_native_unconfirmed", True)
    with pytest.raises(MacSpeechError) as error:
        with workflow._claim_workflow(paths):
            raise failure
    assert getattr(error.value, "_mac_speech_native_unconfirmed", False)
    assert paths.lock.exists()


def test_unconfirmed_communicate_oserror_keeps_workflow_claim(tmp_path, monkeypatch):
    process = Mock()
    process.communicate.side_effect = OSError("synthetic communication failure")
    process.kill.side_effect = PermissionError("synthetic kill failure")
    monkeypatch.setattr(tts_engine, "resolve_binary", lambda: tmp_path / "mock-engine")
    monkeypatch.setattr(tts_engine.subprocess, "Popen", lambda *args, **kwargs: process)
    with pytest.raises(MacSpeechError) as error:
        workflow.run_narration_pipeline("Public sample.", output_dir=str(tmp_path), align=False, persist_manifest=True)
    assert getattr(error.value, "_mac_speech_native_unconfirmed", False)
    assert (tmp_path / ".narration.workflow.lock").exists()


def test_failed_cleanup_warning_preserves_original_exception(tmp_path, monkeypatch):
    paths = workflow.prepare_workflow_paths(str(tmp_path), align=False)
    original = Path.unlink
    failure = KeyboardInterrupt()

    def denied(path, *args, **kwargs):
        if path == paths.lock:
            raise PermissionError("synthetic marker cleanup failure")
        return original(path, *args, **kwargs)

    def unavailable(message):
        raise BrokenPipeError("synthetic disconnected stderr")

    monkeypatch.setattr(Path, "unlink", denied)
    monkeypatch.setattr(logging_utils, "diagnostic", unavailable)
    with pytest.raises(KeyboardInterrupt) as error:
        with workflow._claim_workflow(paths):
            raise failure
    assert error.value is failure
