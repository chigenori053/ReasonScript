"""Unified Execution Runtime command surface."""

from __future__ import annotations

import json

from frontend.unified_execution_runtime import runtime_info


def run(args: list[str]) -> int:
    if args == ["info"] or args == ["info", "--json"]:
        print(json.dumps(runtime_info(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print("Usage: reason runtime info [--json]")
    return 1
