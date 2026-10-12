# Clean-install and offline core verification

## Explicit setup and real ownership evidence — latest local verification

The approved temporary en_CA metadata reacquisition succeeded without an
installation request/download: cache usability was restored while bound, then
owned cleanup returned to the same4/5 idle state. The original stopped-window
result below is historical, not the final outcome.

| Native owned case | Actual outcome | Cleanup/readback |
| --- | --- | --- |
| Synthetic word-JSON success | exit0, expected nonempty transcript/words | en_CA acquired/released, original four preserved |
| Invalid media after acquisition | exit1, AVFoundation/-11800 | same verified return |
| Closed stdout after collection | exit1, POSIX/32 | same verified return |
| SIGTERM after first real analyzer input requested | exit130, no analysis-finished event | same verified return |

Each run required reserve==true and a unique actual supporting delta; emitted
`acquired` only after ownership established and `released` only after joined
cleanup/readback succeeded. An `analysis-entry` marker alone is not proof; this
cancellation trial waited for `analysis-input` from the wrapped iterator. It proves
cancellation after native input consumption began, not a hardware-inference timing
measurement. No held pre-existing reservations were released during these tests.

Same compiled binary SHA256:
`58a1fa9259852c4fa78ba3a82475452b0fe96750fa167977856062090dba1846`.
Evidence under approved temp `stt-owned-proof-w5ykvv8x/summary.json`, case JSON and
synthetic transcript. Seven more newly-owned CA recordings and sequential text
switching across en-US/en-CA/en-GB/en-AU/en-IN passed (`stt-owned-repeat.json`).
Other four remained reserved/installed; no installations/downloads/re-pinning.
Independent read-only evidence closure recomputed that executable hash and checked
all four raw case logs, parsed events, transcript (nine ordered words) and identical
before/after inventory/installed status. It supports **local resolution of the two
original risk #19 source defects**, with recorded Mac/SDK/artifact scope. It audited
retained results, not a new native reproduction. Input consumption is not proof of
sustained hardware inference; OS-wide background network activity was not measured.

Real French inspection/setup PREVIEW and public Python wrapper refusal showed the
resolved fr_FR locale and exact quoted confirmed-setup command. No French analysis,
reservation or download started, and inventory was unchanged (`stt-french-preflight.json`).
An initial script expected an optional nil JSON key to exist; `.get` fixed the
read-only assertion, and the successful rerun is the evidence counted here.

Commands: default Python **574 passed/four explicit opt-in skips**; native-enabled
Python **578 passed/zero skips**, including text/JSON/segment+word SRT fixtures.
Root Swift **61 tests passed**, release build passed; Ruff/mypy (18 sources)/legacy
py_compile passed. Independent TTS helper results remain separate. No shared
caches/DBs were purged; generated evidence/binaries stay outside Git.
Fresh independent TTS helper completed **48 tests and release build**, with its
existing isolated TestingMacros retry (`stt-setup-tts.log`). Native-enabled Python
again passed **578/zero skips** after final setup fixes. No new hosted CI run,
source commit/push or installed engine replacement is implied.

Independent setup/preflight review closed both medium findings (report/cancellation
outside retention lifetime and non-target loss before installer). Its isolated
61 Swift tests, 131 Python mocked tests, release build and correction repros passed,
with no remaining medium/high findings in that scope. Source/test files were
matched to tested snapshots; reviewer performed no real asset calls/downloads.
Evidence: `asset-closure-swift-e9h_m0w6/` and `asset-closure-python-cvkr9gf7/`.

Successful explicit setup is deliberate persistent subscription intent; regular
transcription remains temporary-owned or borrowed. No confirmed setup command was
executed here. Native first-use downloads are now forbidden during transcription;
setup/network consent is separate. Generic preflight paths/capability negotiation
are documented in `docs/apple-asset-setup.md`.

## Approved en_CA maintenance window — stopped result

