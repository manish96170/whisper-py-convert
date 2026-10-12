# macOS and Apple Silicon support

Current uncommitted follow-up keeps default en-US and every supported regional
locale; no variant is automatically evicted as "unused". New maintenance and
native validation controls preserve the same Swift 6.4/macOS 27 STT boundary,
independent of TTS. See [maintenance safety](stt-reservation-maintenance.md).

In the subsequently approved en_CA window, its reservation was released but exact
installed status became false; the test window stopped. Canadian English remains
supported by the SDK, not confirmed offline-ready. Other four regions remain
installed/reserved. Do not equate available regional choices with installed assets.

**Status:** Updated through Phase 12. Personal Voice/system-voice findings
remain the Phase 5 observations; packaging/Python evidence is below. Native
source requires Swift 6.4+, separately from runtime deployment floors (TTS
macOS 13+, Apple STT macOS 27+). Older OS/Intel runtime claims await actual
testing, not inference from compilation or mocked CI jobs.

The subsequent approved en_CA metadata binding restored cached usability while
owned without an installation request. Four owned outcomes/repetition/readback
are now evidenced locally, not a general offline-retention guarantee. Apple
first-use setup is explicit and readiness checks are generic to the selected
compatible Mac/helper; see [asset setup](apple-asset-setup.md).

## Phase 12 Python runtime evidence

