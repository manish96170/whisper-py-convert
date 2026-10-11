# Configuration and environment variables

**Precedence (highest wins):** explicit CLI flag/function argument >
environment variable > built-in default. No configuration file is read.
Core binary discovery and diagnostics require no network or credentials.
Optional exporters have explicit credential settings below; remote uploads
are separate network-capable actions, never a speech-generation prerequisite.

## Environment variables

| Variable | Affects | Default if unset | Notes |
| --- | --- | --- | --- |
| `MAC_SPEECH_TTS_BINARY` | Which `mac-speech-tts` binary `mac_speech.capabilities.find_tts_binary()` / `mac_speech.tts.engine.resolve_binary()` use | Auto-discovered: `engines/tts-swift/.build/out/Products/Release/mac-speech-tts`, then a few other build-output locations, then `~/.local/share/mac-speech/mac-speech-tts` (see `capabilities.py` for the exact candidate list) | Highest-priority override. Must point at an executable file; a non-executable or missing explicitly configured path yields no match, with no discovery fallback. Correct or unset the override. |
| `WHISPER_PY_CONVERT_BIN` | Which `whisper-py-convert.py` script `mac_speech.capabilities.find_whisper_py_convert()` / `mac_speech.stt.engine.resolve_whisper_py_convert()` use | Auto-discovered: `<repo root>/whisper-py-convert.py`, then `~/.local/share/whisper-py-convert/whisper-py-convert.py` | Highest-priority override; points at the Python script, not an executable binary — it is run via `sys.executable` |
| `MAC_SPEECH_TTS_PID_FILE` | Where `speak()`'s PID is recorded for cross-process `tts stop`/`pause`/`resume` | `${XDG_CACHE_HOME:-~/.cache}/mac-speech/tts.pid` | Set this if running multiple concurrent `speak()` calls that each need independent stop/pause/resume targeting — the default path is shared and only tracks the most recent tracked `speak()` call |
| `XDG_CACHE_HOME` | Base directory for the default PID file location above | `~/.cache` | Standard XDG variable; only consulted if `MAC_SPEECH_TTS_PID_FILE` is unset |
| `XDG_DATA_HOME` | Where `install.sh` places installed binaries (`whisper-py-convert`, `mac-speech-tts`) | `~/.local/share` | Pre-existing convention from the original `whisper-py-convert` installer; unchanged by Phase 3 |
| `XDG_BIN_HOME` | Where `install.sh` symlinks the `whisper-py-convert` command | `~/.local/bin` | Pre-existing; unrelated to TTS |
| `HF_TOKEN` | Hugging Face auth for faster-whisper model downloads | unset | Existing STT-only variable (`whisper-py-convert.py`); unrelated to TTS, listed here only to avoid confusion with the TTS variables above |
| `MAC_SPEECH_GDRIVE_CLIENT_SECRETS` | Path to a Google OAuth `client_secret.json` for the `gdrive` exporter | unset (export fails with an actionable error) | Download from Google Cloud Console (Desktop app type); never commit this file |
| `MAC_SPEECH_GDRIVE_TOKEN` | Where the Drive OAuth token (with refresh token) is cached | `~/.config/mac-speech/gdrive-token.json` | Created with `0600` permissions on first use; contains a credential — never commit it |
| `MAC_SPEECH_SLACK_BRIDGE_PATH` | Path to a local `team-slack-bridge` checkout, for the `slack` exporter | unset (export fails with an actionable error) | Not a Python dependency — a sibling project invoked via `node` as a subprocess |

## Exporter-specific configuration

The `s3` exporter's `profile`/`region`/`endpoint_url` are Python
constructor arguments / none are read from new environment variables —
it defers entirely to the `aws` CLI's own standard credential/region
resolution (named profile, `AWS_PROFILE`, `AWS_REGION`, SSO, instance
role). See `docs/exporters.md`.

## CLI flags that override environment/defaults

`mac-speech tts speak` and `mac-speech tts save` accept `--timeout <seconds>`,
which overrides the engine's default timeout
(`mac_speech.tts.engine.DEFAULT_TIMEOUT_SECONDS`, currently 120 seconds).
There is no environment variable for the timeout default — pass `--timeout`
(CLI) or `timeout=` (Python) explicitly if 120 seconds is wrong for your
use case (e.g., very long narration).

## Why so few variables

Per `PLAN.md`'s "Keep the base Python wrapper small and standard-library-first"
principle, configuration is intentionally minimal: a binary-location
override and a PID-file-location override are the core TTS environment
knobs. Optional exporters and the legacy STT dispatcher have their own
explicit settings, listed above. Voice, rate, language, output format, and output path are always
explicit function arguments or CLI flags — never implicit environment
state — because changing which voice speaks or where a file is written
silently based on an environment variable is exactly the kind of "silent
fallback" `PLAN.md` section 2 (non-goals) and section 3.3 ("Prefer
explicit capability detection... over guessing or silent fallback.") warn
against.
