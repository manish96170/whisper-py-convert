# ADR-001: Repository and module boundaries for TTS and the shared wrapper

**Status:** Accepted (Phase 0)
**Date:** 2026-10-09

## Implementation clarification (through Phase 12)

The monorepo/additive-boundary decision remains accepted. The context below
records **Phase 0 facts**, not current package/test/CI absences. Phase 2 chose
the independent `engines/tts-swift/Package.swift` option to keep TTS's macOS 13
floor separate from root STT's macOS 27 floor; the root manifest did **not**
gain a TTS target. Both now require Swift tools 6.4, with no external Swift
package dependencies. Phase 4 added `stt`/`tts`/`all` native installer modes;
all copy the legacy script, but Python package installation remains a separate
pip action, not an installer side effect. The legacy dispatcher/native STT
sources and Windows helper remain preserved. Phase 12 added packaging and CI;
[ADR-002](ADR-002-packaging-and-distribution.md) governs distribution and the
unresolved public-release license gate.

## Context

`PLAN.md` requires inspecting the existing STT repository before deciding
"monorepo versus companion repository" (section 3.2, Phase 0 task). The
existing repository, `whisper-py-convert`, was inspected directly (see
`docs/architecture.md`). Key facts that bear on this decision:

- `whisper-py-convert` is a single-maintainer, personal-use repository with
  no `pyproject.toml`, no published package, no CI, and no external
  consumers found during inspection (git remote has one branch, no tags, no
  releases).
- It already implements the exact pattern `PLAN.md` wants for TTS: **one
  stable Python CLI/dispatcher** (`whisper-py-convert.py`) **selecting among
  multiple independent, platform-specific native backends**
  (`whisper-py-convert-apple` built from `Package.swift`, and an optional
  Windows MSIX helper in `windows/`), each with its own build and
  installation path, unified by a documented JSON contract
  (`ARCHITECTURE.md`, "Adding another backend").
- `Package.swift` already supports multiple products/targets; adding a
  second executable target does not require restructuring the existing
  `WhisperAppleTranscribe` target.
- `install.sh` already has a conditional build step
  (`if ... command -v swift`) that is a natural place to add a second,
  independent build step without touching the existing one.
- The CLI name and scope (`whisper-py-convert`) is explicitly STT-branded.
  `PLAN.md` section 4.1 proposes a different, broader command name
  (`mac-speech`) covering STT, TTS, and artifacts/export.

## Decision

**Keep one repository (monorepo-in-place).** Do not create a companion
repository, and do not rename or restructure the existing repository root in
this phase.

Concretely:

1. `whisper-py-convert.py`, `Package.swift`'s existing
   `WhisperAppleTranscribe` target, `windows/`, and `install.sh`'s existing
   behavior are **preserved exactly as-is**. They remain independently usable
   and are the system of record for STT until a later phase deliberately
   adapts them (Phase 4, with explicit regression evidence).
2. New work goes into clearly separated, additive top-level paths, following
   the preferred layout sketched in `PLAN.md` section 3.2:
   - `python/mac_speech/` — the new shared Python package and `mac-speech`
     CLI (Phase 1+). This is a *new* package, not a modification of
     `whisper-py-convert.py`. Its STT support (Phase 4) will be an adapter
     that shells out to the existing Apple/Windows binaries and reuses the
     existing JSON contract, never importing or forking
     `whisper-py-convert.py` internals.
   - `engines/tts-swift/` (or an equivalent new executable target added to
     `Package.swift`) — the new, standalone native TTS engine (Phase 2). It
     must not import, link against, or spawn `whisper-py-convert-apple`.
   - `docs/` — architecture, ADRs, performance, security, formats
     (this discovery's deliverables; growing in later phases).
   - `tests/` — new, for the new package and TTS engine only. Existing STT
     behavior is covered by the manual smoke test in `ARCHITECTURE.md`
     until/unless Phase 4 adds STT regression fixtures around the existing
     binary without modifying it.
3. The existing `whisper-py-convert` command stays installed and usable
   exactly as it is today, independent of whether `mac-speech` is installed.
   `mac-speech stt ...` (Phase 4) is an optional, additive integration layer
   on top of the existing tool, not a replacement for it.
4. Any future decision to rename the repository, split it into multiple
   repositories, or rebrand the STT CLI is explicitly out of scope for this
   ADR and must be made later, with its own justification and review, once
   there is a concrete reason (e.g., separate release cadence, separate
   license, external users depending on the current name).

## Rationale

- **Lowest risk to the working STT tool.** Nothing about the existing STT
  code path needs to change to add TTS. This directly satisfies the plan's
  non-goal: "Do not make the new TTS implementation depend on the STT
  executable, process, app UI, or internal implementation," and "Do not
  rewrite functioning STT code just to fit a new architecture."
- **The existing architecture already matches the target pattern.** This
  repository already proves out "one Python dispatcher, N independent native
  backends, JSON-over-stdout contract." Reusing that pattern for TTS (as a
  new backend-shaped module, not a new backend of the *same* dispatcher) is
  less risky than inventing new repository/package plumbing in a second repo
  for a single-maintainer, single-machine project.
