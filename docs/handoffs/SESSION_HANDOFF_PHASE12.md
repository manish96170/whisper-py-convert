# Historical handoff — Phase 12 integration and authorized source push

**Archive notice:** this captures the pre-commit documentation checkpoint.
The source transaction later completed as `cdd74dd` and its hosted CI passed.
Read `docs/SESSION_HANDOFF.md` for current Phase 13A outcomes; the prior
instructions below are historical, not authorization to restart old work.

**Written:** 2026-10-11. Read `PLAN.md` and this file in full, inspect actual
Git status/diff, and independently rerun the checks before trusting this
summary. The prior handoff is preserved at
`docs/handoffs/SESSION_HANDOFF_PHASES_0_11.md` as historical evidence, not
current instructions.

## Current objective and limits

Phase 12's packaging/documentation/operational implementation is integrated
and locally verified. Its task boxes are checked with evidence in `PLAN.md`.
**Public packaged release is blocked:** no authoritative project license exists.
During Phase 12 implementation, no license grant, commit, tag, release, upload,
signing/notarization, account provisioning, cloud export, or model download was
performed. The subsequent source commit/push is now explicitly authorized
below. Hosted-CI outcomes are not inferred from local verification.

## Explicitly authorized Git transaction

The user subsequently requested two agents: commit/push and documentation
refresh. They confirmed all reviewed pending Phases 0–12 toolkit source/docs,
direct push to `origin/main`, and **no PR**, force-push, package release, or
license grant. Approved commit message:

```text
feat: 🎸 add local mac-speech toolkit and phase 12 packaging
```

The documentation agent reviewed 29 maintained Markdown files and updated 22;
main integrated this handoff and transaction status. Historical evidence and
protected Windows documentation were preserved. The Git agent audited source
paths and excluded generated artifacts/caches and apparent credentials.
Main reran the repository suite (322 passed, four known native STT skips),
links/fences/snippet syntax, Ruff and scoped strict mypy after the refresh.
The updated packaged README/docs were rebuilt into a wheel from the sdist;
that extracted-sdist suite passed 311 tests with 15 expected skips. A fresh
non-editable wheel environment passed `pip check`, engine-free diagnostics
and real TTS-only smoke with credential-free, Python/native network denial.
Commit/push execution follows this documentation checkpoint: verify actual
results with `git log -1`, `git status --short --branch`, and the remote ref.
This file is part of the commit itself, so it does not preclaim its own future
commit ID or successful push. A source push does not clear the license gate
for public wheel/sdist/native-binary releases.

Do not automatically start Phase 13 or fill earlier-phase deferred boxes.
Any next implementation/legacy STT repair needs a separate explicit scope.
There are no outstanding Phase 12 reviewer findings: the separate reviewer
checked the corrective patches and reported all findings resolved.

## Hard constraints still in force

- Do not modify `whisper-py-convert.py`, root `Package.swift`'s preserved
  STT target, `Sources/WhisperAppleTranscribe/`, or `windows/` without an
  explicit, separate decision.
- No automatic Git commits without explicit authorization. The user authorized
  the current transaction only; it is not permission for later commits/releases.
  Original dirty/untracked work was preserved and is intentionally included in
  the approved complete toolkit source commit.
- Core speech/diagnostics must not require cloud credentials or paid services.
  Offline native speech assumes installed toolchains/engines/Apple assets.
  Never trigger model fallback/downloads as a packaging smoke test.
- No model download without explicit approval for that model/version.
- No unannounced remote exports; the only export exercised here was an
  explicit copy of synthetic audio to another temporary local directory.

## Baseline independently checked

At session start, branch `main` had exactly three tracked modifications:
`.gitignore`, `README.md`, `install.sh`; Phase 0–11 additions were untracked.
`git diff` matched the historical handoff. Baseline Python: 188 passed,
four native STT skips; Swift: 39 passed; release build, legacy script syntax
check, and doctor succeeded. Machine: M1 Pro/16 GiB, macOS 27.0.1 arm64,
Swift 6.4, Python 3.11.3, Command Line Tools only.

Hashes taken before edits confirmed that all protected STT files, root
Swift manifest, native TTS sources, and `install.sh` were unchanged by this
session. The installer still has prior-session tracked changes; do not
mistake those for new Phase 12 edits or discard them.

## Delegation and integration

The six handoff workstreams were dispatched separately with the `subagent`
tool: CI, version checks, packaging/signing, dependency inventory/SBOM,
lifecycle/release docs, and narration example. Main integrated metadata,
artifact boundaries, offline/clean-install checks, review corrections,
final tests and plan/handoff updates. A separate read-only Phase 12 reviewer
reviewed actual files/tests and subsequently rechecked fixes.

Important integration corrections:

- TTS already checked numeric protocol mismatches. It now strictly rejects
  missing/string/float/bool/malformed versions, without coercion/tracebacks,
  and gives a synchronization remedy. Legacy STT stays unversioned.
