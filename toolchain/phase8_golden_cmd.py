"""CLI wrapper for Phase 8 Final golden validation."""

from __future__ import annotations

from pathlib import Path

from toolchain.phase8_golden_validation import render_json, update_phase8_golden, validate_phase8_golden


def run(command: str, args: list[str], project_root: Path) -> int:
    if command != "phase8-golden":
        print(f"Unknown phase8-golden command: {command}")
        return 2
    subcommand = args[0] if args else "validate"
    json_output = "--json" in args
    if subcommand not in {"validate", "update"}:
        _usage()
        return 1
    result = update_phase8_golden(project_root) if subcommand == "update" else validate_phase8_golden(project_root)
    if json_output:
        print(render_json(result), end="")
    else:
        print("ReasonScript Phase 8 golden validation " + result["status"])
        for scenario in result["scenarios"]:
            print(f"  {scenario['scenario']}: {scenario['status']}")
    return 0 if result["ok"] else 1


def _usage() -> None:
    print("Usage: reason phase8-golden validate [--json]")
    print("       reason phase8-golden update [--json]")
