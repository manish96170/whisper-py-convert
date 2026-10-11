# Historical handoff: before Phase 12

**Archive notice:** preserved unchanged below apart from this heading/notice.
This records the prior session, not current next-task instructions. Read
`docs/SESSION_HANDOFF.md` for current Phase 12 outcomes and release gates.

**Written:** 2026-10-11, at the end of a session that completed Phases
0-11 of `PLAN.md` in one continuous run. **Read `PLAN.md` in full and
this file before doing anything else.** Then inspect the actual repo
state and `git diff` yourself — do not trust this summary blindly;
verify it, per `PLAN.md`'s own handoff protocol.

## Current phase and objective

Phases 0-11 are complete and checked off in `PLAN.md`, with evidence
inline in each phase's "Status" paragraph. **Phase 12 (Packaging,
releases, documentation, and operational quality) has not been
started.** That is the next and only in-scope phase. Do not start
Phase 13 or revisit earlier phases unless Phase 12 work surfaces a
genuine defect in them.

## Explicit instruction for this next session: use subagents for Phase 12

Phase 12's tasks are mostly independent and parallelizable. **Dispatch
them as separate subagent tasks (the `subagent` tool, `general` agent,
`background: true` where you don't need to block on the result) rather
than doing all of it serially in the main session.** This keeps the
main session's context budget free for integration, review, and
running the final verification pass yourself. Suggested split (each is
a self-contained unit of work with clear inputs/outputs; give each
subagent this handoff file's "Repository facts" and "What must never
change" sections verbatim as context, since they won't have this
conversation's history):

1. **CI workflow** — add `.github/workflows/ci.yml`: Python lint
   (`ruff`/`flake8` — pick one, keep it a dev-only dependency) +
   `pytest tests/unit` on macOS runners; a separate job for
   `swift build`/`swift test --package-path engines/tts-swift` (expect
   and handle the known module-cache flakiness, `docs/risk-register.md`
   risk #17 — the CI job should not flake on it; consider a retry step
   or clearing the module cache before testing). Must not require
   network access beyond installing dependencies, and must not touch
   `whisper-py-convert.py`'s existing CI story (there isn't one yet —
   adding Python/Swift lint+test for the *new* `mac_speech` package and
   `engines/tts-swift` is in scope; retrofitting STT's own test harness
   is not, unless trivial).
2. **Version compatibility checks** — add a protocol-version check
   between `mac_speech.tts.engine`/`mac_speech.native_protocol`
   (`PROTOCOL_VERSION`) and whatever the native `mac-speech-tts` binary
   actually reports, surfaced as a clean `MacSpeechError` (there is
   already an `ErrorCode.PROTOCOL_VERSION_MISMATCH` and
   `check_protocol_version()` in `native_protocol.py` — wire it into
   `mac_speech/tts/engine.py`'s `run_operation()` if it isn't already
   fully exercised there; verify with a test that an artificially wrong
   `protocol_version` in a mocked response is rejected cleanly, not
   silently accepted). Also add a note to `mac-speech doctor` reporting
   the native binary's protocol version if available (optional, nice to
   have, don't scope-creep beyond this).
3. **Packaging/distribution decision + docs** — a short ADR or doc
   section deciding: how do users get the native binaries (build from
   source via `./install.sh`, is that sufficient, or do GitHub release
   assets make sense now?); what are the code-signing/notarization
   implications of distributing a *compiled* `mac-speech-tts` binary
   outside this machine (currently ad-hoc/unsigned — document what
   that means for a recipient: Gatekeeper will block it, right-click
   "Open" is the workaround, real distribution would need a Developer
   ID signature + notarization, which this project does not have).
   Keep this decision proportionate to a single-maintainer personal
   project — do not over-engineer a release pipeline that doesn't
   exist yet.
4. **Dependency/license scanning + SBOM** — audit the actual Python
   dependency surface (`pyproject.toml`'s `dependencies = []` for the
   base install; `dev`/`gdrive` extras) and the Swift package's
   dependencies (none — `engines/tts-swift/Package.swift` has zero
   external dependencies, confirm this is still true before writing
   it down). A simple SBOM (even a hand-written `docs/sbom.md` listing
   direct dependencies and their licenses) is proportionate here; do
   not add a new scanning tool/dependency just to generate one
   automatically unless it's trivial (e.g. `pip-licenses`, dev-only).
5. **Uninstall/upgrade/troubleshooting docs + release notes +
   rollback** — `docs/installation.md` already covers install
   modes/upgrade/uninstall/rollback (Phase 4) — review it for
   completeness against Phase 12's exact task list ("privacy,
   permissions, supported versions, troubleshooting") and fill genuine
   gaps rather than rewriting what's already correct. Add a
   `docs/release-notes-template.md` or a first real `CHANGELOG.md`
   entry summarizing Phases 0-11 for whenever this project's first
   "release" (even an informal one, e.g. a git tag) happens.
6. **Example scripts / sample workflow** — `examples/` already has a
   Python script, a shell script, and an agent-invocation guide for
   TTS (Phase 3). Phase 12 asks for "example scripts and a small
   sample workflow" more generally — a good concrete addition is an
   end-to-end example using `mac_speech.workflow.run_narration_pipeline`
   (Phase 11) plus an optional `mac-speech export` call, showing the
   full text → audio → SRT → (optional) export chain in one script.

After the subagents report back, **you (the main session) integrate,
run the full test suite yourself, resolve any merge conflicts between
their changes, and do the final `PLAN.md` checkbox update for Phase
12** — don't delegate that integration/verification step.

## Repository facts (verified this session; don't take anyone else's word for these — re-verify if anything seems off)

- Repo: `/Users/Manish.Sharma/hornblower/whisper-py-convert`, git remote
  `github.com/manish96170/whisper-py-convert.git`, branch `main`.
- Machine: M1 Pro, 16GB RAM, macOS 27.0.1 (26A434), arm64, Swift 6.4,
  Python 3.11.3, Command Line Tools only (**no full Xcode** — this
  matters for Swift Testing, see below).
- **No commits have been made this entire session, by design** (`git
  status --porcelain` currently shows only the same three modified
  pre-existing files across every phase: `.gitignore`, `install.sh`,
  `README.md`, plus everything else as new/untracked). Committing
  remains the user's explicit action per `PLAN.md`'s governance rules
  — do not auto-commit in the next session either unless asked.
- Two independent, already-built-and-working native engines:
  - `whisper-py-convert-apple` (STT) — root `Package.swift`, macOS 27
    floor, **completely untouched this entire session**.
  - `mac-speech-tts` (TTS) — `engines/tts-swift/Package.swift`, its own
    independent SwiftPM package, macOS 13 floor, built this session
    (Phases 2-5).
- Both are installed via `./install.sh [stt|tts|all]` (default `all`,
  verified identical to pre-Phase-4 behavior for the no-arg case).
- The Python package `mac_speech` (`python/mac_speech/`) is installed
  via `pip install -e ".[dev]"` into `.venv/` at the repo root (not
  installed by `install.sh` — deliberately, see
  `docs/decisions/ADR-001-repository-and-module-boundaries.md`).
- **188 Python unit tests pass, 4 skip** (the 4 skips are the Phase 4
  regression fixtures hitting the real, environmental Apple-STT-locale
  issue below — not a code defect). **39 Swift tests pass.** Both
  verified fresh, from a clean `.build` wipe, in the last few minutes
  of this session (see "Final verification" below).

## What must never change (hard constraints, re-stated from `PLAN.md`/ADR-001)

- `whisper-py-convert.py`, `Package.swift`'s existing
  `WhisperAppleTranscribe` target, `Sources/WhisperAppleTranscribe/`,
  and `windows/` are the preserved, working STT implementation. Do not
  modify them without an explicit, separate decision and justification
  — not as a side effect of Phase 12 packaging work.
- No automatic git commits.
- No cloud credentials, network access, or paid services required for
  the core (`tts`/`stt`/`doctor`/`capabilities`) to work.
- No large model downloads, ever, without explicit human approval for
  that specific model/version (this blocked real neural-TTS
  benchmarking in Phase 6 — intentionally; see `docs/tts-benchmark.md`).

## Known defects and unresolved questions (full detail in `docs/risk-register.md`, risks #1-22)

The one that will most likely bite the next session, confirmed with a
root cause this session (risk #19): **the existing, unmodified
`whisper-py-convert-apple` binary leaks Apple Speech-framework locale
reservations** — it calls `AssetInventory.reserve(locale:)` on every
run but never calls the matching `release`, and Apple enforces a hard
**5-locale maximum**. After enough `--language`-varying invocations in
one session (which this session did, heavily, across Phases 0/4/5/11),
*every* new locale request starts failing with a misleading "does not
support locale" error, including locales that worked minutes earlier.
This is **not a code defect in anything built this session** — it
reproduces identically with the completely unmodified
`whisper-py-convert.py --engine apple`. The real fix (adding an
`AssetInventory.release(reservedLocale:)` call in
`Sources/WhisperAppleTranscribe/main.swift`) was deliberately **not
applied**, per "do not rewrite functioning STT code" — it needs an
explicit, separate decision to touch that file, which this session did
not seek. If STT testing in the next session hits this same error, this
is why; it is not something Phase 12 needs to fix, but a future session
could, as its own deliberate, scoped change if asked.

Other open items worth knowing about before touching related code
(see the risk register for full detail, do not re-litigate without
re-reading it first):

- Risk #16: Personal Voice/voice-trait APIs need macOS 14+, not 13+ as
  first assumed — already corrected in code, just know the history if
  you see `#available(macOS 14.0, *)` guards and wonder why.
- Risk #17: `swift test` on this Command-Line-Tools-only toolchain
  intermittently fails with a `TestingMacros` plugin error after
  interleaved debug/release builds. Fix order that has worked:
  (1) `rm -rf engines/tts-swift/.build/out/ModuleCache.noindex
  engines/tts-swift/.build/out/Intermediates.noindex/SwiftExplicitPrecompiledModules`,
  (2) full `rm -rf engines/tts-swift/.build`, (3) also clear
  `~/Library/Caches/org.swift.swiftpm/manifests`. This is exactly why
  the CI subagent task above needs to handle this proactively, not
  discover it by flaking.
- Risk #20/22: Personal Voice authorization behavior (why status
  transitioned from `not_determined` to `authorized` mid-session, why
  `requestPersonalVoiceAuthorization`'s completion handler never
  fires) is not fully explained. Treated as "report status honestly,
  never try to drive authorization" — correct and sufficient for this
  project's scope; do not try to "fix" or further explain this unless
  specifically asked.
- Google Drive and Slack exporters are code-complete and unit-tested
  with mocks, but **never exercised against a real Google account**
  (no credentials provisioned) and **never sent a real, non-dry-run
  Slack message** (deliberately avoided — `~/hornblower/team-slack-bridge`
  is a real, live, already-configured Slack workspace integration;
  only `--dry-run` was verified against it). S3's dry-run path *was*
  verified against real, configured AWS credentials on this machine
  (`aws configure list` showed them) — only the final non-dry-run
  upload+verify was not attempted, for lack of a human-designated
  disposable bucket. See `docs/exporters.md` for exactly what was and
  wasn't verified, provider by provider.

## Deliberately unchecked boxes within Phases 0-11 (not oversights)

Five task checkboxes within already-"Complete"-marked phases are
deliberately left `[ ]`, not `[x]`, because they genuinely were not
done — per `PLAN.md`'s own rule, "do not claim unfinished tasks are
done." All five are explained in their phase's "Status" paragraph; this
is just an index so the next session doesn't have to search for them:

- Phase 6 (three boxes): "Test CPU/Apple Silicon acceleration
  availability," "Make model downloads explicit, resumable...,"
  "Benchmark quality with human listening tests" — all deferred
  because no neural TTS engine was installed this session (by design,
  per the no-silent-model-download rule).
- Phase 9 (two boxes): "Handle large files with multipart upload" (the
  `aws` CLI's own multipart handling is relied upon, not independently
  confirmed against a real large file) and "Add an optional
  post-upload URL generation feature" (not implemented — no human
  requested a presigned-URL feature yet).

