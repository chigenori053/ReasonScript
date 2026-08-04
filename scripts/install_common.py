#!/usr/bin/env python3
"""Atomic, user-scoped ReasonScript source installer."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import UTC, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from toolchain.distribution_validation import (
    COMPONENTS,
    DISTRIBUTION_TARGETS,
    DistributionError,
    inventory,
    validate_source_targets,
    validate_staged_distribution,
)
from toolchain.install_update.platform import current_adapter

VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def default_home() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ReasonScript"
    return Path.home() / ".reasonscript"


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
        validate_source_targets(ROOT)
        temp.mkdir()
        for name in DISTRIBUTION_TARGETS:
            source = ROOT / name
            shutil.copytree(source, temp / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", "node_modules", ".git", "target"))
        for name in ("reason", "VERSION", "pyproject.toml"):
            if (ROOT / name).is_file():
                shutil.copy2(ROOT / name, temp / name)
        runtime_launcher = temp / "bin/reason-runtime"
        runtime_launcher.parent.mkdir(parents=True)
        runtime_launcher.write_text(
            "#!/usr/bin/env python3\n"
            "import os, pathlib, sys\n"
            "target = pathlib.Path(__file__).resolve().parent.parent / 'reason'\n"
            "os.execv(sys.executable, [sys.executable, str(target), *sys.argv[1:]])\n",
            encoding="utf-8",
        )
        runtime_launcher.chmod(0o755)
        vision_name = "reason-vision.exe" if os.name == "nt" else "reason-vision"
        vision_binary = temp / "bin" / vision_name
        packaged_vision = ROOT / "bin" / vision_name
        if packaged_vision.is_file():
            shutil.copy2(packaged_vision, vision_binary)
        else:
            cargo = shutil.which("cargo")
            if not cargo:
                raise RuntimeError("cargo is required to build the native VisionRuntime from source")
            vision_build = subprocess.run(
                [cargo, "build", "--offline", "--release", "--manifest-path", str(ROOT / "VisionRuntime/Cargo.toml")],
                text=True,
                capture_output=True,
            )
            if vision_build.returncode:
                raise RuntimeError(f"VisionRuntime build failed: {vision_build.stderr.strip()}")
            shutil.copy2(ROOT / "VisionRuntime" / "target" / "release" / vision_name, vision_binary)
        vision_binary.chmod(0o755)
        visualization_name = "reason-visualization.exe" if os.name == "nt" else "reason-visualization"
        visualization_binary = temp / "bin" / visualization_name
        packaged_visualization = ROOT / "bin" / visualization_name
        if packaged_visualization.is_file():
            shutil.copy2(packaged_visualization, visualization_binary)
        else:
            cargo = shutil.which("cargo")
            if not cargo:
                raise RuntimeError("cargo is required to build the native VisualizationRuntime from source")
            visualization_build = subprocess.run(
                [cargo, "build", "--offline", "--release", "--manifest-path", str(ROOT / "VisualizationRuntime/Cargo.toml")],
                text=True,
                capture_output=True,
            )
            if visualization_build.returncode:
                raise RuntimeError(f"VisualizationRuntime build failed: {visualization_build.stderr.strip()}")
            shutil.copy2(ROOT / "VisualizationRuntime" / "target" / "release" / visualization_name, visualization_binary)
        visualization_binary.chmod(0o755)
        reasonunit_name = (
            "reasonunit-runtime-native.exe"
            if os.name == "nt"
            else "reasonunit-runtime-native"
        )
        reasonunit_binary = temp / "bin" / reasonunit_name
        packaged_reasonunit = ROOT / "bin" / reasonunit_name
        if packaged_reasonunit.is_file():
            shutil.copy2(packaged_reasonunit, reasonunit_binary)
        else:
            cargo = shutil.which("cargo")
            if not cargo:
                raise RuntimeError(
                    "cargo is required to build the native "
                    "NativeReasonUnitRuntime from source"
                )
            reasonunit_build = subprocess.run(
                [
                    cargo,
                    "build",
                    "--offline",
                    "--release",
                    "--manifest-path",
                    str(ROOT / "NativeReasonUnitRuntime/Cargo.toml"),
                ],
                text=True,
                capture_output=True,
            )
            if reasonunit_build.returncode:
                raise RuntimeError(
                    "NativeReasonUnitRuntime build failed: "
                    f"{reasonunit_build.stderr.strip()}"
                )
            shutil.copy2(
                ROOT
                / "NativeReasonUnitRuntime"
                / "target"
                / "release"
                / reasonunit_name,
                reasonunit_binary,
            )
        reasonunit_binary.chmod(0o755)
        validate_staged_distribution(temp, ROOT)
        file_inventory = inventory(temp)
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
        native_source = ROOT / "InstallFoundationUpdater/src/main.rs"
        native_updater = bin_dir / ("reason-updater.exe" if os.name == "nt" else "reason-updater")
        packaged_updater = ROOT / "bin" / native_updater.name
        rustc = shutil.which("rustc")
        if packaged_updater.is_file():
            shutil.copy2(packaged_updater, native_updater)
            native_updater.chmod(0o755)
        elif rustc and native_source.is_file():
            compiled = subprocess.run([rustc, "-O", str(native_source), "-o", str(native_updater)], text=True, capture_output=True)
            if compiled.returncode:
                raise RuntimeError(f"Native updater build failed: {compiled.stderr.strip()}")
        launcher_py = bin_dir / "reason-launcher.py"
        launcher_py.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            "root = pathlib.Path(__file__).resolve().parent.parent\n"
            "state = json.loads((root / 'metadata/current.json').read_text(encoding='utf-8'))\n"
            "target = root / 'versions' / state['active_version'] / 'bin/reason-runtime'\n"
            "os.environ['REASONSCRIPT_HOME'] = str(root)\n"
            "os.execv(sys.executable, [sys.executable, str(target), *sys.argv[1:]])\n",
            encoding="utf-8",
        )
        launcher_py.chmod(0o755)
        if os.name == "nt":
            wrapper = bin_dir / "reason.cmd"
            wrapper.write_text(f'@echo off\r\n"{sys.executable}" "{launcher_py}" %*\r\n', encoding="utf-8")
        else:
            wrapper = bin_dir / "reason"
            wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{launcher_py}" "$@"\n', encoding="utf-8")
            wrapper.chmod(0o755)
        for directory in ("artifacts/install", "cache", "config", "metadata", "staging", "backup"):
            (prefix / directory).mkdir(parents=True, exist_ok=True)
        manifest = {"schema_version": "reasonscript-install-manifest/1.0", "install_id": f"rs-install-{uuid.uuid4().hex}",
                    "reason_version": VERSION, "runtime_version": VERSION, "install_foundation_version": "1.0",
                    "installed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "install_method": "source",
                    "install_root": str(prefix), "platform": {"os": platform.system().lower(), "architecture": platform.machine()},
                    "python": {"version": platform.python_version(), "executable": sys.executable},
                    "components": [{"id": x, "version": VERSION, "required": True, "status": "installed", "path": f"versions/{VERSION}/{p}"}
                                   for x, p in COMPONENTS],
                    "files": [{**item, "path": f"versions/{VERSION}/{item['path']}"} for item in file_inventory],
                    "validation": {"status": "pass"},
                    "distribution_validation": {"status": "partial", "import_closure": "pass", "repository_independence": "pass", "installed_cli_smoke": "pending"}}
        (prefix / "install_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        adapter = current_adapter()
        now = manifest["installed_at"]
        adapter.atomic_json_write(prefix / "metadata/current.json", {
            "schema_version": "reasonscript-current-installation/1.0", "active_version": VERSION,
            "previous_version": None, "activation_status": "active",
        })
        adapter.atomic_json_write(prefix / "metadata/install_state.json", {
            "schema_version": "reasonscript-install-state/1.1", "installed_version": VERSION,
            "runtime_version": VERSION, "install_foundation_version": "1.1",
            "platform": adapter.name, "architecture": adapter.architecture, "install_root": str(prefix),
            "installed_at": now, "updated_at": now, "update_count": 0, "status": "healthy",
        })
        adapter.atomic_json_write(prefix / "metadata/installed_files.json", {
            "schema_version": "reasonscript-installed-files/1.1", "version": VERSION,
            "files": [{"path": f"versions/{VERSION}/{item['path']}", "sha256": item["sha256"],
                       "managed": True, "component": item["path"].split("/", 1)[0]}
                      for item in file_inventory],
        })
        adapter.atomic_json_write(prefix / "metadata/update_history.json", {
            "schema_version": "reasonscript-update-history/1.0", "updates": [],
        })
        shutil.copy2(prefix / "install_manifest.json", prefix / "metadata/install_manifest.json")
        result = {"schema_version": "reasonscript-install-report/1.0", "status": "success", "reason_version": VERSION,
                  "install_method": "source", "install_root": str(prefix), "cli_path": str(wrapper),
                  "validation": {"status": "pass"}, "diagnostics": []}
        (prefix / "artifacts/install/install_report.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2, sort_keys=True) if json_output else f"ReasonScript {VERSION} installed.\nAdd {bin_dir} to PATH.")
        return 0 if str(bin_dir) in os.environ.get("PATH", "").split(os.pathsep) else 1
    except DistributionError as exc:
        shutil.rmtree(temp, ignore_errors=True)
        result = {"schema_version": "reasonscript-install-report/1.0", "status": "failure", "diagnostics": [exc.diagnostic()]}
        print(json.dumps(result, indent=2, sort_keys=True) if json_output else f"{exc.code}: {exc}", file=sys.stderr)
        return 3
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
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--package", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.update:
        if args.package is None:
            return report_error("INS-UPD-017", "--package is required with --update.", args.json, 2)
        from toolchain.install_update.core import UpdateEngine
        payload, exit_code = UpdateEngine(args.prefix).update(args.package, args.force)
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else f"ReasonScript update: {payload['status']}")
        return exit_code
    return install(args.prefix, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
