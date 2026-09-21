#!/usr/bin/env python3
"""Local audio/video transcription with native and faster-whisper backends."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_PACKAGE = "faster-whisper==1.2.1"
REQUIRED_VERSION = "1.2.1"
APPLE_BINARY_NAME = "whisper-py-convert-apple"
WINDOWS_BINARY_NAME = "whisper-py-convert-windows.exe"
SUPPORTED_MODELS = (
    "tiny.en", "tiny", "base.en", "base", "small.en", "small",
    "medium.en", "medium", "large-v1", "large-v2", "large-v3", "large",
)


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Segment:
    text: str
    start: float
    end: float
    words: list[Word] = field(default_factory=list)


@dataclass
class Transcript:
    segments: list[Segment]

    @property
    def text(self) -> str:
        body = "\n".join(s.text.strip() for s in self.segments if s.text.strip()).strip()
        return body + "\n" if body else ""


def package_version() -> str | None:
    try:
        return importlib.metadata.version("faster-whisper")
    except importlib.metadata.PackageNotFoundError:
        return None


def ensure_dependency() -> None:
    version = package_version()
    if version == REQUIRED_VERSION:
        return
    message = "not installed" if version is None else f"version {version} is installed"
    print(f"faster-whisper {message}; installing {REQUIRED_PACKAGE}...", file=sys.stderr)
    command = [sys.executable, "-m", "pip", "install", REQUIRED_PACKAGE]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Could not install faster-whisper 1.2.1. Try manually: {' '.join(command)}") from exc
    os.execv(sys.executable, [sys.executable, *sys.argv])


def model_cache_dir(model: str) -> Path:
    repo = f"models--Systran--faster-whisper-{model}"
    return Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub" / repo


def model_is_cached(model: str) -> bool:
    snapshots = model_cache_dir(model) / "snapshots"
    return snapshots.is_dir() and any(snapshots.iterdir())


def hf_token() -> str | None:
    token = os.environ.get("HF_TOKEN", "").strip()
    return token or None


def find_apple_binary() -> Path | None:
    script_dir = Path(__file__).resolve().parent
    candidates = (
        script_dir / APPLE_BINARY_NAME,
        script_dir / ".build" / "out" / "Products" / "Release" / APPLE_BINARY_NAME,
        script_dir / ".build" / "release" / APPLE_BINARY_NAME,
        script_dir / ".build" / "arm64-apple-macosx" / "release" / APPLE_BINARY_NAME,
    )
    return next((path for path in candidates if path.is_file() and os.access(path, os.X_OK)), None)


def find_windows_binary() -> Path | None:
    script_dir = Path(__file__).resolve().parent
    candidates = (script_dir / WINDOWS_BINARY_NAME, script_dir / "windows" / "publish" / WINDOWS_BINARY_NAME)
    return next((path for path in candidates if path.is_file()), None)


def print_status(model: str | None = None) -> None:
    print(f"Python: {sys.executable}")
    print(f"faster-whisper: {package_version() or 'not installed'}")
    print(f"HF_TOKEN: {'configured' if hf_token() else 'not configured'}")
    print(f"Apple Speech backend: {find_apple_binary() or 'not built'}")
    print(f"Windows AI Speech backend: {find_windows_binary() or 'not installed'}")
    print(f"Model cache: {Path.home() / '.cache' / 'huggingface' / 'hub'}")
    models = (model,) if model else SUPPORTED_MODELS
    for name in models:
        print(f"{name}: {'downloaded' if model_is_cached(name) else 'not downloaded'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whisper-py-convert",
        description="Transcribe audio or video locally with native OS speech or faster-whisper.",
    )
    parser.add_argument("input", nargs="?", type=Path, help="audio/video file, for example recording.mp3 or recording.mp4")
    parser.add_argument("--model", default="small.en", choices=SUPPORTED_MODELS, help="faster-whisper model (default: small.en)")
    parser.add_argument("--engine", choices=("auto", "apple", "windows", "faster-whisper"), default="auto", help="backend (default: auto; native OS backend first)")
    parser.add_argument("-o", "--output", type=Path, help="write output here instead of stdout")
    parser.add_argument("--language", help="language code such as en or en-US")
    parser.add_argument("--device", choices=("auto", "cpu"), default="cpu")
    parser.add_argument("--compute-type", default="int8", help="faster-whisper compute type (default: int8)")
    parser.add_argument("--srt", action="store_true", help="write SubRip subtitle output")
    timestamp_group = parser.add_mutually_exclusive_group()
    timestamp_group.add_argument("--seg-ts", action="store_true", help="use segment timestamps in SRT output")
    timestamp_group.add_argument("--word-ts", action="store_true", help="use word timestamps in SRT output")
    parser.add_argument("--check", action="store_true", help="show installed runtimes and cached models")
    return parser


def resolve_engine(requested: str) -> str:
    if requested == "apple":
        if not find_apple_binary():
            raise SystemExit("Apple Speech backend is not built. Run ./install.sh on macOS 27+.")
        return "apple"
    if requested == "windows":
        if not find_windows_binary():
            raise SystemExit("Windows AI Speech backend is not installed. See windows/README.md.")
        return "windows"
    if requested == "auto":
        if find_apple_binary():
            return "apple"
        if find_windows_binary():
            return "windows"
    return "faster-whisper"


def transcribe_faster_whisper(args: argparse.Namespace) -> Transcript:
    if not args.input.exists() or not args.input.is_file():
        raise SystemExit(f"Input file does not exist or is not a file: {args.input}")
    from faster_whisper import WhisperModel

    print(f"Loading model {args.model}...", file=sys.stderr)
    token = hf_token()
    if token:
        print("Using HF_TOKEN for Hugging Face model download/authentication.", file=sys.stderr)
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type, use_auth_token=token)
    print(f"Transcribing {args.input}...", file=sys.stderr)
    segments, _info = model.transcribe(str(args.input), language=args.language, word_timestamps=args.word_ts)
    result: list[Segment] = []
    for segment in segments:
        words = [Word(word.word.strip(), word.start, word.end) for word in (segment.words or []) if word.word.strip()]
        result.append(Segment(segment.text.strip(), segment.start, segment.end, words))
    return Transcript(result)


def parse_native_json(raw: str) -> Transcript:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Native speech backend returned invalid JSON: {exc}") from exc
    segments = []
    for item in payload.get("segments", []):
        words = [Word(w["text"], float(w["start"]), float(w["end"])) for w in item.get("words", [])]
        segments.append(Segment(item["text"], float(item["start"]), float(item["end"]), words))
    return Transcript(segments)


def run_native_backend(binary: Path, args: argparse.Namespace, *, windows: bool = False) -> Transcript:
    if not args.input.exists() or not args.input.is_file():
        raise SystemExit(f"Input file does not exist or is not a file: {args.input}")
    if windows and args.srt:
        raise SystemExit("Windows native backend currently supports plain transcript output only; use faster-whisper for SRT.")
    command = [str(binary)]
    if args.language and not windows:
        command.extend(["--language", args.language])
    if windows:
        command.append(str(args.input))
    else:
        command.extend(["--format", "json", "--timestamp-mode", "word" if args.word_ts else "segment", str(args.input)])
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    if windows:
        return Transcript([Segment(result.stdout.strip(), 0.0, 0.0)])
    return parse_native_json(result.stdout)


def srt_timestamp(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def render_srt(transcript: Transcript, *, word_timestamps: bool) -> str:
    cues: list[tuple[float, float, str]] = []
    for segment in transcript.segments:
        if word_timestamps and segment.words:
            cues.extend((word.start, word.end, word.text) for word in segment.words if word.text)
        elif segment.text:
            cues.append((segment.start, segment.end, segment.text))
    return "\n".join(
        f"{index}\n{srt_timestamp(start)} --> {srt_timestamp(end)}\n{text}\n"
        for index, (start, end, text) in enumerate(cues, 1)
    )


def main() -> int:
    args = build_parser().parse_args()
    if args.check:
        print_status(args.model)
        return 0
    if args.input is None:
        raise SystemExit("input is required unless --check is used")
    if (args.seg_ts or args.word_ts) and not args.srt:
        raise SystemExit("--seg-ts and --word-ts require --srt")

    engine = resolve_engine(args.engine)
    print(f"Engine: {engine}", file=sys.stderr)
    if engine == "apple":
        transcript = run_native_backend(find_apple_binary(), args)  # type: ignore[arg-type]
    elif engine == "windows":
        transcript = run_native_backend(find_windows_binary(), args, windows=True)  # type: ignore[arg-type]
    else:
        ensure_dependency()
        transcript = transcribe_faster_whisper(args)

    output = render_srt(transcript, word_timestamps=args.word_ts) if args.srt else transcript.text
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"Saved transcript to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
