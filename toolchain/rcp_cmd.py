"""Thin CLI adapter; RCP execution and validation belong to the Rust host."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from toolchain.native_runtime import resolve_native_reasonunit_runtime


def run(args: list[str], root: Path) -> int:
    if len(args) not in (2, 3) or args[0] != "run" or (len(args) == 3 and args[2] != "--json"):
        print("Usage: reason rcp run SESSION.json [--json]")
        return 1
    try:
        with Path(args[1]).open("rb") as source:
            data = source.read(1_048_577)
        if len(data) > 1_048_576:
            raise ValueError("RCP-001: session byte limit")
        completed = subprocess.run([str(resolve_native_reasonunit_runtime()), "rcp"], input=data, cwd=root, capture_output=True, timeout=30, check=False)
        result = json.loads(completed.stdout)
        if completed.returncode != 0 or result.get("schema") != "reasonscript-rcp-session/0.1":
            if result.get("ok"):
                raise ValueError("RCP-001: incompatible native session adapter")
            result["ok"] = False
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        result = {"ok": False, "diagnostics": [{"code": "RCP-001", "message": str(error)}]}
    if "--json" in args:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    else:
        print(f"RCP Foundation session {'succeeded' if result.get('ok') else 'failed'}")
    return 0 if result.get("ok") else 1
