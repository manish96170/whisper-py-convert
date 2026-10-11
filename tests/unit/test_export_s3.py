"""Unit tests for mac_speech.export.s3 (S3Exporter). Mocks
`subprocess.run` and `shutil.which` throughout — never calls a real AWS
account. See docs/export-s3.md for why live testing is deferred."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.export.base import ExportDestination
from mac_speech.export.s3 import S3Exporter


def _fake_result(stdout: str = "", stderr: str = "", returncode: int = 0) -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


def test_validate_destination_requires_s3_uri():
    exporter = S3Exporter()
    with patch("shutil.which", return_value="/usr/local/bin/aws"):
        with pytest.raises(MacSpeechError) as excinfo:
            exporter.validate_destination(ExportDestination(provider="s3", uri="not-an-s3-uri"))
    assert excinfo.value.code == ErrorCode.INVALID_ARGUMENT


def test_validate_destination_requires_aws_cli(tmp_path):
    exporter = S3Exporter()
    with patch("shutil.which", return_value=None):
        with pytest.raises(MacSpeechError) as excinfo:
            exporter.validate_destination(ExportDestination(provider="s3", uri="s3://bucket/prefix/"))
    assert excinfo.value.code == ErrorCode.ENGINE_NOT_FOUND


def test_preview_does_not_call_subprocess(tmp_path):
    source = tmp_path / "out.wav"
    source.write_bytes(b"data")
    exporter = S3Exporter()
    with patch("shutil.which", return_value="/usr/local/bin/aws"), patch.object(subprocess, "run") as run:
        preview = exporter.preview(source, ExportDestination(provider="s3", uri="s3://bucket/prefix/"))
    run.assert_not_called()
    assert preview.destination_description == "s3://bucket/prefix/out.wav"
    assert preview.will_overwrite is None


def test_upload_builds_expected_cp_command(tmp_path):
    source = tmp_path / "out.wav"
    source.write_bytes(b"data")
    exporter = S3Exporter(profile="myprofile", region="us-east-1")

    head_object_response = json.dumps({"ContentLength": len(b"data")})
    with patch("shutil.which", return_value="/usr/local/bin/aws"), patch.object(
        subprocess, "run",
        side_effect=[_fake_result(), _fake_result(stdout=head_object_response)],
    ) as run:
        result = exporter.upload(source, ExportDestination(provider="s3", uri="s3://bucket/prefix/"))

    cp_command = run.call_args_list[0].args[0]
    assert cp_command[:3] == ["aws", "s3", "cp"]
    assert str(source) in cp_command
    assert "s3://bucket/prefix/out.wav" in cp_command
    assert "--profile" in cp_command and "myprofile" in cp_command
    assert "--region" in cp_command and "us-east-1" in cp_command
    assert result.success
    assert result.verified
    assert result.remote_reference == "s3://bucket/prefix/out.wav"


def test_upload_dry_run_adds_dryrun_flag_and_skips_verify(tmp_path):
    source = tmp_path / "out.wav"
    source.write_bytes(b"data")
    exporter = S3Exporter()

    with patch("shutil.which", return_value="/usr/local/bin/aws"), patch.object(
        subprocess, "run", return_value=_fake_result()
    ) as run:
        result = exporter.upload(source, ExportDestination(provider="s3", uri="s3://bucket/prefix/"), dry_run=True)

    cp_command = run.call_args.args[0]
    assert "--dryrun" in cp_command
    assert run.call_count == 1  # no head-object verify call on dry run
    assert result.success
    assert not result.verified


def test_upload_raises_on_cp_failure(tmp_path):
    source = tmp_path / "out.wav"
    source.write_bytes(b"data")
    exporter = S3Exporter()

    with patch("shutil.which", return_value="/usr/local/bin/aws"), patch.object(
        subprocess, "run", return_value=_fake_result(stderr="AccessDenied", returncode=1)
    ):
        with pytest.raises(MacSpeechError) as excinfo:
            exporter.upload(source, ExportDestination(provider="s3", uri="s3://bucket/prefix/"))
    assert excinfo.value.code == ErrorCode.NATIVE_PROCESS_ERROR


def test_verify_returns_false_when_head_object_fails(tmp_path):
    source = tmp_path / "out.wav"
    source.write_bytes(b"data")
    exporter = S3Exporter()

    with patch("shutil.which", return_value="/usr/local/bin/aws"), patch.object(
        subprocess, "run",
        side_effect=[_fake_result(), _fake_result(returncode=1)],
    ):
        result = exporter.upload(source, ExportDestination(provider="s3", uri="s3://bucket/prefix/"))
    assert result.success  # the copy itself succeeded
    assert not result.verified  # but verification failed
