"""Unit tests for mac_speech.align."""

from __future__ import annotations

from unittest.mock import patch

from mac_speech import align
from mac_speech.stt.models import Segment, Transcript


def test_align_via_stt_roundtrip_delegates_to_stt_json():
    transcript = Transcript(engine="apple", segments=[Segment(text="Hello.", start=0.0, end=1.0)])
    with patch.object(align, "transcribe_json", return_value=transcript) as transcribe_json:
        result = align.align_via_stt_roundtrip("narration.wav", language="en-US")
    assert result is transcript
    transcribe_json.assert_called_once_with("narration.wav", engine_name="auto", language="en-US")
