# ADR-003: Custom proprietary personal-use license

**Status:** Selected by explicit maintainer instruction; text and package
inclusion require verification before release.
**Date:** 2026-10-12

## Decision

The maintainer selected a custom proprietary personal-use, non-commercial,
no-derivatives license. [LICENSE](../../LICENSE) is authoritative;
[licensing guidance](../licensing.md) summarizes its scope and legal-review
caveats. The grant permits download/install/run and unchanged-source local
compilation for personal, non-commercial use. It prohibits Software
modification/derivative works and commercial/revenue-generating use, subject
to non-waivable legal rights; other rights require a separate written grant.

The project is source-available, **not OSI-approved open source**. This
supersedes the original open-source-first goal as a license policy for
first-party project materials, not third-party engines/models/tools/voices.
Their separate licenses and independently granted rights remain in force.

## Packaging

Use the custom PEP 639 identifier
`LicenseRef-Mac-Speech-Personal-NonCommercial-NoDerivatives`, ship `LICENSE`
in the wheel/sdist, and require setuptools 77+ as a build dependency. Do not
mislabel the custom license MIT, Apache-2.0, or OSI-approved. Python runtime
minimum and zero base runtime dependencies remain unchanged.

ADR-002's missing-license gate is addressed by this explicit selection;
its source/wheel/native boundaries and other release checks still apply.
This decision is not an automatic commit, publication, signing authorization,
legal enforceability opinion, or proof of rights in all contributions.

## Concurrent work

The separate STT repair session owns already-modified code and shared plan,
risk-register/handoff/operational docs. This license decision does not alter
or discard those edits. Reconcile their former missing-license statements
against ADR-003 after that session's work settles; historical handoffs retain
their original time-scoped evidence.
