# Dependency and license inventory

This is a **proportionate direct-dependency inventory**, not a resolved
transitive release SBOM, vulnerability scan, legal opinion, or assertion that
all permitted future versions have the same license. Reviewed 2026-10-11
against the actual `pyproject.toml` and both Swift manifests. Source
declarations are ranges/pins; the license examples below identify specific
upstream releases, **not versions resolved for a mac-speech release**.

## Project and runtime boundary

- `mac-speech` source metadata declares version `0.1.0`, Python `>=3.9`, and
  **`dependencies = []`**. The base wrapper requires only the Python standard
  library; there are no mandatory third-party Python runtime packages.
- Root `Package.swift` (`whisper-py-convert-apple`) and
  `engines/tts-swift/Package.swift` (`mac-speech-tts`) have **no external Swift
  package dependencies**. TTS target-to-target dependencies are internal, not
  third-party packages. The engines use Apple's SDK/system frameworks, not
  bundled neural models or redistributed Apple voices. Python, the Swift
  toolchain, macOS/frameworks and downloaded system voices have their own
  terms; the absence of package dependencies is not a claim that those terms
  do not apply.
- **Project license selected on 2026-10-12:** custom proprietary personal-use,
  non-commercial, no-derivatives terms in [LICENSE](../LICENSE), identified
  by `LicenseRef-Mac-Speech-Personal-NonCommercial-NoDerivatives`. It is not
  OSI-approved open source and does not relicense third-party components.
  See [licensing](licensing.md) and [ADR-003](decisions/ADR-003-project-license.md).
