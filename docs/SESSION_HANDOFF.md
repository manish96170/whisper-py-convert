# Session handoff — explicit Apple asset setup and live ownership proof

**Source transaction checkpoint:** the user has now separately requested
"commit and push" for this reviewed follow-up, retaining the main/no-PR workflow
to `manish96170/whisper-py-convert`. Current GitHub account/access and matching
local/origin baseline `4769606` were independently verified. Commit execution
follows this documentation checkpoint; verify actual Git/remote state rather
than infer a new hash from this file. Only reviewed source/tests/docs are included;
generated/private artifacts, installed binary replacement, asset downloads,
new real maintenance actions, full TUI and future automatic commits remain excluded.

**Latest checkpoint (2026-10-12):** the user approved a temporary no-download en_CA
reacquisition after the stopped release window, plus generic pre-analysis language
readiness/setup guidance for Python/CLI users. No French download, persistent CA
re-pin, installed-binary replacement, new commit/push or full TUI was authorized.
Read PLAN.md and this file in full; independently inspect the dirty tree and results.
Published baseline remains `4769606`; these changes are **uncommitted**.

## Current result

The metadata-only en_CA reservation made cached assets usable, without creating
an installation request. Real owned tests now passed: success exit0, invalid
media exit1 (AVFoundation/-11800), closed output exit1 (POSIX/32), and SIGTERM exit130
after analyzeSequence requested its first real input (not merely admission).
Every run required a new reservation, emitted actual en_CA acquired/released events,
fully joined cleanup/readback and returned to **the same four** pre-existing
reserved/installed locales: en_AU/en_GB/en_IN/en_US. Seven additional owned recordings
and sequential switching among all five English regions also passed. No other
pre-existing release, install/download or persistent re-pinning occurred.
Independent retained-evidence review recomputed the hash, audited each raw case,
transcript/word intervals and readback, and found no new blocker. It supports
**local resolution of risk #19's two original source defects** on this tested
Mac/SDK/artifact. It did not rerun native tests or measure sustained hardware
inference/OS-wide networking. Operational/deployment limits remain; code is uncommitted.

Owned proof: approved temp `stt-owned-proof-w5ykvv8x/summary.json`/case JSON,
artifact SHA256 `58a1fa9259852c4fa78ba3a82475452b0fe96750fa167977856062090dba1846`.
Reacquisition trial: `stt-approved-reacquire-9uimsvhl/result.json`; repeat/switch
evidence: `stt-owned-repeat.json`. SDK en_CA may still report uninstalled while
unreserved at idle; successful binding proved physical-cache usability **in this
window**, not indefinite retention or a guarantee on other Macs.

## Generic setup behavior

`AssetSetup.swift` provides `--install-assets --language LOCALE` read-only preview;
only matching `--confirm-download SUPPORTED_LOCALE` allows explicit setup. It may
reuse cached data or download missing Apple models; success intentionally retains
the supporting reservation for asset subscription. Failure/cancellation/report-output
failure cleans only uniquely new ownership. Validate complete post-reserve state
before the installer; do not reset unknown state.

Native transcription now forbids automatic installation requests/downloads by
default and checks readiness after reservation, before media/analyzer setup.
Stronger `--require-installed-assets` still checks before allocation as well.
`--no-asset-download` explicitly names the reservation-first no-installer path.
Inventory capability fields let the Python adapter reject old/unsafe helpers.

Python `engine.py` now preflights the EXACT helper used by direct JSON or protected
legacy-script text/SRT. Missing assets produce requested/resolved locale and a
shell-quoted explicit setup command, before analysis. A diagnostic native process
is needed to query Apple; do not claim zero processes launch. Other backends stay
unchanged. Real French read-only preview/wrapper refusal was tested, with no French
analysis/download or reservation change (`stt-french-preflight.json`).

Docs: `docs/apple-asset-setup.md`. The legacy script/Windows/TTS/package platform,
product and empty base dependencies remain unchanged. First-use automatic Apple
downloads are an explicitly approved behavior change, not preserved legacy behavior.

