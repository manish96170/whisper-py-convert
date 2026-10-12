# Project licensing

On 2026-10-12, the maintainer explicitly selected a **custom proprietary
personal-use, non-commercial, no-derivatives license** for first-party code
and documentation. The authoritative terms are in [LICENSE](../LICENSE).

This is **source-available, not OSI-approved open-source software**. Public
source visibility does not grant modification, commercial-use, or
redistribution rights. The original plan's open-source-first goal is a
historical design preference, not the current license grant for project code.

## Permitted and restricted use

- Download/install/run for an individual's own personal, non-commercial use.
- Compile/package **unmodified** source for that permitted local use, and
  retain personal installation/backup copies with the license/notices.
- Use supported runtime options/configuration and your own input content.
- No modification, adaptation, translation of the Software, reverse
  engineering, or derivative works, subject to non-waivable legal rights.
- No sale/rental/lease, commercial services, business/employer/client use,
  or revenue-generating/monetized-content use without a separate written grant.
- No licensee redistribution/sublicensing rights are granted. The rights
  holder can separately authorize distribution and other uses in writing.

Input/output ownership is not transferred to the maintainer; the restrictions
apply to use of the Software, not a claim of ownership over your narration.
Third-party library/tool/model/voice terms and their independently granted
rights remain separate; this license cannot relicense those components.
See [the dependency inventory](sbom.md) for its scope and limitations.

## Packaging and release policy

The custom metadata identifier is
`LicenseRef-Mac-Speech-Personal-NonCommercial-NoDerivatives`. It identifies
the project text; it is **not** the name of an OSI-approved license or a claim
that every repository component has the same terms. Python packaging uses
PEP 639 license metadata and includes the actual `LICENSE` in wheel/sdist.
The build backend needs setuptools 77+ for that metadata; base runtime
dependencies and Python 3.9+ runtime requirements are unchanged.

The previous **missing-license** blocker is resolved by the maintainer's
selection and recorded text. That alone does not publish or authorize a
package/tag/binary release, clear third-party compliance, prove rights in all
contributions, or complete signing/notarization/platform/security review.
Releases remain maintainer-controlled; do not infer future commit/push or
publication permission from this licensing change.

This is a software-license draft, not a legal opinion. Before distributing
publicly, have qualified counsel review the terms, rights-holder authority,
contract acceptance/enforceability (especially reverse engineering), and any
required jurisdiction-specific wording. No legal entity, governing law,
copyright attribution/year, or commercial-contact identity was invented.

## Concurrent STT work

STT repair is being handled in another session. This licensing task does not
change its code or overwrite its active `PLAN.md`, risk-register, handoff,
installation, architecture, platform, or verification updates. Those shared
documents should reconcile their old missing-license statements with this
decision when the STT session finishes. Historical handoffs remain historical.

## Verification snapshot (2026-10-12)

- 40 focused project-license/dependency-inventory tests passed; the new test
  file passes correctness lint. No live speech/provider tests were invoked.
- Offline `audit_dependencies.py --group runtime --check` returns **0** with
  the custom declaration, root `LICENSE`, empty runtime dependencies and no
  metadata findings. This is completeness, not legal clearance.
- With build 1.6.1/setuptools 84.0.0, a disposable copy built its wheel **from
  the sdist**. Both metadata records carry the exact custom `License-Expression`;
  the wheel carries `License-File: LICENSE` and byte-identical text at
  `.dist-info/licenses/LICENSE`; the sdist contains the root license and ADR.
- A clean non-editable Python 3.11.3 venv installed the built wheel locally
  (`--no-index --no-deps`); `pip check` and CLI version passed. No native engine,
  cloud credential or model was required for these packaging checks.
- Setuptools 77.0.3 upstream metadata declares Python `>=3.9`, consistent
  with the unchanged wrapper minimum. No new Python 3.9 runtime execution
  or complete concurrent STT verification is claimed by this task.
- A separate read-only license-engineering reviewer found one copy-checklist
  omission; root `LICENSE` was explicitly added to the packaging checklist.
  This does not replace qualified legal review or rights-holder confirmation.

Local evidence/artifacts are under the approved temp root in
`license-final-l22x22pf/`. They may include a snapshot of concurrent wrapper
work, are **not published/authenticated releases**, and must be rebuilt from
reviewed committed source before any authorized publication. No files were
staged, committed or pushed by this licensing task.
