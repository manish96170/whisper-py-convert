# Packaging, source trust, and macOS signing

**Decision:** [ADR-002](decisions/ADR-002-packaging-and-distribution.md).
Build native engines from reviewed source; package the Python wrapper
separately as a wheel and sdist. These instructions describe local builds
and release preparation, **not an existing PyPI publication or hosted
binary release**.

## Project license and remaining release gates

The maintainer selected a **custom proprietary personal-use, non-commercial,
no-derivatives license** on 2026-10-12. [LICENSE](../LICENSE) supplies the
terms; [ADR-003](decisions/ADR-003-project-license.md) records the decision.
This is source-available, **not OSI-approved open source**. Read the
[licensing guidance](licensing.md) before installation/distribution.

PEP 639 metadata uses the custom identifier
`LicenseRef-Mac-Speech-Personal-NonCommercial-NoDerivatives` and
`license-files = ["LICENSE"]`; setuptools **77+** is required to build it.
Inspect the actual license text/metadata in both wheel and sdist. No open-source
classifier, invented copyright attribution/year, legal entity or jurisdiction
is added. Unchanged-source compilation for permitted personal use is allowed;
licensee modification, commercial use and redistribution are not granted.

This resolves the **missing-license selection** blocker only. It does not
create a public release, clear third-party obligations, establish rights in
every contribution, or replace qualified legal review of enforceability.

Optional dependency licenses, any future model/voice licenses, and Apple's
SDK/system-voice terms require their own review. No Apple voices or models
are redistributed in these artifacts. See [the risk register](risk-register.md)
and [exporter boundaries](exporters.md).

## Artifact boundaries

| Artifact | Contains / purpose | Does not provide |
| --- | --- | --- |
| `mac_speech-<version>-py3-none-any.whl` | Python modules, console entry point, package metadata | Native engines, legacy STT dispatcher, voices/models, Swift compilation |
| `mac_speech-<version>.tar.gz` (Python sdist) | Python source, packaging files, unit tests and their Python example/smoke helpers, package README, packaging decision/docs; enough to rebuild the wheel | `install.sh`, `whisper-py-convert.py`, either Swift package, Windows helper; not a full repository archive |
| Full repository checkout or separately verified source archive | Installer, legacy dispatcher, both Swift manifests and source trees, repository docs/examples | Prebuilt native executables or a promise of published release assets |
| Native executables built locally | `mac-speech-tts` and/or `whisper-py-convert-apple` for the build platform | A Python CLI installation, Apple voice assets, Developer ID identity/notarization |

`MANIFEST.in` enforces the Python sdist boundary. There is deliberately no
native build hook in `pyproject.toml`. The wheel's `any` tag means its
Python code has no native extension; it does not mean macOS speech works
on Linux/Windows. Import/help/diagnostics can run without installed engines.
STT text/SRT/WebVTT and non-Apple fallback paths can need the installed
legacy dispatcher in addition to a native executable.

Use a **full repository checkout** for `./install.sh [tts|stt|all]`, followed
by a separate Python install (`python -m pip install .` for a regular
installation, or `python -m pip install -e '.[dev]'` for development).
The default install paths are `~/.local/share/mac-speech/mac-speech-tts`,
`~/.local/share/whisper-py-convert/` for the STT script/binary, and
`~/.local/bin/whisper-py-convert` for the legacy command. Even `tts` mode
currently copies/symlinks the legacy dispatcher; it does not build Apple
STT. `install.sh` does not install the `mac-speech` Python entry point.
See [installation](installation.md) for modes, XDG overrides, upgrade,
uninstall, and rollback. Check diagnostics after installation: build
failure can produce a warning rather than a failing installer exit code.

## Build requirements versus runtime support