After explicit user approval, main verified no native STT helper was active,
froze the compiled artifact, inspected full5/5/all-installed state, and executed
**one** confirmed pre-existing en_CA release through that same binary/gate. Apple
returned **true**; readback verified only en_CA disappeared and the other four
reservations remained unchanged. The exact en_CA installed check became **false**.
Main immediately STOPPED as promised: **zero owned-transcription validation runs,
zero downloads/installation requests, zero re-pinning**. Read-only diagnostics then
confirmed en_CA remains supported (`supported_locale: en_CA`) but `installed: false`;
en-US/en-GB/en-AU/en-IN remain exact and installed, with4/5 reservations.

This establishes real targeted release/readback, not complete new-ownership cleanup.
Risk #19 remains partial. SDK uninstalled status does not prove physical files were
deleted; a later reserve-only recovery could potentially expose cached data, but
that is unverified and needs new approval. Normal unguarded CA transcription may
create an installation request and is not an approved diagnostic probe.

Evidence under approved temporary `stt-approved-window-q645k4du/`: fingerprint,
before/release/stopped read-only JSON. Frozen binary SHA256
`4bce6e5aaf6502e2a91231ca49eeec465c82e265c0e3a4f40b0f11fc996f76b9`, original
product identifier/ad-hoc linker signing; no identity-evasion step. Validation-only
stderr ownership/analysis diagnostics were added and tested before the action:
**47 Swift tests passed**, release build passed. No installed binary replacement,
commit/push or TUI implementation was performed.
Independent stopped-window review verified the report/hash/non-target preservation,
reran 47 mocked Swift tests, and found one evidence-label ambiguity: the initial
`analysis-started` event preceded analyzer admission and could not establish active
analysis. It is now named `analysis-entry`, explicitly not active-analysis proof.
No owned runtime validation used that event. Current-facing stale state wording
was corrected; reviewer closure reported no new issue in those fixes. The original
4bce… window executable is preserved unchanged, while the final source build uses
a separate scratch directory (`stt-window-final-release`) and is not executed as
a recovery probe. No further Speech mutation was performed after stopping.

## Uncommitted reservation maintenance follow-up — 2026-10-12

Starting tree independently verified clean at published `4769606`; hosted CI
`38213808150` passed for that baseline, not these new changes. The user authorized
the bounded [maintenance safeguards](stt-reservation-maintenance.md), while keeping
default en-US/all regional choices, not an exact real release, download or new push.

- Baseline rerun: **483 passed/four explicit native opt-in skips**.
- New default Python suite: **491 passed/four opt-in skips**; native-enabled suite:
  **495 passed/zero skips**, including real text/JSON/segment+word SRT fixtures.
  Ruff/mypy (18-file scope)/legacy py_compile passed; release STT build passed.
- Independent TTS helper: **48 Swift tests passed**, release build passed, unchanged
  TTS implementation/platform. No global caches were deleted.
- Native locked inspect and **five previews** made no reservation changes. Exact
  installed/offline word JSON passed for en-US/en-CA/en-GB/en-AU/en-IN. New-ownership
  validation correctly rejected borrowed reuse; invalid media preserved the expected
  provider failure. Same-executable inventory remained **5/5 unchanged**.
- Root Swift: **46 tests passed**, three suites; release build passed. Initial Swift
  builds caught an async short-circuit autoclosure and throwing `#require` inputs;
  these compile errors were corrected, not counted as passing checks.

The reviewer identified two mocked medium cases: a confirmed alias/absent selector
could claim verified success, and cleanup could miss an extra reservation introduced
during release. Both were corrected with refusal before mutation and full post-release
extra-state reporting, preserving primary failures and retaining unknown entries.
Added tests exercise installed→absent transitions during release and reservation,
no installation-request creation and owned cleanup following offline refusal.
These are mocked failure scenarios, not reproduced Apple defects.
Reviewer closure independently passed **46 repository Swift tests** and **48
adapter mocked Python tests**, byte-matched the tested source/tests, and reported
no remaining medium/high findings in scope. Evidence:
`maintenance-closure-5bfersgk/closure-test.log` beneath the approved temporary root.
The reviewer made no real Speech calls or asset changes.

