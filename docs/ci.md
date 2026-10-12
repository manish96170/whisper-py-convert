# Continuous integration

`.github/workflows/ci.yml` checks the **new** `python/mac_speech` package
and the independent `engines/tts-swift` package. It does not build the root
STT Swift package, lint `whisper-py-convert.py`, or alter the Windows engine.

## Automatic Python checks

Pushes, pull requests, and manual dispatches run on hosted
`macos-15-intel`. The explicit Intel label avoids assuming older CPython
versions are available on the default hosted runner's architecture. These
are mocked wrapper tests, not proof of native-engine support on Intel Macs:

- **Runtime compatibility:** install the package and run mocked unit tests
  separately on Python **3.9, 3.10, 3.11, 3.12, 3.13, and 3.14**, including
  the declared `requires-python = ">=3.9"` floor. These are real interpreter
  jobs, not just a syntax check or a type check targeting Python 3.9.
  Future Python releases are not validated until added to the matrix.
- **Lint:** Ruff 0.14.14 on Python 3.11, targeting Python 3.9 syntax.
  `E4`, `E7`, `E9`, and `F` catch import, syntax, and Pyflakes correctness
  issues across `python/mac_speech`; this is not a formatting migration.
- **Types:** mypy 1.15.0 on Python 3.11, with Python 3.9 as its target and
   `strict = true` for the 18 files explicitly listed in `pyproject.toml`.
- **Installed CLI:** `mac-speech version` after the editable installation.
- **Clean install:** a separate job builds an sdist and a wheel from it,
  installs only that wheel with `--no-index --no-deps` in a fresh venv, and
  runs `scripts/smoke_core.py --require-noneditable` with Python networking
  denied. This job checks engine-free diagnostics/validation, not native TTS.
- **Explicit helper/safety lint:** an isolated correctness-lint command
  checks audit/smoke/narration/lifecycle, file/workflow and batch/cancellation tests, outside
  Ruff's package-only configured include list.
- **Offline inventory:** the quality job reports the empty base dependency
  surface and selected custom project license. It does not run `--check` or
  represent a public-release/vulnerability clearance; publication stays gated.

Ruff and mypy are pinned, **development-only** dependencies in `.[dev]`.
The base package still has **zero runtime dependencies**. Test jobs install
only the base package and pytest; they do not install Google Drive extras,
speech models, native engines, AWS tooling, or a Slack bridge. There are no
cloud secrets, credential setup steps, or live export calls.

