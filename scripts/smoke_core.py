"""Smoke-test an installed wrapper without optional packages or Python networking.

Run using the clean environment's Python, not the development interpreter.
On macOS, wrap this command with sandbox-exec to deny native-child networking
as well. See docs/verification.md. No transcription or model download is run.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import io
import json
import os
import socket
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any


def deny_python_network(event: str, args: tuple[Any, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"}:
        raise PermissionError("Network access is disabled for the core smoke test.")


def invoke_cli(argv: list[str]) -> tuple[int, dict[str, Any]]:
    from mac_speech.cli import main

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
        code = main(argv)
    return code, json.loads(stdout.getvalue())


def verify_wav(path: Path) -> None:
    with wave.open(str(path), "rb") as audio:
        assert audio.getnframes() > 0, "Synthesis produced no audio frames."
        assert audio.getframerate() > 0
        assert audio.getnchannels() > 0


def run_checks(*, native_tts: bool, require_noneditable: bool) -> dict[str, Any]:
    import mac_speech

    if require_noneditable:
        package_path = Path(mac_speech.__file__).resolve()
        assert Path(sys.prefix).resolve() in package_path.parents, (
            "Use a clean venv with a wheel installed, not an editable/source import."
        )
    # Required dependencies must be absent; extras may be recorded in metadata.
    requirements = importlib.metadata.requires("mac-speech") or []
    assert all("extra ==" in requirement for requirement in requirements), (
        "The base wrapper unexpectedly declares a runtime dependency."
    )
    version_code, version = invoke_cli(["version", "--json"])
    assert version_code == 0
    assert version["version"] == importlib.metadata.version("mac-speech")
    capabilities_code, capabilities = invoke_cli(["capabilities", "--json"])
    assert capabilities_code == 0 and capabilities["schema_version"] == 1
    doctor_code, doctor = invoke_cli(["doctor", "--json"])
    # An independently absent STT engine is expected in a TTS-only installation.
    assert doctor_code in (0, 1) and doctor["schema_version"] == 1
    assert doctor_code == (0 if doctor["ok"] else 1)

    with tempfile.TemporaryDirectory(prefix="mac-speech-smoke-") as temporary:
        directory = Path(temporary)
        # Missing native engine or input is rejected before any native invocation
        # or model fallback. Engine-free wheels check availability first.
        code, error = invoke_cli([
            "stt", "transcribe", str(directory / "missing.wav"),
            "--engine", "apple", "--format", "json", "--json",
        ])
        assert code != 0 and error["error"]["code"] in {"input_not_found", "engine_not_found"}
        if native_tts:
            code, voices = invoke_cli(["tts", "voices", "--json"])
            assert code == 0
            ordinary = [voice for voice in voices["voices"] if not voice["is_personal_voice"]]
            assert ordinary, "No locally available ordinary system voice was reported."
            output = directory / "smoke.wav"
            arguments = [
                "tts", "save", "Hello from the local speech toolkit.",
                "--voice", ordinary[0]["identifier"], "--output", str(output),
                "--manifest", "--json",
            ]
            code, result = invoke_cli(arguments)
            assert code == 0 and result["duration_seconds"] > 0
            verify_wav(output)
            manifest = json.loads(output.with_name(output.name + ".manifest.json").read_text())
            assert "Hello from the local speech toolkit." not in json.dumps(manifest)
            before = output.read_bytes()
            code, error = invoke_cli(arguments)
            assert code != 0 and error["error"]["code"] == "output_exists"
            assert output.read_bytes() == before, "An existing artifact was overwritten."

    return {
        "ok": True,
        "version": version["version"],
        "python_network": "denied by audit hook",
        "native_tts": "passed" if native_tts else "not requested",
        "stt": "availability/input validation only; no transcription/model download attempted",
        "doctor_ok": doctor["ok"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-tts", action="store_true", help="also test installed native TTS")
    parser.add_argument("--tts-binary", type=Path, help="explicit native TTS binary path")
    parser.add_argument("--require-noneditable", action="store_true", help="require a clean wheel install")
    args = parser.parse_args(argv)
    if args.tts_binary:
        os.environ["MAC_SPEECH_TTS_BINARY"] = str(args.tts_binary.resolve())
    sys.addaudithook(deny_python_network)
    # Prove the Python network guard is active without contacting a remote host.
    with socket.socket() as connection:
        try:
            connection.connect(("127.0.0.1", 9))
        except PermissionError:
            pass
        else:
            raise AssertionError("Python network guard is not active.")
    print(json.dumps(run_checks(
        native_tts=args.native_tts, require_noneditable=args.require_noneditable,
    )))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
