"""Standard-library-only, bounded read-only probes for the optional dashboard.

Only owned diagnostic children may be stopped/reaped. No speech operation,
installation, reservation mutation, playback or external signalling is exposed.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import __version__
from ..capabilities import detect_platform, find_apple_stt_binary, find_tts_binary, find_whisper_py_convert
from ..errors import ErrorCode, MacSpeechError
from ..native_protocol import NativeResponse, ProtocolVersionError, check_protocol_version
from ..stt.engine import _find_legacy_apple_binary

MAX_OUTPUT = 1_048_576


def validate_locale(locale: str) -> str:
    if not isinstance(locale, str) or len(locale) > 64 or not re.fullmatch(r"[A-Za-z]{2,8}(?:[-_][A-Za-z0-9]{1,8})*", locale):
        raise MacSpeechError(code=ErrorCode.INVALID_ARGUMENT, message="Use a locale identifier such as en-US or fr-FR (maximum 64 characters).")
    return locale


def validate_timeout(timeout: float) -> float:
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 30:
        raise MacSpeechError(code=ErrorCode.INVALID_ARGUMENT, message="Diagnostic timeout must be finite and between 0 and 30 seconds.")
    return float(timeout)


def display_text(value: object, *, limit: int = 512) -> str:
    """Do not interpret native strings as terminal escapes or Rich markup."""
    return "".join(character if character.isprintable() else "?" for character in str(value))[:limit]


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ProbeResult:
    captured_at: str
    value: dict[str, Any] | None = None
    error: str | None = None


class ProbeFailure(Exception):
    pass


def discovery() -> dict[str, Any]:
    platform = detect_platform()
    script = find_whisper_py_convert()
    legacy = _find_legacy_apple_binary(script) if script else None
    apple = find_apple_stt_binary()
    tts = find_tts_binary()
    return {
        "platform": f"{platform.os_name} {platform.os_version} ({platform.machine})",
        "python": platform.python_version, "wrapper_version": __version__,
        "apple_binary": str(apple) if apple else None,
        "legacy_apple_binary": str(legacy) if legacy else None,
        "legacy_script": str(script) if script else None,
        "tts_binary": str(tts) if tts else None,
    }


def system_sample() -> dict[str, Any]:
    """Host load and THIS dashboard's cumulative CPU/peak RSS, not job totals."""
    result: dict[str, Any] = {"cpu_count": os.cpu_count(), "dashboard_pid": os.getpid()}
    try:
        result["load_average"] = os.getloadavg()
    except (AttributeError, OSError):
        result["load_average"] = None
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        result["dashboard_cpu_seconds"] = usage.ru_utime + usage.ru_stime
        result["dashboard_peak_rss_bytes"] = usage.ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    except (ImportError, OSError):
        result["dashboard_cpu_seconds"] = result["dashboard_peak_rss_bytes"] = None
    return result


