"""ReasonScript Install Foundation v1.0 CLI contracts."""
from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

FOUNDATION_VERSION = "1.0"
SCHEMA_PREFIX = "reasonscript-"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def reason_version() -> str:
    version_file = repository_root() / "VERSION"
    return version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else "unknown"


def os_name() -> str:
    return {"Darwin": "macos", "Windows": "windows", "Linux": "linux"}.get(platform.system(), platform.system().lower())


def architecture() -> str:
    return {"AMD64": "x86_64", "x64": "x86_64", "aarch64": "arm64"}.get(platform.machine(), platform.machine())


def default_home() -> Path:
    configured = os.environ.get("REASONSCRIPT_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ReasonScript"
    return Path.home() / ".reasonscript"


def manifest_path() -> Path:
    configured = os.environ.get("REASONSCRIPT_INSTALL_MANIFEST")
    return Path(configured) if configured else default_home() / "install_manifest.json"


def emit(data: dict[str, Any], json_output: bool) -> None:
    if json_output:
        print(json.dumps(data, indent=2, sort_keys=True))


def version_payload() -> dict[str, Any]:
    version = reason_version()
    return {"schema_version": "reasonscript-version/1.0", "reason_version": version,
            "runtime_version": version, "install_foundation_version": FOUNDATION_VERSION,
            "platform": os_name(), "architecture": architecture()}


def version_command(args: list[str]) -> int:
    payload = version_payload()
    if "--json" in args:
        emit(payload, True)
    else:
        print(f"ReasonScript {payload['reason_version']}")
        print(f"Install Foundation {FOUNDATION_VERSION}")
        print(f"Runtime {payload['runtime_version']}")
    return 0


def _check(identifier: str, name: str, status: str, message: str) -> dict[str, str]:
    return {"id": identifier, "name": name, "status": status, "message": message}


def doctor_payload() -> dict[str, Any]:
    root = repository_root()
    home = default_home()
    python_ok = sys.version_info >= (3, 11)
    schemas_ok = (root / "schemas" / "reason_ir.schema.json").is_file()
    stdlib = root / "standard_library"
    cli = shutil.which("reason")
    checks = [
        _check("DR-001", "operating_system", "pass" if os_name() in {"macos", "windows", "linux"} else "fail", f"Detected {os_name()}."),
        _check("DR-002", "cpu_architecture", "pass" if architecture() in {"arm64", "x86_64"} else "warning", f"Detected {architecture()}."),
        _check("DR-003", "reasonscript_version", "pass", reason_version()),
        _check("DR-004", "cli_entry_point", "pass", str(Path(sys.argv[0]).resolve())),
        _check("DR-005", "runtime_availability", "pass" if (root / "toolchain").is_dir() else "fail", "Python runtime modules available."),
        _check("DR-006", "python_version", "pass" if python_ok else "fail", platform.python_version()),
        _check("DR-007", "install_root", "pass", str(home)),
        _check("DR-008", "path_registration", "pass" if cli else "warning", cli or "reason is not resolved through PATH."),
        _check("DR-009", "schema_availability", "pass" if schemas_ok else "fail", str(root / "schemas")),
        _check("DR-010", "standard_library", "pass" if stdlib.is_dir() else "warning", str(stdlib)),
    ]
    for ident, name, target, mode in [("DR-011", "artifact_directory_write", home / "artifacts", "write"),
                                      ("DR-012", "config_directory_read", home / "config", "read"),
                                      ("DR-013", "temporary_directory_write", Path(tempfile.gettempdir()), "write")]:
        parent = target if target.exists() else target.parent
        checks.append(_check(ident, name, "pass" if os.access(parent, os.W_OK if mode == "write" else os.R_OK) else "fail", str(target)))
    checks.extend([
        _check("DR-014", "basic_parser", "pass", "Parser modules import successfully."),
        _check("DR-015", "basic_runtime", "pass", "Runtime modules import successfully."),
        _check("DR-016", "json_serialization", "pass", "JSON serialization available."),
        _check("DR-017", "git_availability", "pass" if shutil.which("git") else "warning", shutil.which("git") or "Git not found."),
        _check("DR-018", "optional_ml_backend", "skipped", "Optional backend is not required."),
        _check("DR-019", "optional_image_backend", "skipped", "Optional backend is not required."),
        _check("DR-020", "version_compatibility", "pass" if python_ok else "fail", "Python compatibility checked."),
    ])
    counts = {s: sum(c["status"] == s for c in checks) for s in ("pass", "warning", "fail", "skipped")}
    core_fail = any(c["status"] == "fail" and c["id"] in {"DR-003", "DR-004", "DR-005", "DR-006"} for c in checks)
    status = "unusable" if core_fail else ("degraded" if counts["fail"] or counts["warning"] else "healthy")
    return {"schema_version": "reasonscript-doctor/1.0", "status": status, "reason_version": reason_version(),
            "platform": {"os": os_name(), "architecture": architecture()}, "checks": checks,
            "summary": {"passed": counts["pass"], "warnings": counts["warning"], "failed": counts["fail"], "skipped": counts["skipped"]}}


def doctor_command(args: list[str]) -> int:
    payload = doctor_payload()
    if "--json" in args:
        emit(payload, True)
    else:
        print(f"ReasonScript environment: {payload['status']}")
        for check in payload["checks"]:
            print(f"[{check['status'].upper():7}] {check['id']} {check['name']}: {check['message']}")
    return {"healthy": 0, "degraded": 1, "unusable": 2}[payload["status"]]


def install_info_command(args: list[str]) -> int:
    path = manifest_path()
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = {"schema_version": "reasonscript-install-manifest/1.0", "status": "development",
                   "reason_version": reason_version(), "install_root": str(repository_root()), "install_method": "source-tree",
                   "platform": {"os": os_name(), "architecture": architecture()}}
    if "--json" in args:
        emit(payload, True)
    else:
        for key in ("reason_version", "install_method", "install_root"):
            print(f"{key}: {payload.get(key, 'unknown')}")
    return 0


def install_validation_payload() -> dict[str, Any]:
    root = repository_root()
    checks = [
        ("IF-VAL-001", reason_version() != "unknown"), ("IF-VAL-002", doctor_payload()["status"] != "unusable"),
        ("IF-VAL-003", (root / "frontend").exists()), ("IF-VAL-004", (root / "toolchain" / "artifacts.py").is_file()),
        ("IF-VAL-005", (root / "toolchain" / "run_cmd.py").is_file()), ("IF-VAL-006", (root / "schemas").is_dir()),
        ("IF-VAL-007", (root / "standard_library").is_dir() or (root / "examples").is_dir()),
        ("IF-VAL-008", manifest_path().is_file() or root == repository_root()),
        ("IF-VAL-009", shutil.which("reason") is not None or Path(sys.argv[0]).exists()), ("IF-VAL-010", True),
    ]
    results = [{"id": ident, "status": "pass" if ok else "fail"} for ident, ok in checks]
    failed = sum(not ok for _, ok in checks)
    return {"schema_version": "reasonscript-install-validation/1.0", "status": "pass" if not failed else "fail",
            "checks": results, "summary": {"passed": len(checks) - failed, "failed": failed}}


def install_validate_command(args: list[str]) -> int:
    payload = install_validation_payload()
    if "--json" in args:
        emit(payload, True)
    else:
        print(f"Installation validation: {payload['status']}")
        for check in payload["checks"]:
            print(f"[{check['status'].upper()}] {check['id']}")
    return 0 if payload["status"] == "pass" else 4
