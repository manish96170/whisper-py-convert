"""Unit tests for mac_speech.errors."""

from __future__ import annotations

from mac_speech.errors import ErrorCode, MacSpeechError


def test_error_codes_are_stable_strings():
    assert ErrorCode.NOT_IMPLEMENTED.value == "not_implemented"
    assert ErrorCode.ENGINE_NOT_FOUND.value == "engine_not_found"
    assert ErrorCode.INVALID_ARGUMENT.value == "invalid_argument"


def test_exit_code_mapping_is_defined_for_every_code():
    from mac_speech.errors import EXIT_CODE_BY_ERROR

    for code in ErrorCode:
        assert code in EXIT_CODE_BY_ERROR, f"missing exit code mapping for {code}"
        assert isinstance(EXIT_CODE_BY_ERROR[code], int)
        assert EXIT_CODE_BY_ERROR[code] != 0, "no error code should map to a success exit code"


def test_mac_speech_error_to_dict_shape():
    error = MacSpeechError(code=ErrorCode.INPUT_NOT_FOUND, message="missing file", remedy="check the path")
    assert error.to_dict() == {
        "code": "input_not_found",
        "message": "missing file",
        "remedy": "check the path",
    }


def test_mac_speech_error_exit_code_matches_mapping():
    error = MacSpeechError(code=ErrorCode.TIMEOUT, message="too slow")
    assert error.exit_code == 124


def test_mac_speech_error_str_is_message():
    error = MacSpeechError(code=ErrorCode.INTERNAL_ERROR, message="boom")
    assert str(error) == "boom"
