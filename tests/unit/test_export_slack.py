"""Unit tests for mac_speech.export.slack (SlackExporter). Mocks
`subprocess.run` throughout — never invokes the real `team-slack-bridge`
CLI or posts to a real Slack workspace. See docs/export-slack.md for
what *was* verified live (a real `--dry-run` call) during Phase 10
discovery."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.export.base import ExportDestination
from mac_speech.export.slack import SlackExporter


def _fake_result(stdout: str = "", stderr: str = "", returncode: int = 0) -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


def _make_bridge_checkout(tmp_path):
    cli_dir = tmp_path / "cli"
    cli_dir.mkdir()
    (cli_dir / "post.js").write_text("// stub\n")
    (cli_dir / "dm.js").write_text("// stub\n")
    return tmp_path


def test_validate_destination_requires_bridge_path():
    exporter = SlackExporter(bridge_path=None)
    with pytest.raises(MacSpeechError) as excinfo:
        exporter.validate_destination(ExportDestination(provider="slack", uri="#channel"))
    assert excinfo.value.code == ErrorCode.ENGINE_NOT_FOUND


def test_validate_destination_requires_cli_scripts_present(tmp_path):
    exporter = SlackExporter(bridge_path=str(tmp_path))  # no cli/ dir created
    with pytest.raises(MacSpeechError) as excinfo:
        exporter.validate_destination(ExportDestination(provider="slack", uri="#channel"))
    assert excinfo.value.code == ErrorCode.ENGINE_NOT_FOUND


def test_validate_destination_requires_uri(tmp_path):
    bridge_root = _make_bridge_checkout(tmp_path)
    exporter = SlackExporter(bridge_path=str(bridge_root))
    with patch("shutil.which", return_value="/usr/local/bin/node"):
        with pytest.raises(MacSpeechError) as excinfo:
            exporter.validate_destination(ExportDestination(provider="slack", uri=""))
    assert excinfo.value.code == ErrorCode.INVALID_ARGUMENT


def test_upload_posts_to_channel_by_default(tmp_path):
    bridge_root = _make_bridge_checkout(tmp_path)
    source = tmp_path / "narration.wav"
    source.write_bytes(b"data")
    exporter = SlackExporter(bridge_path=str(bridge_root))

    response = json.dumps({"ok": True, "channel": "C123", "ts": "1699999999.000100"})
    with patch("shutil.which", return_value="/usr/local/bin/node"), patch.object(
        subprocess, "run", return_value=_fake_result(stdout=response)
    ) as run:
        result = exporter.upload(source, ExportDestination(provider="slack", uri="#deploys"))

    command = run.call_args.args[0]
    assert str(bridge_root / "cli" / "post.js") in command
    assert "--channel" in command and "#deploys" in command
    assert "--text" in command
    assert result.success
    assert result.verified
    assert result.remote_reference == "1699999999.000100"


def test_upload_as_dm_uses_dm_script(tmp_path):
    bridge_root = _make_bridge_checkout(tmp_path)
    source = tmp_path / "narration.wav"
    source.write_bytes(b"data")
    exporter = SlackExporter(bridge_path=str(bridge_root))

    response = json.dumps({"ok": True, "ts": "123.456"})
    with patch("shutil.which", return_value="/usr/local/bin/node"), patch.object(
        subprocess, "run", return_value=_fake_result(stdout=response)
    ) as run:
        exporter.upload(
            source, ExportDestination(provider="slack", uri="U0123ABC", options={"as_dm": True})
        )

    command = run.call_args.args[0]
    assert str(bridge_root / "cli" / "dm.js") in command
    assert "--user" in command and "U0123ABC" in command


def test_upload_dry_run_adds_flag_and_reports_unverified(tmp_path):
    bridge_root = _make_bridge_checkout(tmp_path)
    source = tmp_path / "narration.wav"
    source.write_bytes(b"data")
    exporter = SlackExporter(bridge_path=str(bridge_root))

    response = json.dumps({"ok": True, "dryRun": True, "request": {"method": "chat.postMessage"}})
    with patch("shutil.which", return_value="/usr/local/bin/node"), patch.object(
        subprocess, "run", return_value=_fake_result(stdout=response)
    ) as run:
        result = exporter.upload(
            source, ExportDestination(provider="slack", uri="#deploys"), dry_run=True
        )

    assert "--dry-run" in run.call_args.args[0]
    assert result.success
    assert not result.verified


def test_upload_includes_idempotency_key_when_provided(tmp_path):
    bridge_root = _make_bridge_checkout(tmp_path)
    source = tmp_path / "narration.wav"
    source.write_bytes(b"data")
    exporter = SlackExporter(bridge_path=str(bridge_root))

    response = json.dumps({"ok": True, "ts": "1.1"})
    with patch("shutil.which", return_value="/usr/local/bin/node"), patch.object(
        subprocess, "run", return_value=_fake_result(stdout=response)
    ) as run:
        exporter.upload(
            source,
            ExportDestination(provider="slack", uri="#deploys", options={"idempotency_key": "abc123"}),
        )

    command = run.call_args.args[0]
    assert "--idempotency-key" in command and "abc123" in command


def test_upload_raises_on_bridge_failure_response(tmp_path):
    bridge_root = _make_bridge_checkout(tmp_path)
    source = tmp_path / "narration.wav"
    source.write_bytes(b"data")
    exporter = SlackExporter(bridge_path=str(bridge_root))

    response = json.dumps({"ok": False, "error": "channel-required", "retryable": False})
    with patch("shutil.which", return_value="/usr/local/bin/node"), patch.object(
        subprocess, "run", return_value=_fake_result(stdout=response)
    ):
        with pytest.raises(MacSpeechError) as excinfo:
            exporter.upload(source, ExportDestination(provider="slack", uri="#deploys"))
    assert excinfo.value.code == ErrorCode.NATIVE_PROCESS_ERROR


def test_summary_text_includes_link_when_provided(tmp_path):
    bridge_root = _make_bridge_checkout(tmp_path)
    source = tmp_path / "narration.wav"
    exporter = SlackExporter(bridge_path=str(bridge_root))
    destination = ExportDestination(provider="slack", uri="#deploys", options={"link": "https://example.com/x"})
    text = exporter._summary_text(source, destination)
    assert "https://example.com/x" in text
    assert "narration.wav" in text