## Checks and review

Main: **61 Swift tests/release build**, **574 Python/four opt-in skips**, **578 with
Apple opt-in/zero skips** (includes real text/JSON/segment+word SRT), Ruff/mypy
(18-source scope)/legacy py_compile. Independent TTS helper results are recorded
in verification. Initial read-only French script used a missing optional JSON key;
corrected `.get` handling and reran without mutation.

Reviewer closed two medium setup cases: report publication/final cancellation now
stay inside ownership lifetime, and complete inventory preservation is checked
before installation. Independent 61 Swift tests, 131 Python preflight/engine mocks,
release build and repros passed; no remaining medium/high findings in that scope.
New input observation is opt-in and emits only on actual input consumption.
The real owned-evidence review/outcome is in `docs/verification.md`.

## Next three actions

1. Complete and verify the newly approved source commit/push, then check hosted
   CI separately from local native evidence. Review remaining operational caveats; do not relabel
   cached-data behavior as guaranteed offline retention or SIGKILL cleanup.
2. Obtain separate approval for installing the newer helper or any future push. Old
   installed engines will not gain these guarantees from a Python-only update.
3. Keep TUI work proposal-only (`docs/tui-proposal.md`) unless implementation is
   separately approved; reuse readiness/confirmation/job ownership safely.

---

# Historical checkpoint — stopped en_CA window and maintenance safeguards

**2026-10-12: en_CA window approved; release verified, validation STOPPED on asset
unavailability. No download/re-pin/new commit/push approved.** Read this file and PLAN.md in full, inspect actual Git/diff and rerun
checks. Verified starting tree was clean `main` at
`4769606b3d3aa9a38fa4b59dedc4b75d49b721cc`; its GitHub CI `38213808150` succeeded.
The old handoff below is retained as a historical checkpoint, not current permission.

The user confirmed **en-US default, all English regions preserved for other
users**, and approved the bounded Terra/Opus maintenance recommendation. Do not
classify a non-default locale as unused or automatically evict it.

**Latest approval/result:** the user approved one temporary en_CA release and
guarded native tests, stopping on unexpected state, with no downloads or automatic
re-pinning. No native STT invocation was running at preflight. The SAME built
executable reported full5/5/all installed, then the one confirmed en_CA release
returned true and verified non-target preservation. Its after-report was **4/5**:
`en_AU,en_GB,en_IN,en_US`; all four installed. Exact en_CA is still supported but
SDK installed status became **false**, confirmed by read-only per-region status.
The agent STOPPED before any owned-transcription test, reacquisition, installation
or re-pinning. Do not infer physical file deletion from that status. Canadian
offline availability is not currently confirmed. Risk #19 remains partial.

Actual evidence: approved temporary `stt-approved-window-q645k4du/` contains
`fingerprint.json`, `before.json`, `release.json`, `stopped-readonly-status.json`.
Binary SHA256: `4bce6e5aaf6502e2a91231ca49eeec465c82e265c0e3a4f40b0f11fc996f76b9`;
identifier `whisper-py-convert-apple`, normal linker/ad-hoc signing unchanged.
No rebuild/copy/rename/re-sign occurred between action and readbacks.

To make later owned evidence unambiguous, require-new validation now emits opt-in
stderr `Validation:` JSON (actual acquired/released locale, analysis entry/finish),
never audio paths/transcript. Entry is an admission boundary, not proof an analyzer
began work; marker-triggered cancellation alone cannot prove active-analysis cleanup.
The label was corrected after final review (no owned runtime test had used it).
These are not a general TUI protocol. Mock test added;
**47 Swift tests and release build passed** before the real action. Installed
binaries still were not replaced. Normal en_CA invocation might attempt installation;
do not use it as an unapproved recovery probe.

User also requested future TUI ideas, not full implementation. `docs/tui-proposal.md`
captures STT/TTS/jobs/assets tabs, optional dependencies, safe owned-process controls,
stale snapshot handling and preview-first maintenance. No TUI/daemon/cache/ledger
or arbitrary process control was implemented.

