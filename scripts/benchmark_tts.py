#!/usr/bin/env python3
"""Repeatable TTS performance benchmark (PLAN.md Phase 6).

Measures cold start, warm latency, real-time factor, peak memory, and
output size for the native `mac-speech-tts` engine against four fixed
test texts. Prints a markdown table to stdout; diagnostics go to stderr.

Usage:
    .venv/bin/python scripts/benchmark_tts.py

This only exercises the native engine (always available offline, no
cloud, no model download) — there is no neural-engine comparison here
because no neural engine is installed in the base toolkit (see
docs/tts-benchmark.md for why Kokoro/Piper were evaluated by research
only, not installed, in this pass).
"""

from __future__ import annotations

import json
import resource
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from mac_speech.capabilities import find_tts_binary  # noqa: E402

TEST_TEXTS = {
    "short_command": "Stop the recording now.",
    "paragraph": (
        "Local speech synthesis on Apple Silicon runs entirely offline once the "
        "system voices are installed, which means no audio or text ever leaves "
        "this machine during a normal narration task."
    ),
    "narration_script": (
        "Welcome back to the show. Today we are going to walk through three "
        "practical techniques for keeping a command-line tool fast, predictable, "
        "and safe to use offline. First, we will look at how to avoid silent "
        "fallbacks. Second, we will cover explicit capability detection. "
        "Finally, we will talk about why local-first tools are worth the extra "
        "design effort."
    ),
    "long_article": " ".join(
        [
            "The history of local speech synthesis stretches back decades, long "
            "before cloud-based neural models made natural-sounding voices "
            "widely available over the network.",
            "Early formant synthesizers were intelligible but clearly "
            "mechanical, trading naturalness for the ability to run on modest "
            "hardware in real time.",
            "Concatenative synthesis improved naturalness by stitching together "
            "recorded speech units, at the cost of much larger voice data and "
            "less flexibility in prosody.",
            "Modern on-device neural text-to-speech, including the system "
            "voices used in this benchmark, closes much of the naturalness gap "
            "while still running entirely offline on a laptop-class chip.",
            "Measuring these systems fairly requires fixed test texts, repeated "
            "trials, and attention to real-time factor rather than a single "
            "anecdotal timing.",
            "This benchmark intentionally keeps its methodology simple and "
            "reproducible: four fixed texts, a native engine invocation per "
            "trial, and peak memory sampled from the operating system rather "
            "than estimated.",
        ]
    ),
}

TRIALS = 3


def run_once(binary: Path, text: str, output_path: Path) -> dict:
    start = time.monotonic()
    result = subprocess.run(
        [str(binary), "save", text, "--output", str(output_path), "--force"],
        capture_output=True,
        text=True,
    )
    elapsed = time.monotonic() - start
    if result.returncode != 0:
        raise RuntimeError(f"synthesis failed: {result.stdout} {result.stderr}")
    payload = json.loads(result.stdout)["result"]
    return {
        "wall_seconds": elapsed,
        "duration_seconds": payload["duration_seconds"],
        "file_size_bytes": payload["file_size_bytes"],
    }


def peak_rss_mb(binary: Path, text: str, output_path: Path) -> float | None:
    """Uses /usr/bin/time -l to sample peak resident set size (macOS)."""
    try:
        result = subprocess.run(
            ["/usr/bin/time", "-l", str(binary), "save", text, "--output", str(output_path), "--force"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None
    for line in result.stderr.splitlines():
        if "maximum resident set size" in line:
            try:
                return int(line.split()[0]) / (1024 * 1024)
            except (ValueError, IndexError):
                return None
    return None


def main() -> int:
    binary = find_tts_binary()
    if binary is None:
        print("No native TTS binary found; build it first (./install.sh).", file=sys.stderr)
        return 1

    print(f"# TTS performance benchmark\n")
    print(f"Engine: `{binary}`\n")
    print("| Text | Cold (s) | Warm avg (s) | Audio duration (s) | RTF (wall/audio) | Peak RSS (MB) | Output bytes |")
    print("| --- | --- | --- | --- | --- | --- | --- |")

    tmp_dir = Path("/private/tmp")
    for name, text in TEST_TEXTS.items():
        output_path = tmp_dir / f"benchmark-{name}.wav"
        print(f"running {name}...", file=sys.stderr)

        cold = run_once(binary, text, output_path)
        warm_trials = [run_once(binary, text, output_path) for _ in range(TRIALS)]
        warm_avg = sum(t["wall_seconds"] for t in warm_trials) / len(warm_trials)
        audio_duration = cold["duration_seconds"]
        rtf = cold["wall_seconds"] / audio_duration if audio_duration else float("nan")
        rss = peak_rss_mb(binary, text, output_path)
        rss_str = f"{rss:.1f}" if rss is not None else "n/a"

        print(
            f"| {name} | {cold['wall_seconds']:.3f} | {warm_avg:.3f} | "
            f"{audio_duration:.2f} | {rtf:.3f} | {rss_str} | {cold['file_size_bytes']} |"
        )
        output_path.unlink(missing_ok=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