| Component | Build/install requirement | Runtime floor / evidence |
| --- | --- | --- |
| Python wrapper | Python 3.9+, setuptools backend when building from source; no Swift for wheel installation | Python 3.9+; native capabilities remain platform-specific |
| Native TTS | Both current manifests declare Swift tools **6.4**; suitable Apple SDK and host for that toolchain | Deployment target **macOS 13+**; Personal Voice probes use macOS 14+ availability guards |
| Apple STT | Swift **6.4+** and SDK supporting the macOS 27 APIs used by the root package | **macOS 27+** |

Swift 6.4 is a **source-build requirement**, not the TTS runtime OS floor.
The chosen Swift toolchain itself may require a newer host OS than macOS
13; check its host requirements. A deployment target alone does not prove
successful execution on that minimum OS. Native verification is currently
macOS 27.0.1/arm64 (M1 Pro); macOS 13/14 TTS and Intel are not runtime-tested.
No universal native binary is promised. See [platform support](platform-support.md).

After toolchains, Python build/runtime dependencies, and the required Apple
voices/speech assets are present, native core use needs no cloud credentials
or paid API. Initial tool/dependency or OS asset acquisition can need network.
Use an installed voice and an explicitly selected Apple STT engine for
offline checks; the preserved legacy `auto`/`faster-whisper` path can install
dependencies/download a model on first use. Do not trigger that fallback as
a packaging smoke test. No neural model is bundled or downloaded here.

## Establish trust before building

1. Get source from the expected repository:
   `https://github.com/manish96170/whisper-py-convert`. Do not pipe a remote
   installer directly into a shell. Review `install.sh`, both
   `Package.swift` files, and relevant Python/native changes first.
2. Obtain a **full commit ID through a source you trust**, not just from the
   same untrusted archive. Branch names and unsigned/movable tags are not
   immutable trust anchors. Use a separate clean checkout for a pinned
   revision; do not reset a working tree containing your changes.
3. Before executing code, compare the full revision and inspect changes:

   ```sh
   git remote get-url origin
   git rev-parse HEAD
   git status --short
   git diff HEAD -- install.sh Package.swift engines/tts-swift python pyproject.toml
   ```

   A clean status plus a matching expected commit establishes that you are
   building the reviewed tree, not that its author is trustworthy. Untracked
   files also deserve inspection. Phase 12's verification artifacts were
   built from then-uncommitted work; a later commit does not retroactively
   make those builds an authenticated release of `HEAD`.
4. If an authorized release later uses signed tags/commits, verify with
   `git verify-tag <tag>` or `git verify-commit <commit>`, and independently
   verify the signer's key/identity. These commands do not create signatures
   or make an unsigned existing revision trusted. No signed release is
   claimed by this policy.
5. Record full source revision (and dirty state), toolchain/SDK versions,
   architecture, and output hashes. Use the same reviewed revision for
   wrapper and native engines initially; do not infer compatibility merely
   from matching package version strings. See [protocol](protocol.md).

For a downloaded archive or wheel, compare its SHA-256 against an expected
value obtained through a trusted channel **before installing or running it**:

```sh
shasum -a 256 /path/to/artifact
```

A `SHA256SUMS` file distributed beside an artifact detects corruption, but
an attacker who can replace both defeats that check. It is not independent
publisher authentication. A digest you generate after a local build is
useful provenance, not proof of source safety or byte-for-byte reproducibility.
Python wheel `RECORD` hashes have the same authenticity limitation. Pin
Python build dependencies separately when repeatable release tooling is
required; metadata minimum versions are not lockfiles.

### Full repository source archives

A native-source archive is a separate future artifact. After review,
license resolution, and a human-controlled commit, a maintainer can create
one from an explicit committed revision (no automatic commit):

```sh
git archive --format=tar.gz --prefix=mac-speech-source/ \
  --output=/path/to/output/mac-speech-source.tar.gz <full-commit-id>
```

