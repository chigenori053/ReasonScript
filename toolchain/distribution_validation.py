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

VISION_DISTRIBUTION_PROFILE = "reasonscript-vision-install-distribution/0.1"

DISTRIBUTION_TARGETS = (
    "toolchain", "scripts", "schemas", "frontend", "runtime", "examples",
    "standard_library", "metadata", "playground", "conformance", "canonical_fixtures",
    "VisionRuntime", "NativeReasonUnitRuntime",
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
    ("vision-runtime-v0.1", "VisionRuntime"),
    ("reasonunit-runtime-v1.0", "NativeReasonUnitRuntime"),
)

EVALUATION_IMPORTS = (
    "runtime", "runtime.data", "runtime.visualization", "runtime.visualization.evaluation",
    "runtime.visualization.evaluation.model", "runtime.visualization.evaluation.metrics",
    "runtime.visualization.evaluation.operations", "runtime.visualization.evaluation.artifacts",
)
REQUIRED_IMPORTS = (
    "toolchain", "scripts.reason_cli", "playground.backend.main",
    "frontend.vision.contracts", "frontend.vision.runtime", *EVALUATION_IMPORTS,
)
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
    "VisionRuntime/Cargo.toml", "frontend/vision/contracts.py",
    "NativeReasonUnitRuntime/Cargo.toml",
    "schemas/vision_observation.schema.json",
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
    vision_binary = _vision_binary(root)
    if vision_binary is None:
        raise DistributionError("IF-DC-001", "Required VisionRuntime native executable is missing.", "vision-runtime", "bin/reason-vision")
    proc = subprocess.run([str(vision_binary), "verify-native"], cwd=tempfile.gettempdir(), text=True, capture_output=True)
    try:
        native = json.loads(proc.stdout)
    except json.JSONDecodeError as error:
        raise DistributionError("IF-DC-003", "VisionRuntime native smoke output is invalid.", "vision-runtime", str(vision_binary)) from error
    if proc.returncode or native.get("ok") is not True or native.get("unsafe_blocks") != 0 or native.get("profile") != "reasonscript-vision-runtime/0.1":
        raise DistributionError("IF-DC-003", "VisionRuntime native smoke validation failed.", "vision-runtime", str(vision_binary))
    if not (root / "schemas/vision_observation.schema.json").is_file():
        raise DistributionError("IF-DC-006", "Vision observation schema is missing.", "vision-runtime", "schemas/vision_observation.schema.json")
    payload["vision_runtime"] = {"path": str(vision_binary), "profile": native.get("profile"), "unsafe_blocks": 0}
    reasonunit_binary = _reasonunit_binary(root)
    if reasonunit_binary is None:
        raise DistributionError(
            "IF-DC-001",
            "Required Native ReasonUnit Runtime executable is missing.",
            "reasonunit-runtime",
            "bin/reasonunit-runtime-native",
        )
    proc = subprocess.run(
        [str(reasonunit_binary), "verify-native"],
        cwd=tempfile.gettempdir(),
        text=True,
        capture_output=True,
    )
    try:
        reasonunit_native = json.loads(proc.stdout)
    except json.JSONDecodeError as error:
        raise DistributionError(
            "IF-DC-003",
            "Native ReasonUnit Runtime smoke output is invalid.",
            "reasonunit-runtime",
            str(reasonunit_binary),
        ) from error
    if (
        proc.returncode
        or reasonunit_native.get("ok") is not True
        or reasonunit_native.get("unsafe_blocks") != 0
        or reasonunit_native.get("native_execution_provenance")
        != "reasonscript-reasonunit-native-runtime/1.0"
    ):
        raise DistributionError(
            "IF-DC-003",
            "Native ReasonUnit Runtime smoke validation failed.",
            "reasonunit-runtime",
            str(reasonunit_binary),
        )
    payload["reasonunit_runtime"] = {
        "path": str(reasonunit_binary),
        "profile": reasonunit_native.get("native_execution_provenance"),
        "unsafe_blocks": 0,
    }
    return payload


def _vision_binary(root: Path) -> Path | None:
    name = "reason-vision.exe" if os.name == "nt" else "reason-vision"
    candidates = (
        root / "bin" / name,
        root / "VisionRuntime" / "target" / "release" / name,
        root / "VisionRuntime" / "target" / "debug" / name,
    )
    return next((path for path in candidates if path.is_file()), None)


def _reasonunit_binary(root: Path) -> Path | None:
    name = (
        "reasonunit-runtime-native.exe"
        if os.name == "nt"
        else "reasonunit-runtime-native"
    )
    candidates = (
        root / "bin" / name,
        root / "NativeReasonUnitRuntime" / "target" / "release" / name,
        root / "NativeReasonUnitRuntime" / "target" / "debug" / name,
    )
    return next((path for path in candidates if path.is_file()), None)


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
