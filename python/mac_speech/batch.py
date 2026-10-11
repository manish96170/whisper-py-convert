"""Bounded, local TTS-only scene synthesis; never aligns, plays or exports.

Input text remains in memory/input files. Reports contain hashes, paths and
sanitized status—not source text or raw backend diagnostics. Only the main
scheduler writes the batch report; workers own distinct scene checkpoints.
"""

from __future__ import annotations

import hashlib
import math
import time
import unicodedata
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Event
from threading import Lock
from typing import Any, Sequence

from . import workflow
from .errors import ErrorCode, MacSpeechError
from .file_io import atomic_write_checkpoint, check_output_path
from .logging_utils import secondary_diagnostic, suppress_diagnostics
from .tts import synthesize_to_file

BATCH_SCHEMA_VERSION = 1
MAX_WORKERS = 4
MAX_SCENES = 1000


@dataclass(frozen=True)
class BatchScene:
    basename: str
    text: str = field(repr=False)
    voice: str | None = None
    language: str | None = None


@dataclass
class SceneResult:
    basename: str
    input_text_sha256: str
    status: str = "pending"  # pending/running/success/failed/cancelled
    output_path: str | None = None
    manifest_path: str | None = None
    error_code: str | None = None
    error: str | None = None
    elapsed_seconds: float = 0.0
    termination_unconfirmed: bool = False


@dataclass
class BatchResult:
    schema_version: int
    created_at: str
    output_dir: str
    workers: int
    scenes: list[SceneResult]
    elapsed_seconds: float = 0.0
    cancelled: bool = False
    termination_unconfirmed: bool = False

    @property
    def ok(self) -> bool:
        return bool(self.scenes) and all(scene.status == "success" for scene in self.scenes)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "ok": self.ok}


def _invalid(message: str) -> MacSpeechError:
    return MacSpeechError(code=ErrorCode.INVALID_ARGUMENT, message=message)


def _validate_scenes(scenes: Sequence[BatchScene]) -> None:
    if not 1 <= len(scenes) <= MAX_SCENES:
        raise _invalid(f"Batch must contain 1–{MAX_SCENES} scenes.")
    identities: set[str] = set()
    for scene in scenes:
        if not isinstance(scene, BatchScene):
            raise _invalid("Python batches require BatchScene objects.")
        workflow.validate_basename(scene.basename)
        identity = unicodedata.normalize("NFC", scene.basename).casefold()
        if identity in identities:
            raise _invalid("Batch scene basenames must be unique, including case/Unicode aliases.")
        identities.add(identity)
        if not isinstance(scene.text, str) or not scene.text.strip():
            raise _invalid("Every batch scene requires non-empty text.")
        if "\0" in scene.text:
            raise _invalid("Scene text must not contain embedded NUL characters.")
        try:
            scene.text.encode("utf-8")
        except UnicodeError as failure:
            raise _invalid("Scene text must be valid UTF-8.") from failure
        for selection in (scene.voice, scene.language):
            if selection is not None and (not isinstance(selection, str) or not selection.strip()):
                raise _invalid("Optional voice/language selections must be non-empty strings.")
            if selection is not None:
                if "\0" in selection:
                    raise _invalid("Voice/language selections must not contain embedded NUL characters.")
                try:
                    selection.encode("utf-8")
                except UnicodeError as failure:
                    raise _invalid("Voice/language selections must be valid UTF-8.") from failure


