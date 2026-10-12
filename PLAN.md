# Mac Speech Toolkit --- Phased Product and Engineering Plan

**Status:** Risk #19 locally resolved with owned native evidence; explicit asset setup uncommitted\
**Purpose:** A durable implementation plan for GPT, Codex, Claude Code,
OpenCode, or other local coding agents.\
**Primary platform:** macOS on Apple Silicon, starting with the user's
M1 Pro / 16 GB RAM machine.\
**Core principles:** local-first, free/open-source-first, modular,
loosely coupled, independently installable, measurable, and safe by
default.

**Reading guide (2026-10-11):** Sections 1–6 retain the original design baseline;
phase-specific completion notes/test counts are historical snapshots. Current
interfaces and repository boundaries are in `python/README.md` and
`docs/architecture.md`; final Phase 12 evidence is below and in
`docs/verification.md`. Phase 6's explicitly deferred model work remains
deferred and native STT risk #19 remains open. The user has now authorized
Phase 13; the bounded Phase 13A output-safety slice below is locally complete.
The broader optional Phase 13 backlog remains deferred, not completed. The
user authorized the 13A source push, then continuation to the bounded batch
synthesis slice in 13B, now locally complete. The 13B checkpoint was license-blocked;
current licensing is separate concurrent work in `LICENSE`/`docs/licensing.md`.

------------------------------------------------------------------------

## 1. Product vision

Build a small, modular **Mac Speech Toolkit** that exposes local speech
capabilities through a lightweight Python package and CLI while keeping
speech engines independent.

The toolkit should support:

1.  **Speech-to-text (STT):** preserve and package the existing working
    Swift/native STT implementation without destabilizing it.
2.  **Text-to-speech (TTS):** add a standalone native macOS TTS engine
    using Apple's speech APIs.
3.  **One shared Python wrapper and CLI:** a consistent interface can
    invoke STT, TTS, or both; installing one capability must not require
    installing the other.
4.  **Optional voice engines:** investigate Apple system voices,
    Personal Voice where supported and authorized, and optional
    open-source local neural engines such as Kokoro or Piper.
5.  **Audio and transcript artifacts:** produce and manage audio,
    transcript, subtitle, and timing files in well-defined formats.
6.  **Optional integrations:** export or send artifacts to local
    folders, Google Drive, Amazon S3 using AWS CLI/SDK or explicitly
    configured credentials, and Slack through the separate
    `team-slack-bridge` project or a well-defined adapter.
7.  **Future workflow integration:** support narration and time-aligned
    SRT/word timestamps for the user's broader open-source
    video-generation workflow without coupling the speech core to a
    specific video editor or renderer.

This is a local speech toolkit first, not a cloud speech service. Cloud
storage and messaging are optional output destinations, not
prerequisites for core speech functions.

## 2. Non-goals and constraints

-   Do not require paid speech APIs, subscriptions, or cloud inference
    for the default workflow.
-   Do not upload audio, transcripts, or text without an explicit user
    action or configured automation policy.
-   Do not make the new TTS implementation depend on the STT executable,
    process, app UI, or internal implementation.
-   Do not rewrite functioning STT code just to fit a new architecture.
    Inspect first, preserve behavior, and migrate incrementally.
-   Do not bundle large neural models in the base installation or
    download them silently.
-   Do not assume Apple Personal Voice is available to arbitrary
    processes or that it can be used through `say`. Probe supported
    native APIs and permissions on the actual macOS version.
-   Do not claim every third-party voice model has the same license as
    its engine. Verify licenses and redistribution terms separately.
-   Do not make Google Drive, S3, Slack, or video tooling mandatory
    dependencies.
-   Do not store credentials in source code, logs, project configuration
    committed to Git, or artifact metadata.
-   Do not introduce automatic Git commits. The agent may edit files and
    run checks, but Git commits remain a human-controlled action unless
    explicitly requested.
-   Keep the base Python wrapper small and standard-library-first
    wherever practical.
-   Prefer explicit capability detection and actionable errors over
    guessing or silent fallback.
-   Target macOS and Apple Silicon first. Clearly document what is and
    is not supported on Intel Macs or other operating systems.

## 3. Product architecture

### 3.1 Logical components

``` text
Applications / scripts / coding agents / video workflow
                         |
                         v
              Python package + CLI
       common configuration, results, errors
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
       STT adapter    TTS adapter    Artifact/workflow API
          |              |              |
     Existing Swift   Native Swift   Local filesystem first
     implementation   AVSpeech...   plus optional exporters
          |              |
          v              v
     transcript /    playback or audio file
     SRT / timestamps
                         |
                         v
             Optional provider adapters
          +--------------+---------------+
          |              |               |
          v              v               v
      Google Drive    Amazon S3       Slack bridge
      optional        optional        optional
```

### 3.2 Repository strategy

Start by inspecting the existing STT repository and deciding whether a
monorepo or a small companion repository is safest. Do not move code
until the current structure, release process, licenses, and wrapper
contract are understood.

**Preferred logical layout if a unified repository is appropriate:**

``` text
mac-speech/
  README.md
  PLAN.md
  pyproject.toml
  python/
    mac_speech/
      __init__.py
      cli.py
      config.py
      capabilities.py
      errors.py
      results.py
      stt/
        __init__.py
        client.py
        models.py
      tts/
        __init__.py
        client.py
        models.py
        engines.py
      artifacts/
        __init__.py
        manifest.py
        paths.py
      integrations/
        __init__.py
        base.py
        gdrive/
        s3/
        slack/
  engines/
    stt-swift/           # existing implementation or subproject
    tts-swift/           # new standalone native implementation
  tests/
    unit/
    integration/
    fixtures/
  docs/
    architecture.md
    decisions/
    formats.md
    security.md
    integrations.md
    performance.md
  scripts/
  examples/
```

This is a target shape, not an instruction to restructure before
inspection. If the existing STT repository is already independently
packaged and stable, a companion TTS repository plus a shared wrapper
package may be safer. Document the decision in an Architecture Decision
Record (ADR).

### 3.3 Loose coupling rules

-   Python owns the stable public API, CLI, configuration, capability
    discovery, artifact naming/metadata, and user-facing errors.
-   Each native engine owns the platform-specific work and exposes a
    documented machine interface.
-   Prefer a versioned JSON-lines protocol over parsing human-oriented
    console output if a long-running subprocess is used.
-   For one-shot commands, stdin/stdout with a documented JSON request
    and response is acceptable.
-   Never mix diagnostic logs with machine-readable stdout. Send
    diagnostics to stderr.
-   Define protocol versioning, timeout handling, cancellation, exit
    codes, and graceful shutdown.
-   The wrapper must detect missing engines and explain how to install
    them.
-   STT and TTS can be installed and tested separately.
-   Optional integrations implement a small common exporter interface
    and are loaded only when selected.
-   Keep the core usable offline after installation, without sign-in or
    network access.

## 4. Public interface proposal

The examples below are the original proposed contract candidates, not a
current command reference. Many have since been implemented, but names,
flags, and result signatures must be taken from CLI help, `python/README.md`,
and current contract docs rather than assumed from these planning examples.

### 4.1 CLI

``` bash
# Capability and environment information
mac-speech doctor
mac-speech capabilities
mac-speech version

# TTS
mac-speech tts voices
mac-speech tts speak "Hello from my Mac"
mac-speech tts save "Narration text" --output ./artifacts/narration.aiff
mac-speech tts stop
mac-speech tts pause
mac-speech tts resume

# STT — preserve existing behavior and map existing options carefully
mac-speech stt transcribe ./audio.m4a
mac-speech stt transcribe ./audio.m4a --format json
mac-speech stt transcribe ./audio.m4a --format srt --output ./artifacts/transcript.srt

# Artifact management and explicit export
mac-speech artifacts list ./artifacts
mac-speech export ./artifacts/narration.aiff --to s3 --destination s3://bucket/path/
mac-speech export ./artifacts/transcript.srt --to gdrive --destination "folder-id"
mac-speech export ./artifacts/narration.aiff --to slack --destination "#channel-name"
```

Do not implement commands merely because they appear here. First settle
a coherent CLI contract, command names, and backward compatibility.

### 4.2 Python API

Keep the API predictable and typed where useful:

``` python
from mac_speech.tts import list_voices, speak, synthesize_to_file

voices = list_voices()
speak("Hello from the Mac", voice=None, rate=None)
result = synthesize_to_file(
    "Narration for a video.",
    output_path="artifacts/narration.aiff",
)
```

And, conceptually, for STT:

``` python
from mac_speech.stt import transcribe

result = transcribe("recording.m4a", output_format="json")
```

The real signatures must be designed after inspecting the existing
wrapper. Avoid creating two competing APIs for the same operation.

### 4.3 Contract requirements

Every operation should define: - Required and optional inputs. -
Supported formats and capability requirements. - Output schema and
stable error codes. - Whether it starts playback, creates a file, or
both. - Cancellation, timeout, and progress semantics where relevant. -
Whether the operation needs network access or permissions. - Timing
fields such as startup latency and synthesis duration, where
measurable. - Version compatibility between Python wrapper and native
binary.

## 5. Artifact model and formats

Artifacts are first-class outputs. The core should create files locally
first and keep export independent from generation.

### 5.1 Supported artifacts

