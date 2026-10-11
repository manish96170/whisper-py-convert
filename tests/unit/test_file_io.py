"""Actual local atomic filesystem operations; no native speech or network."""

from __future__ import annotations

import errno
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from mac_speech import file_io
from mac_speech.errors import ErrorCode, MacSpeechError


def test_private_complete_write_and_cleanup(tmp_path):
    target = tmp_path / "report.json"
    assert file_io.atomic_write_text(target, "café\n") == target
    assert target.read_text() == "café\n"
    assert target.stat().st_mode & 0o777 == 0o600
    assert list(tmp_path.iterdir()) == [target]


def test_default_refuses_existing_output(tmp_path):
    target = tmp_path / "report.json"
    target.write_text("keep")
    with pytest.raises(MacSpeechError) as error:
        file_io.atomic_write_text(target, "new")
    assert error.value.code == ErrorCode.OUTPUT_EXISTS
    assert target.read_text() == "keep"
    assert list(tmp_path.iterdir()) == [target]


def test_force_replaces_name_not_old_inode(tmp_path):
    target = tmp_path / "report.json"
    kept = tmp_path / "kept.json"
    target.write_text("keep old inode")
    os.link(target, kept)
    file_io.atomic_write_text(target, "new", force=True)
    assert target.read_text() == "new"
    assert kept.read_text() == "keep old inode"


@pytest.mark.parametrize("force", [False, True])
@pytest.mark.parametrize("kind", ["symlink", "dangling", "directory"])
def test_non_regular_output_is_rejected(tmp_path, kind, force):
    target = tmp_path / "report.json"
    outside = tmp_path / "kept.json"
    if kind == "directory":
        target.mkdir()
    else:
        if kind == "symlink":
            outside.write_text("keep")
        target.symlink_to(outside)
    with pytest.raises(MacSpeechError) as error:
        file_io.atomic_write_text(target, "new", force=force)
    assert error.value.code == ErrorCode.INVALID_ARGUMENT
    if kind == "symlink":
        assert outside.read_text() == "keep"
    elif kind == "dangling":
        assert not outside.exists() and target.is_symlink()
    else:
        assert list(target.iterdir()) == []


def test_late_writer_is_preserved_and_our_temporary_is_cleaned(tmp_path, monkeypatch):
    target = tmp_path / "report.json"
    original = file_io.os.link

    def late_writer(source, destination):
        destination.write_text("other writer")
        original(source, destination)

    monkeypatch.setattr(file_io.os, "link", late_writer)
    with pytest.raises(MacSpeechError) as error:
        file_io.atomic_write_text(target, "our complete output")
    assert error.value.code == ErrorCode.OUTPUT_EXISTS
    assert target.read_text() == "other writer"
    assert list(tmp_path.iterdir()) == [target]


def test_concurrent_create_has_one_complete_winner(tmp_path):
    target = tmp_path / "report.json"
    barrier = threading.Barrier(8)
    contents = [str(index) * 64_000 for index in range(8)]

    def write(content):
        barrier.wait(timeout=10)
        try:
            file_io.atomic_write_text(target, content)
            return True
        except MacSpeechError as error:
            assert error.code == ErrorCode.OUTPUT_EXISTS
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        result = list(pool.map(write, contents))
    assert sum(result) == 1
    assert target.read_text() == contents[result.index(True)]
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("force", [False, True])
def test_encoding_failure_preserves_existing_data_and_cleans_temp(tmp_path, force):
    target = tmp_path / "report.json"
    if force:
        target.write_text("keep")
    with pytest.raises(MacSpeechError):
        file_io.atomic_write_text(target, "invalid UTF-8 surrogate \ud800", force=force)
    assert target.read_text() == "keep" if force else not target.exists()
    assert not any(".tmp-" in path.name for path in tmp_path.iterdir())


def test_unsupported_link_filesystem_fails_closed(tmp_path, monkeypatch):
    target = tmp_path / "report.json"

    def unavailable(*args, **kwargs):
        raise OSError(errno.EOPNOTSUPP, "links unavailable")

    monkeypatch.setattr(file_io.os, "link", unavailable)
    with pytest.raises(MacSpeechError) as error:
        file_io.atomic_write_text(target, "new")
    assert error.value.code == ErrorCode.INTERNAL_ERROR
    assert list(tmp_path.iterdir()) == []


def test_failed_replace_preserves_original(tmp_path, monkeypatch):
    target = tmp_path / "report.json"
    target.write_text("keep")

    def denied(*args, **kwargs):
        raise PermissionError("synthetic rename failure")

    monkeypatch.setattr(file_io.os, "replace", denied)
    with pytest.raises(MacSpeechError):
        file_io.atomic_write_text(target, "new", force=True)
    assert target.read_text() == "keep"
    assert list(tmp_path.iterdir()) == [target]
