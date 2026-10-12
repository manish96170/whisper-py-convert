"""Read-only dashboard primitives and synthetic-child lifecycle tests."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from mac_speech import cli
from mac_speech.errors import MacSpeechError
from mac_speech.tui.backend import (
    DemoBackend, MAX_OUTPUT, ReadOnlyBackend, display_text, system_sample, validate_locale, validate_timeout,
)


def helper(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "diagnostic-helper"
    path.write_text(f"#!{sys.executable}\n" + source)
    path.chmod(0o700)
    return path


@pytest.mark.parametrize("locale", ["", "--confirm-release", "en US", "en-US\x1b[2J", "en-US;rm", "x" * 65])
def test_locale_cannot_inject_native_command_options(locale):
    with pytest.raises(MacSpeechError):
        validate_locale(locale)


@pytest.mark.parametrize("value", [0, -1, 31, True, float("nan"), float("inf"), "8"])
def test_timeout_is_bounded(value):
    with pytest.raises(MacSpeechError):
        validate_timeout(value)


def test_display_strips_terminal_control_characters_and_limits_length():
    assert display_text("hello\x1b[2J\nworld") == "hello?[2J?world"
    assert len(display_text("x" * 1000)) == 512
    assert validate_locale("en_US") == "en_US"
    assert validate_timeout(8) == 8.0


def test_missing_extra_is_actionable_without_importing_it_on_normal_commands(capsys):
    assert cli.main(["version"]) == 0
    capsys.readouterr()
    with patch("mac_speech.tui.importlib.import_module", side_effect=ModuleNotFoundError(name="textual")):
        assert cli.main(["tui", "--demo"]) == 4
    assert ".[tui]" in capsys.readouterr().err


def test_tui_help_needs_no_optional_import(capsys):
    with patch("mac_speech.tui.importlib.import_module", side_effect=AssertionError("must not load Textual")):
        with pytest.raises(SystemExit) as exit_info:
            cli.main(["tui", "--help"])
    assert exit_info.value.code == 0
    assert "--demo" in capsys.readouterr().out


def test_demo_never_spawns_native_processes():
    async def run():
        backend = DemoBackend()
        with patch("asyncio.create_subprocess_exec", side_effect=AssertionError("no native probe in demo")):
            apple, assets, voices = await asyncio.gather(backend.apple(None, "fr-FR"), backend.assets(None), backend.voices(None))
            assert apple.value["installed"] is False
            assert assets.value["maximum_reserved_locales"] == 3
            assert voices.value["voices"]
        await backend.close()
        assert backend.active_probes == 0
    asyncio.run(run())


def test_native_executor_refuses_every_mutating_family(tmp_path):
    async def run():
        backend = ReadOnlyBackend()
        for command in [("--install-assets",), ("--reservation-maintenance", "release"), ("save",), ("speak",), ("--format", "json")]:
            with patch("asyncio.create_subprocess_exec", side_effect=AssertionError("must refuse before spawning")):
                with pytest.raises(Exception, match="non-read-only"):
                    await backend._query(tmp_path / "unused", command)
        await backend.close()
    asyncio.run(run())


def test_real_synthetic_helper_only_receives_read_only_commands(tmp_path):
    audit = tmp_path / "arguments.jsonl"
    status = {"available": True, "installed": False, "supported_locale": "fr_FR",
              "reserved_locales": ["en_US"], "maximum_reserved_locales": 9}
    inventory = {"dry_run": True, "release_attempted": False, "verified": True,
                 "before": {"reserved_locales": ["en_US"], "maximum_reserved_locales": 9, "installed_assets": {"en_US": True}}}
    voices = {"protocol_version": 1, "status": "ok", "result": {"voices": [
        {"identifier": "fictional", "name": "Demo", "language": "en-US", "quality": "demo"}]}}
    binary = helper(tmp_path, f"""import json,sys
