# Clean-install and offline core verification

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
.venv/bin/python -m pip install build 'setuptools>=68' wheel
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
validation before a native process runs, **not successful real transcription**. The existing Apple
locale-reservation defect is out of Phase 12 scope; unit tests mock native
output, and the four real STT fixtures can skip for that environmental error.

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
