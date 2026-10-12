# Toolkit architecture and Phase 0 discovery

**Current status:** Phase 13B source is committed at the verified `ad414ab`
baseline; authorized STT risk #19 maintenance is partially verified (2026-10-12).
Publication remains outside this task; separately added [licensing guidance](licensing.md)
supersedes historical missing-license statements. Hosted Python CI does not
establish native macOS 27 STT coverage.

## Current repository boundaries

- `whisper-py-convert.py`, root `Package.swift` and
  `Sources/WhisperAppleTranscribe/` retain the legacy STT contract; `windows/`
  remains a separate, untouched helper. See [the legacy extension guide](../ARCHITECTURE.md).
- `python/mac_speech/` supplies the additional typed API/`mac-speech` CLI,
  diagnostics, STT/TTS adapters, manifests, SRT/WebVTT, approximate
  STT-roundtrip alignment, narration stages, and explicit local/Drive/S3/Slack
  exporters. The base Python dependencies are empty; provider tooling is optional.
- `engines/tts-swift/` is a **separate SwiftPM package**, not a root target.
  Both source manifests require Swift tools 6.4; TTS targets macOS 13+ and
  Apple STT macOS 27+. Neither has external Swift package dependencies.
- `install.sh [stt|tts|all]` builds the selected native engines independently.
  Every mode copies the legacy script/symlink; pip installs `mac-speech`
  separately. Wheel/sdist artifacts are Python-only, not full native-source
  archives. See [installation](installation.md), [packaging](packaging.md), and
  [ADR-002](decisions/ADR-002-packaging-and-distribution.md).
- `tests/`, `scripts/`, and `.github/workflows/ci.yml` now provide tests,
  scoped quality checks, isolated Swift checks, and clean-wheel/offline smoke.
  Automatic CI covers mocked Python jobs; native CI is manual/opt-in on a
  provisioned Swift 6.4 macOS runner. Local evidence and limits are in
  [verification](verification.md), [CI](ci.md), and [platform support](platform-support.md).

