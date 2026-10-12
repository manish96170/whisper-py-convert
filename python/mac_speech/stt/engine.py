"""Subprocess engine wrapper for STT.

Per docs/decisions/ADR-001-repository-and-module-boundaries.md, this
module never imports or forks `whisper-py-convert.py`. Instead:

* `text`/`srt` output formats shell out to the existing, unmodified
  `whisper-py-convert` entrypoint exactly as a user would run it — same
  flags, same stdout/stderr behavior, same engine auto-resolution. This
  trivially satisfies "preserve existing input/output behavior" because
  nothing about that tool's behavior is reinterpreted.
* `json` output format needs genuine structured segments/words, which
  `whisper-py-convert.py` itself does not expose as a CLI format. For the
  Apple engine, this module calls the existing `whisper-py-convert-apple`
  binary *directly* (bypassing the Python wrapper) and parses its real
  native JSON — exactly the "shells out to the existing Apple/Windows
  binaries and reuses the existing JSON contract" approach the ADR
  describes. For the Windows engine (plain text only, no JSON/SRT
  support) and the faster-whisper engine (no JSON-capable binary at all),
  it derives a best-effort `Transcript` from plain text or a parsed SRT,
  documented as such rather than claimed to be a native capability.
"""

from __future__ import annotations

import json as json_module
import re
import subprocess
import sys
from pathlib import Path

from ..capabilities import find_apple_stt_binary, find_whisper_py_convert, find_windows_stt_binary
from ..errors import ErrorCode, MacSpeechError
from ..logging_utils import diagnostic
from .models import Segment, TranscribeResult, Transcript, Word

DEFAULT_TIMEOUT_SECONDS = 300.0  # STT can take a while for longer recordings.

_ENGINE_LINE_RE = re.compile(r"^Engine:\s*(\S+)")


def resolve_whisper_py_convert() -> Path:
    script = find_whisper_py_convert()
    if script is None:
        raise MacSpeechError(
            code=ErrorCode.ENGINE_NOT_FOUND,
            message="The existing `whisper-py-convert` script was not found.",
            remedy="Run ./install.sh, or set WHISPER_PY_CONVERT_BIN to its path.",
        )
    return script


def _classify_failure(stderr: str, returncode: int) -> MacSpeechError:
    # Native stage markers survive both direct JSON and the unchanged legacy
    # script's stderr forwarding. Check them before broad legacy heuristics:
    # a framework's "unavailable" is not proof that the binary is missing.
    if "Error: [cancelled]" in stderr:
        return MacSpeechError(
            code=ErrorCode.CANCELLED,
            message=stderr.strip(),
            remedy="Inspect any reservation cleanup warnings before retrying.",
        )
    remedies = {
        "unsupported_locale": "Choose a locale supported by Apple SpeechTranscriber on this Mac.",
        "reservation_capacity": (
            "Inspect this same Apple binary with --inventory-status. Capacity is device-specific; "
            "do not delete speech assets or release unrelated reservations automatically."
        ),
        "reservation_failed": "Inspect the included Apple framework domain/code and this binary's --inventory-status.",
        "reservation_ownership": "Inspect --inventory-status; ownership was ambiguous and no global reset was attempted.",
        "reservation_cleanup": "Inspect --inventory-status; owned reservation cleanup could not be confirmed.",
        "reservation_coordination": "Check the owned private Apple STT lock directory; do not unlink an active lock file.",
        "asset_installation": "Check installed Apple speech assets and the included framework domain/code.",
        "transcription_failed": "Check the media input and included Apple framework domain/code.",
        "output_failed": "Check stdout/output destination and the included error information.",
    }
    for marker, remedy in remedies.items():
        if f"Error: [{marker}]" in stderr:
            return MacSpeechError(code=ErrorCode.NATIVE_PROCESS_ERROR, message=stderr.strip(), remedy=remedy)
    lowered = stderr.lower()
    if "does not exist" in lowered or "not a file" in lowered:
        return MacSpeechError(code=ErrorCode.INPUT_NOT_FOUND, message=stderr.strip() or "Input file not found.")
    if "is not built" in lowered or "is not installed" in lowered or "unavailable" in lowered:
        return MacSpeechError(code=ErrorCode.ENGINE_NOT_FOUND, message=stderr.strip() or "STT engine is unavailable.")
    return MacSpeechError(
        code=ErrorCode.NATIVE_PROCESS_ERROR,
        message=stderr.strip() or f"whisper-py-convert exited with status {returncode}.",
    )