`git archive` includes **only tracked files at that revision**; it cannot
capture untracked additions or later working-tree edits. Inspect the archive for
`install.sh`, `whisper-py-convert.py`, root `Package.swift`/`Sources/`,
`engines/tts-swift/Package.swift`/`Sources/`, Python package, docs, and the
authorized license. Exclude generated `.build`, venvs, credentials,
private speech data, and models through source review/archive policy. Record
the revision, compute its SHA-256, and publish it only after the release
gates below. Do not substitute the Python sdist for this artifact.

## Local wheel/sdist verification

Build in a **disposable copy** of the source to keep `build/`, `dist/`,
egg-info, and native `.build` out of a shared checkout. Copy the intended
Python source, root `LICENSE`, `pyproject.toml`, `MANIFEST.in`, package README, referenced
readme file, included docs (including `docs/sbom.md`), unit tests,
`examples/narration_workflow.py`, `examples/batch_scenes.json`,
`docs/batch-synthesis.md`, `scripts/smoke_core.py`, and
`scripts/audit_dependencies.py`; do not copy venvs, build outputs, credentials,
audio, or models. In that copy, with a dedicated build venv:

```sh
python -m pip install build 'setuptools>=77' wheel
python -m build --no-isolation --outdir /path/to/output /path/to/source-copy
```

Here `python` is the build venv's interpreter. `--no-isolation` is suitable
when backend requirements are already installed in that dedicated venv;
the default isolated build is also valid but can fetch backend dependencies.
Installing build tooling can require network; building with preinstalled
tooling and this dependency-free base package need not. The default
`python -m build` produces an sdist and **builds the wheel from that sdist**,
checking the archive has enough source. It does not compile Swift.

Inspect both archives and their `PKG-INFO`/`METADATA`:

- Name/version and `Requires-Python` match `pyproject.toml` and the package.
- The `mac-speech` entry point targets `mac_speech.cli:main`.
- Base runtime requirements are empty; any extra requirements are
  explicitly conditional. Optional Google credentials are not needed.
- The project description/README describes missing-engine behavior,
  native build/runtime floors, and the selected custom proprietary terms.
  Both archives include the real `LICENSE`; a metadata presence check is
  not legal/license-compatibility clearance or publication authorization.
- Native binaries/source trees, models, build outputs, credentials, local
  paths, and private data are absent. Unit tests are in the sdist, not
  installed as wrapper packages in the wheel.

Install the wheel into a second empty venv from a directory **outside the
checkout** to avoid importing source accidentally:

```sh
python -m pip install --no-index --no-deps /path/to/output/mac_speech-<version>-py3-none-any.whl
mac-speech version --json
mac-speech --help
mac-speech capabilities --json
mac-speech doctor --json
```

Activate that second venv first (or use its absolute executable paths).
`doctor`/`capabilities` report what is actually installed; missing engines
are expected on a Python-only environment, not a broken wheel. They can
discover user-installed native engines even outside the source tree. Run
unit tests separately from the sdist with preinstalled test tooling;
repository-only installer lifecycle tests skip because native installer
sources are deliberately absent. Run native TTS smoke tests only with an
explicitly installed local engine and voice. See [installation](installation.md)
for end-to-end checks.

## macOS code signing, quarantine, and notarization

These are different controls, not synonyms:

- **Local source build:** this installer runs SwiftPM and copies output.
  It does not use Developer ID certificates or submit artifacts to Apple's
  notary service. Some compiler/linker outputs carry an **ad-hoc** code
  signature (common on Apple Silicon); that does not authenticate a
  developer. Do not equate "no Developer ID" with "cannot execute".
- **Downloaded/quarantined executable:** browsers and archive tools can
  attach `com.apple.quarantine`. Gatekeeper can block quarantined unsigned
  or unnotarized builds, depending on the artifact and macOS policy. A
  local compiler output normally has a different quarantine/provenance
  context, although working from downloaded quarantined source can still
  need scrutiny. Neither path is a guarantee of safety or execution.