Apple STT [risk #19](risk-register.md) is **partially repaired** in separately
authorized maintenance (2026-10-12). The helper resolves a supported equivalent,
serializes cooperating per-user invocations through awaited cleanup, borrows
pre-existing reservations and releases only its uniquely identified new asset
locale. The native transcript contract and independent TTS package are unchanged.
Read-only `--inventory-status` reports this executable's reservation state;
neither it nor the repair resets old state. See [repair evidence](stt-reservation-repair.md).
Native success is never inferred from diagnostics or skipped tests.
Neural-engine installation and real remote export validation remain deferred.

## Historical Phase 0 discovery (2026-10-09)

The numbered sections below preserve the facts and experiments recorded **at
discovery**, not present-day absences or instructions. Package/tests/CI were
subsequently added and Personal Voice observations changed in Phase 5; the
current risk register and TTS docs take precedence. See [ADR-001](decisions/ADR-001-repository-and-module-boundaries.md)
for the original decision and its implementation clarification.

## 1. Repository at discovery

`whisper-py-convert` is a **speech-to-text (STT)** command-line tool with
three interchangeable backends, unified by one Python entrypoint:

```text
whisper-py-convert.py          Single-file Python CLI/dispatcher (no package,
                                no subcommands; flat argparse)
Package.swift                  Swift package, single executable target
                                "whisper-py-convert-apple"
Sources/WhisperAppleTranscribe/main.swift
                                Apple SpeechAnalyzer/SpeechTranscriber backend
windows/                        Optional C#/MSIX Windows AI Speech backend
install.sh                      Builds Swift backend (if on macOS+Swift) and
                                installs the Python script + binary to
                                ~/.local/share and ~/.local/bin
BROWSER.md                      Notes explaining why there is no browser
                                frontend yet (deferred)
ARCHITECTURE.md, README.md      Existing docs for the STT tool
```

There is **no Python package** (`mac_speech` or otherwise), no
`pyproject.toml`/`setup.py`, no `tests/` directory, no CI configuration
(`.github/` absent), and no `LICENSE` file in the repository root. This is a
single-maintainer personal tool, not a packaged/distributed library.

The CLI is flat, not subcommand-based:

```text
whisper-py-convert [--model M] [--engine auto|apple|windows|faster-whisper]
                    [-o OUTPUT] [--language L] [--srt] [--seg-ts|--word-ts]
                    [--check] INPUT
```

This is a different shape than the `mac-speech <noun> <verb>` CLI sketched in
`PLAN.md` section 4.1. Any new unified CLI is an **addition**, not a rename or
rewrite of this entrypoint.

## 2. Verified environment facts (this machine)

Captured directly, not assumed:

| Fact | Value |
| --- | --- |
| macOS product version | 27.0.1 (build 26A434) |
| CPU architecture | arm64 (Apple Silicon) |
| Swift | swift-driver 1.168.6, Apple Swift 6.4 (swiftlang-6.4.0.34.1), target `arm64-apple-macosx27.0.0` |
| Python | 3.11.3 (`/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`) |
| Xcode | Only Command Line Tools installed; no full Xcode (`xcodebuild` unavailable) |
| `swift build` SDK | macOS SDK 27.0 via `xcrun` |
| faster-whisper | 1.2.1 installed, matches pinned `REQUIRED_VERSION` |
| Apple STT binary | Already built at `.build/out/Products/Release/whisper-py-convert-apple` (both Release and Debug present) |
| Installed CLI | `~/.local/bin/whisper-py-convert` symlink to `~/.local/share/whisper-py-convert/whisper-py-convert.py`; a separately-installed copy of the Apple binary also lives in `~/.local/share/whisper-py-convert/` |
| Git remote | `https://github.com/manish96170/whisper-py-convert.git`, branch `main`, clean except untracked `PLAN.md` |

`SFSpeechRecognizer.authorizationStatus()` returns `0`
(`.notDetermined`) when probed from a standalone `swift -e` script outside
the app bundle — expected, and irrelevant to the newer `SpeechTranscriber`
API the Apple backend actually uses, which does not require that legacy
authorization call.

## 3. STT baseline behavior (reproduced, not assumed)

Reproduced the exact smoke test documented in `ARCHITECTURE.md`:

```sh
say -o /private/tmp/whisper-py-convert-test.aiff 'This is a local transcription test.'
python3 whisper-py-convert.py --engine apple /private/tmp/whisper-py-convert-test.aiff
python3 whisper-py-convert.py --engine apple /private/tmp/whisper-py-convert-test.aiff --srt --word-ts
python3 whisper-py-convert.py --engine apple /private/tmp/whisper-py-convert-test.aiff --srt --seg-ts
```

Results:

- Plain text: `This is a local transcription test.`
- Word-level SRT: 6 cues, one per word, monotonically increasing timestamps
  (e.g. `00:00:00,000 --> 00:00:00,300` for "This" through
  `00:00:01,620 --> 00:00:02,400` for "test.").
- Segment-level SRT: 1 cue spanning the whole utterance
  (`00:00:00,000 --> 00:00:02,460`).
- `--check` correctly reports Python path, faster-whisper version, HF_TOKEN
  state, Apple backend path, Windows backend absence, and per-model cache
  status.

One transient failure was reproduced and diagnosed: running the Apple engine
*immediately* after `say` wrote the file in the same shell pipeline raised
`Input file does not exist or is not a file`, even though `ls`/`file` showed
the file moments later. This is a filesystem-visibility race in the test
harness (writing to `/private/tmp` right after `say` exits), not a defect in
`whisper-py-convert.py` or the Apple backend — a short delay or `sync` between
`say` and the transcribe call avoids it. Documented here so it is not
mistaken for a regression in later phases.

**Conclusion: the existing STT workflow is reproducible and unmodified.** No
source files for the STT path were changed during this discovery.

## 4. TTS feasibility probe (read-only, no repo changes)

To de-risk Phase 2 before any implementation, three throwaway Swift scripts
were run outside the repository (`swift -e` / `swift file.swift`, no project
files touched) and then deleted:

1. **Voice enumeration** — `AVSpeechSynthesisVoice.speechVoices()` returned
   **191 voices** on this machine, including compact, premium, and
   `gryphon-neural` quality tiers across many languages/locales (e.g.
   `com.apple.voice.compact.en-IN.Rishi`, `com.apple.voice.Aman.premium`).
   Voice identifiers, names, languages, and quality are all available through
   public API — no scraping or private API needed.
2. **Personal Voice** — `AVSpeechSynthesisVoice.speechVoices()` filtered by
   `.isPersonalVoice` trait returned **0** voices on this machine (none
   created/authorized). This confirms Personal Voice availability must be
   treated as a runtime capability check, never assumed present, exactly as
   `PLAN.md` section 2 and Phase 5 require. `AVSpeechSynthesizer
   .personalVoiceAuthorizationStatus` is the documented public API for
   checking authorization and was reachable without entitlements in this
   probe.
3. **Synthesis to file** — `AVSpeechSynthesizer.write(_:toBufferCallback:)`
   successfully produced a valid, playable audio file with **no network
   access and no dependency on the STT binary, process, or Python wrapper**.
   `afinfo` confirmed a well-formed CAF container: 1 channel, 22050 Hz,
   32-bit float PCM, ~1.71s duration for a short test phrase. This validates
   the core Phase 2 assumption: native file synthesis is possible with public
   API only.

Caveats surfaced by the probe, to track as risks (see
`docs/risk-register.md`):

- `write(_:toBufferCallback:)` is callback-based and required running a
  bounded `RunLoop` to drain; a naive `DispatchSemaphore.wait()` without
  pumping the run loop **hung indefinitely** in a plain `swift script.swift`
  process. The real Swift TTS CLI (Phase 2) must use a run loop /
  `async`-compatible wrapper deliberately, not a raw semaphore, to avoid
  hangs — this is a concrete lifecycle risk for the "do not leak child
  processes or leave audio sessions stuck" acceptance criterion.
  **Follow-up for Phase 2:** evaluate whether `AVSpeechSynthesizer`'s
  Swift Concurrency surface or an explicit `CFRunLoop` adapter is the
  more deterministic implementation; this needs its own prototype under
  the actual CLI process model (one-shot vs. long-running) before Phase 2
  design.
- The output container was CAF (float32), not AIFF/WAV/MP4 — do not assume a
  specific container/codec until Phase 2 explicitly tests and documents
  `AVAudioFile` settings/format options against downstream tooling (e.g. SRT
  tooling, video pipeline, Slack/S3 playback compatibility).

## 5. Repository/module boundary decision

See `docs/decisions/ADR-001-repository-and-module-boundaries.md`. Summary:
**extend this repository in place** (monorepo), add new, clearly separated
top-level modules for TTS and the shared Python wrapper, and leave
`whisper-py-convert.py`, `Package.swift`'s existing target, and `install.sh`'s
existing behavior untouched until a later phase explicitly needs to adapt
them.

## 6. Known issues and rollback strategy

Known issues identified during discovery (none require code changes to fix
right now):

1. No `LICENSE` file — license terms for this repository are currently
   undefined. Any decision to depend on third-party models/engines (Phase 6,
   8-10) must not be blocked by this, but publishing/distribution (Phase 12)
   should resolve it first.
2. No automated tests, no CI. Phase 1+ introduces `tests/` without touching
   the existing STT code paths.
3. `whisper-py-convert.py` has no package metadata (`pyproject.toml`), so it
   cannot currently be `pip install`-ed; it is copied by `install.sh`
   instead. The new `mac_speech` package (Phase 1) will have its own
   `pyproject.toml` and must not require changes to this install model for
   the existing tool.
4. The Windows backend (`windows/`) is unrelated to macOS TTS work and is
   explicitly out of scope for this plan; it is noted here only so future
   agents do not assume it needs to change.

**Phase 0 rollback observation:** discovery made no source changes, only
new documentation. This is not authorization to remove today's additions or
use `git clean` on a shared dirty checkout. For current rollback, preserve
source and artifacts and restore a kept matching wheel/native pair or use a
separate reviewed source directory; see [installation](installation.md#rollback).