If Phase 12 or beyond happens to need any of these for real, do them
then, with their own justification — do not silently check these boxes
without actually doing the work.

## Phase-by-phase summary (one paragraph each; full detail is in `PLAN.md`'s own per-phase "Status" paragraphs — read those, this is just an index)

- **Phase 0** — Discovery. Inspected the existing STT repo, decided
  monorepo-in-place (ADR-001), captured a baseline. No code changes.
- **Phase 1** — `python/mac_speech/` created: capabilities, errors,
  results, config, logging, doctor, native_protocol, cli skeleton.
  `tts`/`stt` were stubs raising `NOT_IMPLEMENTED`.
- **Phase 2** — `engines/tts-swift/` native TTS engine built from
  scratch. Found and fixed three real `AVSpeechSynthesizer` bugs
  (multi-sentence `write()` truncation, `AVAudioFile` header-flush
  requirement, container-vs-extension mismatch) — all documented with
  regression tests in `docs/tts-engine.md`.
- **Phase 3** — Wired the TTS engine into `mac_speech.tts`
  (`client.py`/`engine.py`/`models.py`) and real `mac-speech tts`
  CLI subcommands, replacing the Phase 1 stubs. PID-file-based
  cross-process stop/pause/resume, verified live.
- **Phase 4** — `mac_speech.stt` adapter wired to the *existing*
  `whisper-py-convert` engines (shells out, never imports/forks).
  `install.sh` gained `[stt|tts|all]` modes. Isolation (TTS-only,
  STT-only) proven by physically hiding each binary in turn.
