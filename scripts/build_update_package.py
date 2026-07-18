#!/usr/bin/env python3
"""Build a deterministic local Install Foundation v1.1 update package."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from toolchain.distribution_validation import COMPONENTS, DISTRIBUTION_TARGETS, validate_source_targets
from toolchain.install_update.platform import architecture_id, platform_id


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build(output: Path, target_platform: str, target_architecture: str,
          minimum_previous_version: str | None, archive_format: str) -> Path:
    validate_source_targets(ROOT)
    if target_platform != platform_id() or target_architecture != architecture_id():
        raise ValueError("Native update packages must be built on the target platform and architecture.")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    package_name = f"reasonscript-{version}-{target_platform}-{target_architecture}"
    with tempfile.TemporaryDirectory(prefix="reason-update-build-") as directory:
        package = Path(directory) / package_name
        payload = package / "payload"
        payload.mkdir(parents=True)
        ignored = shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            ".venv",
            "node_modules",
            ".git",
            "target",
            ".DS_Store",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
        )
        for name in DISTRIBUTION_TARGETS:
            shutil.copytree(ROOT / name, payload / name, ignore=ignored)
        for name in ("reason", "VERSION", "pyproject.toml"):
            shutil.copy2(ROOT / name, payload / name)
        runtime_launcher = payload / "bin/reason-runtime"
        runtime_launcher.parent.mkdir()
        runtime_launcher.write_text(
            "#!/usr/bin/env python3\nimport os, pathlib, sys\n"
            "target = pathlib.Path(__file__).resolve().parent.parent / 'reason'\n"
            "os.execv(sys.executable, [sys.executable, str(target), *sys.argv[1:]])\n",
            encoding="utf-8",
        )
        runtime_launcher.chmod(0o755)
        updater_name = "reason-updater.exe" if target_platform == "windows" else "reason-updater"
        native_updater = payload / "bin" / updater_name
        rustc = shutil.which("rustc")
        if not rustc:
            raise RuntimeError("rustc is required to build the native update helper")
        compiled = subprocess.run([rustc, "-O", str(ROOT / "InstallFoundationUpdater/src/main.rs"), "-o", str(native_updater)],
                                  text=True, capture_output=True)
        if compiled.returncode:
            raise RuntimeError(f"Native updater build failed: {compiled.stderr.strip()}")
        files = [{"path": f"payload/{path.relative_to(payload).as_posix()}", "sha256": _hash(path)}
                 for path in sorted(payload.rglob("*")) if path.is_file()]
        components = [{"name": name, "version": version} for name, _ in COMPONENTS]
        _stable_json(package / "manifest.json", {
            "schema_version": "reasonscript-install-manifest/1.1", "package_version": version,
            "runtime_version": version, "install_foundation_version": "1.1",
            "platform": target_platform, "architecture": target_architecture,
            "minimum_previous_version": minimum_previous_version, "maximum_previous_version": None,
            "package_type": "update_and_install", "components": components, "files": [],
        })
        _stable_json(package / "checksums.json", {
            "schema_version": "reasonscript-package-checksums/1.0", "algorithm": "sha256", "files": files,
        })
        output.mkdir(parents=True, exist_ok=True)
        if archive_format == "directory":
            destination = output / package_name
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(package, destination)
            return destination
        if archive_format == "zip":
            destination = output / f"{package_name}.zip"
            with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(package.rglob("*")):
                    if path.is_file():
                        archive.write(path, f"{package_name}/{path.relative_to(package).as_posix()}")
            return destination
        destination = output / f"{package_name}.tar.gz"
        with tarfile.open(destination, "w:gz") as archive:
            archive.add(package, arcname=package_name, recursive=True)
        return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--platform", choices=["macos", "linux", "windows"], default=platform_id())
    parser.add_argument("--architecture", default=architecture_id())
    parser.add_argument("--minimum-previous-version", default="0.5.0")
    parser.add_argument("--format", choices=["tar.gz", "zip", "directory"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    archive_format = args.format or ("zip" if args.platform == "windows" else "tar.gz")
    path = build(args.out.resolve(), args.platform, args.architecture, args.minimum_previous_version, archive_format)
    payload = {"schema_version": "reasonscript-update-package-build/1.0", "status": "success", "path": str(path)}
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