def scenes_from_dict(payload: Any) -> list[BatchScene]:
    """Strict versioned JSON input; unknown options cannot silently trigger STT."""
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "scenes"}:
        raise _invalid("Batch JSON requires exactly schema_version and scenes.")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != BATCH_SCHEMA_VERSION:
        raise _invalid("Unsupported batch input schema version.")
    entries = payload["scenes"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_SCENES:
        raise _invalid(f"Batch scenes must be an array with 1–{MAX_SCENES} entries.")
    scenes = []
    for entry in entries:
        if (
            not isinstance(entry, dict) or not {"basename", "text"} <= set(entry)
            or set(entry) - {"basename", "text", "voice", "language"}
        ):
            raise _invalid("Each scene requires basename/text and only optional voice/language.")
        scenes.append(BatchScene(**entry))
    _validate_scenes(scenes)
    return scenes


def _failure(result: SceneResult, code: ErrorCode) -> None:
    result.status = "cancelled" if code == ErrorCode.CANCELLED else "failed"
    result.error_code = code.value
    result.error = "Scene synthesis cancelled." if code == ErrorCode.CANCELLED else f"Scene synthesis failed ({code.value})."


def _run_scene(
    scene: BatchScene, directory: Path, force: bool, timeout: float, stop: Event, unsafe: Event,
) -> SceneResult:
    started = time.monotonic()
    result = SceneResult(scene.basename, hashlib.sha256(scene.text.encode("utf-8")).hexdigest())
    try:
        if stop.is_set():
            _failure(result, ErrorCode.CANCELLED)
            return result
        paths = workflow.prepare_workflow_paths(str(directory), basename=scene.basename, align=False, force=force)
        with workflow.claim_output_path(paths.lock):
            # Repeat the output checks inside the owned scene claim.
            for path in (paths.audio, paths.manifest):
                check_output_path(path, force=force)
            manifest = workflow.new_manifest(scene.text)
            identity = manifest.write_checkpoint(paths.manifest, force=force)
            result.manifest_path = str(paths.manifest)
            try:
                with suppress_diagnostics():
                    audio = synthesize_to_file(
                        scene.text, output_path=str(paths.audio), voice=scene.voice,
                        language=scene.language, force=force, timeout=timeout, cancel_event=stop,
                    )
                result.output_path = audio.output_path
                result.status = "success"
                stage = workflow.WorkflowStage(
                    name="synthesize", status="success", output_path=audio.output_path,
                    provenance={"engine": "mac-speech-tts", "duration_seconds": audio.duration_seconds},
                )
            except MacSpeechError as failure:
                if getattr(failure, "_mac_speech_native_unconfirmed", False):
                    raise  # Scene claim must remain, not be silently released.
                _failure(result, failure.code)
                stage = workflow.WorkflowStage(name="synthesize", status="failed", error=result.error)
            manifest.stages.append(stage)
            manifest.write_checkpoint(paths.manifest, force=True, expected_identity=identity)
    except MacSpeechError as failure:
        _failure(result, failure.code)
        if getattr(failure, "_mac_speech_native_unconfirmed", False):
            result.termination_unconfirmed = True
            unsafe.set()
            stop.set()  # Never free capacity for another native writer.
    except Exception as failure:
        _failure(result, ErrorCode.INTERNAL_ERROR)
        if getattr(failure, "_mac_speech_native_unconfirmed", False):
            result.termination_unconfirmed = True
            unsafe.set()
            stop.set()
    finally:
        result.elapsed_seconds = time.monotonic() - started
    return result


def synthesize_batch(
    scenes: Sequence[BatchScene], *, output_dir: str, workers: int = 1,
    force: bool = False, timeout: float = 120.0, cancel_event: Event | None = None,
) -> BatchResult:
    """Generate WAV/checkpoints with at most workers submitted/active scenes.

    KeyboardInterrupt cancels/drains owned work and returns a partial report.
    Other scheduler/report failures propagate only after cancellation/drain.
    Unconfirmed cleanup retains batch/scene claims. Parent directories are
    trusted; no hostile filesystem sandbox or multi-file transaction is claimed.
    """
    _validate_scenes(scenes)
    scenes = tuple(scenes)  # Do not schedule against a mutable caller list.
    _validate_scenes(scenes)
    if type(workers) is not int or not 1 <= workers <= MAX_WORKERS:
        raise _invalid(f"workers must be an integer from 1 to {MAX_WORKERS}.")
    if type(force) is not bool or not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise _invalid("force must be boolean and timeout must be finite and positive.")
    try:
        directory = Path(output_dir).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError, RuntimeError) as failure:
        raise _invalid("Cannot prepare the batch output directory.") from failure
    stop = cancel_event if cancel_event is not None else Event()
    unsafe = Event()
    report_path = directory / "batch.json"
    check_output_path(report_path, force=force)
    result = BatchResult(
        schema_version=BATCH_SCHEMA_VERSION,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        output_dir=str(directory), workers=workers,
        scenes=[SceneResult(scene.basename, hashlib.sha256(scene.text.encode("utf-8")).hexdigest()) for scene in scenes],
    )
    started = time.monotonic()
    with workflow.claim_output_path(directory / ".batch.lock", retain_event=unsafe):
        identity = atomic_write_checkpoint(report_path, _report_json(result), force=force)
        pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="mac-speech-batch")
        active: dict[Future[SceneResult], int] = {}
        next_index = 0
        completed: dict[int, SceneResult] = {}
        completion_lock = Lock()
        admissions: dict[int, tuple[Event, Event, Event, Event]] = {}

        def execute(index: int, ready: Event, abandoned: Event, entered: Event, finished: Event) -> SceneResult:
            entered.set()
            try:
                # No scene filesystem/native work until submit returned and
                # its Future was recorded. Thread.start interruption can leave
                # an executor thread outside its _threads bookkeeping.
                while not ready.wait(timeout=0.05):
                    if abandoned.is_set():
                        scene_result = SceneResult(
                            scenes[index].basename, hashlib.sha256(scenes[index].text.encode("utf-8")).hexdigest(),
                        )
                        _failure(scene_result, ErrorCode.CANCELLED)
                        with completion_lock:
                            completed[index] = scene_result
                        return scene_result
                scene_result = _run_scene(scenes[index], directory, force, timeout, stop, unsafe)
            except BaseException as failure:
                scene_result = SceneResult(
                    scenes[index].basename, hashlib.sha256(scenes[index].text.encode("utf-8")).hexdigest(),
                )
                _failure(scene_result, ErrorCode.CANCELLED if isinstance(failure, KeyboardInterrupt) else ErrorCode.INTERNAL_ERROR)
                if getattr(failure, "_mac_speech_native_unconfirmed", False):
                    scene_result.termination_unconfirmed = True
                    unsafe.set()
                    stop.set()
                with completion_lock:
                    completed[index] = scene_result
                raise
            else:
                with completion_lock:
                    completed[index] = scene_result
                return scene_result
            finally:
                finished.set()

        def checkpoint() -> None:
            nonlocal identity
            result.elapsed_seconds = time.monotonic() - started
            result.cancelled = stop.is_set()
            result.termination_unconfirmed = unsafe.is_set()
            identity = atomic_write_checkpoint(report_path, _report_json(result), force=True, expected_identity=identity)

        def fill() -> None:
            nonlocal next_index
            while not stop.is_set() and len(active) < workers and next_index < len(scenes):
                index = next_index
                next_index += 1
                result.scenes[index].status = "running"
                admission = (Event(), Event(), Event(), Event())
                admissions[index] = admission
                ready, abandoned, entered, finished = admission
                try:
                    future = pool.submit(execute, index, ready, abandoned, entered, finished)
                    active[future] = index
                    ready.set()
                except BaseException:
                    abandoned.set()
                    stop.set()
                    raise

        primary: BaseException | None = None
        try:
            fill()
            checkpoint()
            while active:
                done, _ = wait(tuple(active), timeout=0.1, return_when=FIRST_COMPLETED)
                for future in done:
                    index = active.pop(future)
                    result.scenes[index] = future.result()
                checkpoint()
                fill()
        except BaseException as failure:
            stop.set()
            if getattr(failure, "_mac_speech_native_unconfirmed", False):
                unsafe.set()
            if not isinstance(failure, KeyboardInterrupt):
                primary = failure
        finally:
            if stop.is_set():
                for future in active:
                    future.cancel()
            try:
                pool.shutdown(wait=True, cancel_futures=True)
            except BaseException as failure:
                unsafe.set()
                if primary is None:
                    primary = failure
            # Drain workers that entered before executor registration. An
            # unentered, abandoned admission can never perform scene work.
            for ready, abandoned, entered, finished in admissions.values():
                if not ready.is_set():
                    abandoned.set()
                if entered.is_set() and not finished.wait(timeout=10):
                    unsafe.set()
            for future, index in active.items():
                if future.done() and not future.cancelled():
                    try:
                        result.scenes[index] = future.result()
                    except BaseException as failure:
                        if getattr(failure, "_mac_speech_native_unconfirmed", False):
                            unsafe.set()
                        _failure(result.scenes[index], ErrorCode.INTERNAL_ERROR)
                else:
                    _failure(result.scenes[index], ErrorCode.CANCELLED)
            for scene in result.scenes:
                if scene.status in {"pending", "running"}:
                    _failure(scene, ErrorCode.CANCELLED)
            # A submit/acquisition interruption can occur before the main
            # thread receives its Future. The executor owns/drains that work;
            # the worker mailbox retains its actual result independently.
            with completion_lock:
                for index, scene_result in completed.items():
                    result.scenes[index] = scene_result
        if primary is not None:
            try:
                checkpoint()
            except BaseException:
                secondary_diagnostic("Batch checkpoint update failed; the original scheduler failure was retained.")
            raise primary
        checkpoint()
    return result


def _report_json(result: BatchResult) -> str:
    import json

    return json.dumps(result.to_dict(), indent=2) + "\n"
