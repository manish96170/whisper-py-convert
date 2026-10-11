"""Amazon S3 exporter via the AWS CLI (PLAN.md Phase 9).

Shells out to the `aws` CLI rather than adding `boto3` as a dependency —
per PLAN.md: "Keep AWS SDK packages out of the base install if a CLI
adapter is sufficient." This also means credential resolution is
entirely the AWS CLI's own well-documented chain (named profile,
environment variables, SSO, instance role, etc.) — nothing here reads,
stores, or logs AWS credentials itself.

**Not tested against a real S3 bucket in this session** — doing so
requires an AWS account and a bucket/prefix the agent is authorized to
write to, which is account setup only a human should provision. `tests/`
mocks `subprocess.run` rather than hitting a real bucket. Verify against
a real, disposable bucket/prefix before relying on this.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from ..errors import ErrorCode, MacSpeechError
from .base import ExportDestination, ExportPreview, ExportResult, Exporter

_S3_URI_RE = re.compile(r"^s3://([^/]+)/(.*)$")


class S3Exporter(Exporter):
    provider = "s3"

    def __init__(
        self,
        *,
        profile: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
        aws_cli: str = "aws",
    ):
        self.profile = profile
        self.region = region
        self.endpoint_url = endpoint_url
        self.aws_cli = aws_cli

    def _require_aws_cli(self) -> None:
        if shutil.which(self.aws_cli) is None:
            raise MacSpeechError(
                code=ErrorCode.ENGINE_NOT_FOUND,
                message="AWS CLI not found.",
                remedy='Install it (e.g. "brew install awscli") or pass aws_cli= to a specific path.',
            )

    def _parse_destination(self, destination: ExportDestination) -> tuple[str, str]:
        match = _S3_URI_RE.match(destination.uri or "")
        if not match:
            raise MacSpeechError(
                code=ErrorCode.INVALID_ARGUMENT,
                message=f"Invalid S3 destination '{destination.uri}'; expected s3://bucket/prefix/",
            )
        return match.group(1), match.group(2)

    def validate_destination(self, destination: ExportDestination) -> None:
        if destination.provider != self.provider:
            raise MacSpeechError(
                code=ErrorCode.INVALID_ARGUMENT,
                message=f"S3Exporter cannot handle provider '{destination.provider}'.",
            )
        self._parse_destination(destination)
        self._require_aws_cli()

    def _key_for(self, prefix: str, source_path: Path) -> str:
        prefix = prefix.rstrip("/")
        return f"{prefix}/{source_path.name}" if prefix else source_path.name

    def _base_command(self, *subcommand: str) -> list[str]:
        command = [self.aws_cli, *subcommand]
        if self.profile:
            command += ["--profile", self.profile]
        if self.region:
            command += ["--region", self.region]
        if self.endpoint_url:
            command += ["--endpoint-url", self.endpoint_url]
        return command

    def preview(self, source_path: Path, destination: ExportDestination) -> ExportPreview:
        self.validate_destination(destination)
        bucket, prefix = self._parse_destination(destination)
        key = self._key_for(prefix, source_path)
        return ExportPreview(
            provider=self.provider,
            source_path=str(source_path),
            destination_description=f"s3://{bucket}/{key}",
            estimated_size_bytes=source_path.stat().st_size if source_path.exists() else 0,
            # Deliberately not checked: PLAN.md Phase 9 says "avoid bucket
            # listing unless needed and authorized." A HeadObject call
            # would answer this, but it is an extra authenticated call
            # this preview does not make by default.
            will_overwrite=None,
        )

    def upload(self, source_path: Path, destination: ExportDestination, *, dry_run: bool = False) -> ExportResult:
        self.validate_destination(destination)
        bucket, prefix = self._parse_destination(destination)
        key = self._key_for(prefix, source_path)
        description = f"s3://{bucket}/{key}"

        command = self._base_command("s3", "cp", str(source_path), description)
        if dry_run:
            command.append("--dryrun")

        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise MacSpeechError(
                code=ErrorCode.NATIVE_PROCESS_ERROR,
                message=result.stderr.strip() or "aws s3 cp failed",
                remedy="Check your AWS credentials/profile/region and bucket permissions.",
            )

        if dry_run:
            return ExportResult(
                provider=self.provider,
                source_path=str(source_path),
                destination_description=description,
                success=True,
                verified=False,
                message="dry run; nothing uploaded",
            )

        verified = self._verify(bucket, key, source_path.stat().st_size)
        return ExportResult(
            provider=self.provider,
            source_path=str(source_path),
            destination_description=description,
            success=True,
            verified=verified,
            remote_reference=description,
        )

    def _verify(self, bucket: str, key: str, expected_size: int) -> bool:
        """Confirms the object exists and its size matches, via a single
        HeadObject call — not a bucket listing."""
        import json

        command = self._base_command("s3api", "head-object", "--bucket", bucket, "--key", key, "--output", "json")
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            return False
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return False
        return payload.get("ContentLength") == expected_size
