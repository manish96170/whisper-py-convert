"""Optional frontend headless tests; no native engines or assets are accessed."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual", reason="Optional TUI headless tests require the tui extra")

from textual.widgets import Button, DataTable, Input, Static, TabbedContent

from mac_speech.tui.app import SpeechDashboard
from mac_speech.tui.backend import DemoBackend, ProbeResult


def test_demo_tabs_readonly_tables_and_clean_quit():
    async def run():
        app = SpeechDashboard(demo=True)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(.2)
            assert app.query_one("#voices", DataTable).row_count == 1
            assert app.query_one("#assets", DataTable).row_count == 2
            assert "Requested: en-US" in str(app.query_one("#stt-status", Static).content)
            assert "DEMO" in str(app.query_one("#banner", Static).content)
            assert [button.id for button in app.query(Button)] == ["refresh"]
            tabs = app.query_one("#tabs", TabbedContent)
            for name in ["tts-tab", "jobs-tab", "assets-tab", "stt-tab"]:
                tabs.active = name
                await pilot.pause()
                assert tabs.active == name
            await app.action_quit()
        assert app.backend.active_probes == 0
    asyncio.run(run())


def test_blocked_inventory_does_not_freeze_tabs_or_duplicate_refreshes():
    class SlowBackend(DemoBackend):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.calls = 0
        async def assets(self, binary):
            self.calls += 1
            self.started.set()
            await self.release.wait()
            return await super().assets(binary)
    async def run():
        backend = SlowBackend()
        app = SpeechDashboard(demo=True, backend=backend)
        async with app.run_test(size=(100, 35)) as pilot:
            await backend.started.wait()
            await pilot.pause(.1)
            assert app.query_one("#voices", DataTable).row_count == 1
            assert app.query_one("#refresh", Button).disabled
            app.action_refresh()
            app.action_refresh()
            assert backend.calls == 1
            tabs = app.query_one("#tabs", TabbedContent)
            tabs.active = "jobs-tab"
            await pilot.pause()
            assert tabs.active == "jobs-tab"
            assert "Refresh pending" in str(app.query_one("#refresh-status", Static).content)
            backend.release.set()
            await pilot.pause(.1)
            assert not app.query_one("#refresh", Button).disabled
            await app.action_quit()
    asyncio.run(run())


def test_refresh_error_keeps_last_successful_data_timestamp_and_locale():
    class FailingBackend(DemoBackend):
        async def apple(self, binary, locale):
            return ProbeResult("new-attempt", error="diagnostic timed out")
    async def run():
        app = SpeechDashboard(demo=True)
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause(.2)
            old = app._last["stt"].captured_at
            app.backend = FailingBackend()
            app.query_one("#locale", Input).value = "fr-FR"
            app.action_refresh()
            await pilot.pause(.2)
            status = str(app.query_one("#stt-status", Static).content)
            assert "diagnostic timed out" in status and old in status
            assert "Requested: en-US" in status  # retained data not relabelled French
            await app.action_quit()
    asyncio.run(run())


def test_invalid_locale_is_not_submitted_and_native_strings_are_not_markup():
    async def run():
        app = SpeechDashboard(demo=True)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(.2)
            app.query_one("#locale", Input).value = "--install-assets"
            app.action_refresh()
            assert "locale identifier" in str(app.query_one("#refresh-status", Static).content)
            result = ProbeResult("now", value={"voices": [{"identifier": "fake", "name": "[bold]literal[/bold]\x1b[2J", "language": "en-US", "quality": "demo"}]})
            app._render("tts", result, "en-US")
            cell = app.query_one("#voices", DataTable).get_cell_at((0, 0))
            assert "[bold]literal[/bold]" in str(cell) and "\x1b" not in str(cell)
            await app.action_quit()
    asyncio.run(run())


def test_quit_cancels_pending_refresh_without_waiting_for_inventory_lock():
    class BlockedBackend(DemoBackend):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.cancelled = False
        async def assets(self, binary):
            self.started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise
    async def run():
        backend = BlockedBackend()
        app = SpeechDashboard(demo=True, backend=backend)
        async with app.run_test():
            await backend.started.wait()
            await asyncio.wait_for(app.action_quit(), 2)
        assert backend.cancelled
    asyncio.run(run())


def test_exceptional_section_retains_wave_guard_until_blocked_sibling_joins():
    class ExceptionalBackend(DemoBackend):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.calls = 0
        async def apple(self, binary, locale):
            raise RecursionError("PRIVATE payload must not be displayed")
        async def assets(self, binary):
            self.calls += 1
            self.started.set()
            await self.release.wait()
            return await super().assets(binary)
    async def run():
        backend = ExceptionalBackend()
        app = SpeechDashboard(demo=True, backend=backend)
        async with app.run_test() as pilot:
            await backend.started.wait()
            await pilot.pause(.1)
            assert app._dashboard_busy and app.query_one("#refresh", Button).disabled
            assert "PRIVATE" not in str(app.query_one("#stt-status", Static).content)
            app.action_refresh()
            assert backend.calls == 1
            backend.release.set()
            await pilot.pause(.1)
            assert not app._dashboard_busy
            await app.action_quit()
    asyncio.run(run())


def test_native_capability_text_is_defensively_control_sanitized_in_view():
    async def run():
        app = SpeechDashboard(demo=True)
        async with app.run_test() as pilot:
            await pilot.pause(.1)
            app._render("stt", ProbeResult("now", value={"available": True, "installed": True,
                "supported_locale": "en_US", "asset_setup_supported": "bad\x1b[2J\nspoof"}), "en-US")
            content = str(app.query_one("#stt-status", Static).content)
            assert "\x1b" not in content and "bad?[2J?spoof" in content
            await app.action_quit()
    asyncio.run(run())
