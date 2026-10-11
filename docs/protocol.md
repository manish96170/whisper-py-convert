# Native-process protocol and CLI contract

**Status:** Defined in Phase 1, implemented for native TTS in Phases 2–3,
with strict version validation completed in Phase 12. Governs *new* engines only — see the
"Relationship to the existing STT engines" section below before assuming
this applies to `whisper-py-convert-apple` or the Windows helper.

## Scope

This document defines the contract between the `mac_speech` Python package
and any native engine process it talks to, going forward:

- The Phase 2 native TTS engine.
- Any future rewritten/versioned STT adapter, if one is ever built.

It does **not** change `whisper-py-convert-apple`'s or
`whisper-py-convert-windows.exe`'s existing, unversioned JSON shape. Those
binaries predate this contract and are preserved exactly as-is per
`docs/decisions/ADR-001-repository-and-module-boundaries.md` and
`PLAN.md`'s "do not rewrite functioning STT code" rule. `mac_speech`'s
STT adapter *consumes* that existing shape through its own translation
layer rather than forcing the Apple/Windows binaries to speak this
protocol. This is a deliberate compatibility limitation: the wrapper
cannot verify a native protocol version for these legacy STT binaries.
Do not add a required version field to their output or apply the TTS
version check to existing STT responses.

## Transport

- One-shot commands only for now, per `PLAN.md` section 3.3: a native
  process is invoked, produces exactly one JSON response document, and exits.
  A long-running/streaming subprocess model is not adopted unless a
  concrete need is demonstrated in a later phase.
- Inputs depend on the engine's transport: the request object below is
  for JSON request transports; current native TTS uses CLI arguments and
  optional raw text on stdin.
- Diagnostics, progress, and warnings go to **stderr only**. **stdout**
  carries exactly one JSON document and nothing else. Mixing the two breaks
  any caller piping stdout into a JSON parser.

## Message shapes

Implemented in `python/mac_speech/native_protocol.py`.

Request (Python -> native process):
```json
{
  "operation": "speak",
  "payload": { "...": "operation-specific fields" },
  "protocol_version": 1
}
```

Response (native process -> Python), success:
```json
{
  "status": "ok",
  "protocol_version": 1,
  "result": { "...": "operation-specific fields" },
  "error": null
}
```

Response (native process -> Python), failure:
```json
{
  "status": "error",
  "protocol_version": 1,
  "result": null,
  "error": { "code": "engine_not_found", "message": "...", "remedy": "..." }
}
```

- `protocol_version` is a required integer on both sides. A native engine
  that receives a request with a `protocol_version` it does not implement
  must fail fast with `error.code == "protocol_version_mismatch"` rather
  than guess at compatibility.
- The TTS wrapper validates every response's version before interpreting
  its success result or native error, even when the subprocess exits
  nonzero. Missing versions and non-integer values (including strings,
  floats, booleans, and null) are rejected, not coerced or defaulted.
  Missing, malformed, and unsupported versions raise `MacSpeechError`
  with `code == "protocol_version_mismatch"` (exit code 5). Invalid JSON
  or a JSON value that is not an object remains `native_process_error`.
- `error.code` values come from the stable set defined in
  `python/mac_speech/errors.py` (`ErrorCode`). Do not invent ad hoc string
  codes outside that enum; add a new value there first if a new failure
  mode needs one.

## Exit codes

| Error code | Exit code | Meaning |
| --- | --- | --- |
| `invalid_argument` | 2 | Bad CLI input / usage error |
| `input_not_found` | 3 | Input path missing or not a file |
| `output_exists` | 3 | Refused to overwrite an existing output file |
| `engine_not_found` | 4 | Required native binary is missing/not built |
| `unsupported_platform` | 4 | API/engine unavailable on this OS/version |
| `protocol_version_mismatch` | 5 | Native engine and wrapper disagree on protocol version |
| `native_process_error` | 6 | The native process ran but reported a failure |
| `timeout` | 124 | Operation exceeded its allotted time (124 matches the common shell `timeout` convention) |
| `cancelled` | 130 | Cooperative cancellation requested; added in Phase 13B without changing prior codes |
| `not_implemented` | 10 | Reserved/unimplemented feature; historical Phase 1 STT/TTS stubs used this, but those operations are now implemented |
| `internal_error` | 1 | Unexpected/unclassified failure |

