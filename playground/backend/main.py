"""ReasonScript Playground IDE — FastAPI backend."""

from __future__ import annotations

import dataclasses
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure the repo root is on the path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from pydantic import BaseModel

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal test envs
    class _MissingFastAPI:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.routes: list[tuple[str, str, Any]] = []

        def add_middleware(self, *args: Any, **kwargs: Any) -> None:
            return None

        def mount(self, *args: Any, **kwargs: Any) -> None:
            return None

        def get(self, path: str, **kwargs: Any):
            return self._route("GET", path)

        def post(self, path: str, **kwargs: Any):
            return self._route("POST", path)

        def _route(self, method: str, path: str):
            def decorator(func: Any) -> Any:
                self.routes.append((method, path, func))
                return func

            return decorator

    FastAPI = _MissingFastAPI
    CORSMiddleware = object
    class StaticFiles:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    class FileResponse:  # type: ignore[no-redef]
        def __init__(self, path: str) -> None:
            self.path = path

from frontend.ast import to_json_value as semantic_to_json_value
from frontend.language_surface.parser import parse, SurfaceSyntaxError
from frontend.language_surface.integration import compile_program, project_program
from frontend.language_surface.nodes import to_json_value as surface_to_json_value
from frontend.language_surface.validation import SurfaceValidationError
from frontend.language_surface.namespace import NamespaceResolutionError
from playground.backend.engine import build_execution_plan, simulate, extract_knowledge
from playground.backend.analyzer import analyze_ir
from playground.backend.language_audit import run_language_audit, write_language_audit_reports

EXAMPLES_DIR = REPO_ROOT / "TestPlayground" / "examples"
REGRESSION_EXAMPLES_DIR = REPO_ROOT / "examples"
EXPORTS_DIR = REPO_ROOT / "playground" / "exports"
BASELINE_DIR = REPO_ROOT / "playground" / "baseline"

ARTIFACT_FILES = {
    "ast": "ast.json",
    "semantic_ast": "semantic_ast.json",
    "reason_ir": "reason_ir.json",
    "execution_plan": "execution_plan.json",
    "simulation": "simulation.json",
    "knowledge": "knowledge.json",
    "validation": "validation.json",
}

app = FastAPI(title="ReasonScript Playground")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class SourceRequest(BaseModel):
    source: str
    filename: str = "playground.rsn"
    compiler_mode: str = "normal"  # normal | strict | rust_compatible


class ValidateResponse(BaseModel):
    ok: bool
    phase: str | None = None
    errors: list[dict[str, Any]] = []
    ast: dict[str, Any] | None = None


class CompileResponse(BaseModel):
    ok: bool
    phase: str | None = None
    errors: list[dict[str, Any]] = []
    ast: dict[str, Any] | None = None
    reason_irs: list[dict[str, Any]] = []


class PipelineResponse(BaseModel):
    ok: bool
    phase: str | None = None
    errors: list[dict[str, Any]] = []
    ast: dict[str, Any] | None = None
    semantic_ast: dict[str, Any] | None = None
    reason_irs: list[dict[str, Any]] = []
    execution_plan: dict[str, Any] | None = None
    simulation: dict[str, Any] | None = None
    knowledge: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None


class Example(BaseModel):
    id: str
    category: str
    name: str
    source: str


class ArtifactPathRequest(BaseModel):
    path: str


