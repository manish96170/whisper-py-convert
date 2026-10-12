"""Optional read-only terminal workspace; importing this requires no UI extra."""

from __future__ import annotations

import importlib
import sys

from ..errors import ErrorCode, MacSpeechError


def launch(*, locale: str = "en-US", timeout: float = 8.0, demo: bool = False) -> int:
    """Load the optional frontend only when explicitly requested."""
    from .backend import validate_locale, validate_timeout

    validate_locale(locale)
    validate_timeout(timeout)
    try:
        module = importlib.import_module("mac_speech.tui.app")
    except ModuleNotFoundError as error:
        if error.name and (error.name == "textual" or error.name.startswith("textual.") or error.name == "rich"):
            raise MacSpeechError(
                code=ErrorCode.ENGINE_NOT_FOUND,
                message="The optional read-only TUI dependency is not installed.",
                remedy="From the reviewed checkout run: python -m pip install -e '.[tui]'. Ordinary CLI commands do not require this extra.",
            ) from error
        raise
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise MacSpeechError(code=ErrorCode.INVALID_ARGUMENT, message="The TUI needs an interactive terminal (stdin and stdout).")
    module.SpeechDashboard(locale=locale, timeout=timeout, demo=demo).run()
    return 0
