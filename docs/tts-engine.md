# Native macOS TTS engine (`mac-speech-tts`)

**Status:** Phase 2–5 engine implementation complete; Phase 12 packaging and
isolated build/test checks are locally verified. Covers the standalone Swift engine; its
Python/CLI integration is Phase 3, and Personal Voice/system-voice
findings are Phase 5.

## What this is

`engines/tts-swift/` is an independent SwiftPM package that builds
`mac-speech-tts`, a one-shot CLI around `AVSpeechSynthesizer`. It has no
dependency on `whisper-py-convert-apple`, the Windows STT helper, or
Python, matching `PLAN.md` Phase 2's "keep the native TTS target
independent of the existing STT target."

Source builds require **Swift 6.4+** and a suitable Apple SDK. The TTS runtime
deployment target is macOS 13+; Personal Voice APIs use macOS 14+ guards.
Only macOS 27.0.1 arm64 runtime execution is verified. There are no external
Swift package dependencies; no prebuilt signed/notarized release is claimed.

```sh
swift build --package-path engines/tts-swift --configuration release
swift test  --package-path engines/tts-swift
```

For repeatable checks in a shared checkout, prefer the Phase 12 helper:

```sh
bash scripts/ci_swift.sh
```

It passed **39 Swift tests and a release build** using isolated scratch/cache
directories. On a Command-Line-Tools-only setup, interleaved builds can still
surface the known `TestingMacros` plugin/cache error (risk #17); the helper
retries only that compilation failure once in fresh private caches. Do not
delete shared/global caches as routine recovery. See [CI](ci.md) for the
toolchain/plugin boundary and manual/opt-in native CI requirements.

The compiled binary lands at
`engines/tts-swift/.build/out/Products/Release/mac-speech-tts` (debug at
the `Debug` equivalent). `python/mac_speech/capabilities.py` already knows
to look there (and at `~/.local/share/mac-speech/mac-speech-tts`, and at
`$MAC_SPEECH_TTS_BINARY`). Phase 3 implemented installation with
`./install.sh tts` (mode selection added in Phase 4); pip installs the Python
wrapper separately. Isolated helper builds use temporary scratch paths and
do not install/replace that binary. See [installation](installation.md).

## Why it is a separate SwiftPM package, not a second target in the root `Package.swift`

The root `Package.swift` declares `platforms: [.macOS(.v27)]` for the
existing STT binary. `AVSpeechSynthesizer`'s file-synthesis API only
requires macOS 13+. Adding TTS as a second target in that same manifest
would have silently inherited the macOS 27 floor — overstating what TTS
actually needs just because it shares a repository with STT. See
`docs/decisions/ADR-001-repository-and-module-boundaries.md` and
`docs/platform-support.md`.

## Three empirical findings that shaped this implementation

All three were reproduced with throwaway scripts outside the repository
before writing any real source, then re-verified against the actual
compiled binary and the automated test suite. Do not "simplify away" the
code that exists because of these findings without re-reproducing the
original bug first.

### 1. Multi-sentence `write()` truncation (the big one)

`AVSpeechSynthesizer.write(_:toBufferCallback:)`, given a **single**
`AVSpeechUtterance` containing multiple sentences, stops producing real
speech after the first sentence on this macOS version (27.0.1) — while
still emitting a plausible-length tail of audio frames, so the output file
*looks* like it has the right duration for the full text. This was proven,
not guessed:

- A 6-sentence, 167-word paragraph fed to `write()` as one utterance
  produced a file whose declared duration matched speaking roughly the
  first 1-2 sentences, but running it back through the existing
  `whisper-py-convert --engine apple` STT tool showed only the first
  sentence's words were actually audible/recognizable.
- Splitting that same text into separate `AVSpeechSynthesizer`/
  `AVSpeechUtterance` instances per sentence (one `write()` call each) and
  concatenating the output produced a file whose STT transcript matched
  every sentence, in order, with no missing content.
- `speak()` (direct playback, not file writing) was separately verified
  **not** to have this bug: an 81-word, multi-sentence utterance's
  `didFinish` delegate callback fired after ~31.7 seconds — consistent
  with normal speaking pace (~154 WPM), not truncation.

**Consequence:** `runSave` (`Synthesize.swift`) always splits text into
sentences via `splitIntoSentences` (`NLTokenizer(unit: .sentence)`,
`Sentences.swift`) and synthesizes one sentence per fresh
`AVSpeechSynthesizer` instance, concatenating the PCM into one output
file. This is not an optional "long text" code path — it runs for every
`save` call, including single-sentence ones, so there is only one code
path to trust. `runSpeak` queues the same per-sentence utterances onto one
`AVSpeechSynthesizer` (which natively plays a queue back-to-back) for
consistent behavior and clean stop/pause/resume boundaries, even though
`speak()` alone was not shown to need it.

A regression test for this exact failure mode exists in
`Tests/MacSpeechTTSCoreTests/IntegrationTests.swift`:
`saveSynthesizesEveryQueuedSentenceNotJustTheFirst`. It synthesizes three
sentences individually, sums their durations, and asserts the combined
multi-sentence `save` call's duration is not far short of that sum — the
exact property that was broken before chunking.

### 2. `AVAudioFile` needs an explicit release to flush its header

Letting an `AVAudioFile` go out of scope implicitly at the end of a
top-level script did **not** reliably flush/finalize its header: `afinfo`
reported zero duration and zero audio bytes even though the correct
number of audio bytes were physically present on disk (confirmed via file
size and a hex dump of the RIFF header's declared size field, which was
stale/wrong). Explicitly setting the `AVAudioFile?` variable to `nil`
after the write loop completes fixed this deterministically.

**Consequence:** `runSave` always does `audioFile = nil` immediately after
its synthesis loop, before reading the file back or moving it (see the
comment at that line in `Synthesize.swift`). Do not refactor this into
relying on ARC scope-exit timing.

### 3. `AVAudioFile`'s container comes from the destination URL's
   extension, not from `settings`

Writing with explicit linear-PCM `settings` to a path ending in a generic
`.tmp` extension silently produced a **CAF** container (not WAV/AIFF),
regardless of the `AVFormatIDKey`/`AVLinearPCMIsBigEndianKey` values
passed in `settings`. The sample format inside was correct; only the
container "wrapper" was wrong — `file`/`afinfo` reported `CoreAudio Format
audio file version 1` for a file later renamed to `.wav`.
`AVAudioFile(forReading:)` round-tripping that same mislabeled file does
**not** surface this — it reads CAF just fine — so a test that only reads
the file back through `AVAudioFile` cannot catch this class of bug.

**Consequence:** the atomic-write temp file (`runSave`'s `tempURL`) is
named to preserve the real target extension
(`.<name>.mac-speech-tts-<uuid>.tmp.<ext>`), not a generic `.tmp`. The
test suite's `saveWritesTheDeclaredContainerNotJustTheDeclaredSampleFormat`
reads the first four magic bytes of each produced file (`RIFF`/`FORM`/
`caff`) rather than trusting `AVAudioFile` to tell it the container type.

### Separately: a mismatched-settings corruption hazard

Writing AIFF-style big-endian PCM `settings` to a `.wav`-extensioned URL
(mismatched on purpose, during discovery) produced a valid-looking WAV
header with **zero** audio bytes/duration — a second, different way
format/container mismatches silently corrupt output. This is why
`--format` always drives a single, fixed settings dictionary
(`AudioFormat.swift`) and the output extension is validated against it
(`resolveOutputURL` in `Synthesize.swift`) rather than ever being used to
*infer* the format, per `PLAN.md` section 5.1.

## Supported audio formats (verified, not assumed)

| `--format` | Container | Sample format | Sample rate | Verified with |
| --- | --- | --- | --- | --- |
| `wav` (default) | RIFF/WAVE | 16-bit linear PCM, little-endian | 22,050 Hz | `file`, `afinfo`, magic-byte test, STT round-trip |
| `aiff` | IFF/AIFF-C | 16-bit linear PCM, big-endian | 22,050 Hz | `file`, `afinfo`, magic-byte test |
| `caf` | CAF | 32-bit float PCM | 22,050 Hz | `file`, `afinfo`, magic-byte test |

All three are mono (1 channel). The output path's extension must match
the chosen format's canonical extension (`.wav`/`.aiff`/`.caf`); if
omitted, it is appended automatically. A mismatched extension is rejected
with `invalid_argument` rather than silently honored or inferred.

## Process lifecycle: stop, pause, resume

`speak` blocks until all queued sentences finish or it is interrupted.
Verified manually (background process + `kill -SIG` from a separate
shell) and documented here because it is easy to get subtly wrong:

- **SIGINT or SIGTERM -> stop.** `signal(sig, SIG_IGN)` first disarms the
  default disposition, then a `DispatchSource.makeSignalSource` handler
  (the Apple-recommended, async-signal-safe pattern — not a raw C signal
  handler) calls `stopSpeaking(at: .immediate)` and marks the result
  `stopped_early: true`. Verified: process exited cleanly ~1.2s after
  SIGINT was sent partway through a longer utterance.
- **SIGTSTP -> pause.** Installing a handler for SIGTSTP supersedes the
  kernel's default "stop the process" action — verified with `ps -o stat`
  showing the process stayed in state `S` (sleeping), never `T`
  (stopped), across a real SIGTSTP delivery.
- **SIGCONT -> resume.** Verified: after a SIGTSTP-then-3-second-wait-
  then-SIGCONT sequence, the process correctly resumed and completed with
  an elapsed time consistent with (base duration + pause duration), not a
  restart or a stall.
- A Phase 0 finding still applies: never gate completion on a raw
  `DispatchSemaphore.wait()` — it hung indefinitely in one Phase 0 probe
  when the completion callback was never invoked. Both `runSave` and
  `runSpeak` instead pump `RunLoop.current.run(mode:before:)` in a bounded
  loop against `options.timeoutSeconds`, so a stuck callback times out
  (`ErrorCode.timeout`, exit 124) instead of hanging the process forever.

There is no automated end-to-end test for `speak`'s audible playback path
(it would make noise every `swift test` run); the signal behavior above
was verified manually and the shared per-sentence logic it depends on is
covered by automated tests.

## Phase 13A file publication and privacy

`runSave` now checks destination entry types before resolving a voice and
again when publishing. Symlinks, directories, FIFOs and sockets are refused
even with `--force`. Regular replacements use atomic POSIX rename; default
publication uses atomic create-if-absent hard linking, never check-then-delete.
Unsupported hard-link destinations fail closed instead of copying partial data.

An exclusively created `0700` staging directory contains an extension-preserving
file reserved at `0600` before AVFoundation opens it. The inode/mode is verified
before PCM writes and remains private after publication. Owned temporary state
is cleaned on normal completion/error; process crashes can leave private
staging state for explicit inspection after writers are confirmed stopped.
The synthesis timeout error no longer quotes the input sentence.

Rebuild/install this engine from the same updated source as the wrapper;
protocol compatibility alone does not upgrade an old executable's filesystem
behavior. See [workflow hardening](phase13-hardening.md) for trust boundaries,
cancellation and checkpoint rules. No legacy STT source changed.

## JSON protocol conformance

Every invocation prints exactly one JSON document to stdout and nothing
else; all diagnostics go to stderr via `diagnostic()`. The shape matches
`docs/protocol.md` and `python/mac_speech/native_protocol.py` exactly:
`{"status", "protocol_version", "result", "error"}`, with
`error.code` values drawn from the same string set as
`python/mac_speech/errors.py`'s `ErrorCode` (verified by
`ErrorsTests.swift`'s `rawValuesMatchPythonErrorCodeStrings` /
`exitCodesMatchPythonMapping`). Keep both sides in sync by hand; there is
no shared schema file generating either side yet.

## CLI reference

```text
mac-speech-tts <voices|speak|save|personal-voice-status> [options] [text]

voices                   List available voices as one JSON document
speak <text>             Speak text through the default audio output
save <text> --output P   Synthesize text to an audio file
personal-voice-status    Report (never request) Personal Voice authorization status

--voice <identifier>     Voice identifier (default: system default voice)
--language <locale>      BCP-47 locale, used to pick a voice if --voice is omitted
--rate <0.0-1.0>         Speech rate (default: AVSpeechUtterance's own default)
--format wav|aiff|caf    Output container for `save` (default: wav)
--output <path>          Required for `save`
--force                  Overwrite an existing output file
--stdin                  Read text from standard input instead of an argument
--timeout <seconds>      Safety timeout: per-sentence for `save`, total for `speak` (default: 120)
```

## Known limitations / explicitly deferred

- Voice/rate selection is per-utterance only; there is no persistent
  "default voice" configuration yet (future work, if needed).
- No pitch or volume control (not required by `PLAN.md` Phase 2; can be
  added later behind the same `--format`-style explicit-flag pattern).
- Sample rate is fixed at 22,050 Hz for all formats; this matched what
  `AVSpeechSynthesizer` actually produced natively during testing on this
  machine and was not independently varied. Revisit if a future voice/OS
  combination produces audibly different quality at a different native
  rate.
- The exact set of voices the compiled binary sees fluctuates run to run
  (see Phase 5 finding below) — do not assume a fixed voice count or that
  every "premium"/"enhanced"-quality voice visible to other processes is
  visible here.

## Personal Voice and system-voice findings (Phase 5)

**Personal Voice correctly requires macOS 14+, not macOS 13+ as Phase 2
initially (incorrectly) documented.** `AVSpeechSynthesizer
.personalVoiceAuthorizationStatus` failed to compile against this
package's macOS 13 floor with "only available in macOS 14.0 or newer" —
caught only once an actual `#available` guard was required by the
compiler against a real deployment target; a bare `swift -e` script
(no deployment-target restriction) would never have caught this. Fixed
with `if #available(macOS 14.0, *) { ... } else { return "unsupported" }`
in `personalVoiceAuthorizationStatusString()` (`Voices.swift`). Lesson:
verify API availability by compiling against the actual package
deployment target, not by running a throwaway script.

**This engine reports Personal Voice authorization status; it never
requests it.** `mac-speech-tts personal-voice-status` calls the
read-only `AVSpeechSynthesizer.personalVoiceAuthorizationStatus`
property only. A wrapper around `AVSpeechSynthesizer
.requestPersonalVoiceAuthorization` was deliberately **not** built after
testing showed its completion handler never fires from this compiled,
unsigned, bundle-less binary — reproduced twice, including once when
the status was already `.authorized` (so it was not merely "waiting on
a system prompt that would appear"). The most plausible explanation:
this API expects a real app bundle with an `Info.plist` declaring
`NSPersonalVoiceUsageDescription`, which a bare SwiftPM executable does
not have. Per `PLAN.md` Phase 5 ("avoid depending on private APIs...
the app never implies it can create or extract a Personal Voice
itself"), authorization must happen some other way — a properly bundled
app, or because the user already uses Personal Voice with other Apple
software on this Mac — and this tool only ever reports whatever the
system has already decided.

**Verified end-to-end: once authorized, Personal Voice works through
the exact same, unmodified code path as any other voice.** On a Mac
where the user had already created Personal Voice(s) through Apple's
own flow, `personal-voice-status` reported `"authorized"`, `voices`
correctly flagged those entries with `is_personal_voice: true` (and
only those entries — never a false positive on an ordinary voice), and
`save --voice <personal-voice-identifier>` produced a valid, correctly
attributed audio file. No special-case code was needed for any of this:
`resolveVoice()` and `runSave()`/`runSpeak()` already treat a Personal
Voice identifier exactly like any other `AVSpeechSynthesisVoice`
identifier. **Do not commit, log, or print the specific name/identifier
of a real Personal Voice anywhere** — those are real personal data
belonging to whoever's Mac they were tested on, not test fixtures.
Automated tests that encounter a real Personal Voice on the host must
only assert on counts/flags/success, never on the specific name.

**Observed, not fully explained: authorization status changed from
`not_determined` to `authorized` partway through this session**,
without ever observing the request's completion handler actually fire.
Plausible explanations (not confirmed): the system may resolve
authorization asynchronously through a path independent of that
specific completion handler, or a non-sandboxed command-line process
running as the logged-in user may receive more permissive treatment for
already-user-configured assistive/accessibility-adjacent features than
the formal per-app `AVSpeechSynthesizerPersonalVoiceAuthorizationStatus`
API suggests. Do not rely on a specific transition mechanism — only on
the fact that `personal-voice-status` always reflects whatever the
system currently reports, checked fresh on every call.

**Voice enumeration count is unstable, and the compiled binary
consistently sees somewhat fewer voices than a fresh `swift` script
run in the same session** (observed: 180-182 from the compiled binary
across several runs, vs. 191 from a `swift -e`/`swift file.swift`
script moments apart, on the same machine, same user session). The
missing entries were specifically the non-default-quality
("enhanced"/"premium"-named) voices in one comparison. This was *not*
observed to be randomly flaky run-to-run for the script context (191
was stable there), but the compiled binary's count did vary across
runs during this session (180, then later 182) — plausibly related to
the same kind of asset-reservation instability documented for the STT
binary in `docs/risk-register.md` risk #19 (both are unsigned,
bundle-less SwiftPM executables). Do not assume the voice catalog
reported by `voices` is exhaustive or stable; always re-query rather
than caching a voice list across invocations.

## Python/CLI integration (Phase 3-5)

The engine documented above is wired into `mac_speech`:
`python/mac_speech/tts/` (`client.py`, `engine.py`, `models.py`) spawns
this binary as a subprocess, parses its JSON, and exposes typed Python
functions (`list_voices`, `personal_voice_status`, `speak`,
`synthesize_to_file`, `stop`, `pause`, `resume`) and `mac-speech tts
<voices|personal-voice-status|speak|save|stop|pause|resume>` CLI
subcommands. See `docs/configuration.md` for environment variables,
`examples/` for Python/shell/agent usage, and this file's "Process
lifecycle" section above for how cross-process `stop`/`pause`/`resume`
work via a small PID file.
