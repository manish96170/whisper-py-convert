"""Export adapters (PLAN.md Phases 8-10): optional, loosely coupled file
export, never part of core speech generation. `local` has no
dependencies; `gdrive` needs the optional `mac-speech[gdrive]` extra;
`s3` needs the `aws` CLI on PATH; `slack` needs a local
`team-slack-bridge` checkout (`MAC_SPEECH_SLACK_BRIDGE_PATH`). Importing
this package never requires any of those — only using the relevant
exporter does.
"""

from __future__ import annotations

from .base import ExportDestination, ExportPreview, ExportResult, Exporter
from .local import LocalExporter

__all__ = [
    "Exporter",
    "ExportDestination",
    "ExportPreview",
    "ExportResult",
    "LocalExporter",
    "get_exporter",
]


def get_exporter(provider: str) -> Exporter:
    """Resolves an exporter by provider name, importing its module lazily
    so e.g. `gdrive`'s optional dependency is only required when actually
    requested."""
    import importlib

    from ..errors import ErrorCode, MacSpeechError

    registry = {
        "local": ("mac_speech.export.local", "LocalExporter"),
        "gdrive": ("mac_speech.export.gdrive", "GoogleDriveExporter"),
        "s3": ("mac_speech.export.s3", "S3Exporter"),
        "slack": ("mac_speech.export.slack", "SlackExporter"),
    }
    if provider not in registry:
        raise MacSpeechError(
            code=ErrorCode.INVALID_ARGUMENT,
            message=f"Unknown export provider '{provider}'.",
            remedy=f"Supported providers: {', '.join(registry)}.",
        )
    module_name, class_name = registry[provider]
    module = importlib.import_module(module_name)
    return getattr(module, class_name)()
