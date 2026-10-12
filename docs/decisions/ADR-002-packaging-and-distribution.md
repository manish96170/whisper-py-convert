# ADR-002: Python distributions and source-built native engines

**Status:** Accepted; original missing-license gate addressed by ADR-003
**Date:** 2026-10-11

**Licensing update (2026-10-12):** the maintainer selected the custom
proprietary license recorded in [ADR-003](ADR-003-project-license.md).
The discovery/context below records the original Phase 12 state. Current
terms are in [LICENSE](../../LICENSE); source availability is not OSI-open-source
licensing or permission for commercial/modification use. Other release gates
and third-party rights remain separate.

## Context

Phase 12 needs an installation and release policy without destabilizing the
preserved STT implementation. The repository has a standard-library-first
Python wrapper at `python/mac_speech/`, two independent SwiftPM packages,
and `install.sh [stt|tts|all]`. The installer builds native engines but does
not install the Python package. Both Swift manifests currently require
Swift tools 6.4; TTS targets macOS 13+, while Apple STT targets macOS 27+.
These runtime floors are not promises that Swift 6.4 can run on every older
macOS release.

Inspection found no project `LICENSE`, `LICENCE`, `COPYING`, or `NOTICE`
file, no license declaration in `pyproject.toml`, and no authoritative
license grant in the tracked source or available local Git history. A
public repository and the plan's open-source-first goal do not establish
redistribution terms. There is no basis for inventing a license.

## Decision

1. **Distribute the wrapper as a normal Python wheel and sdist**, named
   `mac-speech` (import `mac_speech`, command `mac-speech`). The wheel is
   pure Python (`py3-none-any`), not evidence of cross-platform native
   speech support. Neither artifact bundles native binaries, Apple voices,
   neural models, credentials, or native build hooks. Base runtime Python
   dependencies remain empty; Google Drive stays an explicit extra.
2. **Obtain native engines by building reviewed repository source** with
   `./install.sh tts`, `./install.sh stt`, or `./install.sh all`. Keep these
   builds independent and preserve the legacy STT files. No Homebrew
   formula, binary-download installer, Developer ID release pipeline, or
   bundled application is introduced now.
3. **Treat a Python sdist and a repository source archive as different
   artifacts.** The Python sdist rebuilds the Python wheel; it is not a
   native-engine SDK or a replacement for a checkout. `MANIFEST.in`
   explicitly excludes `install.sh`, the legacy dispatcher, and Swift and
   Windows source trees. Native installation needs the full checkout or a
   separately verified full repository source archive containing those
   files. A future source archive must be made from the reviewed, committed
   revision, never inferred from a Python sdist.
4. **Pin and record provenance.** Match wrapper and native source revisions
   for initial installations/upgrades; record the full commit ID, Python
   and Swift versions, SDK, macOS, architecture, and artifact SHA-256s.
   Review the installer and manifests before execution. A checksum detects
   changed bytes but does not independently authenticate a publisher.
   Signed tags/checksum manifests help only with a separately trusted key
   or identity; do not claim signatures that do not exist.
5. **Block public publication until the rights holder establishes the
   project license.** Do not create an invented `LICENSE`, select an SPDX
   identifier, or add an open-source license classifier. Once authorized,
   add the actual license text and matching package metadata and verify
   inclusion in both distributions. Dependency licenses and Apple
   system-voice terms remain separate from the project's license.
6. **Document signing accurately rather than bypassing platform security.**
   Source builds are not automatically Developer ID signed or notarized.
   Swift/compiler tooling may apply an ad-hoc signature, which is not a
   publisher identity. Quarantined downloaded unsigned binaries can be
   blocked by Gatekeeper; locally built executables have a different
   provenance/quarantine context. Signing/notarization would be a separate
   release decision, not a fix for all speech-asset or permission issues.

## Consequences

- Installing a wheel alone permits imports, help, and diagnostics, but
  native speech operations still require a separately installed engine.
  Some STT formats also require the preserved `whisper-py-convert` script;
  the native binary alone is not a complete legacy STT installation.
- Users need an appropriate Swift 6.4+ toolchain and SDK to build the
  current sources. Only macOS 27.0.1/Apple Silicon has native runtime
  verification; older TTS runtime floors and Intel builds are not a tested
  compatibility matrix.
- Source builds reduce release infrastructure and credential requirements
  but require users to establish trust in source and their compiler. They
  are not guaranteed byte-for-byte reproducible across toolchains.
- A working local wheel/sdist alone did not resolve the original missing-license
  blocker; ADR-003 records the later explicit selection. Local builds still do
  not reserve the `mac-speech` PyPI name or mean PyPI packages, signed tags, repository
  source tarballs, or native release assets have been published.
- `docs/packaging.md` is the release/trust/signing reference;
  `docs/installation.md` remains the operational install/upgrade/uninstall
  guide. Neither `PLAN.md` nor the handoff is changed by this decision.

## Alternatives considered

- **Bundle native binaries in platform wheels:** rejected for now. Adds
  architecture/OS matrices, signing/provenance work, and coupled releases
  without removing Apple asset/permission requirements.
- **Build Swift during `pip install`:** rejected. Makes a lightweight
  Python installation require platform-specific compilers and hides native
  build execution in a Python packaging hook.
- **Ship unsigned downloaded binary assets now:** deferred. Requires a
  verified distribution identity, integrity policy, quarantine review,
  license resolution, and tested supported platforms first.
- **Developer ID signed/notarized application or package:** deferred until
  a concrete binary-distribution need justifies Apple Developer account,
  credential management, bundling/entitlement design, and clean-machine
  verification. Core local use must not require signing credentials.
- **Put every repository file into the Python sdist:** rejected. Blurs the
  Python/native boundary and risks accidentally distributing build caches,
  local assets, or internal handoff material. A full repository source
  archive is the explicit native-source vehicle instead.
