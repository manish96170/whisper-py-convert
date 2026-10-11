# Exporter architecture: local, Google Drive, S3, Slack (Phases 8-10)

## Common contract

Every exporter (`mac_speech.export.base.Exporter`) implements the same
four operations: `validate_destination`, `preview`, `upload` (with
`dry_run=`), and reports an `ExportResult`. Core speech generation
(`mac_speech.tts`, `mac_speech.stt`) never imports this package —
export is strictly opt-in, invoked explicitly via `mac-speech export`
or the Python API, never a side effect of `tts save`/`stt transcribe`.

```python
from pathlib import Path
from mac_speech.export import ExportDestination, get_exporter

exporter = get_exporter("local")  # or "gdrive" | "s3" | "slack"
destination = ExportDestination(provider="local", uri="/path/to/dir")
result = exporter.upload(Path("narration.wav"), destination, dry_run=True)
```

```sh
mac-speech export narration.wav --to local --destination /path/to/dir --json
mac-speech export narration.wav --to s3 --destination s3://bucket/prefix/ --dry-run --json
mac-speech export narration.wav --to slack --destination '#channel' --dry-run --link https://... --json
mac-speech export narration.wav --to gdrive --destination "folder-id" --dry-run --json
```

**Implemented boundaries and limitations:**

- Local files remain the source of truth; no exporter deletes or
  modifies the local artifact, on success or failure.
- `--dry-run` resolves and validates but transfers nothing
  (`success=True, verified=False`).
- Export result fields report destination/reference/status, not a credential
  store. **Drive does persist an OAuth token** as described below; S3 and
  Slack delegate credential handling to external tools. Provider errors and
  caller-supplied destination/link/message values are not universally
  redacted: do not put secrets in them, and review diagnostics before sharing.
- No exporter enables public sharing by default.

## Local (`--to local`)

No dependencies, no network. Copies the file (atomic temp-write +
rename), refuses to overwrite an existing destination unless
`options={"force": True}` (`--force` on the CLI). Fully verified by
`tests/unit/test_export_local.py` and a live run against the real
filesystem during Phase 8 development.

## Google Drive (`--to gdrive`)

**Optional dependency** — not in the base install:

```sh
YOUR_VENV/bin/python -m pip install '.[gdrive]'
```

From a reviewed local checkout; for a locally built wheel, install that wheel
with its `gdrive` extra instead. No public PyPI package is claimed while the
project license is unresolved.