- **Phase 5** — Personal Voice/system-voice exploration. Added
  `personal-voice-status` (report-only, never request). Found and
  fixed the macOS-13-vs-14 availability mistake. Verified Personal
  Voice works end-to-end with zero special-case code once authorized.
- **Phase 6** — Benchmarked the native engine for real
  (`scripts/benchmark_tts.py` → `docs/tts-benchmark.md`: RTF
  0.03-0.07, flat ~44MB peak RSS). Kokoro-82M/Piper evaluated by
  research only — **no model downloaded**, by design.
- **Phase 7** — `mac_speech.artifacts` (opt-in manifests, checksums),
  `mac_speech.stt.webvtt`, `mac_speech.align`. Found and fixed a real
  bug: `--json` was skipping the file write entirely for `stt
  transcribe --format text/srt/webvtt` when combined with `--output`.
- **Phase 8/9/10** — `mac_speech.export` common contract +
  `LocalExporter`/`GoogleDriveExporter`/`S3Exporter`/`SlackExporter`.
  `team-slack-bridge` was actually inspected on disk (not assumed) —
  its CLI contract, lack of file-upload capability, and existing
  idempotency-key mechanism directly shaped the Slack adapter.
- **Phase 11** — `mac_speech.workflow`: text → audio → STT-roundtrip
  alignment → SRT, as three independently-retryable stage functions
  plus a versioned manifest. Verified for real (not synthetically)
  that a failed alignment stage leaves the synthesized audio file
  intact — using the real locale-exhaustion bug above as the test
  case.