- `setuptools` is a **build/development dependency**, not a runtime dependency.
  The optional `tui` extra adds pinned `textual==8.2.8`, checked from
  [PyPI metadata](https://pypi.org/pypi/textual/8.2.8/json): Python>=3.9,<4, MIT.
  Its Rich dependency has separate MIT terms. No UI requirement is in the base
  runtime; a resolved extra-environment inventory remains distinct from this direct
  declaration audit. No vulnerability or legal-compatibility clearance is implied.
  An isolated wheel build resolves `[build-system].requires` separately.
  `pip`, `wheel`, `build`, test runners and audit tools used by a release job
  belong in its separately recorded build/tool environment, not in the base
  wrapper's runtime inventory.

## Declared direct third-party Python dependencies

License evidence was retrieved from public PyPI metadata without installing
Google packages or authenticating to any service. SPDX-style names in the
table are human summaries of that evidence; legacy/classifier fields are
not silently converted to an SPDX expression by the script.

| Scope | Exact source declaration | License evidence for the reviewed example release | Version-specific evidence |
| --- | --- | --- | --- |
| Build/development | `setuptools>=77` | MIT; `License-Expression: MIT` in **84.0.0** | [PyPI JSON](https://pypi.org/pypi/setuptools/84.0.0/json), [source](https://github.com/pypa/setuptools) |
| `dev` only: tests | `pytest>=7.4` | MIT; `License-Expression: MIT` in **9.1.1** | [PyPI JSON](https://pypi.org/pypi/pytest/9.1.1/json), [source](https://github.com/pytest-dev/pytest) |
| `dev` only: lint | `ruff==0.14.14` | MIT license classifier in **0.14.14**; no SPDX-expression field reported | [PyPI JSON](https://pypi.org/pypi/ruff/0.14.14/json), [source](https://github.com/astral-sh/ruff) |
| `dev` only: type checks | `mypy==1.15.0` | `License: MIT` and MIT classifier in **1.15.0** | [PyPI JSON](https://pypi.org/pypi/mypy/1.15.0/json), [source](https://github.com/python/mypy) |
| Optional `gdrive` runtime | `google-api-python-client>=2.0` | Apache-2.0; legacy `License: Apache 2.0` and Apache classifier in **2.201.0** | [PyPI JSON](https://pypi.org/pypi/google-api-python-client/2.201.0/json), [source](https://github.com/googleapis/google-api-python-client/) |
| Optional `gdrive` runtime | `google-auth-oauthlib>=1.0` | Apache-2.0; legacy `License: Apache 2.0` and Apache classifier in **1.5.0** | [PyPI JSON](https://pypi.org/pypi/google-auth-oauthlib/1.5.0/json), [source](https://github.com/googleapis/google-cloud-python/tree/main/packages/google-auth-oauthlib) |
| Optional `gdrive` runtime | `google-auth-httplib2>=0.1` | Apache-2.0; legacy `License: Apache 2.0` and Apache classifier in **0.4.4** | [PyPI JSON](https://pypi.org/pypi/google-auth-httplib2/0.4.4/json), [source](https://github.com/googleapis/google-cloud-python/tree/main/packages/google-auth-httplib2) |

`>=` is not a lock. Even the pinned dev tools have platform/Python-dependent
transitive dependencies. The range-example versions above require Python
`>=3.10`; they are not a promise that a Python 3.9 resolver will select them.
Resolve separately for each supported Python/platform and recheck that
selection's actual license texts, notices and embedded/bundled components
(including Rust crates in Ruff's executable). Do not treat top-level metadata
as a complete bundled-component audit. MIT/Apache labels alone do not waive
notice, attribution or other applicable redistribution obligations.

A concrete bundled-license exception was checked in the installed mypy
**1.15.0**: `mypy/typeshed/LICENSE` identifies the bundled **typeshed as
Apache-2.0**, despite mypy's top-level MIT metadata. Retain both applicable
notices if redistributing that development tool. This is not an exhaustive
audit of mypy's or Ruff's bundled components and adds no base runtime package.

### Optional external components, not Python package requirements

- S3 uses a separately installed/configured `aws` CLI, not `boto3`. Its
  version, installation channel and bundled license notices belong to the
  user's deployment inventory; there is no pinned CLI version in this
  package. This review does not resolve its bundled dependency graph.
- Slack invokes a separate `team-slack-bridge` checkout and Node tooling;
  neither is vendored or declared as a Python dependency. Record the bridge
  revision, its actual license and Node dependency lock/SBOM if distributing
  a combined deployment; this inventory grants no license for that project.
- Legacy faster-whisper/Windows backends, future Kokoro/Piper engines and
  model/voice downloads are **not dependencies of this base package**. Audit
  separately if enabled or bundled. Engine and model/voice licenses are
  distinct; no model was installed/downloaded for this review.

## Offline metadata scan

Run with Python **3.11+** for stdlib `tomllib`; this developer script does not
raise the wrapper's Python 3.9 runtime minimum. It reads source declarations
and the selected interpreter's installed distribution metadata:

```sh
.venv/bin/python scripts/audit_dependencies.py
.venv/bin/python scripts/audit_dependencies.py --group dev --group build --environment
.venv/bin/python scripts/audit_dependencies.py --group runtime --check
.venv/bin/python -m pytest -q tests/unit/test_dependency_audit.py
```

The default inventories every declared group, preserves requirement strings,
and reports missing installed distributions rather than importing optional
providers. `--environment` adds a **flat snapshot of all installed versions**,
including transitive packages and unrelated tools; it is not a dependency
graph or a clean release SBOM. Use a clean environment to avoid unrelated
packages. License evidence includes `License-Expression`, legacy `License`,
license classifiers, and declared/recorded license-file names. `UNKNOWN`,
`NONE`, `NOASSERTION` and generic `License :: OSI Approved` are not accepted
as identified license metadata. Text-file presence alone does not identify a
dependency's license. No packages are installed and no network request,
optional-service access, native invocation, model download or credential
lookup occurs.

Exit status is **0** for successful report generation, even with findings;
**1** with `--check` for incomplete selected dependency/project license
metadata; **2** for invalid input. Currently `--group runtime --check`
now passes with the selected project license and empty base dependencies.
Earlier snapshots failed for the then-unresolved project license. `--check`
is only a metadata-completeness gate, **not a
license-compatibility, version-satisfaction or vulnerability gate**. It does
not evaluate requirement ranges/markers, inspect source license text, validate
dependency license files on disk, discover native bundled libraries, or parse Swift
dependencies. The no-external-Swift finding above comes from manual manifest
inspection and must be repeated if either manifest changes.

Initial review snapshot (before the main session's build-tool setup): the
repository `.venv` used Python 3.11.3, pytest 9.1.1, Ruff 0.14.14 and mypy
1.15.0 were installed; all three Google extras were absent. Ambient setuptools
65.5.0 is below the declared build requirement and is **not** evidence of an
isolated-build resolution. Missing local metadata for optional extras is
expected; the table's Google license evidence is remote metadata, not a
claim of a local installation or successful live Drive export.

Later main-session integration installed setuptools **84.0.0**, build **1.6.1**
and wheel **0.48.0** in that same development venv to build the local wheel/sdist.
These are actual local build-tool versions, not a separately resolved public
release environment or new base runtime requirements. The clean-wheel smoke
venv installed only the wrapper, with no optional extras.

## Before a release: resolved inventory/SBOM and security review

Keep the above lightweight source inventory for maintenance. For any actual
release, after confirming the selected proprietary terms/legal authority
and remaining publication requirements:

1. Start from the intended commit and build wheel/sdist in an isolated build
   environment. Record commit, Python/Swift/Xcode/SDK/macOS versions, build
   requirements actually resolved, native build flags and artifact SHA-256
   hashes. Record build/dev tooling separately from runtime packages. Do not
   use the source ranges or an ambient venv as resolved-release evidence.
2. Create separate clean venvs for base and each distributed extra/combination
   on each supported Python/platform. Install the **built wheel**, not an
   editable checkout. A resolver can fetch package metadata/downloads at
   this explicit release-review stage; this is separate from offline core
   tests and does not require Google/AWS/Slack credentials.
3. Retain resolver/install evidence and exact versions. Example for a base
   venv (replace placeholders; repeat with `mac-speech[gdrive]` where needed):

   ```sh
   python3.11 -m venv /path/to/clean-release-venv
   /path/to/clean-release-venv/bin/python -m pip install --report /path/to/install-report.json /path/to/mac_speech-0.1.0-py3-none-any.whl
   /path/to/clean-release-venv/bin/python -m pip check
   /path/to/clean-release-venv/bin/python -m pip inspect > /path/to/pip-inspect.json
   /path/to/clean-release-venv/bin/python -m pip freeze --all > /path/to/resolved-versions.txt
   /path/to/clean-release-venv/bin/python scripts/audit_dependencies.py --group runtime --environment > /path/to/license-inventory.json
   ```

   Select `--group runtime --group gdrive` for the Google profile. This
   script still reads the checkout's declarations: use the **same release
   commit** as the wheel and compare the wheel's `METADATA`/`Requires-Dist`.
   `pip inspect` supplies dependency relationships/markers; install-report
   records fetched artifacts and available hashes. A freeze file alone
   is not a hash-locked resolver graph. Bootstrap pip/setuptools in these
   snapshots are tooling, not magically runtime dependencies. Review/redact
   private index URLs, local paths and other sensitive provenance before
   publishing reports; never publish credentials.
4. Check the **exact distributions'** license texts and notices, not only
   metadata. Retain required notices for what is actually shipped; investigate
   missing/conflicting metadata and embedded components. Include native
   executable hashes, their build provenance and system prerequisites.
   Review the project license and separate voice/model terms explicitly.
5. If a consumer needs machine-standard SBOMs, use a pinned, reviewed
   CycloneDX/SPDX generator in a **separate release-tool venv**, feed the
   resolved clean environment/graph, validate its schema, and attach the
   resulting runtime SBOM (plus separate build/tool inventory) to that
   release. Record generator version/options, target environment, component
   versions, hashes and license evidence. This document and the script's
   custom JSON are **not** claimed to be CycloneDX/SPDX documents.
6. Vulnerability review is a separate step. If appropriate, install a pinned,
   reviewed `pip-audit` in a disposable audit-tool venv and audit the
   resolved runtime/extra environments (for example its `--path` option
   targeting their site-packages, with `--format json --output ...`). Record
   tool version, advisory service, query date, findings and remediation or
   accepted-risk decisions. Consult that version's CLI help; retain tool
   inventory separately. Advisory lookups require networking, may disclose
   package names/versions and can fail; an unavailable advisory service is
   **not a clean scan**. Do not add this to the offline core test gate or
   install it as a runtime dependency. Python advisory scans also do not
   cover Apple's SDK, native/toolchain vulnerabilities or every bundled
   component.

**No advisory vulnerability scan was performed for this source inventory.**
The lack of mandatory Python packages reduces the base's third-party package
surface; it does not imply absence of vulnerabilities in project code,
optional dependencies, native binaries or operating-system components.
