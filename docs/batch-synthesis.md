# Phase 13B — bounded local batch synthesis

Use a finite scene list when narration otherwise requires repeating one
TTS-only workflow call per scene. The base remains standard-library-only.
Batch synthesis produces **WAV audio only**: no STT/alignment, playback,
export, watcher/daemon, neural engine or model download is implicit.

## CLI example

Build/install a matching native TTS engine and the Python wrapper first.
The included input uses public sample text, not private audio or voice IDs:

```sh
.venv/bin/mac-speech tts batch --input examples/batch_scenes.json \
  --output-dir ./examples/output/batch-demo --json
# Opt into parallel synthesis, in a fresh workspace:
.venv/bin/mac-speech tts batch --input examples/batch_scenes.json \
  --output-dir ./examples/output/batch-parallel --workers 2 --json
```

Default **one worker**. `--workers` permits **1–4**. At most that many scenes
are submitted/in-flight, not a future for every scene. Input contains **1–1000
scenes** and the CLI reads at most 8 Mi characters of UTF-8 JSON. Per-scene
`--timeout` defaults to 120 seconds. Choose locally installed ordinary voices;
missing Apple assets are not provisioned by the batch command.

Schema version 1 requires exactly `schema_version` and `scenes`. Each scene
requires `basename` and `text`, with only optional `voice`/`language` fields.
Version must be integer 1 (not boolean/string); text must be non-empty valid
UTF-8; optional selections must be non-empty strings. Unknown options are
rejected instead of silently enabling transcription or a backend fallback.

Basenames must be filename components, not paths. Duplicate case/Unicode
aliases are rejected before filesystem/speech side effects. Files are:

- `<basename>.wav`
- `<basename>.workflow.json` — private per-scene checkpoint
- `batch.json` — ordered, private aggregate report

## Python API

```python
from mac_speech.batch import BatchScene, synthesize_batch

result = synthesize_batch(
    [BatchScene("scene-01", "A short local sample."),
     BatchScene("scene-02", "Another local sample.")],
    output_dir="examples/output/python-batch",
    workers=2,
)
print(result.ok)
```

Callers may provide a `threading.Event` as `cancel_event` to request
cooperative cancellation. A caller's scene list is snapshotted rather than
scheduled against later mutation. No global stderr replacement or signal
handler is installed.

## Results, privacy and partial failures

The report retains input order even if completion order differs. Scene
statuses are `pending`/`running` during a checkpoint and
`success`/`failed`/`cancelled` in a completed result. Each includes a source
text hash, output/checkpoint references when available, elapsed time and
sanitized error/code. It does **not** store source text or raw backend
diagnostics. Worker diagnostics are suppressed per thread/context; ordinary
non-batch diagnostics keep their existing behavior.

Audio/input JSON necessarily contain narration, and filenames/paths can be
sensitive. Keep inputs private and avoid synced/public output directories.
Reports/checkpoints are owner-only (`0600`) and output publication follows
[Phase 13A safeguards](phase13-hardening.md). A successful scene is never
deleted merely because another scene fails. Re-run selected failed scenes
with a fresh batch report/workspace to avoid regenerating unrelated audio.

Ordinary scene failures—including existing-file collisions—are recorded while
other scenes continue. A pre-existing `batch.json` is refused before speech.
`--force`/`force=True` explicitly permits replacing regular report/scene outputs;
it does not bypass an active/unverified claim or allow unsafe entry types.

## Cancellation and ownership

The coordinator owns `.batch.lock` and only its main scheduler writes the
aggregate checkpoint. Each worker owns its scene's workflow claim and
checkpoint; inode identities are checked on updates. An intervening independent
replacement is not silently overwritten. Existing parent-directory/trusted
writer assumptions remain; this is not a hostile compare-and-swap or a
multi-file transaction.

Cooperative cancellation polls an owned single I/O exchange at most every 200 ms,
then kills/reaps the owned child through the Phase 13A cleanup path. Long
stdin text is sent once, with EOF handled by one standard-library communication
call rather than fragile input=None retries. The scheduler cancels
queued work and drains owned workers before releasing its claim. Keyboard
interruption returns a partial batch result after cancellation/drain; completed
scenes remain success. An interrupted submit can still produce an owned
completed scene; worker results are collected independently of receipt of its
Future handle. A worker cannot begin scene/native work until its submission
has been acknowledged and registered by the coordinator; abandoned startup
cannot perform late filesystem/audio side effects.

If a writer or drain cannot be confirmed stopped, further submissions stop
and the relevant batch/scene claims are retained. Do not infer safety from a
stored parent PID, remove active/unverified markers, or force another batch
into that workspace. Inspect all corresponding writers, or choose a fresh
workspace. Native-process cleanup can take up to its 10-second reap backstop;
200 ms is a polling interval, not a universal cancellation-latency guarantee.

CLI exit codes: **0** all scenes succeed; **1** partial failure or unconfirmed
cleanup; **130** confirmed cancellation; validation/ownership exceptions use
the normal structured `MacSpeechError` exit codes. `--json` emits one final
result on stdout, not a stream of source-text/progress events.

Exact test/review/native/performance evidence and any unresolved limits are
recorded in `PLAN.md` and `docs/SESSION_HANDOFF.md`; do not infer hosted-CI
success for uncommitted code from a prior run.

## Local verification snapshot (2026-10-11)

The final repository suite passed **431 tests, four existing native STT skips**;
42 batch/cancellation tests were added. Local 3.12/3.13/3.14 source suites
passed 431 each; Ruff and strict mypy passed (18 source targets). Native
mapping/regressions passed 48 Swift tests and release build with isolated
caches. The extracted-sdist suite passed 420 tests/15 expected skips, and a
fresh wheel completed a real batch with credentials stripped/network denied.
Separate review/rechecks closed startup, long-stdin and malformed-argv findings.

For the included three-scene input, the current single-run observation was
**4.163 s with one worker** versus **2.206 s with two** on M1 Pro/macOS
27.0.1/Python 3.11.3 using installed ordinary voices. Serial ran first;
cache/system load and voice choice matter. This is not a quality, energy/RSS
measurement or a guarantee that parallelism always helps; default remains one.
Workers/queued submissions are capped, with at most one native I/O exchange
per admitted worker. Unsupported platforms/assets are not provisioned here.
