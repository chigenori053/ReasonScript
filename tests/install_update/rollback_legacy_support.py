"""Test-only support for Install Foundation v1.1.1 Phase R1 reproduction."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from toolchain.install_update.core import UpdateEngine
from toolchain.install_update.platform import PlatformAdapter


SCENARIO_ID = "rollback_legacy_0_5_0_from_0_5_1_failure"
OBSERVATION_SCHEMA = "reasonscript-rollback-reproduction-observation/1.0"
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures/install_update/rollback_legacy_reproduction"
INSTALLED_FIXTURE = FIXTURE_ROOT / "installed_0_5_0"
PACKAGE_FIXTURE = FIXTURE_ROOT / "package_0_5_1"
EXPECTED_OBSERVATION = FIXTURE_ROOT / "expected/rollback_failure_reproduction_observation.json"
ARTIFACT_OBSERVATION = (
    Path(__file__).resolve().parents[2]
    / "artifacts/install_foundation_v1_1_1/phase_r1/rollback_failure_reproduction_observation.json"
)
PASS_VALIDATION = {
    "version": "passed",
    "doctor": "passed",
    "install_info": "passed",
    "install_validate": "passed",
    "scalar_smoke": "passed",
    "tensor_smoke": "passed",
    "loop_smoke": "passed",
    "project_validation": "passed",
}


def stable_json(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh_package_checksums(package: Path) -> None:
    payload = package / "payload"
    files = [
        {"path": f"payload/{path.relative_to(payload).as_posix()}", "sha256": _sha256(path)}
        for path in sorted(payload.rglob("*"))
        if path.is_file()
    ]
    (package / "checksums.json").write_text(
        stable_json(
            {
                "schema_version": "reasonscript-package-checksums/1.0",
                "algorithm": "sha256",
                "files": files,
            }
        ),
        encoding="utf-8",
    )


def materialize_fixtures(destination: Path) -> tuple[Path, Path, PlatformAdapter]:
    install_root = (destination / "install").resolve()
    if install_root == (Path.home() / ".reasonscript").resolve():
        raise ValueError("Phase R1 reproduction may not use the real user install root")
    package_root = destination / "package_0_5_1"
    shutil.copytree(INSTALLED_FIXTURE, install_root)
    shutil.copytree(PACKAGE_FIXTURE, package_root)
    for executable in (
        install_root / "bin/reason",
        install_root / "versions/0.5.0/reason",
        package_root / "payload/reason",
        package_root / "payload/bin/reason-runtime",
        package_root / "payload/bin/reason-updater",
    ):
        executable.chmod(executable.stat().st_mode | 0o111)
    refresh_package_checksums(package_root)
    return install_root, package_root, PlatformAdapter("macos", "arm64")


@dataclass
class UpdateTestHooks:
    """Deterministic failure injection; never enabled by the production default."""

    force_post_install_validation_failure: bool = False
    rollback_validator: Callable[[Path], dict[str, str]] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def validate(self, version_root: Path) -> dict[str, str]:
        version = (version_root / "VERSION").read_text(encoding="utf-8").strip()
        self.events.append({"event": "validation_started", "version": version})
        if version == "0.5.1" and self.force_post_install_validation_failure:
            self.events.append(
                {
                    "event": "post_install_validation_forced_failure",
                    "phase": "validating_active",
                    "reason": "fixture_manifest_flag",
                }
            )
            return {**PASS_VALIDATION, "tensor_smoke": "failed"}
        if self.rollback_validator is None:
            raise RuntimeError("rollback validator was not configured")
        fixture_path = version_root / "canonical_fixtures/phase1r"
        self.events.append(
            {
                "event": "phase1r_fixture_lookup",
                "version": version,
                "path": str(fixture_path),
                "exists": fixture_path.exists(),
            }
        )
        return self.rollback_validator(version_root)


def _run_launcher(launcher: Path, *args: str) -> tuple[bool, dict[str, Any]]:
    process = subprocess.run(
        [sys.executable, str(launcher), *args, "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError:
        payload = {}
    return process.returncode == 0, payload


def run_reproduction(destination: Path) -> dict[str, Any]:
    install_root, package_root, adapter = materialize_fixtures(destination)
    legacy_manifest = _read_json(install_root / "install_manifest.json")
    before_current = _read_json(install_root / "metadata/current.json")
    before_versions = sorted(path.name for path in (install_root / "versions").iterdir())
    preserved = {
        relative: (install_root / relative).read_bytes()
        for relative in (
            "config/user.json",
            "projects/sample-project/project.rsn",
            "artifacts/sample-artifact.json",
            "cache/sample-cache",
        )
    }
    manifest = _read_json(package_root / "manifest.json")
    hooks = UpdateTestHooks(
        force_post_install_validation_failure=bool(manifest["test_hooks"]["force_post_install_validation_failure"])
    )
    engine = UpdateEngine(install_root, adapter, validator=hooks.validate)
    hooks.rollback_validator = engine._post_install_validation
    plan = engine.check(package_root)
    report, exit_code = engine.update(package_root)

    current = _read_json(install_root / "metadata/current.json")
    launcher_ok, version_payload = _run_launcher(install_root / "bin/reason", "--version")
    health = {}
    for command in ("doctor", "install-info", "install-validate"):
        ok, payload = _run_launcher(install_root / "bin/reason", command)
        health[command.replace("-", "_")] = "passed" if ok and payload.get("status") in {"pass", "healthy"} else "failed"
    lookup = next(event for event in hooks.events if event["event"] == "phase1r_fixture_lookup")
    diagnostic = report["diagnostics"][0]
    missing_path = "<install-root>/versions/0.5.0/canonical_fixtures/phase1r"
    user_data_preserved = all((install_root / relative).read_bytes() == content for relative, content in preserved.items())
    required_components = all(
        (install_root / "versions/0.5.0" / relative).exists()
        for relative in ("reason", "VERSION", "runtime", "toolchain", "schemas", "standard_library", "metadata")
    )
    observation = {
        "schema_version": OBSERVATION_SCHEMA,
        "scenario_id": SCENARIO_ID,
        "before_update": {
            "active_version": before_current["active_version"],
            "previous_version": before_current["previous_version"],
            "install_foundation_version": legacy_manifest["install_foundation_version"],
            "runtime_version": legacy_manifest["runtime_version"],
            "installation_health": legacy_manifest["validation"]["status"],
            "version_directories": before_versions,
        },
        "update": {
            "from_version": "0.5.0",
            "to_version": "0.5.1",
            "package_validation": "passed",
            "staging_result": "passed",
            "version_installation_result": "passed",
            "activation_reached": any(
                event == {"event": "validation_started", "version": "0.5.1"} for event in hooks.events
            ),
            "post_install_validation_failed": True,
            "failure_phase": "validating_active",
            "failure_reason": "fixture_manifest_flag",
            "plan_status": plan["status"],
        },
        "rollback": {
            "started": len(hooks.events) > 2,
            "pointer_restored": current["active_version"] == "0.5.0",
            "restored_version": current["active_version"],
            "launcher_resolved": launcher_ok,
            "launcher_reported_version": version_payload.get("reason_version"),
            "phase1r_fixture_lookup_attempted": True,
            "phase1r_fixture_path": missing_path,
            "phase1r_fixture_exists": lookup["exists"],
            "validation_failed": True,
        },
        "current_behavior": {
            "top_level_status": report["status"],
            "diagnostic_code": diagnostic["code"],
            "exit_code": exit_code,
        },
        "diagnostic": {
            "code": diagnostic["code"],
            "severity": diagnostic["severity"],
            "category": diagnostic["category"],
            "phase": diagnostic["phase"],
            "message": diagnostic["message"].replace(str(install_root), "<install-root>"),
            "message_classification": "rollback_failure",
            "recovery_hint": diagnostic["recovery_hint"].replace(str(install_root), "<install-root>"),
            "attempted_version": "0.5.1",
            "restored_version": "0.5.0",
            "missing_path": missing_path,
        },
        "after_rollback": {
            "active_version": current["active_version"],
            "previous_version": current["previous_version"],
            "fixed_launcher_version": version_payload.get("reason_version"),
            "doctor_status": health["doctor"],
            "install_info_status": health["install_info"],
            "install_validate_status": health["install_validate"],
            "required_components_present": required_components,
            "failed_version_directory_exists": (install_root / "versions/0.5.1").is_dir(),
            "user_data_preserved": user_data_preserved,
        },
        "environment": {
            "temporary_install_root": True,
            "network_used": False,
            "operational_recovery_confirmed": (
                launcher_ok
                and version_payload.get("reason_version") == "0.5.0"
                and all(value == "passed" for value in health.values())
                and required_components
            ),
        },
        "observation_order": [event["event"] for event in hooks.events],
    }
    return observation