def run_text_or_srt(
    input_path: str,
    *,
    output_format: str,
    engine: str = "auto",
    model: str | None = None,
    language: str | None = None,
    seg_ts: bool = False,
    word_ts: bool = False,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> TranscribeResult:
    """Runs the existing `whisper-py-convert` entrypoint for the `text` or
    `srt` output formats and returns its content exactly as produced,
    along with the engine it actually resolved to."""
    script = resolve_whisper_py_convert()
    command = [sys.executable, str(script), "--engine", engine]
    if model:
        command += ["--model", model]
    if language:
        command += ["--language", language]
    if output_format == "srt":
        command.append("--srt")
        if word_ts:
            command.append("--word-ts")
        elif seg_ts:
            command.append("--seg-ts")
    command.append(input_path)

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise MacSpeechError(
            code=ErrorCode.TIMEOUT,
            message=f"whisper-py-convert did not finish within {timeout:.0f} seconds.",
        )

    resolved_engine = "unknown"
    for line in result.stderr.splitlines():
        diagnostic(f"[whisper-py-convert] {line}")
        match = _ENGINE_LINE_RE.match(line.strip())
        if match:
            resolved_engine = match.group(1)

    if result.returncode != 0:
        raise _classify_failure(result.stderr, result.returncode)

    return TranscribeResult(engine=resolved_engine, format=output_format, content=result.stdout)


# --- SRT parsing (for the faster-whisper JSON fallback) --------------------

_SRT_TIME_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")


def _parse_srt_timestamp(raw: str) -> float:
    match = _SRT_TIME_RE.fullmatch(raw.strip())
    if not match:
        raise ValueError(f"Invalid SRT timestamp: {raw!r}")
    hours, minutes, seconds, millis = (int(group) for group in match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


def parse_srt(content: str) -> list[tuple[float, float, str]]:
    """Parses the SRT format rendered by `whisper-py-convert.py`'s
    `render_srt()` into `(start, end, text)` cues."""
    cues: list[tuple[float, float, str]] = []
    for block in re.split(r"\n\s*\n", content.strip()):
        lines = [line for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        has_index = lines[0].strip().isdigit()
        time_line = lines[1] if has_index else lines[0]
        text_lines = lines[2:] if has_index else lines[1:]
        if "-->" not in time_line:
            continue
        start_raw, end_raw = (part.strip() for part in time_line.split("-->"))
        cues.append((_parse_srt_timestamp(start_raw), _parse_srt_timestamp(end_raw), " ".join(text_lines).strip()))
    return cues


# --- JSON (structured segments/words) --------------------------------------

def _resolve_engine_for_json(requested: str) -> str:
    """Mirrors `resolve_engine()` in whisper-py-convert.py exactly, so
    `--engine auto` picks the same backend here as it would there."""
    if requested == "apple":
        if find_apple_stt_binary() is None:
            raise MacSpeechError(
                code=ErrorCode.ENGINE_NOT_FOUND,
                message="Apple Speech backend is not built.",
                remedy="Run ./install.sh on macOS 27+.",
            )
        return "apple"
    if requested == "windows":
        if find_windows_stt_binary() is None:
            raise MacSpeechError(
                code=ErrorCode.ENGINE_NOT_FOUND,
                message="Windows AI Speech backend is not installed.",
            )
        return "windows"
    if requested == "auto":
        if find_apple_stt_binary():
            return "apple"
        if find_windows_stt_binary():
            return "windows"
        return "faster-whisper"
    return "faster-whisper"


def _run_apple_json(input_path: str, *, language: str | None, timeout: float) -> Transcript:
    binary = find_apple_stt_binary()
    assert binary is not None  # guaranteed by _resolve_engine_for_json
    command = [str(binary), "--format", "json", "--timestamp-mode", "word"]
    if language:
        command += ["--language", language]
    command.append(input_path)
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise MacSpeechError(code=ErrorCode.TIMEOUT, message=f"Apple STT engine timed out after {timeout:.0f}s.")
    for line in result.stderr.splitlines():
        diagnostic(f"[whisper-py-convert-apple] {line}")
    if result.returncode != 0:
        raise _classify_failure(result.stderr, result.returncode)

    try:
        payload = json_module.loads(result.stdout)
    except json_module.JSONDecodeError as exc:
        raise MacSpeechError(code=ErrorCode.NATIVE_PROCESS_ERROR, message=f"Invalid JSON from Apple STT engine: {exc}")

    segments = [
        Segment(
            text=item["text"],
            start=float(item["start"]),
            end=float(item["end"]),
            words=[Word(text=w["text"], start=float(w["start"]), end=float(w["end"])) for w in item.get("words", [])],
        )
        for item in payload.get("segments", [])
    ]
    return Transcript(segments=segments, engine="apple")


def _run_windows_text_only(input_path: str, *, timeout: float) -> Transcript:
    binary = find_windows_stt_binary()
    assert binary is not None
    try:
        result = subprocess.run([str(binary), input_path], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise MacSpeechError(code=ErrorCode.TIMEOUT, message=f"Windows STT engine timed out after {timeout:.0f}s.")
    for line in result.stderr.splitlines():
        diagnostic(f"[whisper-py-convert-windows] {line}")
    if result.returncode != 0:
        raise _classify_failure(result.stderr, result.returncode)

    text = result.stdout.strip()
    # No timing data: the Windows backend does not expose segment/word
    # timestamps today (see README.md's backend comparison table). One
    # segment spanning the whole transcript, zero-duration, is the honest
    # representation — never invented timing.
    segment = Segment(text=text, start=0.0, end=0.0, words=[])
    return Transcript(segments=[segment] if text else [], engine="windows")


def _run_faster_whisper_json(
    input_path: str, *, model: str | None, language: str | None, timeout: float
) -> Transcript:
    text_result = run_text_or_srt(
        input_path,
        output_format="srt",
        engine="faster-whisper",
        model=model,
        language=language,
        word_ts=True,
        timeout=timeout,
    )
    cues = parse_srt(text_result.content)
    words = [Word(text=text, start=start, end=end) for start, end, text in cues if text]
    if not words:
        return Transcript(segments=[], engine="faster-whisper")
    # A word-level SRT has no preserved segment boundaries; one segment
    # spanning all words is an honest representation of what is actually
    # known, not an invented structure.
    segment = Segment(
        text=" ".join(word.text for word in words),
        start=words[0].start,
        end=words[-1].end,
        words=words,
    )
    return Transcript(segments=[segment], engine="faster-whisper")


def run_json(
    input_path: str,
    *,
    engine: str = "auto",
    model: str | None = None,
    language: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Transcript:
    resolved = _resolve_engine_for_json(engine)
    if resolved == "apple":
        return _run_apple_json(input_path, language=language, timeout=timeout)
    if resolved == "windows":
        return _run_windows_text_only(input_path, timeout=timeout)
    return _run_faster_whisper_json(input_path, model=model, language=language, timeout=timeout)
