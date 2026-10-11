"""Unit tests for mac_speech.export.local (LocalExporter) and the
Exporter contract/registry."""

from __future__ import annotations

import pytest

from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.export import ExportDestination, LocalExporter, get_exporter


def test_get_exporter_returns_local_exporter():
    exporter = get_exporter("local")
    assert isinstance(exporter, LocalExporter)


def test_get_exporter_unknown_provider_raises():
    with pytest.raises(MacSpeechError) as excinfo:
        get_exporter("dropbox")
    assert excinfo.value.code == ErrorCode.INVALID_ARGUMENT


def test_local_exporter_copies_file(tmp_path):
    source = tmp_path / "source.wav"
    source.write_bytes(b"audio bytes")
    dest_dir = tmp_path / "exports"
    dest_dir.mkdir()

    exporter = LocalExporter()
    destination = ExportDestination(provider="local", uri=str(dest_dir))
    result = exporter.upload(source, destination)

    assert result.success
    assert result.verified
    target = dest_dir / "source.wav"
    assert target.read_bytes() == b"audio bytes"
    assert result.remote_reference == str(target)


def test_local_exporter_refuses_to_overwrite_by_default(tmp_path):
    source = tmp_path / "source.wav"
    source.write_bytes(b"new")
    target = tmp_path / "existing.wav"
    target.write_bytes(b"old")

    exporter = LocalExporter()
    destination = ExportDestination(provider="local", uri=str(target))
    with pytest.raises(MacSpeechError) as excinfo:
        exporter.upload(source, destination)
    assert excinfo.value.code == ErrorCode.OUTPUT_EXISTS
    assert target.read_bytes() == b"old"


def test_local_exporter_force_overwrites(tmp_path):
    source = tmp_path / "source.wav"
    source.write_bytes(b"new")
    target = tmp_path / "existing.wav"
    target.write_bytes(b"old")

    exporter = LocalExporter()
    destination = ExportDestination(provider="local", uri=str(target), options={"force": True})
    result = exporter.upload(source, destination)
    assert result.success
    assert target.read_bytes() == b"new"


def test_local_exporter_dry_run_does_not_copy(tmp_path):
    source = tmp_path / "source.wav"
    source.write_bytes(b"data")
    target = tmp_path / "out.wav"

    exporter = LocalExporter()
    destination = ExportDestination(provider="local", uri=str(target))
    result = exporter.upload(source, destination, dry_run=True)

    assert result.success
    assert not result.verified
    assert not target.exists()


def test_local_exporter_preview_reports_overwrite(tmp_path):
    source = tmp_path / "source.wav"
    source.write_bytes(b"data")
    target = tmp_path / "existing.wav"
    target.write_bytes(b"old")

    exporter = LocalExporter()
    destination = ExportDestination(provider="local", uri=str(target))
    preview = exporter.preview(source, destination)
    assert preview.will_overwrite is True
    assert preview.estimated_size_bytes == len(b"data")


def test_local_exporter_rejects_mismatched_provider(tmp_path):
    exporter = LocalExporter()
    destination = ExportDestination(provider="s3", uri="s3://bucket/key")
    with pytest.raises(MacSpeechError) as excinfo:
        exporter.validate_destination(destination)
    assert excinfo.value.code == ErrorCode.INVALID_ARGUMENT
