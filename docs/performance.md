# Performance baseline (Phase 0)

**Machine:** M1 Pro, 16 GB RAM, macOS 27.0.1 (26A434), arm64.
**Purpose:** Preserve the Phase 0 discovery and Phase 2 first-run measurements.
These are historical snapshots, not a regression-tested benchmark suite.
Phase 6's completed repeatable TTS methodology/results are in
[tts-benchmark.md](tts-benchmark.md) and supersede measurements covered there.
The later Apple STT reservation defect is tracked as [risk #19](risk-register.md);
this discovery's successful STT run is not a current regression pass.

## STT (existing, unmodified) — Apple backend

Test input: `say -o test.aiff 'This is a local transcription test.'`
(≈2.47s AIFF, 22050 Hz mono 16-bit PCM, per `afinfo`).

| Observation | Result |
| --- | --- |
| Plain text output | Correct: `This is a local transcription test.` |
| Word-level SRT (`--srt --word-ts`) | 6 cues, one per word, timestamps monotonic and non-overlapping (0.000s–2.400s span) |
| Segment-level SRT (`--srt --seg-ts`) | 1 cue spanning 0.000s–2.460s |
| `--check` diagnostics | Correctly reports interpreter path, faster-whisper 1.2.1, HF_TOKEN unset, Apple binary path, Windows backend absent, per-model cache state |
| Apple speech asset install | Not observed on this run (assets already installed from prior use); first-use asset download time is **not yet measured** — follow-up for whoever first clears `AssetInventory` cache |
| Wall-clock timing | Not instrumented in this pass (no `time` wrapper used). **Follow-up:** add explicit cold/warm timing before treating this as a tracked baseline metric, per `PLAN.md` section 8.4 |

No faster-whisper or Windows-backend timing was captured in this pass (out of
scope for Phase 0; faster-whisper model was not downloaded —
`small.en: not downloaded` per `--check`). Capturing faster-whisper and
Windows timings is deferred to whichever phase first depends on comparing
them (likely Phase 4 regression work or Phase 6 benchmarking).

## TTS feasibility probe (throwaway scripts, not the real Phase 2 implementation)

Three standalone `swift` scripts were run outside the repository and deleted
after use. These numbers are **not a benchmark** — no warm-up, no repeated
trials, no instrumentation beyond what the one-shot run showed. They exist
only to confirm the public API surface works before Phase 2 design.

| Probe | Result |
| --- | --- |
| `AVSpeechSynthesisVoice.speechVoices().count` | 191 voices available offline, no network call observed |
| Personal Voice trait filter | 0 personal voices visible (none created/authorized on this machine) — expected and must stay a runtime check, never assumed |
| `AVSpeechSynthesizer.personalVoiceAuthorizationStatus` | Reachable without entitlements in a bare `swift` script |
| File synthesis (`write(_:toBufferCallback:)`) for "Testing file synthesis." (3 words) | Produced valid CAF file: 1 channel, 22050 Hz, Float32 PCM, ~1.71s duration, 150,896 audio bytes |
| Run-loop requirement | A plain `DispatchSemaphore.wait()` **hung indefinitely**; required pumping `RunLoop.current.run(mode:before:)` in a bounded loop to observe completion. This is a concrete lifecycle risk to design around in Phase 2, not just a scripting quirk — the real CLI must not block indefinitely if the completion callback is never invoked (e.g. unavailable voice, synthesis error) |

No cold-start, warm-latency, time-to-first-audio, real-time-factor, or
memory numbers were captured for TTS in Phase 0 — those require the actual
Phase 2 CLI (so there is a stable process to measure) and are explicitly
Phase 2/6 work, not Phase 0.

## TTS engine baseline (Phase 2, `mac-speech-tts` release build)

Measured with `/usr/bin/time -p` against the compiled
`engines/tts-swift/.build/out/Products/Release/mac-speech-tts` binary. This
is a first baseline from a handful of runs, not the repeatable
multi-text/memory/energy benchmark methodology Phase 6 defines — do not
treat it as a regression-tested performance contract yet.

| Measurement | Result |
| --- | --- |
| `voices` first invocation ("cold") | 0.48s wall time |
| `voices`, 3 subsequent invocations ("warm") | 0.12-0.13s wall time each |
| `save` of a 6-word sentence (process wall time) | 0.77s to produce a 2.13s audio file — synthesis-to-file is faster than real-time (expected: `write()` generates samples, it does not play them) |
| 2-sentence, ~45-word paragraph (`save`) | 19.69s of audio produced; not separately time-boxed in this pass |
| Orphan process check | 0 stray `mac-speech-tts` processes after 3 sequential `save` calls |

Time-to-first-audio for the `speak` (playback) path was not independently
instrumented; the manual signal tests (`docs/tts-engine.md`) measured
elapsed time to `didFinish`/stop/resume instead, which is a different
metric. Peak memory and energy were not measured. All of these are
explicitly Phase 6 scope.

**Phase 6 update:** the repeatable multi-text benchmark (cold/warm
latency, real-time factor, peak RSS, output size) is now in
`docs/tts-benchmark.md`, generated by `scripts/benchmark_tts.py`. That
document supersedes the single-run numbers above for anything it
covers.

## What is explicitly NOT measured yet

- faster-whisper cold start / model load time on this machine.
- Apple STT first-run asset-download time.
- Windows backend timing (no Windows machine available in this environment).
- Native TTS audible time-to-first-audio, CPU/energy, and human listening
  comparison against a neural engine. Cold/warm file synthesis, RTF, and
  peak RSS **were measured in Phase 6**; do not confuse those metrics with
  playback latency or treat the single discovery probe as a benchmark.
