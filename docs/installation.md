# Installation, upgrade, uninstall, and rollback

## Requirements and distribution

Native binaries are built from source; the Python wrapper is installed
separately with pip. See [packaging.md](packaging.md) for distribution,
integrity, signing, and notarization decisions. A local build is not a
promise of a signed/notarized downloadable release.

| Component | Declared requirement | Actually verified locally |
| --- | --- | --- |
| Python wrapper | Python >= 3.9 in `pyproject.toml` | Clean-wheel/native smoke on 3.11.3; final mocked suite also passes on 3.12.5, 3.13.7, 3.14.8. Python 3.9/3.10 are not locally validated. |
| Source build | Swift **6.4+**, as required by the SwiftPM manifests, with a compatible macOS SDK | Swift 6.4, Command Line Tools only, on macOS 27.0.1 arm64 |
| Native TTS runtime | macOS 13+ deployment target | macOS 27.0.1 arm64 only; macOS 13/14 runtime paths have not been exercised |
| Personal Voice status/traits | macOS 14+ APIs, guarded in TTS | Previously authorized use on macOS 27.0.1; no first-time authorization flow |
| Apple STT runtime/build SDK | macOS 27+ APIs | macOS 27.0.1 arm64, with the known locale-reservation limitation below |

The TTS runtime's macOS 13 floor does **not** mean a stock macOS 13 Swift
toolchain can build this source. Use a toolchain/SDK that supports the
manifests and targets. Intel Macs are unverified; Apple native engines
are not Windows/Linux TTS implementations. See [platform-support.md](platform-support.md)
for the detailed evidence and limitations.

## Install modes

```sh
./install.sh          # both STT and TTS (default)
./install.sh stt       # Apple Speech backend only
./install.sh tts       # native TTS engine only
```

Each mode only **builds the native capability** it names; all three modes
unconditionally copy the legacy `whisper-py-convert.py` script and create
its `whisper-py-convert` symlink. Thus `tts` avoids building Apple STT but
does not omit the legacy wrapper. No mode removes
or disables whatever is already installed from a previous run. Running
`./install.sh stt` after `./install.sh tts` adds STT alongside the
existing TTS install, and vice versa — there is no "uninstall the other
one" behavior, consistent with "no existing working flow is removed or
silently changed" (`PLAN.md` Phase 4 acceptance criteria).

