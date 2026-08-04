from __future__ import annotations

import copy
import json
from pathlib import Path

from playground.backend.main import SourceRequest, analyze_endpoint
from playground.backend.reasoning_overview import (
    CONTRACT_SCHEMA,
    build_reasoning_overview_view_model,
    serialize_reasoning_overview_view_model,
)

ROOT = Path(__file__).resolve().parents[2]

SOURCE = """
module ReasoningOverviewSample {
  fn Select(flag: bool) -> int {
    if flag {
      return 1
    }

    return 0
  }

  calculation Answer {
    result = Select(true)
  }
}
"""


def _response(source: str = SOURCE) -> dict:
    return analyze_endpoint(SourceRequest(source=source, filename="reasoning_overview.rsn", compiler_mode="normal"))


def _runtime() -> dict:
    return _response()["reasoning_runtime"]


def test_ro_t001_valid_runtime_result_produces_complete_view_model() -> None:
    vm = build_reasoning_overview_view_model(_runtime())
    assert vm["schemaVersion"] == CONTRACT_SCHEMA
    assert vm["runtimeStatus"]["status"] == "passed"
    assert vm["modelSummary"]["modelId"] == "ReasoningOverviewSample.ReasoningModel"
    assert vm["reasoningPath"]["paths"][0]["steps"]
    assert vm["evaluationReport"]["checks"]


def test_ro_t002_missing_reasoning_model_produces_unavailable_model_summary() -> None:
    runtime = _runtime()
    runtime["reasoning_model"] = {}
    vm = build_reasoning_overview_view_model(runtime)
    assert vm["runtimeStatus"]["hasReasoningModel"] is False
    assert vm["modelSummary"]["available"] is False
    assert vm["modelSummary"]["modelId"] == "ReasoningModel unavailable"


def test_ro_t003_missing_evaluation_report_produces_unavailable_evaluation_report() -> None:
    runtime = _runtime()
    runtime["evaluation_report"] = {}
    vm = build_reasoning_overview_view_model(runtime)
    assert vm["runtimeStatus"]["hasEvaluationReport"] is False
    assert vm["evaluationReport"]["available"] is False
    assert vm["evaluationReport"]["reportId"] == "EvaluationReport unavailable"


def test_ro_t004_failed_evaluation_report_produces_failed_status() -> None:
    runtime = _runtime()
    runtime["evaluation_report"]["summary"]["status"] = "failed"
    runtime["evaluation_report"]["summary"]["passed"] = False
    runtime["evaluation_report"]["summary"]["failed_checks"] = 1
    vm = build_reasoning_overview_view_model(runtime)
    assert vm["evaluationReport"]["status"] == "failed"
    assert vm["evaluationReport"]["passed"] is False
    assert vm["evaluationReport"]["failedChecks"] == 1


def test_ro_t005_diagnostics_are_grouped_by_source() -> None:
    runtime = _runtime()
    runtime["diagnostics"] = [{"code": "RRP-X", "severity": "warning", "message": "runtime"}]
    runtime["reasoning_model"]["diagnostics"] = [{"code": "RM-X", "severity": "error", "message": "model"}]
    runtime["evaluation_report"]["diagnostics"] = [{"code": "ER-X", "severity": "info", "message": "report"}]
    vm = build_reasoning_overview_view_model(runtime)
    sources = {item["source"] for item in vm["diagnostics"]["items"]}
    assert {"runtime", "reasoning_model", "evaluation_report"} <= sources


def test_ro_t006_diagnostics_are_sorted_deterministically() -> None:
    runtime = _runtime()
    runtime["diagnostics"] = [
        {"code": "RRP-W", "severity": "warning", "message": "warning"},
        {"code": "RRP-F", "severity": "fatal", "message": "fatal"},
        {"code": "RRP-E", "severity": "error", "message": "error"},
    ]
    vm = build_reasoning_overview_view_model(runtime)
    assert [item["severity"] for item in vm["diagnostics"]["items"][:3]] == ["fatal", "error", "warning"]


def test_ro_t007_raw_artifacts_are_preserved() -> None:
    runtime = _runtime()
    vm = build_reasoning_overview_view_model(runtime)
    assert vm["rawArtifacts"]["runtimeResult"]["run_id"] == runtime["run_id"]
    assert vm["rawArtifacts"]["reasoningModel"]["model_id"] == runtime["reasoning_model"]["model_id"]
    assert vm["rawArtifacts"]["evaluationReport"]["report_id"] == runtime["evaluation_report"]["report_id"]


def test_ro_t008_view_model_serialization_is_deterministic() -> None:
    runtime = _runtime()
    first = serialize_reasoning_overview_view_model(build_reasoning_overview_view_model(runtime))
    second = serialize_reasoning_overview_view_model(build_reasoning_overview_view_model(copy.deepcopy(runtime)))
    assert first == second
    assert json.loads(first)["schemaVersion"] == CONTRACT_SCHEMA


def test_ro_t101_analyze_endpoint_includes_reasoning_runtime_when_pipeline_succeeds() -> None:
    response = _response()
    assert response["ok"] is True
    assert response["reasoning_runtime"]["schema_version"] == "reasonscript-reasoning-runtime-prototype/1.0"


def test_ro_t102_analyze_endpoint_includes_reasoning_model_when_generated() -> None:
    response = _response()
    assert response["reasoning_model"]["schema_version"] == "reasonscript-reasoning-model/1.0"


def test_ro_t103_analyze_endpoint_includes_reasoning_evaluation_report_when_generated() -> None:
    response = _response()
    assert response["reasoning_evaluation_report"]["schema_version"] == "reasonscript-reasoning-evaluation-report/1.0"


def test_ro_t104_analyze_endpoint_includes_reasoning_overview_view_model() -> None:
    response = _response()
    assert response["reasoning_overview"]["schemaVersion"] == CONTRACT_SCHEMA


def test_ro_t105_invalid_source_returns_structured_reasoning_diagnostics() -> None:
    response = _response("module Invalid { calculation Answer { result = } }")
    assert response["ok"] is False
    assert response["reasoning_runtime"]["pipeline_status"]["status"] == "fatal"
    assert response["reasoning_overview"]["diagnostics"]["fatal"] >= 1


def test_ro_t106_existing_analyze_response_fields_remain_compatible() -> None:
    response = _response()
    for key in ("ok", "pipeline", "artifacts", "views", "diagnostics", "ast", "semantic_ast", "execution_plan", "simulation", "knowledge"):
        assert key in response


def test_ro_t201_frontend_reasoning_overview_wiring_exists() -> None:
    app = (ROOT / "apps" / "reasonscript-ide" / "ui" / "src" / "App.tsx").read_text(encoding="utf-8")
    standard_layout = (ROOT / "apps" / "reasonscript-ide" / "ui" / "src" / "views" / "StandardLayoutViews.tsx").read_text(encoding="utf-8")
    view = (ROOT / "apps" / "reasonscript-ide" / "ui" / "src" / "views" / "ReasoningOverviewView.tsx").read_text(encoding="utf-8")
    bridge = (ROOT / "apps" / "reasonscript-ide" / "ui" / "src" / "bridge.ts").read_text(encoding="utf-8")
    assert "reasoningOverviewVm" in app
    assert "ReasoningOverviewView" in standard_layout
    assert 'label: "Reasoning"' in standard_layout
    assert "Runtime Result JSON" in view
    assert "ReasoningModel JSON" in view
    assert "EvaluationReport JSON" in view
    assert "ViewModel JSON" in view
    assert "reasoning_overview" in bridge
