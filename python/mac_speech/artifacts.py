"""Artifact manifests and collision-safe naming (PLAN.md Phase 7).

A manifest is an optional JSON sidecar (`<artifact>.manifest.json`)
describing a generated audio or transcript file: schema version,
creation time, operation, engine, checksum, and provenance. Manifests
are opt-in (`--manifest` on the relevant CLI commands) — PLAN.md
describes them as something to "optionally create," not a mandatory
side effect of every command.

Privacy rule (PLAN.md section 5.2): never store full source text by
default. `input_text_sha256` is always included; the actual text is
only included if the caller explicitly opts in.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .file_io import atomic_write_text

MANIFEST_SCHEMA_VERSION = 1


@dataclass
class Manifest:
    schema_version: int
    artifact_id: str
    created_at: str  # UTC, ISO 8601
    operation: str  # "tts_save" | "stt_transcribe" | ...
    engine: str | None
    output_path: str
    media_type: str | None
    file_size_bytes: int
    checksum_sha256: str
    voice_identifier: str | None = None
    language: str | None = None
    input_text_sha256: str | None = None
    input_text: str | None = None  # only present if the caller opted in
    extra: dict[str, Any] = field(default_factory=dict)
    export_destinations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_manifest(
    output_path: Path,
    *,
    operation: str,
    engine: str | None = None,
    voice_identifier: str | None = None,
    language: str | None = None,
    input_text: str | None = None,
    store_text: bool = False,
    extra: dict[str, Any] | None = None,
) -> Manifest:
    """Builds a manifest describing an existing artifact file at
    `output_path`. The file must already exist (manifests are written
    after an artifact is finalized, never before)."""
    size = output_path.stat().st_size
    media_type, _ = mimetypes.guess_type(str(output_path))
    artifact_id = _sha256_text(f"{output_path}:{time.time_ns()}")[:16]

    return Manifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        artifact_id=artifact_id,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        operation=operation,
        engine=engine,
        output_path=str(output_path),
        media_type=media_type,
        file_size_bytes=size,
        checksum_sha256=_sha256_file(output_path),
        voice_identifier=voice_identifier,
        language=language,
        input_text_sha256=_sha256_text(input_text) if input_text is not None else None,
        input_text=input_text if (store_text and input_text is not None) else None,
        extra=extra or {},
    )


def manifest_path_for(output_path: Path) -> Path:
    return output_path.with_name(output_path.name + ".manifest.json")


def write_manifest(manifest: Manifest, output_path: Path, *, force: bool = False) -> Path:
    """Writes the manifest JSON sidecar next to `output_path`, atomically
    (write to a temp file, then rename)."""
    target = manifest_path_for(output_path)
    return atomic_write_text(target, json.dumps(manifest.to_dict(), indent=2) + "\n", force=force)


def read_manifest(manifest_file: Path) -> dict[str, Any]:
    return json.loads(manifest_file.read_text(encoding="utf-8"))


# --- Collision-safe default naming -----------------------------------------

_UNSAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")


def suggest_artifact_path(directory: Path, *, prefix: str, extension: str) -> Path:
    """Suggests a collision-safe default path for an auto-named artifact
    (used only when the caller does not specify an explicit --output;
    explicit paths keep the existing explicit-error-unless-force
    behavior documented in docs/tts-engine.md and docs/installation.md).

    Format: ``<prefix>-<UTC timestamp>-<counter>.<extension>``, where the
    counter increments only if the timestamp-based name collides within
    the same second — this stays deterministic for a human reading
    directory listings while still being collision-safe.
    """
    directory.mkdir(parents=True, exist_ok=True)
    safe_prefix = _UNSAFE_CHARS_RE.sub("-", prefix).strip("-") or "artifact"
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    candidate = directory / f"{safe_prefix}-{timestamp}.{extension}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{safe_prefix}-{timestamp}-{counter}.{extension}"
        counter += 1
    return candidate