-   Generated audio: start with formats reliably supported by the native
    API and file writer. Document codec/container behavior; do not infer
    a format solely from a filename extension.
-   STT transcript: JSON containing text and available metadata.
-   Subtitle transcript: SRT.
-   Structured timing: word- or segment-level timestamps where the
    selected STT engine actually supplies them.
-   Optional later: WebVTT, plain text, timing alignment JSON, and
    video-workflow manifests.

### 5.2 Artifact manifest

For generated files, optionally create a sidecar manifest such as
`artifact.json` with: - Schema version. - Artifact ID. - Creation time
in UTC. - Operation (`tts`, `stt`, or later alignment). - Engine name
and engine version. - Voice identifier and language, if applicable. -
Input text hash rather than full text by default, to avoid unnecessary
sensitive-text duplication. - Output file path, media type, file size,
and checksum. - Sample rate, channels, duration, and codec when known. -
STT segments/word timestamps only when returned by the engine. -
Provenance and processing steps. - Explicit export destinations and
status, without credentials.

Do not include secrets, access tokens, full local usernames/paths unless
necessary, or full source text by default. Provide an opt-in way to
retain source text for reproducibility.

### 5.3 File handling rules

-   Use deterministic, collision-safe filenames with an option to
    specify an output path.
-   Never overwrite an existing file silently.
-   Write temporary files and atomically finalize them where practical.
-   Validate that output paths stay within intended destinations when
    operating in managed workspaces.
-   Handle Unicode text, long text, and empty input.
-   For long synthesis, define chunking that preserves sentence
    boundaries and avoids audible gaps where feasible.
-   Track chunks and final outputs in a manifest if chunking is used.
-   Never claim word-level synchronization from TTS unless alignment is
    actually computed or supplied.

## 6. Security and privacy principles

-   Local synthesis and transcription should work without sending user
    content to third parties.
-   Exports are explicit by default. Any configured automatic export
    must be opt-in and display/document its destination.
-   Resolve credentials through supported provider mechanisms, such as
    AWS credential chain, environment variables, named profiles, or the
    provider's OAuth flow. Never ask users to paste secrets into source
    files.
-   Redact tokens and sensitive paths from logs.
-   Do not log full speech text or transcripts by default.
-   Apply least privilege for cloud destinations and Slack.
-   Support dry-run and destination preview for bulk export.
-   Report exactly which files were sent and to which destination.
-   Avoid automatic public sharing links. Sharing permissions must be
    explicit.
-   Treat remote files and messages as untrusted data.
-   Define deletion and retention behavior; do not delete local
    artifacts after upload unless explicitly requested.
-   Document Personal Voice consent and availability constraints, and
    never attempt to bypass Apple's restrictions.
-   Add dependency and license review before including any engine or
    voice model.

------------------------------------------------------------------------

# 7. Phased delivery plan

Work phase by phase. Each phase must have explicit acceptance criteria,
tests, documentation updates, and a review by a separate reviewer agent
when available. Keep this plan as the source of truth.

## Phase 0 --- Discovery, baseline, and risk register

**Goal:** Understand the existing STT implementation and avoid breaking
it.

Tasks: - \[x\] Locate the existing Swift STT app, Python wrapper, build
scripts, and distribution instructions. - \[x\] Record the current OS,
CPU architecture, Swift and Python versions, and actual install/runtime
requirements. - \[x\] Run the existing STT workflow and capture
reproducible baseline behavior. - \[x\] Record supported input formats,
output formats, timing capabilities, permissions, and current
limitations. - \[x\] Identify current repository structure, release
process, license, tests, and any generated binaries. - \[x\] Decide
monorepo versus companion repository using an ADR. - \[x\] Inventory
assumptions about Apple Personal Voice and verify them against installed
macOS APIs. - \[x\] Create a risk register covering API availability,
audio formats, latency, subprocess lifecycle, licensing, privacy, and
cloud credentials.

Status: Complete. See `docs/architecture.md`,
`docs/decisions/ADR-001-repository-and-module-boundaries.md`,
`docs/performance.md`, and `docs/risk-register.md` for evidence. No
reviewer agent was available in this session; findings above should be
sanity-checked by a reviewer before Phase 1 work is treated as fully
clear of hidden risks.

Deliverables: - `docs/architecture.md` -
`docs/decisions/ADR-001-repository-and-module-boundaries.md` -
`docs/performance.md` with the STT baseline - A list of known issues and
a rollback strategy

Acceptance criteria: - Existing STT workflow is demonstrated and
documented. - No behavior has been changed. - Architecture choice is
based on repository inspection, not assumption. - Each risk has an owner
or a planned validation step.

Review agent: inspect architecture and risks; identify unnecessary
migration, hidden dependencies, and compatibility risks.

## Phase 1 --- Shared contracts and minimal Python package

**Goal:** Define a stable interface without requiring both engines to be
installed.

Tasks: - \[x\] Design API and CLI naming based on existing code. - \[x\]
Define typed request/result models and stable error codes. - \[x\]
Define capability discovery (`stt`, `tts`, available voices, available
output formats). - \[x\] Define native-process protocol and protocol
versioning. - \[x\] Define logging rules and ensure stdout remains
machine-readable for JSON mode. - \[x\] Create package metadata and a
reproducible development/test setup. - \[x\] Add unit tests for
configuration, validation, capability reporting, and error mapping. - \[
x\] Add a `doctor` command that diagnoses missing binaries and
unsupported environments. - \[x\] Document macOS/Apple Silicon support
and limitations.

Status: Complete. New package at `python/mac_speech/` (editable install
via root `pyproject.toml`), CLI entry point `mac-speech` with working
`version`/`capabilities`/`doctor` commands (`--json` supported) and
reserved `tts`/`stt` stub subcommands that return a stable
`not_implemented` error. 37 unit tests pass under `pytest tests/unit`.
Voice enumeration and real output-format lists are deferred to Phase 2/3
since no TTS engine exists yet; `capabilities` honestly reports this
rather than guessing. See `docs/protocol.md` and
`docs/platform-support.md` for the new contracts, and `python/README.md`
for the package-level dev setup. No reviewer agent was available this
session.

Acceptance criteria: - Python package can be imported without installing
a TTS model. - Missing TTS does not break STT and missing STT does not
break TTS. - CLI help, version, and diagnostics work on a clean
environment. - Contract examples are tested. - No cloud credentials or
network access are required.

Review agent: check API simplicity, backward compatibility, protocol
robustness, and packaging hygiene.

## Phase 2 --- Standalone native macOS TTS

**Goal:** Ship a useful zero-cloud-cost TTS engine.

Tasks: - \[x\] Create a separate Swift target/CLI for TTS using
`AVSpeechSynthesizer`. - \[x\] Implement voice enumeration and stable
voice identifiers. - \[x\] Implement speech rate and language/voice
selection where supported. - \[x\] Implement speak, stop, pause, and
resume if the chosen process model supports them reliably. - \[x\]
Implement synthesis-to-file separately from playback. - \[x\] Decide on
supported audio formats after testing the actual APIs; verify output
with media tools. - \[x\] Define how long text is handled and whether
chunking is required. - \[x\] Handle unavailable voices, invalid rates,
empty input, interrupted playback, and OS/API errors. - \[x\] Add a
versioned machine-readable interface between Python and Swift. - \[x\]
Add unit tests for request validation and integration tests for voice
discovery and file output. - \[x\] Keep the native TTS target
independent of the existing STT target.

