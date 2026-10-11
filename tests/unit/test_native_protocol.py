"""Unit tests for mac_speech.native_protocol."""

from __future__ import annotations

import pytest

from mac_speech.native_protocol import (
    PROTOCOL_VERSION,
    NativeRequest,
    NativeResponse,
    ProtocolVersionError,
    check_protocol_version,
)


def test_native_request_round_trip():
    request = NativeRequest(operation="speak", payload={"text": "hello"})
    assert request.to_dict() == {
        "operation": "speak",
        "payload": {"text": "hello"},
        "protocol_version": PROTOCOL_VERSION,
    }


def test_native_response_from_dict_round_trip():
    payload = {
        "status": "ok",
        "protocol_version": PROTOCOL_VERSION,
        "result": {"duration": 1.5},
        "error": None,
    }
    response = NativeResponse.from_dict(payload)
    assert response.status == "ok"
    assert response.protocol_version == PROTOCOL_VERSION
    assert response.result == {"duration": 1.5}
    assert response.to_dict() == payload


def test_check_protocol_version_accepts_matching_version():
    response = NativeResponse(status="ok", protocol_version=PROTOCOL_VERSION)
    check_protocol_version(response)  # must not raise


def test_check_protocol_version_rejects_mismatch():
    response = NativeResponse(status="ok", protocol_version=PROTOCOL_VERSION + 1)
    with pytest.raises(ProtocolVersionError):
        check_protocol_version(response)


def test_native_response_requires_version():
    with pytest.raises(ProtocolVersionError, match="missing required protocol_version"):
        NativeResponse.from_dict({"status": "ok", "result": {}})


@pytest.mark.parametrize(
    "version", [None, "1", "invalid", "", 1.0, 1.9, True, False, [], {}]
)
def test_native_response_rejects_non_integer_version(version):
    with pytest.raises(ProtocolVersionError, match="must be an integer"):
        NativeResponse.from_dict({"status": "ok", "protocol_version": version})


@pytest.mark.parametrize("version", [None, "1", 1.0, True])
def test_check_protocol_version_rejects_non_integer_version(version):
    response = NativeResponse(status="ok", protocol_version=version)
    with pytest.raises(ProtocolVersionError, match="must be an integer"):
        check_protocol_version(response)
