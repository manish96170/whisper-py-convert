"""Logging rules for mac_speech.

Diagnostics, progress, and warnings always go to stderr via
``diagnostic()``. stdout is reserved for command results: human-readable
text by default, or a single JSON document when ``--json`` is requested.
This mirrors the existing ``whisper-py-convert.py`` convention
(``print(..., file=sys.stderr)`` for progress) so stdout stays safe to
redirect to a file in either tool.

Nothing here configures Python's ``logging`` module; the rule is enforced by
convention (always write diagnostics through this function) rather than by a
logging framework, keeping the base package dependency-free.
"""

from __future__ import annotations

import sys


def diagnostic(message: str) -> None:
    print(message, file=sys.stderr)
