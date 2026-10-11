"""Unit tests for mac_speech.stt.webvtt (SRT -> WebVTT conversion)."""

from __future__ import annotations

from mac_speech.stt.webvtt import srt_to_webvtt


def test_srt_to_webvtt_basic_conversion():
    srt = "1\n00:00:00,000 --> 00:00:02,460\nThis is a local transcription test.\n"
    vtt = srt_to_webvtt(srt)

    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:00.000 --> 00:00:02.460" in vtt
    assert "This is a local transcription test." in vtt
    assert "," not in vtt.split("\n\n", 1)[1]  # no SRT-style comma separators remain


def test_srt_to_webvtt_multiple_cues_preserve_order():
    srt = (
        "1\n00:00:00,000 --> 00:00:00,300\nThis\n"
        "\n"
        "2\n00:00:00,300 --> 00:00:00,540\nis\n"
    )
    vtt = srt_to_webvtt(srt)
    this_index = vtt.index("This")
    is_index = vtt.index("is", this_index + 1)
    assert this_index < is_index


def test_srt_to_webvtt_empty_input_still_has_header():
    assert srt_to_webvtt("").strip() == "WEBVTT"
