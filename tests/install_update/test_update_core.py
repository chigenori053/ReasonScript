from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from toolchain.install_update.core import UpdateEngine, UpdateError, compare_versions
from toolchain.install_update.platform import PlatformAdapter


PASS_VALIDATION = {
    "version": "passed", "doctor": "passed", "install_info": "passed", "install_validate": "passed",
    "scalar_smoke": "passed", "tensor_smoke": "passed", "loop_smoke": "passed",
}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def installed(tmp_path: Path) -> tuple[Path, PlatformAdapter]:
    root = tmp_path / "install"
    adapter = PlatformAdapter("macos", "arm64")
    version = root / "versions/0.5.0"
    for relative in ("reason", "VERSION", "bin/reason-runtime", "runtime/__init__.py", "toolchain/__init__.py",
                     "schemas/base.json", "standard_library/base.rsn", "metadata/release_manifest.json"):
        _write(version / relative, "0.5.0\n" if relative == "VERSION" else relative)
    _write(root / "bin/reason", "launcher")
    _write(root / "config/user.json", '{"keep": true}')
    _write(root / "artifacts/user.json", '{"keep": true}')
    now = "2026-07-14T00:00:00Z"
    adapter.prepare_install_root(root)
    adapter.activate_version(root, "0.5.0", None)
    files = [{"path": f"versions/0.5.0/{path.relative_to(version).as_posix()}", "sha256": _sha(path),
              "managed": True, "component": path.relative_to(version).parts[0]}
             for path in sorted(version.rglob("*")) if path.is_file()]
    adapter.atomic_json_write(root / "metadata/install_state.json", {
        "schema_version": "reasonscript-install-state/1.1", "installed_version": "0.5.0",
        "runtime_version": "0.5.0", "install_foundation_version": "1.1", "platform": "macos",
        "architecture": "arm64", "install_root": str(root), "installed_at": now, "updated_at": now,
        "update_count": 0, "status": "healthy",
    })
    adapter.atomic_json_write(root / "metadata/installed_files.json", {
        "schema_version": "reasonscript-installed-files/1.1", "version": "0.5.0", "files": files,
    })
    adapter.atomic_json_write(root / "metadata/update_history.json", {
        "schema_version": "reasonscript-update-history/1.0", "updates": [],
    })
    manifest = {"schema_version": "reasonscript-install-manifest/1.0", "install_id": "rs-install-test",
                "reason_version": "0.5.0", "runtime_version": "0.5.0", "install_foundation_version": "1.0",
                "installed_at": now, "install_method": "source", "install_root": str(root),
                "platform": {"os": "macos", "architecture": "arm64"}, "python": {}, "components": [],
                "files": files, "validation": {"status": "pass"}}
    adapter.atomic_json_write(root / "install_manifest.json", manifest)
    adapter.atomic_json_write(root / "metadata/install_manifest.json", manifest)
    return root, adapter


def package(tmp_path: Path, *, version: str = "0.5.1", platform: str = "macos",
            architecture: str = "arm64") -> Path:
    root = tmp_path / f"package-{version}-{platform}-{architecture}"
    payload = root / "payload"
    for relative in ("reason", "VERSION", "bin/reason-runtime", "runtime/__init__.py", "toolchain/__init__.py",
                     "schemas/base.json", "standard_library/base.rsn", "metadata/release_manifest.json"):
        _write(payload / relative, f"{version}\n" if relative == "VERSION" else f"new:{relative}")
    files = [{"path": f"payload/{path.relative_to(payload).as_posix()}", "sha256": _sha(path)}
             for path in sorted(payload.rglob("*")) if path.is_file()]
    (root / "manifest.json").write_text(json.dumps({
        "schema_version": "reasonscript-install-manifest/1.1", "package_version": version,
        "runtime_version": version, "install_foundation_version": "1.1", "platform": platform,
        "architecture": architecture, "minimum_previous_version": "0.5.0", "maximum_previous_version": None,
        "package_type": "update_and_install", "components": [
            {"name": name, "version": version} for name in
            ("cli", "runtime-core", "toolchain", "schemas", "standard-library")],
    }), encoding="utf-8")
    (root / "checksums.json").write_text(json.dumps({
        "schema_version": "reasonscript-package-checksums/1.0", "algorithm": "sha256", "files": files,
    }), encoding="utf-8")
    return root


def engine(root: Path, adapter: PlatformAdapter) -> UpdateEngine:
    return UpdateEngine(root, adapter, validator=lambda _: dict(PASS_VALIDATION))


def test_version_comparison_is_deterministic() -> None:
    assert compare_versions("0.5.1", "0.5.0") == 1
    assert compare_versions("0.5.0", "0.5.0") == 0
    assert compare_versions("0.5.1-dev", "0.5.1") == -1


