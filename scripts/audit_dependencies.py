"""Offline declaration/license metadata inventory (Python 3.11+, stdlib only).

This is not a vulnerability scan or a resolved, standards-compliant SBOM.
Run with the interpreter of the environment being inventoried. No optional
provider imports, package installation, subprocesses, or networking are used.
See docs/sbom.md for limitations and release-resolution procedures.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "mac-speech-dependency-inventory-v1"
LICENSE_FILENAME = re.compile(r"^(LICENSE|LICENCE|COPYING|NOTICE)(?:[._-].*)?$", re.I)


def normalize_name(name: str) -> str:
    """PEP 503 normalization, not requirement/version evaluation."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(requirement: str) -> str:
    """Extract the distribution name while retaining the declaration verbatim.

    This deliberately does not interpret PEP 440 constraints, environment
    markers, extras, or URLs; a resolver must do that for a release.
    """
    match = re.match(r"^\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)", requirement)
    if match is None:
        raise ValueError("Requirement must begin with a distribution name")
    return normalize_name(match.group(1))


def clean_label(value: str | None) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ValueError("License metadata must be text")
    if not value or value.strip().upper() in {"UNKNOWN", "NONE", "NOASSERTION"}:
        return None
    return value.strip()


def distribution_record(distribution: Any) -> dict[str, Any]:
    """Report metadata evidence without guessing SPDX IDs from classifiers."""
    fields = distribution.metadata
    expression = clean_label(fields.get("License-Expression"))
    legacy = clean_label(fields.get("License"))
    classifiers = [
        item for item in fields.get_all("Classifier", [])
        if item.startswith("License ::")
    ]
    # Generic 'License :: OSI Approved' is not an actual license identification.
    specific_classifiers = [item for item in classifiers if item.count(" :: ") >= 2]
    files = set(fields.get_all("License-File", []))
    files.update(
        str(path) for path in (distribution.files or [])
        if LICENSE_FILENAME.match(Path(str(path)).name)
    )
    return {
        "name": fields["Name"],
        "version": distribution.version,
        "license_expression": expression,
        "license_legacy": legacy,
        "license_classifiers": classifiers,
        "license_files": sorted(files),
        "license_metadata_present": bool(expression or legacy or specific_classifiers),
    }


def installed_record(name: str) -> dict[str, Any] | None:
    try:
        return distribution_record(metadata.distribution(name))
    except metadata.PackageNotFoundError:
        return None


def declaration_groups(document: dict[str, Any]) -> dict[str, list[str]]:
    project = document.get("project", {})
    dynamic = project.get("dynamic", [])
    if "dependencies" in dynamic or "optional-dependencies" in dynamic:
        raise ValueError("Dynamic dependencies require built package metadata; cannot inventory statically")
    groups = {
        "runtime": project.get("dependencies", []),
        "build": document.get("build-system", {}).get("requires", []),
    }
    for name, requirements in project.get("optional-dependencies", {}).items():
        if name in groups:
            raise ValueError(f"Extra name conflicts with inventory group: {name}")
        groups[name] = requirements
    for requirements in groups.values():
        if not isinstance(requirements, list) or not all(isinstance(item, str) for item in requirements):
            raise ValueError("Dependency declarations must be arrays of requirement strings")
    return groups


def project_license_record(root: Path, project: dict[str, Any]) -> dict[str, Any]:
    declared = project.get("license")
    if declared is not None and not isinstance(declared, (str, dict)):
        raise ValueError("project.license must be text or a table containing file or text")
    if isinstance(declared, dict):
        if set(declared) not in ({"file"}, {"text"}):
            raise ValueError("project.license table must contain exactly one of file or text")
        key = next(iter(declared))
        if not isinstance(declared[key], str) or not declared[key].strip():
            raise ValueError(f"project.license.{key} must be non-empty text")
    files = sorted(path.name for path in root.iterdir() if path.is_file() and LICENSE_FILENAME.match(path.name))
    declared_file_present = None
    if isinstance(declared, dict) and "file" in declared:
        path = (root / declared["file"]).resolve()
        if root.resolve() not in path.parents:
            raise ValueError("Declared project license file must be inside the project")
        declared_file_present = path.is_file()
        if declared_file_present:
            files = sorted(set(files + [path.relative_to(root.resolve()).as_posix()]))
    identified = (
        bool(clean_label(declared)) if isinstance(declared, str)
        else bool(declared and (clean_label(declared.get("text")) or declared_file_present))
    )
    return {
        "declaration": declared,
        "text_files": files,
        "declared_file_present": declared_file_present,
        "license_metadata_present": identified,
        "note": "File presence/metadata only; no license grant is inferred or legally approved.",
    }


