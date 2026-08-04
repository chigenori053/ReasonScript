"""CLI wrapper for reasonscript-reasoning-model/1.0 (`reason reasoning-model`)."""

from __future__ import annotations

from pathlib import Path

from toolchain.reasoning_model_contract import render_json, validate


def run(command: str, args: list[str], project_root: Path) -> int:
    if command != "reasoning-model":
        print(f"Unknown reasoning-model command: {command}")
        return 2

    subcommand = args[0] if args else None
    if subcommand != "validate":
        print("Usage: reason reasoning-model validate <file> [--json]")
        return 1

    json_output = "--json" in args
    file_arg = _file_arg(args[1:])
    if file_arg is None:
        print("Usage: reason reasoning-model validate <file> [--json]")
        return 1

    result = validate(project_root / file_arg if not Path(file_arg).is_absolute() else Path(file_arg))
    if json_output:
        print(render_json(result), end="")
    else:
        print("ReasonScript reasoning model " + ("valid" if result["valid"] else "invalid"))
        for diagnostic in result["diagnostics"]:
            print(f"{diagnostic['severity']}: {diagnostic['code']}: {diagnostic['message']}")
    return 0 if result["valid"] else 1


def _file_arg(args: list[str]) -> str | None:
    for arg in args:
        if arg == "--json" or arg.startswith("--"):
            continue
        return arg
    return None
