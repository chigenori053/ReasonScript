"""CLI wrapper for `reason ci` (reasonscript-ci/1.0)."""

from __future__ import annotations

from pathlib import Path

from toolchain.ci import (
    DEFAULT_TEST_COMMAND,
    ci_report,
    ci_summary,
    run_pipeline,
    write_ci_reports,
)
from toolchain.diagnostics import render_diagnostics
from toolchain.diagnostics import stable_json as render_json


def run(command: str, args: list[str], project_root: Path) -> int:
    json_output = "--json" in args
    skip_tests = "--skip-tests" in args
    out_dir = _option_value(args, "--out")
    root = _path_arg(args, project_root)

    result = run_pipeline(root, run_tests=not skip_tests, test_command=DEFAULT_TEST_COMMAND)

    if out_dir is not None:
        write_ci_reports(Path(out_dir), result)

    if json_output:
        print(render_json(ci_report(result)), end="")
    else:
        summary = ci_summary(result)
        print("ReasonScript CI " + summary["status"])
        for phase in result["phases"]:
            print(f"  {phase['id']}: {phase['status']}")
        if result["diagnostics"]:
            print(render_diagnostics(result["diagnostics"]))

    return 0 if result["ok"] else 1


def _path_arg(args: list[str], default: Path) -> Path:
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in {"--json", "--skip-tests"}:
            continue
        if arg == "--out":
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
