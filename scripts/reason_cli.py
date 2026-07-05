"""Official ReasonScript compiler/runtime CLI used by scripts/dev.py."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from playground.backend.main import SourceRequest, analyze_endpoint
from scripts.reason_artifacts import stable_json, write_cli_artifacts
from toolchain.artifacts import validate_artifact_directory
from toolchain.diagnostics import render_diagnostics
from toolchain.workspace_cmd import run as run_workspace_command


REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_EXAMPLES_DIR = REPO_ROOT / "examples" / "v0_5"
INVALID_EXAMPLES_DIR = VALID_EXAMPLES_DIR / "invalid"
IGNORED_DIRS = {".git", "node_modules", "target", "dist", "build", ".venv", "__pycache__", "artifacts"}


class CliFileSystemError(Exception):
    pass


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv or [])
    except CliFileSystemError as error:
        print(f"ReasonScript CLI filesystem error: {error}", file=sys.stderr)
        return 3
    except Exception as error:
        print(f"ReasonScript CLI internal error: {error}", file=sys.stderr)
        return 4


def _main(argv: list[str]) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code) if isinstance(error.code, int) else 2
    if not hasattr(args, "handler"):
        parser.print_usage(sys.stderr)
        return 2
    return args.handler(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 scripts/dev.py reason", description="ReasonScript CLI")
    subparsers = parser.add_subparsers(dest="subcommand")

    for name in ("check", "analyze", "run", "artifacts", "export"):
        sub = subparsers.add_parser(name)
        sub.add_argument("file")
        sub.add_argument("--compiler-mode", choices=["normal", "strict", "default"], default="normal")
        if name in {"check", "analyze", "run"}:
            sub.add_argument("--json", action="store_true")
        if name in {"analyze", "run", "artifacts", "export"}:
            sub.add_argument("--out")
        if name == "run":
            sub.add_argument("--trace", action="store_true")
        sub.set_defaults(handler={
            "check": cmd_check,
            "analyze": cmd_analyze,
            "run": cmd_run,
            "artifacts": cmd_artifacts,
            "export": cmd_artifacts,
        }[name])

    validate_artifacts = subparsers.add_parser("validate-artifacts")
    validate_artifacts.add_argument("artifact_dir")
    validate_artifacts.add_argument("--json", action="store_true")
    validate_artifacts.set_defaults(handler=cmd_validate_artifacts)

    manifest = subparsers.add_parser("manifest")
    manifest.add_argument("artifact_dir")
    manifest.add_argument("--json", action="store_true")
    manifest.set_defaults(handler=cmd_manifest)

    examples = subparsers.add_parser("examples")
    examples.add_argument("--json", action="store_true")
    examples.add_argument("--out")
    examples.set_defaults(handler=cmd_examples)

    build = subparsers.add_parser("build")
    build.add_argument("project_dir")
    build.add_argument("--json", action="store_true")
    build.set_defaults(handler=cmd_build)

    for name in ("workspace", "summary", "index", "scan"):
        sub = subparsers.add_parser(name)
        sub.add_argument("project_dir", nargs="?")
        sub.add_argument("--json", action="store_true")
        if name in {"workspace", "index"}:
            sub.add_argument("--out")
        sub.set_defaults(handler=cmd_workspace_foundation)

    test = subparsers.add_parser("test")
    test.add_argument("--json", action="store_true")
    test.set_defaults(handler=cmd_examples)
    return parser


def cmd_check(args: argparse.Namespace) -> int:
    result = _check_result(Path(args.file), args.compiler_mode)
    if args.json:
        print(stable_json(result), end="")
    else:
        _print_check(result)
    return 0 if result["ok"] else 1


def cmd_analyze(args: argparse.Namespace) -> int:
    result = _analyze_result(Path(args.file), args.compiler_mode)
    if args.out:
        _write_out(Path(args.out), result)
    if args.json:
        print(stable_json(result), end="")
    else:
        _print_analyze(result)
    return 0 if result["ok"] else 1


def cmd_run(args: argparse.Namespace) -> int:
    result = _run_result(Path(args.file), args.compiler_mode, include_trace=args.trace or args.json)
    if args.out:
        _write_out(Path(args.out), result)
    if args.json:
        print(stable_json(result), end="")
    else:
        _print_run(result)
    return 0 if result["ok"] else 1


def cmd_artifacts(args: argparse.Namespace) -> int:
    if not args.out:
        print("  [ERROR] reason artifacts requires --out <dir>", file=sys.stderr)
        return 2
    result = _analyze_result(Path(args.file), args.compiler_mode)
    _write_out(Path(args.out), result)
    print(f"ReasonScript artifacts written\nfile: {result['source_file']}\nout: {args.out}")
    return 0 if result["ok"] else 1


def cmd_validate_artifacts(args: argparse.Namespace) -> int:
    document = validate_artifact_directory(_resolve_input_path(Path(args.artifact_dir)))
    ok = len(document["diagnostics"]) == 0
    if args.json:
        print(stable_json(document), end="")
    else:
        print("ReasonScript artifact validation " + ("passed" if ok else "failed"))
        if not ok:
            print(render_diagnostics(document["diagnostics"]))
    return 0 if ok else 1


def cmd_manifest(args: argparse.Namespace) -> int:
    path = _resolve_input_path(Path(args.artifact_dir)) / "artifact_manifest.json"
    if not path.is_file():
        raise CliFileSystemError(f"artifact manifest not found: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if args.json:
        print(stable_json(manifest), end="")
    else:
        print("ReasonScript artifact manifest")
        print(f"generator: {manifest.get('generator')}")
        print(f"language_version: {manifest.get('language_version')}")
        print(f"artifacts: {len(manifest.get('artifacts', []))}")
    return 0


def cmd_examples(args: argparse.Namespace) -> int:
    result = _examples_result()
    if args.out:
        out = _resolve_output_dir(Path(args.out))
        out.mkdir(parents=True, exist_ok=True)
        (out / "examples_summary.json").write_text(stable_json(result), encoding="utf-8")
    if args.json:
        print(stable_json(result), end="")
    else:
        print("ReasonScript examples validation")
        print(f"valid_passed: {result['valid_passed']}/{result['valid_total']}")
        print(f"invalid_passed: {result['invalid_passed']}/{result['invalid_total']}")
        print(f"failed: {result['failed']}")
    return 0 if result["ok"] else 1


def cmd_build(args: argparse.Namespace) -> int:
    root = _resolve_input_path(Path(args.project_dir))
    if not root.is_dir():
        raise CliFileSystemError(f"project directory not found: {args.project_dir}")
    files = [
        path for path in sorted(root.rglob("*.rsn"))
        if not any(part in IGNORED_DIRS for part in path.relative_to(root).parts)
    ]
    results = [_check_result(path, "normal") for path in files]
    ok = all(item["ok"] for item in results)
    result = {
        "schema_version": "reasonscript-cli-build/0.1",
        "ok": ok,
        "project_dir": _display_path(root),
        "file_count": len(files),
        "diagnostics": [diag for item in results for diag in item["diagnostics"]],
        "results": results,
    }
    if args.json:
        print(stable_json(result), end="")
    else:
        print("ReasonScript build " + ("passed" if ok else "failed"))
        print(f"project: {_display_path(root)}")
        print(f"files: {len(files)}")
        print(f"diagnostics: {len(result['diagnostics'])}")
    return 0 if ok else 1


def cmd_workspace_foundation(args: argparse.Namespace) -> int:
    argv = []
    if getattr(args, "project_dir", None):
        argv.append(args.project_dir)
    if getattr(args, "json", False):
        argv.append("--json")
    if getattr(args, "out", None):
        argv.extend(["--out", args.out])
    return run_workspace_command(args.subcommand, argv, Path.cwd())


def _check_result(path: Path, compiler_mode: str) -> dict[str, Any]:
    response = _analyze_endpoint_response(path, compiler_mode)
    return {
        "schema_version": "reasonscript-cli-check/0.1",
        "ok": response["ok"],
        "source_file": _display_path(path),
        "compiler_mode": compiler_mode,
        "diagnostics": _cli_diagnostics(response.get("diagnostics", []), path),
    }


def _analyze_result(path: Path, compiler_mode: str) -> dict[str, Any]:
    response = _analyze_endpoint_response(path, compiler_mode)
    diagnostics = _cli_diagnostics(response.get("diagnostics", []), path)
    artifacts = response.get("artifacts") if isinstance(response.get("artifacts"), dict) else {}
    cli_artifacts = {
        "surface_ast": artifacts.get("ast"),
        "semantic_ast": artifacts.get("semantic_ast"),
        "reason_ir": artifacts.get("reason_ir"),
        "execution_plan": artifacts.get("execution_plan"),
        "simulation": artifacts.get("simulation"),
        "knowledge": artifacts.get("knowledge"),
        "validation": artifacts.get("validation"),
    }
    return {
        "ok": response["ok"],
        "schema_version": "reasonscript-cli-analyze/0.1",
        "source_file": _display_path(path),
        "compiler_mode": compiler_mode,
        "diagnostics": diagnostics,
        "project_state": response,
        "artifacts": cli_artifacts,
    }


def _run_result(path: Path, compiler_mode: str, *, include_trace: bool) -> dict[str, Any]:
    analyze = _analyze_result(path, compiler_mode)
    simulation = analyze["artifacts"].get("simulation") if isinstance(analyze.get("artifacts"), dict) else {}
    knowledge = analyze["artifacts"].get("knowledge") if isinstance(analyze.get("artifacts"), dict) else {}
    views = analyze["project_state"].get("views", {}) if isinstance(analyze.get("project_state"), dict) else {}
    output = views.get("output", {}) if isinstance(views, dict) else {}
    result = {
        "schema_version": "reasonscript-cli-run/0.1",
        "ok": analyze["ok"],
        "source_file": analyze["source_file"],
        "compiler_mode": compiler_mode,
        "diagnostics": analyze["diagnostics"],
        "goal_reached": simulation.get("goal_reached") if isinstance(simulation, dict) else None,
        "runtime_output": output.get("events", []) if isinstance(output, dict) else [],
        "knowledge": knowledge,
        "project_state": analyze["project_state"],
        "artifacts": analyze["artifacts"],
    }
    if include_trace:
        result["trace"] = simulation.get("trace", []) if isinstance(simulation, dict) else []
    return result


def _analyze_endpoint_response(path: Path, compiler_mode: str) -> dict[str, Any]:
    source = _read_source(path)
    req = SourceRequest(source=source, filename=_display_path(path), compiler_mode=compiler_mode)
    return analyze_endpoint(req)


def _read_source(path: Path) -> str:
    resolved = _resolve_input_path(path)
    if not resolved.exists():
        raise CliFileSystemError(f"file not found: {path}")
    if not resolved.is_file():
        raise CliFileSystemError(f"not a file: {path}")
    try:
        return resolved.read_text(encoding="utf-8")
    except OSError as error:
        raise CliFileSystemError(f"cannot read {path}: {error}") from error


def _resolve_input_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _resolve_output_dir(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _display_path(path: Path) -> str:
    resolved = _resolve_input_path(path).resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def _cli_diagnostics(diagnostics: list[dict[str, Any]], path: Path) -> list[dict[str, Any]]:
    result = []
    if _resolve_input_path(path).suffix != ".rsn":
        result.append({
            "severity": "warning",
            "code": "CLI-001",
            "message": "ReasonScript source files should use the .rsn extension.",
            "stage": "source",
            "source_file": _display_path(path),
            "line": None,
            "column": None,
            "evidence": None,
        })
    for item in diagnostics:
        code = item.get("code")
        if code == "LL-001C-MODULE-COMPAT-INFO":
            continue
        message = item.get("message", "Unknown diagnostic")
        if code and isinstance(message, str) and message.startswith(f"{code} "):
            message = message[len(str(code)) + 1:]
        result.append({
            "severity": item.get("severity", "error"),
            "code": code,
            "message": message,
            "stage": item.get("stage") or item.get("phase"),
            "source_file": _display_path(path),
            "line": item.get("line"),
            "column": item.get("column"),
            "evidence": item.get("evidence"),
        })
    return result


def _write_out(path: Path, result: dict[str, Any]) -> None:
    try:
        write_cli_artifacts(_resolve_output_dir(path), result)
    except OSError as error:
        raise CliFileSystemError(f"cannot write output directory {path}: {error}") from error


def _print_check(result: dict[str, Any]) -> None:
    print("ReasonScript check " + ("passed" if result["ok"] else "failed"))
    print(f"file: {result['source_file']}")
    if result["ok"]:
        print(f"diagnostics: {len(result['diagnostics'])}")
    else:
        _print_diagnostics(result["diagnostics"])


def _print_analyze(result: dict[str, Any]) -> None:
    print("ReasonScript analyze " + ("passed" if result["ok"] else "failed"))
    print(f"file: {result['source_file']}")
    stages = result.get("project_state", {}).get("pipeline", {}).get("stages", [])
    if stages:
        print("pipeline:")
        for stage in stages:
            print(f"  {stage['id']}: {stage['status']}")
    print("artifacts: available" if result.get("artifacts") else "artifacts: unavailable")
    print(f"diagnostics: {len(result['diagnostics'])}")
    if not result["ok"]:
        _print_diagnostics(result["diagnostics"])


def _print_run(result: dict[str, Any]) -> None:
    print("ReasonScript run " + ("passed" if result["ok"] else "failed"))
    print(f"file: {result['source_file']}")
    if result["ok"]:
        trace = result.get("trace")
        if trace is None:
            simulation = result.get("artifacts", {}).get("simulation", {})
            trace = simulation.get("trace", []) if isinstance(simulation, dict) else []
        knowledge = result.get("knowledge", {})
        print(f"goal_reached: {str(result.get('goal_reached')).lower()}")
        print(f"trace_steps: {len(trace)}")
        print(f"knowledge_items: {knowledge.get('knowledge_count', 0) if isinstance(knowledge, dict) else 0}")
    else:
        first = next((d for d in result["diagnostics"] if d.get("severity") == "error"), None)
        if first:
            print(f"stage: {first.get('stage')}")
        _print_diagnostics(result["diagnostics"])


def _print_diagnostics(diagnostics: list[dict[str, Any]]) -> None:
    rendered = render_diagnostics(diagnostics)
    if rendered:
        print(rendered)


def _examples_result() -> dict[str, Any]:
    valid_files = sorted(path for path in VALID_EXAMPLES_DIR.glob("*.rsn") if path.is_file())
    invalid_files = sorted(path for path in INVALID_EXAMPLES_DIR.glob("*.rsn") if path.is_file())
    valid = [_example_check(path, expect_ok=True) for path in valid_files]
    invalid = [_example_check(path, expect_ok=False) for path in invalid_files]
    failed = [item for item in valid + invalid if not item["passed"]]
    return {
        "schema_version": "reasonscript-cli-examples/0.1",
        "ok": not failed,
        "valid_total": len(valid),
        "valid_passed": sum(1 for item in valid if item["passed"]),
        "invalid_total": len(invalid),
        "invalid_passed": sum(1 for item in invalid if item["passed"]),
        "failed": len(failed),
        "results": valid + invalid,
    }


def _example_check(path: Path, *, expect_ok: bool) -> dict[str, Any]:
    result = _check_result(path, "normal")
    codes = [item.get("code") for item in result["diagnostics"]]
    return {
        "file": _display_path(path),
        "expected_ok": expect_ok,
        "actual_ok": result["ok"],
        "passed": result["ok"] is expect_ok,
        "diagnostic_codes": codes,
    }