At this earlier safeguards-only checkpoint no confirmed native maintenance release
was executed; the later approved stopped result is recorded above. Cancellation shielding is
defensive hardening because Apple's cancelled-task behavior is undocumented, not
proof of a prior framework failure. Owned acquisition/release native validation
still needs separately approved exact-target recovery; do not resolve risk #19 on
mocks/borrowed runs. Asset retention/reversibility and abrupt-kill cleanup remain
unproven. No ledger, persistent worker/cache, daemon or automatic pruning was added.

Evidence under the approved temporary root: `stt-maintenance-{test,build,tts}.log`,
`stt-maintenance-native.json`, scratch source/binaries/caches in `stt-maintenance-*`.
Final native read-only/borrowed evidence is in `stt-maintenance-final-native.json`;
all five unconfirmed previews preserve state. SIGINT while inspect waits for the
gate returns130 without a mutation being admitted. Existing default text/JSON/SRT
fixtures also pass; no real release/newly-owned result is implied.
No artifacts/binaries were added to Git or installed over existing engines.

Phase 12 adds `scripts/smoke_core.py`. Run it with the **installed wrapper's
Python**, preferably from a fresh virtual environment with a wheel installed.
It uses only the standard library, checks package/version metadata and the
JSON CLI contracts, and installs a Python audit hook that rejects socket
connections, address resolution, and datagram sends. No cloud account,
exporter dependency, model, or optional scanner is needed.

## Build and install separately from the development environment

