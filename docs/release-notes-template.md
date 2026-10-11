# Release notes template

Copy this template for a specific reviewed release; replace every
placeholder and omit unimplemented features. `CHANGELOG.md` tracks
unreleased changes. Do not invent a release date, tag, checksum, signing
identity, tested platform, or license. Distribution/signing policy:
[packaging.md](packaging.md).

## `<version>` — `<actual release date>`

- Reviewed commit/tag: `<revision>`; clean release source: `<yes/no>`.
- Python wrapper version: `<version>`; native TTS version/protocol:
  `<version/protocol>`; legacy STT revision: `<revision>`.
- Distribution: `<source-only / exact published assets and URLs>`.
- Integrity: `<SHA-256 for each actual asset, how it was obtained>`.
- Signing/notarization: `<actual status, verification evidence, or not provided>`.
- Project license: `<maintainer-established license and LICENSE reference>`.
  **If not established, mark public distribution blocked; do not substitute
  a dependency's license.**
- Dependency inventory/SBOM and review: `<references and date>`.

### Highlights

- `<User-visible additions/fixes, with explicit scope and affected capability>`.
- `<Any changed CLI/API, error, protocol, artifact/workflow schema, or defaults>`.
- `<Legacy behavior intentionally preserved; any separately authorized change>`.

### Requirements and compatibility

- Source toolchain/SDK: `<versions actually required>` (currently Swift 6.4+).
- Runtime targets: `<per-engine deployment target>` (currently TTS macOS
  13+, Apple STT macOS 27+, Personal Voice APIs macOS 14+).
- Python metadata requirement: `<declared range>` (currently >=3.9).
- Actually tested: `<OS/build, CPU, Python, Swift/SDK versions>`.
- Unverified/unsupported: `<older OS/Python, Intel, other platforms>`.
- Wrapper/native compatibility: `<supported protocol and version pairing>`.
  Minimum deployment targets are not a tested-runtime matrix.

### Install / upgrade

Refer to [installation.md](installation.md), choosing `stt`, `tts`, or
`all`. State that all modes still install the legacy wrapper/symlink and
that pip installs the shared Python CLI separately. Specify:

- `<Editable/non-editable/wheel update commands for the chosen environment>`.
- `<Native build/update command, custom XDG settings, discovery overrides>`.
- `<How to stop playback/jobs and keep previous installed binaries/wheel or source>`.
- `<Metadata/dependency changes requiring pip reinstall; extras needed>`.
- `<Any migration, retention changes, and what is NOT deleted>`.

### Privacy, permissions, and known limitations

- `<Local/offline prerequisites; explicit optional network/export behavior>`.
- `<Permission/Personal Voice constraints; no authorization-bypass guidance>`.
- `<Credential locations/removal and provider-specific revocation guidance>`.
  In particular, the Drive token under `~/.config/mac-speech/` or its
  override is a **sensitive credential**, not disposable artifact cache.
- `<Known defects, skips, deferred validations; relevant risk-register IDs>`.
- `<Real provider tests versus mock/dry-run-only coverage>`.

### Validation evidence

| Check | Exact command and environment | Result / limitations |
| --- | --- | --- |
| Python unit tests | `<venv python -m pytest tests/unit -q>` | `<passed/skipped/failed counts and reasons>` |
| Python lint/type checks | `<actual commands and checked scope>` | `<result; unchecked modules>` |
| Native Swift build/tests | `<commands and toolchain/SDK>` | `<counts/result; cache workaround if used>` |
| Clean install / no-network native TTS | `<steps, paths, asset readiness>` | `<real native run or not performed; not just mocks>` |
| TTS-only/STT-only/all lifecycle | `<commands/test file>` | `<simulation versus actual build clearly distinguished>` |
| Uninstall/rollback | `<isolated HOME/XDG/worktree/venv checks>` | `<files preserved; no real user auth/install touched>` |
| Optional exporters | `<provider and test type>` | `<mock / dry-run / human-approved real destination>` |

### Rollback and uninstall

Link to the [tested lifecycle procedure](installation.md#rollback): stop
work; restore a kept matching binary/wheel pair or rebuild a reviewed
previous revision in a **separate source directory/worktree with its own
venv**. Preserve the current dirty tree, outputs, credentials, and shared
model caches. Never instruct users to check out an old revision over their
uncommitted work. State any older-schema/OS limitations and whether the
previous tag actually contains the components required for rollback.

Use focused uninstall commands from the same guide; token deletion,
remote-data deletion, shared-model cleanup, and generated-artifact removal
are separate explicit user decisions, not automatic uninstall steps.