OAuth scope: `drive.file` only — per-file access for files created by or
explicitly authorized to the app, not unrestricted whole-Drive access. This
adapter has no existing-file picker/authorization flow. A supplied folder ID
must be accessible to that app; typing an arbitrary ID does not grant access.
First upload needing authorization opens a
browser for one-time consent (`InstalledAppFlow.run_local_server`);
the resulting token (contains a refresh token) is cached at
`~/.config/mac-speech/gdrive-token.json` with `0600` permissions,
never in a repository. The token is plain JSON, not Keychain-encrypted; see
[credential removal and revocation](installation.md#cachemodel-cleanup-and-credential-removal-separate-opt-in-actions).
Dry-run validates local setup without requesting OAuth or verifying remote
folder access. Set `MAC_SPEECH_GDRIVE_CLIENT_SECRETS` to a
`client_secret.json` downloaded from Google Cloud Console (Desktop app
type) before first use.

**Not tested against a real Google account in this session** —
provisioning a Google Cloud project and OAuth client is account setup
only a human should do, not something to provision autonomously.
`tests/unit/test_export_gdrive.py` mocks the
`googleapiclient`/`google-auth` layer; the error paths (missing
dependency, missing client secrets file) were verified against the
real, unmodified environment (no `gdrive` extra installed here) and
correctly report `engine_not_found` with an actionable remedy rather
than a stack trace. **Before relying on this, run one real upload
against a disposable test folder and confirm the result.**

## Amazon S3 (`--to s3`)

Shells out to the `aws` CLI (no `boto3` dependency — "keep AWS SDK
packages out of the base install if a CLI adapter is sufficient").
Credential resolution is entirely the AWS CLI's own chain (named
profile, environment variables, SSO, instance role); nothing here
reads or stores AWS credentials. `--profile`/`--region`/`--endpoint-url`
are explicit, optional constructor arguments.

Verified in Phase 9 against a **real, configured AWS CLI installation
on this machine** (`aws configure list` showed real credentials):
`--dry-run` executed cleanly end-to-end (`aws s3 cp --dryrun`) against
a deliberately nonexistent bucket name, confirming the full command
construction and response-handling path works with the actual CLI, not
just mocks. **A real upload+verify (non-dry-run) was deliberately not
attempted** — that would need a real bucket/prefix a human has chosen
and is comfortable with, which was not specified in this session.
`tests/unit/test_export_s3.py` covers the mocked success/failure/verify
paths, including the `HeadObject`-based size verification after
upload.

Verification compares remote size, **not checksum**. Multipart/retry behavior
is delegated to the installed AWS CLI and large-file behavior has not been
independently tested. Existing object keys can be replaced; `--force` governs
only the local exporter, not a remote collision check. IAM/encryption policy
and any presigned URL remain user-managed, not toolkit provisioning features.

## Slack (`--to slack`, via `team-slack-bridge`)

**Inspected directly before building anything** — per `PLAN.md`
Phase 10's explicit instruction, `~/hornblower/team-slack-bridge`'s
`README.md`, `cli/`, and `core/` were read before any code was written.
Findings that shaped this adapter:

- It is a mature, documented CLI (`node cli/post.js`/`node cli/dm.js`),
  with universal `--dry-run`/`--json` flags and an idempotency-key
  mechanism (`--idempotency-key`) already built in — reused directly
  for "make retries idempotent," rather than inventing a second one.
- **It has no file-upload/attachment command** (confirmed: no such file
  exists under `cli/` or `core/`). This exporter therefore never
  uploads the artifact file to Slack itself — only a short text
  summary, optionally with a link (`options={"link": "..."}`) to
  wherever the file was separately exported (local/Drive/S3). This is
  the explicit choice `PLAN.md` asks for ("decide whether the actual
  file is uploaded to Slack, stored in Drive/S3 and linked, or both").
- It already has its own, independent, working Slack OAuth/token setup
  — this adapter deliberately does not add a second one, per "no
  second independent Slack authentication implementation."

**`--dry-run` was verified live** against a real, already-configured
`team-slack-bridge` install on this machine (`node cli/doctor.js --json`
showed a live, connected "Hornblower" Slack workspace) —
`node cli/post.js --channel '#test' --text '...' --dry-run --json`
returned exactly the documented
`{"ok": true, "dryRun": true, "request": {...}}` shape, and this
exporter's own `mac-speech export ... --to slack --dry-run` produced
the correct result against that same real install. **An actual
non-dry-run post was deliberately not sent** — doing so would place a
real message in a real, already-configured Slack workspace as a side
effect of this session, which is exactly the kind of unannounced
action to avoid. `tests/unit/test_export_slack.py` covers the mocked
success/failure/DM/idempotency-key paths.

Set `MAC_SPEECH_SLACK_BRIDGE_PATH` to a `team-slack-bridge` checkout to
use this exporter (not a Python dependency — a sibling project on
disk, invoked as a subprocess via `node`).

## What's deliberately not built

- No second Slack authentication path, per the acceptance criteria.
- No automatic/implicit export triggered by `tts save`/`stt
  transcribe` — always a separate, explicit `mac-speech export` call.
- No public-sharing defaults for any provider.
- No bucket/Drive-folder listing beyond what each provider's own
  single-object HeadObject-equivalent check needs — browsing a
  destination's existing contents was judged unnecessary scope.
