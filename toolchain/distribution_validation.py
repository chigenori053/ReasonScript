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
    "standard_library", "metadata", "playground", "conformance", "canonical_fixtures",
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
    ("canonical-fixtures", "canonical_fixtures"),
    ("ml-evaluation-visualization-v0.2", "runtime/visualization/evaluation"),
)

EVALUATION_IMPORTS = (
    "runtime", "runtime.data", "runtime.visualization", "runtime.visualization.evaluation",
    "runtime.visualization.evaluation.model", "runtime.visualization.evaluation.metrics",
    "runtime.visualization.evaluation.operations", "runtime.visualization.evaluation.artifacts",
)
REQUIRED_IMPORTS = ("toolchain", "scripts.reason_cli", "playground.backend.main", *EVALUATION_IMPORTS)
EVALUATION_PUBLIC_API = (
    "evaluate_classification", "confusion_matrix", "normalized_confusion_matrix",
    "classification_metrics", "roc_curve", "precision_recall_curve", "rule_coverage",
    "rule_accuracy", "decision_path_frequency", "error_distribution",
    "confidence_distribution", "score_distribution",
)
EVALUATION_SCHEMAS = (
    "classification_evaluation.schema.json", "classification_metrics.schema.json",
    "confusion_matrix.schema.json", "decision_path_evaluation.schema.json",
    "evaluation_render_plan.schema.json", "evaluation_visualization_ir.schema.json",
    "evaluation_visualization_result.schema.json", "evaluation_visualization_spec.schema.json",
    "precision_recall_curve.schema.json", "prediction_evidence.schema.json",
    "roc_curve.schema.json", "rule_evaluation.schema.json",
)
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
    visualization = import_from_distribution(root, "runtime.visualization")
    missing = [name for name in EVALUATION_PUBLIC_API if not hasattr(visualization, name)]
    if missing:
        raise DistributionError("IF-DC-003", f"ML Evaluation public API is incomplete: {missing}", "ml-evaluation")
    for schema in EVALUATION_SCHEMAS:
        if not (root / "schemas" / schema).is_file():
            raise DistributionError("IF-DC-006", "Required ML Evaluation schema is missing.", "ml-evaluation", f"schemas/{schema}")
    return payload


def import_from_distribution(root: Path, name: str):
    """Import from a staged tree for in-process source validation."""
    original = list(sys.path)
    previous = {key: value for key, value in sys.modules.items() if key == "runtime" or key.startswith("runtime.")}
    try:
        for key in previous:
            sys.modules.pop(key, None)
        sys.path.insert(0, str(root))
        return importlib.import_module(name)
    finally:
        sys.path[:] = original
        for key in list(sys.modules):
            if key == "runtime" or key.startswith("runtime."):
                sys.modules.pop(key, None)
        sys.modules.update(previous)


def inventory(root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for relative in INTEGRITY_ENTRY_POINTS:
        if not (root / relative).is_file():
            raise DistributionError("IF-DC-006", "Required component integrity record source is missing.", "integrity", relative)
    paths = {path for path in root.rglob("*") if path.is_file() and path.suffix != ".pyc" and "__pycache__" not in path.parts}
    for path in sorted(paths):
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
