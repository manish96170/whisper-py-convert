"""mac_speech: shared Python wrapper and CLI for local macOS speech capabilities.

This package defines the stable contracts (capability discovery, typed
results, error codes, and the native-process protocol) shared by the STT
and TTS engines described in ``PLAN.md``. Importing this package must never
require a built native binary, a downloaded model, or network access —
``capabilities.py`` only performs read-only, local checks.

See ``docs/architecture.md`` for how this package relates to the existing
``whisper-py-convert`` command, and
``docs/decisions/ADR-001-repository-and-module-boundaries.md`` for why both
live in this repository.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