def _locale(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 128 and value.isprintable()


def _reservations(payload: dict[str, Any]) -> None:
    locales = payload.get("reserved_locales")
    maximum = payload.get("maximum_reserved_locales")
    if not isinstance(locales, list) or len(locales) > 1024 or not all(_locale(item) for item in locales):
        raise ProbeFailure("Malformed reservation list; update/check the selected helper.")
    if type(maximum) is not int or maximum < 0:
        raise ProbeFailure("Malformed device reservation capacity; update/check the selected helper.")


class ReadOnlyBackend:
    def __init__(self, *, timeout: float = 8.0) -> None:
        self.timeout = validate_timeout(timeout)
        self._requests: set[asyncio.Task[Any]] = set()
        self._processes: set[asyncio.subprocess.Process] = set()
        self._drainers: dict[asyncio.subprocess.Process, list[asyncio.Task[Any]]] = {}
        self._closed = False

    @property
    def active_probes(self) -> int:
        return len(self._processes)

    async def _stop(self, process: asyncio.subprocess.Process) -> None:
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), 2.0)
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
        await process.wait()

    async def _joined_stop(self, process: asyncio.subprocess.Process) -> None:
        async def finish() -> None:
            # Keep pipe readers alive during terminate/kill/wait. asyncio's
            # process waiter may depend on EOF even after returncode is set.
            if process not in self._drainers:
                # Cancellation during acquisition can bypass _output entirely.
                # Establish discard-only readers BEFORE signalling/waiting.
                async def discard(reader: asyncio.StreamReader | None) -> None:
                    if reader is not None:
                        while await reader.read(65536):
                            pass
                self._drainers[process] = [asyncio.create_task(discard(process.stdout)),
                                           asyncio.create_task(discard(process.stderr))]
            await self._stop(process)
            drainers = self._drainers.pop(process, [])
            await asyncio.gather(*drainers, return_exceptions=True)

        cleanup = asyncio.create_task(finish())
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                # Repeated quit/cancellation cannot abandon an owned child.
                continue
        cleanup.result()

    async def _output(self, process: asyncio.subprocess.Process) -> bytes:
        overflow = asyncio.Event()
        async def read(reader: asyncio.StreamReader | None) -> bytes:
            if reader is None:
                return b""
            chunks: list[bytes] = []
            size = 0
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    return b"".join(chunks)
                # Retain at most MAX_OUTPUT bytes but continue draining the
                # owned transport. Discard excess; never cancel a full pipe.
                if size < MAX_OUTPUT:
                    chunks.append(chunk[:MAX_OUTPUT - size])
                size += len(chunk)
                if size > MAX_OUTPUT:
                    overflow.set()

        tasks = [asyncio.create_task(read(process.stdout)), asyncio.create_task(read(process.stderr))]
        async def collect() -> bytes:
            stdout, _stderr = await asyncio.gather(*tasks)
            return stdout
        collector = asyncio.create_task(collect())
        self._drainers[process] = [*tasks, collector]
        over_limit = asyncio.create_task(overflow.wait())
        try:
            await asyncio.wait([collector, over_limit], return_when=asyncio.FIRST_COMPLETED)
            if overflow.is_set():
                raise ProbeFailure("Read-only helper output exceeded the diagnostic size limit.")
            stdout = await asyncio.shield(collector)
            await process.wait()
            return stdout
        finally:
            over_limit.cancel()
            await asyncio.gather(over_limit, return_exceptions=True)

    async def _query(self, binary: Path, arguments: tuple[str, ...]) -> dict[str, Any]:
        # Defense in depth: the generic executor also enforces the read-only set.
        allowed = arguments == ("--reservation-maintenance", "inspect") or arguments == ("voices", "--timeout", str(self.timeout))
        if len(arguments) == 3 and arguments[:2] == ("--inventory-status", "--language"):
            validate_locale(arguments[2])
            allowed = True
        if not allowed:
            raise ProbeFailure("The dashboard refuses non-read-only native commands.")
        if self._closed:
            raise asyncio.CancelledError()
        request = asyncio.current_task()
        if request is not None:
            self._requests.add(request)
        process: asyncio.subprocess.Process | None = None
        starting = asyncio.create_task(asyncio.create_subprocess_exec(
            str(binary), *arguments, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        ))
        try:
            try:
                process = await asyncio.shield(starting)
            except asyncio.CancelledError:
                # Acquisition may have started a child before returning its handle.
                while not starting.done():
                    try:
                        await asyncio.shield(starting)
                    except asyncio.CancelledError:
                        continue
                process = starting.result()
                self._processes.add(process)
                raise
            self._processes.add(process)
            stdout = await asyncio.wait_for(self._output(process), self.timeout)
            if process.returncode != 0:
                raise ProbeFailure(f"Read-only native query failed (exit {process.returncode}); check/update the selected helper.")
            payload = json.loads(stdout.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ProbeFailure("Read-only native query did not return a JSON object.")
            return payload
        except asyncio.TimeoutError as error:
            raise ProbeFailure("Read-only query timed out; the helper may be waiting for the STT gate or slow. Last successful data is retained.") from error
        except (OSError, UnicodeError, ValueError, RecursionError) as error:
            raise ProbeFailure("Cannot read valid diagnostic data from the selected native helper.") from error
        finally:
            if process is not None:
                await self._joined_stop(process)
                self._processes.discard(process)
            if request is not None:
                self._requests.discard(request)

    async def close(self) -> None:
        self._closed = True
        current = asyncio.current_task()
        requests = [task for task in self._requests if task is not current]
        for task in requests:
            task.cancel()
        await asyncio.gather(*requests, return_exceptions=True)

    async def apple(self, binary: Path | None, locale: str) -> ProbeResult:
        validate_locale(locale)
        if binary is None:
            return ProbeResult(timestamp(), error="Apple STT helper not found; build/install it on a compatible Mac.")
        try:
            payload = await self._query(binary, ("--inventory-status", "--language", locale))
            _reservations(payload)
            if type(payload.get("available")) is not bool or type(payload.get("installed")) is not bool:
                raise ProbeFailure("Malformed Apple readiness booleans; update the selected helper.")
            if "supported_locale" not in payload or (payload["supported_locale"] is not None and not _locale(payload["supported_locale"])):
                raise ProbeFailure("Malformed resolved Apple locale; update the selected helper.")
            if any(field in payload and type(payload[field]) is not bool for field in ("asset_setup_supported", "automatic_asset_downloads")):
                raise ProbeFailure("Malformed Apple capability flags; update the selected helper.")
            return ProbeResult(timestamp(), value=payload)
        except ProbeFailure as error:
            return ProbeResult(timestamp(), error=str(error))

    async def assets(self, binary: Path | None) -> ProbeResult:
        if binary is None:
            return ProbeResult(timestamp(), error="Apple STT helper not found; asset inventory is unknown.")
        try:
            payload = await self._query(binary, ("--reservation-maintenance", "inspect"))
            if payload.get("dry_run") is not True or payload.get("release_attempted") is not False or payload.get("verified") is not True:
                raise ProbeFailure("Unexpected non-read-only inspection response; update the selected helper.")
            before = payload.get("before")
            if not isinstance(before, dict):
                raise ProbeFailure("Missing read-only inventory snapshot.")
            _reservations(before)
            installed = before.get("installed_assets")
            if not isinstance(installed, dict) or not all(_locale(key) and type(value) is bool for key, value in installed.items()):
                raise ProbeFailure("Malformed exact installed-asset status.")
            return ProbeResult(timestamp(), value=before)
        except ProbeFailure as error:
            return ProbeResult(timestamp(), error=str(error))

    async def voices(self, binary: Path | None) -> ProbeResult:
        if binary is None:
            return ProbeResult(timestamp(), error="Native TTS helper not found; voices are unknown.")
        try:
            payload = await self._query(binary, ("voices", "--timeout", str(self.timeout)))
            response = NativeResponse.from_dict(payload)
            check_protocol_version(response)
            result = response.result
            if response.status != "ok" or not isinstance(result, dict) or not isinstance(result.get("voices"), list):
                raise ProbeFailure("Malformed TTS voice response; update the selected helper.")
            voices = result["voices"]
            if len(voices) > 4096 or not all(isinstance(voice, dict) and all(isinstance(voice.get(key), str) for key in ("identifier", "name", "language", "quality")) for voice in voices):
                raise ProbeFailure("Malformed or excessive TTS voice data.")
            return ProbeResult(timestamp(), value={"voices": voices})
        except ProtocolVersionError:
            return ProbeResult(timestamp(), error="TTS protocol mismatch; install matching wrapper/native versions.")
        except ProbeFailure as error:
            return ProbeResult(timestamp(), error=str(error))


class DemoBackend(ReadOnlyBackend):
    """Fictional, clearly labelled snapshots; never launches a native process."""
    async def apple(self, binary: Path | None, locale: str) -> ProbeResult:
        await asyncio.sleep(0)
        return ProbeResult(timestamp(), value={"available": True, "installed": locale != "fr-FR", "supported_locale": locale.replace("-", "_"),
            "reserved_locales": ["en_US", "en_GB"], "maximum_reserved_locales": 3,
            "automatic_asset_downloads": False, "asset_setup_supported": True})

    async def assets(self, binary: Path | None) -> ProbeResult:
        await asyncio.sleep(0)
        return ProbeResult(timestamp(), value={"reserved_locales": ["en_US", "en_GB"], "maximum_reserved_locales": 3,
                                             "installed_assets": {"en_US": True, "en_GB": True}})

    async def voices(self, binary: Path | None) -> ProbeResult:
        await asyncio.sleep(0)
        return ProbeResult(timestamp(), value={"voices": [{"identifier": "demo-voice", "name": "Fictional demo system voice", "language": "en-US", "quality": "demo"}]})
