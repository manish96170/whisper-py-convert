"""Unit tests for mac_speech.stt.client and mac_speech.stt.models.

Mocks the engine layer; never spawns a real subprocess.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mac_speech import stt
from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.stt.models import Segment, Transcript, TranscribeResult, Word


def test_segment_to_dict_includes_words():
    segment = Segment(text="Hi.", start=0.0, end=1.0, words=[Word(text="Hi.", start=0.0, end=1.0)])
    assert segment.to_dict() == {
        "text": "Hi.",
        "start": 0.0,
        "end": 1.0,
        "words": [{"text": "Hi.", "start": 0.0, "end": 1.0}],
    }


def test_transcript_text_joins_segments():
    transcript = Transcript(
        engine="apple",
        segments=[Segment(text="First.", start=0.0, end=1.0), Segment(text="Second.", start=1.0, end=2.0)],
    )
    assert transcript.text == "First.\nSecond.\n"


def test_transcript_text_empty_when_no_segments():
    assert Transcript(engine="apple", segments=[]).text == ""


def test_transcribe_result_round_trip():
    result = TranscribeResult(engine="apple", format="text", content="Hi.\n")
    assert result.to_dict() == {"engine": "apple", "format": "text", "content": "Hi.\n"}


def test_transcribe_text_delegates_to_engine():
    with patch.object(stt.client.engine, "run_text_or_srt") as run:
        run.return_value = TranscribeResult(engine="apple", format="text", content="Hi.\n")
        result = stt.transcribe_text("r.mp3", engine_name="apple")
    assert result.content == "Hi.\n"
    run.assert_called_once_with(
        "r.mp3", output_format="text", engine="apple", model=None, language=None,
        timeout=stt.client.DEFAULT_TIMEOUT_SECONDS,
    )


def test_transcribe_srt_passes_word_timestamps():
    with patch.object(stt.client.engine, "run_text_or_srt") as run:
        run.return_value = TranscribeResult(engine="apple", format="srt", content="")
        stt.transcribe_srt("r.mp3", word_timestamps=True)
    assert run.call_args.kwargs["word_ts"] is True
    assert run.call_args.kwargs["seg_ts"] is False


def test_transcribe_srt_defaults_to_segment_timestamps():
    with patch.object(stt.client.engine, "run_text_or_srt") as run:
        run.return_value = TranscribeResult(engine="apple", format="srt", content="")
        stt.transcribe_srt("r.mp3")
    assert run.call_args.kwargs["word_ts"] is False
    assert run.call_args.kwargs["seg_ts"] is True


def test_transcribe_json_delegates_to_engine():
    transcript = Transcript(engine="apple", segments=[])
    with patch.object(stt.client.engine, "run_json", return_value=transcript) as run:
        result = stt.transcribe_json("r.mp3", engine_name="apple", model="small.en")
    assert result is transcript
    run.assert_called_once_with(
        "r.mp3", engine="apple", model="small.en", language=None, timeout=stt.client.DEFAULT_TIMEOUT_SECONDS
    )


def test_transcribe_dispatcher_text():
    with patch.object(stt.client, "transcribe_text") as transcribe_text:
        transcribe_text.return_value = "text-result"
        assert stt.transcribe("r.mp3", output_format="text") == "text-result"


def test_transcribe_dispatcher_srt():
    with patch.object(stt.client, "transcribe_srt") as transcribe_srt:
        transcribe_srt.return_value = "srt-result"
        assert stt.transcribe("r.mp3", output_format="srt", word_timestamps=True) == "srt-result"
        assert transcribe_srt.call_args.kwargs["word_timestamps"] is True


def test_transcribe_dispatcher_json():
    with patch.object(stt.client, "transcribe_json") as transcribe_json:
        transcribe_json.return_value = "json-result"
        assert stt.transcribe("r.mp3", output_format="json") == "json-result"


def test_transcribe_dispatcher_unsupported_format():
    with pytest.raises(MacSpeechError) as excinfo:
        stt.transcribe("r.mp3", output_format="xml")
    assert excinfo.value.code == ErrorCode.INVALID_ARGUMENT


def test_engine_not_found_propagates_as_mac_speech_error():
    with patch.object(stt.client.engine, "run_text_or_srt") as run:
        run.side_effect = MacSpeechError(code=ErrorCode.ENGINE_NOT_FOUND, message="missing")
        with pytest.raises(MacSpeechError) as excinfo:
            stt.transcribe_text("r.mp3")
    assert excinfo.value.code == ErrorCode.ENGINE_NOT_FOUND