From the repository root, after installing the development/build tools:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pip install build 'setuptools>=77' wheel
WORK=$(mktemp -d "${TMPDIR:-/tmp}/mac-speech-verification.XXXXXX")
.venv/bin/python -m build --outdir "$WORK/dist"
python3 -m venv "$WORK/clean"
"$WORK/clean/bin/python" -m pip install --no-index --no-deps "$WORK/dist/mac_speech-0.1.0-py3-none-any.whl"
"$WORK/clean/bin/python" scripts/smoke_core.py --require-noneditable
```

The default `python -m build` builds its wheel **from the sdist**. Prefer a
disposable reviewed source copy as described in [packaging](packaging.md),
so packaging build/egg-info outputs do not modify a shared checkout.
The build may fetch packaging tools unless already installed; **installation
of the built wheel and smoke execution do not fetch anything**. Adjust the
wheel filename when releasing a different version. The wheel packages only
the Python wrapper, not the native engines. If building wheel/sdist separately,
also build a wheel from the extracted sdist before a release; inspect both archives for
generated audio, models, credentials, or accidental development files.

`doctor` can return 1 for absent STT while the smoke test passes. This is
expected for a TTS-only/engine-free environment; its JSON and exit status
must agree. STT smoke coverage exercises native availability/missing-input
validation before a native process runs, **not successful real transcription**.
The reservation repair was outside historical Phase 12 scope. Current real
fixtures require explicit native opt-in and installed-asset preflight; they no
longer skip a provisioned transcription error. See the risk #19 evidence below.

## Apple STT risk #19 maintenance — 2026-10-12

**Partial, not fully resolved:** both source defects are repaired and real
reservation reuse works; existing full inventory blocks real newly-owned release
testing without separately authorized targeted recovery. Full design/API evidence:
[stt-reservation-repair.md](stt-reservation-repair.md).

| Command/check | Actual local outcome |
| --- | --- |
| Baseline `.venv/bin/python -m pytest tests/unit -q -rs` | **431 passed, 4 skipped**, all four from the incorrect unsupported-locale catch; not native passes |
| Repaired repository suite with native opt-in unset | STT-only snapshot: **480 passed, 4 explicit opt-in skips**; latest combined checkout: **483 passed, 4 skips** (8.98 s), including three external licensing tests; no generic locale-flakiness skip |
| Same suite with `MAC_SPEECH_TEST_APPLE_STT=1 MAC_SPEECH_TEST_APPLE_BINARY=<scratch release binary>` | STT-only snapshot: **484 passed, 0 skipped**; latest combined checkout: **487 passed, 0 skipped** (14.78 s), including three separately added licensing tests; four real fixtures explicitly use Apple |
| Opted-in `pytest tests/unit/test_stt_regression_fixtures.py -q -rs` | **4 passed**; text, JSON, segment SRT and word SRT |
| `.venv/bin/python -m ruff check python/mac_speech` and scoped affected-test Ruff | Passed |
| `.venv/bin/python -m mypy` | Passed, **18 source files** (existing scope) |
| `swift build --configuration release` with isolated scratch/cache/manifest-cache none | Passed; Swift 6.4/macOS 27.0.1 arm64; existing CLT linker-path warnings |
| `swift test` with isolated scratch/cache | **26 tests passed**, two suites; reservation ownership/error/cancellation, analyzer/results lifetime seam, delayed-stop race, installation mutation/error classification and stalled-output/broken/full-diagnostic cleanup |
| `RUNNER_TEMP=<approved temporary root> bash scripts/ci_swift.sh` | **48 TTS tests passed**, release build passed; independent package unchanged |
| `python3 -m py_compile whisper-py-convert.py` | Passed; legacy file unchanged |

Root test attempts first encountered CLT's absent XCTest, then the known
TestingMacros plugin issue. Tests use Swift Testing; a private-cache retry
explicitly loads the installed toolchain plugin with
`-Xswiftc -load-plugin-library -Xswiftc <selected-toolchain>/lib/swift/host/plugins/testing/libTestingMacros.dylib`.
One real concurrent gate test caught transient directory permissions from
Foundation creation; atomic `mkdir(0700)` fixed it and final tests pass.
The first TTS helper attempt timed out at 120 s; the longer-timeout complete
helper passed. No shared/global caches were deleted, and failures are not counted
as passing test runs.
A diagnostic flags assertion initially compared all flags from before pipe
filling; Darwin reports an additional internal bit after writing. It now checks
restoration of the configurable `O_NONBLOCK` bit at the diagnostic boundary.

Native scratch executable checks (same binary for before/after inventory):

- **Seven separate** synthetic en-US recordings: valid nonempty word JSON with
  expected words, all passed; more than five recordings are not a quota breach.
- Sequential text switching among installed en-AU, en-CA, en-GB, en-IN, en-US:
  **five passed**, no download, unchanged reservations after every call.
- Invalid media: expected provider failure `AVFoundationErrorDomain/-11800`,
  primary error retained, unchanged borrowed inventory.
- Two concurrent same-locale processes: **both passed** under cooperating gate.
- Closed stdout consumer: exit **1**, `[output_failed]` rather than SIGPIPE
  termination; unchanged reservations. Initial throwing-write evidence used
  `NSCocoaErrorDomain/512`; final nonblocking writer reports `NSPOSIXErrorDomain/32`.
- Stalled stdout with **65,536 bytes** buffered and reader kept open/unread:
  SIGTERM exited **130** before draining the pipe; unchanged borrowed inventory.
  Cancellation can leave partial stdout bytes; consumers must check exit status.
- Closed stderr during invalid-media failure: exit **1**, no SIGABRT, unchanged
  borrowed inventory. Owned mock cleanup also survives a broken diagnostic pipe.
- SIGINT while gate waiting and SIGTERM during long synthetic native media:
  both exit **130**, no partial successful output, unchanged reservations.
- Unsupported read-only locale diagnostic contains `supported_locale: null`,
  `installed: false`, rather than malformed/missing-field JSON.

Read-only inventory was already full at **5/5**, with
`en_AU,en_CA,en_GB,en_IN,en_US`. All these real lifetime checks reuse **borrowed**
entries, which are deliberately not released. Newly-owned acquisition/release
after success/failure is mock-verified only and remains a native validation gate.
No old reservations were evicted. A separately compiled probe cannot be assumed
to recover the executable's identity. SIGKILL/power loss (and existing wrapper
kill-on-timeout behavior) bypass cooperative native cleanup. No recovery,
download, binary rename/re-sign, commit/push or unrelated TTS implementation ran.

Evidence under the approved temporary `opencode` root:
`stt-risk19-build-final.log`, `stt-risk19-test-final.log`,
`stt-risk19-tts-final.log`, `stt-risk19-real-5n3fbvkf/{before,after,results}.json`,
and `stt-risk19-signals-gkdr3snh/{results,review-fixes}.json`. OS-cleanable scratch files are
not Git artifacts/public-release evidence. Hosted Python CI does not establish
macOS 27 native STT coverage, and TTS CI does not inherit the STT platform floor.

Concurrent licensing work appeared during final inspection in `LICENSE`,
`docs/licensing.md`, `MANIFEST.in`, `pyproject.toml`, `README.md` and
`python/README.md`. These are not STT repair changes; they were preserved, not
reverted or included in this task's packaging/release validation. Consult their
current terms separately from historical missing-license snapshots below.
Later concurrent licensing edits include related docs and
`tests/unit/test_project_license.py` (three tests); these explain the combined
suite count increase and are not owned by this repair.

Independent review found unsafe broken-stderr writes, uncancellable blocked
stdout, a stop-task completion-boundary join race, and a silent installation
reservation-mutation gap. Rechecks confirmed their fixes. A further full-but-open
stderr repro prompted one bounded nonblocking diagnostic/help write (drop bytes
on backpressure), rather than a potentially blocking throwing write. Tests cover
delayed stop joining, stalled stdout owned cleanup and broken/full diagnostic
preservation. Live installation/newly-owned release remain blocked, not inferred
from these mocked fixes.
Final independent review rebuilt the snapshot, repeated its full-unread-stderr
`--help` probe **four times** (all exit0 without draining), and found no remaining
medium/high runtime issue in output/analyzer-stop cleanup. Its snapshot's stale
flag assertion was corrected as described above; main reran the final suite.
The reviewer then independently reran the complete corrected snapshot: **26
passed, exit0**, runtime/test sources byte-matched, **no remaining medium/high
findings in reviewed scope**. Closure log:
`risk19-rereview-6be30hbf/closure-test.log` beneath the approved temporary root.
That closure does not validate live newly-owned reservations or authorize recovery.

## Combined source commit checkpoint — 2026-10-12

After the maintenance evidence above, the user explicitly authorized committing
and pushing **all reviewed source/docs/tests, including concurrent licensing**,
on `main` without a PR to `manish96170/whisper-py-convert`. Generated binaries,
audio, models, credentials and caches are excluded. This is source publication,
not a package release or permission to remove existing reservations. The commit
transaction follows this documentation checkpoint; verify actual Git/remote state.

Fresh main checks: **483 Python passed/four explicit opt-in skips**, **487 passed/
zero skips with Apple opt-in**, **26 root STT Swift tests passed**, STT release
build passed, Ruff/mypy (18 files)/legacy py_compile passed. The independent TTS
helper again passed **48 Swift tests and release build**, with its existing narrow
TestingMacros retry; no shared caches were removed. This remains separate from
native STT coverage. Six simultaneous direct
Apple calls all completed successfully (**2.651 s** for this local sample), with
the same borrowed reservation inventory before/after. This validates cooperating
admission beyond five submitted requests, not newly-owned cleanup or FIFO order.

The separate combined reviewer found no blocking runtime/packaging issues and
independently verified: **483 passed/four skips** in the checkout, **472 passed/
15 expected skips** in an extracted sdist (11 repository-only installer checks,
four native fixtures), offline runtime license inventory exit0, affected-test
lint, offline disposable wheel-from-sdist build with installed build1.6.1/
setuptools84.0.0, exact PEP639 expression and byte-identical license inclusion,
all **30 Python modules byte-matched**, Python-only wheel boundaries, and fresh
`--no-index --no-deps` install/pip check/engine-free socket-denied smoke. No speech
asset changes, shared-cache purges or network dependency/model downloads occurred.
This verifies license engineering/inclusion, not legal enforceability or rights
in every contribution. Active missing-license/authorization statements and build
tool examples were reconciled; historical phase snapshots remain unchanged.
Reviewer closure approved those doc-only corrections with no new blocker and
confirmed 64 runtime/test/license/packaging files byte-matched its tested snapshot.
Retained evidence is in `combined-precommit-package-__64sgsn/` (build log,
extracted package, clean install and artifacts) beneath the approved temporary
root. Those artifacts predate the final documentation corrections and are not
published/final release artifacts.

Commit-preparation native evidence is under the approved temporary root:
`stt-risk19-precommit-{test,build,tts}.log` and
`stt-risk19-precommit-concurrent.json`. Existing inventory remains full5/5;
real newly-owned acquisition/release and approved targeted recovery remain open.

## Network-denied native TTS on macOS

Build/install TTS with `./install.sh tts`, using a compatible Swift toolchain,
then run:

```sh
sandbox-exec -p '(version 1) (allow default) (deny network*)' \
  "$WORK/clean/bin/python" scripts/smoke_core.py --require-noneditable \
  --native-tts --tts-binary "$HOME/.local/share/mac-speech/mac-speech-tts"
