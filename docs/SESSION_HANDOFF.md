# Session handoff — Phase 13A output-safety milestone

**Written:** 2026-10-11. Read `PLAN.md` and this file in full; inspect actual
Git status/diff and rerun checks before trusting any summary.

## Outcome and current scope

The user explicitly requested continuation to the next phase. **Phase 13A,
a bounded workspace/output-safety hardening milestone, is locally complete.**
This does not mark the entire open-ended Phase 13 candidate backlog complete.
The separate reviewer identified cancellation/checkpoint/staging/cleanup
issues; they were fixed and independently rechecked, including broken stderr
and real synthetic child-process cancellation. No review findings remain.

**Verification checkpoint: changes were uncommitted.** The user subsequently
confirmed the audio and explicitly requested committing/pushing all reviewed
Phase 13A source/docs, retaining the earlier `main`/no-PR choices, then
continuing the next bounded hardening slice. Generated audio/builds/caches
and credentials are excluded. Execution follows this documentation snapshot;
verify actual Git/local/remote state rather than preclaiming its commit ID.
This does not authorize automatic commits of subsequent Phase 13B work.
The previous explicitly authorized source
commit/push completed at `cdd74dd53a97b3f21df2cee1b9bfc983d55917cc` on
`main`/`origin/main`; that one transaction does not authorize further commits.
[Hosted CI run 38117411339](https://github.com/manish96170/whisper-py-convert/actions/runs/38117411339)
passed Python 3.9–3.14, quality and clean-wheel jobs; native CI was intentionally
skipped because it is opt-in. That run verifies the earlier committed source,
**not these uncommitted Phase 13A changes**.

Prior handoffs are preserved at:

- `docs/handoffs/SESSION_HANDOFF_PHASE12.md`
- `docs/handoffs/SESSION_HANDOFF_PHASES_0_11.md`

## Constraints and release gates

- `whisper-py-convert.py`, root `Package.swift`,
  `Sources/WhisperAppleTranscribe/` and `windows/` remain untouched. The
  existing STT locale-reservation defect (risk #19) still needs a separate
  explicit repair decision; four native fixtures skip for it.
- No automatic commit/push, tag, package release, signing/notarization,
  cloud export, credential provisioning or model download was performed.
- Base Python runtime dependencies remain empty; Swift has no external
  package dependencies. Core tests/runtime do not require cloud credentials.
- Public packaged release remains blocked on an authorized project license.
  Never infer a license grant from public source availability/dependencies.
- Only the **new native TTS** implementation was deliberately changed for
  output safety. Rebuild/install it from matching source to get the fixes;
  a Python wheel cannot replace an older native binary automatically.

## What was implemented

1. Validated filename-only managed basenames and canonical workspace paths;
   rejected traversal/control characters and unsafe output entries before
   directory creation/speech. Regular replacements require force; symlink,
   directory, FIFO/socket/special outputs are refused even with force.
2. Atomic create-if-absent hard-link publication and explicit regular-file
   rename replacement for native audio and Python text/SRT/manifests.
   No truncation/check-then-delete, partial-copy fallback, or late-writer wipe.
3. Owner-only outputs (`0600`). Native TTS creates an exclusive `0700` staging
   directory, reserves a `0600` extension-preserving file before AVFoundation,
   and verifies inode/mode preservation before PCM writes. Timeout diagnostics
   no longer quote the input sentence.
4. Cooperative per-basename claims. CLI and opt-in Python
   `persist_manifest=True` checkpoint before speech and after each attempted
   stage. Checkpoint inode identities come from owned staging descriptors;
   intervening independent replacement is retained/fails closed.
5. Guarded subprocess acquisition/lifetime; known writers are killed/reaped
   before cancellation releases their claim. Unconfirmed acquisition or
   termination retains the claim. Original exceptions/tags survive OS-error
   conversion, marker/PID cleanup, and failed secondary stderr warnings.
6. Regression tests, updated example checkpoints, 17-file strict typing,
   expanded CI lint inputs, migration/trust/cleanup documentation and local
   overhead measurements.

## Changed files (inspect tracked diff AND untracked additions)

Source/config/tests:

- `.github/workflows/ci.yml`, `pyproject.toml`
- `python/mac_speech/file_io.py` (new)
- `python/mac_speech/{artifacts,cli,logging_utils,workflow}.py`
- `python/mac_speech/tts/engine.py`
- `engines/tts-swift/Sources/MacSpeechTTSCore/Publish.swift` (new)
- `engines/tts-swift/Sources/MacSpeechTTSCore/Synthesize.swift`
- `engines/tts-swift/Tests/MacSpeechTTSCoreTests/PublishTests.swift` (new)
- `examples/narration_workflow.py`
- `tests/unit/test_file_io.py`, `tests/unit/test_workflow_safety.py` (new)
- `tests/unit/{test_cli,test_narration_example,test_tts_engine}.py`

Documentation:

- `PLAN.md`, `README.md`, `CHANGELOG.md`, `python/README.md`
- `docs/{ci,formats,tts-engine,verification,workflow}.md`
- `docs/phase13-hardening.md` (new), this handoff, and the preserved Phase 12 archive

## Independent final verification

Repository Python 3.11.3: **389 passed, four existing STT skips**.
Mocked source suites on 3.12.5/3.13.7/3.14.8: **389 passed each** using
existing pure-Python pytest tooling/PYTHONPATH, not clean installations.
Ruff/package plus explicit safety-test lint pass; strict mypy passes across
**17 source files**, not whole-package strict typing.

```sh
.venv/bin/python -m pytest tests/unit -q -rs
.venv/bin/python -m ruff check python/mac_speech
.venv/bin/python -m ruff check --isolated --select E4,E7,E9,F \
  scripts/audit_dependencies.py scripts/smoke_core.py examples/narration_workflow.py \
  tests/unit/test_dependency_audit.py tests/unit/test_smoke_core.py \
  tests/unit/test_narration_example.py tests/unit/test_installation_lifecycle.py \
  tests/unit/test_file_io.py tests/unit/test_workflow_safety.py tests/unit/test_tts_engine.py
.venv/bin/python -m mypy
```

Framework runtime checks used:

```sh
PYTHONPATH="$PWD/python:$PWD/.venv/lib/python3.11/site-packages" \
  /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
  -m pytest tests/unit --ignore=tests/unit/test_stt_regression_fixtures.py -q
# Repeat with 3.13 and 3.14. Local 3.9/3.10 are still not installed/validated.
```

Native: `scripts/ci_swift.sh` returned **exit 0**, **48 tests passed** and
release build succeeded in isolated caches. Final complete-helper logging
used a 360-second tool limit; a prior 120-second call ran tests/build successfully
but expired around cleanup and was **not** credited as a complete helper pass.
A filtered attempt hit the known TestingMacros plugin omission; no shared
global caches were deleted. Existing CLT/Testing/Sendable warnings persist.

```sh
RUNNER_TEMP="${TMPDIR%/}/opencode" bash scripts/ci_swift.sh
# Set RUNNER_TEMP to the existing approved temp root if this path differs.
```

### Packaging, real workflow and offline checks

- Built a wheel **from its sdist** in a disposable source copy. Byte-compared
  all wheel modules to actual repository source and checked README metadata,
  conditional-only extras and Python-only archive boundaries.
- Extracted-sdist suite explicitly importing extracted modules:
  **378 passed, 15 skips** (11 checkout-only lifecycle checks plus four STT).
- Clean non-editable 3.11.3 wheel: local `--no-index --no-deps` install,
  `pip check`, engine-free and updated-native smoke passed.
- The updated native engine was separately built/retained from current source.
  Real TTS-only workflow produced audio/checkpoint at `0600`, removed its
  owned marker, and refused a same-name repeat without altering audio.
- Actual native checks used installed ordinary system voices, a minimal
  HOME/PATH/TMPDIR/locale environment, Python audit-hook network denial and
  macOS `sandbox-exec` network denial. No real STT/export/account was invoked.
- Actual parent-only SIGINT, post-constructor tracing and unknown-handle
  construction tests use harmless synthetic children, not paid speech/models.
  The reviewer independently checked actual failed stderr `.write()` behavior.
- Measured 30 writes each at 1 KiB/1 MiB on the local M1 Pro/macOS 27.0.1
  temp filesystem: hardened median **1.365/1.935 ms**, plain temp/replace
  **0.667/0.986 ms**; maxima **3.679/4.790 ms** for hardened writes.
  This is measured overhead, not a timing threshold or recommendation to
  use the unsafe baseline. See `docs/phase13-hardening.md`.

Evidence/artifacts are under the approved temp root at `phase13-tlkdpesi/`:
`final-swift-check.log`, `final-native/`, `verified-source/`, `verified-dist/`,
`verified-extracted/`, `clean/`, `real-scene/`, `io-benchmark.json`.
Temporary directories can be removed later by the OS; these are **local test
outputs**, not published or authenticated release artifacts.

```text
abfbb7d0b91f65023c2926b3f8fb7f9a63c2c0f66ec3256e96459d5c93a021a2  mac_speech-0.1.0-py3-none-any.whl
d0825cd69f082c72b0602bdb541be1e60c2f4f1beca46223db3526502764d38f  mac_speech-0.1.0.tar.gz
```

## Remaining limitations

The parent directory must be trusted; inode checks are not a hostile atomic
compare-and-swap or protection against in-place mutation. Publication is
**file-wise**, not an all-artifact transaction or power-loss durability promise.
Hard-link support is required; unsupported filesystems fail closed.
Crashes/unconfirmed children can leave markers/private staging state. A stored
parent PID alone cannot prove all child writers stopped. Never blindly remove
or bypass an active/unverified claim; use a fresh basename instead.

Broader privacy/log redaction, automated retention/audit trails, batch queues,
GUI/services/watchers, neural engines and extra providers remain unscoped
Phase 13 candidates. Old-macOS/Intel native execution, real provider uploads,
full current native STT success and project-license clearance remain unverified
or blocked as previously documented. Earlier deferred boxes remain unchanged.

## Next three actions

1. Review the uncommitted diff and rerun checks. Rebuild/install matching TTS
   with `./install.sh tts`, then run the safe TTS-only example in
   `docs/phase13-hardening.md`; choose fresh scene basenames.
2. Complete and independently verify the newly authorized Phase 13A source
   commit/push. The older `cdd74dd` authorization was not reused; the user
   gave a new request after testing the audio. Do not include later Phase 13B
   implementation in this transaction or commit it automatically.
3. Choose/authorize the project license before public packaged release.
   Separately authorize the protected STT locale repair for full STT use,
   or choose one justified optional next capability; do not implement the
   entire open-ended backlog or download a model automatically.
