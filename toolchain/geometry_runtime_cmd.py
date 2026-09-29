"""CLI adapter for the native Geometry runtime."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def run(args: list[str], root: Path) -> int:
    if not args or args[0] not in {"run", "observe", "rus"} or len(args) < (3 if args[0] == "rus" else 2):
        print("Usage: reason geometry <run|observe> <vision-observation.json> [--json]")
        print("       reason geometry rus <geometry-state.json> <steps.json> [--json]")
        return 1
    source = Path(args[1])
    if not source.is_absolute():
        source = root / source
    distribution_root = Path(__file__).resolve().parents[1]
    binary_name = "reason-geometry.exe" if os.name == "nt" else "reason-geometry"
    installed = distribution_root / "bin" / binary_name
    binary = distribution_root / "ReasonRuntime/target/debug" / binary_name
    sources = [*(distribution_root / "ReasonRuntime/crates/geometry-core/src").glob("*.rs"), *(distribution_root / "ReasonRuntime/crates/vision-core/src").glob("*.rs")]
    current = binary.is_file() and binary.stat().st_mtime_ns >= max(path.stat().st_mtime_ns for path in sources)
    command = [str(installed)] if installed.is_file() else ([str(binary)] if current else ["cargo", "run", "--offline", "--quiet", "--manifest-path", str(distribution_root / "ReasonRuntime/crates/geometry-core/Cargo.toml"), "--bin", "reason-geometry", "--"])
    native_args = [args[0], str(source)]
    if args[0] == "rus":
        steps = Path(args[2])
        native_args.append(str(steps if steps.is_absolute() else root / steps))
    result = subprocess.run([*command, *native_args], cwd=root, capture_output=True, text=True, check=False)
    if "--json" in args:
        print(result.stdout.strip() or json.dumps({"ok": False, "error": result.stderr.strip()}))
    else:
        if result.returncode:
            print(result.stdout.strip() or result.stderr.strip())
        else:
            value = json.loads(result.stdout)
            print(f"Geometry Runtime {args[0]} completed")
    return result.returncode