## New implementation scope

- `ReservationMaintenance.swift`: locked inspect/unconfirmed preview; an actual
  exact single-target release requires matching confirmation + unused/quiescent
  client acknowledgement; default en_US needs an extra flag. No release-all,
  aliases, retries, installs, reserve or rollback. Readback checks target absence
  and non-target preservation, returning a structured report/nonzero verification
  failure. The one later user-approved confirmed en_CA release is recorded above.
- `Reservation.swift`: complete owned cleanup/readback is cancellation-isolated
  and fully awaited, including primary error preservation and late cancellation.
  Optional installed/exact/new validation seams prevent accidental downloads or
  borrowed/fallback success being counted as owned cleanup evidence.
- `main.swift`, `AppleInventory.swift`: additive native-only flags, locked existing
  inventory inspection, exact asset-status checks and a no-install-request guard.
  Normal defaults/first-use installation/transcript/text/SRT semantics are preserved.
- New `MaintenanceSafetyTests.swift`; narrowly extended adapter stage-error tests.
  No persistent worker/cache, ledger, daemon or automatic pruning was introduced.

Cancellation shielding addresses a documented-contract uncertainty, **not a
reproduced Apple defect**. Release can unsubscribe assets; post-release availability
and reversibility are not guaranteed. No extra region assets are downloaded to test.

## Verification and remaining gates

Baseline default Python suite independently reran **483 passed/four opt-in skips**.
Final counts: **491 Python/four explicit opt-in skips**, **495 passed/zero skips
with Apple opt-in**, **46 Swift STT tests/release build**, **48 independent TTS
tests/release build**, Ruff/mypy (18 source files)/legacy py_compile. Five English
regions pass strict offline word JSON; five previews and locked inspection preserve
the inventory. New-owned validation rejects borrowed reuse as intended. Current
native/reviewer results are recorded in `docs/verification.md`.
Initial Swift compilation found an async short-circuit autoclosure and throwing
`#require` macro inputs; both were corrected before final runs. No shared caches
were purged. Build/test artifacts are under approved temporary `opencode` paths
`stt-maintenance-*`, not Git; installed binaries were not overwritten.
Reviewer found/closed two medium mock cases: confirmed absent/alias targets now
refuse before mutation, and newly appearing post-release reservations are retained
and reported rather than silently succeeding. Integrated asset-loss tests cover
release and acquisition, installation-call refusal and owned cleanup. Independent
closure: **46 Swift tests passed**, 48 adapter tests passed, byte-matched source,
no remaining medium/high findings in reviewed scope. Evidence under the approved
temporary root: `maintenance-closure-5bfersgk/closure-test.log`.

The earlier safeguards-only snapshot had full5/5; the approved action above now
leaves4/5 with exact en_CA uninstalled. Risk #19 stays partial: real true acquisition/
release after success/failure was not run because the availability guard stopped
the window. A new recovery/reacquisition or installation action needs further
approval; do not proceed from the now-ended window. Mocked releases are
not native recovery evidence. Older/non-cooperating clients and abrupt death remain
limitations; do not add PID-based automatic recovery.

## Next actions

1. Inspect this uncommitted diff and verify the final tests/reviewer outcome in
   `docs/verification.md` before any further work.
2. Report the exact stopped state and ask for separately scoped en_CA recovery:
   metadata-only reserve/readback or explicit installation (if needed), with no
   promise that re-reserving restores assets. No automatic rollback/download.
3. Obtain separate approval for a future commit/push or installed-engine update;
   prior source publication and this implementation approval do not grant those.

Details/commands: `docs/stt-reservation-maintenance.md`. Changed scope is the native
STT helper/tests, narrow Python failure mapping/tests, PLAN and affected docs only.
Legacy script, Windows, TTS, root platform/product requirements and base runtime
dependencies remain unchanged.

---

# Historical handoff — original Apple STT risk #19 maintenance and source push