The Python CLI (`mac-speech`) is **not** installed by `install.sh` at
all; it is a standard Python package with its own `pyproject.toml`.
`install.sh` only prints setup guidance. For a base install, use:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .       # base wrapper, no runtime dependencies
# Contributors can use -e ".[dev]" instead; Drive users can use -e ".[gdrive]".
.venv/bin/mac-speech doctor
```

This is deliberate — `install.sh` already knows how to build/place native
binaries safely, but automatically running `pip install` against a
user's environment is a different kind of side effect (see
`docs/decisions/ADR-001-repository-and-module-boundaries.md` and
`PLAN.md`'s "do not introduce automatic... side effects" principle).

## What gets installed where

| Artifact | Location | Installed by |
| --- | --- | --- |
| `whisper-py-convert` command | `~/.local/bin/whisper-py-convert` (symlink) | `install.sh` — unconditionally, every mode |
| `whisper-py-convert.py` | `~/.local/share/whisper-py-convert/whisper-py-convert.py` | `install.sh` — unconditionally, every run |
| Apple STT binary | `~/.local/share/whisper-py-convert/whisper-py-convert-apple` | `install.sh` (`stt` or `all`), only on macOS with Swift |
| Native TTS binary | `~/.local/share/mac-speech/mac-speech-tts` | `install.sh` (`tts` or `all`), only on macOS with Swift |
| `mac-speech` Python package/command | chosen Python environment's site-packages / `bin/mac-speech` (typically `.venv/`) | the user, via pip; editable installs refer back to this source tree |
| TTS playback PID | `${XDG_CACHE_HOME:-$HOME/.cache}/mac-speech/tts.pid`, or `MAC_SPEECH_TTS_PID_FILE` | tracked `mac-speech tts speak` calls; normally removed at completion |
| Google Drive token | `~/.config/mac-speech/gdrive-token.json`, or `MAC_SPEECH_GDRIVE_TOKEN` | explicit interactive Drive OAuth use; **sensitive refresh-token credential**, not disposable speech cache |
| faster-whisper + models | Python environment used by the legacy wrapper / Hugging Face cache (normally `~/.cache/huggingface/hub`) | legacy STT first-use installation/download, not `install.sh` or the base wrapper install |

### Custom paths and discovery

`install.sh` honors `XDG_DATA_HOME` and `XDG_BIN_HOME`. Keep those values
for upgrades/uninstall; the script does not record an installation receipt.
`XDG_BIN_HOME` is this installer's convention, not a standard XDG variable.
The Python package's `mac-speech` command still lives in the venv.

Binary discovery does **not** automatically follow custom XDG data/bin
locations or search `PATH` for native engines. It checks source build
outputs before the default `~/.local/share` copies. For a custom install,
or to ensure you run the installed TTS copy rather than an older build:

```sh
export PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$PATH"
export MAC_SPEECH_TTS_BINARY="${XDG_DATA_HOME:-$HOME/.local/share}/mac-speech/mac-speech-tts"
export WHISPER_PY_CONVERT_BIN="${XDG_DATA_HOME:-$HOME/.local/share}/whisper-py-convert/whisper-py-convert.py"
```

The legacy script can find an Apple binary next to itself at the custom
location. However, the shared wrapper's **direct Apple JSON path and
capability probe** only check repository builds and the default data
location; there is currently no Apple-binary environment override.
`WHISPER_PY_CONVERT_BIN` selects the legacy script, not that direct binary.
Use the default data location or an editable source checkout with a built
Apple engine for that path. See [configuration.md](configuration.md).

## Upgrade

First stop playback and let running synthesis/transcription/export jobs
finish (see Uninstall below). Record your environment and keep backups
**before** replacing installed files; installation is not transactional:
the legacy script is copied before builds, builds may warn and continue,
and old binaries may remain if a build fails. A zero installer exit code
alone is not proof of a successful native upgrade.

Review `git status --short` and the release notes first. Do not pull,
switch revisions, or overwrite files to resolve a dirty checkout. Obtain
the selected revision in a separate source directory/worktree if you have
local edits, and leave the original tree intact. If the tree is clean,
`git pull --ff-only` is an option; inspect the fetched changes before use.
Re-run the **same selected mode** and XDG settings, for example:

```sh
./install.sh tts
.venv/bin/python -m pip install -e .
.venv/bin/mac-speech doctor
```

This rebuilds/replaces the selected native binary and the always-installed
legacy wrapper/symlink; it leaves the other native capability alone.
Retain the same extras (`.[dev]`, `.[gdrive]`) if you need them.

- **Editable:** source edits in that checkout are immediately visible;
  re-run pip for metadata/dependency/entry-point changes. Switching to a
  different source directory requires re-installing from that directory
  or, preferably, creating its own venv.
- **Non-editable:** source edits are not reflected until reinstalling.
  Use `YOUR_VENV/bin/python -m pip install --upgrade /path/to/new/source`
  or `YOUR_VENV/bin/python -m pip install --force-reinstall /path/to/new.whl`.
  A Python wheel alone does not update native binaries.
- **Different Python interpreter:** create a new venv using that Python,
  install the desired package/extras there, then invoke its explicit
  `bin/mac-speech`. Do not copy a venv between paths/interpreters or use
  an unqualified system `pip`. Keep the old venv for rollback.

Use wrapper and TTS engine from the same revision. TTS protocol-version
checks detect incompatible responses, but do not constitute an automatic
updater or prove compatibility with every historical build.

## Uninstall

### 1. Stop work before removing files

Use your installed environment's `mac-speech tts stop` to stop a tracked
playback; use the same `MAC_SPEECH_TTS_PID_FILE`/`XDG_CACHE_HOME` as the
playback. "No running ... process was found" is expected if none is
tracked. Wait for the original `speak` process to exit. The default PID
file only tracks one call: stop untracked/concurrent calls in their
own terminal with Ctrl+C and wait for them too. Do not blindly signal a
PID copied from an old file. Complete/cancel other jobs before cleanup.

### 2. Remove only the installed files you selected

Nothing here installs a launch agent or background service. Inspect these
paths first; use the XDG settings from installation, **not** a guessed
default. These variables are also used by the backup/restore examples:

<!-- lifecycle: paths -->
```sh
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
STT_DIR="$DATA_HOME/whisper-py-convert"
TTS_DIR="$DATA_HOME/mac-speech"
PID_FILE="${MAC_SPEECH_TTS_PID_FILE:-${XDG_CACHE_HOME:-$HOME/.cache}/mac-speech/tts.pid}"
```

For **TTS only**, after stopping playback:

<!-- lifecycle: uninstall-tts -->
```sh
rm -f "$TTS_DIR/mac-speech-tts" "$PID_FILE"
rmdir "$TTS_DIR" 2>/dev/null || true     # succeeds only if empty
```

For **STT/legacy wrapper only**, if you no longer use it:

<!-- lifecycle: uninstall-stt -->
```sh
if [ -L "$BIN_DIR/whisper-py-convert" ] &&
   [ "$(readlink "$BIN_DIR/whisper-py-convert")" = "$STT_DIR/whisper-py-convert.py" ]; then
    rm -f "$BIN_DIR/whisper-py-convert"
