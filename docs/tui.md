# Optional read-only terminal workspace — phase 1

This phase implements the user-approved **read-only** first slice of the
[TUI proposal](tui-proposal.md). It is not a speech runner, process supervisor,
reservation recovery UI or persistent background service.

## Install and launch

From a reviewed checkout, in your chosen virtual environment:

```sh
python -m pip install -e '.[tui]'
mac-speech tui
mac-speech tui --locale fr-FR --timeout 8
mac-speech tui --demo
```

No public PyPI publication is implied. For a reviewed wheel, install that local
wheel with its `tui` extra instead. Textual8.2.8 is pinned, MIT-licensed and declares
Python>=3.9; its optional transitive dependencies are not base runtime requirements.
The base package remains dependency-free, and normal CLI/help/version commands do
not import Textual. Missing UI dependencies produce install guidance. Launch needs
an interactive terminal; `--demo` displays explicitly fictional data with no native
processes. Installing the extra may fetch UI libraries, **not speech models**.

## Four tabs

- **STT:** selected locale/readiness, resolved locale, API availability and helper
  capability flags. Binary discovery alone never establishes asset readiness.
- **TTS:** currently reported voice catalog, names/regions/quality and identifiers
  displayed locally. No authorization request, speak/save or playback control.
- **Jobs:** no speech jobs are created by this phase. This session's speech job
  count is zero; external/other-CLI jobs are **unknown**, not assumed zero. Owned
  diagnostics are counted separately from speech execution.
- **System & Assets:** direct JSON and legacy-script helper paths, platform/Python,
  asset inventory and installed status. Host load/logical CPU count and **this
  dashboard's cumulative CPU/peak RSS** are labelled; they are not whole-machine
  RAM/CPU or native-job resource totals. Unavailable platform metrics stay unknown.

`Ctrl+R`, Refresh or Enter in the locale field refreshes read-only data; `Ctrl+Q`
quits. Tab navigation remains responsive while a probe waits. Refresh may start
short native diagnostic processes, but only these command families are allowlisted:

```text
whisper-py-convert-apple --inventory-status --language <validated locale>
whisper-py-convert-apple --reservation-maintenance inspect
mac-speech-tts voices --timeout <bounded timeout>
```

There are **no mutating action buttons**. Opening/refreshing never reserves,
releases, installs, transcribes, synthesizes, pauses/stops external processes or
exports data. Trust the configured/discovered native executable; an argv allowlist
is not a sandbox against a malicious binary.

## Freshness and shutdown

One refresh wave can run at a time. STT, inventory and TTS sections finish
independently; a busy STT gate does not block voice results or tab interaction.
Native inventory is itself locked. While it waits, the previous successful data
stays visible with its capture timestamp; errors show last-success retention.
Snapshots are observations, not continuous guarantees, and helper waiting/slow
status is not a fabricated analysis phase or progress percentage.

Each stdout/stderr stream is capped at 1MiB, with a diagnostic timeout between0
and30 seconds (exclusive0), default8. No raw engine stderr is rendered. Native
strings are plain text, control-sanitized and length-bounded; markup is not executed.
No default persistent log/history/cache/export file is written by this UI.

Quit/timeout drains only owned **read-only** diagnostic children. Cooperative
terminate is followed by a bounded wait and kill/reap fallback for those probes,
never arbitrary PID/name matching or an external speech job. Cancellation during
subprocess acquisition must wait for the created handle and stop/reap it. Abrupt
SIGKILL/power loss and malicious/uninterruptible OS I/O are not cleanup guarantees.

## Tests and boundaries

Backend tests use standard Python with fake payloads/synthetic children. Optional
Textual headless tests exercise tabs, responsive pending refresh, retained states,
invalid locale, literal native strings and clean Quit. They explicitly skip without
the extra; a skip is not frontend execution evidence. The developer's real UI smoke
uses demo/read-only diagnostics only, not any speech/asset mutation.

Normal transcript stdout/JSON/SRT and independent STT/TTS native targets are unchanged.
Readiness and asset counts are different from queued jobs, active processes and TTS
workers. This phase adds no cross-CLI registry, live speech cancellation, asset
confirmation dialog, automatic asset eviction or daemon. Those remain separately
approved later phases; see current verification/handoff for actual test outcomes.