0 always means success. This mapping is defined once, in
`EXIT_CODE_BY_ERROR` (`python/mac_speech/errors.py`), and must stay stable
across releases — a script may branch on exit code alone without parsing
JSON if it chooses to.

## Logging rules

- `mac_speech.logging_utils.diagnostic()` is the only sanctioned way to
  write progress/diagnostic text; it always targets stderr.
- The CLI (`mac_speech/cli.py`) writes human-readable text to stdout by
  default, or a single JSON document to stdout when `--json` is passed.
  Never both in the same invocation.
- This mirrors the existing `whisper-py-convert.py` convention
  (`print(..., file=sys.stderr)` for progress messages) so both tools are
  safe to pipe `stdout` to a file.

## Timeout, cancellation, and graceful shutdown

Implemented for one-shot native TTS in Phases 2–3:

- The Swift engine pumps a bounded run loop. `--timeout` defaults to 120
  seconds: per-sentence for `save`, total for `speak`.
- The Python wrapper calls `communicate(timeout=timeout + 10)` as a whole-call
  backstop; expiry kills and waits for the child and raises `timeout` (124).
  Thus long multi-sentence saves can hit the wrapper's overall limit even if
  no individual sentence exceeds the native limit. Increase the explicit
  timeout when appropriate; do not assume a graceful SIGTERM/SIGKILL ladder.
- Phase 13B's optional cooperative Event uses one owned communication thread
  for complete stdin/output delivery, while the caller polls cancellation at
  200-ms intervals. It does not repeatedly invoke `communicate(input=None)`.
  Owned child and I/O drain are confirmed before claims are released; uncertain
  cleanup retains claims. Normal calls without an Event keep their original
  one-shot communication behavior. Batch worker admission also waits for its
  Future to be registered before scene/native side effects.
- Playback responds to SIGINT/SIGTERM (stop), SIGTSTP (pause), and SIGCONT
  (resume). Cross-process `mac-speech tts stop|pause|resume` target a tracked
  playback PID; the default single slot does not supervise concurrent jobs.
  See [TTS lifecycle](tts-engine.md#process-lifecycle-stop-pause-resume) and
  [configuration](configuration.md) for the PID-file override.

There is no persistent daemon or cooperative JSON cancellation protocol.
This contract does not retrofit lifecycle/versioning guarantees onto the
preserved legacy STT binaries.

## Versioning policy

- Current native TTS protocol version: **1**, independently of the Python
  package's release version. Compatibility requires an exact protocol
  version match, not matching package/binary release strings. The wrapper
  does not probe versions on import or launch a second process: it checks
  the version in the response to the requested operation. Rejection cannot
  undo playback or file creation already performed by that native process.
- The request object above describes the shared contract for future JSON
  request transports. Today's TTS engine accepts CLI arguments (and raw
  text via `--stdin`), not that JSON request object; its responses carry
  the version checked by the Python wrapper.
- `PROTOCOL_VERSION` (`python/mac_speech/native_protocol.py`) increments on
  any backward-incompatible change to the request/response shape.
- `SCHEMA_VERSION` (`python/mac_speech/results.py`) is a separate counter
  for the CLI's own JSON output shapes (`capabilities`, `doctor`), since
  those are consumed directly by scripts, not just by native engines.
- Additive, backward-compatible fields do not require a version bump;
  removing or renaming a field does.

### Resolving a TTS version mismatch

Synchronize the Python wrapper and native TTS binary from the **same
source checkout or release**. For a source checkout, activate the intended
Python environment, run `python -m pip install -e .`, then run
`./install.sh tts` to rebuild/install only TTS. Check `MAC_SPEECH_TTS_BINARY`
and `PATH` for an older binary still being selected (and `mac-speech doctor`
for binary-discovery details). Reinstalling only the Python package will
not update a separately installed native binary. Do not suppress the check
or substitute a guessed version; legacy STT's deliberate lack of a
version field is not a reason to accept an unversioned TTS response.