with open({str(audit)!r},'a') as handle:handle.write(json.dumps(sys.argv[1:])+'\\n')
answers={status!r},{inventory!r},{voices!r}
print(json.dumps(answers[0 if sys.argv[1]=='--inventory-status' else 1 if sys.argv[1]=='--reservation-maintenance' else 2]))
""")

    async def run():
        backend = ReadOnlyBackend()
        results = await asyncio.gather(backend.apple(binary, "fr-FR"), backend.assets(binary), backend.voices(binary))
        assert all(result.error is None for result in results)
        assert results[0].value["installed"] is False
        assert results[1].value["maximum_reserved_locales"] == 9
        await backend.close()
        assert backend.active_probes == 0
    asyncio.run(run())
    commands = [json.loads(line) for line in audit.read_text().splitlines()]
    assert sorted(commands) == sorted([["--inventory-status", "--language", "fr-FR"], ["--reservation-maintenance", "inspect"], ["voices", "--timeout", "8.0"]])


@pytest.mark.parametrize("payload", [[], {}, {"available": 1, "installed": True, "supported_locale": "en_US",
                                            "reserved_locales": [], "maximum_reserved_locales": 5}])
def test_malformed_native_data_reports_unknown_without_raw_stderr(tmp_path, payload):
    binary = helper(tmp_path, f"import json,sys\nprint('PRIVATE TRANSCRIPT SECRET',file=sys.stderr)\nprint(json.dumps({payload!r}))\n")
    async def run():
        backend = ReadOnlyBackend()
        result = await backend.apple(binary, "en-US")
        assert result.error and "PRIVATE" not in result.error
        await backend.close()
    asyncio.run(run())


def test_old_tts_protocol_is_not_treated_as_a_valid_voice_catalog(tmp_path):
    binary = helper(tmp_path, "print('{\"status\":\"ok\",\"result\":{\"voices\":[]}}')\n")
    async def run():
        backend = ReadOnlyBackend()
        result = await backend.voices(binary)
        assert "protocol mismatch" in result.error
        await backend.close()
    asyncio.run(run())


@pytest.mark.skipif(os.name != "posix", reason="Synthetic POSIX child lifecycle")
def test_timeout_and_close_stop_only_owned_readonly_children(tmp_path):
    binary = helper(tmp_path, "import time\ntime.sleep(60)\n")
    async def run():
        original = asyncio.create_subprocess_exec
        children = []
        async def capture(*arguments, **kwargs):
            process = await original(*arguments, **kwargs)
            children.append(process)
            return process
        with patch("asyncio.create_subprocess_exec", side_effect=capture):
            backend = ReadOnlyBackend(timeout=.2)
            result = await backend.apple(binary, "en-US")
            assert "timed out" in result.error
            assert backend.active_probes == 0 and children[0].returncode is not None
            with pytest.raises(ProcessLookupError):
                os.kill(children[0].pid, 0)
            await backend.close()
            backend = ReadOnlyBackend()
            request = asyncio.create_task(backend.assets(binary))
            while backend.active_probes == 0:
                await asyncio.sleep(.01)
            await backend.close()
            assert request.cancelled() and backend.active_probes == 0
            assert children[1].returncode is not None
    asyncio.run(run())


def test_excessive_output_is_bounded_and_child_reaped(tmp_path):
    binary = helper(tmp_path, f"import sys\nsys.stdout.write('x'*{MAX_OUTPUT + 1000})\n")
    async def run():
        backend = ReadOnlyBackend()
        result = await backend.apple(binary, "en-US")
        assert result.error and "size limit" in result.error
        assert backend.active_probes == 0
        await backend.close()
    asyncio.run(run())


def test_cancelled_subprocess_acquisition_still_joins_and_reaps(tmp_path):
    binary = helper(tmp_path, "import time\ntime.sleep(60)\n")
    async def run():
        original = asyncio.create_subprocess_exec
        created = asyncio.Event()
        child = None

        async def delayed(*arguments, **kwargs):
            nonlocal child
            child = await original(*arguments, **kwargs)
            created.set()
            await asyncio.sleep(.1)
            return child
        backend = ReadOnlyBackend()
        with patch("asyncio.create_subprocess_exec", side_effect=delayed):
            request = asyncio.create_task(backend.apple(binary, "en-US"))
            await created.wait()
            request.cancel()
            await asyncio.sleep(.02)
            request.cancel()  # repeated cancellation must not cancel acquisition
            with pytest.raises(asyncio.CancelledError):
                await request
        assert child.returncode is not None
        assert backend.active_probes == 0
        await backend.close()
    asyncio.run(run())


def test_system_samples_are_explicitly_dashboard_metrics():
    data = system_sample()
    assert data["dashboard_pid"] == os.getpid()
    assert "dashboard_peak_rss_bytes" in data


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
@pytest.mark.skipif(os.name != "posix", reason="Synthetic POSIX termination/backpressure")
def test_overflow_readers_keep_draining_through_sigterm_refusal_and_kill(tmp_path, stream):
    binary = helper(tmp_path, f"import signal,sys,time\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\nsys.{stream}.write('x'*2000000)\nsys.{stream}.flush()\ntime.sleep(60)\n")
    async def run():
        backend = ReadOnlyBackend(timeout=1)
        request = asyncio.create_task(backend.apple(binary, "en-US"))
        done, _ = await asyncio.wait([request], timeout=6)
        assert done, "Cleanup must not wait indefinitely on a paused subprocess pipe"
        result = request.result()
        assert result.error and ("size limit" in result.error or "timed out" in result.error)
        assert backend.active_probes == 0
        assert not backend._drainers
        await backend.close()
    asyncio.run(run())


def test_deep_json_failure_is_sanitized_and_all_owned_resources_join(tmp_path):
    binary = helper(tmp_path, "import sys\nsys.stdout.write('{\"nested\":'+('['*2000)+'0'+(']'*2000)+'}')\n")
    async def run():
        backend = ReadOnlyBackend()
        result = await backend.apple(binary, "en-US")
        assert result.error and result.value is None
        assert backend.active_probes == 0
        await backend.close()
    asyncio.run(run())


@pytest.mark.parametrize("field", ["asset_setup_supported", "automatic_asset_downloads"])
def test_optional_capabilities_reject_malformed_native_values(tmp_path, field):
    data = {"available": True, "installed": True, "supported_locale": "en_US",
            "reserved_locales": [], "maximum_reserved_locales": 9, field: "bad\x1b[2J\nspoof"}
    binary = helper(tmp_path, f"import json\nprint(json.dumps({data!r}))\n")
    async def run():
        backend = ReadOnlyBackend()
        result = await backend.apple(binary, "en-US")
        assert "capability flags" in result.error
        assert "\x1b" not in result.error and "spoof" not in result.error
        await backend.close()
    asyncio.run(run())


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
@pytest.mark.skipif(os.name != "posix", reason="Synthetic acquisition/pipe/termination")
def test_cancelled_acquisition_drains_full_sigterm_refusing_child_before_close(tmp_path, stream):
    binary = helper(tmp_path, f"import signal,sys,time\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\nsys.{stream}.write('x'*2000000)\nsys.{stream}.flush()\ntime.sleep(60)\n")
    async def run():
        original = asyncio.create_subprocess_exec
        started = asyncio.Event()
        child = None
        async def delayed(*arguments, **kwargs):
            nonlocal child
            child = await original(*arguments, **kwargs)
            started.set()
            await asyncio.sleep(.7)
            return child
        backend = ReadOnlyBackend()
        with patch("asyncio.create_subprocess_exec", side_effect=delayed):
            request = asyncio.create_task(backend.apple(binary, "en-US"))
            await started.wait()
            request.cancel()
            closing = asyncio.create_task(backend.close())
            done, _ = await asyncio.wait([closing], timeout=7)
            assert done, "Quit must drain even when cancellation bypassed normal readers"
            await closing
        assert request.cancelled() and child.returncode is not None
        assert backend.active_probes == 0 and not backend._drainers
    asyncio.run(run())
