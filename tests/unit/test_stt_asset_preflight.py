"""Read-only Apple readiness tests; every subprocess is mocked, never Speech."""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from mac_speech.errors import ErrorCode, MacSpeechError
from mac_speech.stt import engine


def _status(**changes):
    status = {
        "available": True,
        "supported_locale": "fr_FR",
        "installed": True,
        "reserved_locales": ["en_US", "fr_FR"],
        "maximum_reserved_locales": 9,
        "asset_setup_supported": True,
        "automatic_asset_downloads": False,
    }
    status.update(changes)
    return status


def _result(payload, returncode=0):
    return subprocess.CompletedProcess([], returncode, json.dumps(payload), "")


def _executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# mock only; must never execute\n")
    path.chmod(0o700)
    return path


@pytest.fixture
def binaries(monkeypatch, tmp_path):
    directory = tmp_path / "speech tools with spaces"
    directory.mkdir()
    script = directory / "whisper-py-convert.py"
    script.write_text("# mock only\n")
    legacy = _executable(directory / "whisper-py-convert-apple")
    installed = _executable(tmp_path / "installed tools" / "whisper-py-convert-apple")
    monkeypatch.setattr(engine, "find_whisper_py_convert", lambda: script)
    monkeypatch.setattr(engine, "find_apple_stt_binary", lambda: installed)
    return script, legacy, installed


def _transcribe(route, *, selected="apple", language="fr"):
    if route == "json":
        return engine.run_json("recording.wav", engine=selected, language=language, timeout=17)
    return engine.run_text_or_srt(
        "recording.wav", output_format=route, engine=selected, language=language, timeout=17,
    )


@pytest.mark.parametrize("route", ["json", "text", "srt"])
@pytest.mark.parametrize("selected", ["apple", "auto"])
def test_missing_assets_blocks_transcription_and_quotes_exact_resolved_setup(binaries, route, selected):
    _, legacy, installed = binaries
    binary = installed if route == "json" else legacy
    with patch.object(subprocess, "run", return_value=_result(_status(installed=False))) as run:
        with pytest.raises(MacSpeechError) as caught:
            _transcribe(route, selected=selected)
    error = caught.value
    assert error.code == ErrorCode.NATIVE_PROCESS_ERROR
    assert "fr" in error.message and "fr_FR" in error.message
    assert "Asset setup may download missing Apple models; no transcription or download started." in error.message
    assert error.remedy == "Run explicit command then retry: " + shlex.join([
        str(binary), "--install-assets", "--language", "fr_FR", "--confirm-download", "fr_FR",
    ])
    run.assert_called_once_with(
        [str(binary), "--inventory-status", "--language", "fr"],
        capture_output=True, text=True, timeout=17,
    )


@pytest.mark.parametrize("route", ["json", "text", "srt"])
def test_ready_assets_allow_transcription_without_changing_language_or_content(binaries, route):
    script, legacy, installed = binaries
    binary = installed if route == "json" else legacy
    output = '{"segments": []}' if route == "json" else "unchanged transcript or SRT\n"
    final = subprocess.CompletedProcess([], 0, output, "Engine: apple\n")
    with patch.object(subprocess, "run", side_effect=[_result(_status()), final]) as run:
        result = _transcribe(route)
    assert run.call_count == 2
    probe, transcription = [call.args[0] for call in run.call_args_list]
    assert probe == [str(binary), "--inventory-status", "--language", "fr"]
    assert transcription[0 if route == "json" else 1] == str(binary if route == "json" else script)
    assert transcription[transcription.index("--language") + 1] == "fr"
    assert transcription[-1] == "recording.wav"
    assert "--install-assets" not in transcription
    assert result.engine == "apple"
    if route != "json":
        assert result.content == output