```

Use the actual install path if XDG paths differ. The sandbox denies network
operations in the test **and its subprocesses**, while allowing local Apple
speech services and filesystem access. `sandbox-exec` is a macOS-specific,
deprecated testing utility, not a production dependency or a portable
security boundary. When it is unavailable, the Python audit guard alone
does **not** establish native-child network denial; report that limitation
rather than claiming a complete offline test.

The native smoke selects a currently enumerated ordinary (non-Personal)
voice, synthesizes a WAV in a temporary directory, validates actual audio
frames, checks the opt-in manifest avoids full source text, and verifies a
second invocation refuses to overwrite the artifact. It does not play audio,
change system voices, invoke real STT, export files, or request permissions.
Temporary artifacts are removed by the test, never user artifacts.

This is evidence for already-installed local voices/assets, not a claim that
first-time Apple voice/locale provisioning can work without a download.

## Maintenance checks

```sh
.venv/bin/python -m pytest tests/unit -q
.venv/bin/python -m ruff check python/mac_speech
.venv/bin/python -m ruff check --isolated --select E4,E7,E9,F \
  scripts/audit_dependencies.py scripts/smoke_core.py examples/narration_workflow.py \
  tests/unit/test_dependency_audit.py tests/unit/test_smoke_core.py \
  tests/unit/test_narration_example.py tests/unit/test_installation_lifecycle.py \
  tests/unit/test_file_io.py tests/unit/test_workflow_safety.py
