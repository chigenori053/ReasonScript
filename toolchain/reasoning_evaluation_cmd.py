"""CLI wrapper for ReasoningEvaluationReport (`reason reasoning-eval`)."""

from __future__ import annotations

from pathlib import Path

from toolchain.reasoning_evaluation_report import (
    evaluate_reasoning_model,
    render_json,
    serialize_evaluation_report,
    validate_evaluation_report,
)


def run(command: str, args: list[str], project_root: Path) -> int:
    if command != "reasoning-eval":
        print(f"Unknown reasoning-eval command: {command}")
        return 2

    subcommand = args[0] if args else None
    json_output = "--json" in args
    file_arg = _file_arg(args[1:])
    if subcommand not in {"evaluate", "validate"} or file_arg is None:
        print("Usage: reason reasoning-eval evaluate <reasoning-model.json> [--json]")
        print("       reason reasoning-eval validate <evaluation-report.json> [--json]")
        return 1

    path = project_root / file_arg if not Path(file_arg).is_absolute() else Path(file_arg)
    if subcommand == "evaluate":
        report = evaluate_reasoning_model(path)
        if json_output:
            print(serialize_evaluation_report(report), end="")
        else:
            print("ReasonScript reasoning evaluation " + report["summary"]["status"])
            for check in report["checks"]:
                print(f"{check['status']}: {check['check_type']}: {check['message']}")
        return 0 if report["summary"]["passed"] else 1

    result = validate_evaluation_report(path)
    if json_output:
        print(render_json(result), end="")
    else:
        print("ReasonScript reasoning evaluation report " + ("valid" if result["valid"] else "invalid"))
        for diagnostic in result["diagnostics"]:
            print(f"{diagnostic['severity']}: {diagnostic['code']}: {diagnostic['message']}")
    return 0 if result["valid"] else 1


def _file_arg(args: list[str]) -> str | None:
    for arg in args:
        if arg == "--json" or arg.startswith("--"):
            continue
        return arg
    return None
