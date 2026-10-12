# Changelog

## Unreleased — initial Mac Speech Toolkit baseline

The Python metadata currently says `0.1.0`; this section is not a claim
that a `0.1.0` tag, published wheel, or signed native release exists.
Use [the release-notes template](docs/release-notes-template.md) when a
specific reviewed revision is actually released.

### Phase 13A hardening

- Managed workflow basenames cannot traverse outside their selected canonical
  directory. Preflight rejects unsafe output entries before speech starts.
- Native audio and Python text/SRT/manifest publication use atomic
  create-if-absent or explicit regular-file replacement, preserving late
  concurrent writers. Unsafe symlink/special-file entries are refused.
- Private `0600` outputs, native `0700` staging with pre-reserved audio inode,
  and TTS timeout errors that do not duplicate source sentences.
- Cooperating runs claim their basename and optionally persist owned stage
  checkpoints (`persist_manifest=True`, always enabled by the CLI). Foreign
  checkpoint replacements fail closed instead of being silently overwritten.
- Cancellation kills/reaps owned native writers before claim release;
  unconfirmed acquisition/termination retains the claim. Cleanup failures
  preserve original operation errors and cancellation.
- **Compatibility:** raw `WorkflowManifest.write`, artifact `write_manifest`
  and `stage_render_srt` now require `force=True` to replace existing regular
  files. Rebuild/install native TTS from matching updated source; a wheel
  does not replace an old native binary. These changes remain unreleased.

### Added

- Apple STT reservation maintenance: already-reserved false returns are reused,
  newly-owned supporting locale variants are released with awaited cleanup, and
  cooperating native calls serialize through analysis/output/cleanup. Additive
  read-only `--inventory-status` and named Speech error diagnostics distinguish
  locale/capacity failures; graceful cancellation and pipe backpressure are covered.
  Transcript/text/SRT contracts and independent TTS are unchanged. Real borrowed
  reuse passes; newly-owned native cleanup remains a separate validation gate.
- Phase 13B bounded TTS-only batches: default one worker, explicit cap 1–4,
  finite validated scene JSON, input-ordered private `batch.json` and per-scene
  workflow checkpoints. No implicit STT, playback, export or model download.
- Cooperative cancellation/owned I/O exchange with complete long-stdin delivery,
  acknowledged worker admission and drain-before-release safeguards. New
  Python/native `cancelled` error code maps to exit 130; prior codes unchanged.

- Small standard-library-first `mac_speech` Python API and `mac-speech`
  CLI with version, capability, and environment diagnostics.
- Independent native Swift TTS engine using Apple's system voices:
  voice listing, playback/control, WAV/AIFF/CAF file synthesis, bounded
  timeouts, sentence chunking, and a versioned JSON response protocol.
- Shared STT adapter preserving the legacy script/native engines,
  structured transcripts, SRT/WebVTT, and explicitly approximate
  STT-roundtrip alignment (not forced alignment or native TTS word timing).
- Opt-in artifact manifests/checksums, overwrite protection, and
  independently retryable narration workflow stages that retain
  successful outputs when later stages fail.
- Optional explicit local/Google Drive/S3/Slack-link exporters. Drive
  dependencies remain an extra; S3 uses AWS CLI and Slack uses the
  separate `team-slack-bridge` CLI, not an additional credential store.
- Source installer modes `stt`, `tts`, and `all`; installation, privacy,
  cleanup, release, and dirty-tree-preserving rollback guidance.
- Phase 12 Python-only wheel/sdist packaging, strict required-integer TTS
  protocol validation, automatic mocked Python CI configuration, scoped
  lint/type gates, and manual/opt-in isolated Swift checks.
- Offline dependency/license inventory, clean-wheel/network-denied native
  smoke helper, release checklist/template, and tested narration/lifecycle
  examples. No public release, signing, model download, or live export is
  implied by this locally verified implementation.

### Compatibility and operational notes

- Both Swift source manifests require Swift 6.4+. Runtime deployment
  targets are macOS 13+ for TTS and macOS 27+ for Apple STT; Personal
  Voice status/traits require macOS 14+. Only macOS 27.0.1 arm64 has
  been tested locally. Python metadata permits >=3.9; the local baseline
  was Python 3.11.3. Do not infer older-OS/Intel validation.
- The installer does not install the Python package. **Every mode**
  installs the legacy script/symlink; `tts` skips the STT native build,
  not the legacy wrapper. No mode removes a previously installed engine.
- Custom XDG installation paths may require explicit TTS/script overrides;
  direct Apple JSON discovery does not honor custom XDG data paths.
- Keep matching wrapper/native versions together; review resolved engine
  paths when upgrading or rolling back. See [installation.md](docs/installation.md)
  and [packaging.md](docs/packaging.md).

### Known limitations / release gates

- Apple STT risk #19 is **partially repaired**: capacity is device-specific, not
  universally five or a process/request quota. Existing full reservation state
  can still reject a new supporting locale and is not automatically evicted.
  Borrowed-reservation fixtures pass; real newly-owned release remains blocked
  pending a free slot or explicitly approved targeted recovery. Default native
  skips are now explicit prerequisites, never generic unsupported-locale catches.
- Personal Voice authorization is report-only. Voice catalog membership
  can vary; there is no creation/extraction/unlocking flow.
- Concurrent playback shares a single PID-file control slot by default.
  Swift Testing can suffer toolchain module-cache/plugin flakiness.
- No neural TTS models were downloaded or bundled. Candidate model
  licensing/acceleration/listening evaluations remain deferred.
- Google Drive real-account upload, S3 real upload/large-file verification,
  and a real Slack post have not been validated. Provider mocks and
  selected S3/Slack dry-runs do not establish production readiness.
- The maintainer selected custom proprietary personal-use/non-commercial/
  no-derivatives terms on 2026-10-12; see [LICENSE](LICENSE). This is not
  OSI-approved open source and does not replace third-party rights/terms.
  Missing-license selection is resolved, but legal/compliance review and
  explicit publication/signing decisions remain separate release gates.

### Evidence baseline

The Phase 11 handoff records **188 Python tests passed, 4 skipped** and
**39 Swift tests passed**, on the machine/version above. This is a
historical baseline, not a claim about the current unreleased test count.

Phase 12 independent final local evidence: Python 3.11.3 **322 passed,
4 native STT skips**; mocked source suites **322 passed each** on
3.12.5/3.13.7/3.14.8; extracted sdist **311 passed, 15 skipped**. Package/helper
Ruff and 16-file scoped strict mypy passed, as did **39 Swift tests/release
build** via `scripts/ci_swift.sh`. Clean 3.11.3 wheel and real TTS-only smoke
passed with credential environment stripped and network denied; focused
wheel/native uninstall/restore was verified in temporary paths. See
[verification](docs/verification.md) for boundaries. Hosted-CI results and
local Python 3.9/3.10 remain unverified; native CI requires manual opt-in.

Record exact commands, results, skips, and actual revision in each release's
notes; installer lifecycle simulations do not replace real native smoke tests.
