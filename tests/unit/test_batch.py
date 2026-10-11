"""Bounded batch scheduler with real local I/O and mocked speech engines."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest

from mac_speech import batch
from mac_speech.cli import main
from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.logging_utils import diagnostic
from mac_speech.tts.models import SynthesizeResult


def scene_list(count=3):
    return [batch.BatchScene(f"scene-{index:02}", f"Private source sentence number {index}.") for index in range(count)]


def save(text, *, output_path, **kwargs):
    Path(output_path).write_bytes(b"synthetic audio")
    return SynthesizeResult(
        output_path=output_path, format="wav", sample_rate=22050.0, channels=1,
        bit_depth=16, duration_seconds=1, file_size_bytes=15, sentence_count=1,
        voice_identifier="public-test-voice", language="en-US",
    )


@pytest.fixture
def synth(monkeypatch):
    mocked = Mock(side_effect=save)
    monkeypatch.setattr(batch, "synthesize_to_file", mocked)
    return mocked


def test_serial_default_produces_private_ordered_report_and_checkpoints(tmp_path, synth):
    scenes = scene_list()
    result = batch.synthesize_batch(scenes, output_dir=str(tmp_path))
    assert result.ok and result.workers == 1
    assert [item.basename for item in result.scenes] == [item.basename for item in scenes]
    report = json.loads((tmp_path / "batch.json").read_text())
    assert report["ok"] and report["schema_version"] == 1
    assert (tmp_path / "batch.json").stat().st_mode & 0o777 == 0o600
    for item in scenes:
        assert item.text not in json.dumps(report)
        checkpoint = tmp_path / f"{item.basename}.workflow.json"
        assert checkpoint.stat().st_mode & 0o777 == 0o600
        assert json.loads(checkpoint.read_text())["ok"]
    assert not list(tmp_path.glob(".*.lock"))
    assert synth.call_count == 3


@pytest.mark.parametrize("workers", [0, 5, True, "2", -1])
def test_bad_worker_cap_rejected_before_directory_or_speech(tmp_path, synth, workers):
    output = tmp_path / "not-created"
    with pytest.raises(MacSpeechError) as error:
        batch.synthesize_batch(scene_list(), output_dir=str(output), workers=workers)
    assert error.value.code == ErrorCode.INVALID_ARGUMENT
    assert not output.exists()
    synth.assert_not_called()


@pytest.mark.parametrize("scenes", [
    [], [batch.BatchScene("../outside", "Text")],
    [batch.BatchScene("scene", " ")], [batch.BatchScene("scene", "\ud800")],
    [batch.BatchScene("scene", "public\0")],
    [batch.BatchScene("scene", "public", voice="v\0")],
    [batch.BatchScene("scene", "public", language="\ud800")],
    [batch.BatchScene("same", "A"), batch.BatchScene("SAME", "B")],
    [batch.BatchScene("caf\u00e9", "A"), batch.BatchScene("cafe\u0301", "B")],
])
def test_invalid_scenes_rejected_without_side_effects(tmp_path, synth, scenes):
    output = tmp_path / "not-created"
    with pytest.raises(MacSpeechError):
        batch.synthesize_batch(scenes, output_dir=str(output))
    assert not output.exists()
    synth.assert_not_called()


@pytest.mark.parametrize("payload", [
    None, [], {}, {"schema_version": True, "scenes": []},
    {"schema_version": "1", "scenes": []}, {"schema_version": 2, "scenes": []},
    {"schema_version": 1, "scenes": [], "align": True},
    {"schema_version": 1, "scenes": [{"basename": "x", "text": "Text", "engine": "faster-whisper"}]},
    {"schema_version": 1, "scenes": [{"basename": "x"}]},
])
def test_strict_input_schema(payload):
    with pytest.raises(MacSpeechError) as error:
        batch.scenes_from_dict(payload)
    assert error.value.code == ErrorCode.INVALID_ARGUMENT


def test_valid_json_input_and_repr_do_not_duplicate_text():
    parsed = batch.scenes_from_dict({"schema_version": 1, "scenes": [{"basename": "x", "text": "private narration", "language": "en-US"}]})
    assert parsed[0].text == "private narration"
    assert "private narration" not in repr(parsed[0])


def test_parallelism_is_bounded_and_result_order_is_input_order(tmp_path, synth):
    gate = threading.Lock()
    active = 0
    maximum = 0

    def slower(text, **kwargs):
        nonlocal active, maximum
        with gate:
            active += 1
            maximum = max(maximum, active)
        try:
            time.sleep(0.02 if "number 0" not in text else 0.06)
            return save(text, **kwargs)
        finally:
            with gate:
                active -= 1

    synth.side_effect = slower
    result = batch.synthesize_batch(scene_list(7), output_dir=str(tmp_path), workers=2)
    assert maximum == 2
    assert result.ok
    assert [item.basename for item in result.scenes] == [item.basename for item in scene_list(7)]


def test_inflight_submission_is_capped_not_entire_batch(tmp_path, synth, monkeypatch):
    gate = threading.Lock()
    submitted = 0
    maximum = 0

    class TrackingPool(ThreadPoolExecutor):
        def submit(self, *args, **kwargs):
            nonlocal submitted, maximum
            with gate:
                submitted += 1
                maximum = max(maximum, submitted)
            future = super().submit(*args, **kwargs)

            def done(_):
                nonlocal submitted
                with gate:
                    submitted -= 1

            future.add_done_callback(done)
            return future

    monkeypatch.setattr(batch, "ThreadPoolExecutor", TrackingPool)
    synth.side_effect = lambda text, **kwargs: (time.sleep(0.01), save(text, **kwargs))[1]
    assert batch.synthesize_batch(scene_list(15), output_dir=str(tmp_path), workers=3).ok
    assert maximum <= 3


def test_scene_collision_is_partial_failure_and_force_is_explicit(tmp_path, synth):
    old = tmp_path / "scene-00.wav"
    old.write_bytes(b"keep old")
    result = batch.synthesize_batch(scene_list(2), output_dir=str(tmp_path))
    assert not result.ok
    assert [item.status for item in result.scenes] == ["failed", "success"]
    assert result.scenes[0].error_code == "output_exists"
    assert old.read_bytes() == b"keep old"
    assert synth.call_count == 1
    second = batch.synthesize_batch(scene_list(2), output_dir=str(tmp_path), force=True)
    assert second.ok and old.read_bytes() == b"synthetic audio"
    assert all(call.kwargs["force"] for call in synth.call_args_list[-2:])


def test_existing_batch_report_or_claim_preserved_before_speech(tmp_path, synth):
    report = tmp_path / "batch.json"
    report.write_text("keep")
    with pytest.raises(MacSpeechError):
        batch.synthesize_batch(scene_list(), output_dir=str(tmp_path))
    assert report.read_text() == "keep"
    marker = tmp_path / ".batch.lock"
    marker.write_text("unverified")
    with pytest.raises(MacSpeechError):
        batch.synthesize_batch(scene_list(), output_dir=str(tmp_path), force=True)
    assert marker.read_text() == "unverified" and report.read_text() == "keep"
    synth.assert_not_called()


def test_raw_engine_failures_and_diagnostics_are_not_in_report(tmp_path, synth, capsys):
    def failure(text, **kwargs):
        diagnostic(text)
        raise MacSpeechError(code=ErrorCode.NATIVE_PROCESS_ERROR, message=text)

    synth.side_effect = failure
    result = batch.synthesize_batch(scene_list(1), output_dir=str(tmp_path))
    assert result.scenes[0].status == "failed"
    combined = json.dumps(result.to_dict()) + (tmp_path / "batch.json").read_text() + (tmp_path / "scene-00.workflow.json").read_text()
    assert scene_list(1)[0].text not in combined
    assert capsys.readouterr().err == ""


def test_unconfirmed_writer_stops_queue_and_retains_claims(tmp_path, synth):
    error = MacSpeechError(code=ErrorCode.NATIVE_PROCESS_ERROR, message="private backend message")
    setattr(error, "_mac_speech_native_unconfirmed", True)
    synth.side_effect = error
    result = batch.synthesize_batch(scene_list(3), output_dir=str(tmp_path))
    assert result.termination_unconfirmed and not result.ok
    assert synth.call_count == 1
    assert (tmp_path / ".batch.lock").exists()
    assert (tmp_path / ".scene-00.workflow.lock").exists()
    assert [item.status for item in result.scenes] == ["failed", "cancelled", "cancelled"]
    assert "private backend message" not in json.dumps(result.to_dict())


def test_cooperative_cancel_drains_active_scenes_and_does_not_start_more(tmp_path, synth):
    stop = threading.Event()
    started = threading.Event()

    def waiting(text, **kwargs):
        started.set()
        assert kwargs["cancel_event"].wait(timeout=5)
        raise MacSpeechError(code=ErrorCode.CANCELLED, message="cancelled")

    synth.side_effect = waiting
    timer = threading.Thread(target=lambda: (started.wait(timeout=5), stop.set()))
    timer.start()
    try:
        result = batch.synthesize_batch(scene_list(8), output_dir=str(tmp_path), workers=2, cancel_event=stop)
    finally:
        timer.join(timeout=5)
    assert result.cancelled and not result.ok
    assert synth.call_count <= 2
    assert all(item.status == "cancelled" for item in result.scenes)
    assert not list(tmp_path.glob(".*.lock"))


def test_keyboard_interrupt_cancels_before_executor_drain(tmp_path, synth, monkeypatch):
    def waiting(text, **kwargs):
        assert kwargs["cancel_event"].wait(timeout=5)
        raise MacSpeechError(code=ErrorCode.CANCELLED, message="cancelled")

    synth.side_effect = waiting
    monkeypatch.setattr(batch, "wait", Mock(side_effect=KeyboardInterrupt))
    result = batch.synthesize_batch(scene_list(6), output_dir=str(tmp_path), workers=2)
    assert result.cancelled and all(item.status == "cancelled" for item in result.scenes)
    assert not list(tmp_path.glob(".*.lock"))


def test_interrupted_submit_does_not_admit_unknown_scene(tmp_path, synth, monkeypatch):
    class InterruptedPool(ThreadPoolExecutor):
        def submit(self, *args, **kwargs):
            super().submit(*args, **kwargs)
            raise KeyboardInterrupt

    monkeypatch.setattr(batch, "ThreadPoolExecutor", InterruptedPool)
    result = batch.synthesize_batch(scene_list(3), output_dir=str(tmp_path))
    assert all(item.status == "cancelled" for item in result.scenes)
    assert result.cancelled
    synth.assert_not_called()


def test_interruption_after_thread_start_cannot_begin_native_work(tmp_path, synth, monkeypatch):
    original = threading.Thread.start
    started_threads = []

    def start_then_interrupt(thread):
        original(thread)
        if thread.name.startswith("mac-speech-batch"):
            started_threads.append(thread)
            raise KeyboardInterrupt

    monkeypatch.setattr(threading.Thread, "start", start_then_interrupt)
    result = batch.synthesize_batch(scene_list(3), output_dir=str(tmp_path), workers=2)
    for thread in started_threads:
        thread.join(timeout=5)
        assert not thread.is_alive()
    assert result.cancelled and all(item.status == "cancelled" for item in result.scenes)
    synth.assert_not_called()
    assert not list(tmp_path.glob("*.wav"))
    assert not list(tmp_path.glob(".*.lock"))


def test_foreign_batch_report_is_not_overwritten(tmp_path, synth):
    def replace_report(text, **kwargs):
        other = tmp_path / "other.json"
        other.write_text("keep foreign")
        other.replace(tmp_path / "batch.json")
        return save(text, **kwargs)

    synth.side_effect = replace_report
    with pytest.raises(MacSpeechError) as error:
        batch.synthesize_batch(scene_list(1), output_dir=str(tmp_path))
    assert error.value.code == ErrorCode.OUTPUT_EXISTS
    assert (tmp_path / "batch.json").read_text() == "keep foreign"
    assert (tmp_path / "scene-00.wav").exists()
    assert not (tmp_path / ".batch.lock").exists()


def test_cli_batch_json_and_invalid_input_are_sanitized(tmp_path, synth, capsys):
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps({"schema_version": 1, "scenes": [{"basename": "scene", "text": "private input"}]}))
    output = tmp_path / "outputs"
    assert main(["tts", "batch", "--input", str(input_file), "--output-dir", str(output), "--json"]) == 0
    report = capsys.readouterr().out
    assert json.loads(report)["ok"] and "private input" not in report
    input_file.write_text('invalid private input {')
    assert main(["tts", "batch", "--input", str(input_file), "--output-dir", str(output), "--json"]) == 2
    error = capsys.readouterr().out
    assert json.loads(error)["error"]["code"] == "invalid_argument"
    assert "private input" not in error
