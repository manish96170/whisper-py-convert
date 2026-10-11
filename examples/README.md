# Local speech examples

Run these commands from the repository root with the Python wrapper installed
in `.venv` (`python3 -m venv .venv`, then `.venv/bin/python -m pip install -e .`).
Build/install the independent native TTS engine with `./install.sh tts`.
See [installation](../docs/installation.md) for requirements and other install modes.
No optional exporter dependencies or credentials are needed for these examples.

## Small narration workflow

Start with TTS alone: this saves audio without playback or STT, and works offline
after installation with a locally available system voice. It avoids the known
Apple STT locale/reservation issue entirely.

```sh
.venv/bin/python examples/narration_workflow.py --help
.venv/bin/python examples/narration_workflow.py \
  --text "Welcome to this short local narration example." \
  --output-dir ./artifacts/tts-demo-01 --synthesize-only
```

Outputs: `narration.wav` and `narration.workflow.json`. **Choose a new output
directory on every run** (even an existing empty directory is refused).
There is no overwrite/force option. Existing audio, SRT, manifests, and symlinks
are never reused. The script does not clean up generated artifacts on failure.

To include approximate word-timed SRT, install the existing Apple STT engine
(`./install.sh stt`, macOS 27+) and use a different new directory:

```sh
.venv/bin/python examples/narration_workflow.py \
  --text "Welcome to this short local narration example." \
  --output-dir ./artifacts/narration-demo-01 --language en-US
```

The script calls `mac_speech.workflow.stage_synthesize`, `stage_align`, and
`stage_render_srt`. STT explicitly selects the **Apple** engine: it does not fall
back to faster-whisper or download a model if that engine is missing or fails.
Timing is **STT-roundtrip approximation, not forced alignment**. SRT contains
STT-recognized words, which may differ from the input; review it before using it
in a video. When word timings are absent, the renderer uses supplied segment
timings. Empty, whitespace-only, or invalid/non-positive timed cues fail the
alignment stage rather than producing a successful empty SRT; audio is retained.
See [workflow semantics and retry recipes](../docs/workflow.md).

Normal execution writes one JSON result to stdout with `ok`, `mode`,
`manifest_path`, `timing_method`, and stage statuses/output paths. Successful
runs exit 0; stage/filesystem failures exit 1; invalid input exits 2; an existing
output path exits 3. Argument/help handling uses ordinary `argparse` output.
The result and manifest remain useful when alignment fails: `ok` is false,
the process exits nonzero, and the WAV plus failure manifest stay on disk.
Fix the STT environment, then retry alignment on that WAV rather than
regenerating it. The script does not attempt any locale-reservation workaround.

### Privacy and retention

Use `--text-file script.txt` or `--text-file -` (stdin) instead of `--text` for
content you do not want in your shell history. Neither source text nor recognized
transcripts are printed. Native stderr is suppressed, and failures are replaced
with stage-level guidance rather than potentially sensitive engine messages.
The manifest stores a source-text SHA-256 hash and stage provenance, not source
text. Audio/SRT necessarily contain the narration; the manifest includes local
output paths and the selected system voice identifier. Treat these files as
potentially sensitive, avoid synced/public directories when privacy matters,
and delete your run directory manually when no longer needed. The underlying
TTS adapter may pass short text to its native subprocess as an argument; this
example does not promise protection from other local processes inspecting argv.

### Optional export is a separate action

The sample never imports/calls exporters or sends anything remotely. If you
want a local copy, explicitly run the existing export CLI afterwards:

```sh
.venv/bin/mac-speech export ./artifacts/tts-demo-01/narration.wav \
  --to local --destination ./handoff/narration.wav --preview --json
# Only after checking that preview:
.venv/bin/mac-speech export ./artifacts/tts-demo-01/narration.wav \
  --to local --destination ./handoff/narration.wav --json
```

Choose a truly local, non-synced destination for offline/private use. For
explicitly opted-in remote exports, consult [exporters](../docs/exporters.md)
separately; no remote setup or credentials are part of this workflow.

## Existing TTS-only examples

These remain independent of STT:

- [tts_python_script.py](tts_python_script.py): voice listing, playback, and file
  synthesis through the Python API. It plays audio and explicitly overwrites its
  demo output with `force=True`; use the narration sample above for retained,
  overwrite-protected artifacts.
- [tts_shell.sh](tts_shell.sh): native TTS through the shared CLI.
- [tts_agent_invocation.md](tts_agent_invocation.md): machine-readable CLI/API
  recipes for automation.
