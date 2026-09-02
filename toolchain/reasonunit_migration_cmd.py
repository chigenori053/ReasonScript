"""CLI adapter for `reason object migrate`."""

from __future__ import annotations

import json
from pathlib import Path

from toolchain.reasonunit_migration import (
    MigrationError,
    analyze,
    compare,
    convert,
    discover,
    dry_run,
    generate_migration_profile,
    plan,
    publish,
    rollback,
    status,
    validate,
    validate_migration_profile,
)


def _option(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def _path(value: str) -> Path:
    path = Path(value); return path if path.is_absolute() else Path.cwd() / path


def _positionals(args: list[str]) -> list[str]:
    values, skip = [], False
    valued = {"--output", "--profile", "--staging", "--target"}
    for item in args:
        if skip: skip = False; continue
        if item in valued: skip = True; continue
        if not item.startswith("--"): values.append(item)
    return values


def run(args: list[str], root: Path) -> int:
    operation = args[0] if args else ""; allowed = {"discover", "analyze", "plan", "dry-run", "convert", "compare", "validate", "publish", "rollback", "status", "generate", "validate-phase"}
    try:
        if operation not in allowed: raise MigrationError("RUO-M1-021", "usage: reason object migrate <discover|analyze|plan|dry-run|convert|compare|validate|publish|rollback|status|validate-phase>")
        positional = _positionals(args[1:])
        source = _path(positional[0]) if positional else None
        if operation == "discover":
            output = _option(args, "--output")
            if not source or not output: raise MigrationError("RUO-M1-021", "discover requires SOURCE --output INVENTORY.json")
            result = discover(source, _path(output))
        elif operation == "analyze":
            if not source: raise MigrationError("RUO-M1-021", "analyze requires INVENTORY")
            result = analyze(source, _option(args, "--profile") or "legacy-json/1")
            if _option(args, "--output"): _path(_option(args, "--output") or "").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        elif operation == "plan":
            output = _option(args, "--output")
            if not source or not output: raise MigrationError("RUO-M1-021", "plan requires ANALYSIS --output PLAN")
            result = plan(source, _path(output))
        elif operation in {"dry-run", "convert", "compare", "validate", "status"}:
            if not source: raise MigrationError("RUO-M1-021", f"{operation} requires PLAN")
            staging = _path(_option(args, "--staging") or str(source.parent / "staging"))
            result = {"dry-run": dry_run, "convert": convert, "compare": compare, "validate": validate}.get(operation, status)(source, staging)
        elif operation == "publish":
            target = _option(args, "--target")
            if not source or not target: raise MigrationError("RUO-M1-021", "publish requires PLAN --target TARGET")
            result = publish(source, _path(_option(args, "--staging") or str(source.parent / "staging")), _path(target), allow_write="--allow-write" in args)
        elif operation == "rollback":
            if not source: raise MigrationError("RUO-M1-021", "rollback requires ROLLBACK.json")
            result = rollback(source, allow_write="--allow-write" in args)
        else:
            output = _path(_option(args, "--output") or "artifacts/reasonunit_migration/ruo_m1")
            result = generate_migration_profile(root, output) if operation == "generate" else validate_migration_profile(root, output)
        ok = result.get("ok", result.get("phase_status") != "NOT_VALIDATED" and result.get("status") not in {"REJECTED", "NOT_VALIDATED"})
        document = {"command": f"object migrate {operation}", "ok": bool(ok), "exit_status": 0 if ok else 1, "diagnostics": result.get("issues", []), **result}
    except (MigrationError, OSError, ValueError, json.JSONDecodeError) as error:
        code = error.code if isinstance(error, MigrationError) else "RUO-M1-021"; document = {"command": f"object migrate {operation}", "ok": False, "exit_status": 1, "diagnostics": [{"code": code, "severity": "ERROR", "stage": operation, "message": str(error)}]}
    print(json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) if "--json" in args else f"RUO-M1 {operation} {'succeeded' if document['ok'] else 'failed'}")
    return document["exit_status"]
