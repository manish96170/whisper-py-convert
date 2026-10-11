"""Unit tests for the mac_speech CLI (mac_speech.cli).

TTS/STT subcommand tests mock `mac_speech.tts`/`mac_speech.stt`'s public
functions rather than spawning real subprocesses — this file tests CLI
argument wiring and JSON/text output shaping, not the engines themselves
(TTS has its own integration tests in `engines/tts-swift/Tests/` and is
exercised manually; see docs/tts-engine.md; STT's engine logic has its own
mocked tests in `test_stt_engine.py`/`test_stt_client.py`). This also
matches PLAN.md section 8.1: "Mock subprocesses ... for failure and
timeout paths."
"""

from __future__ import annotations

import json

import mac_speech.stt as stt
import mac_speech.tts as tts
from mac_speech import __version__
from mac_speech.cli import main
from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.tts.models import SpeakResult, SynthesizeResult, Voice


def test_version_human(capsys):
    exit_code = main(["version"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert __version__ in captured.out


def test_version_json(capsys):
    exit_code = main(["version", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["version"] == __version__
    assert "protocol_version" in payload


def test_capabilities_json_contains_stt_and_tts(capsys):
    exit_code = main(["capabilities", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    names = {c["name"] for c in payload["capabilities"]}
    assert names == {"stt", "tts"}


def test_capabilities_human_output(capsys):
    exit_code = main(["capabilities"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "stt" in captured.out
    assert "tts" in captured.out


def test_doctor_text_output_has_marker_lines(capsys):
    exit_code = main(["doctor"])
    captured = capsys.readouterr()
    assert exit_code in (0, 1)
    lines = [line for line in captured.out.splitlines() if line.startswith("[")]
    assert lines, "expected at least one [OK]/[FAIL] doctor line"


def test_doctor_json_is_valid(capsys):
    exit_code = main(["doctor", "--json"])
    captured = capsys.readouterr()
    assert exit_code in (0, 1)
    payload = json.loads(captured.out)
    assert "checks" in payload


def test_no_command_prints_help_and_returns_usage_error(capsys):
    exit_code = main([])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "usage" in captured.err.lower()


def test_tts_without_subcommand_is_invalid_argument(capsys):
    exit_code = main(["tts"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "subcommand is required" in captured.err


# --- tts voices -----------------------------------------------------------

def test_tts_voices_json(monkeypatch, capsys):
    sample = Voice(
        identifier="com.apple.voice.compact.en-US.Samantha",
        name="Samantha",
        language="en-US",
        quality="default",
        gender="female",
        is_personal_voice=False,
        is_novelty_voice=False,
    )
    monkeypatch.setattr(tts, "list_voices", lambda language=None: [sample])

    exit_code = main(["tts", "voices", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["count"] == 1
    assert payload["voices"][0]["identifier"] == sample.identifier


def test_tts_voices_human(monkeypatch, capsys):
    sample = Voice(
        identifier="id-1", name="Name", language="en-US", quality="default",
        gender="female", is_personal_voice=False, is_novelty_voice=False,
    )
    monkeypatch.setattr(tts, "list_voices", lambda language=None: [sample])

    exit_code = main(["tts", "voices"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "id-1" in captured.out
    assert "Name" in captured.out


def test_tts_voices_passes_language_filter(monkeypatch):
    seen = {}

    def fake_list_voices(language=None):
        seen["language"] = language
        return []

    monkeypatch.setattr(tts, "list_voices", fake_list_voices)
    main(["tts", "voices", "--language", "en-GB"])
    assert seen["language"] == "en-GB"


# --- tts personal-voice-status -----------------------------------------------

def test_tts_personal_voice_status_json(monkeypatch, capsys):
    monkeypatch.setattr(tts, "personal_voice_status", lambda: "not_determined")
    exit_code = main(["tts", "personal-voice-status", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {"authorization_status": "not_determined"}


def test_tts_personal_voice_status_human(monkeypatch, capsys):
    monkeypatch.setattr(tts, "personal_voice_status", lambda: "authorized")
    exit_code = main(["tts", "personal-voice-status"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "authorized"


# --- tts speak --------------------------------------------------------------

def test_tts_speak_requires_text_or_stdin(capsys):
    exit_code = main(["tts", "speak"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Text is required" in captured.err


def test_tts_speak_json(monkeypatch, capsys):
    result = SpeakResult(
        completed=True, stopped_early=False, voice_identifier="v", language="en-US",
        sentence_count=1, text_length=5,
    )
    captured_kwargs = {}

    def fake_speak(text, **kwargs):
        captured_kwargs["text"] = text
        captured_kwargs.update(kwargs)
        return result

    monkeypatch.setattr(tts, "speak", fake_speak)
    exit_code = main(["tts", "speak", "hello", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload == result.to_dict()
    assert captured_kwargs["text"] == "hello"
    assert captured_kwargs["track_for_control"] is True


def test_tts_speak_no_track_flag(monkeypatch):
    captured_kwargs = {}
    monkeypatch.setattr(
        tts, "speak",
        lambda text, **kwargs: (captured_kwargs.update(kwargs) or SpeakResult(
            completed=True, stopped_early=False, voice_identifier="v", language="en-US",
            sentence_count=1, text_length=len(text),
        )),
    )
    main(["tts", "speak", "hi", "--no-track"])
    assert captured_kwargs["track_for_control"] is False


def test_tts_speak_propagates_engine_not_found(monkeypatch, capsys):
    def fake_speak(text, **kwargs):
        raise MacSpeechError(code=ErrorCode.ENGINE_NOT_FOUND, message="not found", remedy="build it")

    monkeypatch.setattr(tts, "speak", fake_speak)
    exit_code = main(["tts", "speak", "hi", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 4
    payload = json.loads(captured.out)
    assert payload["error"]["code"] == "engine_not_found"
    assert payload["error"]["remedy"] == "build it"


# --- tts save ---------------------------------------------------------------

def test_tts_save_requires_output_flag(capsys):
    exit_code = main(["tts", "save", "hi"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--output is required" in captured.err


def test_tts_save_json(monkeypatch, capsys, tmp_path):
    output_path = str(tmp_path / "out.wav")
    result = SynthesizeResult(
        output_path=output_path, format="wav", sample_rate=22050.0, channels=1,
        bit_depth=16, duration_seconds=1.5, file_size_bytes=1000, sentence_count=1,
        voice_identifier="v", language="en-US",
    )
    captured_kwargs = {}

    def fake_synthesize(text, **kwargs):
        captured_kwargs["text"] = text
        captured_kwargs.update(kwargs)
        return result

    monkeypatch.setattr(tts, "synthesize_to_file", fake_synthesize)
    exit_code = main(["tts", "save", "hello", "--output", output_path, "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == result.to_dict()
    assert captured_kwargs["output_path"] == output_path


def test_tts_save_writes_manifest_when_requested(monkeypatch, tmp_path):
    output_path = tmp_path / "out.wav"
    output_path.write_bytes(b"fake wav bytes")
    result = SynthesizeResult(
        output_path=str(output_path), format="wav", sample_rate=22050.0, channels=1,
        bit_depth=16, duration_seconds=1.5, file_size_bytes=1000, sentence_count=1,
        voice_identifier="v", language="en-US",
    )
    monkeypatch.setattr(tts, "synthesize_to_file", lambda text, **kwargs: result)
    main(["tts", "save", "hello", "--output", str(output_path), "--manifest"])
    manifest_file = output_path.with_name(output_path.name + ".manifest.json")
    assert manifest_file.exists()
    payload = json.loads(manifest_file.read_text())
    assert payload["operation"] == "tts_save"
    assert payload["input_text"] is None  # never stored by default


def test_tts_save_human_output(monkeypatch, capsys, tmp_path):
    output_path = str(tmp_path / "out.wav")
    result = SynthesizeResult(
        output_path=output_path, format="wav", sample_rate=22050.0, channels=1,
        bit_depth=16, duration_seconds=2.5, file_size_bytes=2000, sentence_count=1,
        voice_identifier="v", language="en-US",
    )
    monkeypatch.setattr(tts, "synthesize_to_file", lambda text, **kwargs: result)
    exit_code = main(["tts", "save", "hello", "--output", output_path])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert output_path in captured.out
    assert "2.50s" in captured.out


def test_tts_save_output_exists_error(monkeypatch, capsys, tmp_path):
    output_path = str(tmp_path / "out.wav")

    def fake_synthesize(text, **kwargs):
        raise MacSpeechError(code=ErrorCode.OUTPUT_EXISTS, message="already exists", remedy="use --force")

    monkeypatch.setattr(tts, "synthesize_to_file", fake_synthesize)
    exit_code = main(["tts", "save", "hello", "--output", output_path, "--json"])
    captured = capsys.readouterr()
    assert exit_code == 3
    assert json.loads(captured.out)["error"]["code"] == "output_exists"


# --- tts stop/pause/resume ---------------------------------------------------

def test_tts_stop_calls_client_and_reports_ok(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(tts, "stop", lambda: calls.append("stop"))
    exit_code = main(["tts", "stop", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == ["stop"]
    assert json.loads(captured.out) == {"status": "ok"}


def test_tts_pause_and_resume(monkeypatch):
    calls = []
    monkeypatch.setattr(tts, "pause", lambda: calls.append("pause"))
    monkeypatch.setattr(tts, "resume", lambda: calls.append("resume"))
    main(["tts", "pause"])
    main(["tts", "resume"])
    assert calls == ["pause", "resume"]


def test_tts_stop_no_running_process_error(monkeypatch, capsys):
    def fake_stop():
        raise MacSpeechError(code=ErrorCode.ENGINE_NOT_FOUND, message="no running process")

    monkeypatch.setattr(tts, "stop", fake_stop)
    exit_code = main(["tts", "stop", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 4
    assert json.loads(captured.out)["error"]["code"] == "engine_not_found"


# --- stt transcribe ----------------------------------------------------------

def test_stt_without_subcommand_is_invalid_argument(capsys):
    exit_code = main(["stt"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "subcommand is required" in captured.err


def test_stt_transcribe_text_default(monkeypatch, capsys):
    from mac_speech.stt.models import TranscribeResult

    captured_kwargs = {}

    def fake_transcribe_text(path, **kwargs):
        captured_kwargs["path"] = path
        captured_kwargs.update(kwargs)
        return TranscribeResult(engine="apple", format="text", content="Hello world.\n")

    monkeypatch.setattr(stt, "transcribe_text", fake_transcribe_text)
    exit_code = main(["stt", "transcribe", "recording.mp3"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "Hello world.\n"
    assert captured_kwargs["path"] == "recording.mp3"
    assert captured_kwargs["engine_name"] == "auto"


def test_stt_transcribe_text_json_wraps_result(monkeypatch, capsys):
    from mac_speech.stt.models import TranscribeResult

    result = TranscribeResult(engine="apple", format="text", content="Hello world.\n")
    monkeypatch.setattr(stt, "transcribe_text", lambda path, **kwargs: result)
    exit_code = main(["stt", "transcribe", "recording.mp3", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == result.to_dict()


def test_stt_transcribe_srt_word_ts(monkeypatch, capsys):
    from mac_speech.stt.models import TranscribeResult

    captured_kwargs = {}

    def fake_transcribe_srt(path, **kwargs):
        captured_kwargs.update(kwargs)
        return TranscribeResult(engine="apple", format="srt", content="1\n00:00:00,000 --> 00:00:01,000\nHi\n")

    monkeypatch.setattr(stt, "transcribe_srt", fake_transcribe_srt)
    exit_code = main(["stt", "transcribe", "recording.mp3", "--format", "srt", "--word-ts"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "00:00:00,000" in captured.out
    assert captured_kwargs["word_timestamps"] is True


def test_stt_transcribe_seg_ts_without_srt_format_is_rejected(capsys):
    exit_code = main(["stt", "transcribe", "recording.mp3", "--seg-ts"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "require --format srt" in captured.err


def test_stt_transcribe_json(monkeypatch, capsys):
    from mac_speech.stt.models import Segment, Transcript, Word

    transcript = Transcript(
        engine="apple",
        segments=[Segment(text="Hello world.", start=0.0, end=1.0, words=[Word(text="Hello", start=0.0, end=0.5)])],
    )
    monkeypatch.setattr(stt, "transcribe_json", lambda path, **kwargs: transcript)
    exit_code = main(["stt", "transcribe", "recording.mp3", "--format", "json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload == transcript.to_dict()
    assert payload["engine"] == "apple"


def test_stt_transcribe_writes_to_output_file(monkeypatch, tmp_path, capsys):
    from mac_speech.stt.models import TranscribeResult

    output_path = tmp_path / "out.txt"
    monkeypatch.setattr(
        stt, "transcribe_text", lambda path, **kwargs: TranscribeResult(engine="apple", format="text", content="Hi.\n")
    )
    exit_code = main(["stt", "transcribe", "recording.mp3", "--output", str(output_path)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert output_path.read_text() == "Hi.\n"
    assert "Saved transcript to" in captured.err


def test_stt_transcribe_refuses_to_overwrite_existing_output(monkeypatch, tmp_path, capsys):
    from mac_speech.stt.models import TranscribeResult

    output_path = tmp_path / "out.txt"
    output_path.write_text("original")
    monkeypatch.setattr(
        stt, "transcribe_text", lambda path, **kwargs: TranscribeResult(engine="apple", format="text", content="new\n")
    )
    exit_code = main(["stt", "transcribe", "recording.mp3", "--output", str(output_path), "--json"])
    captured = capsys.readouterr()
    assert exit_code == 3
    assert json.loads(captured.out)["error"]["code"] == "output_exists"
    assert output_path.read_text() == "original"


def test_stt_transcribe_force_overwrites_existing_output(monkeypatch, tmp_path):
    from mac_speech.stt.models import TranscribeResult

    output_path = tmp_path / "out.txt"
    output_path.write_text("original")
    monkeypatch.setattr(
        stt, "transcribe_text", lambda path, **kwargs: TranscribeResult(engine="apple", format="text", content="new\n")
    )
    main(["stt", "transcribe", "recording.mp3", "--output", str(output_path), "--force"])
    assert output_path.read_text() == "new\n"


def test_stt_transcribe_webvtt_format(monkeypatch, capsys):
    from mac_speech.stt.models import TranscribeResult

    monkeypatch.setattr(
        stt, "transcribe_webvtt",
        lambda path, **kwargs: TranscribeResult(engine="apple", format="webvtt", content="WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHi\n"),
    )
    exit_code = main(["stt", "transcribe", "recording.mp3", "--format", "webvtt"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.startswith("WEBVTT")


def test_stt_transcribe_writes_manifest_when_requested(monkeypatch, tmp_path):
    from mac_speech.stt.models import TranscribeResult

    output_path = tmp_path / "out.txt"
    monkeypatch.setattr(
        stt, "transcribe_text", lambda path, **kwargs: TranscribeResult(engine="apple", format="text", content="Hi.\n")
    )
    main(["stt", "transcribe", "recording.mp3", "--output", str(output_path), "--manifest"])
    manifest_file = output_path.with_name(output_path.name + ".manifest.json")
    assert manifest_file.exists()


def test_stt_transcribe_engine_not_found_error(monkeypatch, capsys):
    def fake_transcribe_text(path, **kwargs):
        raise MacSpeechError(code=ErrorCode.ENGINE_NOT_FOUND, message="no engine", remedy="install one")

    monkeypatch.setattr(stt, "transcribe_text", fake_transcribe_text)
    exit_code = main(["stt", "transcribe", "recording.mp3", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 4
    assert json.loads(captured.out)["error"]["code"] == "engine_not_found"


# --- workflow narrate ----------------------------------------------------

def test_workflow_without_subcommand_is_invalid_argument(capsys):
    exit_code = main(["workflow"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "subcommand is required" in captured.err


def test_workflow_narrate_success(monkeypatch, tmp_path, capsys):
    from mac_speech import workflow as workflow_module

    def fake_run(text, **kwargs):
        manifest = workflow_module.new_manifest(text)
        manifest.stages.append(
            workflow_module.WorkflowStage(name="synthesize", status="success", output_path="out.wav")
        )
        return manifest

    monkeypatch.setattr(workflow_module, "run_narration_pipeline", fake_run)
    exit_code = main(
        ["workflow", "narrate", "Hello.", "--output-dir", str(tmp_path), "--no-align", "--json"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert (tmp_path / "narration.workflow.json").exists()


def test_workflow_narrate_reports_failure_exit_code(monkeypatch, tmp_path):
    from mac_speech import workflow as workflow_module

    def fake_run(text, **kwargs):
        manifest = workflow_module.new_manifest(text)
        manifest.stages.append(
            workflow_module.WorkflowStage(name="synthesize", status="failed", error="no engine")
        )
        return manifest

    monkeypatch.setattr(workflow_module, "run_narration_pipeline", fake_run)
    exit_code = main(["workflow", "narrate", "Hello.", "--output-dir", str(tmp_path), "--json"])
    assert exit_code == 1
