"""CLI wrapper for `reason ci-entry` (reasonscript-ci-entry/1.0)."""

from __future__ import annotations

from pathlib import Path

from toolchain.ci_entry import render_json, validate_entry_point
from toolchain.diagnostics import render_diagnostics


def run(command: str, args: list[str], project_root: Path) -> int:
    json_output = "--json" in args
    root = _path_arg(args, project_root)

    result = validate_entry_point(root)

    if json_output:
        print(render_json(result), end="")
    else:
        print("ReasonScript CI entry point " + ("passed" if result["ok"] else "failed"))
        if not result["ok"]:
            print(render_diagnostics(result["diagnostics"]))

    return 0 if result["ok"] else 1


def _path_arg(args: list[str], default: Path) -> Path:
    for arg in args:
        if arg == "--json":
            continue
        if arg.startswith("--"):
            continue
        return Path(arg)
    return default