.venv/bin/python -m mypy
bash scripts/ci_swift.sh
python3 -m py_compile whisper-py-convert.py
```

See `docs/ci.md` for the exact automated lint/type scope and isolated Swift
cache runner. Never delete shared global Swift caches as routine CI cleanup.
See `docs/releasing.md` for a release gate; local checks do not prove a hosted
CI run or code-signing/notarization succeeded.

## Independently verified Phase 12 local evidence (2026-10-11)

| Check | Result / boundary |
| --- | --- |
| Repository Python 3.11.3 suite | **322 passed, 4 native STT skips** for risk #19; not successful real transcription |
| Mocked source tests on 3.12.5 / 3.13.7 / 3.14.8 | **322 passed each**; existing pure-Python pytest tooling reused via `PYTHONPATH`, not fresh installs |
| Extracted sdist, importing its extracted package | **311 passed, 15 skipped**: 11 repository-only installer simulations and 4 STT fixtures |
| Package/helper Ruff and strict mypy | Pass; mypy scope is **16 files**, not the entire package |
| Isolated `scripts/ci_swift.sh` | **39 Swift tests passed and release build succeeded**; existing CLT/Testing/Sendable warnings remain |
| Clean non-editable wheel and real TTS-only install, Python 3.11.3 | Engine-free and native WAV/manifest/overwrite smoke passed with credential environment stripped, Python socket denial, and macOS sandbox network denial |
| Focused real uninstall/restore | Temporary HOME/XDG/venv native binary and wheel uninstall/restore passed; unrelated artifacts and legacy files retained |

Base Python dependencies are empty and both Swift manifests have no external
package dependencies. Offline runtime assumes installed Apple assets/tooling.
Local Python 3.9/3.10, older TTS OS/Intel execution and live
remote uploads/posts remain unverified. The committed Phase 12 hosted run
`38117411339` later passed Python 3.9–3.14/quality/clean-wheel jobs;
native CI remained intentionally skipped/manual. Project
license remains unresolved (`audit_dependencies.py --group runtime --check`
intentionally exits 1), so no public packaged release is authorized by these
checks. Full commands/artifact snapshots are in [SESSION_HANDOFF.md](SESSION_HANDOFF.md).

## Phase 13A local verification (2026-10-11)

This evidence is for uncommitted output-safety hardening after `cdd74dd`,
not an additional hosted-CI result or a public release:

| Check | Result / boundary |
| --- | --- |
| Repository Python 3.11.3 | **389 passed, 4 known native STT skips** |
| Local 3.12.5 / 3.13.7 / 3.14.8 mocked source suites | **389 passed each**, reused pure-Python pytest tooling/PYTHONPATH |
| Package/safety Ruff; scoped strict mypy | Pass; **17 source files** strictly checked |
| Complete isolated native helper | **48 tests passed, release build succeeded, exit 0** with a sufficient timeout |
| Extracted sdist selecting extracted modules | **378 passed, 15 expected skips** |
| Clean wheel and updated-native network-denied TTS | `--no-index --no-deps`, `pip check`, engine-free and real TTS smoke pass |
| Real TTS-only workflow | Private audio/checkpoint, owned marker cleanup and unchanged-name refusal pass |
| Independent review/rechecks | Cancellation/acquisition, checkpoint ownership, private staging and failed-warning findings resolved |

See [the hardening scope/benchmark](phase13-hardening.md) and current handoff
for migration rules, claim recovery, source/binary pairing and exact local
artifact evidence. No protected legacy STT repair or new runtime dependency
was included.

## Phase 13B local verification (2026-10-11)

Uncommitted batch code after the pushed `56cb3bb` baseline has independent
local evidence, not an additional hosted-CI result:

| Check | Result / boundary |
| --- | --- |
| Python 3.11.3 repository | **431 passed, 4 existing native STT skips** |
| 3.12.5 / 3.13.7 / 3.14.8 source suites | **431 passed each**, existing pytest/PYTHONPATH tooling |
| New batch/cancellation regressions | **42 tests**; actual thread-start and delayed-reader/backpressure cases |
| Ruff / scoped strict mypy | Pass, **18 source targets** |
| Native enum/regressions | **48 Swift tests, release build, exit 0** with narrow known plugin retry |
| Extracted sdist | **420 passed, 15 expected skips** |
| Clean wheel real TTS-only batch | Local no-index/no-deps install, pip check, valid ordered WAV/checkpoints, credential-stripped/network-denied pass |
| Review | Three startup/transport/validation findings fixed and independently rechecked |

See [batch usage/trust/performance](batch-synthesis.md) for the measured
three-scene observation and migration/cancellation limits. No STT/model/cloud
operation is implicit, and protected legacy code remains unchanged.
