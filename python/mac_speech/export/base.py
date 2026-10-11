"""Common exporter contract (PLAN.md Phase 8).

Every exporter (local copy, Google Drive, S3, Slack) implements this
same small interface: validate a destination, preview what would
happen, upload with optional dry-run, and report a verifiable result —
never credentials. Local files remain the source of truth; no exporter
deletes or modifies the local artifact.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ExportDestination:
    provider: str  # "local" | "gdrive" | "s3" | "slack"
    uri: str  # provider-specific: a path, "folder-id", "s3://bucket/prefix/", "#channel"
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportPreview:
    provider: str
    source_path: str
    destination_description: str
    estimated_size_bytes: int
    will_overwrite: bool | None  # None when unknown without a network call

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "source_path": self.source_path,
            "destination_description": self.destination_description,
            "estimated_size_bytes": self.estimated_size_bytes,
            "will_overwrite": self.will_overwrite,
        }


@dataclass
class ExportResult:
    provider: str
    source_path: str
    destination_description: str
    success: bool
    verified: bool
    remote_reference: str | None = None  # file ID, S3 key+version, Slack message ts, etc.
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "source_path": self.source_path,
            "destination_description": self.destination_description,
            "success": self.success,
            "verified": self.verified,
            "remote_reference": self.remote_reference,
            "message": self.message,
        }


class Exporter(ABC):
    """Base class for all exporters. Implementations must never log or
    persist credentials, must never enable public sharing by default,
    and must leave the local artifact untouched regardless of outcome."""

    provider: str

    @abstractmethod
    def validate_destination(self, destination: ExportDestination) -> None:
        """Raises `MacSpeechError` if the destination is malformed or the
        exporter is not usable right now (e.g. missing optional
        dependency, missing credentials) — never a network call."""

    @abstractmethod
    def preview(self, source_path: Path, destination: ExportDestination) -> ExportPreview:
        """Describes what `upload()` would do, without side effects."""

    @abstractmethod
    def upload(self, source_path: Path, destination: ExportDestination, *, dry_run: bool = False) -> ExportResult:
        """Uploads `source_path` to `destination`. When `dry_run=True`,
        performs validation and returns a result with `success=True,
        verified=False` without actually transferring anything."""
