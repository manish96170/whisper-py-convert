"""Stable error codes and the base exception type for mac_speech.

Error codes are part of the public contract: scripts and coding agents may
match on ``MacSpeechError.code`` or the ``"code"`` field of JSON error
output. Do not rename or remove a code once shipped without a documented
migration note in ``docs/``.

Exit codes are a related but separate contract: multiple error codes may
share an exit code, but the mapping below must stay stable across releases
so a calling script can branch on process exit status alone, without
parsing JSON, if it chooses to.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCode(str, Enum):
    INVALID_ARGUMENT = "invalid_argument"
    INPUT_NOT_FOUND = "input_not_found"
    OUTPUT_EXISTS = "output_exists"
    ENGINE_NOT_FOUND = "engine_not_found"
    UNSUPPORTED_PLATFORM = "unsupported_platform"
    PROTOCOL_VERSION_MISMATCH = "protocol_version_mismatch"
    NATIVE_PROCESS_ERROR = "native_process_error"
    TIMEOUT = "timeout"
    NOT_IMPLEMENTED = "not_implemented"
    INTERNAL_ERROR = "internal_error"


EXIT_CODE_BY_ERROR: dict[ErrorCode, int] = {
    ErrorCode.INVALID_ARGUMENT: 2,
    ErrorCode.INPUT_NOT_FOUND: 3,
    ErrorCode.OUTPUT_EXISTS: 3,
    ErrorCode.ENGINE_NOT_FOUND: 4,
    ErrorCode.UNSUPPORTED_PLATFORM: 4,
    ErrorCode.PROTOCOL_VERSION_MISMATCH: 5,
    ErrorCode.NATIVE_PROCESS_ERROR: 6,
    ErrorCode.TIMEOUT: 124,
    ErrorCode.NOT_IMPLEMENTED: 10,
    ErrorCode.INTERNAL_ERROR: 1,
}


@dataclass
class MacSpeechError(Exception):
    """Base error for mac_speech with a stable code and an actionable remedy."""

    code: ErrorCode
    message: str
    remedy: str | None = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message

    @property
    def exit_code(self) -> int:
        return EXIT_CODE_BY_ERROR.get(self.code, 1)

    def to_dict(self) -> dict[str, str | None]:
        return {"code": self.code.value, "message": self.message, "remedy": self.remedy}
