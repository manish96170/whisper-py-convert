# Invoking `mac-speech tts` from a coding agent or automation script

This is the contract an AI agent (or any non-interactive script) should
rely on. It mirrors `docs/protocol.md`'s rules for the native engine, one
level up at the `mac-speech` CLI.

## Rules

1. **Always pass `--json`.** Human-readable output format is not a stable
   contract; the JSON shape is (`python/mac_speech/tts/models.py`).
2. **stdout carries exactly one JSON document; stderr carries
   diagnostics.** Never parse stderr. Never expect JSON on stderr.
3. **Exit code 0 means success for an operation.** Handled operation errors pair with a JSON
   error document on stdout: `{"error": {"code", "message", "remedy"}}`.
   `error.code` is one of the stable values in
   `python/mac_speech/errors.py` (`ErrorCode`) — branch on it, not on the
   human-readable `message`. Parser/help errors can instead use ordinary
   `argparse` stderr/exit 2, and `doctor --json` returns its report with exit 1
   when checks fail. Do not assume every nonzero exit from every command has
   an `error` object.
4. **A missing native engine is `engine_not_found` (exit 4) with a
   `remedy` telling you how to build/locate it.** Check for this
   explicitly before assuming TTS is unusable.
5. **Never pass credentials as speech text.** Treat narration/audio and
   returned paths/voice identifiers as potentially sensitive. Short text can
   reach subprocess argv; stdin avoids shell history but is not a promise
   of protection from other local processes. Manifests omit full text by
   default, not the speech content from audio.

## Recipes

Check whether a TTS engine is discovered before trying to use it (availability
does not prove voice/permission/synthesis success):

```sh
mac-speech capabilities --json
# -> { "capabilities": [ { "name": "tts", "available": true/false, ... } ] }
```

Synthesize text to a file and get back structured metadata:

```sh
mac-speech tts save "Narration text for a video." \
  --output /tmp/narration.wav --json
```

```json
{
  "output_path": "/tmp/narration.wav",
  "format": "wav",
  "sample_rate": 22050,
  "channels": 1,
  "bit_depth": 16,
  "duration_seconds": 2.78,
  "file_size_bytes": 126866,
  "sentence_count": 1,
  "voice_identifier": "com.apple.voice.compact.en-US.Samantha",
  "language": "en-US"
}
```

Handle an already-existing output file explicitly rather than guessing:

```sh
mac-speech tts save "Text" --output /tmp/narration.wav --json
# exit 3, {"error": {"code": "output_exists", ...}}
mac-speech tts save "Text" --output /tmp/narration.wav --force --json
# succeeds, overwrites
```

List voices without hard-coding any voice name (voice catalogs vary by
machine and OS version, and were found to fluctuate even across
back-to-back runs on the same machine — never assume a specific voice
exists or that a previous listing still holds):

```sh
mac-speech tts voices --language en-US --json
```

Check Personal Voice availability before trying to use one — never
assume a `is_personal_voice: true` entry exists, and never attempt to
request/create one from this tool (not supported; see
docs/tts-engine.md):

```sh
mac-speech tts personal-voice-status --json
# -> {"authorization_status": "not_determined" | "denied" | "unsupported" | "authorized" | "unknown"}
```

If (and only if) `voices --json` already lists an entry with
`"is_personal_voice": true`, its `identifier` can be passed to `--voice`
for `speak`/`save` exactly like any other voice — no special handling
required. Never log, print, or hard-code a specific Personal Voice name
or identifier; those are real personal data tied to whoever's Mac they
came from, not portable test fixtures.

Very long narration text: pass it on stdin instead of as a shell argument
to avoid command-line length limits (the Python layer also does this
automatically above an internal threshold — see
`python/mac_speech/tts/engine.py`'s `STDIN_TRANSPORT_THRESHOLD_CHARS`):

```sh
cat long_script.txt | mac-speech tts save --stdin --output /tmp/long.wav --json
```

## From Python directly (no subprocess/CLI parsing needed)

```python
from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.tts import synthesize_to_file

try:
    result = synthesize_to_file("Narration text.", output_path="/tmp/out.wav")
except MacSpeechError as exc:
    if exc.code is ErrorCode.ENGINE_NOT_FOUND:
        ...  # tell the user how to build/install it (exc.remedy)
    raise
```

This is almost always preferable to shelling out to the CLI from a Python
agent — it is one function call, with typed results
(`mac_speech.tts.models.SynthesizeResult`), and the same error contract.

## What not to do

- Do not parse `mac-speech tts save ...`'s human-readable stdout
  (`"Saved 2.78s of audio to ..."`). That format is for terminals and can
  change; `--json` will not.
- Do not assume a specific voice identifier is present on every machine —
  always discover voices via `tts voices`, per `PLAN.md` section 3.3.
- Do not retry blindly on every non-zero exit code. `output_exists` (3)
  means "ask the user or pass --force", not "retry the same call".
