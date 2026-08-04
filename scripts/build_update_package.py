#!/usr/bin/env python3
"""Build a deterministic local Install Foundation v1.1 update package.

Embeds provenance and freshness metadata per the Update Package Provenance
and Freshness Verification Specification v0.1: the package carries a
canonical ``metadata/update_package_manifest.json`` recording the source
commit, dirty state, builder identity, validation profile, and payload
hashes, and the finished archive is self-validated in a staging area before
being atomically promoted into ``dist``.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from toolchain.distribution_validation import COMPONENTS, DISTRIBUTION_TARGETS, validate_source_targets
from toolchain.install_update.package_provenance import (
    ProvenanceBuildError,
    build_manifest,
    builder_metadata,
    canonical_json,
    git_provenance,
    payload_file_records,
    sha256_bytes,
    sha256_file,
    validation_profile_metadata,
    write_manifest,
)
from toolchain.install_update.package_validator import validate_package_provenance
from toolchain.install_update.platform import architecture_id, platform_id


class BuildRejected(Exception):
    """Raised when a provenance gate rejects the build (BLD-PROV-001..012)."""


def _stable_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _timestamp(source_date_epoch: int | None) -> str:
    moment = (datetime.fromtimestamp(source_date_epoch, tz=timezone.utc)
              if source_date_epoch is not None else datetime.now(timezone.utc))
    return moment.isoformat().replace("+00:00", "Z")


def _collect_provenance(package_class: str, allow_dirty: bool, expected_commit: str | None) -> dict:
    try:
        git_info = git_provenance(ROOT)
    except ProvenanceBuildError as exc:
        raise BuildRejected(f"BLD-PROV-001: {exc}") from exc
    if expected_commit and git_info["source_commit"]["sha"] != expected_commit:
        raise BuildRejected(
            "BLD-PROV-004: HEAD does not match --expected-commit "
            f"({git_info['source_commit']['sha']} != {expected_commit})."
        )
    if git_info["source_tree"]["dirty"]:
        if package_class == "release":
            raise BuildRejected("BLD-PROV-003: Release packages must be built from a clean source tree (INS-PROV-006).")
        if not allow_dirty:
            raise BuildRejected("BLD-PROV-003: Source tree is dirty; pass --allow-dirty for development builds.")
    return git_info


def _write_payload(package: Path, target_platform: str) -> Path:
    payload = package / "payload"
    payload.mkdir(parents=True)
    ignored = shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".venv", "node_modules", ".git", "target",
        ".DS_Store", ".pytest_cache", ".mypy_cache", ".ruff_cache",
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
    cargo = shutil.which("cargo")
    if not cargo:
        raise BuildRejected("cargo is required to build the native VisionRuntime")
    vision_build = subprocess.run(
        [cargo, "build", "--offline", "--release", "--manifest-path", str(ROOT / "VisionRuntime/Cargo.toml")],
        text=True,
        capture_output=True,
    )
    if vision_build.returncode:
        raise BuildRejected(f"VisionRuntime build failed: {vision_build.stderr.strip()}")
    vision_name = "reason-vision.exe" if target_platform == "windows" else "reason-vision"
    shutil.copy2(ROOT / "VisionRuntime" / "target" / "release" / vision_name, payload / "bin" / vision_name)
    (payload / "bin" / vision_name).chmod(0o755)
    visualization_build = subprocess.run(
        [cargo, "build", "--offline", "--release", "--manifest-path", str(ROOT / "VisualizationRuntime/Cargo.toml")],
        text=True, capture_output=True,
    )
    if visualization_build.returncode:
        raise BuildRejected(f"VisualizationRuntime build failed: {visualization_build.stderr.strip()}")
    visualization_name = "reason-visualization.exe" if target_platform == "windows" else "reason-visualization"
    shutil.copy2(ROOT / "VisualizationRuntime" / "target" / "release" / visualization_name, payload / "bin" / visualization_name)
    (payload / "bin" / visualization_name).chmod(0o755)
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
        raise BuildRejected(
            "NativeReasonUnitRuntime build failed: "
            f"{reasonunit_build.stderr.strip()}"
        )
    reasonunit_name = (
        "reasonunit-runtime-native.exe"
        if target_platform == "windows"
        else "reasonunit-runtime-native"
    )
    shutil.copy2(
        ROOT / "NativeReasonUnitRuntime" / "target" / "release" / reasonunit_name,
        payload / "bin" / reasonunit_name,
    )
    (payload / "bin" / reasonunit_name).chmod(0o755)
    updater_name = "reason-updater.exe" if target_platform == "windows" else "reason-updater"
    native_updater = payload / "bin" / updater_name
    rustc = shutil.which("rustc")
    if not rustc:
        raise BuildRejected("rustc is required to build the native update helper")
    compiled = subprocess.run([rustc, "-O", str(ROOT / "InstallFoundationUpdater/src/main.rs"), "-o", str(native_updater)],
                              text=True, capture_output=True)
    if compiled.returncode:
        raise BuildRejected(f"Native updater build failed: {compiled.stderr.strip()}")
    return payload


def _archive(package: Path, destination: Path, archive_format: str, package_name: str,
             source_date_epoch: int | None) -> Path:
    entries = sorted(path for path in package.rglob("*"))
    if archive_format == "zip":
        target = destination / f"{package_name}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in entries:
                if path.is_file():
                    archive.write(path, f"{package_name}/{path.relative_to(package).as_posix()}")
        return target
    target = destination / f"{package_name}.tar.gz"

    def _normalize(info: tarfile.TarInfo) -> tarfile.TarInfo:
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        if source_date_epoch is not None:
            info.mtime = source_date_epoch
        return info

    with open(target, "wb") as raw:
        gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw,
                           mtime=source_date_epoch if source_date_epoch is not None else None)
        with gz, tarfile.open(fileobj=gz, mode="w") as archive:
            for path in entries:
                archive.add(path, arcname=f"{package_name}/{path.relative_to(package).as_posix()}",
                            recursive=False, filter=_normalize)
    return target


def build(output: Path, target_platform: str, target_architecture: str,
          minimum_previous_version: str | None, archive_format: str, *,
          package_class: str = "release", allow_dirty: bool = False,
          expected_commit: str | None = None, source_date_epoch: int | None = None,
          expected_version: str | None = None) -> dict:
    validate_source_targets(ROOT)
    if target_platform != platform_id() or target_architecture != architecture_id():
        raise BuildRejected("Native update packages must be built on the target platform and architecture.")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if expected_version is not None and expected_version != version:
        raise BuildRejected(f"BLD-PROV-004: --version {expected_version} does not match source VERSION {version}.")
    git_info = _collect_provenance(package_class, allow_dirty, expected_commit)
    package_name = f"reasonscript-{version}-{target_platform}-{target_architecture}"
    staging_root = output / ".staging" / package_name
    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True)
    try:
        with tempfile.TemporaryDirectory(prefix="reason-update-build-") as directory:
            package = Path(directory) / package_name
            _write_payload(package, target_platform)

            files = payload_file_records(package)
            components = [{"name": name, "version": version} for name, _ in COMPONENTS]
            _stable_json(package / "manifest.json", {
                "schema_version": "reasonscript-install-manifest/1.1", "package_version": version,
                "runtime_version": version, "install_foundation_version": "1.1",
                "platform": target_platform, "architecture": target_architecture,
                "minimum_previous_version": minimum_previous_version, "maximum_previous_version": None,
                "package_type": "update_and_install", "components": components, "files": [],
            })
            _stable_json(package / "checksums.json", {
                "schema_version": "reasonscript-package-checksums/1.0", "algorithm": "sha256",
                "files": [{"path": item["path"], "sha256": item["sha256"]} for item in files],
            })
            try:
                profile = validation_profile_metadata(package, version)
                builder = builder_metadata(Path(__file__).resolve())
            except ProvenanceBuildError as exc:
                raise BuildRejected(f"BLD-PROV-005: {exc}") from exc
            manifest = build_manifest(
                expected_version=version, package_class=package_class,
                target_platform=target_platform, target_architecture=target_architecture,
                archive_format=archive_format, git_info=git_info, builder=builder,
                validation_profile=profile, file_records=files,
                timestamp_utc=_timestamp(source_date_epoch),
                expected_commit=expected_commit or git_info["source_commit"]["sha"],
                source_date_epoch=source_date_epoch,
            )
            write_manifest(package, manifest)

            # BLD-PROV-012: self-validate with the install-side validator before promotion.
            report = validate_package_provenance(
                package, platform=target_platform, architecture=target_architecture,
                expected_version=version, expected_commit=manifest["release"]["expected_commit"],
                allow_development=package_class == "development",
            )
            if not report.valid:
                details = "; ".join(f"{item.code}: {item.message}" for item in report.issues)
                raise BuildRejected(f"BLD-PROV-012 (INS-PROV-018): package self-validation failed: {details}")

            if archive_format == "directory":
                staged = staging_root / package_name
                shutil.copytree(package, staged)
                artifact = staged
                archive_hash = None
            else:
                artifact = _archive(package, staging_root, archive_format, package_name, source_date_epoch)
                archive_hash = sha256_file(artifact)
                (artifact.parent / f"{artifact.name}.sha256").write_text(
                    f"{archive_hash}  {artifact.name}\n", encoding="utf-8")
            # External sidecar manifest copies for dist-level inspection.
            external_manifest = staging_root / f"{package_name}.manifest.json"
            external_manifest.write_text(canonical_json(manifest), encoding="utf-8")
            (staging_root / f"{package_name}.manifest.sha256").write_text(
                sha256_bytes(canonical_json(manifest).encode("utf-8")) + "\n", encoding="utf-8")

            # Atomic promotion into dist.
            output.mkdir(parents=True, exist_ok=True)
            promoted = []
            for item in sorted(staging_root.iterdir()):
                destination = output / item.name
                if destination.exists():
                    shutil.rmtree(destination) if destination.is_dir() else destination.unlink()
                item.replace(destination) if not item.is_dir() else shutil.move(str(item), str(destination))
                promoted.append(str(destination))
            return {
                "path": str(output / artifact.name),
                "promoted": promoted,
                "package_id": manifest["package_id"],
                "package_class": package_class,
                "source_commit_sha": manifest["source_commit"]["sha"],
                "dirty": manifest["source_tree"]["dirty"],
                "builder_version": manifest["builder"]["version"],
                "validation_profile_version": manifest["validation_profile"]["profile_version"],
                "manifest_sha256": sha256_bytes(canonical_json(manifest).encode("utf-8")),
                "payload_sha256": manifest["integrity"]["payload_sha256"],
                "archive_sha256": archive_hash,
                "self_validation": "passed",
            }
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
        parent = output / ".staging"
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    parser.add_argument("--version", dest="expected_version")
    parser.add_argument("--platform", choices=["macos", "linux", "windows"], default=platform_id())
    parser.add_argument("--architecture", default=architecture_id())
    parser.add_argument("--minimum-previous-version", default="0.5.0")
    parser.add_argument("--format", choices=["tar.gz", "zip", "directory"])
    parser.add_argument("--package-class", choices=["release", "development"], default="release")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--expected-commit")
    parser.add_argument("--source-date-epoch", type=int,
                        default=int(os.environ["SOURCE_DATE_EPOCH"]) if os.environ.get("SOURCE_DATE_EPOCH") else None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.allow_dirty and args.package_class == "release":
        print("error: --allow-dirty is not permitted for release packages", file=sys.stderr)
        return 2
    archive_format = args.format or ("zip" if args.platform == "windows" else "tar.gz")
    try:
        result = build(args.out.resolve(), args.platform, args.architecture,
                       args.minimum_previous_version, archive_format,
                       package_class=args.package_class, allow_dirty=args.allow_dirty,
                       expected_commit=args.expected_commit, source_date_epoch=args.source_date_epoch,
                       expected_version=args.expected_version)
    except BuildRejected as exc:
        payload = {"schema_version": "reasonscript-update-package-build/1.1", "status": "rejected", "reason": str(exc)}
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else f"error: {exc}",
              file=sys.stdout if args.json else sys.stderr)
        return 1
    payload = {"schema_version": "reasonscript-update-package-build/1.1", "status": "success", **result}
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else result["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
