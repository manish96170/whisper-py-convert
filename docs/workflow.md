# Workflow orchestration (Phase 11)

## Pipeline

```
text --[stage_synthesize]--> audio.wav --[stage_align]--> Transcript --[stage_render_srt]--> audio.srt
```

```sh
mac-speech workflow narrate "Scene one narration text." \
  --output-dir ./artifacts --basename scene-01 --json
```

```python
from mac_speech.workflow import run_narration_pipeline

manifest = run_narration_pipeline(
    "Scene one narration text.",
    output_dir="./artifacts",
    basename="scene-01",
)
```

Each stage (`stage_synthesize`, `stage_align`, `stage_render_srt`) is a
plain function, independently callable and retryable — `run_narration_pipeline`
is a convenience chain, not the only way to use them. The result is a
`WorkflowManifest` object with a stable schema (`WORKFLOW_SCHEMA_VERSION = 1`)
referencing every stage's
status, output path, and provenance — this is what a video renderer
(Remotion or otherwise) reads to find artifacts, without importing any
of `mac_speech`'s internals.
The CLI writes `<basename>.workflow.json`; Python callers must explicitly
persist it with `manifest.write(Path("artifacts/scene-01.workflow.json"))`.

## Runnable sample and independent retry

See [examples/README.md](../examples/README.md) and
[`examples/narration_workflow.py`](../examples/narration_workflow.py) for a small,
tested script with JSON results, a fresh-directory overwrite guard, and an
offline `--synthesize-only` quickstart. It explicitly chooses native Apple STT
instead of `auto`, so an absent/failing Apple engine never triggers a fallback
to model-based STT. It saves a manifest after each attempted stage, retains audio
on downstream failure, suppresses raw native diagnostics, and exits nonzero on
failure. It does not export anything.

After fixing an Apple STT environment/locale error, reuse the retained WAV:

```python
import os
from contextlib import redirect_stderr
from pathlib import Path
from mac_speech.workflow import stage_align, stage_render_srt

audio = Path("artifacts/narration-demo-01/narration.wav")
# As in the runnable sample, do not forward raw native diagnostics.
with open(os.devnull, "w", encoding="utf-8") as quiet, redirect_stderr(quiet):
    stage, transcript = stage_align(str(audio), engine_name="apple", language="en-US")
if stage.status != "success" or transcript is None:
    raise SystemExit("Apple STT still unavailable; audio and the original manifest are unchanged.")
retry_srt = audio.with_name("narration-retry-01.srt")
if retry_srt.exists() or retry_srt.is_symlink():
    raise SystemExit("Choose a new SRT path; do not overwrite earlier artifacts.")
stage = stage_render_srt(transcript, output_path=str(retry_srt))
if stage.status != "success":
    raise SystemExit("SRT rendering failed; check output permissions.")
```

This sequential retry does not resynthesize audio or rewrite the original
failure manifest. The raw stage helpers do not themselves protect existing SRT
or manifest paths; callers must manage their output workspace. The sample owns
a newly created run directory, while the retry recipe checks its new SRT path.
Do not run concurrent writers against the same files.

## Verified: a failed later stage never invalidates an earlier artifact

Demonstrated for real, not just asserted, during Phase 11 development:
on a machine where the Apple STT engine's locale-reservation quota was
exhausted (see `docs/risk-register.md` risk #19), running
`mac-speech workflow narrate` produced exactly this:

```json
{
  "ok": false,
  "stages": [
    {"name": "synthesize", "status": "success", "output_path": ".../narration.wav"},
    {"name": "align", "status": "failed", "error": "...does not support locale..."}
  ]
}
```

This is a shortened illustration of the observed result; omitted manifest
fields are documented by `WorkflowManifest`, not literal ellipses in JSON.

The `synthesize` stage's `narration.wav` remained on disk, fully valid
(`afinfo`-confirmed), while `align` failed cleanly and the pipeline
stopped there — exactly `PLAN.md` Phase 11's acceptance criterion
("Failed downstream stages do not invalidate successful speech
artifacts"), proven against a real, naturally-occurring failure, not a
synthetic one.

## The timing-approximation decision

This pipeline's only alignment mechanism is `mac_speech.align
.align_via_stt_roundtrip` — running TTS-generated audio back through
STT and using its recognized word timestamps as an approximation of
"where in this audio does each word fall." This is **not** forced
alignment (no phoneme-level matching against the known reference
text), and it is not guaranteed that STT's recognized words exactly
match the original TTS input (homophones, short words, misrecognition
are all possible). A dedicated forced-alignment engine (e.g. Montreal
Forced Aligner, gentle) was deliberately not integrated — it is
materially larger scope than this toolkit's offline-first speech core,
and the STT round-trip has already been empirically shown (Phase 4/7
tests) to produce correctly-ordered, monotonic word timestamps for
synthesized speech specifically, which is cleaner audio than real-world
recordings. If a downstream video workflow needs frame-accurate
alignment, add a dedicated forced-alignment stage on top of this
pipeline's `audio.wav` output — do not assume this pipeline's SRT is
phoneme-accurate.

## Scene/chunk boundaries are the caller's job

Per `PLAN.md`'s explicit boundary ("keep expression timing, visual
editing, and rendering responsibilities in the video project, not in
the speech engine"), this module has no multi-scene orchestration of
its own. A video-generation script calls `run_narration_pipeline` once
per scene/paragraph, with its own `basename` (e.g. `scene-01`,
`scene-02`, ...), and assembles the resulting per-scene manifests
itself. This keeps the speech core decoupled from any specific
renderer, exactly as required.

## Stable paths for downstream renderers

`WorkflowManifest.to_dict()`'s `stages[].output_path` values are the
contract: absolute or caller-relative paths to real files on disk, with
no further processing required to hand off to Remotion or any other
renderer. The manifest itself never contains the source text (only its
sha256 hash), consistent with the artifact-manifest privacy rule
established in Phase 7 (`docs/formats.md`).

## No plugin/hook mechanism was added

`PLAN.md` says to add one "only if concrete workflow needs justify it."
None were identified in this phase — three plain, composable functions
plus a manifest already satisfy every stated acceptance criterion.
Revisit only when a real, specific downstream integration demonstrates
a need beyond what calling these functions directly already provides.