**Current checkpoint: 2026-10-12. Partial; combined commit/push now authorized.** Read `PLAN.md`
and this file in full, then inspect Git/diff and rerun checks independently.
The previous Phase 13B handoff is retained verbatim below as historical evidence,
not active authorization. Current baseline was independently verified clean on
`main` at `ad414abf9dce8b0055aa8a1810355aacb2e1bc0c`.

**Latest user decision:** commit and push all reviewed repository source/docs/tests,
including licensing prepared by the other session, to
`manish96170/whisper-py-convert` on **main, no PR**. GitHub authentication/access
was independently verified as `manish96170`; origin/main still matched the stated
baseline at preparation time. This is a pre-commit checkpoint; transaction execution
follows it. Verify actual Git/local/remote state, not an inferred commit hash.
Generated/private artifacts, reservation recovery, new queue services, package
releases and future automatic commits remain excluded.

## Current scope and design

The user separately authorized narrow STT reservation maintenance. Both original
defects are repaired: `reserve == false` reuses, never means unsupported; actual
newly-owned reservations are released after awaited lifetime cleanup. Supported
equivalent locale is resolved using Apple's API; named Speech error codes classify
unsupported/capacity failures and preserve framework domain/code. One cooperating
per-user flock serializes all locales through analysis, output and cleanup. No
app-global reference-counting assumptions or automatic stale eviction.

Analyzer/results failures stop and drain owned work before reservation release.
SIGINT/SIGTERM request cooperative cancellation, with awaited stop/cleanup before
exit; stdout/diagnostics use bounded nonblocking writes. Abrupt death and non-cooperating old
clients cannot be covered. Existing transcript/CLI/timestamp contracts, legacy
Python file, Windows, native TTS and installation/dependency boundaries are preserved.

## Current evidence and blocker

Baseline Python: **431 passed, four skips**, all hiding the incorrect unsupported
message. New explicit opt-in/installed-asset fixtures no longer catch this as skip.
Real fixtures: **4 passed** (text, JSON, segment SRT, word SRT). Seven separately
synthesized en-US recordings passed; switching among en-AU/en-CA/en-GB/en-IN/en-US
passed. Invalid media failed after reservation reuse with provider error
`AVFoundationErrorDomain/-11800`. Same executable's inventory remained unchanged
after every run. No new assets downloaded.

Read-only inventory **before native testing**: available/installed en-US,
`en_AU,en_CA,en_GB,en_IN,en_US`, capacity **5**. This is a device-specific asset
reservation capacity, not a request quota. The compiled executable remains
`whisper-py-convert-apple`, linker/ad-hoc signed; no rename/re-sign evasion.
No existing entries were released. These native runs exercise **borrowed**
reservations. Real true-acquisition/owned release after success/failure remains
blocked by the full inventory and needs a free slot or separately authorized
targeted recovery. Do not mark risk #19 resolved based only on mocks/reuse.

Quality gates: **480 Python passed/four explicit opt-in skips**, or **484 passed/
zero skips with native opt-in** at the STT-only snapshot; latest combined checkout
has **487 passed/zero skips**, including three separately added licensing tests.
The latest default (native opt-in unset) suite is **483 passed/four opt-in skips**.
**26 root Swift tests/release STT build passed**, **48 independent TTS tests/release
build passed**, Ruff/mypy (18-file scope)/legacy py_compile passed. Signal/output checks include borrowed-state
SIGINT/SIGTERM, closed stdout, **stalled unread stdout** (65,536 buffered bytes,
exit130 without draining), and broken stderr (exit1, no abort). Full unread stderr
also uses bounded best-effort diagnostic writes, dropping bytes on backpressure.
Cancellation may leave partial stdout bytes; consumers must check exit status.

