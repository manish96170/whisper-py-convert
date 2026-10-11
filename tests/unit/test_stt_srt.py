"""Unit tests for mac_speech.stt.srt (Transcript -> SRT rendering)."""

from __future__ import annotations

from mac_speech.stt.models import Segment, Transcript, Word
from mac_speech.stt.srt import transcript_to_srt


def test_segment_level_srt():
    transcript = Transcript(engine="apple", segments=[Segment(text="Hello world.", start=0.0, end=1.5)])
    srt = transcript_to_srt(transcript, word_timestamps=False)
    assert srt == "1\n00:00:00,000 --> 00:00:01,500\nHello world.\n"


def test_word_level_srt_uses_words_not_segment_text():
    transcript = Transcript(
        engine="apple",
        segments=[
            Segment(
                text="Hello world.",
                start=0.0,
                end=1.0,
                words=[Word(text="Hello", start=0.0, end=0.5), Word(text="world.", start=0.5, end=1.0)],
            )
        ],
    )
    srt = transcript_to_srt(transcript, word_timestamps=True)
    assert "1\n00:00:00,000 --> 00:00:00,500\nHello\n" in srt
    assert "2\n00:00:00,500 --> 00:00:01,000\nworld.\n" in srt


def test_word_level_without_words_falls_back_to_segment_text():
    transcript = Transcript(engine="windows", segments=[Segment(text="No timing here.", start=0.0, end=0.0)])
    srt = transcript_to_srt(transcript, word_timestamps=True)
    assert "No timing here." in srt


def test_empty_transcript_produces_empty_srt():
    assert transcript_to_srt(Transcript(engine="apple", segments=[])) == ""
