"""Capability discovery: what this machine can actually do right now.

Every check here is a real, read-only probe (filesystem, package metadata,
the ``platform`` module) — never a hard-coded assumption about engine
availability, per ``PLAN.md`` section 3.3 ("Prefer explicit capability
detection... over guessing or silent fallback.").

Phase 2 (native TTS engine) and Phase 4 (STT adapter) extend these probes as
the real engines land. Until then this module honestly reports "not
available yet" for pieces that have not been implemented, rather than
pretending they work.
"""

from __future__ import annotations

import importlib.metadata
import os
import platform
import sys
from pathlib import Path

from .config import load_config
from .results import CapabilitiesReport, CapabilityStatus, PlatformInfo, SCHEMA_VERSION

FASTER_WHISPER_PACKAGE = "faster-whisper"
FASTER_WHISPER_REQUIRED_VERSION = "1.2.1"
APPLE_STT_BINARY_NAME = "whisper-py-convert-apple"
WINDOWS_STT_BINARY_NAME = "whisper-py-convert-windows.exe"
TTS_BINARY_NAME = "mac-speech-tts"


def detect_platform() -> PlatformInfo:
    machine = platform.machine()
    os_version = platform.mac_ver()[0] if sys.platform == "darwin" else platform.release()
    return PlatformInfo(
        os_name=platform.system(),
        os_version=os_version,
        machine=machine,
        python_version=platform.python_version(),
        is_apple_silicon=sys.platform == "darwin" and machine == "arm64",
    )


def _repo_root() -> Path:
    # python/mac_speech/capabilities.py -> repo root is two levels above the
    # "python" directory this package lives in.
    return Path(__file__).resolve().parents[2]


def find_apple_stt_binary() -> Path | None:
    """Public binary-discovery entry point reused by `mac_speech.stt.engine`."""
    root = _repo_root()
    candidates = (
        root / APPLE_STT_BINARY_NAME,
        root / ".build" / "out" / "Products" / "Release" / APPLE_STT_BINARY_NAME,
        root / ".build" / "release" / APPLE_STT_BINARY_NAME,
        root / ".build" / "arm64-apple-macosx" / "release" / APPLE_STT_BINARY_NAME,
        Path.home() / ".local" / "share" / "whisper-py-convert" / APPLE_STT_BINARY_NAME,
    )
    return next((path for path in candidates if path.is_file() and os.access(path, os.X_OK)), None)


def find_windows_stt_binary() -> Path | None:
    """Public binary-discovery entry point reused by `mac_speech.stt.engine`."""
    root = _repo_root()
    candidates = (root / "windows" / "publish" / WINDOWS_STT_BINARY_NAME,)
    return next((path for path in candidates if path.is_file()), None)


def find_whisper_py_convert() -> Path | None:
    """Finds the existing `whisper-py-convert` Python entrypoint, which the
    STT adapter shells out to for the `text`/`srt` output formats (and for
    the `faster-whisper` engine in any format) rather than importing or
    forking it — see
    docs/decisions/ADR-001-repository-and-module-boundaries.md. Returns the
    script path to run with `sys.executable`, not an executable binary.
    """
    override = load_config().whisper_py_convert_bin_override
    if override:
        candidate = Path(override)
        return candidate if candidate.is_file() else None
    root = _repo_root()
    candidates = (
        root / "whisper-py-convert.py",
        Path.home() / ".local" / "share" / "whisper-py-convert" / "whisper-py-convert.py",
    )
    return next((path for path in candidates if path.is_file()), None)


def _faster_whisper_version() -> str | None:
    try:
        return importlib.metadata.version(FASTER_WHISPER_PACKAGE)
    except importlib.metadata.PackageNotFoundError:
        return None


def detect_stt_capability() -> CapabilityStatus:
    apple_binary = find_apple_stt_binary()
    windows_binary = find_windows_stt_binary()
    fw_version = _faster_whisper_version()
    wrapper_script = find_whisper_py_convert()
    details = {
        "apple_binary": str(apple_binary) if apple_binary else None,
        "windows_binary": str(windows_binary) if windows_binary else None,
        "faster_whisper_installed_version": fw_version,
        "faster_whisper_required_version": FASTER_WHISPER_REQUIRED_VERSION,
        "whisper_py_convert_script": str(wrapper_script) if wrapper_script else None,
        "supported_output_formats": ["text", "srt", "json"],
    }
    ready = apple_binary is not None or windows_binary is not None or fw_version == FASTER_WHISPER_REQUIRED_VERSION
    if ready:
        return CapabilityStatus(name="stt", available=True, details=details)
    return CapabilityStatus(
        name="stt",
        available=False,
        reason="No local STT backend is ready yet on this machine.",
        install_hint=(
            "Build the Apple backend (./install.sh on macOS 27+) or run the "
            "existing `whisper-py-convert` command once, which installs "
            "faster-whisper automatically."
        ),
        details=details,
    )


def find_tts_binary() -> Path | None:
    """Public binary-discovery entry point reused by `mac_speech.tts.engine`
    so there is exactly one place that knows where `mac-speech-tts` can
    live."""
    override = load_config().tts_binary_override
    if override:
        candidate = Path(override)
        return candidate if candidate.is_file() and os.access(candidate, os.X_OK) else None
    root = _repo_root()
    candidates = (
        root / TTS_BINARY_NAME,
        # Independent SwiftPM package; see
        # docs/decisions/ADR-001-repository-and-module-boundaries.md and
        # engines/tts-swift/Package.swift.
        root / "engines" / "tts-swift" / ".build" / "out" / "Products" / "Release" / TTS_BINARY_NAME,
        root / "engines" / "tts-swift" / ".build" / "release" / TTS_BINARY_NAME,
        root / "engines" / "tts-swift" / ".build" / "arm64-apple-macosx" / "release" / TTS_BINARY_NAME,
        Path.home() / ".local" / "share" / "mac-speech" / TTS_BINARY_NAME,
    )
    return next((path for path in candidates if path.is_file() and os.access(path, os.X_OK)), None)


def detect_tts_capability() -> CapabilityStatus:
    binary = find_tts_binary()
    details: dict = {
        "binary": str(binary) if binary else None,
        # Verified during Phase 2 (engines/tts-swift); see
        # docs/tts-engine.md for the exact settings behind each format.
        "supported_output_formats": ["wav", "aiff", "caf"],
    }
    if binary is not None:
        return CapabilityStatus(name="tts", available=True, details=details)
    return CapabilityStatus(
        name="tts",
        available=False,
        reason="Native TTS engine was not found.",
        install_hint=(
            "Run ./install.sh on macOS to build it, or set MAC_SPEECH_TTS_BINARY "
            "to a built mac-speech-tts binary."
        ),
        details=details,
    )


def detect_capabilities() -> CapabilitiesReport:
    return CapabilitiesReport(
        schema_version=SCHEMA_VERSION,
        platform=detect_platform(),
        capabilities=[detect_stt_capability(), detect_tts_capability()],
    )
