"""Unit tests for mac_speech.doctor."""

from __future__ import annotations

from mac_speech.doctor import run_doctor


def test_doctor_report_has_core_checks():
    report = run_doctor()
    names = {c.name for c in report.checks}
    assert {"python_version", "platform", "stt", "tts"}.issubset(names)


def test_doctor_tts_missing_is_informational_not_failing():
    report = run_doctor()
    tts_check = next(c for c in report.checks if c.name == "tts")
    assert tts_check.ok is True  # must never be a failing check, built or not
    if tts_check.message == "tts: available":
        return  # Phase 2 has shipped a TTS binary on this machine; nothing more to assert.
    assert "not available yet" in tts_check.message


def test_doctor_report_to_dict_shape():
    report = run_doctor()
    as_dict = report.to_dict()
    assert set(as_dict.keys()) == {"schema_version", "platform", "ok", "checks"}
    assert isinstance(as_dict["ok"], bool)
    assert as_dict["ok"] == report.ok
