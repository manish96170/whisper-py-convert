"""Workflow orchestration for a narration pipeline (PLAN.md Phase 11).

text -> TTS audio -> STT-roundtrip alignment -> SRT -> downstream video
tool. Each stage below (`stage_synthesize`, `stage_align`,
`stage_render_srt`) is a plain function that can be called
independently and retried without regenerating the others.
`run_narration_pipeline` is a convenience that chains them — not the
only way to use them, and a failed later stage never invalidates an
earlier successfully-produced artifact (it simply stops chaining and
records the failure in the manifest; prior files on disk are
untouched).

**Timing-approximation decision (explicit, per PLAN.md Phase 11):**
this toolkit uses STT-on-generated-audio as its only alignment
mechanism (`mac_speech.align.align_via_stt_roundtrip`), not a dedicated
forced-alignment engine (e.g. Montreal Forced Aligner, gentle).
Deliberate, not an oversight: bundling a separate forced-alignment tool
is materially larger scope than this toolkit's local-first speech core,
and STT round-trip timing already produces monotonic, reasonably
accurate word timestamps for synthesized speech (verified: Phase 4
regression fixtures, Phase 7 `test_align.py`) — synthesized audio is
simpler/cleaner than real-world recordings, which is exactly the case
this pipeline targets. If a downstream workflow needs frame-accurate
phoneme alignment, add a dedicated forced-alignment tool as a new,
separate stage; do not over-claim accuracy from this one.

**Scene/chunk boundaries are the caller's responsibility, by design**
(PLAN.md: "keep expression timing, visual editing, and rendering
responsibilities in the video project, not in the speech engine").
Call `run_narration_pipeline` once per scene/paragraph with its own
`basename`, from the calling video-workflow script — this module does
not invent its own scene-management on top of that.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Event
from typing import Any, Iterator

from .align import align_via_stt_roundtrip
from .errors import ErrorCode, MacSpeechError
from .file_io import atomic_write_checkpoint, atomic_write_text, check_output_path
from .logging_utils import secondary_diagnostic
from .stt.models import Transcript
from .stt.srt import transcript_to_srt
from .tts import synthesize_to_file

WORKFLOW_SCHEMA_VERSION = 1


@dataclass
class WorkflowStage:
    name: str
    status: str  # "success" | "failed"
    output_path: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowManifest:
    schema_version: int
    created_at: str
    source_text_sha256: str
    stages: list[WorkflowStage] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.stages) and all(stage.status == "success" for stage in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "source_text_sha256": self.source_text_sha256,
            "ok": self.ok,
            "stages": [stage.to_dict() for stage in self.stages],
        }

    def write(self, path: Path, *, force: bool = False) -> Path:
        return atomic_write_text(path, json.dumps(self.to_dict(), indent=2) + "\n", force=force)

    def write_checkpoint(
        self, path: Path, *, force: bool = False, expected_identity: tuple[int, int] | None = None
    ) -> tuple[int, int]:
        return atomic_write_checkpoint(
            path, json.dumps(self.to_dict(), indent=2) + "\n",
            force=force, expected_identity=expected_identity,
        )


@dataclass(frozen=True)
class WorkflowPaths:
    directory: Path
    audio: Path
    subtitles: Path
    manifest: Path
    lock: Path


def validate_basename(basename: str) -> None:
    """Validate a managed filename component without creating a directory."""
    if (
        not isinstance(basename, str) or not basename.strip() or basename in {".", ".."}
        or "/" in basename or "\\" in basename
        or any(ord(character) < 32 or ord(character) == 127 for character in basename)
    ):
        raise MacSpeechError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="Workflow basename must be a non-empty filename component, not a path.",
            remedy="Use a scene name such as scene-01, without separators or control characters.",
        )


def prepare_workflow_paths(
    output_dir: str, *, basename: str = "narration", align: bool = True, force: bool = False
) -> WorkflowPaths:
    """Validate a single scene's managed paths before any speech side effect.

    Parent directories must be trusted; this is not a sandbox against an
    actor who can concurrently rename/replace the workspace directory.
    """
    validate_basename(basename)
    try:
        directory = Path(output_dir).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise MacSpeechError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="Cannot prepare the workflow output directory.",
            remedy="Choose a writable, trusted local directory.",
        ) from exc
    paths = WorkflowPaths(
        directory=directory,
        audio=directory / f"{basename}.wav",
        subtitles=directory / f"{basename}.srt",
        manifest=directory / f"{basename}.workflow.json",
        lock=directory / f".{basename}.workflow.lock",
    )
    for path in (paths.audio, paths.manifest, *((paths.subtitles,) if align else ())):
        check_output_path(path, force=force)
    return paths


@contextmanager
def claim_output_path(lock: Path, *, retain_event: Event | None = None) -> Iterator[None]:
    """Exclusive cooperative marker; force never bypasses an active marker.

    A process crash can leave a marker. Do not guess that it is stale or
    unlink another writer's state automatically: choose another basename
    or inspect it only after confirming no corresponding run is active.
    """
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise MacSpeechError(
            code=ErrorCode.OUTPUT_EXISTS,
            message="This workflow basename is already claimed by another run or an unverified marker.",
            remedy="Use a new basename; inspect an old marker only after confirming no run is active.",
        ) from exc
    except OSError as exc:
        raise MacSpeechError(code=ErrorCode.INTERNAL_ERROR, message="Cannot claim the workflow workspace.") from exc
    owned = None
    try:
        owned = os.fstat(descriptor)
        os.write(descriptor, f"{os.getpid()}\n".encode("ascii"))
        yield
    except OSError as exc:
        converted = MacSpeechError(code=ErrorCode.INTERNAL_ERROR, message="Cannot manage the workflow claim.")
        if getattr(exc, "_mac_speech_native_unconfirmed", False):
            setattr(converted, "_mac_speech_native_unconfirmed", True)
        raise converted from exc
    finally:
        failure = sys.exc_info()[1]
        unconfirmed = failure is not None and getattr(failure, "_mac_speech_native_unconfirmed", False)
        unconfirmed = unconfirmed or (retain_event is not None and retain_event.is_set())
        cleanup_failure = None
        try:
            os.close(descriptor)
        except OSError as exc:
            cleanup_failure = exc
        try:
            current = lock.lstat()
            if not unconfirmed and owned is not None and (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino):
                lock.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            cleanup_failure = exc
        if cleanup_failure is not None:
            if failure is not None:
                secondary_diagnostic("Workflow marker cleanup failed; the original failure and completed artifacts were retained.")
            else:
                raise MacSpeechError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message="Could not clean up this workflow's marker; completed artifacts were retained.",
                    remedy="Inspect permissions and use a fresh basename; do not remove an active run's marker.",
                ) from cleanup_failure


@contextmanager
def _claim_workflow(paths: WorkflowPaths) -> Iterator[None]:
    with claim_output_path(paths.lock):
        yield


def new_manifest(source_text: str) -> WorkflowManifest:
    return WorkflowManifest(
        schema_version=WORKFLOW_SCHEMA_VERSION,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        source_text_sha256=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
    )


def stage_synthesize(
    text: str, *, output_path: str, voice: str | None = None, language: str | None = None, force: bool = False
) -> WorkflowStage:
    """Stage 1: text -> TTS audio file."""
    try:
        result = synthesize_to_file(text, output_path=output_path, voice=voice, language=language, force=force)
    except Exception as exc:  # noqa: BLE001 - recorded in the manifest, not raised
        if getattr(exc, "_mac_speech_native_unconfirmed", False):
            raise  # Keep the claim instead of allowing another writer in.
        return WorkflowStage(name="synthesize", status="failed", error=str(exc))
    return WorkflowStage(
        name="synthesize",
        status="success",
        output_path=result.output_path,
        provenance={
            "engine": "mac-speech-tts",
            "voice_identifier": result.voice_identifier,
            "language": result.language,
            "duration_seconds": result.duration_seconds,
        },
    )


def stage_align(
    audio_path: str, *, engine_name: str = "auto", language: str | None = None
) -> tuple[WorkflowStage, Transcript | None]:
    """Stage 2: TTS audio -> approximate word timing via STT round-trip.
    See module docstring for why this is STT-based, not a dedicated
    forced-alignment engine."""
    try:
        transcript = align_via_stt_roundtrip(audio_path, engine_name=engine_name, language=language)
    except Exception as exc:  # noqa: BLE001
        return WorkflowStage(name="align", status="failed", error=str(exc)), None
    stage = WorkflowStage(
        name="align",
        status="success",
        provenance={
            "engine": transcript.engine,
            "segment_count": len(transcript.segments),
            "method": "stt_roundtrip_approximation",
        },
    )
    return stage, transcript


def stage_render_srt(
    transcript: Transcript, *, output_path: str, word_timestamps: bool = True, force: bool = False
) -> WorkflowStage:
    """Stage 3: aligned Transcript -> SRT file for a downstream video tool."""
    try:
        content = transcript_to_srt(transcript, word_timestamps=word_timestamps)
        atomic_write_text(Path(output_path), content, force=force)
    except Exception as exc:  # noqa: BLE001
        return WorkflowStage(name="render_srt", status="failed", error=str(exc))
    return WorkflowStage(
        name="render_srt", status="success", output_path=output_path, provenance={"word_timestamps": word_timestamps}
    )


def run_narration_pipeline(
    text: str,
    *,
    output_dir: str,
    basename: str = "narration",
    voice: str | None = None,
    language: str | None = None,
    align: bool = True,
    force: bool = False,
    persist_manifest: bool = False,
) -> WorkflowManifest:
    """Convenience chain: text -> audio -> (optional) alignment -> SRT.
    Prefer calling `stage_synthesize`/`stage_align`/`stage_render_srt`
    directly for independent retries of a single stage."""
    paths = prepare_workflow_paths(output_dir, basename=basename, align=align, force=force)
    with _claim_workflow(paths):
        # Repeat preflight under our marker: another cooperating run could
        # have completed between the first check and marker acquisition.
        for path in (paths.audio, paths.manifest, *((paths.subtitles,) if align else ())):
            check_output_path(path, force=force)
        manifest = new_manifest(text)
        checkpoint_identity = None
        if persist_manifest:
            checkpoint_identity = manifest.write_checkpoint(paths.manifest, force=force)

        def record(stage: WorkflowStage) -> None:
            nonlocal checkpoint_identity
            manifest.stages.append(stage)
            if persist_manifest:
                # This run owns the initial checkpoint. Replacing its own
                # checkpoint is explicit and remains inside the claim.
                checkpoint_identity = manifest.write_checkpoint(
                    paths.manifest, force=True, expected_identity=checkpoint_identity,
                )

        audio_path = str(paths.audio)
        synth_stage = stage_synthesize(text, output_path=audio_path, voice=voice, language=language, force=force)
        record(synth_stage)
        if synth_stage.status != "success" or not align:
            return manifest

        align_stage, transcript = stage_align(audio_path, language=language)
        record(align_stage)
        if align_stage.status != "success" or transcript is None:
            return manifest

        record(stage_render_srt(transcript, output_path=str(paths.subtitles), force=force))
        return manifest
