"""CLI wrappers for reasonscript-agent-protocol/1.0."""

from __future__ import annotations

from pathlib import Path

from toolchain.agent_protocol import agent_report, render_json, validate_repository
from toolchain.diagnostics import render_diagnostics


def run(command: str, args: list[str], project_root: Path) -> int:
    json_output = "--json" in args
    if command == "agent-protocol":
        root = _path_arg(args, project_root)
        result = validate_repository(root)
        if json_output:
            print(render_json(result), end="")
        else:
            print("ReasonScript agent protocol " + ("passed" if result["ok"] else "failed"))
            if not result["ok"]:
                print(render_diagnostics(result["diagnostics"]))
        return 0 if result["ok"] else 1

    if command == "agent-report":
        report = agent_report(
            task=_option_value(args, "--task") or "Phase 7.5",
            status=_option_value(args, "--status") or "VALIDATED",
            tests_passed=_int_option(args, "--tests-passed"),
            artifacts_generated="--artifacts-generated" in args,
        )
        if json_output:
            print(render_json(report), end="")
        else:
            print("ReasonScript agent report")
            print(f"task: {report['task']}")
            print(f"status: {report['status']}")
            print(f"tests_passed: {report['tests_passed']}")
            print(f"artifacts_generated: {str(report['artifacts_generated']).lower()}")
        return 0

    print(f"Unknown agent protocol command: {command}")
    return 2


def _path_arg(args: list[str], default: Path) -> Path:
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in {"--json", "--artifacts-generated"}:
            continue
        if arg in {"--task", "--status", "--tests-passed"}:
            skip_next = True
            continue
        if arg.startswith("--"):
            continue
        return Path(arg)
    return default


def _option_value(args: list[str], option: str) -> str | None:
    if option not in args:
        return None
    index = args.index(option)
    if index + 1 >= len(args):
        return None
    return args[index + 1]


def _int_option(args: list[str], option: str) -> int:
    value = _option_value(args, option)
    if value is None:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0
