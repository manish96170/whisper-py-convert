"""Exercise the sample with real workflow helpers and mocked speech engines.

No native processes, networks, models, credentials, or private audio are used.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from mac_speech import workflow
from mac_speech.stt.models import Segment, Transcript, Word
from mac_speech.tts.models import SynthesizeResult


_SCRIPT = Path(__file__).resolve().parents[2] / "examples" / "narration_workflow.py"
_SPEC = importlib.util.spec_from_file_location("narration_example", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
example = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(example)


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("The narration sample unit tests must not start processes or connect to networks")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


@pytest.fixture
def synth(monkeypatch):
    def save(text, *, output_path, voice=None, language=None, force=False):
        assert not force
        Path(output_path).write_bytes(b"mock WAV artifact")
        return SynthesizeResult(
            output_path=output_path, format="wav", sample_rate=22050.0,
            channels=1, bit_depth=16, duration_seconds=1.5,
            file_size_bytes=17, sentence_count=1,
            voice_identifier="public-test-system-voice", language=language,
        )

    mock = Mock(side_effect=save)
    monkeypatch.setattr(workflow, "synthesize_to_file", mock)
    return mock


@pytest.fixture
def align(monkeypatch):
    transcript = Transcript(engine="apple", segments=[Segment(
        text="Recognized words.", start=0.0, end=1.5,
        words=[Word(text="Recognized", start=0.0, end=0.75), Word(text="words.", start=0.75, end=1.5)],
    )])
    mock = Mock(return_value=transcript)
    monkeypatch.setattr(workflow, "align_via_stt_roundtrip", mock)
    return mock


def test_full_workflow_saves_audio_srt_manifest_and_private_json_result(tmp_path, capsys, synth, align):
    output = tmp_path / "new-run"
    source = "Sample source must not appear in diagnostics."
    assert example.main(["--text", source, "--output-dir", str(output)]) == 0

    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert captured.err == ""
    assert source not in captured.out
    assert "Recognized words." not in captured.out
    assert "public-test-system-voice" not in captured.out
    assert report["ok"] is True
    assert report["mode"] == "narration"
    assert report["timing_method"] == "stt_roundtrip_approximation"
    assert [stage["name"] for stage in report["stages"]] == ["synthesize", "align", "render_srt"]
    assert all(stage["status"] == "success" for stage in report["stages"])
    assert (output / "narration.wav").read_bytes() == b"mock WAV artifact"
    assert (output / "narration.srt").read_text() == (
        "1\n00:00:00,000 --> 00:00:00,750\nRecognized\n\n"
        "2\n00:00:00,750 --> 00:00:01,500\nwords.\n"
    )
    manifest = json.loads(Path(report["manifest_path"]).read_text())
    assert manifest["ok"] is True
    assert manifest["source_text_sha256"] == hashlib.sha256(source.encode()).hexdigest()
    assert source not in json.dumps(manifest)
    assert manifest["stages"][1]["provenance"]["method"] == "stt_roundtrip_approximation"
    synth.assert_called_once()
    align.assert_called_once_with(str(output / "narration.wav"), engine_name="apple", language="en-US")


def test_synthesize_only_reads_utf8_file_without_calling_stt(tmp_path, capsys, synth, align):
    source = "A Unicode sample: café, 你好."
    text_file = tmp_path / "source.txt"
    text_file.write_text(source, encoding="utf-8")
    output = tmp_path / "tts-only"
    assert example.main([
        "--text-file", str(text_file), "--output-dir", str(output), "--synthesize-only", "--language", "fr-FR",
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "synthesize_only"
    assert report["timing_method"] == "not_computed"
    assert [stage["name"] for stage in report["stages"]] == ["synthesize"]
    assert (output / "narration.wav").exists()
    assert (output / "narration.workflow.json").exists()
    assert not (output / "narration.srt").exists()
    synth.assert_called_once_with(source, output_path=str(output / "narration.wav"), voice=None, language="fr-FR", force=False)
    align.assert_not_called()


def test_stdin_input(tmp_path, capsys, monkeypatch, synth, align):
    monkeypatch.setattr(sys, "stdin", io.StringIO("Public stdin sample."))
    assert example.main([
        "--text-file", "-", "--output-dir", str(tmp_path / "stdin-run"), "--synthesize-only",
    ]) == 0
    assert "Public stdin sample." not in capsys.readouterr().out
    assert synth.call_args.args[0] == "Public stdin sample."
    align.assert_not_called()


def test_alignment_failure_retains_audio_and_failure_manifest_without_raw_logs(
    tmp_path, capsys, synth, align
):
    output = tmp_path / "partial-run"

    def fail(*args, **kwargs):
        # The prior successful stage is persisted before attempting STT.
        saved = json.loads((output / "narration.workflow.json").read_text())
        assert [stage["name"] for stage in saved["stages"]] == ["synthesize"]
        print("Potentially private recognized words.", file=sys.stderr)
        raise RuntimeError("Potentially private input text. Apple does not support locale en-US.")

    align.side_effect = fail
    assert example.main(["--text", "Potentially private input text.", "--output-dir", str(output)]) == 1
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["ok"] is False
    assert report["timing_method"] == "not_computed"
    assert [stage["status"] for stage in report["stages"]] == ["success", "failed"]
    assert "--synthesize-only" in captured.err
    assert "doctor" in captured.err
    assert "locale/reservation" in captured.err
    assert "stage_align" in captured.err
    assert (output / "narration.wav").read_bytes() == b"mock WAV artifact"
    assert not (output / "narration.srt").exists()
    manifest_text = (output / "narration.workflow.json").read_text()
    assert json.loads(manifest_text)["ok"] is False
    for text in (captured.out, captured.err, manifest_text):
        assert "Potentially private" not in text
    synth.assert_called_once()


@pytest.mark.parametrize("segments", [
    [],
    [Segment(text="", start=0.0, end=1.0)],
    [Segment(text="   ", start=0.0, end=1.0)],
    [Segment(text="Unusable words", start=0.0, end=1.0, words=[Word(text="", start=0.0, end=1.0)])],
    [Segment(text="Unusable words", start=0.0, end=1.0, words=[Word(text="  ", start=0.0, end=1.0)])],
    [Segment(text="Missing timing", start=0.0, end=0.0)],
    [Segment(text="Invalid timing", start=float("nan"), end=1.0)],
    [Segment(text="Invalid timing", start=0.0, end=float("inf"))],
])
def test_no_usable_alignment_cues_fails_and_retains_audio(tmp_path, capsys, synth, align, segments):
    align.return_value = Transcript(engine="apple", segments=segments)
    output = tmp_path / "empty-alignment"
    assert example.main(["--text", "Public sample.", "--output-dir", str(output)]) == 1
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["ok"] is False
    assert report["timing_method"] == "not_computed"
    assert [stage["status"] for stage in report["stages"]] == ["success", "failed"]
    assert "no usable timed cues" in captured.err
    assert (output / "narration.wav").exists()
    assert not (output / "narration.srt").exists()
    assert json.loads((output / "narration.workflow.json").read_text())["ok"] is False


def test_synthesis_failure_still_saves_manifest_and_skips_stt(tmp_path, capsys, synth, align):
    synth.side_effect = RuntimeError("private synthesis text")
    output = tmp_path / "failed-tts"
    assert example.main(["--text", "private synthesis text", "--output-dir", str(output)]) == 1
    captured = capsys.readouterr()
    manifest_text = (output / "narration.workflow.json").read_text()
    assert "private synthesis text" not in captured.out + captured.err + manifest_text
    assert json.loads(manifest_text)["stages"][0]["status"] == "failed"
    assert "./install.sh tts" in captured.err
    align.assert_not_called()


def test_srt_failure_keeps_audio_and_records_failed_stage(tmp_path, capsys, monkeypatch, synth, align):
    monkeypatch.setattr(workflow, "transcript_to_srt", Mock(side_effect=ValueError("private recognized transcript")))
    output = tmp_path / "failed-srt"
    assert example.main(["--text", "Sample.", "--output-dir", str(output)]) == 1
    captured = capsys.readouterr()
    manifest_text = (output / "narration.workflow.json").read_text()
    manifest = json.loads(manifest_text)
    assert manifest["ok"] is False
    assert manifest["stages"][-1]["name"] == "render_srt"
    assert manifest["stages"][-1]["status"] == "failed"
    assert (output / "narration.wav").exists()
    assert "private recognized transcript" not in captured.out + captured.err + manifest_text


@pytest.mark.parametrize("artifact", [None, "narration.wav", "narration.srt", "narration.workflow.json"])
def test_existing_directory_is_never_reused_or_overwritten(tmp_path, capsys, synth, align, artifact):
    output = tmp_path / "existing"
    output.mkdir()
    if artifact is not None:
        (output / artifact).write_bytes(b"prior artifact")
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    assert example.main(["--text", "New narration.", "--output-dir", str(output)]) == 3
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "output_exists"
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before
    synth.assert_not_called()
    align.assert_not_called()


@pytest.mark.parametrize("kind", ["file", "directory_symlink", "dangling_symlink"])
def test_existing_output_files_and_symlinks_are_refused(tmp_path, capsys, synth, align, kind):
    output = tmp_path / "existing-path"
    target = tmp_path / "target"
    if kind == "file":
        output.write_bytes(b"prior file")
    else:
        if kind == "directory_symlink":
            target.mkdir()
        output.symlink_to(target)
    assert example.main(["--text", "New narration.", "--output-dir", str(output)]) == 3
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "output_exists"
    if kind == "file":
        assert output.read_bytes() == b"prior file"
    else:
        assert output.is_symlink()
        assert not target.exists() or list(target.iterdir()) == []
    synth.assert_not_called()
    align.assert_not_called()


@pytest.mark.parametrize("text", ["", " \n\t "])
def test_empty_input_rejected_before_creating_output(tmp_path, capsys, synth, align, text):
    output = tmp_path / "not-created"
    assert example.main(["--text", text, "--output-dir", str(output)]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "invalid_input"
    assert not output.exists()
    synth.assert_not_called()
    align.assert_not_called()


@pytest.mark.parametrize("kind", ["missing", "invalid_utf8"])
def test_unreadable_text_input_is_actionable_without_logging_content(tmp_path, capsys, synth, align, kind):
    text_file = tmp_path / "input.txt"
    if kind == "invalid_utf8":
        text_file.write_bytes(b"private input\xff")
    output = tmp_path / "not-created"
    assert example.main(["--text-file", str(text_file), "--output-dir", str(output)]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out)["error"]["code"] == "invalid_input"
    assert "UTF-8" in captured.err
    assert "private input" not in captured.out + captured.err
    assert not output.exists()
    synth.assert_not_called()
    align.assert_not_called()


def test_manifest_write_failure_returns_nonzero_and_retains_audio(tmp_path, capsys, monkeypatch, synth, align):
    monkeypatch.setattr(workflow.WorkflowManifest, "write", Mock(side_effect=OSError("private path")))
    output = tmp_path / "manifest-error"
    assert example.main(["--text", "Sample.", "--output-dir", str(output)]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out)["error"]["code"] == "manifest_write_failed"
    assert "private path" not in captured.out + captured.err
    assert (output / "narration.wav").exists()
    align.assert_not_called()


def test_help_lists_offline_quickstart_without_engine_calls(capsys, synth, align):
    with pytest.raises(SystemExit) as exc:
        example.main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "--synthesize-only" in captured.out
    assert "--text-file" in captured.out
    assert "--output-dir" in captured.out
    assert captured.err == ""
    synth.assert_not_called()
    align.assert_not_called()
