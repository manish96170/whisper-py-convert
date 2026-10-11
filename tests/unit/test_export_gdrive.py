"""Unit tests for mac_speech.export.gdrive (GoogleDriveExporter). Mocks
the optional `google-api-python-client`/`google-auth-oauthlib` layer
throughout — never calls a real Google account. These optional
dependencies are not installed in the base dev environment, so most
tests simulate their absence (the real-world default) and confirm a
clean, actionable error rather than a crash.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.export.base import ExportDestination
from mac_speech.export.gdrive import GoogleDriveExporter


def test_validate_destination_requires_uri():
    exporter = GoogleDriveExporter(client_secrets_path="/tmp/does-not-matter.json")
    with pytest.raises(MacSpeechError) as excinfo:
        exporter.validate_destination(ExportDestination(provider="gdrive", uri=""))
    assert excinfo.value.code == ErrorCode.INVALID_ARGUMENT


def test_validate_destination_reports_missing_optional_dependency():
    """In the base dev environment (no `mac-speech[gdrive]` extra
    installed), this must fail with a clear ENGINE_NOT_FOUND + remedy,
    not an ImportError traceback."""
    exporter = GoogleDriveExporter(client_secrets_path="/tmp/does-not-matter.json")
    with pytest.raises(MacSpeechError) as excinfo:
        exporter.validate_destination(ExportDestination(provider="gdrive", uri="folder-id"))
    # Either the dependency is genuinely missing (ENGINE_NOT_FOUND) or,
    # if it happens to be installed in this environment, the client
    # secrets file check fails first (also ENGINE_NOT_FOUND) — both are
    # the same error code and both have a remedy.
    assert excinfo.value.code == ErrorCode.ENGINE_NOT_FOUND
    assert excinfo.value.remedy


def test_validate_destination_requires_client_secrets_file(tmp_path):
    exporter = GoogleDriveExporter(client_secrets_path=str(tmp_path / "missing.json"))
    with patch.object(exporter, "_require_optional_dependency", return_value=None):
        with pytest.raises(MacSpeechError) as excinfo:
            exporter.validate_destination(ExportDestination(provider="gdrive", uri="folder-id"))
    assert excinfo.value.code == ErrorCode.ENGINE_NOT_FOUND
    assert "client_secret" in excinfo.value.remedy.lower()


def test_preview_does_not_require_network(tmp_path):
    secrets = tmp_path / "client_secret.json"
    secrets.write_text("{}")
    source = tmp_path / "out.wav"
    source.write_bytes(b"data")

    exporter = GoogleDriveExporter(client_secrets_path=str(secrets))
    with patch.object(exporter, "_require_optional_dependency", return_value=None):
        preview = exporter.preview(source, ExportDestination(provider="gdrive", uri="folder-id"))

    assert preview.provider == "gdrive"
    assert preview.will_overwrite is None
    assert preview.estimated_size_bytes == len(b"data")


def test_upload_dry_run_skips_credentials_and_network(tmp_path):
    secrets = tmp_path / "client_secret.json"
    secrets.write_text("{}")
    source = tmp_path / "out.wav"
    source.write_bytes(b"data")

    exporter = GoogleDriveExporter(client_secrets_path=str(secrets))
    with patch.object(exporter, "_require_optional_dependency", return_value=None), patch.object(
        exporter, "_get_credentials"
    ) as get_credentials:
        result = exporter.upload(source, ExportDestination(provider="gdrive", uri="folder-id"), dry_run=True)

    get_credentials.assert_not_called()
    assert result.success
    assert not result.verified


def test_upload_builds_expected_request_with_mocked_api(tmp_path):
    secrets = tmp_path / "client_secret.json"
    secrets.write_text("{}")
    source = tmp_path / "out.wav"
    source.write_bytes(b"data")

    exporter = GoogleDriveExporter(client_secrets_path=str(secrets))

    class FakeRequest:
        def next_chunk(self):
            return None, {"id": "file123", "size": str(len(b"data"))}

    class FakeFiles:
        def create(self, **kwargs):
            return FakeRequest()

    class FakeService:
        def files(self):
            return FakeFiles()

    fake_discovery_module = type(sys)("googleapiclient.discovery")
    fake_discovery_module.build = lambda *a, **k: FakeService()
    fake_http_module = type(sys)("googleapiclient.http")
    fake_http_module.MediaFileUpload = lambda *a, **k: "fake-media"
    fake_googleapiclient_module = type(sys)("googleapiclient")

    with patch.object(exporter, "_require_optional_dependency", return_value=None), patch.object(
        exporter, "_get_credentials", return_value="fake-creds"
    ), patch.dict(
        sys.modules,
        {
            "googleapiclient": fake_googleapiclient_module,
            "googleapiclient.discovery": fake_discovery_module,
            "googleapiclient.http": fake_http_module,
        },
    ):
        result = exporter.upload(source, ExportDestination(provider="gdrive", uri="folder-id"))

    assert result.success
    assert result.verified
    assert result.remote_reference == "file123"