Status: Complete. New independent SwiftPM package at
`engines/tts-swift/` (minimum macOS 13.0, deliberately decoupled from the
STT target's macOS 27 floor) builds `mac-speech-tts`. 37 Swift Testing
tests pass (`swift test --package-path engines/tts-swift`), split across
unit tests (sentence splitting, argument parsing, audio format specs,
error-code mapping) and integration tests against the real
`AVSpeechSynthesizer` API (voice discovery, file synthesis, overwrite
protection, container-format verification). Three concrete bugs were
found and fixed during implementation, each with its own regression
test — see `docs/tts-engine.md`: (1) `write()` silently truncates
multi-sentence utterances to the first sentence, fixed via mandatory
per-sentence chunking; (2) `AVAudioFile` needs an explicit `nil` release
to flush its header; (3) `AVAudioFile` infers its container from the
destination URL's extension, not from `settings`, which broke the
atomic-temp-file write path until the temp file was renamed to preserve
the real extension. Stop/pause/resume verified manually via real
SIGINT/SIGTERM/SIGTSTP/SIGCONT delivery to a running `speak` process. A
first (non-regression-tested) performance baseline was captured in
`docs/performance.md`. `docs/risk-register.md` risks #1, #2, #8 updated
to resolved; risks #14-16 added for new findings. No reviewer agent was
available this session.

Acceptance criteria: - TTS works on the target Mac without cloud access
and without STT installed. - It can speak text and generate an audio
file. - It reports errors and exit codes consistently. - Audio files are
valid, playable, and match documented format metadata. - Repeated calls
do not leak child processes or leave audio sessions stuck. - Performance
baseline includes cold start, warm request, time to first audio when
measurable, and synthesis duration.

Review agent: inspect Swift concurrency/process lifecycle, API
correctness, audio resource cleanup, error handling, and independence
from STT.

## Phase 3 --- Integrate TTS with the shared wrapper and CLI

**Goal:** Make native TTS easy to install and invoke from Python and the
terminal.

Tasks: - \[x\] Implement Python TTS client functions. - \[x\] Implement
the agreed CLI commands. - \[x\] Add structured JSON output mode for
automation. - \[x\] Add timeout, cancellation, subprocess cleanup, and
useful diagnostics. - \[x\] Define binary discovery and install/update
behavior. - \[x\] Add examples for Python scripts, shell use, and
AI-agent invocation. - \[x\] Ensure voice listing uses actual engine
capabilities rather than hard-coded assumptions. - \[x\] Document
environment variables and configuration precedence.

Status: Complete. `python/mac_speech/tts/{client,engine,models}.py`
implement `list_voices`/`speak`/`synthesize_to_file`/`stop`/`pause`/`resume`
as typed functions over a subprocess wrapper around `mac-speech-tts`
(timeout via `communicate(timeout=...)` with kill-on-expiry; cross-process
stop/pause/resume via a small PID file, documented as a known single-slot
limitation). `mac-speech tts voices|speak|save|stop|pause|resume` are real
nested CLI subcommands (`cli.py`), replacing the Phase 1 stub; `--json`
works on every one. `install.sh` gained an additive, independent step that
builds `mac-speech-tts` and installs it to
`~/.local/share/mac-speech/mac-speech-tts`, plus printed guidance (not
automation) for setting up the Python CLI's own venv — the existing STT
build/install step is untouched. 27 new unit tests
(`test_tts_engine.py`, `test_tts_client.py`) mock subprocesses per
PLAN.md section 8.1; 77 total Python tests and 37 Swift tests pass.
Verified manually end-to-end: `save`/`voices`/error paths over the real
compiled binary, and cross-process `stop`/`pause`/`resume` against a
backgrounded `speak` call via real signals. New `docs/configuration.md`
(env vars/precedence) and `examples/` (`tts_python_script.py`,
`tts_shell.sh`, `tts_agent_invocation.md`), all executed successfully
against the real engine during this session. No reviewer agent was
available this session.

Acceptance criteria: - A user can install/use TTS independently. - A
Python script can synthesize audio without importing STT dependencies. -
CLI output is stable enough for scripts. - Failures include actionable
remedies. - The wrapper remains small and adds no unnecessary
machine-learning dependencies.

Review agent: test real-world CLI usage and review ergonomics,
subprocess safety, and compatibility.

## Phase 4 --- STT compatibility and optional combined installation

**Goal:** Expose STT and TTS through one coherent product without
destabilizing STT.

Tasks: - \[x\] Add an adapter around the existing STT implementation
only as needed. - \[x\] Preserve existing input/output behavior and
documented timing semantics. - \[x\] Add capability-based optional
installation for `stt`, `tts`, and `all`. - \[x\] Add regression
fixtures from known audio and expected transcript properties, respecting
privacy. - \[x\] Confirm SRT/JSON output compatibility and timestamp
accuracy. - \[x\] Test installing and running STT-only, TTS-only, and
combined modes. - \[x\] Document upgrade, uninstall, and rollback
behavior.

Status: Complete. `python/mac_speech/stt/{models,engine,client}.py` add
a real adapter that never imports/forks `whisper-py-convert.py`: `text`/
`srt` formats shell out to the existing script unchanged (preserving its
exact behavior for every engine, including faster-whisper); `json`
format calls the Apple binary directly for full multi-segment/word
fidelity, with a documented best-effort single-segment approximation for
Windows (plain text, no timing) and faster-whisper (derived from a
word-level SRT, since it has no native JSON contract). `mac-speech stt
transcribe` is a real nested CLI subcommand (`--format text|srt|json`,
`--seg-ts`/`--word-ts`, `--engine`, `-o/--output`, `--json` wrapper).
`install.sh` gained a `[stt|tts|all]` mode argument (default `all`,
identical behavior to before); manually verified STT-only and TTS-only
by temporarily hiding each native binary in turn and confirming
`capabilities`/`doctor`/the other capability's commands degrade
gracefully with `engine_not_found` while the present capability keeps
working. 41 new mocked unit tests (`test_stt_engine.py`,
`test_stt_client.py`, plus CLI tests) plus 4 skippable regression-fixture
integration tests (`test_stt_regression_fixtures.py`, generating audio
via `say` at test time per PLAN.md's privacy guidance, never committing
audio) — 124 total Python tests (120 passed, 4 skipped). New
`docs/installation.md` (upgrade/uninstall/rollback).

**Known issue surfaced, not caused, by this phase:** the Apple STT
engine's locale/asset reservation became highly unreliable on this
development machine during Phase 4 testing — reproduced identically with
the completely unmodified `whisper-py-convert.py`, and shown via system
logs to be plausibly related to the unsigned SPM binary's unstable
client identity with the speech asset system (see
`docs/risk-register.md` risk #19). This blocked running the regression
fixtures end-to-end in this session (they skip gracefully rather than
fail), but the adapter's own logic is verified via mocked unit tests and
was confirmed working end-to-end earlier in the session before the
flakiness worsened (STT-only/TTS-only isolation tests, `--format json`
parsing of real Apple-engine output, SRT round-trips). No reviewer agent
was available this session.

Acceptance criteria: - Existing STT regression tests pass. - TTS-only
install works without STT. - STT-only install works without TTS. -
Combined install exposes a consistent CLI without duplicating engine
logic. - No existing working flow is removed or silently changed.

Review agent: focus on regressions, installation isolation, dependency
bloat, and compatibility.

## Phase 5 --- Personal Voice and system-voice capability exploration

**Goal:** Support system voices and Personal Voice only through
documented, authorized APIs.

Tasks: - \[x\] Test voice discovery through `AVSpeechSynthesizer` on
supported macOS versions. - \[x\] Determine which system voices are
available locally versus requiring download. - \[x\] Test whether
Personal Voice is exposed to this app/API on the target device and OS. -
\[x\] Implement authorization/status reporting if Personal Voice
integration is supported. - \[x\] Make unavailable or unauthorized
Personal Voice a clear, non-fatal condition. - \[x\] Avoid depending on
private APIs, scraping, or unsupported access to voice data. - \[x\]
Document that availability and use are controlled by Apple and system
settings.

Status: Complete. Added `personal-voice-status` to the Swift engine
(read-only `AVSpeechSynthesizer.personalVoiceAuthorizationStatus` check;
corrected during this phase to require macOS 14+, not macOS 13+ as
Phase 2 had incorrectly assumed — the compiler caught it) and wired it
through to `mac_speech.tts.personal_voice_status()` and `mac-speech tts
personal-voice-status`. Deliberately did **not** build a wrapper around
`requestPersonalVoiceAuthorization`: its completion handler was verified
twice to never fire from this bare, unsigned, bundle-less binary
(including once when status was already `authorized`), most likely
because it lacks an `Info.plist`/`NSPersonalVoiceUsageDescription` — so
this tool only ever reports status, never drives authorization,
directly satisfying "the app never implies it can create or extract a
Personal Voice itself." Verified end-to-end on a Mac with real,
previously-created Personal Voices: `voices` correctly flagged exactly
those entries as `is_personal_voice: true`, and `save --voice
<personal-voice-id>` produced valid audio through the existing,
unmodified voice-resolution code path — no special-case code needed.
Also discovered and documented: (1) the compiled binary's voice catalog
is unstable (180-182 voices across runs vs. 191 from a fresh script in
the same session) — `docs/risk-register.md` risk #21; (2) authorization
status was observed to transition from `not_determined` to `authorized`
mid-session through an unconfirmed mechanism — risk #22; (3) a new
variant of the known `swift test` module-cache flakiness required
clearing the *global* `~/Library/Caches/org.swift.swiftpm/manifests`
cache, not just the local `.build` — risk #17 updated. 6 new/updated
Swift tests, 2 new Python tests, 2 new CLI tests — 124 Python tests (120
passed, 4 skipped) and 39 Swift tests all pass. Per the real sensitivity
of this phase's findings, no specific Personal Voice name or identifier
discovered during testing was committed anywhere — `docs/tts-engine.md`
and `docs/platform-support.md` describe the finding only in general
terms. No reviewer agent was available this session.

Acceptance criteria: - Normal system voices remain the reliable
default. - Personal Voice is offered only when the system reports a
usable capability and permission. - The app never implies it can create
or extract a Personal Voice itself. - No undocumented or
privacy-bypassing behavior is introduced.

Review agent: verify platform/API assumptions, privacy messaging, and
graceful fallback.

## Phase 6 --- Performance benchmarking and optional neural TTS

**Goal:** Measure native performance and add an open-source neural
engine only if it offers a meaningful benefit.

Tasks: - \[x\] Establish repeatable test text: short command, paragraph,
long article, and narration script. - \[x\] Measure cold start, warm
latency, time to first audio, real-time factor, total duration, peak
memory, CPU/energy where feasible, and output size. - \[~\] Compare
native system voices with at least one candidate such as Kokoro-82M;
consider Piper as another lightweight candidate. - \[~\] Verify actual
model and voice licenses, model size, redistribution conditions,
supported languages, and commercial-use restrictions. - \[ \] Test
CPU/Apple Silicon acceleration availability; do not assume all builds
use Metal/Core ML. - \[ \] Make model downloads explicit, resumable
where practical, checksum-verified, and stored outside the source
tree. - \[x\] Keep optional model dependencies isolated from the base
Python package. - \[x\] Define a common TTS engine interface and
capability metadata. - \[x\] Add an engine-selection option while
preserving native TTS as the default. - \[ \] Benchmark quality with
human listening tests in addition to numerical timing.

Status: Partially complete, by design. Native-engine benchmarking is
done and reproducible (`scripts/benchmark_tts.py`,
`docs/tts-benchmark.md`): RTF 0.03-0.07 for realistic text lengths, flat
~44MB peak RSS regardless of length. Neural-engine comparison
(Kokoro-82M/Piper) was done as **research only** — license/size/
acceleration claims are from general knowledge, explicitly flagged as
needing live re-verification, and **no model was downloaded**, per
`PLAN.md`'s own non-goal ("do not bundle large neural models... or
download them silently") — downloading a third-party model
unattended, without a specific user go-ahead for that model/version,
was judged out of scope for an autonomous continuation. The common TTS
engine interface and engine-selection pattern are documented
architecturally (`docs/tts-benchmark.md`'s "Common TTS engine
interface" section) so a future engine can plug in via the existing
`--engine`-flag pattern already proven for STT, without an API
redesign — but no second engine exists yet, so there is nothing to
default-switch away from and no listening test to run. CPU/acceleration
testing and checksum-verified download tooling are deferred to whenever
a specific neural engine is actually approved for installation.

Acceptance criteria: - A documented benchmark table exists for the
target M1 Pro / 16 GB Mac. - No neural engine is made default unless it
demonstrably improves the intended workload. - Base install remains
small and usable offline. - Model/voice licenses and limitations are
documented. - Engine failure falls back only according to an explicit
policy; no silent switch that changes voice unexpectedly.

Review agent: check benchmark methodology, reproducibility, model
licensing, memory use, and unnecessary dependencies.

## Phase 7 --- Artifact lifecycle and speech workflow formats

**Goal:** Make outputs easy to reuse in video creation, editing,
archiving, and automation.

Tasks: - \[x\] Define artifact directory conventions and collision-safe
naming. - \[x\] Implement atomic output writing and overwrite
protection. - \[x\] Add versioned artifact manifests and optional
checksums. - \[x\] Define JSON transcript schema with segment and word
timestamps only where supported. - \[x\] Validate SRT generation,
encoding, cue ordering, and timestamp formatting. - \[x\] Add optional
WebVTT support if required by target workflows. - \[x\] Distinguish
transcription timestamps from TTS timing and forced alignment. - \[x\]
Design chunked long-form synthesis and stitching, including silence/gap
handling. - \[x\] Add a future alignment interface that can consume
generated speech and text to produce word timings, without pretending
TTS inherently supplies them. - \[x\] Document retention and cleanup;
never delete source artifacts after export by default.

Status: Complete. New `mac_speech.artifacts` (opt-in `--manifest`
sidecar JSON, sha256 checksums, privacy-by-default text handling,
collision-safe `suggest_artifact_path()`), `mac_speech.stt.webvtt`
(lossless SRT->WebVTT, wired as `--format webvtt`), and
`mac_speech.align` (explicit, honestly-labeled STT-roundtrip
approximation — never called "forced alignment"). Fixed a real gap
found while adding this: `stt transcribe --output` was using a plain
`write_text()` with no overwrite protection and no atomicity, unlike
`tts save`; now both share the same atomic-write + `--force` pattern,
and a genuine bug was caught and fixed in the process (`--json` was
short-circuiting before the file write for `text`/`srt`/`webvtt`
formats — found by a new overwrite-protection test, not by inspection).
Chunked long-form synthesis (Phase 2) and the JSON transcript schema
(Phase 4) were already in place; this phase documents them under one
roof (`docs/formats.md`) rather than re-implementing anything. 20 new
unit tests (`test_artifacts.py`, `test_webvtt.py`, `test_align.py`,
plus CLI tests) — 141 Python tests pass (4 still skip on the
documented Apple-engine locale flakiness, unrelated to this phase).
Verified manually: `tts save --manifest` produces a correct,
privacy-respecting manifest with a real checksum against the actual
compiled engine. No reviewer agent was available this session.

Acceptance criteria: - Every output has clear format and provenance. -
Manifests contain no secrets and avoid storing full text by default. -
SRT is valid and tested with fixtures. - Long text behavior is
documented and repeatable. - The speech core can be used by video
tooling without depending on Remotion or another renderer.

Review agent: inspect format correctness, timestamp semantics, privacy,
reproducibility, and audio integrity.

## Phase 8 --- Exporter architecture and Google Drive integration

**Goal:** Add optional, loosely coupled file export without making cloud
access part of speech generation.

Tasks: - \[x\] Define a common exporter contract: validate destination,
preview, upload, verify result, and report a remote reference. - \[x\]
Keep local files as the source of truth unless the user chooses another
policy. - \[x\] Research and choose a supported Google Drive integration
approach (OAuth-based API, user-configured tooling, or a separate
adapter). - \[x\] Request only the minimum OAuth scopes required. - \[
x\] Store refresh tokens using appropriate OS-protected storage where
possible; never in repository files. - \[x\] Support explicit
destination selection, including folder IDs where relevant. - \[x\] Add
dry-run, progress, retry, and resumable uploads where supported. - \[x\]
Handle duplicate names and remote naming policy explicitly. - \[x\]
Verify uploads and record remote file IDs/links in export results,
subject to permissions. - \[x\] Do not enable public sharing by default.

Status: Complete. `mac_speech.export` defines the common
`Exporter`/`ExportDestination`/`ExportPreview`/`ExportResult` contract
(`base.py`), with `LocalExporter` as the dependency-free reference
implementation and `GoogleDriveExporter` as the optional
`mac-speech[gdrive]` extra (not in the base install). OAuth scope is
the minimum (`drive.file` — this app can only see files it creates
itself); the refresh-token cache is a `0600` local file under
`~/.config/mac-speech/`, never in a repository. Resumable upload uses
`MediaFileUpload(resumable=True)`'s own chunked `next_chunk()` loop.
**Not tested against a real Google account** — provisioning a Google
Cloud project/OAuth client is account setup only a human should do;
the error paths (missing dependency, missing client secrets) were
verified against this real, unmodified environment, and the
success/upload path is covered by mocked tests
(`test_export_gdrive.py`). Before relying on this, run one real upload
against a disposable test folder.

Acceptance criteria: - Core speech works without Google credentials or
network access. - Drive adapter is optional and tested separately. -
User explicitly selects the files and destination to upload. - Upload
failures do not corrupt or remove local artifacts. - Credentials are not
logged or committed.

Review agent: review OAuth scope, token storage, retry/idempotency
behavior, and accidental sharing risks.

## Phase 9 --- Amazon S3 integration via AWS CLI, SDK, or configured account

**Goal:** Support AWS-native workflows while respecting standard AWS
credential management.

Tasks: - \[x\] Define S3 destinations using bucket and object prefix or
an `s3://bucket/prefix/` URI. - \[x\] Support a configurable provider
strategy: AWS CLI when installed, or an AWS SDK adapter when included as
an optional dependency. - \[x\] Reuse standard AWS credential resolution
(named profile, environment, role/SSO flows supported by the selected
SDK/CLI) rather than inventing credential storage. - \[x\] Make region,
profile, endpoint, and encryption options explicit where needed. - \[~\]
Support least-privilege permissions for only the target bucket/prefix
and required operations. - \[x\] Add dry-run, progress, retry/backoff,
checksum/size verification, and clear exit status. - \[ \] Handle large
files with multipart upload through the chosen provider. - \[x\] Avoid
bucket listing unless needed and authorized. - \[x\] Record
bucket/key/version and upload result in the export report, not
credentials. - \[ \] Add an optional post-upload URL generation feature
only with clear expiry and access semantics; do not make objects
public. - \[x\] Keep AWS SDK packages out of the base install if a CLI
adapter is sufficient for a given use case.

Status: Mostly complete. `S3Exporter` shells out to the `aws` CLI (no
`boto3` dependency); credential resolution is entirely the CLI's own
chain. `--profile`/`--region`/`--endpoint-url` are explicit constructor
options. **Verified against the real, configured AWS CLI on this
machine**: `aws configure list` showed real credentials, and
`--dry-run` executed cleanly end-to-end against a deliberately
nonexistent bucket, confirming command construction and
response-handling against the actual CLI, not just mocks. A real
upload+verify was deliberately not attempted — no specific
bucket/prefix was designated by a human for this session to write to.
`aws s3 cp`'s own multipart handling is relied upon rather than
reimplemented (deferred: not independently confirmed for files large
enough to trigger it). Least-privilege IAM policy design and
presigned-URL generation are documented as the user's own
responsibility (standard AWS credential/IAM practice) rather than
built into this exporter, since this project does not provision IAM
policies. `tests/unit/test_export_s3.py` covers the mocked
success/failure/dry-run/verify paths.

Acceptance criteria: - S3 export works with a user-configured AWS
profile or credential chain. - No long-lived keys are embedded in source
or config committed to Git. - A denied or expired credential produces a
useful error. - The selected upload path is documented and tested. -
Local artifact remains intact on failure.

Review agent: inspect IAM least privilege, credential resolution, region
behavior, multipart/retry handling, and public-access hazards.

## Phase 10 --- Slack integration through `team-slack-bridge`

**Goal:** Share generated artifacts or summaries to Slack without
duplicating Slack functionality.

Tasks: - \[x\] Inspect the existing `team-slack-bridge` repository, its
documented interface, supported operations, and authentication model
before designing integration. - \[x\] Prefer invoking its stable
CLI/API/MCP interface or implementing a small adapter around a
documented contract. - \[x\] Do not import internal code across
repositories without a versioned contract. - \[x\] Support a dry-run
preview of the target workspace/channel and message. - \[x\] Allow
sending a short summary and an attachment/link when the connected Slack
capabilities support it. - \[x\] Decide whether the actual file is
uploaded to Slack, stored in Drive/S3 and linked, or both. Make the
choice explicit. - \[~\] Respect Slack file-size limits, channel
membership, user permissions, and retention policy. - \[x\] Avoid
posting full transcripts or sensitive audio automatically. - \[x\]
Return message/channel references and delivery status where available. -
\[x\] Make retries idempotent where possible to avoid duplicate posts.

Status: Complete. `team-slack-bridge` was actually found and inspected
directly on this machine (`~/hornblower/team-slack-bridge`) —
`README.md`, `cli/`, and `core/` were read before writing any adapter
code, confirming: a stable, documented CLI (`node cli/post.js`/
`node cli/dm.js`) with universal `--dry-run`/`--json`, a built-in
idempotency-key mechanism (reused directly, not reinvented), and —
critically — **no file-upload/attachment command exists at all**,
which settled the "upload vs. link" decision explicitly: `SlackExporter`
only ever posts a text summary with an optional link, never the file
itself. `--dry-run` was verified **live against this machine's real,
already-connected "Hornblower" Slack workspace**
(`node cli/doctor.js --json` confirmed bot/user/socket-mode auth all
`ok`): the dry-run call returned exactly the documented
`{"ok": true, "dryRun": true, "request": {...}}` shape, and this
exporter's own dry-run path produced the correct result against that
same real install. A real, non-dry-run post was deliberately never
sent, to avoid placing an unannounced message in a real workspace as a
side effect of this session. Slack's own file-size/membership/
permission limits are enforced by Slack itself through
`team-slack-bridge`'s existing error responses (`{"ok": false,
"error": ..., "retryable": ...}`), surfaced as `MacSpeechError` rather
than independently re-validated by this adapter — a deliberate choice
to avoid duplicating logic the bridge already owns.
`tests/unit/test_export_slack.py` covers the mocked
channel/DM/idempotency/failure paths.

Acceptance criteria: - No second independent Slack authentication
implementation is added unnecessarily. - Sending is opt-in and previews
the destination. - Failures are clear and do not lose local artifacts. -
Integration can be disabled without affecting core TTS/STT.

Review agent: inspect interface stability, auth duplication, channel
targeting, attachment/link behavior, and accidental data disclosure.

## Phase 11 --- Workflow orchestration and video-generation integration

**Goal:** Enable speech assets to participate in a wider video pipeline
without coupling the toolkit to a particular video renderer.

Tasks: - \[x\] Define a workflow manifest referencing source text, audio
files, transcript files, SRT, timing/alignment outputs, and their
provenance. - \[x\] Support a pipeline of text input → TTS audio → STT
or alignment → SRT/word timestamps → downstream video tool. - \[x\]
Determine whether STT on generated audio is an acceptable timing
approximation or whether a dedicated forced-alignment engine is
needed. - \[x\] Expose stable file paths and machine-readable results
for Remotion or other renderers. - \[x\] Support chunking and
scene/paragraph boundaries for long narration. - \[x\] Keep expression
timing, visual editing, and rendering responsibilities in the video
project, not in the speech engine. - \[x\] Add a future plugin/hook
mechanism only if concrete workflow needs justify it. - \[x\] Ensure
each stage can be run independently and retried without regenerating
unrelated artifacts.

Status: Complete. `mac_speech.workflow` provides three independently
callable/retryable stage functions (`stage_synthesize`, `stage_align`,
`stage_render_srt`) plus `run_narration_pipeline` as a convenience
chain, each stage recording its own status/output/provenance into a
versioned `WorkflowManifest` (schema version 1, source text stored
only as a sha256 hash). Decided explicitly: alignment is STT-roundtrip
only (`mac_speech.align`), not a dedicated forced-alignment engine —
documented rationale in `docs/workflow.md`. **Verified for real, not
synthetically**: running the pipeline on a machine where the Apple STT
engine's locale quota happened to be exhausted (see
`docs/risk-register.md` risk #19 — root cause confirmed in this same
phase) produced exactly the required resilience: the `synthesize`
stage's audio file remained valid on disk while `align` failed
cleanly and the pipeline manifest recorded `"ok": false` with the
specific failure, instead of losing or corrupting the earlier
artifact. Scene/chunk boundaries are explicitly the caller's
responsibility (call the pipeline once per scene with its own
`basename`) — no scene-management was added to this module, keeping
video-project responsibilities out of the speech core. No plugin/hook
mechanism was added; none was justified by a concrete need. 14 new
unit tests (`test_workflow.py`, `test_stt_srt.py`, plus CLI tests) —
188 Python tests pass (4 still skip on the Apple-engine locale issue,
whose root cause this phase finally confirmed). No reviewer agent was
available this session.

Acceptance criteria: - A script can invoke speech stages
non-interactively. - Outputs and timings have explicit semantics. -
Video tools can consume artifacts without importing the speech engine's
internals. - Failed downstream stages do not invalidate successful
speech artifacts.

Review agent: validate workflow boundaries, reproducibility, retry
behavior, and timestamp accuracy.

## Phase 12 --- Packaging, releases, documentation, and operational quality

**Goal:** Make the project safe to install and easy to maintain.

Tasks: - \[x\] Choose packaging and distribution for the Python wrapper
and native binaries. - \[x\] Document code signing/notarization
implications if distributing signed macOS applications/binaries. - \[x\]
Decide how users obtain native binaries: build from source, release
assets, or package manager; document trust and integrity checks. - \[x\]
Provide install paths for TTS-only, STT-only, and combined installs. -
\[x\] Add version compatibility checks between wrapper and native
engine. - \[x\] Add CI for Python lint/type checks and unit tests; run
Swift builds/tests on macOS CI where available. - \[x\] Add smoke tests
for a clean install and a no-network core workflow. - \[x\] Add
dependency/license scanning and a software bill of materials if
appropriate. - \[x\] Document uninstall, upgrades, cache/model cleanup,
privacy, permissions, supported versions, and troubleshooting. - \[x\]
Provide example scripts and a small sample workflow. - \[x\] Create
release notes and a rollback procedure.

Status: Phase 12 implementation is locally verified; **public publication
remains blocked by the missing authorized project license** (risk #4).
Six independent workstreams were delegated; the main session integrated
their changes, independently tested the final repository/artifacts, and
resolved the separate Phase 12 review findings. No automatic commit,
release, upload, signing-account setup, or model download was performed.

Evidence:

- `docs/decisions/ADR-002-packaging-and-distribution.md`,
  `docs/packaging.md`, `MANIFEST.in`, and package README/metadata choose
  source-built native binaries plus Python-only wheel/sdist artifacts.
  The wheel was built **from the sdist**, inspected for boundaries,
  versions, conditional extras and license warning, and installed outside
  the checkout with `--no-index --no-deps`. No native binary/model is
  bundled; there are still zero base runtime dependencies.
- Strict required-integer TTS protocol validation rejects missing,
  malformed and incompatible versions as `protocol_version_mismatch`
  (exit 5), with actionable synchronization guidance. The legacy STT
  contract remains deliberately unversioned and unchanged.
- `.github/workflows/ci.yml` adds automatic Python 3.9–3.14 mocked tests,
  package/helper Ruff, **16-file scoped strict mypy**, offline inventory,
  and clean-wheel smoke. Swift CI is **manual/opt-in**, requiring a
  provisioned Swift 6.4 macOS runner; automatic hosted native coverage is
  explicitly deferred, not silently claimed. The workflow/shell commands
  were validated locally before the requested source commit/push. Hosted-CI
  outcomes remain separate evidence; do not infer them from local success.
- Main verification: `.venv/bin/python -m pytest tests/unit -q -rs`:
  **322 passed, 4 skipped** (unchanged Apple locale-reservation issue).
  Final mocked tests on local Python **3.12.5, 3.13.7, 3.14.8**: **322
  passed each** using source/PYTHONPATH and existing pure-Python pytest
  tooling, not clean installs. Python 3.9/3.10 remain unverified locally.
  Ruff and scoped mypy pass. Extracted-sdist tests with the extracted
  package explicitly selected: **311 passed, 15 skipped** (11
  repository-only installer simulations plus four STT fixtures).
- `bash scripts/ci_swift.sh` passed **39 native Swift tests** and a
  release build with isolated scratch/cache directories; a separate fresh
  scratch test also passed. Shared caches were not deleted. Existing CLT,
  deployment-target/Testing framework, and Sendable warnings remain.
- `scripts/smoke_core.py` passed in an engine-free and real TTS-only
  clean non-editable 3.11.3 venv, with a stripped credential environment,
  Python socket audit denial and macOS `sandbox-exec` network denial.
  WAV frames, manifest privacy and overwrite refusal were checked. STT
  smoke covers availability/input validation, **not successful real
  transcription**; installed Apple voices/assets are prerequisites.
- `docs/sbom.md` and the stdlib-only offline dependency/license scanner
  provide a direct inventory; **37 audit tests pass**. `--group runtime
  --check` intentionally returns 1 for the unresolved project license.
  This is not a resolved transitive release SBOM or an advisory scan;
  no vulnerability scan was performed. Release-resolution/audit steps
  are documented separately and are not core runtime requirements.
- `docs/installation.md` documents actual mode/XDG behavior, focused
  cleanup, sensitive OAuth cache, permissions and safe rollback without
  discarding dirty source. **11 isolated lifecycle tests pass**. Main also
  performed a real TTS-only source install, documented binary
  backup/uninstall/restore and Python wheel uninstall/restore in temporary
  HOME/XDG/venv paths, preserving unrelated artifacts and legacy files.
- `examples/narration_workflow.py` has **27 mocked tests**, retained
  stage manifests/audio, explicit Apple STT selection, a TTS-only option,
  empty/invalid cue rejection, and no implicit export. Main ran real
  TTS-only synthesis and repeat refusal, then explicitly previewed/copied
  the synthetic WAV through the local exporter. `CHANGELOG.md`,
  `docs/release-notes-template.md`, and `docs/releasing.md` describe
  unreleased changes, release gates, and tested rollback.

All separate Phase 12 review findings were fixed and rechecked. Protected
STT files, the root Swift manifest, native TTS sources and `install.sh`
match their start-of-session hashes. Earlier-phase deferred boxes remain
unchanged. Public-release readiness still requires an explicit license
decision, human-controlled committed source/CI runs, and any later actual
distribution/signing/platform validations; none are represented as done.

Acceptance criteria: - A new user can follow the documented install and
run a basic TTS example. - Core tests run in CI. - Optional integrations
are not required to pass core tests. - Release artifacts and
dependencies have traceable versions and licenses. - Uninstall and
rollback instructions are tested.

Review agent: do a clean-room install/release review, inspect
documentation accuracy, and look for hidden network/credential
requirements.

## Phase 13 --- Hardening and future capabilities

Only begin after the earlier phases deliver a stable, useful toolkit.

### Phase 13A — safe workflow workspaces and atomic outputs

**Scope:** harden the existing local narration workflow, not add every
optional future capability. Demonstrated need: basename traversal can put
files outside the requested workspace; subtitle/manifest writers overwrite
silently; native TTS finalization can delete a concurrently created output
even without `--force`. No protected legacy STT changes, model downloads,
remote exports, new runtime dependencies, or automatic commits are authorized.

Implementation checklist (check only after evidence):

- [x] Validate managed workflow basenames and reject unsafe output entries
  before invoking speech engines.
- [x] Atomically publish text, subtitle, manifest and native TTS outputs
  without clobbering another writer; make replacement explicit via `force`.
- [x] Serialize cooperating workflow runs for the same basename, preserve
  completed artifacts on failure, and clean up owned temporary state.
- [x] Add regression tests for traversal, symlinks, collisions, concurrent
  writers, cleanup and existing `--force` behavior.
- [x] Measure local hardening overhead and verify real offline TTS,
  packaging, Python quality gates and native Swift tests.
- [x] Obtain a separate review, resolve findings, and update docs/handoff
  with actual outcomes and the next human-controlled actions.

Status: **locally complete**, with separate review findings resolved and
rechecked. The broader candidate list remains an open-ended
backlog, not a promise to implement GUI/services/models without a concrete
need. Phase 12's committed baseline is `cdd74dd`; hosted CI run
`38117411339` completed successfully (Python 3.9–3.14, quality and clean
wheel jobs). The manual native job was intentionally skipped. Public
packaged release still requires an authorized project license.

Evidence (2026-10-11, local pre-commit snapshot after `cdd74dd`; the user
subsequently explicitly requested a separate source commit/push):

- Repository Python 3.11.3: **389 passed, four existing native STT skips**.
  Mocked suites on 3.12.5/3.13.7/3.14.8: **389 passed each** via existing
  pure-Python pytest tooling/PYTHONPATH, not clean installations.
- Package and explicit safety-test Ruff pass; strict mypy passes across
  **17 source files**. No base runtime dependency was added.
- `scripts/ci_swift.sh` returned **exit 0**, **48 Swift tests passed** and
  release build succeeded with isolated caches. An earlier filtered run hit
  the known TestingMacros toolchain issue; no global caches were deleted.
  A longer timeout was used for final complete-helper/cleanup verification.
- Rebuilt a Python wheel **from its sdist**, byte-checked actual modules,
  and ran the extracted package suite: **378 passed, 15 skips** (11
  repository-only lifecycle checks and four native STT fixtures).
  Clean 3.11.3 wheel/pip check and real updated-native TTS passed with
  credential environment stripped and Python/native network denial.
- Real TTS-only CLI workflow checkpointed audio/manifest at `0600`, removed
  its owned marker, and refused an unchanged-name repeat without touching
  existing audio. Native reservation tests verify `0700` staging directory,
  pre-created `0600` file and AVFoundation inode/mode preservation.
- Regression coverage includes actual parent-only SIGINT, post-constructor
  and interrupted-constructor child ownership, retained unconfirmed claims,
  foreign checkpoint replacement, symlink/FIFO/socket targets, cleanup and
  broken-stderr warnings preserving original cancellation/errors.
- Local file-I/O benchmark (30 samples each, 1 KiB/1 MiB): hardened median
  **1.365/1.935 ms** versus plain temp/replace **0.667/0.986 ms**.
  This observes roughly 0.7–1.0 ms added local write overhead, not a
  cross-filesystem performance guarantee; see `docs/phase13-hardening.md`.
- Protected legacy STT files/root manifest/Windows code remain unchanged.
  Native TTS was deliberately hardened; no STT locale repair was applied.
  No commit/push, release, cloud export, credentials setup or model download
   was performed during Phase 13A implementation/verification. A later
   source commit/push is now explicitly requested; verify its actual outcome.
   Its hosted CI had not run at this checkpoint; the green hosted
  run above belongs to the committed Phase 12 baseline only.

Remaining trust/operational limits: filesystem hard-link support and trusted
parent directories are required; publication is file-wise, not a multi-file
transaction or hostile same-UID sandbox. A crash or unconfirmed child can
leave a marker/private staging state; do not remove it based only on a stored
parent PID. Broader retention/log redaction/audit trails and the optional
candidate features below require their own scope/use case and are deferred.
Specifically, a versioned voice matrix needs additional real OS/hardware;
new formats/normalization need an approved concrete workload and tool/codec
checks; queues/services/watchers/GUI need explicit user demand; new engines,
models or providers need separate dependency/license/download/destination
decisions. Broader privacy/retention/audit automation is also deferred beyond
the implemented output controls. Unchecked candidates are not completion claims.

### Phase 13B — bounded local batch synthesis

**Scope:** generate WAV audio for a finite set of narration scenes without
manually invoking the per-scene workflow each time. No STT/alignment,
playback, exports, model downloads, daemon or new runtime dependency.
Default one worker; explicit parallelism is capped. Reuse the 13A path,
publication, claim and checkpoint protections rather than bypass them.

Checklist (mark only with verified evidence):

- [x] Typed Python batch API and versioned JSON scene input/ordered report.
- [x] CLI entry point, strict input/duplicate/output validation and private
  metadata without source text or raw engine diagnostics.
- [x] Bounded in-flight queue/workers, per-scene partial failures and explicit
  force behavior, retaining successful outputs.
- [x] Cooperative cancellation that stops/reaps active native writers, drains
  owned work and retains claims for unconfirmed cleanup.
- [x] Tests for limits, collisions, partial failure, report ownership,
  cancellation and CLI/core isolation.
- [x] Real offline batch example, performance/resource observations, packaging
  and quality checks, separate review and current docs/handoff.

Status: **locally complete**, with independent review findings resolved and
rechecked. Phase 13A source was pushed as
`56cb3bbae469afb91b82751617bcab1c08942ea8`; hosted CI run `38145240085`
completed successfully. The user authorized that transaction only; new 13B
implementation must not be committed/pushed automatically. After local
completion, the user separately requested committing/pushing Phase 13B;
verify that transaction's actual outcome rather than infer it from this snapshot.

Evidence (2026-10-11, local uncommitted changes after `56cb3bb`):

- `mac_speech.batch` typed API and `mac-speech tts batch` consume strict schema-1
  scene JSON, default to one worker (explicit cap 1–4), and limit batches to
  1000 scenes. Native admission waits for acknowledged Future registration;
  at most the worker cap is submitted/in-flight. Reports preserve input order.
- Aggregate and per-scene checkpoints are private, inode-owned and sanitized;
  source text/raw backend diagnostics are absent. Ordinary failures retain
  successful scenes and continue others. Unsafe native/I/O drain stops new
  submissions and retains claims. Cancelled error code is additive, exit 130.
- One owned communication exchange delivers complete long stdin/EOF while
  cancellation is monitored. Actual delayed-reader/backpressure regressions
  delivered 200,000 characters; reviewer also verified 250,000 mixed-Unicode
  characters with SHA-256. Interrupted thread startup, abandoned admission,
  real synthetic-child cancellation and NUL/surrogate validation are covered.
- Repository Python 3.11.3: **431 passed, four existing native STT skips**.
  Mocked source suites on 3.12.5/3.13.7/3.14.8: **431 passed each** using
  existing pure-Python pytest tooling/PYTHONPATH, not fresh installations.
  Ruff and strict mypy pass across **18 source files**; **42 new tests**.
- Isolated native check returned **exit 0**, **48 Swift tests passed** and
  release build succeeded, including matching cancelled-code mapping. The
  known TestingMacros diagnostic triggered a narrow private-cache/plugin
  retry; no global caches or preserved STT code were changed.
- Wheel rebuilt **from its sdist**, modules byte-checked against current
  source. Extracted package suite: **420 passed, 15 expected skips**.
  Fresh non-editable 3.11.3 wheel/pip check and real three-scene batch passed
  with stripped credential environment/macOS network denial, valid WAVs,
  private ordered report/checkpoints, repeat refusal and claim cleanup.
- Current real three-scene local sample: **4.163 s at one worker**, **2.206 s
  at two**, on M1 Pro/macOS 27.0.1 with installed ordinary system voices.
  This measured workload/cached-host result is not a universal speedup,
  energy/RSS claim or timing threshold. No runtime dependency was added.

The broader candidate backlog remains optional/deferred. This slice does not
transcribe, align, play, export, watch folders, provision voices, download models,
repair protected STT or publish packages. Public license and older/native platform
gates remain. `docs/batch-synthesis.md` gives the runnable example and limits.

Candidate enhancements: - \[ \] Voice and language capability matrix by
macOS version. - \[ \] More output formats, with explicit codec
validation. - \[ \] Better long-form synthesis, chunk stitching, and
silence trimming. - \[ \] Optional local web service or IPC server for
multiple client applications, if demand justifies a persistent
service. - \[x\] Queueing and bounded concurrency for batch synthesis (13B). -
\[ \] Optional audio normalization or post-processing through a
separately installed open-source tool. - \[ \] Additional open-source
TTS engines behind the same interface. - \[ \] Additional storage
providers through the exporter interface. - \[ \] Scheduled or
watched-folder workflows, disabled by default. - \[ \] More robust
content privacy controls, retention rules, and audit logs. - \[ \]
Optional GUI/menu-bar controls, only if the core CLI/API remains
independently usable.

Acceptance criteria: - Every added capability has a demonstrated use
case, performance data, dependency/license review, and tests. - The core
remains small and local-first. - No optional feature is allowed to
destabilize the core speech interfaces.

------------------------------------------------------------------------

# 8. Testing strategy

## Authorized maintenance — Apple STT risk #19 (2026-10-12)

This is explicit authorization to narrowly repair the formerly protected
`Sources/WhisperAppleTranscribe/` reservation handling, not rewrite STT or
continue unrelated Phase 13 features. Clean baseline independently verified:
`main`, `ad414abf9dce8b0055aa8a1810355aacb2e1bc0c`.

- [x] Independently reproduce both source defects and baseline **431 passed,
  four native skips**; verify current Apple SDK/docs (false means already reserved;
  capacity is device/storage-dependent, not universally five).
- [x] Resolve supported equivalent locale; classify named Speech domain/codes;
  serialize cooperating native invocations through complete analysis/output and
  awaited cleanup; release actual uniquely-owned asset locale only.
- [x] Focused mock tests for ownership/variants, capacity, false reuse, primary
  errors, cancellation and analyzer/result teardown; native platform/name/contracts
  and independent TTS remain unchanged.
- [x] Replace unsupported catch-and-skip with explicit Apple/installed-assets
  preflight and opt-in; provisioned regressions fail.
- [x] Real seven-recording en-US repetition, installed regional switching,
  borrowed-state invalid-media failure and text/JSON/segment+word SRT evidence.
- [x] Real newly-owned release after success, provider failure, closed output and
  cooperative cancellation after input consumption. The separately approved en_CA
  release/reacquisition windows returned to the same four other reservations;
  no downloads, global reset, other pre-existing releases or re-pinning occurred.
- [x] Complete final independent review/rechecks and record exact verification.

Status is **locally resolved for the two source defects** on the recorded Mac/SDK/
artifact, with real new ownership plus cleanup/readback evidence, not mocks alone.
Cached availability, abrupt death/non-cooperating clients, other platforms and
deployment of old installed binaries remain limits. Details and exact
command evidence: `docs/stt-reservation-repair.md`, `docs/verification.md`, current
handoff. Historical per-phase snapshots remain untouched. Implementation did
not include a commit/push, download, global reset or signing change. The user
subsequently explicitly authorized the **combined reviewed source/licensing
commit and push on main, no PR**. This transaction does not authorize reservation
eviction/recovery, a new queue service, package release or future automatic commits.

## 8.1 Unit tests

### Authorized follow-up — safe reservation maintenance (2026-10-12)

The combined source commit/push completed at `4769606b3d3aa9a38fa4b59dedc4b75d49b721cc`;
hosted CI run `38213808150` succeeded (Python/quality/clean wheel, native opt-in
job skipped). The user subsequently approved implementing the bounded recovery
recommendation from independent GPT Terra/Claude Opus design consultations.
Default stays en-US; Canadian/British/Australian/Indian English remain supported.
No region is declared unused merely because it is not the default.

- [x] Locked maintenance inspect/preview, and explicit exact single-target
  release with matching confirmation and unused/quiescent-client acknowledgement.
- [x] Optional installed-assets-only, exact-locale and newly-owned validation
  guards; preserve normal CLI defaults, transcript contract and all regions.
- [x] Isolate cleanup from caller cancellation and fully await release/readback;
  test cancellation-sensitive inventory mocks (not an asserted Apple defect).
- [x] Focused tests, borrowed-only native regression, independent review and docs.
- [x] One approved temporary en_CA maintenance release/readback: SDK returned
  true, only en_CA removed, four other reservations preserved.
- [x] Real newly-owned acquisition/release validation, after the initial **STOP** because the
  exact en_CA installed status became false after release. No transcription,
  reacquisition, installation/download or re-pinning followed. SDK still supports
  en_CA; physical file deletion is not established. New recovery scope needs approval.

The stopped result above is historical. The user then approved reservation-first
temporary no-download reacquisition; cached assets became ready while bound and
all four owned native outcomes passed, followed by seven owned repetitions and
five regional switches. Independent retained-evidence review found no new blocker
and supports local risk #19 resolution. No sustained neural-inference timing or
OS-wide network-activity claim is made. Latest readiness UX source disables implicit
transcription downloads and requires explicit asset-setup confirmation.

No ledger, persistent worker/cache, daemon, automatic pruning, asset download,
global reset, installed-binary replacement or new commit/push is authorized here.
The source maintenance interface is authorized; using its mutating path still
required separate exact-target approval, now granted for the bounded en_CA window.
The latest request also authorizes **TUI idea/design gathering**, not a full TUI,
new worker/cache service or source push. Preserve historical checkpoints below.
`docs/tui-proposal.md` records an optional STT/TTS/jobs/assets workspace, owned
process controls and preview-first maintenance; no frontend/dependency was added.
Validation-only ownership/analysis stderr events were added before the action;
47 Swift tests/release build passed. Real stopped-window JSON and executable
fingerprint are in `stt-approved-window-q645k4du/` under the approved temporary root.
Local evidence: **46 Swift STT tests/release build**, **491 Python/four opt-in
skips**, **495 with Apple opt-in/zero skips**, **48 independent TTS tests/release
build**, Ruff/mypy/legacy py_compile. Five regional offline word-JSON transcriptions
and locked previews pass without changing inventory; new-owned guard rejects
borrowed success. Independent reviewer reran 46 Swift tests and closed both medium
mock findings. These earlier safeguard counts remain history; the window above
does not count as owned-transcription evidence. Changes remain uncommitted and
risk #19 remains partial, with current inventory4/5 and exact en_CA uninstalled.

### Latest approved scope — cached reacquisition and generic readiness UX

The user approved temporary metadata-only en_CA reacquisition even though the SDK
pre-reservation installed flag is false: after binding, refuse analysis unless
ready, never create an installation request/download, and clean only new ownership.
The initial trial proved true en_CA acquisition, successful word JSON and joined
release/readback to the same four reservations without installation. Further
invalid/cancellation/output evidence is recorded in verification, not inferred.

The user also requested generic CLI/Python language setup guidance (e.g. French)
before analysis. Native transcription now forbids implicit downloads by default;
explicit `--install-assets` preview/confirmed setup is the only installation path.
Confirmed setup may retain a reservation intentionally for offline caching; it is
not auto-executed by the agent. Python preflights the exact selected helper and
prints its quoted resolved-locale setup command. This approved first-use behavior
change preserves transcript formats/all regions/base dependencies and does not
authorize a French download, persistent CA re-pin, new commit/push or TUI build.
See `docs/apple-asset-setup.md`.

The user subsequently requested committing/pushing this reviewed follow-up on
main/no-PR to the existing `manish96170` repository. This source-only transaction
supersedes the implementation checkpoint's no-commit restriction for this push
only; it does not authorize another real asset operation, installation/download,
binary replacement, TUI implementation or future automatic publication.

-   Input validation, configuration precedence, serialization, error
    mapping, filename handling, manifest schema, and CLI parsing.
-   Mock subprocesses and exporters for failure and timeout paths.
-   Verify logs never contain configured credentials or full text by
    default.

## 8.2 Integration tests

-   TTS voice discovery and audio-file generation on macOS.
-   Playback controls and process cleanup where supported.
-   STT regression tests against approved fixtures.
-   SRT parsing/validation and timestamp monotonicity.
-   Optional exporter tests using mocked providers and dedicated
    non-production accounts/buckets.

## 8.3 End-to-end tests

-   TTS-only install and offline synthesis.
-   STT-only install and existing transcription flow.
-   Combined installation.
-   TTS output file → manifest → optional export.
-   Transcript/SRT → optional export.
-   Slack message with a deliberately non-sensitive test artifact.
-   Video-workflow artifact handoff.

## 8.4 Performance tests

Measure and record: - Cold start and warm start. - Time to first audio
where measurable. - Total synthesis time and real-time factor. - Peak
resident memory and model load time. - Output size and audio duration. -
Long-text chunk boundaries and gap behavior. - TTS/STT latency
independently from cloud upload latency.

Do not set hard performance thresholds until a repeatable baseline has
been captured on the target Mac. Then define regression tolerances.

## 8.5 Manual validation checklist

Repeat this checklist for each intended release/environment. Its unchecked
boxes are not assertions that all these capabilities remain unimplemented;
dated per-phase evidence and `docs/verification.md` record completed checks.

-   [ ] No internet connection: native TTS works.
-   [ ] TTS installed without STT.
-   [ ] STT installed without TTS.
-   [ ] Missing optional model produces an actionable message.
-   [ ] Unauthorized Personal Voice does not break standard voices.
-   [ ] Existing files are not silently overwritten.
-   [ ] Export does not delete local artifacts.
-   [ ] Credentials and full transcript text do not appear in logs.
-   [ ] User can cancel long-running work and recover cleanly.
-   [ ] Repeated commands do not leave orphan processes.

------------------------------------------------------------------------

# 9. Agent workflow and phase governance

Use a main coding agent plus a separate reviewer agent when available.
The reviewer should challenge assumptions and inspect actual code and
test results, not merely approve the plan.

## Before each phase

1.  Read this plan and the current project documentation.
2.  Inspect the current repository state and Git diff.
3.  Identify prerequisites and phase-specific tasks.
4.  Create a short implementation checklist and risk notes.
5.  Do not start later-phase integrations just because they are
    architecturally interesting.

## During each phase

1.  Implement the smallest coherent slice.
2.  Run targeted tests after each significant change.
3.  Run regression tests before completing the phase.
4.  Keep changes scoped; do not mix refactors with feature work without
    justification.
5.  Update documentation and relevant ADRs as decisions become concrete.
6.  Keep secrets, tokens, private audio, and transcripts out of fixtures
    and logs.
7.  Do not commit automatically.

## Before marking a phase complete

-   [ ] All phase tasks are checked off or explicitly deferred with a
    reason.
-   [ ] Acceptance criteria have evidence from commands, tests, or
    manual checks.
-   [ ] Reviewer agent has reviewed the implementation and reported
    findings.
-   [ ] All high-severity review findings are fixed or documented as
    blockers.
-   [ ] Tests and checks are run again after fixes.
-   [ ] README and docs reflect actual implementation, not the original
    plan.
-   [ ] This plan's task checkboxes are updated.
-   [ ] Known limitations and follow-up tasks are recorded.
-   [ ] Git diff is reviewed for unrelated changes and accidental
    secrets.

A phase is not complete merely because code has been written. It is
complete when acceptance criteria are evidenced.

## Context-limit and handoff protocol

When the coding session approaches roughly 80% of its usable context, or
the agent expects to lose important state:

1.  Stop taking on new scope.
2.  Update this plan's checkboxes and current status.
3.  Update docs/ADRs that contain decisions made during the session.
4.  Record exact changed files, commands run, test outcomes, failures,
    and remaining risks.
5.  Create or update `docs/SESSION_HANDOFF.md` with:
    -   Current phase and objective.
    -   Completed work and key decisions.
    -   Exact files changed.
    -   Tests run and their outcomes.
    -   Known defects and unresolved questions.
    -   Next three concrete actions.
    -   Instructions for the next agent to inspect the diff before
        continuing.
6.  Provide a concise prompt for the next clean session, instructing it
    to read this plan and the handoff file first, inspect the repository
    and diff, and continue only the current phase.
7.  Do not claim unfinished tasks are done.

## Reviewer agent prompt template

> Independently review the current phase implementation against
> `PLAN.md`, the actual diff, architecture, and test evidence. Do not
> assume the implementation is correct because the main agent says it
> is. Look for correctness bugs, race conditions, subprocess leaks,
> API/OS compatibility problems, privacy and credential exposure,
> licensing risks, packaging regressions, weak tests, hidden coupling,
> and unnecessary complexity. Run or inspect relevant tests when
> possible. Return findings sorted by severity with file/line
> references, concrete failure scenarios, and recommended fixes. If
> there are no findings, state what you reviewed and what you could not
> verify. Do not expand scope into later phases.

------------------------------------------------------------------------

# 10. Definition of done for the product

The initial product is considered successful when:

-   [x] Native macOS TTS works locally and offline through Swift.
-   [x] TTS can speak text and save a valid audio file.
-   [x] A lightweight Python wrapper and CLI provide a stable,
    documented interface.
-   [x] Existing STT compatibility and owned cleanup validated locally.
    Real borrowed text/JSON/SRT/concurrent calls and owned success/failure/input-
    consumption cancellation now pass on the recorded Mac/SDK/artifact (risk #19).
    Other platforms/cache retention/abrupt death remain limits; default native
    skips are explicit opt-in prerequisites. First-use Apple setup is now explicit.
-   [x] STT and TTS can be installed and used independently.
-   [x] Available voices and capabilities are discovered rather than
    assumed.
-   [x] Personal Voice is handled only through supported APIs and
    permissions.
-   [x] Audio, JSON transcripts, and SRT outputs have documented
    formats.
-   [x] Performance has been measured on the target Apple Silicon Mac.
-   [ ] Optional neural TTS has been evaluated without bloating the base
    installation.
    Research-only evaluation is recorded; actual approved model/license,
    acceleration, and human-listening comparisons remain deferred in Phase 6.
-   [x] Google Drive, S3, and Slack integrations are isolated optional
    adapters, not core dependencies.
-   [x] S3 supports the selected AWS CLI/SDK credential path without
    hard-coded secrets.
-   [x] Slack integration reuses the `team-slack-bridge` contract where
    practical.
-   [x] Generated assets can feed a downstream video workflow without
    coupling the speech core to a renderer.
-   [x] Security, privacy, licensing, installation, troubleshooting, and
    uninstall behavior are documented.
-   [ ] Each phase has acceptance evidence, a separate review, and an
    updated handoff trail.
    Phase 12 received separate review/rechecks; earlier phases explicitly
    recorded reviewer unavailability. Do not retroactively claim those reviews.

Checked criteria refer to the documented local scope, not public-release
readiness, live remote exports, hosted-CI results, or untested OS/architecture
combinations. ADR-003 records the selected custom proprietary license; its
metadata/text inclusion is verified. Legal/third-party review and explicit
package publication remain separate gates, not consequences of a source push.

------------------------------------------------------------------------

# 11. Immediate next actions

1. Review the authorized risk #19 repair diff/evidence and rerun checks. Rebuild
   the Apple helper from matching source; a Python wheel cannot update native code.
2. Decide whether to authorize a **targeted, confirmed-unused** reservation
   recovery in this executable's identity to unblock real newly-owned cleanup
   testing. No release-all, asset deletion, separate-probe reset or quota evasion.
3. Execute the newly authorized combined source/licensing commit and push on
   `main` without a PR, excluding generated/private artifacts, then verify the
   actual remote ref and CI outcome. The combined reviewer verified local
   packaging/license inclusion, not a public package release. Unrelated future
   capabilities and earlier Phase 6/9 deferred validations remain out of scope.

The standing prohibition on automatic Git commits remains: authorization
for the current requested commit/push transaction is not future permission
to commit, publish, sign, export, or download models automatically.

## Original Phase 0 starting checklist (historical)

These were the discovery actions at plan creation, not instructions to restart
completed work:

1.  Locate and inspect the existing STT repository and Python wrapper.
2.  Run the current STT flow and record its baseline.
3.  Inspect current macOS/Swift APIs and repository packaging.
4.  Decide monorepo versus companion module with an ADR.
5.  Define a minimal TTS proof-of-concept using `AVSpeechSynthesizer`,
    without changing the existing STT path.
6.  Return a discovery report with actual repository facts, risks, and a
    phase-by-phase execution proposal before making broad structural
    changes.

**Important:** Original proposals alone are not implementation proof. Use
the dated completion evidence and actual repository/contracts, and validate
environment-specific claims before relying on them.
