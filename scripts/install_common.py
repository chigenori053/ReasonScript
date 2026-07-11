#!/usr/bin/env python3
"""Atomic, user-scoped ReasonScript source installer."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def default_home() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ReasonScript"
    return Path.home() / ".reasonscript"


def digest(path: Path) -> dict[str, object]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size_bytes": path.stat().st_size}


def install(prefix: Path, json_output: bool) -> int:
    if sys.version_info < (3, 11):
        return report_error("IF-004", "Python 3.11 or newer is required.", json_output, 2)
    prefix = prefix.expanduser().resolve()
    release_path = ROOT / "metadata" / "release_manifest.json"
    if not release_path.is_file():
        return report_error("IF-007", "Release manifest not found.", json_output, 3)
    try:
        release = json.loads(release_path.read_text(encoding="utf-8"))
        if release["schema_version"] != "reasonscript-release-manifest/1.0" or release["reason_version"] != VERSION:
            raise ValueError("release version does not match VERSION")
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return report_error("IF-008", f"Invalid release manifest: {exc}", json_output, 3)
    versions = prefix / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    final = versions / VERSION
    temp = versions / f"{VERSION}.tmp-{uuid.uuid4().hex}"
    try:
        temp.mkdir()
        for name in ("toolchain", "scripts", "schemas", "frontend", "runtime", "examples", "standard_library", "metadata"):
            source = ROOT / name
            if source.exists():
                shutil.copytree(source, temp / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for name in ("reason", "VERSION", "pyproject.toml"):
            if (ROOT / name).is_file():
                shutil.copy2(ROOT / name, temp / name)
        validation_files = [temp / "reason", temp / "VERSION", *sorted((temp / "schemas").glob("*.json"))]
        if not (temp / "reason").is_file() or not (temp / "toolchain").is_dir():
            raise RuntimeError("staged distribution is incomplete")
        if final.exists():
            shutil.rmtree(final)
        temp.replace(final)
        current = prefix / "current"
        if current.exists() or current.is_symlink():
            current.unlink() if current.is_symlink() or current.is_file() else shutil.rmtree(current)
        try:
            current.symlink_to(final, target_is_directory=True)
        except OSError:
            shutil.copytree(final, current)
        bin_dir = prefix / "bin"
        bin_dir.mkdir(exist_ok=True)
        if os.name == "nt":
            wrapper = bin_dir / "reason.cmd"
            wrapper.write_text(f'@echo off\r\n"{sys.executable}" "{current / "reason"}" %*\r\n', encoding="utf-8")
        else:
            wrapper = bin_dir / "reason"
            wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{current / "reason"}" "$@"\n', encoding="utf-8")
            wrapper.chmod(0o755)
        for directory in ("artifacts/install", "cache", "config"):
            (prefix / directory).mkdir(parents=True, exist_ok=True)
        manifest = {"schema_version": "reasonscript-install-manifest/1.0", "install_id": f"rs-install-{uuid.uuid4().hex}",
                    "reason_version": VERSION, "runtime_version": VERSION, "install_foundation_version": "1.0",
                    "installed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "install_method": "source",
                    "install_root": str(prefix), "platform": {"os": platform.system().lower(), "architecture": platform.machine()},
                    "python": {"version": platform.python_version(), "executable": sys.executable},
                    "components": [{"id": x, "version": VERSION, "required": True, "status": "installed", "path": f"versions/{VERSION}/{p}"}
                                   for x, p in (("cli", "reason"), ("runtime-core", "toolchain"), ("schemas", "schemas"), ("examples", "examples"))],
                    "files": [digest(ROOT / p.relative_to(temp)) for p in validation_files], "validation": {"status": "pass"}}
        (prefix / "install_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = {"schema_version": "reasonscript-install-report/1.0", "status": "success", "reason_version": VERSION,
                  "install_method": "source", "install_root": str(prefix), "cli_path": str(wrapper),
                  "validation": {"status": "pass"}, "diagnostics": []}
        (prefix / "artifacts/install/install_report.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True) if json_output else f"ReasonScript {VERSION} installed.\nAdd {bin_dir} to PATH.")
        return 0 if str(bin_dir) in os.environ.get("PATH", "").split(os.pathsep) else 1
    except Exception as exc:
        shutil.rmtree(temp, ignore_errors=True)
        return report_error("IF-020", str(exc), json_output, 3)


def report_error(code: str, message: str, json_output: bool, exit_code: int) -> int:
    result = {"schema_version": "reasonscript-install-report/1.0", "status": "failure", "diagnostics": [{"code": code, "severity": "fatal", "message": message}]}
    print(json.dumps(result, indent=2, sort_keys=True) if json_output else f"{code}: {message}", file=sys.stderr)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", type=Path, default=Path(os.environ.get("REASONSCRIPT_HOME", default_home())))
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--modify-path", action="store_true", help="Reserved; profile files are never changed implicitly.")
    args = parser.parse_args()
    return install(args.prefix, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