- **Developer ID signing:** a certificate-backed signature identifies the
  publisher and protects signed code against modification. It requires a
  properly authorized Apple Developer account and secure signing identity;
  an ad-hoc signature or a locally trusted development certificate is not
  the same distribution identity.
- **Notarization:** an additional Apple service check for a submitted,
  appropriately signed release artifact. It requires account credentials
  and network for the maintainer. Acceptance does not guarantee speech
  permissions, Personal Voice authorization, asset availability, or lack
  of all malicious behavior. Users do not need the publisher's signing
  credentials to run a released artifact.

For an unfamiliar binary, inspect without executing it:

```sh
file /path/to/binary
xattr -l /path/to/binary
codesign --display --verbose=4 /path/to/binary
codesign --verify --strict --verbose=2 /path/to/binary
```

An unsigned binary can make `codesign` fail; a successful verification
alone does not establish a trusted Developer ID or notarization. Check the
displayed identity/team against an independently known publisher. For an
appropriate future distributed app/package, assess Gatekeeper using
`spctl --assess --type execute --verbose=4 /path/to/app` (or `--type install`
for an installer package); bare command-line executables may not behave
like application bundles under that assessment.

If macOS blocks a download, do not disable Gatekeeper globally or blindly
strip quarantine attributes. Verify source/publisher/hash, prefer building
reviewed source yourself, and follow Apple's current per-item security UI
guidance only when you deliberately trust that item. A block can signal a
real security problem, not an installation step to bypass automatically.

### If prebuilt native releases are justified later

The maintainer must design and test a separate pipeline, not mark today's
local binaries as signed releases:

1. Choose artifacts/architectures and OS matrix; establish stable bundle
   identity/permission descriptions where required. Design minimal
   entitlements and hardened-runtime signing as applicable. Do not invent
   entitlements to work around speech-asset failures.
2. Sign native code with a controlled Developer ID Application identity;
   sign an installer package with Developer ID Installer if using `.pkg`.
   Protect certificates/private keys and notary credentials in the CI secret
   store, never source or logs. No real credentials are needed for today's
   source-build workflow or tests.
3. Submit the correct supported container (e.g. ZIP, DMG, or PKG) via
   `xcrun notarytool`, wait for acceptance, and inspect the service log.
   Confirm the current Apple requirements for the chosen artifact before
   wiring CI. A bare Mach-O is not a submission container.
4. Staple/validate tickets on **supported** artifacts (app bundle, DMG,
   installer package). Do not promise that a ticket can be stapled to a
   bare CLI executable or ZIP; bare-tool distribution needs a specifically
   tested container/install/offline strategy.
5. Test the final, downloaded, quarantined artifact on a clean supported
   Mac, including signature/Gatekeeper assessment and offline execution.
   Test speech permissions/assets separately. Hash the **final** artifacts
   after signing/stapling and record provenance.

Apple references: [Gatekeeper and runtime protection](https://support.apple.com/guide/security/gatekeeper-and-runtime-protection-sec5599b66df/web),
[notarizing macOS software](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution),
and [customizing the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow).
These are reference links, not claims of completed signing/notarization.

## Public-release gates (not completed by a local build)

- Authorized project license text/metadata, dependency/license review, and
  model exclusion confirmed in final artifacts.
- Reviewed committed source revision, consistent version metadata, native
  compatibility checks, changelog, rollback instructions, and clean-install
  tests recorded; never label a dirty checkout as the tagged release.
- Wheel rebuilt from sdist, installed outside source, and offline core
  smoke-tested without optional integrations/credentials.
- Full source archive independently inspected if provided; native binary
  assets offered only after their own signing/trust/platform review.
- Artifact hashes and provenance generated from final outputs; maintainers
  decide a trusted publication/signature channel and verify package-name
  availability before any PyPI publication.

No upload, release creation, model acquisition, signing-account setup, or
automatic Git commit is part of this packaging decision.
