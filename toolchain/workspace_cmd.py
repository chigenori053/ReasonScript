"""CLI commands for reasonscript-workspace/1.0."""

from __future__ import annotations

from pathlib import Path
import sys

from .workspace_foundation import (
    build_workspace_index,
    stable_json,
    workspace_summary,
    write_workspace_artifacts,
)


def run(command: str, args: list[str], project_root: Path) -> int:
    path = _path_arg(args, project_root)
    json_output = "--json" in args
    out_dir = _option_value(args, "--out")

    if command == "scan":
        index = build_workspace_index(path)
        payload = {"schema": "reasonscript-workspace-scan/1.0", "files": index["files"], "directories": index["directories"]}
        if json_output:
            print(stable_json(payload), end="")
        else:
            print("ReasonScript workspace scan")
            print(f"root: {Path(path).resolve()}")
            print(f"files: {len(payload['files'])}")
            print(f"directories: {len(payload['directories'])}")
        return _exit_code(index)

    if command == "index":
        result = write_workspace_artifacts(path, out_dir)
        if json_output:
            print(stable_json({"schema": "reasonscript-workspace-index/1.0", **result, "index": result["index"]}), end="")
        else:
            print("ReasonScript workspace index")
            print(f"out: {result['out_dir']}")
            print(f"artifacts: {len(result['artifacts'])}")
            print(f"diagnostics: {result['summary']['diagnostics']}")
        return _exit_code(result["index"])

    index = build_workspace_index(path)
    summary = workspace_summary(index)
    if command == "summary":
        if json_output:
            print(stable_json(summary), end="")
        else:
            _print_summary(summary)
        return _exit_code(index)

    if command == "workspace":
        if out_dir is not None:
            write_workspace_artifacts(path, out_dir)
        if json_output:
            print(stable_json(index), end="")
        else:
            _print_summary(summary)
        return _exit_code(index)

    print(f"Unknown workspace command: {command}", file=sys.stderr)
    return 2


def _print_summary(summary: dict[str, object]) -> None:
    print("ReasonScript Workspace")
    print(f"Project: {summary['project']}")
    print(f"Language Version: {summary['language']}")
    print(f"Workspace Version: {summary['workspace']}")
    print(f"Files: {summary['files']}")
    print(f"Modules: {summary['modules']}")
    print(f"Functions: {summary['functions']}")
    print(f"Calculations: {summary['calculations']}")
    print(f"Dependencies: {summary['dependencies']}")
    print(f"Diagnostics: {summary['diagnostics']}")


def _path_arg(args: list[str], default: Path) -> Path:
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in {"--json"}:
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


def _exit_code(index: dict[str, object]) -> int:
    diagnostics = index.get("diagnostics", [])
    if isinstance(diagnostics, list) and any(
        isinstance(diagnostic, dict) and diagnostic.get("severity") == "error"
        for diagnostic in diagnostics
    ):
        return 1
    return 0
