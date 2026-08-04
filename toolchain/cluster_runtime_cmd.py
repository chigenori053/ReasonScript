"""Thin `reason cluster` adapter for the Rust Cluster Runtime binary.

The existing Python toolchain only compiles `.rsn` into the established
artifact bundle. Planning, execution, validation, comparison, workers, and
artifact generation are implemented by `ClusterRuntime` in Rust.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def run(command: str, args: list[str], project_root: Path) -> int:
    if command != "cluster" or not args:
        _usage()
        return 1
    subcommand = args[0]
    if subcommand == "dynamic":
        return _run_dynamic(args[1:], project_root)
    if subcommand == "validate":
        target = _positional(args[1:])
        if target is None:
            _usage()
            return 1
        return _invoke(project_root, ["validate", str(_path(project_root, target))])
    if subcommand == "test-model":
        rust_args = ["test-model"]
        for option in ("--scenario", "--workers", "--mode"):
            value = _option(args, option)
            if value is not None:
                rust_args.extend([option, value])
        return _invoke(project_root, rust_args)
    source = _positional(args[1:])
    if subcommand not in {"plan", "run", "simulate", "compare"} or source is None:
        _usage()
        return 1
    source_path = _path(project_root, source)
    from scripts.reason_cli import _analyze_result
    bundle = _analyze_result(source_path, "normal")
    config_path = _option(args, "--config")
    config: dict[str, Any] | None = None
    if config_path is not None:
        try:
            config = json.loads(_path(project_root, config_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"CRR-CFG-001: {error}")
            return 1
    envelope = {"bundle": bundle, "config": config, "workers": _int_option(args, "--workers", 2)}
    rust_args = [subcommand]
    artifacts = _option(args, "--artifacts-dir")
    if artifacts is not None:
        rust_args.extend(["--artifacts-dir", str(_path(project_root, artifacts))])
    return _invoke(project_root, rust_args, envelope)


def _invoke(project_root: Path, args: list[str], stdin: dict[str, Any] | None = None) -> int:
    crate = project_root / "ClusterRuntime"
    binary = crate / "target" / "debug" / "reason-cluster"
    if binary.is_file():
        command = [str(binary), *args]
    else:
        command = ["cargo", "run", "--offline", "--quiet", "--manifest-path", str(crate / "Cargo.toml"), "--bin", "reason-cluster", "--", *args]
    result = subprocess.run(
        command,
        cwd=project_root,
        input=json.dumps(stdin, ensure_ascii=False, sort_keys=True) if stdin is not None else None,
        text=True,
        check=False,
    )
    return result.returncode


def _run_dynamic(args: list[str], project_root: Path) -> int:
    if not args:
        _usage()
        return 1
    subcommand = args[0]
    if subcommand == "validate":
        target = _positional(args[1:])
        return _invoke(project_root, ["dynamic", "validate", str(_path(project_root, target))]) if target else 1
    if subcommand == "test-model":
        rust_args = ["dynamic", "test-model"]
        for option in ("--scenario", "--workers"):
            value = _option(args, option)
            if value is not None:
                rust_args.extend([option, value])
        return _invoke(project_root, rust_args)
    source = _positional(args[1:])
    if subcommand not in {"plan", "run", "simulate", "compare"} or source is None:
        _usage()
        return 1
    from scripts.reason_cli import _analyze_result
    bundle = _analyze_result(_path(project_root, source), "normal")
    def load(option: str) -> dict[str, Any] | None:
        value = _option(args, option)
        return json.loads(_path(project_root, value).read_text(encoding="utf-8")) if value else None
    try:
        envelope = {"bundle": bundle, "cluster_config": load("--cluster-config"), "dynamic_config": load("--dynamic-config"), "workers": _int_option(args, "--workers", 2)}
    except (OSError, json.JSONDecodeError) as error:
        print(f"DRU-PRP-001: {error}")
        return 1
    rust_args = ["dynamic", subcommand]
    artifacts = _option(args, "--artifacts-dir")
    if artifacts:
        rust_args.extend(["--artifacts-dir", str(_path(project_root, artifacts))])
    return _invoke(project_root, rust_args, envelope)


def _option(args: list[str], name: str) -> str | None:
    if name not in args:
        return None
    index = args.index(name)
    return args[index + 1] if index + 1 < len(args) else None


def _int_option(args: list[str], name: str, default: int) -> int:
    value = _option(args, name)
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _positional(args: list[str]) -> str | None:
    skip = False
    valued = {"--config", "--cluster-config", "--dynamic-config", "--artifacts-dir", "--workers", "--scenario", "--mode"}
    for arg in args:
        if skip:
            skip = False
            continue
        if arg in valued:
            skip = True
            continue
        if arg.startswith("--"):
            continue
        return arg
    return None


def _path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _usage() -> None:
    print("Usage: reason cluster plan <source.rsn> --config <cluster.json> [--json]")
    print("       reason cluster run <source.rsn> --config <cluster.json> --artifacts-dir <dir> [--json]")
    print("       reason cluster simulate <source.rsn> --workers <count> [--json]")
    print("       reason cluster validate <artifact-dir> [--json]")
    print("       reason cluster compare <source.rsn> --config <cluster.json> [--json]")
    print("       reason cluster test-model --scenario <name> --workers <count> [--json]")
    print("       reason cluster dynamic <plan|run|simulate|compare> <source.rsn> --dynamic-config <dynamic.json> [--json]")
    print("       reason cluster dynamic validate <artifact-dir> [--json]")
    print("       reason cluster dynamic test-model --scenario <name> --workers <count> [--json]")
