# Session handoff — Phase 13B bounded batch synthesis

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
