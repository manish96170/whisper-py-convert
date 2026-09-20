#!/usr/bin/env python3
"""Offline audio/video transcription with faster-whisper.

Examples:
    whisper-py-convert --model small.en recording.mp3 > transcript.txt
    whisper-py-convert --model medium.en recording.mp4 --output transcript.txt
    whisper-py-convert --check
"""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path


REQUIRED_PACKAGE = "faster-whisper==1.2.1"
REQUIRED_VERSION = "1.2.1"
APPLE_BINARY_NAME = "whisper-py-convert-apple"
SUPPORTED_MODELS = (
    "tiny.en",
    "tiny",
    "base.en",
    "base",
    "small.en",
    "small",
    "medium.en",
    "medium",
    "large-v1",
    "large-v2",
    "large-v3",
    "large",
)


def package_version() -> str | None:
    try:
        return importlib.metadata.version("faster-whisper")
    except importlib.metadata.PackageNotFoundError:
        return None


def ensure_dependency() -> None:
    """Install the pinned runtime once, then continue in the same interpreter."""
    version = package_version()
    if version == REQUIRED_VERSION:
        return

    if version is None:
        print(f"faster-whisper is not installed; installing {REQUIRED_PACKAGE}...", file=sys.stderr)
    else:
        print(
            f"faster-whisper {version} is installed; upgrading to {REQUIRED_PACKAGE}...",
            file=sys.stderr,
        )

    command = [sys.executable, "-m", "pip", "install", REQUIRED_PACKAGE]
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Could not install faster-whisper 1.2.1. "
            f"Try manually: {' '.join(command)}"
        ) from exc

    # The current Python process may have cached the failed import state.
    os.execv(sys.executable, [sys.executable, *sys.argv])


def model_cache_dir(model: str) -> Path:
    repo = f"models--Systran--faster-whisper-{model}"
    return Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub" / repo


def model_is_cached(model: str) -> bool:
    cache = model_cache_dir(model)
    snapshots = cache / "snapshots"
    return snapshots.is_dir() and any(snapshots.iterdir())


def hf_token() -> str | None:
    """Return an optional Hugging Face token without ever printing it."""
    token = os.environ.get("HF_TOKEN", "").strip()
    return token or None


def print_status(model: str | None = None) -> None:
    version = package_version()
    print(f"Python: {sys.executable}")
    print(f"faster-whisper: {version or 'not installed'}")
    print(f"HF_TOKEN: {'configured' if hf_token() else 'not configured'}")
    apple_binary = find_apple_binary()
    print(f"Apple Speech backend: {apple_binary or 'not built'}")
    print(f"Model cache: {Path.home() / '.cache' / 'huggingface' / 'hub'}")
    models = (model,) if model else SUPPORTED_MODELS
    for name in models:
        print(f"{name}: {'downloaded' if model_is_cached(name) else 'not downloaded'}")
    print("Audio/video formats: handled by faster-whisper/PyAV")


def find_apple_binary() -> Path | None:
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / APPLE_BINARY_NAME,
        script_dir / ".build" / "out" / "Products" / "Release" / APPLE_BINARY_NAME,
        script_dir / ".build" / "release" / APPLE_BINARY_NAME,
        script_dir / ".build" / "arm64-apple-macosx" / "release" / APPLE_BINARY_NAME,
    ]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def resolve_engine(requested: str) -> str:
    if requested == "apple":
        if find_apple_binary() is None:
            raise SystemExit(
                "Apple Speech backend is not built. Run ./install.sh on macOS 27+, "
                "or use --engine faster-whisper."
            )
        return "apple"
    if requested == "auto" and find_apple_binary() is not None:
        return "apple"
    return "faster-whisper"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whisper-py-convert",
        description="Transcribe audio or video locally with faster-whisper.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        help="audio/video file, for example recording.mp3 or recording.mp4",
    )
    parser.add_argument(
        "--model",
        default="small.en",
        choices=SUPPORTED_MODELS,
        help="Whisper model; English recordings can use the .en variants (default: small.en)",
    )
    parser.add_argument(
        "--engine",
        choices=("auto", "apple", "faster-whisper"),
        default="auto",
        help="transcription backend (default: auto; Apple first when built)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="write transcript here instead of stdout",
    )
    parser.add_argument(
        "--language",
        help="language code such as en; omit to let Whisper detect it",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu"),
        default="cpu",
        help="inference device (default: cpu; Apple Silicon uses optimized CPU execution here)",
    )
    parser.add_argument(
        "--compute-type",
        default="int8",
        help="faster-whisper compute type (default: int8)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="show installed runtime and cached model status, without transcribing",
    )
    return parser


def transcribe(args: argparse.Namespace) -> str:
    if not args.input.exists():
        raise SystemExit(f"Input file does not exist: {args.input}")
    if not args.input.is_file():
        raise SystemExit(f"Input is not a file: {args.input}")

    # Import only after dependency bootstrapping has completed.
    from faster_whisper import WhisperModel

    print(f"Loading model {args.model}...", file=sys.stderr)
    token = hf_token()
    if token:
        print("Using HF_TOKEN for Hugging Face model download/authentication.", file=sys.stderr)
    model = WhisperModel(
        args.model,
        device=args.device,
        compute_type=args.compute_type,
        use_auth_token=token,
    )
    print(f"Transcribing {args.input}...", file=sys.stderr)
    segments, _info = model.transcribe(str(args.input), language=args.language)
    return "\n".join(segment.text.strip() for segment in segments).strip() + "\n"


def transcribe_with_apple(args: argparse.Namespace) -> str:
    binary = find_apple_binary()
    if binary is None:
        raise SystemExit("Apple Speech backend is not built.")
    command = [str(binary)]
    if args.language:
        command.extend(["--language", args.language])
    command.append(str(args.input))
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    return result.stdout


def main() -> int:
    args = build_parser().parse_args()

    if args.check:
        print_status(args.model)
        return 0
    if args.input is None:
        raise SystemExit("input is required unless --check is used")

    engine = resolve_engine(args.engine)
    print(f"Engine: {engine}", file=sys.stderr)
    if engine == "apple":
        transcript = transcribe_with_apple(args)
    else:
        ensure_dependency()
        transcript = transcribe(args)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(transcript, encoding="utf-8")
        print(f"Saved transcript to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(transcript)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
