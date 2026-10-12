"""Project license/metadata checks; no speech, providers, or network."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
IDENTIFIER = "LicenseRef-Mac-Speech-Personal-NonCommercial-NoDerivatives"


def test_license_records_requested_grant_and_restrictions():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    for clause in (
        "personal, non-commercial purposes",
        "modify,\nadapt, translate, reverse engineer",
        "derivative works",
        "sell, rent, lease",
        "revenue-generating activities",
        "compile or package the unmodified source",
        "Third-party libraries",
        "non-waivable",
        "not an open-source license",
    ):
        assert clause in license_text


def test_pep639_metadata_and_distribution_manifest_match_license():
    tomllib = pytest.importorskip("tomllib", reason="Static TOML metadata check uses Python 3.11+ tooling")
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert config["project"]["license"] == IDENTIFIER
    assert config["project"]["license-files"] == ["LICENSE"]
    assert config["project"]["dependencies"] == []
    assert config["project"]["requires-python"] == ">=3.9"
    assert config["build-system"]["requires"] == ["setuptools>=77"]
    assert "include LICENSE" in (ROOT / "MANIFEST.in").read_text()
    assert not any("License :: OSI Approved" in item for item in config["project"].get("classifiers", []))


def test_offline_runtime_license_metadata_check_is_complete(capsys):
    pytest.importorskip("tomllib", reason="Offline source inventory uses Python 3.11+ tooling")
    specification = importlib.util.spec_from_file_location("license_inventory", ROOT / "scripts" / "audit_dependencies.py")
    assert specification is not None and specification.loader is not None
    inventory = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(inventory)
    assert inventory.main(["--project", str(ROOT / "pyproject.toml"), "--group", "runtime", "--check"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["declared_base_dependencies"] == []
    assert report["project"]["license"]["declaration"] == IDENTIFIER
    assert report["project"]["license"]["text_files"] == ["LICENSE"]
    assert report["license_metadata_complete"]
