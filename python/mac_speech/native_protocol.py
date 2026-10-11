"""Versioned JSON protocol for one-shot native engine subprocesses.

This governs *new* engines built against this contract: the Phase 2 TTS
engine, and any future STT adapter rewrite. It does not change the existing
``whisper-py-convert-apple`` / ``whisper-py-convert-windows.exe`` JSON shape,
which predates this contract and is preserved exactly as-is per
``docs/decisions/ADR-001-repository-and-module-boundaries.md`` and
``PLAN.md``'s "do not rewrite functioning STT code" rule.

Contract summary (see ``docs/protocol.md`` for the full writeup):

* JSON request transports carry exactly one JSON object each way for
  one-shot commands (``PLAN.md`` section 3.3). The current TTS engine uses
  CLI arguments/raw text on stdin, but implements this response shape.
  Diagnostics and progress go to stderr only; stdout must stay parseable.
* ``protocol_version`` is a required integer field on both the request and
  the response. A native engine that receives a ``protocol_version`` with a
  different value than it implements must fail fast with
  ``PROTOCOL_VERSION_MISMATCH`` rather than guess at compatibility.
* Exit codes: 0 success; non-zero matches ``errors.EXIT_CODE_BY_ERROR`` for
  the error code reported in the response's ``error.code`` field.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PROTOCOL_VERSION = 1


@dataclass
class NativeRequest:
    operation: str
    payload: dict[str, Any] = field(default_factory=dict)
    protocol_version: int = PROTOCOL_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NativeResponse:
    status: str  # "ok" or "error"
    protocol_version: int = PROTOCOL_VERSION
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NativeResponse":
        if "protocol_version" not in payload:
            raise ProtocolVersionError(
                "Native engine response is missing required protocol_version."
            )
        version = _require_integer_version(payload["protocol_version"])
        return cls(
            status=payload.get("status", "error"),
            protocol_version=version,
            result=payload.get("result"),
            error=payload.get("error"),
        )


class ProtocolVersionError(Exception):
    """Raised when a native response's protocol version is absent, invalid or incompatible."""


def _require_integer_version(version: Any) -> int:
    # bool is a subclass of int in Python, but is not a JSON integer.
    # Do not coerce strings or truncate floats to a supported version.
    if type(version) is not int:
        raise ProtocolVersionError(
            "Native engine protocol_version must be an integer "
            f"(received {type(version).__name__})."
        )
    return version


def check_protocol_version(
    response: NativeResponse, *, expected: int = PROTOCOL_VERSION
) -> None:
    version = _require_integer_version(response.protocol_version)
    if version != expected:
        raise ProtocolVersionError(
            f"Native engine protocol version {version} is incompatible "
            f"with wrapper protocol version {expected}."
        )
