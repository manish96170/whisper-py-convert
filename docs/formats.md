# Artifact formats, manifests, and timing semantics (Phases 7–13A)

## Artifact directory conventions

This toolkit does not impose a mandatory artifact directory — file-producing
speech commands accept explicit output paths (narration workflows use an
output directory/basename), consistent with
`PLAN.md`'s "an option to specify an output path." When a caller wants
an auto-named, collision-safe default instead of choosing their own
path, `mac_speech.artifacts.suggest_artifact_path(directory, prefix=,
extension=)` generates one deterministically:
`<prefix>-<UTC timestamp>-[counter].<extension>` — never silently
overwriting an existing file, and never requiring a specific directory
layout.

## Overwrite protection and atomic writes

File-producing commands refuse existing regular outputs unless `--force` is
explicit (`output_exists`, exit 3). Phase 13A extends this to raw SRT helpers,
artifact sidecars and `WorkflowManifest.write`: Python callers must pass
`force=True` when replacement is intended. Requested sidecars are preflighted
before the speech/transcription operation. Symlink, directory and special-file
destinations are refused even with force (`invalid_argument`, exit 2).

Completed temporary files are atomically linked into absent destinations;
explicit regular-file replacement uses atomic rename, never truncation or a
check-then-delete. A concurrent first publisher wins without being clobbered.
Unsupported hard-link filesystems fail closed; choose a suitable local
destination. Text files are staged at `0600`; native audio is reserved at
`0600` in a private `0700` staging directory before AVFoundation opens it.
The real container extension is retained. Published outputs are `0600`.

