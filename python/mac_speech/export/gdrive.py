"""Google Drive exporter (PLAN.md Phase 8).

**Optional dependency, not in the base install.** Requires
`google-api-python-client`, `google-auth-oauthlib`, and
`google-auth-httplib2` — install with `pip install "mac-speech[gdrive]"`.
Importing this module never fails without them; only *using* it does,
with an actionable remedy.

**Not tested against a real Google Drive account in this session** —
doing so requires a user-created Google Cloud project and OAuth client
secret, which is credential setup only a human can do, not something an
agent should provision autonomously. The OAuth flow, request shapes,
and error handling below follow the documented Drive v3 API; `tests/`
mocks the `googleapiclient`/`google-auth` layer rather than hitting a
real account. Before relying on this in production, run it once
against a real, disposable Drive folder and confirm the result.

**Minimum viable OAuth scope:** `drive.file` — this app can only see
files it creates itself, never the user's whole Drive. Token storage is
a local JSON file (contains a refresh token) at
`~/.config/mac-speech/gdrive-token.json` by default, created with
`0600` permissions; never committed to a repository, never logged.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from ..errors import ErrorCode, MacSpeechError
from .base import ExportDestination, ExportPreview, ExportResult, Exporter

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

CLIENT_SECRETS_ENV_VAR = "MAC_SPEECH_GDRIVE_CLIENT_SECRETS"
TOKEN_PATH_ENV_VAR = "MAC_SPEECH_GDRIVE_TOKEN"


def _default_token_path() -> Path:
    return Path.home() / ".config" / "mac-speech" / "gdrive-token.json"


class GoogleDriveExporter(Exporter):
    provider = "gdrive"

    def __init__(self, *, client_secrets_path: str | None = None, token_path: str | None = None):
        self.client_secrets_path = client_secrets_path or os.environ.get(CLIENT_SECRETS_ENV_VAR, "").strip() or None
        self.token_path = Path(token_path or os.environ.get(TOKEN_PATH_ENV_VAR, "").strip() or _default_token_path())

    def _require_optional_dependency(self) -> None:
        try:
            import google.auth  # noqa: F401
            import googleapiclient.discovery  # noqa: F401
            import google_auth_oauthlib.flow  # noqa: F401
        except ImportError as exc:
            raise MacSpeechError(
                code=ErrorCode.ENGINE_NOT_FOUND,
                message="Google Drive export requires optional dependencies that are not installed.",
                remedy='Run: pip install "mac-speech[gdrive]"',
            ) from exc

    def validate_destination(self, destination: ExportDestination) -> None:
        if destination.provider != self.provider:
            raise MacSpeechError(
                code=ErrorCode.INVALID_ARGUMENT,
                message=f"GoogleDriveExporter cannot handle provider '{destination.provider}'.",
            )
        if not destination.uri:
            raise MacSpeechError(
                code=ErrorCode.INVALID_ARGUMENT,
                message="Google Drive destination folder ID is required (ExportDestination.uri).",
            )
        self._require_optional_dependency()
        if not self.client_secrets_path or not Path(self.client_secrets_path).is_file():
            raise MacSpeechError(
                code=ErrorCode.ENGINE_NOT_FOUND,
                message="Google OAuth client secrets file not found.",
                remedy=(
                    f"Download a client_secret.json from Google Cloud Console (Desktop app type) "
                    f"and set {CLIENT_SECRETS_ENV_VAR} to its path."
                ),
            )

    def _get_credentials(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        credentials = None
        if self.token_path.is_file():
            credentials = Credentials.from_authorized_user_file(str(self.token_path), DRIVE_SCOPES)

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

        if not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(self.client_secrets_path, DRIVE_SCOPES)
            credentials = flow.run_local_server(port=0)  # one-time, interactive, user-driven
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(credentials.to_json(), encoding="utf-8")
            os.chmod(self.token_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600: owner read/write only

        return credentials

    def preview(self, source_path: Path, destination: ExportDestination) -> ExportPreview:
        self.validate_destination(destination)
        return ExportPreview(
            provider=self.provider,
            source_path=str(source_path),
            destination_description=f"Google Drive folder {destination.uri}",
            estimated_size_bytes=source_path.stat().st_size if source_path.exists() else 0,
            # Unknown without listing the folder's contents, which this
            # exporter deliberately avoids by default (minimum necessary
            # API calls; `drive.file` scope cannot list arbitrary folders
            # anyway).
            will_overwrite=None,
        )

    def upload(self, source_path: Path, destination: ExportDestination, *, dry_run: bool = False) -> ExportResult:
        self.validate_destination(destination)
        description = f"Google Drive folder {destination.uri}"

        if dry_run:
            return ExportResult(
                provider=self.provider,
                source_path=str(source_path),
                destination_description=description,
                success=True,
                verified=False,
                message="dry run; nothing uploaded",
            )

        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        credentials = self._get_credentials()
        service = build("drive", "v3", credentials=credentials)
        file_metadata = {"name": source_path.name, "parents": [destination.uri]}
        media = MediaFileUpload(str(source_path), resumable=True)
        request = service.files().create(body=file_metadata, media_body=media, fields="id,size,name")

        response = None
        while response is None:
            _status, response = request.next_chunk()

        file_id = response.get("id")
        verified = response.get("size") is not None and int(response["size"]) == source_path.stat().st_size

        return ExportResult(
            provider=self.provider,
            source_path=str(source_path),
            destination_description=description,
            success=True,
            verified=verified,
            remote_reference=file_id,
        )