@pytest.mark.parametrize("route", ["json", "text", "srt"])
@pytest.mark.parametrize("changes,reason", [
    ({"available": False, "supported_locale": None, "installed": False}, "API is unavailable"),
    ({"supported_locale": None, "installed": False}, "locale is unsupported"),
    ({"asset_setup_supported": False}, "automatic downloads disabled"),
    ({"automatic_asset_downloads": True}, "automatic downloads disabled"),
])
def test_unavailable_unsupported_or_unsafe_helpers_fail_without_setup_command(binaries, route, changes, reason):
    with patch.object(subprocess, "run", return_value=_result(_status(**changes))) as run:
        with pytest.raises(MacSpeechError) as caught:
            _transcribe(route)
    assert caught.value.code == ErrorCode.NATIVE_PROCESS_ERROR
    assert reason in caught.value.message
    assert "Rebuild/update" in caught.value.remedy
    assert "--confirm-download" not in caught.value.remedy
    assert run.call_count == 1


@pytest.mark.parametrize("field", [
    "available", "supported_locale", "installed", "reserved_locales",
    "maximum_reserved_locales", "asset_setup_supported", "automatic_asset_downloads",
])
def test_missing_fields_including_old_helper_capabilities_are_rejected(binaries, field):
    payload = _status()
    del payload[field]
    with patch.object(subprocess, "run", return_value=_result(payload)) as run:
        with pytest.raises(MacSpeechError) as caught:
            _transcribe("json")
    assert caught.value.code == ErrorCode.NATIVE_PROCESS_ERROR
    assert "Rebuild/update" in caught.value.remedy
    assert run.call_count == 1


@pytest.mark.parametrize("changes", [
    {"available": 1}, {"installed": "true"}, {"asset_setup_supported": 1},
    {"automatic_asset_downloads": 0}, {"installed": None},
    {"supported_locale": False}, {"supported_locale": ""}, {"supported_locale": " \t"},
    {"supported_locale": "fr\x00FR"}, {"supported_locale": "\ud800"},
    {"reserved_locales": "fr_FR"}, {"reserved_locales": [False]}, {"reserved_locales": [""]},
    {"maximum_reserved_locales": True}, {"maximum_reserved_locales": "5"},
    {"maximum_reserved_locales": 5.0}, {"maximum_reserved_locales": -1},
])
def test_strict_inventory_types_fail_closed(binaries, changes):
    with patch.object(subprocess, "run", return_value=_result(_status(**changes))) as run:
        with pytest.raises(MacSpeechError) as caught:
            _transcribe("json")
    assert caught.value.code == ErrorCode.NATIVE_PROCESS_ERROR
    assert "Rebuild/update" in caught.value.remedy
    assert run.call_count == 1


@pytest.mark.parametrize("payload", [None, [], True, "installed"])
def test_nonobject_inventory_is_rejected(binaries, payload):
    with patch.object(subprocess, "run", return_value=_result(payload)) as run:
        with pytest.raises(MacSpeechError) as caught:
            _transcribe("text")
    assert caught.value.code == ErrorCode.NATIVE_PROCESS_ERROR
    assert run.call_count == 1


@pytest.mark.parametrize("failure", [
    subprocess.CompletedProcess([], 1, "", "unrecognized option --inventory-status"),
    subprocess.CompletedProcess([], 0, "not JSON", ""),
    subprocess.TimeoutExpired("probe", 17),
    OSError("cannot execute helper"),
    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid helper output"),
    ValueError("embedded null byte"),
])
@pytest.mark.parametrize("route", ["json", "text", "srt"])
def test_probe_failure_never_transcribes_and_has_rebuild_instructions(binaries, route, failure):
    kwargs = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
    with patch.object(subprocess, "run", **kwargs) as run:
        with pytest.raises(MacSpeechError) as caught:
            _transcribe(route)
    assert caught.value.code == ErrorCode.NATIVE_PROCESS_ERROR
    assert "No transcription or download started" in caught.value.message
    assert "Rebuild/update" in caught.value.remedy
    assert run.call_count == 1


@pytest.mark.parametrize("maximum", [0, 1, 3, 11])
def test_capacity_is_device_specific_not_five(binaries, maximum):
    _, _, binary = binaries
    with patch.object(subprocess, "run", return_value=_result(_status(maximum_reserved_locales=maximum))):
        engine._preflight_apple_assets(binary, language=None, timeout=17)


