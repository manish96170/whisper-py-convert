# Apple STT language readiness and explicit asset setup

This applies to the Apple engine on a compatible Mac: the current source requires
Swift 6.4/macOS 27-compatible SDK/runtime and supported hardware. It does not make
Apple STT available on every Mac or affect Windows, faster-whisper or independent TTS.
Default stays en-US; other languages/regions come from the device's Apple catalog.

## Before analysis, not a surprise download

The public Python STT adapter now performs a **read-only native preflight** before
Apple transcription, for direct JSON and legacy-script text/SRT routes. A short
native diagnostic process is necessary to query Apple's APIs; no audio analysis,
reservation, installation or download happens in that preflight.

For example:

```sh
mac-speech stt transcribe recording.wav --engine apple --language fr-FR --format json
```

If assets are not ready, the wrapper fails with the requested/resolved locale and
a shell-quoted command for the **exact helper it would invoke**. Conceptually:

```text
Apple STT locale fr-FR (resolved to fr_FR) is not ready.
Asset setup may download missing Apple models; no transcription or download started.
Run explicit command then retry:
<actual Apple helper> --install-assets --language fr_FR --confirm-download fr_FR
```

Do not paste the placeholder; use the real command printed by your installation.
Paths are discovered/quoted, not hardcoded to a development machine. `auto` checks
Apple only if the selected route actually resolves Apple; other backend routing
is unchanged. Prefer explicit `--engine apple` when validating Apple to avoid any
faster-whisper fallback/dependency/model download.

## Preview first, then explicit consent

With `APPLE_BINARY` set to your selected built native helper:

```sh
"$APPLE_BINARY" --inventory-status --language fr-FR
"$APPLE_BINARY" --install-assets --language fr-FR
# Only if you approve setup/network use for the displayed supported locale:
"$APPLE_BINARY" --install-assets --language fr_FR --confirm-download fr_FR
```

The first two commands are read-only. Confirmation must match the displayed
supported locale; unsupported languages, unavailable APIs and full reservation
capacity fail without silently choosing another locale or evicting reservations.
Installed/cached assets might need only a reservation, not a network transfer.
SDK installation requests reuse cached data when available; exact network bytes
are not inferred. No French asset download is performed during development here.

Successful explicit setup **deliberately retains** its supporting reservation so
assets remain subscribed for later use. That persistent cache intent is different
from temporary transcription ownership. Failure/cancellation/report-publication
failure cleans only a newly identified owned reservation; borrowed state remains.
Apple still controls retention/updates, and its capacity varies by device/storage.
No global reset, arbitrary eviction or automatic rollback is provided.

## Native safety and compatibility change

Normal native transcription no longer creates installation requests or downloads
automatically. It reserves if needed, then requires assets ready **before** media
provider/analyzer setup. This closes a readiness race after the wrapper's preflight.
`--no-asset-download` explicitly names that default. Transcript JSON/text/SRT and
timestamp options remain unchanged; first-use language setup is now explicit.

`--require-installed-assets` remains stronger: it refuses before even reserving.
For the separately approved temporary cached en_CA experiment, reservation-first
`--no-asset-download --require-exact-locale --require-new-reservation` can check
whether metadata binding restores readiness, while still refusing any installer.
Only newly owned state is cleaned afterward; no persistent re-pinning is implied.

The inventory reports `asset_setup_supported: true` and
`automatic_asset_downloads: false`. The Python wrapper refuses old/malformed helpers
without these guarantees and prints rebuild guidance. A wheel/source push does
not replace native binaries; use matching reviewed source/engine versions.
The protected standalone legacy script remains unchanged, but its newer native
helper also refuses implicit downloads. Asset flags are native-only, not new legacy
script flags. Missing assets are never treated as a generic regression-test skip.

Future TUI assets/status views should consume these same read-only readiness and
preview/confirmation paths; a missing asset is a setup state, not an active job.
The TUI is still a design proposal in `docs/tui-proposal.md`.
