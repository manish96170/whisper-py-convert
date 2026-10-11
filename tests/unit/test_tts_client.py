"""Unit tests for mac_speech.tts.client and mac_speech.tts.models.

Mocks the engine layer; never spawns a real subprocess.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mac_speech import tts
from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.tts.models import SpeakResult, SynthesizeResult, Voice


def test_voice_round_trip():
    payload = {
        "identifier": "id", "name": "Name", "language": "en-US", "quality": "default",
        "gender": "female", "is_personal_voice": False, "is_novelty_voice": False,
    }
    voice = Voice.from_dict(payload)
    assert voice.to_dict() == payload


def test_speak_result_round_trip():
    payload = {
        "completed": True, "stopped_early": False, "voice_identifier": "v",
        "language": "en-US", "sentence_count": 2, "text_length": 10,
    }
    result = SpeakResult.from_dict(payload)
    assert result.to_dict() == payload


def test_synthesize_result_round_trip():
    payload = {
        "output_path": "/tmp/out.wav", "format": "wav", "sample_rate": 22050.0,
        "channels": 1, "bit_depth": 16, "duration_seconds": 1.0, "file_size_bytes": 100,
        "sentence_count": 1, "voice_identifier": "v", "language": "en-US",
    }
    result = SynthesizeResult.from_dict(payload)
    assert result.to_dict() == payload


def test_list_voices_wraps_engine_result():
    with patch.object(tts.client.engine, "run_operation") as run_operation:
        run_operation.return_value = {
            "voices": [
                {
                    "identifier": "id-1", "name": "N", "language": "en-US", "quality": "default",
                    "gender": "unspecified", "is_personal_voice": False, "is_novelty_voice": False,
                }
            ],
            "count": 1,
        }
        voices = tts.list_voices(language="en-US")
    assert len(voices) == 1
    assert isinstance(voices[0], Voice)
    assert voices[0].identifier == "id-1"
    run_operation.assert_called_once_with("voices", language="en-US", timeout=tts.client.DEFAULT_TIMEOUT_SECONDS)


def test_personal_voice_status_delegates_to_engine():
    with patch.object(tts.client.engine, "run_operation") as run_operation:
        run_operation.return_value = {"authorization_status": "authorized"}
        status = tts.personal_voice_status()
    assert status == "authorized"
    run_operation.assert_called_once_with(
        "personal-voice-status", timeout=tts.client.DEFAULT_TIMEOUT_SECONDS
    )


def test_personal_voice_status_defaults_to_unknown_when_missing_field():
    with patch.object(tts.client.engine, "run_operation", return_value={}):
        assert tts.personal_voice_status() == "unknown"


def test_speak_defaults_to_tracking_for_control():
    with patch.object(tts.client.engine, "run_operation") as run_operation:
        run_operation.return_value = {
            "completed": True, "stopped_early": False, "voice_identifier": "v",
            "language": "en-US", "sentence_count": 1, "text_length": 5,
        }
        result = tts.speak("hello")
    assert isinstance(result, SpeakResult)
    assert run_operation.call_args.kwargs["track_pid"] is True


def test_speak_no_track_for_control():
    with patch.object(tts.client.engine, "run_operation") as run_operation:
        run_operation.return_value = {
            "completed": True, "stopped_early": False, "voice_identifier": "v",
            "language": "en-US", "sentence_count": 1, "text_length": 5,
        }
        tts.speak("hello", track_for_control=False)
    assert run_operation.call_args.kwargs["track_pid"] is False


def test_synthesize_to_file_passes_through_arguments():
    with patch.object(tts.client.engine, "run_operation") as run_operation:
        run_operation.return_value = {
            "output_path": "/tmp/out.aiff", "format": "aiff", "sample_rate": 22050.0,
            "channels": 1, "bit_depth": 16, "duration_seconds": 1.0, "file_size_bytes": 10,
            "sentence_count": 1, "voice_identifier": "v", "language": "en-US",
        }
        result = tts.synthesize_to_file(
            "hello", output_path="/tmp/out.aiff", format="aiff", voice="v1", force=True
        )
    assert isinstance(result, SynthesizeResult)
    assert run_operation.call_args.kwargs["output_path"] == "/tmp/out.aiff"
    assert run_operation.call_args.kwargs["format"] == "aiff"
    assert run_operation.call_args.kwargs["voice"] == "v1"
    assert run_operation.call_args.kwargs["force"] is True


def test_stop_pause_resume_send_expected_signals():
    import signal

    with patch.object(tts.client.engine, "send_control_signal") as send_control_signal:
        tts.stop()
        tts.pause()
        tts.resume()

    assert send_control_signal.call_args_list == [
        ((signal.SIGTERM,),),
        ((signal.SIGTSTP,),),
        ((signal.SIGCONT,),),
    ]


def test_engine_not_found_propagates_as_mac_speech_error():
    with patch.object(tts.client.engine, "run_operation") as run_operation:
        run_operation.side_effect = MacSpeechError(code=ErrorCode.ENGINE_NOT_FOUND, message="missing")
        with pytest.raises(MacSpeechError) as excinfo:
            tts.speak("hello")
    assert excinfo.value.code == ErrorCode.ENGINE_NOT_FOUND
