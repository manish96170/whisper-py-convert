"""Optional Textual frontend. This MVP has no speech or maintenance actions."""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.text import Text

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Input, Static, TabbedContent, TabPane

from ..errors import MacSpeechError
from .backend import DemoBackend, ProbeResult, ReadOnlyBackend, discovery, display_text, system_sample, validate_locale


class SpeechDashboard(App[None]):
    TITLE = "Mac Speech — read-only workspace"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [("ctrl+r", "refresh", "Refresh"), ("ctrl+q", "quit", "Quit")]
    CSS = """
    #banner { height: auto; padding: 0 1; background: $panel; }
    #controls { height: 3; }
    #locale { width: 1fr; }
    #refresh { width: 16; }
    #refresh-status { height: auto; padding: 0 1; }
    TabPane { padding: 1; }
    Static { height: auto; margin-bottom: 1; }
    DataTable { height: 1fr; min-height: 6; }
    #system { height: auto; }
    """

    def __init__(self, *, locale: str = "en-US", timeout: float = 8.0, demo: bool = False,
                 backend: ReadOnlyBackend | None = None) -> None:
        super().__init__()
        self.locale = validate_locale(locale)
        self.demo = demo
        self.backend = backend or (DemoBackend(timeout=timeout) if demo else ReadOnlyBackend(timeout=timeout))
        self._dashboard_busy = False
        self._dashboard_closing = False
        self._last: dict[str, ProbeResult] = {}
        self._last_text: dict[str, str] = {}
        self._discovered: dict[str, object] = {}
        self._dashboard_refresh_task: asyncio.Task[None] | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("DEMO — fictional data, no native probes" if self.demo else
                     "READ ONLY — no analysis, audio generation, downloads, reservation changes or process controls", id="banner", markup=False)
        with Horizontal(id="controls"):
            yield Input(self.locale, placeholder="Locale, e.g. en-US or fr-FR", id="locale")
            yield Button("Refresh", id="refresh", variant="primary")
        yield Static("No successful snapshots yet", id="refresh-status", markup=False)
        with TabbedContent(initial="stt-tab", id="tabs"):
            with TabPane("STT", id="stt-tab"):
                with VerticalScroll():
                    yield Static("Readiness has not been refreshed.", id="stt-status", markup=False)
                    yield Static("Binary presence is discovery only, not proof of readiness. Requested/resolved region and assets are checked by read-only native diagnostics.", markup=False)
                    yield Static("Transcribe and language installation controls are not part of this read-only phase.", markup=False)
            with TabPane("TTS", id="tts-tab"):
                yield Static("Voice catalog has not been refreshed.", id="tts-status", markup=False)
                yield DataTable(id="voices", zebra_stripes=True)
            with TabPane("Jobs", id="jobs-tab"):
                yield Static("Session speech jobs: 0. Speech execution and queuing are not implemented in this phase.\nExternal/other-CLI speech jobs: UNKNOWN — no cross-CLI job registry or process monitor.\nReservations are asset subscriptions, not job/process counts.", markup=False)
                yield Static("Owned diagnostic processes: 0", id="probe-status", markup=False)
                yield Static("No cancel/stop/pause/terminate controls. Refresh timeout and Quit only drain this dashboard's owned read-only diagnostic children.", markup=False)
            with TabPane("System & Assets", id="assets-tab"):
                yield Static("No discovery snapshot yet.", id="binaries", markup=False)
                yield Static("No reservation snapshot yet.", id="asset-status", markup=False)
                yield DataTable(id="assets", zebra_stripes=True)
                yield Static("Host/dashboard metrics not sampled yet.", id="system", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#voices", DataTable).add_columns("Name", "Language", "Quality", "Identifier (local only)")
        self.query_one("#assets", DataTable).add_columns("Exact reserved asset locale", "SDK installed", "Ownership")
        self.set_interval(1.0, self._sample)
        self._sample()
        self.action_refresh()

    def _sample(self) -> None:
        sample = system_sample()
        self.query_one("#system", Static).update(
            f"Host logical CPUs: {sample['cpu_count']} | load averages: {sample['load_average']}\n"
            f"THIS dashboard PID: {sample['dashboard_pid']} | cumulative CPU seconds: {sample['dashboard_cpu_seconds']} | peak RSS bytes: {sample['dashboard_peak_rss_bytes']}\n"
            "Not whole-machine CPU/RAM usage or native-job resource totals; unavailable metrics remain unknown."
        )
        self.query_one("#probe-status", Static).update(f"Owned diagnostic processes: {self.backend.active_probes}. External speech activity: unknown.")

    def action_refresh(self) -> None:
        if self._dashboard_closing or self._dashboard_busy:
            return
        try:
            requested = validate_locale(self.query_one("#locale", Input).value)
        except MacSpeechError as error:
            self.query_one("#refresh-status", Static).update(error.message)
            return
        self._dashboard_busy = True
        self.query_one("#refresh", Button).disabled = True
        self.query_one("#refresh-status", Static).update(f"Refresh pending for {requested}; last successful snapshots stay visible. One refresh wave at a time.")
        # A Textual async worker leaves tab/input handling responsive. Each probe
        # finishes independently, so a busy STT gate does not block TTS results.
        self.run_worker(self._refresh(requested), name="read-only-refresh", exit_on_error=False)

    async def _refresh(self, requested: str) -> None:
        self._dashboard_refresh_task = asyncio.current_task()
        failed = False
        try:
            self._discovered = await asyncio.to_thread(discovery)
            if self.demo:
                self._discovered.update(apple_binary="Demo helper (not executed)", legacy_apple_binary="Demo helper (not executed)", tts_binary="Demo TTS (not executed)")
            self.query_one("#binaries", Static).update("\n".join(f"{key}: {display_text(value)}" for key, value in self._discovered.items()))
            apple_path = self._discovered.get("apple_binary")
            tts_path = self._discovered.get("tts_binary")
            apple = Path(str(apple_path)) if apple_path else None
            tts = Path(str(tts_path)) if tts_path else None

            async def section(name: str, operation) -> None:
                try:
                    result = await operation
                except asyncio.CancelledError:
                    raise
                except Exception:
                    from .backend import timestamp

                    result = ProbeResult(timestamp(), error="Unexpected read-only probe failure; check the selected helper. Last successful data is retained.")
                self._render(name, result, requested)

            sections = [asyncio.create_task(section("stt", self.backend.apple(apple, requested))),
                        asyncio.create_task(section("assets", self.backend.assets(apple))),
                        asyncio.create_task(section("tts", self.backend.voices(tts)))]
            try:
                await asyncio.gather(*sections)
            finally:
                for task in sections:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*sections, return_exceptions=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Never render raw exception/engine stderr (may contain private data).
            if not self._dashboard_closing:
                failed = True
                self.query_one("#refresh-status", Static).update("Read-only refresh failed; retained snapshots remain visible. Check selected helpers.")
        finally:
            self._dashboard_busy = False
            self._dashboard_refresh_task = None
            if not self._dashboard_closing:
                self.query_one("#refresh", Button).disabled = False
                self.query_one("#refresh-status", Static).update(
                    "Read-only refresh failed; retained snapshots remain visible." if failed else
                    f"Refresh completed for {requested}. Per-panel timestamps/errors identify fresh versus retained data."
                )

    def _render(self, name: str, result: ProbeResult, requested: str) -> None:
        if self._dashboard_closing:
            return
        widget_id = {"stt": "stt-status", "assets": "asset-status", "tts": "tts-status"}[name]
        widget = self.query_one(f"#{widget_id}", Static)
        if result.error:
            previous = self._last.get(name)
            widget.update(f"Refresh failed at {result.captured_at}: {display_text(result.error)}\n"
                          + (f"Last successful snapshot retained from {previous.captured_at}.\n{self._last_text[name]}" if previous else "No successful snapshot; data is unknown."))
            return
        self._last[name] = result
        data = result.value or {}
        prefix = f"Snapshot: {result.captured_at} (UTC); observational, not a continuing guarantee.\n"
        if name == "stt":
            widget.update(prefix + f"Requested: {requested} | Resolved: {display_text(data.get('supported_locale'))}\n"
                          f"API available: {display_text(data.get('available'))} | SDK installed: {display_text(data.get('installed'))}\n"
                          f"Explicit setup supported: {display_text(data.get('asset_setup_supported', 'unknown/older helper'))} | Automatic downloads: {display_text(data.get('automatic_asset_downloads', 'unknown/older helper'))}\n"
                          "Missing readiness may need explicit asset setup; this dashboard never starts it.")
        elif name == "assets":
            locales = data.get("reserved_locales", [])
            widget.update(prefix + f"Reserved asset locales: {len(locales)}/{data.get('maximum_reserved_locales')} (device/storage-specific, NOT process/recording quota).\n"
                          "Other supported/unreserved locales are not listed here; selected-locale readiness is in STT. No release controls in this phase.")
            table = self.query_one("#assets", DataTable)
            table.clear()
            for locale in locales:
                table.add_row(Text(display_text(locale)), Text(str(data.get("installed_assets", {}).get(locale, "unknown"))), Text("pre-existing / unknown"))
        else:
            voices = data.get("voices", [])
            widget.update(prefix + f"Available voices reported now: {len(voices)}. Catalog may vary between queries. No authorization requests, playback or synthesis.")
            table = self.query_one("#voices", DataTable)
            table.clear()
            for voice in voices:
                table.add_row(*(Text(display_text(voice.get(key, "unknown"))) for key in ("name", "language", "quality", "identifier")))
        self._last_text[name] = str(widget.content)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh":
            self.action_refresh()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "locale":
            self.action_refresh()

    async def action_quit(self) -> None:
        if self._dashboard_closing:
            return
        self._dashboard_closing = True
        if self._dashboard_refresh_task is not None:
            self._dashboard_refresh_task.cancel()
        await self.backend.close()
        self.exit()

    async def on_unmount(self) -> None:
        self._dashboard_closing = True
        await self.backend.close()
