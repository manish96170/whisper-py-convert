# Safe Apple STT reservation maintenance

**Final follow-up:** after the stopped window below, the user approved temporary
reservation-first no-download reacquisition. Cached en_CA data became ready while
bound; actual owned success/provider failure/output failure/input-consumption
cancellation and readback returned to the same four reservations. Seven owned
repetitions and five-region switching passed. Risk #19's original defects are
locally resolved on the tested artifact; operational/deployment limits remain.
The Python wrapper now preflights readiness and native transcription forbids any
implicit download. [Explicit asset setup](apple-asset-setup.md) replaces first-use
auto-installation. Historical guard/pre-window notes below are not the latest state.

**Latest actual window:** the user subsequently approved one temporary en_CA
release. SDK returned true and exact readback preserved the other four, leaving
4/5. Exact en_CA installed status became false (still supported), so main STOPPED:
zero owned-transcription tests, downloads or re-pinning. The safeguards-only scope
below is historical; this result does not authorize any next recovery action.
See `docs/verification.md` and the current handoff for the recorded artifact hash
and `stt-approved-window-q645k4du/` evidence. Do not equate SDK uninstalled status
with proof the physical model files were deleted.

This uncommitted follow-up builds on `4769606`. **en-US remains the default**;
Canadian, British, Australian and Indian English remain supported. Non-default
does not mean unused. Capacity is a device-specific count of asset reservations,
not a process/recording quota. The existing gate still admits one active operation.

The user approved implementing the interface/guards, **not releasing any particular
real reservation**. No real release, asset download, new commit/push, ledger,
persistent worker/cache, daemon, automatic pruning or release-all is authorized.
Risk #19 stays partial until real newly-owned cleanup is evidenced.

## Read-only inspection and preview

Use the same built `whisper-py-convert-apple` executable throughout. Apple does
not document the identity key for bare executables; a separate Swift probe cannot
be assumed to recover its inventory. With `APPLE_BINARY` set to the intended build:

```sh
"$APPLE_BINARY" --reservation-maintenance inspect
"$APPLE_BINARY" --inventory-status --language en-US
# Exact returned identifier; this is a preview ONLY, not permission to release:
"$APPLE_BINARY" --reservation-maintenance release --reserved-locale en_CA --dry-run
```

Both inspect paths now acquire the same reservation lock. Maintenance JSON shows
current `reserved_locales`, actual maximum and exact installed asset status (not
nearby-region substitution). Unconfirmed `release` also defaults to preview. These
paths never reserve, release, create an installation request or download assets.

## Later separately approved operator action

First confirm one exact emitted identifier is unused and old/non-cooperating
invocations are stopped. The gate cannot protect clients which ignore it. Then,
only after separate approval of that target:

```sh
# Do not run until APPROVED_UNUSED_LOCALE has been explicitly approved.
"$APPLE_BINARY" --reservation-maintenance release \
  --reserved-locale "$APPROVED_UNUSED_LOCALE" \
  --confirm-release "$APPROVED_UNUSED_LOCALE" --confirm-unused
```

Default en_US additionally needs `--allow-default-release`. Aliases, wildcards,
mixed transcription flags, duplicate options and release-all are rejected; the
release selector must match an actual inventory identifier. Confirmation is an
operator acknowledgement, not a manufactured Apple ownership proof.

Exactly one release is attempted using the actual object from `reservedLocales`.
The complete release/readback phase is cancellation-isolated **and fully awaited**
before unlocking. No retry, reserve, installation or automatic rollback occurs.
True/false both require readback: target absent, all non-target entries unchanged.
False with verified absence is legitimate when the target matched before the
attempt. An initially absent target (repeat, typo or alias) is refused without
another release or a claim of prior release history. Unexpected state produces `verified: false`, JSON
and a nonzero exit. Inspect rather than automatically correcting unknown state.

Apple release unsubscribes dependent assets. Availability can change immediately
or later; offline retention and reversibility are not guaranteed. Reports include
post-action asset status but never restore/download assets. After admission, a
signal cannot abandon action/readback; interrupted output may lose the report,
so inspect afterward. SIGKILL/power loss cannot complete this path.

## Optional native validation guards

These flags are for the **native binary**, not the unchanged legacy Python script
or public Python adapter. Normal CLI defaults/first-use installation are unchanged:

- `--require-installed-assets`: check before acquisition and again before media
  setup; fail as `assets_not_installed` without even creating an installation
  request (which itself can reserve), and without downloading.
- `--require-exact-locale`: refuse nearby-region substitution; transcription
  spelling variants (`en-CA`/`en_CA`) are equivalent, maintenance selectors are not.
- `--require-new-reservation`: reject borrowed `reserve == false` as ownership
  evidence, leaving that pre-existing reservation untouched.

After an approved release **only if assets remain installed**, use all three flags
with the exact locale and synthetic media. A successful borrowed/fallback run is
not evidence: require true acquisition, one unique actual supporting-locale delta,
and verified return to the prior inventory after success, invalid media, analyzer
cancellation and controlled output failure. If assets disappear, stop; downloading
requires separate approval. At the safeguards-only checkpoint full5/5 blocked
validation; after the approved window the current blocker is exact en_CA SDK
installed status being false, with4/5 reservations. The window stopped there.

## Cautious cancellation hardening

Apple does not document release behavior inside a cancelled task. The entire owned
cleanup snapshot/release/readback phase now runs independently of caller cancellation
and is fully joined. Cancellation-sensitive mocks test ordering and completion;
primary errors are preserved if cleanup fails, and late cancellation during otherwise
successful cleanup is reported after joining. This is defensive hardening, **not
a reproduced Apple failure**, and not a guarantee for forced wrapper timeout kills,
non-cooperating clients or indefinitely stalled framework/file-device I/O.

Actual verification/reviewer results and remaining gates are in
`docs/verification.md` and `docs/SESSION_HANDOFF.md`. Historical test snapshots
remain historical; no skipped or borrowed run is relabeled newly-owned evidence.
