"""Local-copy exporter: the trivial case, and the one that exercises the
`Exporter` contract without any network/cloud dependency. Useful on its
own (e.g. exporting to an external drive or a synced folder) and as a
reference implementation for the contract.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ..errors import ErrorCode, MacSpeechError
from .base import ExportDestination, ExportPreview, ExportResult, Exporter


class LocalExporter(Exporter):
    provider = "local"

    def validate_destination(self, destination: ExportDestination) -> None:
        if destination.provider != self.provider:
            raise MacSpeechError(
                code=ErrorCode.INVALID_ARGUMENT,
                message=f"LocalExporter cannot handle provider '{destination.provider}'.",
            )
        if not destination.uri:
            raise MacSpeechError(code=ErrorCode.INVALID_ARGUMENT, message="Local destination URI (path) is required.")

    def preview(self, source_path: Path, destination: ExportDestination) -> ExportPreview:
        self.validate_destination(destination)
        target = Path(destination.uri)
        if target.is_dir():
            target = target / source_path.name
        return ExportPreview(
            provider=self.provider,
            source_path=str(source_path),
            destination_description=str(target),
            estimated_size_bytes=source_path.stat().st_size if source_path.exists() else 0,
            will_overwrite=target.exists(),
        )

    def upload(self, source_path: Path, destination: ExportDestination, *, dry_run: bool = False) -> ExportResult:
        self.validate_destination(destination)
        target = Path(destination.uri)
        if target.is_dir():
            target = target / source_path.name

        if dry_run:
            return ExportResult(
                provider=self.provider,
                source_path=str(source_path),
                destination_description=str(target),
                success=True,
                verified=False,
                message="dry run; nothing copied",
            )

        force = bool(destination.options.get("force"))
        if target.exists() and not force:
            raise MacSpeechError(
                code=ErrorCode.OUTPUT_EXISTS,
                message=f"Export destination already exists: {target}",
                remedy="Pass force=True in the destination options to overwrite.",
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + ".mac-speech-export.tmp")
        shutil.copyfile(source_path, temp)
        temp.replace(target)

        verified = target.exists() and target.stat().st_size == source_path.stat().st_size
        return ExportResult(
            provider=self.provider,
            source_path=str(source_path),
            destination_description=str(target),
            success=True,
            verified=verified,
            remote_reference=str(target),
        )
