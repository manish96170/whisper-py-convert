# Release preparation and gates

**No public release was made by Phase 12.** The current `0.1.0` package
version is development metadata, not evidence of a published tag, PyPI
package, signed binary, or notarization. The maintainer has now selected the
custom proprietary license in [LICENSE](../LICENSE)/[licensing guidance](licensing.md).
Missing-license selection is resolved; public publication still needs explicit
approval and the other checks below, including legal/third-party review.

This is a human-controlled checklist, not an automatic publishing pipeline.
See [packaging](packaging.md) for artifact boundaries/trust/signing,
[dependency inventory](sbom.md) for license/audit limitations, and
[installation](installation.md) for tested upgrade/uninstall/rollback.

## Before preparing public artifacts

- Verify the selected custom proprietary license text and matching package
  metadata/inclusion. Do not label it open source; confirm rights-holder
  authority and obtain appropriate legal review. Dependency licenses do not
  grant rights to this project's code or become subject to its restrictions.
- Review all intended source, including untracked files, and confirm the
  selected commit actually contains it (`git archive` omits untracked/dirty
  changes). Commit/push must be explicitly authorized; authorization for that
  transaction is not authorization to tag, upload, or publish a package.
  Agents must not perform those actions automatically.
- Use a separate clean copy of the reviewed source to build release outputs.
  Record the full revision, OS/architecture, Python/Swift/SDK versions,
  build tools, and dirty state. Never label a dirty build as a tagged release.
- Synchronize package and CLI versions, TTS protocol compatibility, and
  [CHANGELOG.md](../CHANGELOG.md). Legacy STT is deliberately unversioned;
  record its source revision without changing its contract.
- Resolve the intended Python extras in disposable environments, record
  actual direct/transitive versions and licenses, and review current
  vulnerability advisories. A range-based direct inventory or an offline
  metadata report is not a complete resolved/vulnerability-audited SBOM.
  These network-capable release checks are separate from offline core tests.

## Validate before publication

1. Run the Python unit suite, configured Ruff and strict mypy gates, and
   isolated lint for the Phase 12 scripts/tests. Record exact counts and skips.
2. Run `bash scripts/ci_swift.sh` with Swift 6.4.x on an appropriate macOS
   host. Automatic Python CI is configured; the native job is opt-in and
   requires an explicitly provisioned runner. Local success is not a hosted
   CI result or a test of every declared runtime floor.
3. Build the Python sdist and a wheel **from that sdist**, inspect metadata
   and archive contents, and install the wheel outside the checkout into a
   clean venv with `--no-index --no-deps`.
4. Run [clean-install/network-denied core verification](verification.md)
   without optional integrations or credentials. Exercise real local TTS
   with installed system voices. Do not silently select faster-whisper,
   provision Apple assets, or download a model for a smoke test.
5. Exercise the documented uninstall and matching wheel/binary rollback in
   temporary HOME/XDG/venv paths, retaining unrelated artifacts and dirty
   source. Installer simulations do not replace a real native install check.
6. Keep real STT validation and optional real provider checks honestly
   labeled. The known Apple locale-reservation defect can prevent STT
   fixtures from running; do not call skipped transcription tests a pass.
7. If offering a full source archive, inspect it separately. If offering
   compiled binaries later, complete the separate signing/notarization and
   quarantined-download tests in the packaging guide first.
8. Generate SHA-256 hashes of final artifacts (after any signing/stapling),
   record provenance/SBOM and known limitations, and fill the
   [release-notes template](release-notes-template.md). Hashes alone do not
   authenticate a publisher. Confirm publication authorization and the
   intended registry/project before any human-triggered upload.

Keep the previous trusted binaries, wheel, or source/venv pair before an
upgrade. Do not roll back by switching or resetting the current dirty tree;
use the [separate-source or kept-backup procedure](installation.md#rollback).