- **Companion repository overhead is not justified yet.** There are no
  external consumers, no packaging/release process, and no license
  separation requirement found during inspection that would justify the
  coordination cost (versioning across repos, duplicated CI, duplicated
  docs) of a second repository. `PLAN.md` itself frames the companion-repo
  option as appropriate "if the existing STT repository is already
  independently packaged and stable" — it is stable, but not independently
  packaged (no `pyproject.toml`, no releases), which weakens the case for
  splitting now.
- **Reversible.** Because the new work lives in additive paths and the new
  Swift target is independent, this decision can be reversed later (e.g., by
  extracting `engines/tts-swift/` and `python/mac_speech/` into a new
  repository) without rewriting their internals, if a concrete need for
  separation (e.g., different open-source license for voice models, separate
  release cadence) emerges in a later phase.

## Consequences

- The repository will contain both an STT-branded legacy entrypoint
  (`whisper-py-convert`) and a broader `mac-speech` CLI/package. This must be
  documented clearly in the top-level `README.md` once Phase 1 ships, so
  users are not confused about which command to use for which purpose.
- `install.sh` will need a second, independent code path for building/
  installing the TTS engine (implemented in Phase 3, mode selection in
  Phase 4). `mac_speech` itself is installed separately with pip.
- TTS builds independently through its own `engines/tts-swift/Package.swift`,
  as clarified above; the root STT manifest/target is unchanged. Isolated
  TTS tests/builds use `scripts/ci_swift.sh`; they do not test the root STT target.
- Future phases must continue updating this ADR's status (e.g., "Superseded
  by ADR-00N") rather than silently deviating from it, per the plan's
  phase-governance rules.

## Alternatives considered

1. **Companion repository (`mac-speech-tts` or `mac-speech`) wrapping this
   repo as a dependency.** Rejected for now: adds cross-repo versioning and
   CI duplication with no current external consumer or packaging constraint
   that requires it. Revisit if/when this project needs independent
   releases, a different license for bundled voice models, or external
   contributors who should not need the STT code to work on TTS.
2. **Rename/restructure this repository to `mac-speech/` immediately,
   matching `PLAN.md`'s preferred layout verbatim.** Rejected: `PLAN.md`
   explicitly says this layout is "a target shape, not an instruction to
   restructure before inspection," and a rename changes the installed
   command path (`~/.local/bin/whisper-py-convert`), git remote/URL
   expectations, and existing muscle memory for a tool that already works.
   No concrete benefit was identified that offsets this churn risk in Phase
   0.
3. **Add TTS as another `--engine`-style backend inside
   `whisper-py-convert.py` itself.** Rejected: TTS and STT are different
   operations (synthesize vs. transcribe) with different inputs/outputs; the
   existing dispatcher's option set (`--model`, `--language`,
   `--seg-ts`/`--word-ts`, `--srt`) is STT-specific. Forcing TTS through the
   same flat argparse surface would violate the plan's requirement for a
   coherent, documented contract per operation (section 4.3) and risks
   destabilizing the existing CLI's option parsing.