def test_legacy_identity_cannot_borrow_installed_binary_readiness(binaries):
    _, legacy, installed = binaries

    def inventory(command, **kwargs):
        assert command[1] == "--inventory-status"
        return _result(_status(installed=command[0] == str(installed)))

    with patch.object(subprocess, "run", side_effect=inventory) as run:
        with pytest.raises(MacSpeechError) as caught:
            _transcribe("srt", selected="auto")
    assert str(legacy) in shlex.split(caught.value.remedy.split(": ", 1)[1])
    assert run.call_count == 1
    assert run.call_args.args[0][0] == str(legacy)


@pytest.mark.parametrize("selected", ["windows", "faster-whisper"])
def test_explicit_nonapple_legacy_backends_do_not_probe_even_with_native_present(binaries, selected):
    final = subprocess.CompletedProcess([], 0, "unchanged\n", f"Engine: {selected}\n")
    with patch.object(subprocess, "run", return_value=final) as run:
        result = _transcribe("text", selected=selected)
    assert result.content == "unchanged\n"
    assert run.call_count == 1
    assert "--inventory-status" not in run.call_args.args[0]


@pytest.mark.parametrize("selected,expected", [("auto", "faster-whisper"), ("apple", None)])
def test_installed_binary_does_not_make_legacy_apple_present(binaries, selected, expected):
    script, legacy, _ = binaries
    # Leave the sibling as a non-executable file; the real script ignores it.
    legacy.chmod(0o600)
    final = subprocess.CompletedProcess([], 0, "other backend\n", "Engine: faster-whisper\n")
    with patch.object(subprocess, "run", return_value=final) as run:
        if selected == "apple":
            with pytest.raises(MacSpeechError) as caught:
                _transcribe("text", selected=selected)
            assert caught.value.code == ErrorCode.ENGINE_NOT_FOUND
            run.assert_not_called()
        else:
            result = _transcribe("text", selected=selected)
            assert result.engine == expected
            assert run.call_count == 1
            assert run.call_args.args[0][1] == str(script)


@pytest.mark.parametrize("relative", [
    "whisper-py-convert-apple",
    ".build/out/Products/Release/whisper-py-convert-apple",
    ".build/release/whisper-py-convert-apple",
    ".build/arm64-apple-macosx/release/whisper-py-convert-apple",
])
def test_legacy_candidate_paths_follow_resolved_script_and_precedence(tmp_path, relative):
    directory = tmp_path / "actual script"
    directory.mkdir()
    script = directory / "whisper-py-convert.py"
    script.write_text("# no import\n")
    link = tmp_path / "linked-script"
    link.symlink_to(script)
    binary = _executable(directory / relative)
    assert engine._find_legacy_apple_binary(link) == binary
    sibling = _executable(directory / "whisper-py-convert-apple")
    assert engine._find_legacy_apple_binary(link) == sibling


@pytest.mark.parametrize("route,resolved", [("json", "windows"), ("json", "faster-whisper"), ("text", "windows")])
def test_auto_other_backends_do_not_probe(monkeypatch, tmp_path, route, resolved):
    script = tmp_path / "whisper-py-convert.py"
    script.write_text("# mock\n")
    monkeypatch.setattr(engine, "find_whisper_py_convert", lambda: script)
    monkeypatch.setattr(engine, "find_apple_stt_binary", lambda: None)
    windows = _executable(tmp_path / "whisper-py-convert-windows.exe")
    monkeypatch.setattr(engine, "find_windows_stt_binary", lambda: windows if resolved == "windows" else None)
    content = "1\n00:00:00,000 --> 00:00:00,300\nHi\n" if resolved == "faster-whisper" else "Hi\n"
    final = subprocess.CompletedProcess([], 0, content, f"Engine: {resolved}\n")
    with patch.object(subprocess, "run", return_value=final) as run:
        result = _transcribe(route, selected="auto")
    assert result.engine == resolved
    assert run.call_count == 1
    assert "--inventory-status" not in run.call_args.args[0]
