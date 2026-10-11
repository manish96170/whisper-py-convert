# mac-speech (Python package: `mac_speech`)

Small, local-first Python wrapper and CLI for independent macOS speech
engines. It lives alongside, not in place of, the preserved
`whisper-py-convert` STT command. Python owns typed results, diagnostics,
artifact/workflow metadata, and explicit exports; native engines own speech.

**License status:** no authoritative project license has been established
in this repository. Public packaged redistribution/publication is blocked until the
rights holder supplies an authorized license and matching metadata. Do not
assume a license from public source availability or dependency licenses.
No PyPI package or prebuilt native release is claimed here.

## Installation boundaries

- **Python 3.9+**; no base Python runtime dependencies. A standard wheel or
  Python sdist installs the wrapper, not a native engine or models. Imports,
  help, and diagnostics work without speech engines.
- Build native engines from a reviewed **full repository checkout** with
  `./install.sh tts`, `./install.sh stt`, or `./install.sh all` (default).
  The installer does not install this Python package. Its `tts` mode still
  copies the legacy STT dispatcher but does not build Apple STT.
- Both Swift manifests require **Swift 6.4+** and an appropriate Apple SDK.
  TTS's deployment target is **macOS 13+**, Apple STT's is **macOS 27+**;
  the Swift toolchain's host OS requirement is a separate constraint.
  Native execution is verified on macOS 27.0.1/Apple Silicon only. The
  older TTS runtime floors and Intel Macs are not runtime-tested.
- A Python **sdist is not the repository source tarball**: it deliberately
  excludes `install.sh`, the legacy dispatcher, and Swift/Windows sources.
  Use a checkout or separately verified full source archive to build native
  engines. No Swift compilation runs during `pip install`.

From the full repository root, for local use (install only the capability
you need):

```sh
./install.sh tts                 # or: stt / all
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
mac-speech version --json
mac-speech doctor --json
mac-speech tts voices --json
mac-speech tts save "Hello from my Mac." --format aiff --output ./hello.aiff
```

Installing a locally built wheel uses `python -m pip install /path/to/wheel.whl`
instead of `pip install .`; install native engines separately first.
See [installation](../docs/installation.md) for paths, modes, upgrades,
uninstall, and rollback, and [packaging](../docs/packaging.md) for local
wheel/sdist builds, pinned source trust, checksums, license gates, and
accurate signing/notarization guidance. Paths/links here refer to the full
repository; the Python sdist includes only a subset of its documentation.

Once required engines and Apple voice/speech assets are already installed,
core native speech needs no cloud account or paid API. Initial tool,
dependency, and Apple asset acquisition may require network. For an offline
STT check select `--engine apple` explicitly: the preserved legacy
`auto`/`faster-whisper` path can install dependencies/download models on first
use. Packaging tests must not trigger that fallback. No voices/models are
bundled, and no model download is part of this package installation.

## Available API and CLI

- `mac-speech version`, `capabilities`, `doctor` support `--json`.
- `mac-speech tts voices|personal-voice-status|speak|save|stop|pause|resume`
  use the independent `mac-speech-tts` engine. `stop`/`pause`/`resume` target
  the tracked playback PID, not every audio process. Personal Voice status
  is read-only; this tool does not request authorization, create, or extract
  a Personal Voice.
- `mac_speech.tts` exposes `list_voices()`, `personal_voice_status()`,
  `speak()`, `synthesize_to_file()`, `stop()`, `pause()`, and `resume()` with
  typed results. Missing engines produce actionable `MacSpeechError`s.
- `mac-speech stt transcribe INPUT --format text|srt|json|webvtt` adapts the
  existing Apple/Windows/faster-whisper paths without importing/forking the
  legacy script. JSON/timestamp fidelity is backend-specific, not invented.
- `mac_speech.stt` exposes `transcribe()`, `transcribe_text()`,
  `transcribe_srt()`, and `transcribe_json()` with typed transcript results.
- Artifact manifests, WebVTT, STT-roundtrip alignment, and narration
  workflows support downstream tooling without bundling a video renderer.
  STT-roundtrip alignment is an approximation, **not forced alignment**.
- `mac-speech export` supports explicit local/Drive/S3/Slack operations.
  Google Drive needs the optional `gdrive` extra and human-configured OAuth;
  S3 uses the separately installed AWS CLI; Slack invokes a separate local
  `team-slack-bridge`. None is needed for core tests or speech generation.

For a Python TTS example with the native engine already installed:

```python
from mac_speech.tts import synthesize_to_file

result = synthesize_to_file("Hello from Python.", output_path="hello.aiff", format="aiff")
print(result.to_dict())
```

Use a new output path; synthesis does not silently overwrite existing files.
See [examples](../examples/) for scripts and agent invocation guidance.

## Development setup

From the repository root (using a separate venv if `.venv` already belongs
to another workflow):

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest tests/unit
```

Swift tests/builds are separate; they are not triggered by Python packaging.
Optional cloud integrations are mocked in core unit tests and need no real
credentials. See [packaging](../docs/packaging.md) for temporary-directory
wheel/sdist checks that do not write shared native `.build` directories.

Use `bash scripts/ci_swift.sh` for isolated native tests/release builds in a
shared checkout. [CI](../docs/ci.md) documents the 18-file strict mypy boundary
and manual/opt-in native runner; [verification](../docs/verification.md)
records Phase 12's final local suite, extracted-sdist, clean-wheel/offline
TTS, and lifecycle evidence. Local verification is not a hosted-CI result or
license-cleared public release.

Phase 13A hardens output/workflow safety: basenames cannot escape a managed
workspace, sidecar/SRT/manifest replacement is explicit, cooperating runs
claim their basename, and text/audio publication cannot silently clobber a
late writer. Rebuild native TTS from the **same updated source** when upgrading
(a Python wheel alone cannot update an already-installed engine). See
[workflow safety and checkpoint opt-in](../docs/workflow.md) for
`persist_manifest=True`, claim/cancellation behavior and trust limitations.

Phase 13B adds `mac-speech tts batch` and `mac_speech.batch.synthesize_batch`
for finite WAV scene lists. Default one worker, explicit cap 1–4, ordered
private reports/checkpoints and cancellation/drain. It does not transcribe,
play, export or download models. See [batch-synthesis](../docs/batch-synthesis.md)
and [the public sample input](../examples/batch_scenes.json).

## Contracts and further documentation

- [Repository boundaries](../docs/decisions/ADR-001-repository-and-module-boundaries.md)
  and [packaging decision](../docs/decisions/ADR-002-packaging-and-distribution.md).
- [Protocol](../docs/protocol.md): native JSON schema, compatibility,
  subprocess exit codes, logging rules.
- [Configuration](../docs/configuration.md): environment variables and
  precedence; [platform support](../docs/platform-support.md): verified
  versus unverified OS/architecture combinations.
- [TTS engine](../docs/tts-engine.md): audio formats, voice constraints, and
  process-control semantics.
- [Formats](../docs/formats.md): manifests, SRT/WebVTT, timing semantics;
  [workflow](../docs/workflow.md): independent narration pipeline stages.
- [Exporters](../docs/exporters.md): opt-in integrations and privacy boundaries.
- `mac_speech.errors.ErrorCode`, `mac_speech.results`,
  `mac_speech.tts.models`, and `mac_speech.stt.models` define the Python
  error/result contracts; their `to_dict()` forms back CLI JSON output.