Final wrapper unit tests pass on Python 3.11.3 (322 passed, four real STT
fixtures skipped for risk #19) and, excluding those native fixtures, 3.12.5,
3.13.7 and 3.14.8 (322 passed each). The latter source-based runs reused
existing pure-Python pytest tooling via `PYTHONPATH`; they are not fresh
install tests. Clean non-editable wheel installation and network-denied
native TTS were independently verified with Python 3.11.3 on the Mac below.
Python 3.9/3.10 remain unverified locally despite configured CI jobs.
These checks do not establish older-macOS or Intel native-engine support.

## What is verified today

| Capability | Verified on | Notes |
| --- | --- | --- |
| `mac_speech` Python package (capability discovery, `doctor`, `version`, shared CLI) | macOS 27.0.1, arm64, Python 3.11.3; newer Python wrapper tests above | Standard-library-first wrapper; diagnostics can run without speech engines. Non-macOS diagnostics are intended to report missing Apple engines rather than infer support. Native speech commands still require the selected installed backend; a pure Python wheel is not proof of native support on another platform. |
| Existing Apple STT backend (`whisper-py-convert-apple`) | macOS 27.0.1, arm64; reservation maintenance 2026-10-12 | Requires Swift 6.4/macOS 27-compatible SDK/runtime because it uses `AssetInputSequenceProvider`; Intel/older macOS unverified. Risk #19 is partially repaired, with explicit real-test prerequisites and no unsupported-locale catch-and-skip. Device-specific reservation capacity is not a request quota. Existing-state recovery and real newly-owned cleanup remain separate gates; see [repair evidence](stt-reservation-repair.md). Phase 12 skips remain historical, not passes. |
| `AVSpeechSynthesizer` voice enumeration (Phase 0 feasibility probe, not shipped code) | macOS 27.0.1, arm64 | 191 voices enumerated with no network call via a throwaway probe script; superseded by the real engine below. |
| **Native TTS engine (`mac-speech-tts`, Phase 2, shipped)** | macOS 27.0.1, arm64 | **Minimum macOS version decided: 13.0** (`engines/tts-swift/Package.swift`), deliberately decoupled from the STT target's macOS 27 floor — see `docs/decisions/ADR-001-repository-and-module-boundaries.md`. Driven by `AVSpeechSynthesizer.write(_:toBufferCallback:)`, a macOS 13+ API. `personalVoiceAuthorizationStatus` and `AVSpeechSynthesisVoice.voiceTraits` (Personal Voice/novelty detection in `voices`) both actually require **macOS 14+** — corrected during Phase 5 after the compiler rejected an incorrect macOS-13 assumption from Phase 2 (`#available(macOS 14.0, *)` guards both, reporting `"unsupported"`/`false` on macOS 13). **Only actually tested on macOS 27.0.1** — the macOS 13/14 code paths compile but have not been run on real macOS 13 or 14 hardware/VMs. |
| Personal Voice (`AVSpeechSynthesizer.personalVoiceAuthorizationStatus`, `.isPersonalVoice` trait) | macOS 27.0.1, arm64 | **Verified end-to-end in Phase 5**, not just detected: on a Mac with real, user-created Personal Voices already set up, authorization status read `"authorized"`, `voices` correctly flagged exactly those entries as `is_personal_voice: true`, and synthesizing audio with a Personal Voice identifier succeeded through the existing, unmodified voice-resolution code path — no special-casing needed. Separately verified `requestPersonalVoiceAuthorization`'s completion handler never fires from this bare, unsigned, bundle-less binary (twice, including once when status was already `.authorized`) — most likely because it has no `Info.plist`/`NSPersonalVoiceUsageDescription` for the system to prompt from. This engine therefore only *reports* status (`personal-voice-status`); it never attempts to request, create, or extract a Personal Voice. See `docs/tts-engine.md` for full detail. **Do not reference the specific name/identifier of any real Personal Voice found during testing in any committed file** — it is real personal data. |
| Voice catalog stability | macOS 27.0.1, arm64 | **Found unstable in Phase 5**: the compiled `mac-speech-tts` binary consistently reported fewer voices (180-182 across several runs) than a fresh `swift -e`/`swift file.swift` script in the same session (191, stable across repeated runs). Treat the voice catalog as something to re-query every time, never cache or assume a fixed count/membership. |

## What is explicitly not supported or not yet verified

- **Intel Macs:** not tested. The existing Apple STT backend's target
  platform list in `Package.swift` is `.macOS(.v27)` with no architecture
  restriction, but `AssetInputSequenceProvider` and friends have only been
  exercised on Apple Silicon here. Treat Intel support as unknown until
  tested on real Intel hardware.
- **macOS versions older than 27:** the existing Apple STT backend
  explicitly requires macOS 27 (`ARCHITECTURE.md`). The native TTS engine
  (`engines/tts-swift/`) deliberately targets a lower minimum, macOS 13.0,
  decoupled from the STT target via a separate SwiftPM package — see
  `docs/tts-engine.md`. That minimum has not been empirically tested on
  real macOS 13 or 14 hardware; only compile-time `#available` checks and
  testing on macOS 27.0.1 have happened so far.
- **Windows and Linux:** the Windows AI Speech backend (`windows/`) is a
  separate, unrelated STT helper outside this plan's TTS scope. There is no
  TTS plan for Windows or Linux. `mac_speech`'s Python-only pieces
  (capability discovery, shared CLI diagnostics) are intended to import/run
  with Python >=3.9 without Apple engines. TTS reports a missing engine;
  STT availability depends on an actually discovered Windows helper or
  matching faster-whisper installation. This is not a verified Windows/Linux
  runtime matrix or a guarantee of unavailable STT on every non-Mac host.
- **Personal Voice full lifecycle:** only authorization-status detection
  and already-authorized usage have been verified (Phase 5). Actually
  driving the authorization *request* flow from this tool is confirmed
  **not** to work (completion handler never fires from this bare binary);
  authorizing Personal Voice for the first time requires some other
  properly-bundled app or system flow, which is out of scope here. Per
  `PLAN.md`'s non-goals, this project will never attempt to bypass
  Apple's Personal Voice restrictions or assume availability.

## Policy

- Capability checks (`mac_speech.capabilities`) always perform real,
  read-only probes rather than branching on a hard-coded OS version string,
  per `PLAN.md` section 3.3. Version-specific behavior differences, when
  discovered, should be handled by checking for the capability itself
  (e.g. "does this API exist / does it return a usable result") rather than
  gating on `sw_vers` output, wherever the underlying API allows that.
- Any new minimum-OS-version requirement introduced by a later phase must
  be recorded in this file with the specific API that requires it, mirroring
  how `ARCHITECTURE.md` already documents why the Apple STT backend
  requires macOS 27.
