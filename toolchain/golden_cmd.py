"""Top-level `reason golden` command wrappers."""

from __future__ import annotations

from pathlib import Path

from toolchain.diagnostics import render_diagnostics
from toolchain.golden import run_corpus, stable_json, update_corpus


def run(command: str, args: list[str], project_root: Path) -> int:
    json_output = "--json" in args
    out_dir = _option_value(args, "--out")
    corpus_root = _path_arg(args, project_root / "golden")
    if command == "update-golden":
        manifest = update_corpus(corpus_root)
        if json_output:
            print(stable_json(manifest), end="")
        else:
            print("ReasonScript golden corpus updated")
            print(f"cases: {manifest['total_cases']}")
        return 0
    result = run_corpus(corpus_root, out_dir=out_dir)
    payload = result["summary"] if command == "golden-summary" else result["report"]
    if json_output:
        print(stable_json(payload), end="")
    else:
        summary = result["summary"]
        print("ReasonScript golden corpus")
        print(f"total: {summary['total']}")
        print(f"passed: {summary['passed']}")
        print(f"failed: {summary['failed']}")
        print(f"skipped: {summary['skipped']}")
        if summary["failed"]:
            print(render_diagnostics(result["diagnostics"]["diagnostics"]))
    return 0 if result["summary"]["failed"] == 0 else 1


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