Final quality/test counts, signal/output checks and reviewer findings are updated
in `docs/verification.md`; detailed API/design/state evidence is in
`docs/stt-reservation-repair.md`. Scratch artifacts live beneath the approved
temporary `opencode` root (not Git/public releases): `stt-risk19-release`,
`stt-risk19-debug-retry`, `stt-risk19-real-5n3fbvkf`, and `stt-risk19-*.log`.
The initial XCTest attempt was blocked by CLT's missing XCTest; tests use Swift
Testing. A later known TestingMacros failure used an explicit installed-plugin
retry with isolated caches. An initial gate race (Foundation post-create directory
permissions) was fixed with atomic `mkdir(0700)` and rechecked. No shared caches
were removed. The first TTS helper attempt hit its execution timeout; the complete
longer-timeout run passed **48 tests and release build**.

## Exact current changed paths

Independent review identified broken/stalled diagnostic writes, blocked-stdout
cancellation, the final-check/analyzer-stop join race, and unexpected automatic
installation reservations. Fixes use bounded nonblocking diagnostics/output,
synchronized stop admission with joining on both outcomes, and a post-body
inventory check that reports/retains ambiguous extras while releasing only
known ownership. Tests exercise each case, including a delayed stop and full
open stderr. The final reviewer recheck is recorded in `docs/verification.md`;
none of this establishes live newly-owned cleanup with the full inventory.
Reviewer closure independently reran **26 mocked Swift tests, all passed**, with
byte-matched source/tests and no remaining medium/high findings in reviewed scope.
Its full-open-unread stderr help repro passed four times without draining the
pipe. A stale full-flags assertion was corrected to compare configurable
`O_NONBLOCK`; both main and reviewer reran the green suite. Closure evidence:
`risk19-rereview-6be30hbf/closure-test.log` under the approved temporary root.

- `Sources/WhisperAppleTranscribe/main.swift`
- New `Sources/WhisperAppleTranscribe/{Reservation,ReservationGate,AppleInventory,AnalyzerStop,GracefulSignals,Output}.swift`
- `Package.swift` (add isolated root STT test target, preserve platform/product)
- New `tests/WhisperAppleTranscribeTests/{ReservationTests,AnalysisLifecycleTests}.swift`
- `python/mac_speech/stt/engine.py`
- `tests/unit/test_stt_engine.py`, `tests/unit/test_stt_regression_fixtures.py`
- New `tests/unit/test_stt_regression_prerequisites.py`
- `ARCHITECTURE.md`, `PLAN.md`, `docs/{architecture,installation,platform-support,risk-register,verification,SESSION_HANDOFF}.md`
- New `docs/stt-reservation-repair.md`

No commit/push occurred during implementation; the user has now separately
authorized the combined source transaction above. Installed binaries were not overwritten;
use the scratch release binary or rebuild before testing this code. New fixture
override `MAC_SPEECH_TEST_APPLE_BINARY` uses an unchanged scratch legacy-script
copy with a sibling symlink, so text/SRT and direct JSON select the same binary.

**Concurrent user/session work discovered during final verification:** `LICENSE`,
`docs/licensing.md`, `MANIFEST.in`, `pyproject.toml`, `README.md`, `python/README.md`
have new licensing/metadata edits, outside STT repair ownership. They were left
untouched, not discarded. Consult current licensing docs rather than historical
missing-license assertions. At the initial STT-only checkpoint those packaging
changes had not yet been validated by the main session.
The subsequent combined pre-commit review **did** validate their license metadata,
text inclusion and disposable wheel-from-sdist build/install. It passed **472
tests/15 expected skips** in the extracted sdist, exact license inclusion and
30-module byte comparison, offline inventory, clean wheel/pip check and engine-free
socket-denied smoke. This is engineering evidence, not legal or release clearance.
The combined reviewer approved the final doc/CI-example corrections with no new
blocking issue and byte-matched 64 runtime/test/license/packaging files against
its tested snapshot. Its retained `combined-precommit-package-__64sgsn/` evidence
under the approved temporary root predates doc-only corrections, not a final release.
Later external changes include licensing-related documentation and
`tests/unit/test_project_license.py`; inspect the full dirty tree and preserve
that session's work rather than treating every current diff as STT-owned.

## Next three actions