These are **individual-file** visibility guarantees, not a transaction across
all outputs or power-loss durability. Managed pipelines additionally claim
their basename and track checkpoint inode ownership; raw stage/helper calls
do not automatically claim a whole workflow. Parent directories must be
trusted; hostile same-UID directory replacement/in-place mutation is not
sandboxed. See [workflow output safety](workflow.md#phase-13a-managed-workspace-and-overwrite-rules)
and the fresh-directory [narration sample](../examples/README.md).

## Manifests (opt-in, `--manifest`)

A manifest is a JSON sidecar: `<artifact-path>.manifest.json`, written
only when `--manifest` is passed (never automatic — PLAN.md describes
manifests as something to "optionally create"). Schema
(`mac_speech.artifacts.Manifest`, `MANIFEST_SCHEMA_VERSION = 1`):

```json
{
  "schema_version": 1,
  "artifact_id": "b27562825b4b4c65",
  "created_at": "2026-10-10T18:57:34Z",
  "operation": "tts_save",
  "engine": "mac-speech-tts",
  "output_path": "/path/to/narration.wav",
  "media_type": "audio/x-wav",
  "file_size_bytes": 122144,
  "checksum_sha256": "...",
  "voice_identifier": "com.apple.voice...",
  "language": "en-IN",
  "input_text_sha256": "...",
  "input_text": null,
  "extra": {},
  "export_destinations": []
}
```

**Privacy rule, enforced by default:** `input_text` is always `null`
unless a caller explicitly opts in (`store_text=True` in
`build_manifest()` — no CLI flag exposes this yet, by design, since the
common case should not retain full source text). `input_text_sha256` is
populated when input text is supplied (TTS); it is `null` for the CLI's STT
manifests, which do not pass source text. It lets a caller compare supplied
text without retaining it. Built-in speech manifests do not add credentials
or tokens. The schema reserves `export_destinations`, initially empty;
current exporters return separate results and do **not** append to the
sidecar automatically. Callers providing arbitrary `extra`/destination
metadata must keep secrets out themselves. Local paths, audio/transcripts,
and voice identifiers can still be sensitive.

## JSON transcript schema (STT)

`mac_speech.stt.models.Transcript`/`Segment`/`Word` — already defined
in Phase 4, documented here for completeness:

```json
{
  "engine": "apple",
  "text": "Full transcript text.\n",
  "segments": [
    {
      "text": "Full transcript text.",
      "start": 0.0,
      "end": 2.46,
      "words": [{"text": "Full", "start": 0.0, "end": 0.3}]
    }
  ]
}
```

`words` is only populated where the underlying engine actually supplies
word-level timing (full fidelity on Apple; derived from a word-level
SRT round-trip for faster-whisper; empty for Windows, which has no
timing exposed by the current helper — see
`python/mac_speech/stt/engine.py`). Never invented, never interpolated. The
JSON block above is a shortened illustrative transcript, not a fixture result.

## SRT and WebVTT

- SRT transcription passes through the existing, unmodified
  `whisper-py-convert` rendering (`transcribe_srt`). Phase 11's workflow also
  renders an SRT from typed transcript data using
  `mac_speech.stt.srt.transcript_to_srt`, preserving the same timestamp/cue
  convention. That workflow renderer is distinct from transcription passthrough.
- WebVTT: added in Phase 7 for workflows that expect `.vtt` (HTML5
  `<track>`, many web-based editors). Conversion only reformats
  timestamps (`,` → `.` millisecond separator) and adds the `WEBVTT`
  header, dropping numeric cue IDs and normalizing whitespace. This preserves
  parsed cue text/timing for the legacy renderer's supported output, not
  byte-for-byte layout or arbitrary SRT extensions.
- Validated by `tests/unit/test_webvtt.py` (fixed fixtures, no live
  engine dependency) and the Phase 4 regression fixtures
  (`test_stt_regression_fixtures.py`, live engine, synthesized audio,
  skips gracefully on the documented Apple-engine locale flakiness).

## Transcription timestamps vs. TTS timing vs. alignment

Three distinct, never-conflated concepts:

1. **Transcription timestamps** (STT): when words/segments were
   recognized as spoken in a *given* audio file. Supplied by the STT
   engine itself (`mac_speech.stt`).
2. **TTS timing**: `mac_speech.tts.SpeakResult`/`SynthesizeResult` never
   report per-word timing — `AVSpeechSynthesizer` does not supply it.
   File results provide `duration_seconds` (overall audio length) and
   `sentence_count`; playback results provide completion/stop status and
   sentence/text counts, not elapsed time, word timestamps, or a file duration.
3. **Alignment** (`mac_speech.align.align_via_stt_roundtrip`, new in
   Phase 7): an explicit, honestly-labeled *approximation* — run
   TTS-generated audio back through STT and use its recognized word
   timestamps as a stand-in for "where in this audio does each word
   fall." This is **not** phoneme-level forced alignment, and STT's
   recognized words are not guaranteed to exactly match the original
   TTS input text (homophones, short words, mis-recognition). Never
   call this "TTS timing" or "forced alignment" in UI copy or docs.

## Long-form synthesis and chunk stitching

Already designed and verified in Phase 2: both paths split text into sentences
(`NLTokenizer`). `runSave` uses a fresh `AVSpeechSynthesizer` per sentence and
concatenates PCM frames; `runSpeak` queues sentences on one synthesizer. No
explicit silence padding is inserted between chunks — `AVSpeechSynthesizer`'s own
per-utterance output already includes enough natural lead-in/trail-out
that historical Phase 2 STT round-trip probes recognized all sentences in
order. `saveSynthesizesEveryQueuedSentenceNotJustTheFirst` compares combined
and individual audio durations, not recognized words; current STT fixtures
can skip for risk #19. No additional gap-handling code was added in Phase 7, since
there is no demonstrated problem to fix — revisit only if a future
real workflow surfaces audible artifacts at chunk boundaries.

## Retention and cleanup

No command in this toolkit deletes a local artifact, ever, as a side
effect of any other operation — not on overwrite failure, not after a
successful export (Phase 8/9/10 exporters), not after `--force`
overwrite (the *old* file's bytes still get replaced only via the
atomic temp-file-then-rename path, which is the intentional, requested
operation, not an incidental deletion). There is no automatic
retention/expiry policy; artifacts persist until a human or another
tool removes them. This matches `PLAN.md` section 5.3 and section 6's
"never delete local artifacts after upload unless explicitly
requested."
