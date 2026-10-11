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
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_QUIET: ContextVar[bool] = ContextVar("mac_speech_quiet_diagnostics", default=False)


def diagnostic(message: str) -> None:
    if not _QUIET.get():
        print(message, file=sys.stderr)


@contextmanager
def suppress_diagnostics() -> Iterator[None]:
    """Thread/context-local suppression; never replace global stderr."""
    token = _QUIET.set(True)
    try:
        yield
    finally:
        _QUIET.reset(token)


def secondary_diagnostic(message: str) -> None:
    """Best-effort warning only while preserving an in-flight failure.

    A broken stderr pipe (or another interrupt during warning emission)
    must not replace cancellation or erase native claim-retention state.
    Normal diagnostics keep their existing behavior.
    """
    try:
        diagnostic(message)
    except BaseException:
        pass
