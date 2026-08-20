"""CLI adapter for the Phase F0 Reason Entity baseline generator."""

from __future__ import annotations

import json
from pathlib import Path

from toolchain.reason_entity_baseline import generate_baseline, validate_baseline

DEFAULT_OUTPUT = Path("artifacts/reason_entity/f0")


def run(args: list[str], root: Path) -> int:
    if not args or args[0] not in {"generate", "validate"}:
        print("Usage: reason reason-entity-baseline <generate|validate> [--output <dir>] [--json]")
        return 1
    output = _path_option(args, "--output", root / DEFAULT_OUTPUT)
    if args[0] == "generate":
        result = generate_baseline(root, output)
        if "--json" in args:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            print(f"Generated {result['artifact_count']} Reason Entity F0 artifacts in {output}")
        return 0
    result = validate_baseline(root, output)
    if "--json" in args:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(
            "Reason Entity F0 baseline valid"
            if result["ok"]
            else f"Reason Entity F0 baseline not validated: {len(result.get('issues', []))} issue(s)"
        )
    return 0 if result["ok"] else 1


def _path_option(args: list[str], name: str, default: Path) -> Path:
    if name not in args:
        return default
    index = args.index(name)
    if index + 1 >= len(args):
        return default
    path = Path(args[index + 1])
    return path if path.is_absolute() else Path.cwd() / path