## Exact test commands and last-verified outcomes

```sh
cd /Users/Manish.Sharma/hornblower/whisper-py-convert

# Python (188 passed, 4 skipped, last run clean)
.venv/bin/python -m pytest tests/unit -q

# Swift (39 passed, last run clean from a full .build wipe)
rm -rf engines/tts-swift/.build
swift test --package-path engines/tts-swift
swift build --package-path engines/tts-swift --configuration release

# Existing STT, unaffected
python3 -m py_compile whisper-py-convert.py

# End-to-end smoke
.venv/bin/mac-speech doctor
```

## Next three concrete actions

1. Read `PLAN.md` end to end (it is the source of truth; this file is
   just an index into it) and `git diff`/`git status` the actual repo
   — confirm this handoff's claims against reality before trusting
   them.
2. Dispatch the Phase 12 subagent tasks listed above (CI, version
   compatibility, packaging/signing docs, SBOM, uninstall/release
   docs, example workflow) — in parallel where they don't touch the
   same files, serially/reviewed where they might conflict (CI config
   and the version-compatibility code both touch `mac_speech/`, so
   consider running those two first and sequentially; the three
   docs-only tasks are safe to fully parallelize).
3. Integrate subagent results yourself in the main session: run the
   full test suite, resolve any overlap, update `PLAN.md`'s Phase 12
   checkboxes with real evidence (not just "subagent said it's done"),
   and write a fresh handoff (or hand control back to the user) once
   Phase 12 is genuinely complete.

## Clean-session starter prompt

> Read `PLAN.md` and `docs/SESSION_HANDOFF.md` in full before doing
> anything else. Inspect the actual repository state and `git diff`
> yourself — do not trust the handoff's summary without verifying it.
> Continue only Phase 12 (Packaging, releases, documentation, and
> operational quality). Per the handoff's explicit instruction, use
> the `subagent` tool to parallelize Phase 12's independent sub-tasks
> (CI workflow, version-compatibility checks, packaging/signing docs,
> SBOM, uninstall/release docs, example workflow) rather than doing
> everything serially in this session — keep this session for
> integration, conflict resolution, and final verification. Do not
> start Phase 13 or modify `whisper-py-convert.py`/
> `Sources/WhisperAppleTranscribe/`/`windows/` without an explicit,
> separate decision. No automatic git commits.
