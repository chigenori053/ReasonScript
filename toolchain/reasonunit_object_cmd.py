"""CLI for RUO-U1 universal Object generation and validation."""

from __future__ import annotations
import json
from pathlib import Path
from toolchain.reasonunit_object import generate_universal_model, validate_universal_model

DEFAULT_OUTPUT = Path("artifacts/reasonunit_object/ruo_u1")

def run(args: list[str], root: Path) -> int:
    if not args or args[0] not in {"generate", "validate"}:
        print("Usage: reason reasonunit-object <generate|validate> [--output <dir>] [--ruo-c1 <dir>] [--json]"); return 1
    output = _option(args, "--output", root / DEFAULT_OUTPUT); c1 = _option(args, "--ruo-c1", root / "artifacts/reasonunit_compatibility/ruo_c1")
    result = generate_universal_model(root, output, c1_directory=c1) if args[0] == "generate" else validate_universal_model(root, output, c1_directory=c1)
    ok = result.get("phase_status") == "VALIDATED" if args[0] == "generate" else result.get("ok", False)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True) if "--json" in args else (f"RUO-U1 {'generated' if args[0] == 'generate' else 'valid'}" if ok else f"RUO-U1 NOT_VALIDATED: {len(result.get('issues', []))} issue(s)"))
    return 0 if ok else 1

def _option(args: list[str], name: str, default: Path) -> Path:
    if name not in args or args.index(name) + 1 >= len(args): return default
    value = Path(args[args.index(name) + 1]); return value if value.is_absolute() else Path.cwd() / value
