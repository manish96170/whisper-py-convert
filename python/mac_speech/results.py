"""Typed result and report models shared by capability discovery and the CLI.

These are the stable public shapes referenced by ``PLAN.md`` section 4.3
("Output schema and stable error codes"). JSON output in ``--json`` mode is
exactly ``to_dict()`` on these models — keep field names stable once shipped,
and bump ``SCHEMA_VERSION`` if a shape changes incompatibly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = 1


@dataclass
class PlatformInfo:
    os_name: str
    os_version: str
    machine: str
    python_version: str
    is_apple_silicon: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CapabilityStatus:
    name: str
    available: bool
    reason: str | None = None
    install_hint: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CapabilitiesReport:
    schema_version: int
    platform: PlatformInfo
    capabilities: list[CapabilityStatus]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "platform": self.platform.to_dict(),
            "capabilities": [c.to_dict() for c in self.capabilities],
        }


@dataclass
class DoctorCheck:
    name: str
    ok: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DoctorReport:
    schema_version: int
    platform: PlatformInfo
    checks: list[DoctorCheck]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "platform": self.platform.to_dict(),
            "ok": self.ok,
            "checks": [c.to_dict() for c in self.checks],
        }
