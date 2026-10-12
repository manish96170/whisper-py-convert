"""mac-speech: shared CLI for local macOS speech capabilities (STT/TTS).

Diagnostics and human-readable progress always go to stderr. stdout is
reserved for the requested output: human-readable text by default, or a
single JSON document when ``--json`` is passed — mirroring the existing
``whisper-py-convert.py`` convention so scripts can keep redirecting stdout.

Both ``tts`` (Phase 3) and ``stt`` (Phase 4) are implemented for real
(``mac_speech.tts``, ``mac_speech.stt``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, artifacts, stt, tts
from .capabilities import detect_capabilities
from .doctor import run_doctor
from .errors import ErrorCode, MacSpeechError
from .file_io import atomic_write_text, check_output_path
from .logging_utils import diagnostic
from .native_protocol import PROTOCOL_VERSION
from .stt import engine as stt_engine
from .tts import engine as tts_engine


def _cmd_version(args: argparse.Namespace) -> int:
    if args.json:
        print(json.dumps({"version": __version__, "protocol_version": PROTOCOL_VERSION}))
    else:
        print(f"mac-speech {__version__}")
    return 0


def _cmd_capabilities(args: argparse.Namespace) -> int:
    report = detect_capabilities()
    if args.json:
        print(json.dumps(report.to_dict()))
        return 0
    print(f"Platform: {report.platform.os_name} {report.platform.os_version} ({report.platform.machine})")
    for capability in report.capabilities:
        state = "available" if capability.available else "unavailable"
        suffix = f" — {capability.reason}" if capability.reason else ""
        print(f"- {capability.name}: {state}{suffix}")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    report = run_doctor()
    if args.json:
        print(json.dumps(report.to_dict()))
    else:
        print(f"Platform: {report.platform.os_name} {report.platform.os_version} ({report.platform.machine})")
        for check in report.checks:
            marker = "OK" if check.ok else "FAIL"
            print(f"[{marker}] {check.name}: {check.message}")
    return 0 if report.ok else 1


def _cmd_tui(args: argparse.Namespace) -> int:
    from .tui import launch

    return launch(locale=args.locale, timeout=args.timeout, demo=args.demo)


def _resolve_text_argument(args: argparse.Namespace) -> str:
    if args.stdin:
        if args.text is not None:
            raise MacSpeechError(
                code=ErrorCode.INVALID_ARGUMENT,
                message="Pass text as an argument or use --stdin, not both.",
            )
        return sys.stdin.read()
    if args.text is None:
        raise MacSpeechError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="Text is required.",
            remedy="Pass it as an argument, or use --stdin to read it from standard input.",
        )
    return args.text


# --- tts subcommands ----------------------------------------------------

def _cmd_tts_voices(args: argparse.Namespace) -> int:
    voices = tts.list_voices(language=args.language)
    if args.json:
        print(json.dumps({"voices": [v.to_dict() for v in voices], "count": len(voices)}))
        return 0
    for voice in voices:
        print(f"{voice.identifier}\t{voice.name}\t{voice.language}\t{voice.quality}")
    return 0


def _cmd_tts_personal_voice_status(args: argparse.Namespace) -> int:
    status = tts.personal_voice_status()
    if args.json:
        print(json.dumps({"authorization_status": status}))
    else:
        print(status)
    return 0


def _cmd_tts_speak(args: argparse.Namespace) -> int:
    text = _resolve_text_argument(args)
    result = tts.speak(
        text,
        voice=args.voice,
        rate=args.rate,
        language=args.language,
        timeout=args.timeout,
        track_for_control=not args.no_track,
    )
    if args.json:
        print(json.dumps(result.to_dict()))
    elif result.stopped_early:
        diagnostic("Stopped early.")
    return 0


def _cmd_tts_save(args: argparse.Namespace) -> int:
    text = _resolve_text_argument(args)
    if not args.output:
        raise MacSpeechError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="--output is required for `mac-speech tts save`.",
        )
    if getattr(args, "manifest", False):
        requested = Path(args.output)
        if not requested.suffix:
            requested = requested.with_suffix(f".{args.format}")
        check_output_path(artifacts.manifest_path_for(requested), force=args.force)
    result = tts.synthesize_to_file(
        text,
        output_path=args.output,
        voice=args.voice,
        rate=args.rate,
        language=args.language,
        format=args.format,
        force=args.force,
        timeout=args.timeout,
    )
    if getattr(args, "manifest", False):
        manifest = artifacts.build_manifest(
            Path(result.output_path),
            operation="tts_save",
            engine="mac-speech-tts",
            voice_identifier=result.voice_identifier,
            language=result.language,
            input_text=text,
        )
        manifest_file = artifacts.write_manifest(manifest, Path(result.output_path), force=args.force)
        diagnostic(f"Wrote manifest to {manifest_file}")
    if args.json:
        print(json.dumps(result.to_dict()))
    else:
        print(f"Saved {result.duration_seconds:.2f}s of audio to {result.output_path}")
    return 0


def _cmd_tts_stop(args: argparse.Namespace) -> int:
    tts.stop()
    if args.json:
        print(json.dumps({"status": "ok"}))
    else:
        print("Stop signal sent.")
    return 0


def _cmd_tts_pause(args: argparse.Namespace) -> int:
    tts.pause()
    if args.json:
        print(json.dumps({"status": "ok"}))
    else:
        print("Pause signal sent.")
    return 0


def _cmd_tts_resume(args: argparse.Namespace) -> int:
    tts.resume()
    if args.json:
        print(json.dumps({"status": "ok"}))
    else:
        print("Resume signal sent.")
    return 0


def _cmd_tts_batch(args: argparse.Namespace) -> int:
    from .batch import scenes_from_dict, synthesize_batch

    try:
        if args.input == "-":
            content = sys.stdin.read(8 * 1024 * 1024 + 1)
        else:
            with open(args.input, encoding="utf-8") as handle:
                content = handle.read(8 * 1024 * 1024 + 1)
        if len(content) > 8 * 1024 * 1024:
            raise MacSpeechError(code=ErrorCode.INVALID_ARGUMENT, message="Batch input exceeds the 8 Mi-character limit.")
        scenes = scenes_from_dict(json.loads(content))
    except (OSError, UnicodeError, json.JSONDecodeError) as failure:
        raise MacSpeechError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="Cannot read batch input as UTF-8 JSON.",
            remedy="Supply a readable scene JSON file, or --input - for stdin.",
        ) from failure
    result = synthesize_batch(
        scenes, output_dir=args.output_dir, workers=args.workers, force=args.force, timeout=args.timeout,
    )
    if args.json:
        print(json.dumps(result.to_dict()))
    else:
        for scene in result.scenes:
            print(f"[{scene.status}] {scene.basename}: {scene.output_path or scene.error or ''}")
        print(f"Batch report: {Path(result.output_dir) / 'batch.json'}")
    if result.termination_unconfirmed:
        return 1
    return 130 if result.cancelled else (0 if result.ok else 1)


def _cmd_tts(args: argparse.Namespace) -> int:
    if not getattr(args, "tts_command", None):
        raise MacSpeechError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="A tts subcommand is required: voices, speak, save, stop, pause, or resume.",
        )
    return args.tts_handler(args)


# --- stt subcommands -----------------------------------------------------

def _write_text_atomically(path: Path, content: str, *, force: bool) -> None:
    atomic_write_text(path, content, force=force)


def _write_manifest_if_requested(args: argparse.Namespace, output_path: Path, *, engine_name: str) -> None:
    if not getattr(args, "manifest", False):
        return
    manifest = artifacts.build_manifest(output_path, operation="stt_transcribe", engine=engine_name)
    manifest_file = artifacts.write_manifest(manifest, output_path, force=args.force)
    diagnostic(f"Wrote manifest to {manifest_file}")


def _cmd_stt_transcribe(args: argparse.Namespace) -> int:
    if (args.seg_ts or args.word_ts) and args.output_format not in ("srt", "webvtt"):
        raise MacSpeechError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="--seg-ts and --word-ts require --format srt or --format webvtt.",
        )
    if args.output:
        output = Path(args.output)
        check_output_path(output, force=args.force)
        if getattr(args, "manifest", False):
            check_output_path(artifacts.manifest_path_for(output), force=args.force)

    if args.output_format == "json":
        transcript = stt.transcribe_json(
            args.input, engine_name=args.engine, model=args.model, language=args.language, timeout=args.timeout
        )
        payload = json.dumps(transcript.to_dict())
        if args.output:
            output_path = Path(args.output)
            _write_text_atomically(output_path, payload + "\n", force=args.force)
            diagnostic(f"Saved transcript to {output_path}")
            _write_manifest_if_requested(args, output_path, engine_name=transcript.engine)
        else:
            print(payload)
        return 0

    if args.output_format in ("srt", "webvtt"):
        transcribe_fn = stt.transcribe_webvtt if args.output_format == "webvtt" else stt.transcribe_srt
        result = transcribe_fn(
            args.input,
            word_timestamps=args.word_ts,
            engine_name=args.engine,
            model=args.model,
            language=args.language,
            timeout=args.timeout,
        )
    else:
        result = stt.transcribe_text(
            args.input, engine_name=args.engine, model=args.model, language=args.language, timeout=args.timeout
        )

    if args.output:
        output_path = Path(args.output)
        _write_text_atomically(output_path, result.content, force=args.force)
        diagnostic(f"Saved transcript to {output_path}")
        _write_manifest_if_requested(args, output_path, engine_name=result.engine)
        if args.json:
            print(json.dumps(result.to_dict()))
        return 0

    if args.json:
        print(json.dumps(result.to_dict()))
    else:
        sys.stdout.write(result.content)
    return 0


def _cmd_stt(args: argparse.Namespace) -> int:
    if not getattr(args, "stt_command", None):
        raise MacSpeechError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="An stt subcommand is required: transcribe.",
        )
    return args.stt_handler(args)


# --- export (Phases 8-10) -------------------------------------------------

def _cmd_export(args: argparse.Namespace) -> int:
    from .export import ExportDestination, get_exporter

    exporter = get_exporter(args.to)
    options: dict = {}
    if args.as_dm:
        options["as_dm"] = True
    if args.idempotency_key:
        options["idempotency_key"] = args.idempotency_key
    if args.link:
        options["link"] = args.link
    if args.text:
        options["text"] = args.text
    if args.force:
        options["force"] = True
    destination = ExportDestination(provider=args.to, uri=args.destination, options=options)
    source_path = Path(args.artifact)

    if args.preview:
        preview = exporter.preview(source_path, destination)
        if args.json:
            print(json.dumps(preview.to_dict()))
        else:
            print(f"Would export {preview.source_path} to {preview.destination_description}")
            print(f"  estimated size: {preview.estimated_size_bytes} bytes")
            print(f"  will overwrite: {preview.will_overwrite}")
        return 0

    result = exporter.upload(source_path, destination, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(result.to_dict()))
    else:
        verb = "Would export" if args.dry_run else "Exported"
        print(f"{verb} {result.source_path} to {result.destination_description} (verified={result.verified})")
        if result.remote_reference:
            print(f"  reference: {result.remote_reference}")
    return 0 if result.success else 1


# --- workflow (Phase 11) --------------------------------------------------

def _cmd_workflow_narrate(args: argparse.Namespace) -> int:
    from . import workflow

    text = _resolve_text_argument(args)
    manifest = workflow.run_narration_pipeline(
        text,
        output_dir=args.output_dir,
        basename=args.basename,
        voice=args.voice,
        language=args.language,
        align=not args.no_align,
        force=args.force,
        persist_manifest=True,
    )
    manifest_path = Path(args.output_dir).expanduser().resolve() / f"{args.basename}.workflow.json"

    if args.json:
        print(json.dumps(manifest.to_dict()))
    else:
        for stage in manifest.stages:
            marker = "OK" if stage.status == "success" else "FAIL"
            print(f"[{marker}] {stage.name}: {stage.output_path or stage.error}")
        print(f"Manifest: {manifest_path}")
    return 0 if manifest.ok else 1


def _cmd_workflow(args: argparse.Namespace) -> int:
    if not getattr(args, "workflow_command", None):
        raise MacSpeechError(
            code=ErrorCode.INVALID_ARGUMENT,
            message="A workflow subcommand is required: narrate.",
        )
    return args.workflow_handler(args)


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON on stdout")


def _add_speech_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("text", nargs="?", help="text to synthesize; omit if using --stdin")
    parser.add_argument("--stdin", action="store_true", help="read text from standard input")
    parser.add_argument("--voice", help="voice identifier (default: system default voice)")
    parser.add_argument("--language", help="BCP-47 locale, used to pick a voice if --voice is omitted")
    parser.add_argument("--rate", type=float, help="speech rate between 0.0 and 1.0")
    parser.add_argument(
        "--timeout",
        type=float,
        default=tts_engine.DEFAULT_TIMEOUT_SECONDS,
        help=f"safety timeout in seconds (default: {tts_engine.DEFAULT_TIMEOUT_SECONDS:.0f})",
    )


def _build_tts_subparser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    tts_parser = subparsers.add_parser("tts", help="text-to-speech")
    tts_parser.set_defaults(handler=_cmd_tts)
    tts_subparsers = tts_parser.add_subparsers(dest="tts_command")

    voices_parser = tts_subparsers.add_parser("voices", help="list available voices")
    _add_json_flag(voices_parser)
    voices_parser.add_argument("--language", help="filter by BCP-47 locale")
    voices_parser.set_defaults(tts_handler=_cmd_tts_voices)

    personal_voice_status_parser = tts_subparsers.add_parser(
        "personal-voice-status", help="report (never request) Personal Voice authorization status"
    )
    _add_json_flag(personal_voice_status_parser)
    personal_voice_status_parser.set_defaults(tts_handler=_cmd_tts_personal_voice_status)

    speak_parser = tts_subparsers.add_parser("speak", help="speak text through the default audio output")
    _add_json_flag(speak_parser)
    _add_speech_input_args(speak_parser)
    speak_parser.add_argument(
        "--no-track",
        action="store_true",
        help="do not write a PID file; `mac-speech tts stop/pause/resume` cannot target this call",
    )
    speak_parser.set_defaults(tts_handler=_cmd_tts_speak)

    save_parser = tts_subparsers.add_parser("save", help="synthesize text to an audio file")
    _add_json_flag(save_parser)
    _add_speech_input_args(save_parser)
    save_parser.add_argument("--output", help="output file path")
    save_parser.add_argument(
        "--format", choices=("wav", "aiff", "caf"), default="wav", help="output container (default: wav)"
    )
    save_parser.add_argument("--force", action="store_true", help="overwrite an existing output file")
    save_parser.add_argument(
        "--manifest", action="store_true", help="also write a <output>.manifest.json sidecar"
    )
    save_parser.set_defaults(tts_handler=_cmd_tts_save)

    stop_parser = tts_subparsers.add_parser("stop", help="stop a speak() call tracked via its PID file")
    _add_json_flag(stop_parser)
    stop_parser.set_defaults(tts_handler=_cmd_tts_stop)

    pause_parser = tts_subparsers.add_parser("pause", help="pause a speak() call tracked via its PID file")
    _add_json_flag(pause_parser)
    pause_parser.set_defaults(tts_handler=_cmd_tts_pause)

    resume_parser = tts_subparsers.add_parser("resume", help="resume a paused speak() call")
    _add_json_flag(resume_parser)
    resume_parser.set_defaults(tts_handler=_cmd_tts_resume)

    batch_parser = tts_subparsers.add_parser("batch", help="bounded local WAV synthesis for multiple scenes")
    _add_json_flag(batch_parser)
    batch_parser.add_argument("--input", required=True, help="versioned UTF-8 scene JSON; - for stdin")
    batch_parser.add_argument("--output-dir", required=True, help="trusted local batch workspace")
    batch_parser.add_argument("--workers", type=int, default=1, help="worker cap (1–4, default: 1)")
    batch_parser.add_argument("--timeout", type=float, default=tts_engine.DEFAULT_TIMEOUT_SECONDS, help="per-scene native timeout")
    batch_parser.add_argument("--force", action="store_true", help="explicitly replace regular scene/report outputs")
    batch_parser.set_defaults(tts_handler=_cmd_tts_batch)

    return tts_parser


def _build_stt_subparser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    stt_parser = subparsers.add_parser("stt", help="speech-to-text")
    stt_parser.set_defaults(handler=_cmd_stt)
    stt_subparsers = stt_parser.add_subparsers(dest="stt_command")

    transcribe_parser = stt_subparsers.add_parser("transcribe", help="transcribe an audio/video file")
    _add_json_flag(transcribe_parser)
    transcribe_parser.add_argument("input", help="audio/video file, e.g. recording.mp3 or recording.mp4")
    transcribe_parser.add_argument(
        "--format", dest="output_format", choices=("text", "srt", "webvtt", "json"), default="text",
        help="transcript content format (default: text)",
    )
    timestamp_group = transcribe_parser.add_mutually_exclusive_group()
    timestamp_group.add_argument(
        "--seg-ts", action="store_true", help="segment-level timestamps (requires --format srt or webvtt)"
    )
    timestamp_group.add_argument(
        "--word-ts", action="store_true", help="word-level timestamps (requires --format srt or webvtt)"
    )
    transcribe_parser.add_argument(
        "--engine", choices=("auto", "apple", "windows", "faster-whisper"), default="auto",
        help="backend (default: auto; native OS backend first)",
    )
    transcribe_parser.add_argument("--model", help="faster-whisper model; ignored by native engines")
    transcribe_parser.add_argument("--language", help="language code such as en or en-US")
    transcribe_parser.add_argument("-o", "--output", help="write the transcript here instead of stdout")
    transcribe_parser.add_argument("--force", action="store_true", help="overwrite an existing --output file")
    transcribe_parser.add_argument(
        "--manifest", action="store_true", help="also write a <output>.manifest.json sidecar (requires --output)"
    )
    transcribe_parser.add_argument(
        "--timeout", type=float, default=stt_engine.DEFAULT_TIMEOUT_SECONDS,
        help=f"safety timeout in seconds (default: {stt_engine.DEFAULT_TIMEOUT_SECONDS:.0f})",
    )
    transcribe_parser.set_defaults(stt_handler=_cmd_stt_transcribe)

    return stt_parser


def _build_export_subparser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    export_parser = subparsers.add_parser(
        "export", help="export a generated artifact (local copy, Google Drive, S3, or Slack)"
    )
    _add_json_flag(export_parser)
    export_parser.add_argument("artifact", help="path to a previously generated artifact file")
    export_parser.add_argument(
        "--to", required=True, choices=("local", "gdrive", "s3", "slack"), help="export provider"
    )
    export_parser.add_argument(
        "--destination", required=True,
        help="provider-specific destination: a local path, a Drive folder ID, an s3://bucket/prefix/ URI, "
        "or a Slack channel/user ID",
    )
    export_parser.add_argument("--preview", action="store_true", help="describe the export without performing it")
    export_parser.add_argument("--dry-run", action="store_true", help="resolve and validate, but transfer nothing")
    export_parser.add_argument("--force", action="store_true", help="overwrite an existing destination (local only)")
    export_parser.add_argument("--as-dm", action="store_true", help="Slack only: --destination is a user ID for a DM")
    export_parser.add_argument("--text", help="Slack only: message text (default: an auto-generated summary)")
    export_parser.add_argument("--link", help="Slack only: a URL to include in the summary message")
    export_parser.add_argument("--idempotency-key", help="Slack only: avoid duplicate posts on retry")
    export_parser.set_defaults(handler=_cmd_export)
    return export_parser


def _build_workflow_subparser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    workflow_parser = subparsers.add_parser("workflow", help="narration pipeline: text -> audio -> alignment -> SRT")
    workflow_parser.set_defaults(handler=_cmd_workflow)
    workflow_subparsers = workflow_parser.add_subparsers(dest="workflow_command")

    narrate_parser = workflow_subparsers.add_parser(
        "narrate", help="run the text -> audio -> alignment -> SRT pipeline for one scene/paragraph"
    )
    _add_json_flag(narrate_parser)
    narrate_parser.add_argument("text", nargs="?", help="narration text; omit if using --stdin")
    narrate_parser.add_argument("--stdin", action="store_true", help="read text from standard input")
    narrate_parser.add_argument("--output-dir", required=True, help="directory for generated artifacts")
    narrate_parser.add_argument("--basename", default="narration", help="base filename for artifacts (default: narration)")
    narrate_parser.add_argument("--voice", help="voice identifier (default: system default voice)")
    narrate_parser.add_argument("--language", help="BCP-47 locale")
    narrate_parser.add_argument(
        "--no-align", action="store_true", help="skip the STT-roundtrip alignment and SRT stages"
    )
    narrate_parser.add_argument("--force", action="store_true", help="overwrite existing output files")
    narrate_parser.set_defaults(workflow_handler=_cmd_workflow_narrate)

    return workflow_parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mac-speech",
        description="Local macOS speech toolkit: capability discovery, diagnostics, STT, and TTS.",
    )
    subparsers = parser.add_subparsers(dest="command")

    json_flag = argparse.ArgumentParser(add_help=False)
    _add_json_flag(json_flag)

    version_parser = subparsers.add_parser("version", parents=[json_flag], help="print the mac-speech package version")
    version_parser.set_defaults(handler=_cmd_version)

    capabilities_parser = subparsers.add_parser(
        "capabilities", parents=[json_flag], help="report detected STT/TTS capabilities"
    )
    capabilities_parser.set_defaults(handler=_cmd_capabilities)

    doctor_parser = subparsers.add_parser(
        "doctor", parents=[json_flag], help="diagnose missing binaries and unsupported environments"
    )
    doctor_parser.set_defaults(handler=_cmd_doctor)

    tui_parser = subparsers.add_parser("tui", help="optional read-only speech dashboard (requires tui extra)")
    tui_parser.add_argument("--locale", default="en-US", help="locale for read-only Apple readiness queries")
    tui_parser.add_argument("--timeout", type=float, default=8.0, help="per-query timeout, 0 < seconds <= 30")
    tui_parser.add_argument("--demo", action="store_true", help="fictional demonstration data; no native processes")
    tui_parser.set_defaults(handler=_cmd_tui)

    _build_tts_subparser(subparsers)
    _build_stt_subparser(subparsers)
    _build_export_subparser(subparsers)
    _build_workflow_subparser(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help(sys.stderr)
        return 2

    # --json is defined per-subparser (including per tts sub-subparser),
    # so it is always present on `args` by the time a handler runs; the
    # top-level namespace has it only when a leaf subcommand set it.
    as_json = getattr(args, "json", False)
    try:
        return args.handler(args)
    except MacSpeechError as exc:
        if as_json:
            print(json.dumps({"error": exc.to_dict()}))
        else:
            diagnostic(f"Error: {exc.message}")
            if exc.remedy:
                diagnostic(exc.remedy)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
