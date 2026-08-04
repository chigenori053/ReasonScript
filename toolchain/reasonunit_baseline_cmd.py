"""CLI adapter for the RUO-C0 baseline generator."""

from __future__ import annotations

import json
from pathlib import Path

from toolchain.reasonunit_baseline import generate_baseline, validate_baseline


DEFAULT_OUTPUT = Path("artifacts/reasonunit_baseline/ruo_c0")


def run(args: list[str], root: Path) -> int:
    if not args or args[0] not in {"generate", "validate"}:
        print("Usage: reason reasonunit-baseline <generate|validate> [--output <dir>] [--external-evidence <manifest>] [--json]")
        return 1
    output = _path_option(args, "--output", root / DEFAULT_OUTPUT)
    external = _path_option(args, "--external-evidence", None)
    if args[0] == "generate":
        result = generate_baseline(root, output, external_manifest=external)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True) if "--json" in args else f"Generated {result['artifact_count']} RUO-C0 artifacts in {output}")
        return 0
    result = validate_baseline(root, output, external_manifest=external)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True) if "--json" in args else ("RUO-C0 baseline valid" if result["ok"] else f"RUO-C0 baseline not validated: {len(result.get('issues', []))} artifact issues, {len(result.get('mandatory_failures', []))} mandatory failures"))
    return 0 if result["ok"] else 1


def _path_option(args: list[str], name: str, default: Path | None) -> Path | None:
    if name not in args:
        return default
    index = args.index(name)
    if index + 1 >= len(args):
        return default
    path = Path(args[index + 1])
    return path if path.is_absolute() else Path.cwd() / path
