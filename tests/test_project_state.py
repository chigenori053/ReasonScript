"""Tests for ProjectState schema and pipeline integration (Phase 5.0)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from playground.backend.main import _run_pipeline_artifacts, SourceRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_project_state(source: str, filename: str = "test.rsn", compiler_mode: str = "normal") -> dict:
    """Run pipeline and normalise output to a ProjectState-shaped dict."""
    req = SourceRequest(source=source, filename=filename, compiler_mode=compiler_mode)
    artifacts, errors = _run_pipeline_artifacts(req)

    reason_ir = artifacts.get("reason_ir")
    if isinstance(reason_ir, dict) and "modules" in reason_ir:
        reason_irs = reason_ir["modules"]
    else:
        reason_irs = [reason_ir] if reason_ir else []

    diagnostics = [
        {
            "severity": "error",
            "message": e.get("message", ""),
            "phase": e.get("phase", "parse"),
            "span": {"start_line": e["line"] - 1} if e.get("line") else None,
        }
        for e in errors
    ]

    return {
        "schema_version": "project-state/0.1",
        "compiler_version": "0.1.0",
        "source_files": [{"uri": filename, "text": source, "language_id": "reasonscript"}],
        "surface_ast": artifacts.get("ast"),
        "semantic_ast": artifacts.get("semantic_ast"),
        "reason_ir": artifacts.get("reason_ir"),
        "execution_plan": artifacts.get("execution_plan"),
        "diagnostics": diagnostics,
        "validation": artifacts.get("validation"),
        "simulation": artifacts.get("simulation"),
        "knowledge": artifacts.get("knowledge"),
        "metadata": {"compiler_mode": compiler_mode, "source_filename": filename},
    }


# ---------------------------------------------------------------------------
# Schema version tests
# ---------------------------------------------------------------------------

def test_project_state_schema_version():
    source = "module M { object A }"
    ps = build_project_state(source)
    assert ps["schema_version"] == "project-state/0.1"
    assert ps["compiler_version"] == "0.1.0"


def test_project_state_has_required_fields():
    source = "module M { object A }"
    ps = build_project_state(source)
    required = [
        "schema_version", "compiler_version", "source_files",
        "surface_ast", "semantic_ast", "reason_ir", "execution_plan",
        "diagnostics", "validation", "simulation", "knowledge", "metadata",
    ]
    for field in required:
        assert field in ps, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Basic module (golden)
# ---------------------------------------------------------------------------

def test_project_state_basic_module():
    source = """module HelloWorld {
  object Start
  object Goal
  transition Move {
    Start -> Goal
  }
}"""
    ps = build_project_state(source, "basic_module.rsn")
    assert ps["diagnostics"] == [], f"Unexpected errors: {ps['diagnostics']}"
    assert ps["surface_ast"] is not None
    assert ps["reason_ir"] is not None
    assert ps["execution_plan"] is not None
    assert ps["validation"]["ok"] is True


def test_project_state_basic_module_has_simulation():
    source = """module HelloWorld {
  object Start
  object Goal
  transition Move {
    Start -> Goal
  }
}"""
    ps = build_project_state(source)
    assert ps["simulation"] is not None


def test_project_state_basic_module_has_knowledge():
    source = """module HelloWorld {
  object Start
  object Goal
  transition Move {
    Start -> Goal
  }
}"""
    ps = build_project_state(source)
    assert ps["knowledge"] is not None


# ---------------------------------------------------------------------------
# Error diagnostics
# ---------------------------------------------------------------------------

def test_project_state_parse_error_produces_diagnostic():
    source = "module { broken syntax @@@ }"
    ps = build_project_state(source, "error.rsn")
    assert len(ps["diagnostics"]) > 0
    d = ps["diagnostics"][0]
    assert d["severity"] == "error"
    assert d["phase"] in ("parse", "semantic", "compile", "validation", "Compile", "Parse")
    assert ps["validation"]["ok"] is False


def test_project_state_diagnostic_has_message():
    source = "module { broken @@@ }"
    ps = build_project_state(source)
    for d in ps["diagnostics"]:
        assert "message" in d
        assert isinstance(d["message"], str)
        assert len(d["message"]) > 0


# ---------------------------------------------------------------------------
# Diagnostics schema stability
# ---------------------------------------------------------------------------

def test_diagnostic_schema_stable():
    source = "module { @@@ broken }"
    ps = build_project_state(source)
    for d in ps["diagnostics"]:
        assert "severity" in d
        assert "message" in d
        assert "phase" in d


def test_source_span_schema_stable():
    source = "module { @@@ broken }"
    ps = build_project_state(source)
    for d in ps["diagnostics"]:
        if d.get("span"):
            span = d["span"]
            assert "start_line" in span


# ---------------------------------------------------------------------------
# Serialisability
# ---------------------------------------------------------------------------

def test_project_state_is_json_serialisable():
    source = """module HelloWorld {
  object Start
  object Goal
  transition Move {
    Start -> Goal
  }
}"""
    ps = build_project_state(source)
    dumped = json.dumps(ps)
    back = json.loads(dumped)
    assert back["schema_version"] == "project-state/0.1"


# ---------------------------------------------------------------------------
# Reason IR and ExecutionPlan present
# ---------------------------------------------------------------------------

def test_reason_ir_and_execution_plan_included():
    source = """module HelloWorld {
  object Start
  object Goal
  transition Move {
    Start -> Goal
  }
}"""
    ps = build_project_state(source)
    assert ps["reason_ir"] is not None, "reason_ir must be present"
    assert ps["execution_plan"] is not None, "execution_plan must be present"
