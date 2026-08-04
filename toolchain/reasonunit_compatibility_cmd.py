"""CLI adapter for RUO-C1 compatibility generation and validation."""

from __future__ import annotations

import json
from pathlib import Path

from toolchain.reasonunit_compatibility import (
    generate_compatibility,
    validate_compatibility,
)

DEFAULT_OUTPUT = Path("artifacts/reasonunit_compatibility/ruo_c1")


def run(args: list[str], root: Path) -> int:
    if not args or args[0] not in {"generate", "validate"}:
        print("Usage: reason reasonunit-compatibility <generate|validate> [--output <dir>] [--ruo-c0 <dir>] [--json]")
        return 1
    output = _path_option(args, "--output", root / DEFAULT_OUTPUT)
    c0 = _path_option(args, "--ruo-c0", root / "artifacts/reasonunit_baseline/ruo_c0")
    if args[0] == "generate":
        result = generate_compatibility(root, output, c0_directory=c0)
    else:
        result = validate_compatibility(root, output, c0_directory=c0)
    if "--json" in args:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        ok = result.get("phase_status") == "VALIDATED" if args[0] == "generate" else result.get("ok", False)
        print(f"RUO-C1 {'generated' if args[0] == 'generate' else 'valid'}" if ok else f"RUO-C1 NOT_VALIDATED: {len(result.get('issues', []))} issue(s)")
    return 0 if (result.get("phase_status") == "VALIDATED" if args[0] == "generate" else result.get("ok")) else 1


def _path_option(args: list[str], name: str, default: Path) -> Path:
    if name not in args:
        return default
    index = args.index(name)
    if index + 1 >= len(args):
        return default
    path = Path(args[index + 1])
    return path if path.is_absolute() else Path.cwd() / path