- Every installer mode installs the legacy wrapper/symlink. `tts` skips only
  the native STT build. Custom XDG paths are not automatically discovered by
  every adapter; documentation describes actual overrides/limitations.
- The narration sample rejects empty/invalid timed cues instead of reporting
  successful empty SRT. Audio and stage manifests remain on downstream failure.
- The sdist includes audit/smoke/narration helpers required by its tests.
  It is **not** a full native-source repository archive.
- Dependency scanner malformed license declarations produce actionable exit
  2; missing project-license metadata intentionally fails `--check` with 1.
- CI/docs now agree on 16 strict targets, explicit helper lint, and a separate
  wheel-from-sdist clean-install job. Native CI is manual/provisioned, not an
  automatic hosted result.

## Exact Phase 12 changed files

Existing files modified:

- `.gitignore`, `README.md`, `PLAN.md`, `pyproject.toml`
- `python/README.md`
- `python/mac_speech/native_protocol.py`, `python/mac_speech/tts/engine.py`
- `python/mac_speech/export/gdrive.py`, `python/mac_speech/stt/webvtt.py`
  (the latter two: unused import removal only for lint)
- `tests/unit/test_native_protocol.py`, `tests/unit/test_tts_engine.py`
- `docs/protocol.md`, `docs/configuration.md`, `docs/platform-support.md`
- `docs/installation.md`, `docs/workflow.md`, `docs/risk-register.md`
- This handoff; its previous contents were moved to the historical path above.

New files:

- `.github/workflows/ci.yml`, `CHANGELOG.md`, `MANIFEST.in`
- `docs/ci.md`, `docs/packaging.md`, `docs/sbom.md`, `docs/verification.md`
- `docs/releasing.md`, `docs/release-notes-template.md`
- `docs/decisions/ADR-002-packaging-and-distribution.md`
- `examples/README.md`, `examples/narration_workflow.py`
- `scripts/ci_swift.sh`, `scripts/audit_dependencies.py`, `scripts/smoke_core.py`
- `tests/unit/test_dependency_audit.py`, `tests/unit/test_smoke_core.py`
- `tests/unit/test_narration_example.py`, `tests/unit/test_installation_lifecycle.py`

These were uncommitted at the original Phase 12 verification snapshot; the
current authorized transaction includes them. Inspect Git for the current
tracked/committed state. Before staging, `git diff` alone cannot show untracked
contents; inspect the explicit source manifest. Do not infer future commit
authorization from this transaction.

## Final verification and commands

From the repository root:

```sh
.venv/bin/python -m pytest tests/unit -q -rs
# 322 passed, 4 skipped: unchanged Apple STT locale-reservation issue (risk #19)

.venv/bin/python -m ruff check python/mac_speech
.venv/bin/python -m ruff check --isolated --select E4,E7,E9,F \
  scripts/audit_dependencies.py scripts/smoke_core.py examples/narration_workflow.py \
  tests/unit/test_dependency_audit.py tests/unit/test_smoke_core.py \
  tests/unit/test_narration_example.py tests/unit/test_installation_lifecycle.py
.venv/bin/python -m mypy
# Ruff passes; strict mypy passes across 16 source files (not whole-package strict typing)

RUNNER_TEMP="${TMPDIR%/}/opencode" bash scripts/ci_swift.sh
# Set RUNNER_TEMP to an existing approved temp directory if that path differs.
# Main used the environment's approved opencode temp root directly.
# 39 Swift tests passed, release build succeeded; caches/scratch isolated.

python3 -m py_compile whisper-py-convert.py
.venv/bin/mac-speech doctor
# Syntax check passes; doctor reports both discovered engines available here.

.venv/bin/python scripts/audit_dependencies.py --group runtime --check
# Expected exit 1: unresolved project license; base dependencies remain empty.
```

The main session also reran the final mocked suite on local Framework
interpreters **3.12.5, 3.13.7, 3.14.8**, 322 passed each:

```sh
PYTHONPATH="$PWD/python:$PWD/.venv/lib/python3.11/site-packages" \
  /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
  -m pytest tests/unit --ignore=tests/unit/test_stt_regression_fixtures.py -q
# Repeat with 3.13 and 3.14. These reuse pure-Python pytest tooling via PYTHONPATH;
# they are source runtime checks, not fresh-venv installation checks.
```

### Artifact/clean-room evidence

Main build tooling: build 1.6.1, setuptools 84.0.0, wheel 0.48.0 in the
development venv; none became a base runtime dependency. Builds used a
disposable source copy and `python -m build --no-isolation`, producing the
wheel **from its sdist**, not an independently built wheel from the checkout.

- Final wheel modules were byte-compared to actual repository Python modules.
- Final sdist helper/SBOM files were byte-compared to actual repository files.
- Metadata, conditional-only extras, embedded unresolved-license warning,
  artifact boundaries and wheel RECORD hashes were inspected.