The four real-native STT regression fixtures in
`tests/unit/test_stt_regression_fixtures.py` are deliberately excluded from
the CI unit-test command. They use `say` and an installed STT engine, are
not mocked unit tests, and can hit the documented Apple locale reservation
issue (risk #19). Run them locally when intentionally validating native STT.
All other tests under `tests/unit` are included, including optional-provider
tests with mocks. Dependency installation needs network access; the test
operations do not need network access. This is not an OS-level network
sandbox for subprocesses or Apple's services.

### Type-check boundary

The strict gate checks configuration, error/result models, logging helpers,
alignment/workflow orchestration, the STT adapter and its models/SRT/WebVTT
helpers, TTS result models, the native protocol/TTS process wrapper, and the
exporter interface/local-copy adapter, atomic file I/O and bounded batch module.
It checks annotated function bodies, requires complete function annotations,
checks return types, and rejects unparameterized generics and unused ignores.

`follow_imports = "silent"` lets mypy use imported type information without
reporting errors in modules outside this gate. This is **not whole-package
strict typing**. The CLI, capability/doctor discovery, JSON artifact loader,
TTS client, cloud-provider adapters, package
re-exports, and tests are not direct strict targets. Some dynamic JSON and
dataclass constructors in checked files still use explicit `Any`; strict
mode is not runtime schema validation. Expanding the boundary should be a
separate focused change, not a broad refactor hidden in CI setup.

Reproduce from the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m ruff check python/mac_speech
.venv/bin/python -m mypy
.venv/bin/python -m pytest tests/unit --ignore=tests/unit/test_stt_regression_fixtures.py -q

# Optional local integration fixtures, not part of hosted CI:
.venv/bin/python -m pytest tests/unit/test_stt_regression_fixtures.py -q
```

## Native Swift checks: opt-in, not a hosted-CI claim

The TTS manifest requires **Swift tools 6.4**. The workflow does **not**
assume a stock hosted macOS runner has that compiler, downgrade the manifest,
or silently skip a failed compiler check. Automatic push/PR Swift coverage
is **deferred** until a suitable hosted image or explicitly provisioned
toolchain is verified. A green automatic Python run therefore does **not**
mean native Swift checks ran.

To run them manually:

1. Provision a dedicated Apple Silicon macOS runner with labels
   `self-hosted`, `macOS`, `ARM64`, and `swift-6.4`. Select the intended
   **Swift 6.4.x** installation and its compatible macOS SDK using
   `DEVELOPER_DIR`/`TOOLCHAINS` as appropriate for that installation. Ensure
   `swift` on `PATH` and `xcrun --find swiftc` select the same toolchain.
   Both full Xcode and a working Command Line Tools installation are valid;
   Swift Testing must be available. Do not label an older compiler as 6.4.
   The helper prints the exact compiler build and fails unless its version
   is in the 6.4 release line (including patch releases).
2. Ensure at least one system voice is already installed: the Swift suite
   includes real voice enumeration and local synthesis. No voice/model
   download or Personal Voice authorization is performed by this workflow.
   Provisioning is a human action, not a CI side effect.
3. In GitHub Actions, select **CI → Run workflow**, choose a trusted,
   reviewed ref, and enable `swift_tests`. Without that input the Swift
   job is skipped; without the labeled runner it waits, not passes.

Only manually dispatched jobs use the self-hosted runner. Do not dispatch
untrusted PR refs. Prefer an ephemeral/dedicated runner without cloud
credentials or personal files, and restrict runner access in GitHub.
`contents: read` and checkout without persisted credentials limit the
workflow token; they do not protect a persistent machine from arbitrary
code in a ref a maintainer selects.

The same check works locally:

```sh
bash scripts/ci_swift.sh
```

### Module-cache handling (risk #17)

`scripts/ci_swift.sh` builds/tests **only** `engines/tts-swift`:

- A unique temporary workspace under `RUNNER_TEMP` (or local `TMPDIR`)
  holds separate debug/test and release scratch directories and SwiftPM
  cache directories. Manifest caching is disabled.
- If compilation emits the known missing **TestingMacros** plugin/macro
  implementation diagnostic, it retries **once** in a fresh scratch/cache
  directory using the same selected toolchain and default build system.
  When the selected compiler's `usr/lib/swift/host/plugins/testing/`
  directory contains `libTestingMacros.dylib`, the retry explicitly loads
  it with `-Xswiftc -load-plugin-library`. This addresses the observed
  CLT-only 6.4 omission of the installed plugin from the compiler's load
  list; it does not fetch or copy a plugin from another toolchain. If that
  file is absent, only the fresh-cache retry is used.
  It does not switch to `--build-system native`: on this CLT-only 6.4
  installation that build system cannot locate the `Testing` module.
- Ordinary compilation failures and failed test assertions are not
  retried. A failed retry fails CI; release builds are not retried.
- Cleanup removes only the workspace created by that invocation, never
  `engines/tts-swift/.build`, another session's build tree, or shared user
  module/manifest caches. No `~/Library/Caches` deletion is used.

There are no external Swift package dependencies. `--skip-update` also
prevents dependency updates (Swift 6.4 warns that this flag is deprecated).
Build/test operations do not require network access. Pre-installing a
toolchain is separate from runtime use of the offline speech core.

## Verification and limits

The Phase 13A source was later explicitly authorized and pushed as
`56cb3bb`; [run 38145240085](https://github.com/manish96170/whisper-py-convert/actions/runs/38145240085)
also completed successfully. This does **not** verify newer uncommitted
Phase 13B changes, including the 18th type target and batch/cancellation code.

The Phase 12 baseline was explicitly authorized, committed and pushed as
`cdd74dd`. [Run 38117411339](https://github.com/manish96170/whisper-py-convert/actions/runs/38117411339)
completed successfully: all six Python versions, quality and clean-wheel
jobs passed; the manual native job was intentionally skipped. This verifies
that committed baseline, **not subsequent uncommitted Phase 13A changes**.
Those changes must be separately authorized/committed/pushed before their
hosted workflow can run.
Configuration alone is not evidence that any hosted matrix job or
self-hosted job has run. Local evidence and the main session's independent
integration checks should be recorded separately; do not report Python 3.9
runtime compatibility as verified solely because mypy's target is 3.9.
The main session ran the final mocked suite on local Framework interpreters
3.12.5, 3.13.7, and 3.14.8: 322 passed on each. These source-based runs used
`PYTHONPATH=python:.venv/lib/python3.11/site-packages` to reuse the existing
pure-Python pytest tooling; they are not clean-venv installation evidence.
The independent 3.11.3 repository run was 322 passed/4 native STT skips, and
the clean-wheel/native offline checks used a separate 3.11.3 venv. Local
3.9/3.10 validation remains unverified locally; the hosted baseline matrix
does validate those runtimes. Current local Phase 13A results are recorded
separately in the plan/handoff.
The current scope does not establish Intel Mac support, the macOS 13 runtime
floor of native TTS, real cloud-provider uploads, or the existing native STT
engine's compatibility with older macOS releases.
