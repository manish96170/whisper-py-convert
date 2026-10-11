#!/usr/bin/env python3
"""Local narration sample: text -> WAV -> Apple STT round-trip -> SRT.

Run with the installed Python wrapper; see examples/README.md. The output
directory must be new. No playback, export, credentials, or model download
is performed. --synthesize-only does not call STT at all.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from contextlib import redirect_stderr
from pathlib import Path

from mac_speech import workflow
from mac_speech.stt.models import Transcript


_STAGE_FAILURES = {
    "synthesize": (
        "Synthesis failed. Run `mac-speech doctor --json`; install the native TTS "
        "engine with `./install.sh tts` and check the requested language/output permissions."
    ),
    "align": (
        "Apple STT round-trip alignment failed or returned no usable timed cues; generated audio is retained. "
        "Run `mac-speech doctor --json`. Apple STT requires macOS 27+ and available "
        "locale assets; known locale/reservation errors are documented in docs/risk-register.md "
        "(risk #19). Use --synthesize-only in a new output directory for TTS alone, "
        "or retry stage_align on the retained WAV as shown in docs/workflow.md."
    ),
    "render_srt": (
        "SRT rendering failed; generated audio is retained. Check output permissions "
        "and retry the alignment/SRT stages as shown in docs/workflow.md."
    ),
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="short public sample text (visible in shell history/process arguments)")
    source.add_argument("--text-file", type=Path, help="UTF-8 text file; use - to read stdin")
    parser.add_argument("--output-dir", type=Path, required=True, help="NEW directory; existing paths are never reused")
    parser.add_argument("--language", default="en-US", help="BCP-47 locale for native TTS and Apple STT (default: en-US)")
    parser.add_argument("--synthesize-only", action="store_true", help="offline TTS quickstart: save WAV/manifest, skip STT/SRT")
    return parser


def _error(code: str, message: str, exit_code: int) -> int:
    print(json.dumps({"ok": False, "error": {"code": code, "message": message}}))
    print(message, file=sys.stderr)
    return exit_code


def _record_stage(
    manifest: workflow.WorkflowManifest, stage: workflow.WorkflowStage, manifest_path: Path
) -> None:
    # Native exception strings can contain input/transcript text. Keep only
    # stage-level guidance in this sample's manifest and console output.
    if stage.status != "success":
        stage.error = _STAGE_FAILURES[stage.name]
    manifest.stages.append(stage)
    manifest.write(manifest_path)


def _has_usable_cues(transcript: Transcript) -> bool:
    # Match the renderer's word-first, segment-fallback selection without
    # accepting an empty/whitespace-only SRT or inventing missing timing.
    cues: list[tuple[float, float, str]] = []
    for segment in transcript.segments:
        if segment.words:
            cues.extend((word.start, word.end, word.text) for word in segment.words if word.text)
        elif segment.text:
            cues.append((segment.start, segment.end, segment.text))
    return bool(cues) and all(
        text.strip() and math.isfinite(start) and math.isfinite(end) and 0 <= start < end
        for start, end, text in cues
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.text_file is not None:
            text = sys.stdin.read() if str(args.text_file) == "-" else args.text_file.read_text(encoding="utf-8")
        else:
            text = args.text
    except (OSError, UnicodeError):
        return _error("invalid_input", "Cannot read input. Supply a readable UTF-8 text file or stdin.", 2)
    if not text.strip():
        return _error("invalid_input", "Narration text must not be empty or whitespace-only.", 2)

    # The SRT/manifest helpers can replace files. Claim an entirely new run
    # directory exclusively, rather than risk overwriting a previous run's
    # audio, subtitles, or failure manifest. There is deliberately no --force.
    output_dir = args.output_dir.expanduser().absolute()
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        return _error("output_exists", "Output path already exists. Choose a new --output-dir; nothing was changed.", 3)
    except OSError:
        return _error("output_error", "Cannot create output directory. Check its parent directory and permissions.", 1)

    manifest = workflow.new_manifest(text)
    manifest_path = output_dir / "narration.workflow.json"
    audio_path = output_dir / "narration.wav"
    try:
        # The adapters forward captured native stderr, which is not a
        # privacy-safe log contract. Suppress it; report sanitized failures
        # after leaving this context. Never print the source or transcript.
        with open(os.devnull, "w", encoding="utf-8") as quiet, redirect_stderr(quiet):
            stage = workflow.stage_synthesize(text, output_path=str(audio_path), language=args.language)
            _record_stage(manifest, stage, manifest_path)
            if stage.status == "success" and not args.synthesize_only:
                # Explicit native selection avoids auto fallback to a neural
                # backend that could need extra dependencies/model downloads.
                stage, transcript = workflow.stage_align(str(audio_path), engine_name="apple", language=args.language)
                if stage.status == "success" and (transcript is None or not _has_usable_cues(transcript)):
                    stage.status = "failed"
                _record_stage(manifest, stage, manifest_path)
                if stage.status == "success" and transcript is not None:
                    stage = workflow.stage_render_srt(transcript, output_path=str(output_dir / "narration.srt"))
                    _record_stage(manifest, stage, manifest_path)
    except OSError:
        return _error(
            "manifest_write_failed",
            "Cannot save workflow manifest. Any generated audio was retained; check output permissions before retrying.",
            1,
        )

    aligned = any(stage.name == "align" and stage.status == "success" for stage in manifest.stages)
    print(json.dumps({
        "ok": manifest.ok,
        "mode": "synthesize_only" if args.synthesize_only else "narration",
        "manifest_path": str(manifest_path),
        "timing_method": "stt_roundtrip_approximation" if aligned else "not_computed",
        "stages": [
            {"name": stage.name, "status": stage.status, "output_path": stage.output_path, "error": stage.error}
            for stage in manifest.stages
        ],
    }))
    for stage in manifest.stages:
        if stage.status != "success":
            print(stage.error, file=sys.stderr)
    return 0 if manifest.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
