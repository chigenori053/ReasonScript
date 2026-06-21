"""ReasonScript Playground IDE — FastAPI backend."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import Any

# Ensure the repo root is on the path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from frontend.language_surface.parser import parse, SurfaceSyntaxError
from frontend.language_surface.integration import compile_program, project_program
from frontend.language_surface.validation import SurfaceValidationError
from frontend.language_surface.namespace import NamespaceResolutionError
from playground.backend.engine import build_execution_plan, simulate, extract_knowledge

EXAMPLES_DIR = REPO_ROOT / "TestPlayground" / "examples"

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
    reason_irs: list[dict[str, Any]] = []
    execution_plan: dict[str, Any] | None = None
    simulation: dict[str, Any] | None = None
    knowledge: dict[str, Any] | None = None


class Example(BaseModel):
    id: str
    category: str
    name: str
    source: str


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
    reason_irs, ast_dict, errors = _compile_ir(req)
    if errors:
        return PipelineResponse(ok=False, phase="Compile", errors=errors, ast=ast_dict)

    plans = [build_execution_plan(ir) for ir in reason_irs]
    sims = [simulate(ir) for ir in reason_irs]
    knowledges = [extract_knowledge(ir, sim) for ir, sim in zip(reason_irs, sims)]

    return PipelineResponse(
        ok=True,
        ast=ast_dict,
        reason_irs=reason_irs,
        execution_plan=plans[0] if len(plans) == 1 else {"modules": plans},
        simulation=sims[0] if len(sims) == 1 else {"modules": sims},
        knowledge=knowledges[0] if len(knowledges) == 1 else {"modules": knowledges},
    )


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
