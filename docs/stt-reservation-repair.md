# Apple STT reservation maintenance — risk #19

**2026-10-12; partially repaired, not fully resolved.** This is separately
authorized maintenance of the native Apple STT target, not a TTS refactor or
Phase 13 feature expansion. Baseline was clean `main`,
`ad414abf9dce8b0055aa8a1810355aacb2e1bc0c`.

## Defects and current API evidence

The baseline source called `AssetInventory.reserve` but never released it,
and used a false return to report unsupported locale. Apple explicitly says
**false means already reserved**. The baseline Python suite reproduced **431
passed, four skipped**; all four skipped the incorrect unsupported message.
Those skips were not successful native regression tests.

Apple documentation and the installed Swift 6.4/macOS 27 SDK were checked:

- [reserve(locale:)](https://developer.apple.com/documentation/speech/assetinventory/reserve(locale:))
  reserves the supporting asset locale; false means already reserved; capacity
  and unsupported allocation throw.
- [reservedLocales](https://developer.apple.com/documentation/speech/assetinventory/reservedlocales)
  is an async app inventory; returned locales may be variants of requested tags.
- [maximumReservedLocales](https://developer.apple.com/documentation/speech/assetinventory/maximumreservedlocales)
  is synchronous, device/storage-dependent. Five was observed here; it is not
  a universal count, recording limit, duration restriction or paid request quota.
- [release(reservedLocale:)](https://developer.apple.com/documentation/speech/assetinventory/release(reservedlocale:))
  is async/nonthrowing; false means not reserved; it unsubscribes dependent assets.
- [supportedLocale(equivalentTo:)](https://developer.apple.com/documentation/speech/speechtranscriber/supportedlocale(equivalentto:))
  may choose a near-equivalent region, preferring installed locales. The helper
  uses the returned locale consistently and reports meaningful substitutions.
- [assetInstallationRequest(supporting:)](https://developer.apple.com/documentation/speech/assetinventory/assetinstallationrequest(supporting:))
  can automatically reserve missing required locales. This helper explicitly
  reserves before requesting assets for its **single** resolved transcriber.
  The complete-body cleanup snapshot checks for unexpected extra supporting
  reservations, including when request creation/download throws. Extra entries
  are retained with an ownership error/warning; only the original confidently
  owned reservation is released. No undocumented invariant or extra-entry
  ownership is silently assumed.
- The SDK exposes `SFSpeechErrorDomain` and named
  `SFSpeechError.Code.tooManyAssetLocalesAllocated` /
  `cannotAllocateUnsupportedLocale`. Classification uses these values, not
  localized English substrings; other errors retain domain/code/description.
- [cancelAndFinishNow()](https://developer.apple.com/documentation/speech/speechanalyzer/cancelandfinishnow())
  finishes analysis and result streams, even before input. `analyzeSequence`
  can return early on cancellation without throwing, so explicit task checks
  reject cancelled partial success. Finishing an analyzer does not drain the
  application-owned input sequence by itself.

The SDK evidence is in
`Speech.framework/Versions/A/Modules/Speech.swiftmodule/arm64e-apple-macos.swiftinterface`
under the selected macOS SDK. Asset/transcriber APIs begin at OS 26, but this
target retains **macOS 27** for `AssetInputSequenceProvider` and Swift tools 6.4.
Independent TTS stays in its separate package/platform boundary.

## Design and preserved contracts

One per-user `flock` gate at
`~/Library/Application Support/whisper-py-convert/apple-stt-reservations.lock`
serializes **cooperating repaired executables across all locales**, from
inventory snapshot through output and awaited cleanup. It is intentionally not
per-locale: locale slots share app capacity. Lock file/directory are owned,
private regular state; the file is never unlinked, so waiters use the same lock.
Concurrent CLI requests wait (50-ms cancellable polling), reducing parallel STT
throughput. TTS is never gated by this lock.

This gate is not a five-process limit or a persistent FIFO job queue. Six
simultaneously submitted direct calls completed successfully in the final local
commit-preparation check with unchanged borrowed inventory. A full idle locale
inventory can still block a genuinely new supporting locale; waiting alone does
not evict stale reservations. The user later authorized a combined source/licensing
commit and push, not automatic asset recovery or a queue-service implementation.

`reserve == false` borrows a pre-existing reservation, never releasing it.
For true, exactly one newly-added inventory locale establishes ownership;
cleanup releases **that returned variant**, not the requested identifier.
Ambiguous ownership fails closed and retains state for manual inspection.
There is no persistent reference counter, arbitrary eviction or auto-reset.
Apple exposes no process reservation handle or documented app-global reference
count. The gate cannot protect clients that do not cooperate (including old
binaries), or an independently modified lock pathname/trusted directory.

The entire asset/provider/analysis/results/encoding/output body is inside the
reservation lifetime. It records the primary result/error, then awaits release
before returning/unlocking/outer `exit`. Release false/error is reported; a
secondary cleanup issue warns without replacing the primary transcription error.
Tests inject a throwing release to exercise that preservation although Apple's
actual release API is nonthrowing.

Analyzer failure/cancellation initiates an idempotent stop task and **awaits the
same task**, cancels and awaits the owned results collector, then releases assets.
Successful collection also atomically closes cancellation-handler admission and
joins any initiated stop, including cancellation at the final-check/scope-exit
boundary. A deterministic delayed-stop test covers that race.
Input analysis is awaited; no application-owned provider producer task is
detached. Success finalizes through the returned last sample and awaits results;
no-input completion uses immediate finish rather than waiting for nonexistent
input. SIGINT/SIGTERM cancel the operation and the entry point awaits cleanup.
Stdout uses bounded nonblocking partial writes with cancellable readiness polling;
closed pipes fail without SIGPIPE termination and stalled readers do not leave
an undrained background writer. Diagnostics/help make one bounded nonblocking
write and discard unwritten bytes on backpressure/error, so broken **or full
unread** stderr cannot abort/block cleanup or mask the primary error. Diagnostics
are best-effort, not lossless; transcript output remains separately error-reporting.
Cancellation during framework asset installation must wait for the framework
call to return; bounded cancellation latency is not promised.
Nonblocking pipe output is not a real-time guarantee for regular-file storage I/O.

Existing `--language`, `--format text|json`, `--timestamp-mode none|segment|word`,
`segments[].text/start/end/words[]`, text newline behavior and Python SRT
rendering remain intact. Diagnostic markers on stderr distinguish unsupported,
capacity, reservation, installation, transcription, output and cleanup failures.
Both Python legacy-script and direct-JSON paths retain these diagnostics and
provide compatible actionable errors. `whisper-py-convert.py`, `windows/`,
`engines/tts-swift/`, `install.sh` and base runtime dependencies are unchanged.

## Read-only state and native evidence

Additive `--inventory-status [--language locale]` emits read-only JSON from the
**same executable identity**, with availability, resolved locale, asset status,
actual reservations and capacity. It never reserves, installs or releases.
Before any repaired transcription, the scratch-built executable reported:

```json
{"available":true,"supported_locale":"en_US","installed":true,
 "reserved_locales":["en_AU","en_CA","en_GB","en_IN","en_US"],
 "maximum_reserved_locales":5}
```

Seven independently synthesized non-sensitive en-US recordings transcribed
successfully to native JSON with actual words. Sequential text transcription
switched among **all five already-installed regional locales** successfully.
The same executable's inventory was unchanged after every run. Invalid media
failed during provider setup with `[transcription_failed]`, domain
`AVFoundationErrorDomain`, code `-11800`, and unchanged reservations. These are
**borrowed-reservation** tests, not evidence of newly-owned release.
Opted-in Python fixtures passed **4/4** (text, JSON, segment SRT, word SRT), with
explicit Apple selection; no auto fallback/dependency/model download occurred.

The machine has no free reservation slot. No pre-existing reservation was
released; real true-acquisition/owned cleanup after success/failure remains
**blocked**. No additional locale assets were downloaded. Approving any targeted
release requires confirming that reservation is unused and performing recovery
through the same executable identity under coordination—not assuming a separate
Swift probe resets this binary. Current installed binaries were not overwritten.
Read-only `codesign` shows linker/ad-hoc signing with identifier
`whisper-py-convert-apple`, no bound Info.plist/team. Apple's exact reservation
identity key for bare executables/rebuilds is not documented; matching identifiers
and observed inventories do not establish universal rebuild/copy identity rules.

SIGKILL, crashes and power loss cannot guarantee framework cleanup. The OS
releases the file lock on process death, not Apple reservations. No global cache,
speech database or asset purge, binary renaming or re-signing workaround is used.

## Repeatable checks

Use isolated scratch/cache directories beneath the approved temporary root:

```sh
.venv/bin/python -m pytest tests/unit -q -rs
.venv/bin/python -m ruff check python/mac_speech
.venv/bin/python -m mypy
swift build --configuration release --scratch-path "$STT_RELEASE" \
  --cache-path "$STT_RELEASE_CACHE" --manifest-cache none
swift test --scratch-path "$STT_DEBUG" --cache-path "$STT_DEBUG_CACHE" \
  --manifest-cache none
RUNNER_TEMP="$APPROVED_TEMP" bash scripts/ci_swift.sh
python3 -m py_compile whisper-py-convert.py
MAC_SPEECH_TEST_APPLE_STT=1 MAC_SPEECH_TEST_APPLE_BINARY="$APPLE_BINARY" \
  .venv/bin/python -m pytest tests/unit/test_stt_regression_fixtures.py -q -rs
```

`MAC_SPEECH_TEST_APPLE_LOCALE` defaults to en-US. Native fixture audio is generated
only after a successful read-only installed-asset preflight. The fixture uses an
unchanged scratch copy of the legacy script with a sibling symlink to the selected
binary, ensuring text/SRT and direct JSON actually invoke the same executable.
Without native opt-in the four fixtures skip for that precise prerequisite;
provisioned transcription errors, including unsupported messages, **fail**.
Malformed/failed inventory diagnostics also fail, never becoming broad skips.
Hosted Python CI does not establish native macOS 27 STT coverage; the TTS CI
helper remains independent and unchanged.

Final command counts and independent review are recorded in
[verification](verification.md) and [session handoff](SESSION_HANDOFF.md).
Historical per-phase counts/handoffs have not been rewritten as repaired passes.
