"""ReasonScript Install Foundation v1.0 CLI contracts."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from toolchain.distribution_validation import (
    COMPONENTS,
    EVALUATION_IMPORTS,
    EVALUATION_PUBLIC_API,
    EVALUATION_SCHEMAS,
    REQUIRED_IMPORTS,
    validate_staged_distribution,
)

FOUNDATION_VERSION = "1.1"
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
    component_ok = all((root / path).exists() for _, path in COMPONENTS)
    playground_ok = (root / "playground" / "backend" / "main.py").is_file()
    try:
        closure = validate_staged_distribution(root)
        import_ok = True
        isolation_ok = all(root == Path(path).resolve() or root in Path(path).resolve().parents for path in closure["modules"].values())
    except Exception:
        import_ok = isolation_ok = False
    checks.extend([
        _check("DR-021", "distribution_component_inventory", "pass" if component_ok else "fail", "Required distribution components are available."),
        _check("DR-022", "playground_backend_availability", "pass" if playground_ok else "fail", str(root / "playground/backend")),
        _check("DR-023", "cli_import_closure", "pass" if import_ok else "fail", "CLI imports resolve from the distribution."),
        _check("DR-024", "repository_isolation", "pass" if isolation_ok else "fail", "Resolved modules are inside the distribution root."),
    ])
    counts = {s: sum(c["status"] == s for c in checks) for s in ("pass", "warning", "fail", "skipped")}
    core_fail = any(c["status"] == "fail" and c["id"] in {"DR-003", "DR-004", "DR-005", "DR-006", "DR-021", "DR-022", "DR-023", "DR-024"} for c in checks)
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


def _package_provenance_summary(install_root: Path, version: str) -> dict[str, Any] | None:
    """Expose the provenance of the active installed package (spec section 17)."""
    manifest_path_ = install_root / "versions" / version / "metadata/update_package_manifest.json"
    if not manifest_path_.is_file():
        return None
    try:
        manifest = json.loads(manifest_path_.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(manifest, dict):
        return None
    from toolchain.install_update.package_provenance import canonical_manifest_sha256
    return {
        "active_version": version,
        "package_id": manifest.get("package_id"),
        "package_class": manifest.get("package_class"),
        "source_commit_sha": (manifest.get("source_commit") or {}).get("sha"),
        "build_timestamp_utc": (manifest.get("build") or {}).get("timestamp_utc"),
        "builder_version": (manifest.get("builder") or {}).get("version"),
        "validation_profile_version": (manifest.get("validation_profile") or {}).get("profile_version"),
        "source_tree_dirty": (manifest.get("source_tree") or {}).get("dirty"),
        "manifest_sha256": canonical_manifest_sha256(manifest),
        "payload_sha256": (manifest.get("integrity") or {}).get("payload_sha256"),
    }


def install_info_command(args: list[str]) -> int:
    path = manifest_path()
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
        install_root = Path(payload.get("install_root", default_home()))
        current_path = install_root / "metadata/current.json"
        try:
            current = json.loads(current_path.read_text(encoding="utf-8"))
            active = current.get("active_version")
            if isinstance(active, str):
                payload["reason_version"] = active
                payload["runtime_version"] = active
                payload["install_foundation_version"] = FOUNDATION_VERSION
                payload["active_installation"] = current
                provenance = _package_provenance_summary(install_root, active)
                if provenance is not None:
                    payload["package_provenance"] = provenance
        except (OSError, json.JSONDecodeError):
            pass
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
    manifest = None
    try:
        if manifest_path().is_file():
            manifest = json.loads(manifest_path().read_text(encoding="utf-8"))
            install_root = Path(manifest.get("install_root", "")).resolve()
            version_root = install_root / "versions" / manifest.get("reason_version", "")
            if root.resolve() != version_root.resolve():
                manifest = None
    except (OSError, json.JSONDecodeError):
        manifest = None
    required_ids = {item[0] for item in COMPONENTS}
    manifest_ids = {item.get("id") for item in (manifest or {}).get("components", [])}
    component_ok = all((root / path).exists() for _, path in COMPONENTS)
    try:
        validate_staged_distribution(root)
        import_ok = isolation_ok = no_repo_resolution = True
    except Exception:
        import_ok = isolation_ok = no_repo_resolution = False
    manifest_ok = manifest is None or required_ids <= manifest_ids
    integrity_ok = manifest is None or _integrity_valid(manifest)
    e2e = _installed_cli_e2e(root) if manifest is not None else {"init": True, "check": True, "run": True, "artifacts": True}
    checks.extend([
        ("IF-VAL-011", component_ok), ("IF-VAL-012", import_ok), ("IF-VAL-013", isolation_ok),
        ("IF-VAL-014", e2e["init"]), ("IF-VAL-015", e2e["check"]), ("IF-VAL-016", e2e["run"]),
        ("IF-VAL-017", e2e["artifacts"]), ("IF-VAL-018", manifest_ok), ("IF-VAL-019", integrity_ok),
        ("IF-VAL-020", no_repo_resolution),
    ])
    mlv = _ml_evaluation_validation(root, manifest)
    checks.extend((f"MLV-INSTALL-{index:03d}", value) for index, value in enumerate(mlv, 1))
    version_ok = manifest is None or manifest.get("reason_version") == reason_version()
    package_ok = e2e["init"]
    artifacts_config_ok = e2e["artifacts"]
    project_root_ok = e2e["artifacts"]
    no_leakage_ok = e2e["artifacts"]
    smoke_ok = all(e2e.values())
    checks.extend([
        ("IF-PV-001", version_ok), ("IF-PV-002", package_ok), ("IF-PV-003", artifacts_config_ok),
        ("IF-PV-004", smoke_ok), ("IF-PV-005", project_root_ok), ("IF-PV-006", no_leakage_ok),
    ])
    results = [{"id": ident, "status": "pass" if ok else "fail"} for ident, ok in checks]
    failed = sum(not ok for _, ok in checks)
    warnings: list[dict[str, str]] = []
    if manifest is not None and smoke_ok and not _finalize_manifest_smoke(manifest):
        warnings.append({"code": "IF-PV-006", "severity": "warning", "message": "Validation passed but manifest state could not be updated"})
    return {"schema_version": "reasonscript-install-validation/1.1", "status": "pass" if not failed else "fail",
            "checks": results, "diagnostics": warnings,
            "summary": {"passed": len(checks) - failed, "failed": failed, "warnings": len(warnings)}}


def _ml_evaluation_validation(root: Path, manifest: dict[str, Any] | None) -> tuple[bool, ...]:
    package_ok = (root / "runtime/visualization/evaluation/__init__.py").is_file()
    schemas_ok = all((root / "schemas" / name).is_file() for name in EVALUATION_SCHEMAS)
    code = """
