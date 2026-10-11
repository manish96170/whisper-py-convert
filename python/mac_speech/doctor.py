"""``mac-speech doctor``: diagnose the local environment.

Each check is informational unless it represents something actionable and
broken. A missing native TTS engine is expected before Phase 2 ships, so it
is reported as informational rather than a failing check — running
``doctor`` today should not cry wolf about work that has not happened yet.
"""

from __future__ import annotations

import sys

from .capabilities import detect_capabilities, detect_platform
from .results import DoctorCheck, DoctorReport, SCHEMA_VERSION

MIN_PYTHON = (3, 9)


def run_doctor() -> DoctorReport:
    platform_info = detect_platform()
    checks: list[DoctorCheck] = []

    checks.append(
        DoctorCheck(
            name="python_version",
            ok=sys.version_info[:2] >= MIN_PYTHON,
            message=(
                f"Python {platform_info.python_version} "
                f"(requires >= {'.'.join(map(str, MIN_PYTHON))})"
            ),
        )
    )
    checks.append(
        DoctorCheck(
            name="platform",
            ok=True,
            message=(
                f"{platform_info.os_name} {platform_info.os_version} on {platform_info.machine}"
                + (
                    " (Apple Silicon)"
                    if platform_info.is_apple_silicon
                    else " (not Apple Silicon macOS; native engines target Apple Silicon macOS first, see docs/platform-support.md)"
                )
            ),
        )
    )

    for capability in detect_capabilities().capabilities:
        if capability.name == "tts" and not capability.available:
            # Expected pre-Phase-2 state: informational, not a failing check.
            checks.append(
                DoctorCheck(name="tts", ok=True, message=f"tts: not available yet — {capability.reason}")
            )
            continue
        checks.append(
            DoctorCheck(
                name=capability.name,
                ok=capability.available,
                message=(
                    f"{capability.name}: available"
                    if capability.available
                    else f"{capability.name}: unavailable — {capability.reason} ({capability.install_hint})"
                ),
            )
        )

    return DoctorReport(schema_version=SCHEMA_VERSION, platform=platform_info, checks=checks)