1. Commit/push the now-authorized complete reviewed tree on main, excluding
   generated/private state; verify remote commit and hosted CI separately.
2. Ask the user whether to authorize a narrowly selected, confirmed-unused
   reservation release **in this executable's identity under the gate**, then
   test real new ownership/success/failure cleanup without downloading assets.
   Do not implement destructive recovery or purge state without approval.
3. Rebuild/install native STT from reviewed source when requested. A source push
   does not update installed binaries, publish packages, authorize new queues,
   or establish older/native platform coverage. TTS/unrelated phases remain outside
   the maintenance implementation scope.

Fresh pre-commit verification again passed **483 Python/four opt-in skips** or
**487 Python/zero skips with Apple opt-in**, **26 Swift STT tests/release build**,
Ruff/scoped mypy/legacy py_compile. **Six simultaneous direct calls** all succeeded
in 2.651 s with borrowed inventory unchanged; the existing gate admits one active
STT operation at a time, not five active operations. Main's separate TTS helper
is recorded in `docs/verification.md`. No source/runtime repair expansion was
needed; active license/authorization docs and setuptools77+ build examples were
reconciled before staging. This combined transaction additionally includes the
licensing paths listed above and related docs/tests, plus the minimal CI build-tool
example update in `.github/workflows/ci.yml`.

---

# Historical session handoff — Phase 13B bounded batch synthesis

**Written:** 2026-10-11. Read `PLAN.md` and this file in full; inspect actual
Git status/diff and independently rerun checks before trusting the summary.

## Outcome and scope

**Phase 13B is locally complete**, with separate reviewer findings fixed and
rechecked. It implements the Phase 13 candidate for queueing/bounded batch
synthesis, not every optional GUI/service/model/storage/privacy enhancement.
Batch generation is **TTS-only WAV**: no STT/alignment, playback, exports,
watchers/daemon, voice provisioning, neural engine/model download or new
runtime dependency is implicit.

