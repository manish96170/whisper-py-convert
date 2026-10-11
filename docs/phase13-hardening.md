# Phase 13A — workspace and output safety

This is a bounded hardening milestone for the existing local toolkit, not
completion of every open-ended Phase 13 candidate. The concrete use case is
repeated/per-scene narration in a shared output directory without losing
another run's audio, subtitles or provenance.

## What changed

- Managed basenames are filename components, never paths; traversal, absolute
  names and control characters fail before directory creation or speech.
- Text/SRT/sidecar/workflow manifests and native audio publish atomically.
  Default create-if-absent preserves a late writer. Regular-file replacement
  requires `force`; symlink, directory and special-file targets are refused.
- Native audio is reserved privately (`0600`, enclosing staging directory
  `0700`) before AVFoundation opens it. The writer's inode/mode is verified.
  Completed text/audio/manifest outputs are owner-only by default.
- Pipeline calls claim their basename. CLI checkpoints before speech and after
  each attempted stage; Python opts in with `persist_manifest=True`.
  Updates check published inode ownership and do not overwrite an intervening
  independent replacement. The sample uses the same checkpoint mechanism.
- Cancellation guards process acquisition and the child writer's owned
  lifetime. Known children are killed/reaped before claim release; unconfirmed
  acquisition/termination retains the marker. Secondary cleanup warnings are
  best-effort and cannot replace cancellation, even if stderr is disconnected.
- Existing successful outputs remain on downstream failure. There is no
  automatic retention deletion, remote export, new model or runtime dependency.

## Use the updated code

Rebuild the native engine from matching source before relying on its new file
publication rules. The Python package alone does not replace an old binary:

```sh
./install.sh tts
.venv/bin/python -m pip install -e .
.venv/bin/mac-speech workflow narrate "A short local narration example." \
  --output-dir ./examples/output/phase13-demo --basename scene-01 \
  --no-align --json
```

The output is `scene-01.wav` plus `scene-01.workflow.json`. Choose a fresh
basename for another scene. Repeating without `--force` refuses existing
outputs. `--force` is explicit consent to replace regular outputs, **not**
permission to bypass another active or unverified claim.

For Python orchestration:

```python
from mac_speech.workflow import run_narration_pipeline

manifest = run_narration_pipeline(
    "A short local narration example.",
    output_dir="examples/output/phase13-python",
    basename="scene-01",
    align=False,
    persist_manifest=True,
)
assert manifest.ok
```

Use `--no-align`/`align=False` for the offline TTS-only example. Actual native
STT remains affected by risk #19 and requires a separate authorized repair.

## Compatibility and limits

- Raw `WorkflowManifest.write`, artifact `write_manifest`, and
  `stage_render_srt` now refuse replacement by default. Callers intentionally
  replacing an existing regular file must opt into `force=True`.
- Hard-link support on a same-filesystem local destination is required for
  atomic no-clobber publication; unsupported filesystems fail closed.
- Parent directories must be trusted. The inode check detects ordinary
  intervening replacement, not a hostile compare-and-swap or in-place editor.
  Do not mutate a live run's files. This is not a sandbox or a multi-file
  transaction, nor a power-loss durability guarantee.
- A crash or unconfirmed child can leave `.<basename>.workflow.lock` and
  private staging state. Use a new basename, or inspect the exact state only
  after verifying **all corresponding writers** have stopped. A stored parent
  PID alone is insufficient; do not blindly kill it or delete its marker.
- Broader log redaction, retention automation/audit trails, batch queues,
  models, GUI/services and additional platforms remain separately scoped.
  A source-code change or green local test is not a license-cleared release.

## Measured local file-I/O overhead

M1 Pro/16 GiB, macOS 27.0.1, Python 3.11.3; 30 sequential fresh-file samples
per payload on the local temp filesystem. The comparison is a plain
temp-write/replace against private, flushed, atomic create-if-absent. It is
an observed overhead comparison, **not a recommendation to use the unsafe
baseline**, a cross-filesystem guarantee, or a performance threshold.

| Payload | Plain temp/replace median | Hardened publish median | Hardened maximum |
| --- | --- | --- | --- |
| 1 KiB | 0.667 ms | 1.365 ms | 3.679 ms |
| 1 MiB | 0.986 ms | 1.935 ms | 4.790 ms |

The additional local overhead is roughly 0.7–1.0 ms per tested write.
Results include file flushing, not just the final link/rename syscall;
cache/load conditions vary. Exact current test/review/build evidence is
maintained in `PLAN.md` and [the session handoff](SESSION_HANDOFF.md).