class DiffRequest(BaseModel):
    a: dict[str, Any] | str
    b: dict[str, Any] | str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ast_to_dict(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _ast_to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [_ast_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _ast_to_dict(v) for k, v in obj.items()}
    return obj


def _make_error(phase: str, message: str) -> dict[str, Any]:
    import re
    line_match = re.search(r"line\s+(\d+)", message, re.IGNORECASE)
    line = int(line_match.group(1)) if line_match else None
    return {"phase": phase, "message": message, "line": line}


def _validation_node(name: str, ok: bool, children: list[dict[str, Any]] | None = None, details: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "ok": ok,
        "details": details,
        "children": children or [],
    }


def _validation_report(ok: bool, errors: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    errors = errors or []
    failed_phase = errors[0]["phase"] if errors else None
    parser_ok = ok or failed_phase not in {"Parse"}
    semantic_ok = ok or failed_phase not in {"Validation", "Compile"}
    pipeline_ok = ok and not errors
    return {
        "schema_version": "validation-report/0.3",
        "ok": ok,
        "generated_at": datetime.now(UTC).isoformat(),
        "errors": errors,
        "tree": _validation_node("Validation", ok, [
            _validation_node("Parser", parser_ok, details={"phase": "Parse"}),
            _validation_node("Semantic", semantic_ok, details={"phase": "Semantic Validation"}),
            _validation_node("SCV-1", semantic_ok, details={"phase": "Semantic Consistency Validation"}),
            _validation_node("Planning", pipeline_ok, details={"phase": "ExecutionPlan"}),
            _validation_node("Simulation", pipeline_ok, details={"phase": "Semantic Simulation"}),
            _validation_node("Knowledge", pipeline_ok, details={"phase": "Knowledge Emergence"}),
        ]),
    }


def _run_pipeline_artifacts(req: SourceRequest) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        program = parse(req.source)
    except SurfaceSyntaxError as e:
        errors = [_make_error("Parse", str(e))]
        return _failed_artifacts(req, {}, errors), errors
    except Exception as e:
        errors = [_make_error("Parse", str(e))]
        return _failed_artifacts(req, {}, errors), errors

    ast_dict = surface_to_json_value(program)

    try:
        semantic_modules = project_program(program)
        semantic_ast = [semantic_to_json_value(module) for module in semantic_modules]
        reason_irs = list(compile_program(program))
    except (SurfaceValidationError, NamespaceResolutionError) as e:
        errors = [_make_error("Compile", str(e))]
        return _failed_artifacts(req, ast_dict, errors), errors
    except Exception as e:
        errors = [_make_error("Compile", str(e))]
        return _failed_artifacts(req, ast_dict, errors), errors

    plans = [build_execution_plan(ir) for ir in reason_irs]
    sims = [simulate(ir) for ir in reason_irs]
    knowledges = [extract_knowledge(ir, sim) for ir, sim in zip(reason_irs, sims)]
    validation = _validation_report(True)

    return {
        "ast": ast_dict,
        "semantic_ast": semantic_ast[0] if len(semantic_ast) == 1 else {"modules": semantic_ast},
        "reason_ir": reason_irs[0] if len(reason_irs) == 1 else {"modules": reason_irs},
        "execution_plan": plans[0] if len(plans) == 1 else {"modules": plans},
        "simulation": sims[0] if len(sims) == 1 else {"modules": sims},
        "knowledge": knowledges[0] if len(knowledges) == 1 else {"modules": knowledges},
        "validation": validation,
        "source": {"filename": req.filename, "text": req.source},
    }, []


def _failed_artifacts(req: SourceRequest, ast_dict: dict[str, Any], errors: list[dict[str, Any]]) -> dict[str, Any]:
    validation = _validation_report(False, errors)
    return {
        "ast": ast_dict,
        "semantic_ast": None,
        "reason_ir": [],
        "execution_plan": None,
        "simulation": None,
        "knowledge": None,
        "validation": validation,
        "source": {"filename": req.filename, "text": req.source},
    }


def _artifact_response(artifacts: dict[str, Any], ok: bool = True, errors: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    reason_ir = artifacts.get("reason_ir")
    reason_irs = reason_ir.get("modules", []) if isinstance(reason_ir, dict) and "modules" in reason_ir else ([reason_ir] if reason_ir else [])
    return {
        "ok": ok,
        "errors": errors or [],
        "ast": artifacts.get("ast"),
        "semantic_ast": artifacts.get("semantic_ast"),
        "reason_irs": reason_irs,
        "execution_plan": artifacts.get("execution_plan"),
        "simulation": artifacts.get("simulation"),
        "knowledge": artifacts.get("knowledge"),
        "validation": artifacts.get("validation"),
        "artifacts": artifacts,
    }


def _safe_artifact_dir(base_dir: Path, requested: str | None = None) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    name = requested or datetime.now(UTC).strftime("sample_%Y%m%d_%H%M%S")
    name = Path(name).name
    return base_dir / name


def _write_artifacts(directory: Path, artifacts: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for key, filename in ARTIFACT_FILES.items():
        (directory / filename).write_text(
            json.dumps(artifacts.get(key), indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
    manifest = {
        "schema_version": "reasonscript-playground-artifacts/0.3",
        "created_at": datetime.now(UTC).isoformat(),
        "files": ARTIFACT_FILES,
        "source": artifacts.get("source"),
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_artifacts(path: str) -> dict[str, Any]:
    artifact_dir = Path(path)
    if not artifact_dir.is_absolute():
        artifact_dir = REPO_ROOT / artifact_dir
    artifacts: dict[str, Any] = {}
    for key, filename in ARTIFACT_FILES.items():
        file_path = artifact_dir / filename
        artifacts[key] = json.loads(file_path.read_text(encoding="utf-8")) if file_path.exists() else None
    manifest_path = artifact_dir / "manifest.json"
    if manifest_path.exists():
        artifacts["manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts["path"] = str(artifact_dir)
    return artifacts


def _artifact_from_payload(value: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(value, str):
        return _read_artifacts(value)
    return value.get("artifacts", value)


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _knowledge_lines(value: Any) -> set[str]:
    if not value:
        return set()
    if isinstance(value, dict) and "modules" in value:
        lines: set[str] = set()
        for module in value["modules"]:
            lines |= _knowledge_lines(module)
        return lines
    items = value.get("knowledge", []) if isinstance(value, dict) else []
    return {
        (
            f"{item.get('source')} {item.get('relation')} {item.get('target')} "
            f"{item.get('path_signature', '')}"
        )
        for item in items
        if isinstance(item, dict)
    }


def _trace_labels(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, dict) and "modules" in value:
        traces: list[str] = []
        for module in value["modules"]:
            traces.extend(_trace_labels(module))
        return traces
    trace = value.get("trace", []) if isinstance(value, dict) else []
    return [str(item.get("state")) for item in trace if isinstance(item, dict) and item.get("state") is not None]


def _diff_artifacts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    plan_a = a.get("execution_plan")
    plan_b = b.get("execution_plan")
    sim_a = a.get("simulation")
    sim_b = b.get("simulation")
    know_a = _knowledge_lines(a.get("knowledge"))
    know_b = _knowledge_lines(b.get("knowledge"))
    changes: list[dict[str, Any]] = []
    for key in ("execution_plan", "simulation", "knowledge"):
        old = a.get(key)
        new = b.get(key)
        if _stable_json(old) != _stable_json(new):
            changes.append({"artifact": key, "status": "changed", "old": old, "new": new})
    return {
        "schema_version": "pipeline-diff/0.3",
        "ok": True,
        "summary": {
            "changed": len(changes),
            "unchanged": 3 - len(changes),
        },
        "execution_plan": {
            "distance": {
                "old": plan_a.get("distance") if isinstance(plan_a, dict) else None,
                "new": plan_b.get("distance") if isinstance(plan_b, dict) else None,
            },
            "changed": _stable_json(plan_a) != _stable_json(plan_b),
        },
        "simulation": {
            "old_trace": _trace_labels(sim_a),
            "new_trace": _trace_labels(sim_b),
            "changed": _stable_json(sim_a) != _stable_json(sim_b),
        },
        "knowledge": {
            "added": sorted(know_b - know_a),
            "removed": sorted(know_a - know_b),
            "changed": know_a != know_b,
        },
        "changes": changes,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/examples")
def list_examples() -> list[Example]:
    examples: list[Example] = []
    if not EXAMPLES_DIR.exists():
        return examples
    for rsn_file in sorted(EXAMPLES_DIR.rglob("*.rsn")):
        category = rsn_file.parent.name
        examples.append(
            Example(
                id=rsn_file.stem,
                category=category,
                name=rsn_file.stem.replace("_", " ").title(),
                source=rsn_file.read_text(encoding="utf-8"),
            )
        )
    return examples


@app.post("/api/validate", response_model=ValidateResponse)
def validate(req: SourceRequest) -> ValidateResponse:
    # Parse
    try:
        program = parse(req.source)
    except SurfaceSyntaxError as e:
        return ValidateResponse(
            ok=False,
            phase="Parse",
            errors=[_make_error("Parse", str(e))],
        )
    except Exception as e:
        return ValidateResponse(
            ok=False,
            phase="Parse",
            errors=[_make_error("Parse", str(e))],
        )

    ast_dict = _ast_to_dict(program)

    # Semantic validation
    try:
        project_program(program)
    except (SurfaceValidationError, NamespaceResolutionError) as e:
        return ValidateResponse(
            ok=False,
            phase="Validation",
            errors=[_make_error("Validation", str(e))],
            ast=ast_dict,
        )
    except Exception as e:
        return ValidateResponse(
            ok=False,
            phase="Validation",
            errors=[_make_error("Validation", str(e))],
            ast=ast_dict,
        )

    return ValidateResponse(ok=True, ast=ast_dict)


@app.post("/api/compile", response_model=CompileResponse)
def compile_endpoint(req: SourceRequest) -> CompileResponse:
    # Parse
    try:
        program = parse(req.source)
    except SurfaceSyntaxError as e:
        return CompileResponse(
            ok=False,
            phase="Parse",
            errors=[_make_error("Parse", str(e))],
        )
    except Exception as e:
        return CompileResponse(
            ok=False,
            phase="Parse",
            errors=[_make_error("Parse", str(e))],
        )

    ast_dict = _ast_to_dict(program)

    # Compile → Reason IR
    try:
        reason_irs = list(compile_program(program))
    except (SurfaceValidationError, NamespaceResolutionError) as e:
        return CompileResponse(
            ok=False,
            phase="Compile",
            errors=[_make_error("Compile", str(e))],
            ast=ast_dict,
        )
    except Exception as e:
        return CompileResponse(
            ok=False,
            phase="Compile",
            errors=[_make_error("Compile", str(e))],
            ast=ast_dict,
        )

    return CompileResponse(ok=True, ast=ast_dict, reason_irs=reason_irs)


def _compile_ir(req: SourceRequest) -> tuple[list[Any], dict[str, Any], list[dict[str, Any]]]:
    """Parse + compile; returns (reason_irs, ast_dict, errors). errors=[] means success."""
    try:
        program = parse(req.source)
    except SurfaceSyntaxError as e:
        return [], {}, [_make_error("Parse", str(e))]
    except Exception as e:
        return [], {}, [_make_error("Parse", str(e))]

    ast_dict = _ast_to_dict(program)

    try:
        reason_irs = list(compile_program(program))
    except (SurfaceValidationError, NamespaceResolutionError) as e:
        return [], ast_dict, [_make_error("Compile", str(e))]
    except Exception as e:
        return [], ast_dict, [_make_error("Compile", str(e))]

    return reason_irs, ast_dict, []


@app.post("/api/execution-plan")
def execution_plan_endpoint(req: SourceRequest) -> dict[str, Any]:
    reason_irs, ast_dict, errors = _compile_ir(req)
    if errors:
        return {"ok": False, "errors": errors, "ast": ast_dict}
    plans = [build_execution_plan(ir) for ir in reason_irs]
    result = plans[0] if len(plans) == 1 else {"modules": plans}
    return {"ok": True, "ast": ast_dict, "execution_plan": result, "reason_irs": reason_irs}


@app.post("/api/simulate")
def simulate_endpoint(req: SourceRequest) -> dict[str, Any]:
    reason_irs, ast_dict, errors = _compile_ir(req)
    if errors:
        return {"ok": False, "errors": errors, "ast": ast_dict}
    sims = [simulate(ir) for ir in reason_irs]
    result = sims[0] if len(sims) == 1 else {"modules": sims}
    return {"ok": True, "ast": ast_dict, "simulation": result, "reason_irs": reason_irs}


@app.post("/api/knowledge")
def knowledge_endpoint(req: SourceRequest) -> dict[str, Any]:
    reason_irs, ast_dict, errors = _compile_ir(req)
    if errors:
        return {"ok": False, "errors": errors, "ast": ast_dict}
    all_knowledge: list[dict[str, Any]] = []
    for ir in reason_irs:
        sim = simulate(ir)
        k = extract_knowledge(ir, sim)
        all_knowledge.append(k)
    result = all_knowledge[0] if len(all_knowledge) == 1 else {"modules": all_knowledge}
    return {"ok": True, "ast": ast_dict, "knowledge": result, "reason_irs": reason_irs}


@app.post("/api/pipeline", response_model=PipelineResponse)
def pipeline_endpoint(req: SourceRequest) -> PipelineResponse:
    """Run the full pipeline: parse → compile → execution_plan → simulation → knowledge."""
    artifacts, errors = _run_pipeline_artifacts(req)
    if errors:
        return PipelineResponse(
            ok=False,
            phase="Compile",
            errors=errors,
            ast=artifacts.get("ast"),
            semantic_ast=artifacts.get("semantic_ast"),
            validation=artifacts.get("validation"),
        )
    reason_ir = artifacts.get("reason_ir")
    reason_irs = reason_ir.get("modules", []) if isinstance(reason_ir, dict) and "modules" in reason_ir else [reason_ir]

    return PipelineResponse(
        ok=True,
        ast=artifacts.get("ast"),
        semantic_ast=artifacts.get("semantic_ast"),
        reason_irs=reason_irs,
        execution_plan=artifacts.get("execution_plan"),
        simulation=artifacts.get("simulation"),
        knowledge=artifacts.get("knowledge"),
        validation=artifacts.get("validation"),
    )


@app.post("/api/export")
@app.post("/export")
def export_endpoint(req: SourceRequest) -> dict[str, Any]:
    artifacts, errors = _run_pipeline_artifacts(req)
    if errors:
        return _artifact_response(artifacts, ok=False, errors=errors)
    target = _safe_artifact_dir(EXPORTS_DIR, Path(req.filename).stem)
    if target.exists():
        target = _safe_artifact_dir(EXPORTS_DIR, f"{Path(req.filename).stem}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}")
    _write_artifacts(target, artifacts)
    response = _artifact_response(artifacts)
    response["path"] = str(target)
    response["files"] = ARTIFACT_FILES
    return response


@app.post("/api/import")
@app.post("/import")
def import_endpoint(req: ArtifactPathRequest) -> dict[str, Any]:
    artifacts = _read_artifacts(req.path)
    response = _artifact_response(artifacts)
    response["path"] = artifacts.get("path")
    return response


@app.post("/api/diff")
@app.post("/diff")
def diff_endpoint(req: DiffRequest) -> dict[str, Any]:
    a = _artifact_from_payload(req.a)
    b = _artifact_from_payload(req.b)
    return _diff_artifacts(a, b)


@app.post("/api/run-all")
@app.post("/run-all")
def run_all_endpoint() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    if not REGRESSION_EXAMPLES_DIR.exists():
        return {"ok": False, "pass": 0, "fail": 0, "results": [], "errors": [_make_error("RunAll", "examples directory not found")]}
    for rsn_file in sorted(REGRESSION_EXAMPLES_DIR.rglob("*.rsn")):
        req = SourceRequest(source=rsn_file.read_text(encoding="utf-8"), filename=rsn_file.name)
        artifacts, errors = _run_pipeline_artifacts(req)
        status = "FAIL" if errors else "PASS"
        results.append({
            "file": str(rsn_file.relative_to(REGRESSION_EXAMPLES_DIR)),
            "status": status,
            "errors": errors,
            "validation": artifacts.get("validation"),
        })
    passed = sum(1 for item in results if item["status"] == "PASS")
    failed = len(results) - passed
    return {"ok": failed == 0, "pass": passed, "fail": failed, "results": results}


@app.post("/api/analyze")
def analyze_endpoint(req: SourceRequest) -> dict[str, Any]:
    """Run full pipeline + produce v0.5 analysis artifacts."""
    reason_irs, ast_dict, errors = _compile_ir(req)
    if errors:
        return {"ok": False, "errors": errors, "ast": ast_dict}

    analyses = []
    for ir in reason_irs:
        sim = simulate(ir)
        analyses.append(analyze_ir(ir, sim, compiler_mode=req.compiler_mode))

    analysis = analyses[0] if len(analyses) == 1 else {"modules": analyses}

    # Also run full pipeline for output events
    artifacts, _ = _run_pipeline_artifacts(req)
    reason_ir = artifacts.get("reason_ir") or {}
    runtime_ops = []
    if isinstance(reason_ir, dict):
        runtime_ops = reason_ir.get("metadata", {}).get("runtime_operations", [])

    return {
        "ok": True,
        "ast": ast_dict,
        "semantic_ast": artifacts.get("semantic_ast"),
        "analysis": analysis,
        "runtime_operations": runtime_ops,
        "compiler_mode": req.compiler_mode,
    }


@app.get("/api/language-audit")
def language_audit_endpoint() -> dict[str, Any]:
    return {"ok": True, "matrix": run_language_audit()}


@app.post("/api/language-audit/export")
def language_audit_export_endpoint() -> dict[str, Any]:
    files = write_language_audit_reports(REPO_ROOT)
    return {"ok": True, "files": files, "matrix": run_language_audit()}


@app.post("/api/baseline")
@app.post("/baseline")
def baseline_endpoint(req: SourceRequest) -> dict[str, Any]:
    artifacts, errors = _run_pipeline_artifacts(req)
    if errors:
        return _artifact_response(artifacts, ok=False, errors=errors)
    baseline_artifacts = {
        "execution_plan": artifacts.get("execution_plan"),
        "simulation": artifacts.get("simulation"),
        "knowledge": artifacts.get("knowledge"),
        "validation": artifacts.get("validation"),
        "ast": artifacts.get("ast"),
        "semantic_ast": artifacts.get("semantic_ast"),
        "reason_ir": artifacts.get("reason_ir"),
        "source": artifacts.get("source"),
    }
    target = _safe_artifact_dir(BASELINE_DIR, Path(req.filename).stem)
    _write_artifacts(target, baseline_artifacts)
    response = _artifact_response(baseline_artifacts)
    response["path"] = str(target)
    return response


# ---------------------------------------------------------------------------
# Serve the built React app (production)
# ---------------------------------------------------------------------------

DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str) -> FileResponse:
        index = DIST_DIR / "index.html"
        return FileResponse(str(index))