- Extracted-sdist suite, explicitly importing its extracted `python/` package:
  **311 passed, 15 skipped** (11 checkout-only lifecycle tests plus four STT).
- Clean non-editable 3.11.3 wheel install outside source, `--no-index --no-deps`:
  `pip check`, engine-free and real TTS-only smoke all passed.
- Real TTS-only installer ran under temporary HOME/XDG paths. No STT binary
  was installed, while the always-installed legacy script/symlink was present.
- Native offline smoke used an environment containing only HOME/PATH/TMPDIR/
  locale, plus Python socket audit denial and macOS `sandbox-exec` network
  denial. WAV frames, manifest privacy and overwrite refusal passed. An
  independent socket probe showed OS sandbox permission denial.
- Documented real binary backup/uninstall/restore and Python wheel
  uninstall/restore ran in those temporary paths; legacy/unrelated artifacts
  and current source were retained. All three installer modes and dirty-tree
  rollback have 11 additional isolated fake-Swift lifecycle tests.
- Real example TTS-only WAV: mono, 22,050 Hz, 2.823 seconds; repeat refused.
  Its explicit local export preview/copy preserved the source/checksum.

Local artifacts/evidence remain under the approved temporary root in
`phase12-9jpyw0e1/` (`verified-dist`, `verified-python-source`,
`verified-extracted`, `clean-venv`, `isolated-home`, `verified-build.log`).
They are **not published releases** and may be removed by later OS temp cleanup.

Historical Phase 12 local artifact SHA-256 values (before the later documentation
refresh changed packaged inputs):

```text
abe2ae1d7f499e802b1cd5355466df7fe8c943bbad7247393b57501bd4230fec  mac_speech-0.1.0-py3-none-any.whl
d3a928571100dbeac6edba0522bb0f86c9067a0e4b0a553f1e5623a60c1bded1  mac_speech-0.1.0.tar.gz
```

Hashes identify these earlier local outputs, not an authenticated or committed
public release or the later refreshed documentation revision. Packaged README
and documentation changes require a rebuild; rerun builds/checks for any actual
publication and record that build's own hashes/source revision.

The subsequent documentation-refresh verification outputs are under the
approved temporary root at `git-docs-verify-iir227vj/` (`dist`, `source`,
`extracted`, `clean`, `build.log`). Their metadata embeds the updated package
README, and their own locally verified SHA-256 values are:

```text
17d19d8b7f0bd635d63f58cf2587ee3b43f9c95c8b9d5624fd50e6e023d0d011  mac_speech-0.1.0-py3-none-any.whl
4792ade05fbe2d3a9f9b61d6aa5d7d633b989e9285b20bc605ad17c05f4acbd6  mac_speech-0.1.0.tar.gz
```

These were built before the authorized source commit and are local test
outputs only, not published or authenticated releases.

## Remaining risks / unverified claims

- **Missing project license**: public packaged release blocked. Rights holder must
  decide/authorize license text; do not infer it from MIT/Apache dependencies.
- Hosted Actions outcomes have not been verified at this documentation checkpoint;
  the requested source push schedules automatic Python CI. Python 3.9/3.10 remain unverified locally.
  Native Swift CI requires a human-provisioned Swift 6.4 macOS runner and
  manual dispatch; automatic hosted coverage is explicitly deferred.
- macOS 13/14 TTS and Intel native execution are still not runtime-tested.
  Swift 6.4 source build requirements differ from runtime deployment floors.
- Existing Apple STT reservation leak/5-locale quota remains untouched (risk
  #19); four real transcription fixtures skip. Native STT success was not
  claimed from availability or negative-input smoke tests.
- Existing Swift Sendable/CLT framework path and Testing runtime-floor warnings
  persist; builds/tests succeed. The helper handles only known macro/plugin
  compilation flakiness with a narrow retry and never deletes shared caches.
- `sandbox-exec` is deprecated and macOS-only. Python audit denial alone does
  not prove native subprocess network isolation; docs distinguish them.
- SBOM is a direct source inventory and offline metadata report, not a
  resolved transitive standards-compliant release SBOM or vulnerability scan.
  No advisory scan was performed; optional integration live-provider limits
  from earlier phases remain unchanged.
- No signed/notarized native release exists. Local/ad-hoc builds do not
  authenticate a publisher or bypass Gatekeeper/permission requirements.

## Next three concrete actions (human-controlled release gates)

1. Verify the explicitly requested source commit/push against actual Git/local
   and remote state and rerun checks. Preserve any remaining work; do not reset,
   clean, or check out an old revision over user changes.
2. Explicitly resolve/authorize the project license and intended publication
   scope, then review package metadata/license/artifact contents again.
3. Inspect the automatic hosted CI scheduled by the source push and, only when
   provisioned/selected, the manual native job; record actual outcomes using
   `docs/releasing.md`, not assumptions from a commit or local test result.
   Do not proceed to Phase 13 or repair protected STT without a separate request.
