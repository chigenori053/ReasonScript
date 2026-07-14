"""CLI surface for ``reason update``."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import UpdateEngine, UpdateError


def _emit(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"ReasonScript update: {payload.get('status', 'unknown')}")
    if payload.get("from_version") or payload.get("installed_version"):
        print(f"from: {payload.get('from_version', payload.get('installed_version'))}")
    if payload.get("to_version") or payload.get("package_version"):
        print(f"to: {payload.get('to_version', payload.get('package_version'))}")
    for diagnostic in payload.get("diagnostics", []):
        print(f"{diagnostic.get('code')}: {diagnostic.get('message')}", file=sys.stderr)


def run(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="reason update")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true")
    action.add_argument("--validate", action="store_true")
    action.add_argument("--rollback", action="store_true")
    parser.add_argument("--package", type=Path)
    parser.add_argument("--prefix", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--force", action="store_true")
    try:
        parsed = parser.parse_args(args)
        if (parsed.check or (not parsed.validate and not parsed.rollback)) and parsed.package is None:
            parser.error("--package is required for check or update")
    except SystemExit as exc:
        return int(exc.code)
    engine = UpdateEngine(parsed.prefix)
    try:
        if parsed.check:
            payload, code = engine.check(parsed.package, parsed.force), 0
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
