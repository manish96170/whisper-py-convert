# Future optional speech workspace TUI — design proposal

**Proposal only, not implemented.** The user requested STT/TTS tabs, monitoring,
job visibility and safe maintenance controls. This does not authorize a daemon,
new runtime dependency, arbitrary process termination, asset download or eviction.
Existing command-line/Python APIs remain first-class and independently usable.

## Layout

```text
┌ Mac Speech ── STT │ TTS │ Jobs │ System & Assets ────────────────────┐
│ STT: input · engine · requested/resolved region · format · output    │
│      [Start] [Cancel queued] [Cancel owned running job when safe]   │
│ TTS: voices · text · rate · audio format · Speak/Save · scene batch  │
│ Jobs: queued → starting → waiting → running → cleaning up → result  │
│ System & Assets: selected binaries, CPU/RSS samples, asset snapshot │
│                  exact reservation preview and confirmation        │
└ active jobs · queued jobs · inventory age · warnings ───────────────┘
```

Show four separate quantities: **queued jobs**, **active native processes**,
**TTS batch workers**, and **Apple reserved asset locales**. A display of 4/5
reservations does not mean four active processes. Missing progress is indeterminate,
not an invented percentage or ETA. Requested versus resolved locale stays visible.

## Concrete asset visibility

The approved en_CA window provides a useful real example: reservation count moved
5→4; exact en_CA remains supported but SDK installed status became false. Other
four regions remain reserved/installed. Display these independently:

| Region | Supported | SDK installed | Reserved | Job ownership |
| --- | --- | --- | --- | --- |
| en_US | yes | yes | yes | pre-existing/unknown unless a tracked job proves otherwise |
| en_CA | yes | no after approved release | no | none established |

Do not label support as deleted, infer physical files were removed, or claim a
released region will remain offline-ready. Apple controls asset retention.

The subsequent approved no-download binding restored cached CA usability while
owned; cleanup returned to4/5. Thus readiness, idle subscription and cache usability
are distinct. Generic French readiness now blocks analysis and displays an explicit
setup command. Future TUI should use native setup preview/confirmation—not silently
call download from a Start/refresh button. See `docs/apple-asset-setup.md`.

## Safety and monitoring boundaries

- Run refreshes off the UI thread. Locked inventory reads can wait behind long STT
  work: show **refresh pending; last snapshot at …**, with one outstanding refresh.
- A release button first **previews** an exact target, displays asset-retention
  consequences, requires matching confirmation and quiescent-client acknowledgement,
  drains owned work, then revalidates under the native gate. No “free all,” stale
  preview execution, PID-based reservation eviction or automatic rollback.
- Controls target **TUI-owned** process handles/jobs by default. Externally observed
  processes are separately labelled, read-only and best-effort; name/PID alone cannot
  prove reservation ownership or safe cancellation. PID reuse needs identity checks.
- Show Cancelling → Cleaning up → terminal outcome, including **cleanup unverified**.
  Cancelling a dialog cannot abandon an already-admitted native release/readback.
- Source text, transcripts, raw stderr, voice identifiers and sensitive paths are
  not persisted in default history. Explicit exports are private and bounded.
- System CPU/RSS sampling is optional/rate-limited, with platform/permission caveats.
  Do not claim comprehensive global speech-client monitoring or zero overhead.

## Architecture and future work

Use existing `mac_speech` clients and native maintenance interfaces, not a second
Speech implementation. Keep independent TTS and empty base runtime dependencies.
Evaluate **Textual as an optional `tui` extra**, checking its version/Python floor
before selecting it. Rich alone needs more custom interaction; stdlib curses moves
resize/input/accessibility/portability work into this repository. Install nothing
for this proposal.

Current gaps: blocking STT clients lack cancellable job handles/live callbacks;
there is no general cross-CLI registry. Playback's single PID-file slot is not a
safe general supervisor. Batch provides typed results/cancellation but no public
live event callback. Native `Validation:` events are **validation-only**, not the
future UI protocol. Later introduce opt-in versioned events on a separate bounded
pipe (job ID, sequence, phase, elapsed time, sanitized error), never altering
transcript stdout or TTS's final response. Drain/coalesce events so telemetry cannot
block cleanup, and support old binaries honestly.

Bounded phases, each separately approved:
1. Read-only tabs, capabilities, timestamped assets and mocked jobs.
2. Session-owned execution through existing APIs; bounded scheduling and only
   genuinely supported cancellation/playback controls.
3. Reviewed structured lifecycle events and exact-target maintenance UI.

Acceptance: responsive navigation during blocked refresh; missing extra/binary
diagnostics; unchanged CLI contracts; limits/cancel/drain/PID reuse tests; stale
preview refusal, exact confirmation and non-target preservation; no asset mutation
just from launching the TUI. Use mocks first, real native actions only with explicit
scope. A TUI improves visibility; it cannot bypass Apple's reservation capacity.
