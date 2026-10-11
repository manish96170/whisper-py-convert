"""Unit tests for mac_speech.workflow. Mocks the TTS/STT layers; never
spawns a real subprocess."""

from __future__ import annotations

from unittest.mock import patch

from mac_speech import workflow
from mac_speech.stt.models import Segment, Transcript, Word
from mac_speech.tts.models import SynthesizeResult


def _fake_synth_result(output_path: str) -> SynthesizeResult:
    return SynthesizeResult(
        output_path=output_path, format="wav", sample_rate=22050.0, channels=1, bit_depth=16,
        duration_seconds=2.0, file_size_bytes=1000, sentence_count=1, voice_identifier="v", language="en-US",
    )


def test_stage_synthesize_success(tmp_path):
    output_path = str(tmp_path / "out.wav")
    with patch.object(workflow, "synthesize_to_file", return_value=_fake_synth_result(output_path)):
        stage = workflow.stage_synthesize("hello", output_path=output_path)
    assert stage.status == "success"
    assert stage.output_path == output_path
    assert stage.provenance["engine"] == "mac-speech-tts"


def test_stage_synthesize_records_failure_without_raising(tmp_path):
    with patch.object(workflow, "synthesize_to_file", side_effect=RuntimeError("boom")):
        stage = workflow.stage_synthesize("hello", output_path=str(tmp_path / "out.wav"))
    assert stage.status == "failed"
    assert "boom" in stage.error


def test_stage_align_success():
    transcript = Transcript(engine="apple", segments=[Segment(text="Hello.", start=0.0, end=1.0)])
    with patch.object(workflow, "align_via_stt_roundtrip", return_value=transcript):
        stage, result = workflow.stage_align("audio.wav")
    assert stage.status == "success"
    assert result is transcript
    assert stage.provenance["method"] == "stt_roundtrip_approximation"


def test_stage_align_failure_returns_none_transcript():
    with patch.object(workflow, "align_via_stt_roundtrip", side_effect=RuntimeError("no engine")):
        stage, result = workflow.stage_align("audio.wav")
    assert stage.status == "failed"
    assert result is None


def test_stage_render_srt_writes_file(tmp_path):
    transcript = Transcript(
        engine="apple",
        segments=[Segment(text="Hi.", start=0.0, end=1.0, words=[Word(text="Hi.", start=0.0, end=1.0)])],
    )
    output_path = str(tmp_path / "out.srt")
    stage = workflow.stage_render_srt(transcript, output_path=output_path)
    assert stage.status == "success"
    assert "Hi." in open(output_path).read()


def test_run_narration_pipeline_full_chain(tmp_path):
    output_dir = str(tmp_path)
    audio_path = str(tmp_path / "narration.wav")
    transcript = Transcript(
        engine="apple",
        segments=[Segment(text="Hello.", start=0.0, end=1.0, words=[Word(text="Hello.", start=0.0, end=1.0)])],
    )

    with patch.object(workflow, "synthesize_to_file", return_value=_fake_synth_result(audio_path)), patch.object(
        workflow, "align_via_stt_roundtrip", return_value=transcript
    ):
        manifest = workflow.run_narration_pipeline("Hello.", output_dir=output_dir)

    assert manifest.ok
    assert [s.name for s in manifest.stages] == ["synthesize", "align", "render_srt"]
    srt_path = tmp_path / "narration.srt"
    assert srt_path.exists()
    assert "Hello." in srt_path.read_text()


def test_run_narration_pipeline_stops_after_synthesize_failure(tmp_path):
    with patch.object(workflow, "synthesize_to_file", side_effect=RuntimeError("no engine")):
        manifest = workflow.run_narration_pipeline("Hello.", output_dir=str(tmp_path))
    assert not manifest.ok
    assert [s.name for s in manifest.stages] == ["synthesize"]


def test_run_narration_pipeline_no_align_skips_alignment_stages(tmp_path):
    audio_path = str(tmp_path / "narration.wav")
    with patch.object(workflow, "synthesize_to_file", return_value=_fake_synth_result(audio_path)) as synth, patch.object(
        workflow, "align_via_stt_roundtrip"
    ) as align:
        manifest = workflow.run_narration_pipeline("Hello.", output_dir=str(tmp_path), align=False)
    assert [s.name for s in manifest.stages] == ["synthesize"]
    align.assert_not_called()
    synth.assert_called_once()


def test_manifest_write_is_atomic_no_leftover_temp_files(tmp_path):
    manifest = workflow.new_manifest("hello")
    manifest_path = tmp_path / "out.workflow.json"
    manifest.write(manifest_path)
    leftovers = [p for p in tmp_path.iterdir() if ".tmp-" in p.name]
    assert leftovers == []
    assert manifest_path.exists()


def test_manifest_source_text_hash_never_stores_text():
    manifest = workflow.new_manifest("sensitive narration text")
    payload = manifest.to_dict()
    assert "sensitive narration text" not in json_dump_safe(payload)


def json_dump_safe(payload):
    import json

    return json.dumps(payload)