fi
rm -f "$STT_DIR/whisper-py-convert.py" "$STT_DIR/whisper-py-convert-apple"
rmdir "$STT_DIR" 2>/dev/null || true
```

For **all**, run both blocks. A TTS-only install also placed the legacy
wrapper: remove it with the STT block only if no other STT workflow uses
it. Keep the shared Python wrapper if you still use either capability.

To remove the Python wrapper from its actual environment:

```sh
.venv/bin/python -m pip uninstall mac-speech
```

This works for editable and non-editable installations, removes that
environment's `mac-speech` entry point, and leaves source files and native
binaries intact. It does not remove optional dependencies. Remove a
whole venv only after confirming it is dedicated, disposable, not used
by other projects, and not needed for rollback. Do not use `sudo pip`.

Uninstall deliberately leaves generated audio/transcripts/manifests,
source checkouts/build outputs, shared model caches, and credentials
alone. If `doctor` still finds an engine, it may be finding a source
`.build` output, an override, or another environment: inspect the
reported path rather than deleting more directories.

## Cache/model cleanup and credential removal (separate opt-in actions)

- The TTS PID file is control state, not audio/models. Remove that one
  file only after playback has stopped; never recursively remove its
  parent, which may contain unrelated files. A custom PID-file path is
  respected by the variables above.
- Generated artifact directories are **user data**, not disposable
  installation cache. Review/backup individual audio, transcripts,
  subtitle files, and workflow/manifests before choosing to delete any.
  Export and uninstall do not delete them. Remote copies require their
  own provider-specific retention/deletion decision.
- Swift `.build` directories can be regenerated, but first keep any
  binary you need for rollback. Stop other builds/tests, then use
  `swift package --package-path engines/tts-swift clean` for TTS-local
  build cleanup. Avoid deleting global Swift caches shared by projects;
  see Troubleshooting for the known toolchain issue.
- faster-whisper is not installed by this installer. If no longer needed,
  run `YOUR_ENV/bin/python -m pip uninstall faster-whisper` in the
  environment that installed it. Pip does not remove model data or all
  transitive dependencies. Inspect Hugging Face's actual cache location
  (`HF_HOME`/`HF_HUB_CACHE` can relocate it) and use its cache-management
  tooling to review **one chosen model/revision** before deleting it.
  Models can be shared by unrelated projects; do not delete the whole
  hub directory or use a wildcard `models--...-*` removal.
- Apple-managed speech assets/system voices are outside this project's
  ownership. Manage downloads through macOS settings, not toolkit `rm`
  commands. No neural TTS model is bundled or silently downloaded.

**Google OAuth cache:** `~/.config/mac-speech/gdrive-token.json` (or
`MAC_SPEECH_GDRIVE_TOKEN`) contains a refresh token. It is a sensitive
credential even though it has "cache" semantics. It is stored as a local
JSON file with owner-only permissions after creation, **not** in Keychain
and not encrypted by this tool. `XDG_CONFIG_HOME` does not relocate this
default; use the explicit token override. Never commit, paste, log, or
include it in release/rollback bundles. Review who can access backups.
If disconnecting Drive, revoke the app's access in your Google account
as well as explicitly deleting this one local token file:

<!-- lifecycle: remove-gdrive-token -->
```sh
rm -f "${MAC_SPEECH_GDRIVE_TOKEN:-$HOME/.config/mac-speech/gdrive-token.json}"
```

Local deletion is not server-side revocation and cannot erase other
backups. Handle your OAuth client-secrets file separately. AWS CLI and
`team-slack-bridge` credentials are externally managed/shared: toolkit
uninstall must not delete `~/.aws`, SSO caches, or bridge auth files.

## Privacy and permissions

Native TTS and Apple STT process content locally. Core commands do not
require cloud accounts; export is a separate explicit operation. First
installation/dependency setup and Apple's missing-asset downloads can
need network access. Legacy STT's `auto` engine can select faster-whisper
and download its runtime/models: choose `--engine apple` explicitly for
a no-model-download Apple workflow, with assets already installed.

Audio, transcripts, output JSON, logs, manifests, shell history, and
command-line arguments can contain sensitive text, voice identifiers,
paths, or destination references. Manifests normally hash source text
instead of retaining it, but that does not make audio/transcripts or all
provenance anonymous. Use non-sensitive smoke text and private output
directories; review/redact diagnostics before sharing them. Do not
include personal voice names/IDs or credentials in bug reports.

Standard system-voice synthesis/playback does not record a microphone.
File transcription is not microphone capture either; macOS Speech
Recognition/asset access can still be restricted by system privacy
policy. If macOS presents an authorization prompt, review it and use
System Settings → Privacy & Security for the relevant requesting
terminal/application. There is no guaranteed prompt or universal TCC
reset command for these bare binaries; do not disable privacy controls.
Personal Voice use is controlled by Apple, user consent, and availability.
`mac-speech tts personal-voice-status` only **reports** authorization;
this tool cannot request, create, extract, or unlock a Personal Voice.
Standard voices remain the fallback the user can explicitly select.

## Rollback

Stop work first, just as for uninstall. There is no install transaction,
automatic binary history, or automatic artifact-schema migration.
Do not overwrite or delete the current source tree, even if dirty.
Older code may not understand newer artifact/workflow manifests: keep
outputs/backups and use a separate output directory during validation.

### Keep installed-file backups before an upgrade

After setting the path variables above, choose a **new, private, empty**
`BACKUP_DIR` outside generated-artifact directories. The block refuses to
reuse an existing directory. Keep it out of Git. It records only selected
installed files, **not** credentials, models, or output artifacts:

<!-- lifecycle: backup-installed -->
```sh
set -e
: "${BACKUP_DIR:?Set BACKUP_DIR to a new private backup directory}"
(umask 077; mkdir "$BACKUP_DIR")
for name in whisper-py-convert.py whisper-py-convert-apple; do
    if [ -f "$STT_DIR/$name" ]; then cp -p "$STT_DIR/$name" "$BACKUP_DIR/$name"; fi