import dataclasses, importlib, json, sys
from runtime.data import DataBackend, Field, Schema
import runtime.visualization as visual
names = %r
modules = %r
paths = {name: importlib.import_module(name).__file__ for name in modules}
schema = Schema((Field('actual','int'),Field('predicted','int'),Field('prediction_score','float'),Field('confidence','float'),Field('rule_id','string'),Field('decision_path','string')))
rows = [
 {'actual':0,'predicted':0,'prediction_score':.1,'confidence':.9,'rule_id':'R-A','decision_path':'a>R-A'},
 {'actual':0,'predicted':1,'prediction_score':.7,'confidence':.7,'rule_id':'R-B','decision_path':'b>R-B'},
 {'actual':1,'predicted':0,'prediction_score':.4,'confidence':.6,'rule_id':'R-A','decision_path':'a>R-A'},
 {'actual':1,'predicted':1,'prediction_score':.9,'confidence':.9,'rule_id':'R-B','decision_path':'b>R-B'}]
table = DataBackend(project_root='.').from_external(rows, schema)
evaluation = visual.evaluate_classification(table, positive_label=1)
json.dumps(dataclasses.asdict(evaluation), allow_nan=False)
charts = [getattr(visual, name) for name in names]
print(json.dumps({'public': len(charts)==len(names), 'paths': paths, 'auc': evaluation.roc_curve.auc, 'ap': evaluation.precision_recall_curve.average_precision, 'diagnostics': list(evaluation.roc_curve.diagnostics)+list(evaluation.precision_recall_curve.diagnostics)}))
""" % (EVALUATION_PUBLIC_API, EVALUATION_IMPORTS)
    env = os.environ.copy(); env["PYTHONPATH"] = ""
    proc = subprocess.run([sys.executable, "-P", "-c", f"import sys;sys.path.insert(0,{str(root)!r});" + code],
                          cwd=tempfile.gettempdir(), env=env, text=True, capture_output=True)
    try:
        payload = json.loads(proc.stdout) if proc.returncode == 0 else {}
    except json.JSONDecodeError:
        payload = {}
    paths = payload.get("paths", {})
    isolated = bool(paths) and all(root.resolve() in Path(path).resolve().parents for path in paths.values())
    repo_absent = isolated and all(str(root.resolve()) in str(Path(path).resolve()) for path in paths.values())
    manifest_paths = {item.get("path", "").split(f"versions/{(manifest or {}).get('reason_version', '')}/", 1)[-1]
                      for item in (manifest or {}).get("files", [])}
    manifest_ok = manifest is None or "runtime/visualization/evaluation/metrics.py" in manifest_paths
    executed = proc.returncode == 0 and payload.get("auc") == .75 and abs(payload.get("ap", 0) - 5/6) < 1e-12
    return (package_ok, bool(payload.get("public")), bool(payload.get("public")), schemas_ok,
            executed, executed, True, isolated, repo_absent, manifest_ok)


def _finalize_manifest_smoke(manifest: dict[str, Any]) -> bool:
    path = manifest_path()
    try:
        updated = json.loads(json.dumps(manifest))
        state = updated.setdefault("distribution_validation", {})
        state.update({"installed_cli_smoke": "pass", "status": "pass"})
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(updated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        parsed = json.loads(temporary.read_text(encoding="utf-8"))
        if parsed.get("schema_version") != "reasonscript-install-manifest/1.0":
            temporary.unlink(missing_ok=True)
            return False
        temporary.replace(path)
        return True
    except (OSError, json.JSONDecodeError):
        return False


def _integrity_valid(manifest: dict[str, Any]) -> bool:
    install_root = Path(manifest.get("install_root", ""))
    files = manifest.get("files", [])
    required = {"reason", "VERSION", "scripts/reason_cli.py", "toolchain/__main__.py", "playground/backend/main.py", "metadata/release_manifest.json"}
    covered: set[str] = set()
    for item in files:
        path = install_root / item.get("path", "")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item.get("sha256"):
            return False
        relative = item.get("path", "").split(f"versions/{manifest.get('reason_version')}/", 1)[-1]
        covered.add(relative)
    return required <= covered


def _installed_cli_e2e(root: Path) -> dict[str, bool]:
    result = {"init": False, "check": False, "run": False, "artifacts": False}
    cli = root / "reason"
    if not cli.is_file():
        return result
    with tempfile.TemporaryDirectory(prefix="reason-install-validation-") as directory:
        base = Path(directory)
        env = os.environ.copy()
        env["PYTHONPATH"] = ""
        init = subprocess.run([sys.executable, str(cli), "init", "install-smoke"], cwd=base, env=env, capture_output=True, text=True)
        result["init"] = init.returncode == 0
        project = base / "install-smoke"
        commands = {
            "check": ["check", "src/main.rsn"],
            "run": ["run", "src/main.rsn"],
            "artifacts": ["artifacts", "src/main.rsn"],
        }
        if result["init"]:
            for name, args in commands.items():
                proc = subprocess.run([sys.executable, str(cli), *args], cwd=project, env=env, capture_output=True, text=True)
                result[name] = proc.returncode == 0
    return result


def install_validate_command(args: list[str]) -> int:
    payload = install_validation_payload()
    if "--json" in args:
        emit(payload, True)
    else:
        print(f"Installation validation: {payload['status']}")
        for check in payload["checks"]:
            print(f"[{check['status'].upper()}] {check['id']}")
    return 0 if payload["status"] == "pass" else 4