**Pre-commit verification checkpoint.** The user subsequently explicitly
requested "commit and push Phase 13B", retaining the existing `main`/no-PR
choices. The approved scope is reviewed source/docs only, excluding generated
audio/builds/caches and credentials. Execution follows this documentation
snapshot; verify actual Git/local/remote state rather than preclaiming this
file's own commit ID. This is not permission for later automatic commits.
The user explicitly authorized the
prior Phase 13A commit/push and continuation. That source transaction completed
at `56cb3bbae469afb91b82751617bcab1c08942ea8` on `origin/main` after transient
Git HTTPS failures. Main verified the GitHub API remote ref and
[CI run 38145240085](https://github.com/manish96170/whisper-py-convert/actions/runs/38145240085)
success. This hosted result verifies **13A**, not these new local changes.
No automatic 13B commit/push is authorized by the previous transaction.

Historical handoffs are retained under `docs/handoffs/`:
`SESSION_HANDOFF_PHASE13A.md`, `SESSION_HANDOFF_PHASE12.md`, and
`SESSION_HANDOFF_PHASES_0_11.md`. Their older instructions are history, not
permission to restart work or mutate protected components.

## Standing constraints / gates

- `whisper-py-convert.py`, root `Package.swift`,
  `Sources/WhisperAppleTranscribe/`, and `windows/` remain untouched.
  Existing STT locale-reservation risk #19 remains; four real fixtures skip.
  A repair needs an explicit, separate decision.
- No package release, tag, signing/notarization, cloud export, credentials
  provisioning or model download was performed for 13B. Base Python runtime
  dependencies remain empty; Swift has no external package dependencies.
- Public packaged release still requires an authorized project license.
  Never infer a license grant from source visibility or dependencies.
- Native/system voices/assets must already be installed. Source/wheel
  installation does not silently acquire models or replace native engines.

## Implemented contract

- `mac_speech.batch.BatchScene` and `synthesize_batch` provide typed local
  batch input/results. `mac-speech tts batch --input ... --output-dir ...`
  consumes strict schema-1 UTF-8 JSON; `--input -` reads stdin.
- Default **one worker**, explicit range **1–4**, at most that many submitted/
  in-flight scenes; finite **1–1000 scenes**. Scene basenames are validated
  filename components, with duplicate case/NFC aliases rejected before I/O.
  NUL/surrogate text or selections fail validation before creating claims.
- Reports preserve input order and contain hashes, paths, sanitized status/
  error/code and elapsed time—not source text/raw diagnostics. Thread-local
  context suppression leaves ordinary logging unchanged. Generated files are
  private and use the 13A atomic/ownership protections.
- Each worker claims/checkpoints its scene. The coordinator owns `.batch.lock`
  and `batch.json`; only its scheduler writes the aggregate. Ordinary scene
  failures preserve successes and allow other scenes to continue. Regular
  replacement is explicit; force does not bypass unverified claims.
- Worker side effects wait until `submit` returns, its Future is registered
  and admission acknowledged. Abandoned/unacknowledged startup cannot run
  late scene/native work; entered workers have explicit completion markers.
- One owned `communicate()` exchange delivers all long stdin and EOF while
  cancellation is monitored at 200-ms intervals. The child and owned I/O
  thread are reaped/drained before normal claim release. Queued work is
  cancelled; successful admitted scenes remain available after interruption.
- Unconfirmed child/thread drain stops further submissions and retains
  relevant claims. `cancelled` is an additive Python/native error-code entry
  with exit **130**; prior codes are unchanged. CLI returns 0 for all-success,
  1 for partial/unconfirmed failure, 130 for confirmed cancellation, or the
  usual structured validation/ownership error exit.

## Review findings and corrections

The reviewer initially reproduced:

1. Interrupted `Thread.start()` before executor registration allowed an
   untracked worker/native child while the batch claim was released.
2. Repeated `communicate(input=None)` stalled long stdin on CPython 3.11.3.
3. Invalid argv NUL/surrogate inputs unnecessarily quarantined a workspace.

All were corrected and independently rerun. Reviewer checked actual startup
interruption, delayed-reader delivery of 200,000 ASCII and 250,000 mixed-Unicode
characters (including SHA-256), I/O startup interruption/cancellation and
unconfirmed drain retaining both claims. No remaining serious finding was
reported. Review was read-only and did not substitute for main's real native,
fresh-wheel/performance/whole-suite checks below.

## Exact implementation/config/test changes

- `python/mac_speech/batch.py` — new
- `python/mac_speech/{errors,logging_utils,workflow,cli}.py`
- `python/mac_speech/tts/{engine,client}.py`
- `engines/tts-swift/Sources/MacSpeechTTSCore/Errors.swift`
- `engines/tts-swift/Tests/MacSpeechTTSCoreTests/ErrorsTests.swift`
- `tests/unit/test_batch.py`, `tests/unit/test_tts_cancellation.py` — new
- `pyproject.toml`, `MANIFEST.in`, `.github/workflows/ci.yml`
- `examples/batch_scenes.json` — new public sample
- `examples/README.md`, `python/README.md`, `README.md`, `CHANGELOG.md`, `PLAN.md`
- `docs/batch-synthesis.md` — new; `docs/{ci,packaging,protocol,verification}.md`
- This handoff and preserved Phase 13A archive

No other native implementation or preserved legacy source was changed for
13B; native edits add matching cancellation code/exit assertions only.
Inspect untracked additions explicitly, not just `git diff`.

## Independent final verification

Main repository Python 3.11.3: **431 passed, four known native STT skips**.
42 new batch/cancellation tests cover admission, limits, queue, ownership,
partial failures, cancellation, real long-stdin backpressure and CLI isolation.
Local 3.12.5/3.13.7/3.14.8 mocked source suites: **431 passed each** using
existing pure-Python pytest tooling/PYTHONPATH (not fresh installs).
Ruff/package/explicit tests pass; strict mypy passes **18 source targets**.

```sh
.venv/bin/python -m pytest tests/unit -q -rs
.venv/bin/python -m ruff check python/mac_speech
.venv/bin/python -m ruff check --isolated --select E4,E7,E9,F \
  scripts/audit_dependencies.py scripts/smoke_core.py examples/narration_workflow.py \
  tests/unit/test_dependency_audit.py tests/unit/test_smoke_core.py \
  tests/unit/test_narration_example.py tests/unit/test_installation_lifecycle.py \
  tests/unit/test_file_io.py tests/unit/test_workflow_safety.py \
  tests/unit/test_batch.py tests/unit/test_tts_cancellation.py
.venv/bin/python -m mypy
RUNNER_TEMP="${TMPDIR%/}/opencode" bash scripts/ci_swift.sh
# Use the existing approved temp directory if this path differs.
```

Native helper returned **exit 0**, **48 Swift tests passed**, release build
succeeded; a narrow known TestingMacros/private-cache/plugin retry ran.
No global caches were deleted. Existing toolchain/Sendable warnings remain.

Packaging was rebuilt wheel-from-sdist in a disposable source copy. Wheel
modules were byte-compared with repository source. Extracted package suite:
**420 passed, 15 skips** (11 repository-only lifecycle checks plus four STT).
Fresh non-editable 3.11.3 wheel installed using `--no-index --no-deps`;
`pip check` and a real three-scene TTS-only batch passed with minimal credential
environment and macOS network denial. WAV frames, ordered private report/
checkpoints, repeat refusal and claim cleanup were checked.

Current real three-scene sample on M1 Pro/16 GiB, macOS 27.0.1:
**4.163 seconds at one worker**, **2.206 seconds at two**. Serial ran first;
cache/load/voice selection matter. This is a measured sample, not a universal
speedup, CPU/energy/RSS claim or performance threshold. Default remains one;
in-flight admission is bounded rather than enqueuing every scene.

Evidence under the approved temp root:

- `phase13b-p7v6wh9f/swift-check.log`
- `batch-verified-4n5meu7f/` (real serial/parallel output, performance JSON)
- `batch-package-sbx1u_9u/` (source, build log, dist, extracted package, clean venv,
  real clean-wheel batch)
- `batch-final-wdqmftqm/` (final current included docs/manifest/public input,
  byte-checked modules, extracted package, fresh clean-wheel offline batch)

These temporary directories may be cleaned by the OS and are **not public
release artifacts**. Final test wheel/sdist (before handoff-only updates):

```text
c243bd978e0a61a1253b93c931f0fc2cec469047378f37243a194fa4ddfbdba9  mac_speech-0.1.0-py3-none-any.whl
0fbcfc694c9c5ec2b43c1aac9191b4c26914c274bf3f7f9501168421d8eae3e8  mac_speech-0.1.0.tar.gz
```

The final sdist includes the new batch document/public sample and passes
420 tests/15 expected skips; its clean wheel runs that packaged sample offline.
Any later packaged-input change requires a rebuild. None are authenticated
or committed release hashes.

## Limits and next actions

Trusted parent directories, filesystem hard-link support and the 13A
non-hostile inode assumptions remain. This is not a multi-file transaction,
power-loss guarantee, hostile same-UID sandbox, background service or global
limit across unrelated processes/workspaces. Unconfirmed claims are not
automatically removed; a stored parent PID is insufficient proof of safety.
The 200-ms polling interval is not a cancellation-latency guarantee; native
kill/reap and I/O/worker drain can require the backstop intervals.

1. Try the public sample using `docs/batch-synthesis.md`; select fresh output
   directories, default one worker, opt into two only when useful.
2. Complete and independently verify the separately authorized 13B source
   commit/push. The user gave a new explicit request; the completed `56cb3bb`
   permission was not reused and does not grant future automatic commits.
3. Resolve the project license before public packaged release; separately
   authorize the protected STT locale repair or choose a justified next optional
   capability. Earlier Phase 6/9 deferrals and other Phase 13 candidates remain
   unchanged; do not download a model or implement GUI/services automatically.