def audit_project(
    project_path: Path, *, groups: list[str] | None = None, environment: bool = False,
) -> dict[str, Any]:
    try:
        import tomllib
    except ImportError as exc:
        raise ValueError("Source TOML inventory needs Python 3.11+ (the wrapper still supports Python 3.9+)") from exc
    document = tomllib.loads(project_path.read_text(encoding="utf-8"))
    available = declaration_groups(document)
    selected = list(available) if groups is None else list(dict.fromkeys(groups))
    unknown = set(selected) - available.keys()
    if unknown:
        raise ValueError(f"Unknown inventory groups: {', '.join(sorted(unknown))}")
    project = document.get("project", {})
    root = project_path.resolve().parent
    project_license = project_license_record(root, project)
    findings = []
    if not project_license["license_metadata_present"]:
        findings.append("Project license unresolved: do not infer a grant from dependency licenses.")
    direct = []
    for group in selected:
        for requirement in available[group]:
            name = requirement_name(requirement)
            installed = installed_record(name)
            direct.append({
                "group": group,
                "scope": "development" if group in {"dev", "build"} else (
                    "runtime" if group == "runtime" else "optional-runtime"
                ),
                "requirement": requirement,
                "name": name,
                "installed": installed,
            })
            if installed is None:
                findings.append(f"{group}: {name}: not installed; license/version not scanned locally.")
            elif not installed["license_metadata_present"]:
                findings.append(f"{group}: {name}: installed license metadata missing/unknown.")
    snapshot = None
    if environment:
        snapshot = sorted(
            (distribution_record(item) for item in metadata.distributions()),
            key=lambda item: (normalize_name(item["name"]), item["version"]),
        )
        for item in snapshot:
            if not item["license_metadata_present"]:
                findings.append(f"environment: {item['name']}: license metadata missing/unknown.")
    return {
        "schema": SCHEMA,
        "kind": "declarations-and-local-metadata-inventory",
        "project": {"name": project.get("name"), "version": project.get("version"), "license": project_license},
        "declared_base_dependencies": available["runtime"],
        "selected_groups": selected,
        "direct_dependencies": direct,
        "installed_environment": snapshot,
        "license_metadata_complete": not findings,
        "findings": findings,
        "limitations": [
            "Requirement constraints and markers are not evaluated; installed versions may not satisfy declarations.",
            "Environment snapshot includes unrelated tools; it is not a resolved dependency graph or release SBOM.",
            "License fields/files are metadata evidence, not verified license texts or redistribution approval.",
            "No vulnerability/advisory lookup, network request, installation, or optional-provider import is performed.",
            "Swift manifests, native/system frameworks, external CLI tools and model/voice licenses need separate review.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1] / "pyproject.toml")
    parser.add_argument("--group", action="append", help="inventory runtime/build/dev/gdrive; repeat; default: all declared groups")
    parser.add_argument("--environment", action="store_true", help="also record all installed distribution versions/licenses")
    parser.add_argument("--check", action="store_true", help="exit 1 for incomplete project/dependency license metadata (not a security gate)")
    args = parser.parse_args(argv)
    try:
        report = audit_project(args.project, groups=args.group, environment=args.environment)
    except (OSError, ValueError, TypeError) as exc:
        print(f"Dependency inventory error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.check and not report["license_metadata_complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