done
if [ -f "$TTS_DIR/mac-speech-tts" ]; then
    cp -p "$TTS_DIR/mac-speech-tts" "$BACKUP_DIR/mac-speech-tts"
fi
```

`set -e` makes a failed `mkdir`/copy stop the backup. Record the revision,
wrapper version, OS/architecture, Swift/Python
versions, mode, install-path settings, and hashes alongside the backups.
Keep the matching previous Python wheel or the old venv/source directory;
editable installs are not snapshots of their source.

To restore **only a backed-up TTS binary**, keeping STT intact:

<!-- lifecycle: restore-tts -->
```sh
set -e
: "${BACKUP_DIR:?Set BACKUP_DIR to the trusted installed-file backup}"
test -f "$BACKUP_DIR/mac-speech-tts"
mkdir -p "$TTS_DIR"
cp -p "$BACKUP_DIR/mac-speech-tts" "$TTS_DIR/mac-speech-tts"
chmod 755 "$TTS_DIR/mac-speech-tts"
export MAC_SPEECH_TTS_BINARY="$TTS_DIR/mac-speech-tts"
```

Restore the corresponding wrapper from its kept
wheel into the chosen venv (`python -m pip install --force-reinstall
/path/to/previous.whl`), or invoke its preserved venv. If restoring STT,
copy only the backed-up legacy script/Apple binary to `STT_DIR`, restore
the symlink to that script if needed, and verify the selected source and
binary paths. A TTS override prevents current source build output from
silently taking precedence over your restored installed copy.

### Rebuild from separate previous source, preserving the current tree

If the desired version exists in Git, choose an existing, reviewed
commit/tag and a **new path** for `PREVIOUS_SOURCE` outside this checkout:

<!-- lifecycle: previous-worktree -->
```sh
: "${PREVIOUS_REVISION:?Set PREVIOUS_REVISION to a reviewed previous commit/tag}"
: "${PREVIOUS_SOURCE:?Set PREVIOUS_SOURCE to a new separate worktree path}"
git worktree add --detach "$PREVIOUS_SOURCE" "$PREVIOUS_REVISION"
```

This leaves current tracked edits/untracked files untouched. Important:
the ongoing implementation may be uncommitted; Git cannot recover those
files from a tag/commit that never contained them. Use kept binaries,
wheels, or an earlier separate source copy for that case. Do not
`git checkout`, `reset`, or `clean` the current tree to attempt rollback.

Inspect the previous directory's own installer before running it: older
revisions may not support `tts`/`stt` modes at all. If it does, run
`"$PREVIOUS_SOURCE/install.sh" tts` with the original XDG settings, or the
appropriate supported mode, and create its own venv:

```sh
python3 -m venv "$PREVIOUS_SOURCE/.venv"
"$PREVIOUS_SOURCE/.venv/bin/python" -m pip install -e "$PREVIOUS_SOURCE"
"$PREVIOUS_SOURCE/.venv/bin/mac-speech" doctor
```

If a preserved previous source directory already exists, no Git command
is necessary. Explicitly point TTS/the legacy script at the restored
installation or that previous source, and inspect `capabilities --json`
before running content. Do not reuse a current editable venv if you need
the older Python code. Do not delete the current binaries until you have
backed them up and verified the previous build can run on your OS.

## Verifying an install

```sh
mac-speech doctor           # human-readable
mac-speech capabilities --json
mac-speech tts voices --json
mac-speech tts save "Local installation check." --output ./installation-check.wav --format wav
whisper-py-convert --check  # read-only legacy runtime/cache inventory; no transcription
```

`doctor`/`capabilities` report `stt`/`tts` availability independently —
confirmed during Phase 4 by temporarily hiding each native binary in
turn and re-running `mac-speech capabilities`/`tts save`/`stt
transcribe`: each capability degrades to an actionable
`engine_not_found` error on its own, without affecting the other.

Use the venv's explicit command path if it is not activated. For a
TTS-only install, missing STT is expected; inspect the capability-specific
results, not only `doctor`'s exit code. `doctor`/`capabilities` mainly
report discovered files/runtime metadata, not a guarantee of successful
speech synthesis, permission, or STT locale assets. The TTS save above is
a real native smoke check, requires TTS, and refuses an existing output.
Choose another filename rather than automatically deleting old output.

## Troubleshooting

| Symptom | Focused check/remedy |
| --- | --- |
| `mac-speech: command not found` | Invoke `YOUR_VENV/bin/mac-speech`, or activate the correct venv; `install.sh` does not install the Python command. Check `YOUR_VENV/bin/python -m pip show mac-speech`. |
| `whisper-py-convert` not found | Add the actual `XDG_BIN_HOME` directory to `PATH`; inspect its symlink target. |
| `engine_not_found`, or custom XDG install is invisible | Check `capabilities --json` paths, file existence/executable permissions, and the overrides above. An explicitly set missing TTS/script override yields no match; unset or correct it rather than assuming fallback. Direct Apple JSON has no override for custom XDG paths. |
| TTS `protocol_version_mismatch` | Install the matching Python wrapper/native TTS from the same reviewed revision; check whether an override or source build points at an older binary. Use separate-source/backup rollback if needed. |
| Installer exits successfully but engine still old/missing | Read build warnings; Swift failures are tolerated. Compare the installed file with the intended build, and inspect the resolved path. Repeat the independent TTS build with `swift build --package-path engines/tts-swift --configuration release`. |
| Swift rejects tools version or SDK APIs | Source requires Swift 6.4+ and a suitable SDK, independent of TTS's macOS 13 runtime floor. Check `swift --version` and `xcode-select -p`. |
| `TestingMacros` plugin/module-cache error | Stop overlapping Swift builds/tests; retry in a fresh independent source/build directory. For local cleanup, back up useful binaries and use package-local clean first. The shared-cache flakiness is recorded in [risk-register.md](risk-register.md) #17; do not routinely purge global caches belonging to other projects. |
| Apple STT reservation/locale failure | Rebuild the native Apple helper from the risk #19 repair; installing a Python wheel does not update it. `reserve == false` means already reserved, not unsupported. Run that **same executable** with `--inventory-status --language en-US` for read-only state. Capacity is device-specific, not a request limit. Stage diagnostics retain Speech domain/code. Existing reservations are borrowed, not automatically evicted; do not delete assets or use a separate Swift script as a presumed identity reset. Newly-owned cleanup/recovery evidence remains partial; see [repair evidence](stt-reservation-repair.md). TTS is independent. |
| Preparing explicit reservation recovery | Use the same rebuilt binary's locked `--reservation-maintenance inspect` and unconfirmed preview. No region is presumed unused. A real release needs exact matching confirmation, unused/quiescent-client acknowledgement and separate approval; it may affect offline assets. Optional native installed/exact/new guards prevent misleading validation. See [maintenance safety](stt-reservation-maintenance.md). |
| Apple language not ready before transcription | The Python adapter runs a read-only preflight against its exact selected helper. Missing assets show requested/resolved locale and a quoted `--install-assets --language ... --confirm-download ...` command. Preview first; only explicitly confirmed setup may download and retain an asset reservation. Native transcription no longer downloads automatically. Unsupported/old helpers require matching source rebuild, not arbitrary cache deletion. See [generic asset setup](apple-asset-setup.md). |
| Missing/denied Personal Voice or varying voice list | Re-query `tts voices` and `tts personal-voice-status`; choose a reported standard system voice. macOS availability/consent controls this; the CLI cannot request authorization. Do not rely on a fixed voice count. |
| Playback cannot be stopped from another terminal | Use the same PID-file settings; only the most recent tracked call is controlled. Stop other calls in their original terminal before removing the PID file. |
| `output_exists`, or save format error | Choose a new output path; `--force` is an explicit overwrite decision. Select `wav`, `aiff`, or `caf` with a matching extension and writable parent directory. |
| Long operation times out | Increase that command's explicit `--timeout` if appropriate; verify the engine/process exits before retrying. Do not assume a partially generated file is valid audio. |
| Optional export dependency/auth failure | Core speech remains usable. Install only the needed extra/configure the external provider; use `--dry-run` and [exporters.md](exporters.md). Do not include tokens or full sensitive content in diagnostics. |
| macOS blocks a downloaded binary | Follow the trust/signing guidance in [packaging.md](packaging.md); do not disable Gatekeeper or blindly strip quarantine attributes. |

## Lifecycle-test evidence and limits

`tests/unit/test_installation_lifecycle.py` runs the marked shell examples
in temporary HOME/XDG/source directories with a fake `swift` that emits
sentinel executables. It checks install modes, installed-file backups,
focused uninstall/restore, explicit token removal, and separate-worktree
rollback preserving dirty/untracked source. These tests require the full
repository checkout and skip in the Python-only sdist, which deliberately
omits the installer/legacy/native sources. These are **installer/file
lifecycle simulations**, not evidence of a fresh native Swift build,
Apple permissions, live OAuth, or a macOS 13/14 runtime test. No real
installed binaries, auth caches, or Apple STT locale state are used.

A separate manual check on 2026-10-11 used a disposable Python 3.11.3
venv and copied package source to verify real pip editable/non-editable
installation, source-update behavior, kept-wheel rollback, and uninstall.
Both uninstall paths removed the temporary CLI while retaining the copied
source; wheel rollback replaced the editable package without changing
its dirty source. Build-tool setup downloaded setuptools 84.0.0 and wheel
0.48.0 into that venv only; subsequent package operations used local
source/wheels with `--no-index --no-deps` (source builds also used
`--no-build-isolation`). That check did not execute native speech and is
not an older-Python or no-network dependency-bootstrap claim.

The main session subsequently verified the final wheel built from its sdist
in a clean non-editable Python 3.11.3 venv, **and a real TTS-only source
install** under temporary HOME/XDG paths. Engine-free and native WAV/manifest/
overwrite smoke passed with credential environment stripped and OS/Python
network denial. Documented binary backup/uninstall/restore and wheel
uninstall/restore passed while retaining unrelated artifacts and the legacy
script/symlink. These later checks supplement, not replace or re-label, the
simulations and earlier Python-only snapshot above. See
[verification](verification.md) and [the Phase 12 handoff](SESSION_HANDOFF.md).
