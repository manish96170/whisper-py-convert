# Session handoff — Apple STT risk #19 maintenance

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
