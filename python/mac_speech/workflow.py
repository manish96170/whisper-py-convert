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
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .align import align_via_stt_roundtrip
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
        return all(stage.status == "success" for stage in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "source_text_sha256": self.source_text_sha256,
            "ok": self.ok,
            "stages": [stage.to_dict() for stage in self.stages],
        }

    def write(self, path: Path) -> Path:
        temp = path.with_name(path.name + f".tmp-{time.time_ns()}")
        temp.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
        return path


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


def stage_render_srt(transcript: Transcript, *, output_path: str, word_timestamps: bool = True) -> WorkflowStage:
    """Stage 3: aligned Transcript -> SRT file for a downstream video tool."""
    try:
        content = transcript_to_srt(transcript, word_timestamps=word_timestamps)
        Path(output_path).write_text(content, encoding="utf-8")
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
) -> WorkflowManifest:
    """Convenience chain: text -> audio -> (optional) alignment -> SRT.
    Prefer calling `stage_synthesize`/`stage_align`/`stage_render_srt`
    directly for independent retries of a single stage."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = new_manifest(text)

    audio_path = str(out_dir / f"{basename}.wav")
    synth_stage = stage_synthesize(text, output_path=audio_path, voice=voice, language=language, force=force)
    manifest.stages.append(synth_stage)
    if synth_stage.status != "success" or not align:
        return manifest

    align_stage, transcript = stage_align(audio_path, language=language)
    manifest.stages.append(align_stage)
    if align_stage.status != "success" or transcript is None:
        return manifest

    srt_path = str(out_dir / f"{basename}.srt")
    manifest.stages.append(stage_render_srt(transcript, output_path=srt_path))
    return manifest
