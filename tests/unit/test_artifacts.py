"""Unit tests for mac_speech.artifacts (manifests and collision-safe naming)."""

from __future__ import annotations

import json

from mac_speech import artifacts


def test_build_manifest_computes_checksum_and_size(tmp_path):
    artifact = tmp_path / "out.wav"
    artifact.write_bytes(b"fake audio data")

    manifest = artifacts.build_manifest(artifact, operation="tts_save", engine="mac-speech-tts")

    assert manifest.schema_version == artifacts.MANIFEST_SCHEMA_VERSION
    assert manifest.operation == "tts_save"
    assert manifest.engine == "mac-speech-tts"
    assert manifest.file_size_bytes == len(b"fake audio data")
    assert len(manifest.checksum_sha256) == 64
    assert manifest.input_text is None
    assert manifest.input_text_sha256 is None


def test_build_manifest_never_stores_text_by_default(tmp_path):
    artifact = tmp_path / "out.wav"
    artifact.write_bytes(b"data")

    manifest = artifacts.build_manifest(
        artifact, operation="tts_save", input_text="some sensitive narration text"
    )

    assert manifest.input_text is None
    assert manifest.input_text_sha256 is not None
    assert manifest.input_text_sha256 != "some sensitive narration text"


def test_build_manifest_stores_text_only_when_opted_in(tmp_path):
    artifact = tmp_path / "out.wav"
    artifact.write_bytes(b"data")

    manifest = artifacts.build_manifest(
        artifact, operation="tts_save", input_text="hello", store_text=True
    )

    assert manifest.input_text == "hello"


def test_write_manifest_creates_sidecar_file(tmp_path):
    artifact = tmp_path / "out.wav"
    artifact.write_bytes(b"data")
    manifest = artifacts.build_manifest(artifact, operation="tts_save")

    manifest_file = artifacts.write_manifest(manifest, artifact)

    assert manifest_file == tmp_path / "out.wav.manifest.json"
    assert manifest_file.exists()
    on_disk = json.loads(manifest_file.read_text())
    assert on_disk["checksum_sha256"] == manifest.checksum_sha256


def test_write_manifest_is_atomic_no_leftover_temp_files(tmp_path):
    artifact = tmp_path / "out.wav"
    artifact.write_bytes(b"data")
    manifest = artifacts.build_manifest(artifact, operation="tts_save")

    artifacts.write_manifest(manifest, artifact)

    leftovers = [p for p in tmp_path.iterdir() if ".tmp-" in p.name]
    assert leftovers == []


def test_read_manifest_round_trips(tmp_path):
    artifact = tmp_path / "out.wav"
    artifact.write_bytes(b"data")
    manifest = artifacts.build_manifest(artifact, operation="tts_save", voice_identifier="v1")
    manifest_file = artifacts.write_manifest(manifest, artifact)

    loaded = artifacts.read_manifest(manifest_file)
    assert loaded["voice_identifier"] == "v1"
    assert loaded["artifact_id"] == manifest.artifact_id


def test_suggest_artifact_path_is_collision_safe(tmp_path):
    first = artifacts.suggest_artifact_path(tmp_path, prefix="narration", extension="wav")
    first.write_bytes(b"x")
    second = artifacts.suggest_artifact_path(tmp_path, prefix="narration", extension="wav")

    assert first != second
    assert second.suffix == ".wav"
    assert not second.exists()


def test_suggest_artifact_path_sanitizes_unsafe_prefix_characters(tmp_path):
    path = artifacts.suggest_artifact_path(tmp_path, prefix="a b/c:d", extension="wav")
    assert "/" not in path.name.replace(str(tmp_path), "")
    assert " " not in path.stem
