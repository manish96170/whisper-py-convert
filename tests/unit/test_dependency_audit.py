"""Dependency inventory tests: only synthetic metadata, no advisory services."""

from __future__ import annotations

import importlib.util
import json
from email.message import Message
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location(
    "audit_dependencies", Path(__file__).resolve().parents[2] / "scripts" / "audit_dependencies.py"
)
assert SPEC is not None and SPEC.loader is not None
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class FakeDistribution:
    def __init__(self, name="example", version="1.2.3", *, expression=None, legacy=None, classifiers=()):
        self.metadata = Message()
        self.metadata["Name"] = name
        self.metadata["Version"] = version
        for key, value in (("License-Expression", expression), ("License", legacy)):
            if value is not None:
                self.metadata[key] = value
        for classifier in classifiers:
            self.metadata["Classifier"] = classifier
        self.version = version
        self.files = [Path("example.dist-info/licenses/LICENSE")]


@pytest.fixture
def project(tmp_path):
    pytest.importorskip("tomllib", reason="Source inventory is a Python 3.11+ developer tool")
    path = tmp_path / "pyproject.toml"
    path.write_text('''[build-system]
requires = ["setuptools>=68"]
[project]
name = "example-project"
version = "0.1.0"
dependencies = []
[project.optional-dependencies]
dev = ["pytest>=7.4", "ruff==0.14.14", "mypy==1.15.0"]
gdrive = ["google-api-python-client>=2.0"]
''', encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def synthetic_metadata_only(monkeypatch):
    def missing(name):
        raise audit.metadata.PackageNotFoundError(name)
    monkeypatch.setattr(audit.metadata, "distribution", missing)
    monkeypatch.setattr(audit.metadata, "distributions", lambda: [])


@pytest.mark.parametrize("requirement, expected", [
    ("google_api.python-client>=2.0", "google-api-python-client"),
    (" Example[extra]>=1; python_version >= '3.9'", "example"),
    ("ruff==0.14.14", "ruff"),
])
def test_normalizes_names_without_resolving(requirement, expected):
    assert audit.requirement_name(requirement) == expected


def test_empty_requirement_rejected():
    with pytest.raises(ValueError, match="distribution name"):
        audit.requirement_name("")


def test_preserves_ranges_and_classifies_build_dev_and_optional(project):
    result = audit.audit_project(project)
    entries = result["direct_dependencies"]
    assert result["declared_base_dependencies"] == []
    assert [entry["requirement"] for entry in entries] == [
        "setuptools>=68", "pytest>=7.4", "ruff==0.14.14", "mypy==1.15.0",
        "google-api-python-client>=2.0",
    ]
    assert all(entry["scope"] == "development" for entry in entries[:-1])
    assert entries[-1]["scope"] == "optional-runtime"
    assert all(entry["installed"] is None for entry in entries)
    assert not result["license_metadata_complete"]
    assert result["installed_environment"] is None
    assert "vulnerability" in " ".join(result["limitations"])


def test_license_expression_legacy_and_classifier_are_separate_evidence():
    result = audit.distribution_record(FakeDistribution(
        expression="MIT AND Apache-2.0", legacy="Old wording",
        classifiers=("License :: OSI Approved :: MIT License", "Programming Language :: Python"),
    ))
    assert result["license_expression"] == "MIT AND Apache-2.0"
    assert result["license_legacy"] == "Old wording"
    assert result["license_classifiers"] == ["License :: OSI Approved :: MIT License"]
    assert result["license_files"] == ["example.dist-info/licenses/LICENSE"]
    assert result["license_metadata_present"]


@pytest.mark.parametrize("legacy, classifiers, present", [
    ("UNKNOWN", (), False),
    ("NOASSERTION", ("License :: OSI Approved",), False),
    ("NONE", (), False),
    ("Apache 2.0", (), True),
    (None, ("License :: OSI Approved :: MIT License",), True),
])
def test_unknown_and_generic_metadata_not_mistaken_for_license(legacy, classifiers, present):
    result = audit.distribution_record(FakeDistribution(legacy=legacy, classifiers=classifiers))
    assert result["license_metadata_present"] is present


def test_record_license_file_headers_even_without_record_files():
    distribution = FakeDistribution()
    distribution.files = None
    distribution.metadata["License-File"] = "LICENSE.txt"
    assert audit.distribution_record(distribution)["license_files"] == ["LICENSE.txt"]


def test_installed_version_is_not_claimed_to_satisfy_range(project, monkeypatch):
    monkeypatch.setattr(audit.metadata, "distribution", lambda name: FakeDistribution(name, "0.1", legacy="MIT"))
    result = audit.audit_project(project, groups=["build"])
    entry = result["direct_dependencies"][0]
    assert entry["requirement"] == "setuptools>=68"
    assert entry["installed"]["version"] == "0.1"
    assert "may not satisfy" in result["limitations"][0]
    assert not result["project"]["license"]["license_metadata_present"]


def test_missing_project_license_not_inferred_from_dependency_or_notice(project, monkeypatch):
    (project.parent / "NOTICE").write_text("Third-party notices only", encoding="utf-8")
    monkeypatch.setattr(audit.metadata, "distribution", lambda name: FakeDistribution(name, legacy="MIT"))
    result = audit.audit_project(project)
    assert result["project"]["license"]["declaration"] is None
    assert result["project"]["license"]["text_files"] == ["NOTICE"]
    assert not result["license_metadata_complete"]
    assert len(result["findings"]) == 1


def test_declared_license_file_presence_is_checked(tmp_path):
    pytest.importorskip("tomllib", reason="Source inventory is a Python 3.11+ developer tool")
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname="example"\nlicense={file="LICENSE"}\n', encoding="utf-8")
    result = audit.audit_project(project, groups=["runtime"])
    assert not result["project"]["license"]["declared_file_present"]
    assert not result["license_metadata_complete"]
    (tmp_path / "LICENSE").write_text("Synthetic test license", encoding="utf-8")
    result = audit.audit_project(project, groups=["runtime"])
    assert result["project"]["license"]["declared_file_present"]
    assert result["license_metadata_complete"]


def test_environment_snapshot_sorted_and_missing_licenses_reported(project, monkeypatch):
    monkeypatch.setattr(audit.metadata, "distributions", lambda: [
        FakeDistribution("z-extra", expression="MIT"), FakeDistribution("a-extra"),
    ])
    result = audit.audit_project(project, groups=["runtime"], environment=True)
    assert [item["name"] for item in result["installed_environment"]] == ["a-extra", "z-extra"]
    assert "environment: a-extra: license metadata missing/unknown." in result["findings"]


def test_unknown_group_is_an_actionable_error(project):
    with pytest.raises(ValueError, match="Unknown inventory groups: not-declared"):
        audit.audit_project(project, groups=["not-declared"])


def test_duplicate_group_not_duplicate_inventory(project):
    result = audit.audit_project(project, groups=["dev", "dev"])
    assert result["selected_groups"] == ["dev"]
    assert len(result["direct_dependencies"]) == 3


@pytest.mark.parametrize("document", [
    {"project": {"dynamic": ["dependencies"]}},
    {"project": {"dynamic": ["optional-dependencies"]}},
    {"project": {"dependencies": "not-a-list"}},
    {"project": {"dependencies": [4]}},
    {"project": {"optional-dependencies": {"build": []}}},
])
def test_unsupported_declarations_fail_instead_of_reporting_clean(document):
    with pytest.raises(ValueError):
        audit.declaration_groups(document)


def test_cli_outputs_json_and_check_returns_nonzero_for_missing_license(project, capsys):
    assert audit.main(["--project", str(project), "--group", "runtime"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema"] == audit.SCHEMA
    assert not report["license_metadata_complete"]
    assert audit.main(["--project", str(project), "--group", "runtime", "--check"]) == 1
    assert json.loads(capsys.readouterr().out)["findings"]


def test_cli_invalid_toml_returns_error_not_clean_report(tmp_path, capsys):
    path = tmp_path / "bad.toml"
    path.write_text("[unclosed", encoding="utf-8")
    assert audit.main(["--project", str(path)]) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert "Dependency inventory error" in captured.err


def test_repository_declares_no_base_dependencies():
    tomllib = pytest.importorskip("tomllib", reason="Source inventory is a Python 3.11+ developer tool")
    path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    assert document["project"]["dependencies"] == []
    assert {audit.requirement_name(item) for item in document["project"]["optional-dependencies"]["dev"]} >= {
        "pytest", "ruff", "mypy",
    }


@pytest.mark.parametrize("declaration", [
    "42", "true", '["MIT"]', "{text=42}", "{file=42}",
    '{file=""}', '{text="MIT",file="LICENSE"}', "{}", '{unknown="MIT"}',
])
def test_cli_malformed_license_is_actionable_invalid_input(tmp_path, capsys, declaration):
    pytest.importorskip("tomllib", reason="Source inventory is a Python 3.11+ developer tool")
    path = tmp_path / "pyproject.toml"
    path.write_text(f'[project]\nname="example"\nlicense={declaration}\n', encoding="utf-8")
    assert audit.main(["--project", str(path)]) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert "project.license" in captured.err
    assert "Traceback" not in captured.err


def test_missing_stdlib_toml_parser_has_actionable_error(project, monkeypatch):
    import builtins
    original_import = builtins.__import__

    def without_tomllib(name, *args, **kwargs):
        if name == "tomllib":
            raise ImportError("No module named tomllib")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_tomllib)
    with pytest.raises(ValueError, match="Python 3.11"):
        audit.audit_project(project)


def test_scan_works_with_network_and_provider_imports_blocked(project, monkeypatch, capsys):
    import builtins
    import socket
    original_import = builtins.__import__

    def offline_import(name, *args, **kwargs):
        if name.split(".")[0] in {"google", "google_auth_oauthlib", "google_auth_httplib2", "googleapiclient", "boto3"}:
            raise AssertionError("Optional provider imported by offline audit")
        return original_import(name, *args, **kwargs)

    def deny_network(*args, **kwargs):
        raise AssertionError("Network attempted by offline audit")

    monkeypatch.setattr(builtins, "__import__", offline_import)
    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "getaddrinfo", deny_network)
    assert audit.main(["--project", str(project), "--environment"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["installed_environment"] == []
    assert not result["license_metadata_complete"]
