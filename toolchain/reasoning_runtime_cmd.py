"""CLI wrapper for `reason reasoning-runtime` (Phase 8C)."""

from __future__ import annotations

from pathlib import Path

from toolchain.reasoning_runtime import (
    build_reasoning_model_from_artifacts,
    evaluate_generated_reasoning_model,
    render_json,
    run_reasoning_runtime,
    serialize_reasoning_runtime_result,
    validate_reasoning_runtime_result,
)


def run(command: str, args: list[str], project_root: Path) -> int:
    if command != "reasoning-runtime":
        print(f"Unknown reasoning-runtime command: {command}")
        return 2

    subcommand = args[0] if args else None
    json_output = "--json" in args
    file_arg = _file_arg(args[1:])
    if subcommand not in {"run", "build-model", "evaluate", "validate"} or file_arg is None:
        _usage()
        return 1

    path = project_root / file_arg if not Path(file_arg).is_absolute() else Path(file_arg)
    if subcommand == "validate":
        result = validate_reasoning_runtime_result(path)
        if json_output:
            print(render_json(result), end="")
        else:
            print("ReasonScript reasoning runtime result " + ("valid" if result["valid"] else "invalid"))
            for diagnostic in result["diagnostics"]:
                print(f"{diagnostic['severity']}: {diagnostic['code']}: {diagnostic['message']}")
        return 0 if result["valid"] else 1

    runtime_result = run_reasoning_runtime(path)
    if subcommand == "run":
        if json_output:
            print(serialize_reasoning_runtime_result(runtime_result), end="")
        else:
            print("ReasonScript reasoning runtime " + runtime_result["pipeline_status"]["status"])
            print(f"model: {runtime_result.get('reasoning_model', {}).get('model_id')}")
            print(f"evaluation: {runtime_result.get('evaluation_report', {}).get('summary', {}).get('status')}")
        return 0 if runtime_result["pipeline_status"]["status"] in {"passed", "partial"} else 1

    if subcommand == "build-model":
        model = build_reasoning_model_from_artifacts(_source_bundle(path))
        if json_output:
            from toolchain.reasoning_model_contract import serialize_reasoning_model
            print(serialize_reasoning_model(model), end="")
        else:
            print("ReasonScript reasoning model built")
            print(f"model: {model.get('model_id')}")
        return 0

    report = evaluate_generated_reasoning_model(build_reasoning_model_from_artifacts(_source_bundle(path)))
    if json_output:
        from toolchain.reasoning_evaluation_report import serialize_evaluation_report
        print(serialize_evaluation_report(report), end="")
    else:
        print("ReasonScript reasoning evaluation " + report["summary"]["status"])
    return 0 if report["summary"]["passed"] else 1


def _source_bundle(path: Path) -> dict:
    from scripts.reason_cli import _analyze_result
    return _analyze_result(path, "normal")


def _file_arg(args: list[str]) -> str | None:
    for arg in args:
        if arg == "--json" or arg.startswith("--"):
            continue
        return arg
    return None


def _usage() -> None:
    print("Usage: reason reasoning-runtime run <source.rsn> [--json]")
    print("       reason reasoning-runtime build-model <source.rsn> [--json]")
    print("       reason reasoning-runtime evaluate <source.rsn> [--json]")
    print("       reason reasoning-runtime validate <runtime-result.json> [--json]")