def test_update_plan_and_atomic_update_preserve_user_data(tmp_path: Path) -> None:
    root, adapter = installed(tmp_path)
    candidate = package(tmp_path)
    updater = engine(root, adapter)
    plan = updater.check(candidate)
    assert plan["status"] == "update_available"
    assert plan["plan"]["rollback_target"] == "0.5.0"
    report, code = updater.update(candidate)
    assert code == 0
    assert report["status"] == "completed"
    assert json.loads((root / "metadata/current.json").read_text())["active_version"] == "0.5.1"
    assert (root / "versions/0.5.0").is_dir()
    assert (root / "versions/0.5.1").is_dir()
    assert json.loads((root / "config/user.json").read_text()) == {"keep": True}
    assert json.loads((root / "artifacts/user.json").read_text()) == {"keep": True}


def test_same_version_noop_and_downgrade_rejected(tmp_path: Path) -> None:
    root, adapter = installed(tmp_path)
    updater = engine(root, adapter)
    assert updater.check(package(tmp_path, version="0.5.0"))["status"] == "already_up_to_date"
    report = updater.check(package(tmp_path, version="0.4.9"))
    assert report["status"] == "downgrade_rejected"
    assert report["diagnostics"][0]["code"] == "INS-UPD-002"


@pytest.mark.parametrize(("field", "value", "code"), [
    ("platform", "linux", "INS-UPD-003"), ("architecture", "x86_64", "INS-UPD-004")])
def test_package_compatibility(field: str, value: str, code: str, tmp_path: Path) -> None:
    root, adapter = installed(tmp_path)
    kwargs = {field: value}
    with pytest.raises(UpdateError) as caught:
        engine(root, adapter).check(package(tmp_path, **kwargs))
    assert caught.value.code == code


def test_checksum_and_managed_file_modification_are_rejected(tmp_path: Path) -> None:
    root, adapter = installed(tmp_path)
    candidate = package(tmp_path)
    (candidate / "payload/reason").write_text("tampered", encoding="utf-8")
    with pytest.raises(UpdateError) as checksum:
        engine(root, adapter).check(candidate)
    assert checksum.value.code == "INS-UPD-005"
    candidate = package(tmp_path / "fresh")
    (root / "versions/0.5.0/reason").write_text("modified", encoding="utf-8")
    with pytest.raises(UpdateError) as managed:
        engine(root, adapter).check(candidate)
    assert managed.value.code == "INS-UPD-013"
    assert engine(root, adapter).check(candidate, force=True)["status"] == "update_available"


def test_post_install_failure_rolls_back(tmp_path: Path) -> None:
    root, adapter = installed(tmp_path)
    calls = 0
    def validator(_: Path) -> dict[str, str]:
        nonlocal calls
        calls += 1
        return ({**PASS_VALIDATION, "tensor_smoke": "failed"} if calls == 1 else dict(PASS_VALIDATION))
    report, code = UpdateEngine(root, adapter, validator=validator).update(package(tmp_path))
    assert code == 9
    assert report["status"] == "rolled_back"
    assert json.loads((root / "metadata/current.json").read_text())["active_version"] == "0.5.0"


def test_explicit_rollback_restores_metadata_inventory(tmp_path: Path) -> None:
    root, adapter = installed(tmp_path)
    updater = engine(root, adapter)
    assert updater.update(package(tmp_path))[1] == 0
    report, code = updater.rollback()
    assert code == 0 and report["status"] == "rolled_back"
    assert json.loads((root / "metadata/installed_files.json").read_text())["version"] == "0.5.0"
    assert updater.discover()["state"]["installed_version"] == "0.5.0"


def test_v1_metadata_migration_is_one_time_and_preserves_installation(tmp_path: Path) -> None:
    root, adapter = installed(tmp_path)
    for path in (root / "metadata").glob("*.json"):
        path.unlink()
    state = engine(root, adapter).discover()
    assert state["state"]["install_foundation_version"] == "1.1"
    assert state["state"]["update_count"] == 0
    assert (root / "config/user.json").is_file()


def test_missing_installation_and_archive_traversal_are_normalized(tmp_path: Path) -> None:
    adapter = PlatformAdapter("macos", "arm64")
    with pytest.raises(UpdateError) as missing:
        engine(tmp_path / "missing", adapter).discover()
    assert missing.value.code == "INS-UPD-001"
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("../escape", "bad")
    with pytest.raises(UpdateError) as unsafe:
        engine(tmp_path / "missing", adapter).open_package(archive)
    assert unsafe.value.code == "INS-UPD-017"


def test_update_plan_is_deterministic(tmp_path: Path) -> None:
    root, adapter = installed(tmp_path)
    candidate = package(tmp_path)
    updater = engine(root, adapter)
    assert updater.check(candidate) == updater.check(candidate)
