"""Slack export via the `team-slack-bridge` CLI (PLAN.md Phase 10).

This never duplicates `team-slack-bridge`'s own Slack authentication or
posting logic — it shells out to its documented, versioned CLI contract
(`node cli/post.js` / `node cli/dm.js`, both supporting `--dry-run` and
`--json`), inspected and verified live during Phase 10 against a real,
configured install at the path a user points `bridge_path`/
`MAC_SPEECH_SLACK_BRIDGE_PATH` to (confirmed working via a real
`--dry-run` call during development — see docs/export-slack.md).

**`team-slack-bridge` has no file-upload/attachment primitive** (its
`cli/`/`core/` directories were inspected directly; no such command
exists). This exporter therefore never uploads the artifact file to
Slack itself — it posts a short text summary, optionally with a link
(`destination.options["link"]`, e.g. a Drive/S3 URL from a prior
export). The caller decides and sets that link explicitly; this
exporter does not also perform the Drive/S3 upload.

**Live-sent (non-dry-run) messages were deliberately not tested in this
session** — doing so would post a real message into a real,
already-configured Slack workspace as a side effect of autonomous
agent work, which is exactly the kind of unannounced action
`PLAN.md`'s privacy/consent principles warn against. `--dry-run` was
verified live and is the only mode exercised here beyond mocked unit
tests; actually posting (`dry_run=False`) should be deliberately
confirmed by a human before relying on it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from ..errors import ErrorCode, MacSpeechError
from .base import ExportDestination, ExportPreview, ExportResult, Exporter

BRIDGE_PATH_ENV_VAR = "MAC_SPEECH_SLACK_BRIDGE_PATH"


class SlackExporter(Exporter):
    provider = "slack"

    def __init__(self, *, bridge_path: str | None = None, node_bin: str = "node"):
        self.bridge_path = bridge_path or os.environ.get(BRIDGE_PATH_ENV_VAR, "").strip() or None
        self.node_bin = node_bin

    def _require_bridge(self) -> Path:
        if not self.bridge_path:
            raise MacSpeechError(
                code=ErrorCode.ENGINE_NOT_FOUND,
                message="team-slack-bridge path is not configured.",
                remedy=f"Set {BRIDGE_PATH_ENV_VAR} to a local team-slack-bridge checkout/install.",
            )
        root = Path(self.bridge_path)
        if not (root / "cli" / "post.js").is_file() or not (root / "cli" / "dm.js").is_file():
            raise MacSpeechError(
                code=ErrorCode.ENGINE_NOT_FOUND,
                message=f"team-slack-bridge CLI not found under {root}/cli/.",
                remedy=f"Confirm {BRIDGE_PATH_ENV_VAR} points at a team-slack-bridge checkout.",
            )
        if shutil.which(self.node_bin) is None:
            raise MacSpeechError(
                code=ErrorCode.ENGINE_NOT_FOUND,
                message="Node.js not found.",
                remedy="Install Node >= 26 (team-slack-bridge's own engines requirement).",
            )
        return root

    def validate_destination(self, destination: ExportDestination) -> None:
        if destination.provider != self.provider:
            raise MacSpeechError(
                code=ErrorCode.INVALID_ARGUMENT,
                message=f"SlackExporter cannot handle provider '{destination.provider}'.",
            )
        if not destination.uri:
            raise MacSpeechError(
                code=ErrorCode.INVALID_ARGUMENT,
                message="Slack destination is required: a channel (e.g. '#channel') or, with "
                "options={'as_dm': True}, a Slack member ID for a DM.",
            )
        self._require_bridge()

    def _summary_text(self, source_path: Path, destination: ExportDestination) -> str:
        text = destination.options.get("text")
        if text:
            return text
        link = destination.options.get("link")
        base = f"New speech artifact ready: {source_path.name}"
        return f"{base}\n{link}" if link else base

    def preview(self, source_path: Path, destination: ExportDestination) -> ExportPreview:
        self.validate_destination(destination)
        as_dm = bool(destination.options.get("as_dm"))
        description = f"Slack {'DM to' if as_dm else 'channel'} {destination.uri}"
        return ExportPreview(
            provider=self.provider,
            source_path=str(source_path),
            destination_description=description,
            estimated_size_bytes=source_path.stat().st_size if source_path.exists() else 0,
            will_overwrite=False,  # Slack posts are always new messages, never overwritten.
        )

    def upload(self, source_path: Path, destination: ExportDestination, *, dry_run: bool = False) -> ExportResult:
        bridge_root = self._require_bridge()
        as_dm = bool(destination.options.get("as_dm"))
        text = self._summary_text(source_path, destination)
        description = f"Slack {'DM to' if as_dm else 'channel'} {destination.uri}"

        script = bridge_root / "cli" / ("dm.js" if as_dm else "post.js")
        args = [self.node_bin, str(script)]
        args += ["--user" if as_dm else "--channel", destination.uri, "--text", text]
        idempotency_key = destination.options.get("idempotency_key")
        if idempotency_key:
            args += ["--idempotency-key", idempotency_key]
        if dry_run:
            args.append("--dry-run")
        args.append("--json")

        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            raise MacSpeechError(
                code=ErrorCode.NATIVE_PROCESS_ERROR,
                message=result.stderr.strip() or "team-slack-bridge CLI exited with a non-zero status.",
            )
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise MacSpeechError(
                code=ErrorCode.NATIVE_PROCESS_ERROR, message=f"team-slack-bridge returned invalid JSON: {exc}"
            ) from exc

        if not response.get("ok"):
            raise MacSpeechError(
                code=ErrorCode.NATIVE_PROCESS_ERROR,
                message=f"team-slack-bridge reported failure: {response.get('error', response)}",
            )

        if dry_run or response.get("dryRun"):
            return ExportResult(
                provider=self.provider,
                source_path=str(source_path),
                destination_description=description,
                success=True,
                verified=False,
                message="dry run; nothing posted",
            )

        ts = response.get("ts")
        return ExportResult(
            provider=self.provider,
            source_path=str(source_path),
            destination_description=description,
            success=True,
            verified=bool(ts),
            remote_reference=ts,
        )
