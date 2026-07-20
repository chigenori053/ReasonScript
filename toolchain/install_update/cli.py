"""CLI surface for ``reason update``."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import REPORT_SCHEMA, UpdateEngine, UpdateError


def _emit(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"ReasonScript update: {payload.get('status', 'unknown')}")
    if payload.get("from_version") or payload.get("installed_version"):
        print(f"from: {payload.get('from_version', payload.get('installed_version'))}")
    if payload.get("to_version") or payload.get("package_version"):
        print(f"to: {payload.get('to_version', payload.get('package_version'))}")
    freshness = payload.get("freshness")
    if isinstance(freshness, dict) and freshness.get("status"):
        print(f"freshness: {freshness['status']}")
    for diagnostic in payload.get("diagnostics", []):
        print(f"{diagnostic.get('code')}: {diagnostic.get('message')}", file=sys.stderr)


def _package_report(archive: Path, *, expected_commit: str | None, allow_development: bool,
                    check_platform: bool) -> tuple[dict[str, Any], int]:
    """Inspect or validate a package archive without touching any installation."""
    from .package_validator import validate_package_provenance
    from .platform import current_adapter

    adapter = current_adapter()
    engine = UpdateEngine(Path.cwd(), adapter, validator=lambda _: {})
    try:
        package = engine.open_package(archive)
    except UpdateError as exc:
        return ({"schema_version": REPORT_SCHEMA, "status": "invalid_package", "package_path": str(archive),
                 "freshness": {"status": "invalid"}, "diagnostics": [exc.diagnostic()]}, exc.exit_code)
    try:
        report = validate_package_provenance(
            package.root,
            platform=adapter.name if check_platform else None,
            architecture=adapter.architecture if check_platform else None,
            expected_commit=expected_commit,
            archive_name=archive.name if archive.is_file() else None,
            allow_development=allow_development,
        )
        file_count = len((package.checksums.get("files") or []))
        payload: dict[str, Any] = {
            "schema_version": REPORT_SCHEMA,
            "status": "valid" if report.valid and report.manifest is not None else "invalid_package",
            "package_path": str(archive),
            "expected_version": package.manifest.get("package_version"),
            "file_count": file_count,
            **report.to_dict(),
        }
        if report.manifest is not None:
            payload["manifest"] = report.manifest
        else:
            payload["status"] = "legacy_package"
        return payload, 0 if payload["status"] == "valid" else 4
    finally:
        package.close()


def _run_package_command(command: str, args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog=f"reason update {command}")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-commit")
    parser.add_argument("--allow-development-package", action="store_true")
    parser.add_argument("--json", action="store_true")
    try:
        parsed = parser.parse_args(args)
    except SystemExit as exc:
        return int(exc.code)
    payload, code = _package_report(
        parsed.archive.expanduser().resolve(),
        expected_commit=parsed.expected_commit,
        allow_development=parsed.allow_development_package,
        check_platform=command == "package-validate",
    )
    if command == "package-inspect" and parsed.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif command == "package-inspect":
        print(f"package: {payload.get('package_path')}")
        print(f"status: {payload.get('status')}")
        print(f"freshness: {payload.get('freshness', {}).get('status')}")
        for key, value in sorted((payload.get("package") or {}).items()):
            print(f"{key}: {value}")
    else:
        _emit(payload, parsed.json)
    return code


def run(args: list[str]) -> int:
    if args and args[0] in {"package-inspect", "package-validate"}:
        return _run_package_command(args[0], args[1:])
    parser = argparse.ArgumentParser(prog="reason update")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true")
    action.add_argument("--validate", action="store_true")
    action.add_argument("--rollback", action="store_true")
    parser.add_argument("--package", type=Path)
    parser.add_argument("--prefix", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--expected-commit")
    parser.add_argument("--allow-development-package", action="store_true")
    parser.add_argument("--allow-legacy-package", action="store_true")
    try:
        parsed = parser.parse_args(args)
        if (parsed.check or (not parsed.validate and not parsed.rollback)) and parsed.package is None:
            parser.error("--package is required for check or update")
    except SystemExit as exc:
        return int(exc.code)
    engine = UpdateEngine(parsed.prefix, expected_commit=parsed.expected_commit,
                          allow_development_package=parsed.allow_development_package,
                          allow_legacy_package=parsed.allow_legacy_package)
    try:
        if parsed.check:
            payload = engine.check(parsed.package, parsed.force)
            code = 0 if payload.get("status") != "package_rejected" else 4
        elif parsed.validate:
            payload, code = engine.validate_active()
        elif parsed.rollback:
            payload, code = engine.rollback()
        else:
            payload, code = engine.update(parsed.package, parsed.force)
    except UpdateError as exc:
        payload, code = engine._failure_report(exc, parsed.package), exc.exit_code
    _emit(payload, parsed.json)
    return code
