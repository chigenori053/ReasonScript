"""Distribution completeness contracts shared by installation and diagnostics."""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

DISTRIBUTION_TARGETS = (
    "toolchain", "scripts", "schemas", "frontend", "runtime", "examples",
    "standard_library", "metadata", "playground", "conformance",
)

COMPONENTS = (
    ("cli", "reason"),
    ("runtime-core", "runtime"),
    ("toolchain", "toolchain"),
    ("scripts", "scripts"),
    ("frontend-core", "frontend"),
    ("schemas", "schemas"),
    ("standard-library", "standard_library"),
    ("examples", "examples"),
    ("metadata", "metadata"),
    ("playground-backend", "playground/backend"),
    ("conformance-core", "conformance"),
)

REQUIRED_IMPORTS = ("toolchain", "scripts.reason_cli", "playground.backend.main")
INTEGRITY_ENTRY_POINTS = (
    "reason", "VERSION", "scripts/reason_cli.py", "toolchain/__main__.py",
    "playground/backend/main.py", "metadata/release_manifest.json",
)


class DistributionError(RuntimeError):
    def __init__(self, code: str, message: str, component: str = "distribution", path: str = "") -> None:
        super().__init__(message)
        self.code, self.component, self.path = code, component, path

    def diagnostic(self) -> dict[str, str]:
        return {"code": self.code, "severity": "fatal" if self.code in {"IF-DC-001", "IF-DC-015"} else "error",
                "component": self.component, "message": str(self), "path": self.path,
                "hint": "Include and validate the required component in the distribution."}


def validate_source_targets(root: Path) -> None:
    root = root.resolve()
    for name in DISTRIBUTION_TARGETS:
        source = (root / name).resolve()
        if not source.is_dir() or root not in source.parents:
            raise DistributionError("IF-DC-001", "Required distribution target is missing.", name, name)
    for package in ("toolchain", "scripts", "frontend", "runtime", "playground"):
        if not (root / package).is_dir():
            raise DistributionError("IF-DC-002", "Required Python package is missing.", package, package)


def validate_staged_distribution(root: Path, repository_root: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    for component, relative in COMPONENTS:
        if not (root / relative).exists():
            raise DistributionError("IF-DC-001", "Required distribution target is missing.", component, relative)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    code = (
        "import importlib,json,sys; names=" + repr(REQUIRED_IMPORTS) + "; "
        "mods=[importlib.import_module(n) for n in names]; "
        "print(json.dumps({'modules':{n:str(m.__file__) for n,m in zip(names,mods)},'sys_path':sys.path}))"
    )
    proc = subprocess.run([sys.executable, "-P", "-c", "import sys;sys.path.insert(0," + repr(str(root)) + ");" + code],
                          cwd=tempfile.gettempdir(), env=env, text=True, capture_output=True)
    if proc.returncode:
        raise DistributionError("IF-DC-003", f"Installed CLI import closure is incomplete: {proc.stderr.strip()}", "python-packages")
    payload = json.loads(proc.stdout)
    for name, filename in payload["modules"].items():
        resolved = Path(filename).resolve()
        if root != resolved and root not in resolved.parents:
            raise DistributionError("IF-DC-004", f"Module {name} resolved outside the install root.", name, str(resolved))
        if repository_root and (repository_root.resolve() == resolved or repository_root.resolve() in resolved.parents):
            raise DistributionError("IF-DC-014", f"Repository path leaked while importing {name}.", name, str(resolved))
    return payload


def inventory(root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    paths = {root / p for p in INTEGRITY_ENTRY_POINTS}
    paths.update((root / "schemas").glob("*.json"))
    for path in sorted(paths):
        if not path.is_file():
            raise DistributionError("IF-DC-006", "Required component integrity record source is missing.", "integrity", str(path.relative_to(root)))
        files.append({"path": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size_bytes": path.stat().st_size})
    return files


def normalize_project_identifier(name: str) -> str:
    reserved = {"package", "module", "fn", "return", "model", "if", "else", "match", "import", "export"}
    normalized = unicodedata.normalize("NFKC", name).strip().replace("-", "_")
    value = re.sub(r"[^A-Za-z0-9_]", "_", normalized)
    value = re.sub(r"_+", "_", value).strip("_") or "reason_project"
    if value[0].isdigit() or value in reserved:
        value = f"project_{value}"
    return value
