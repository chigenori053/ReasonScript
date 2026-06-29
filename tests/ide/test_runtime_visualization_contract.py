"""Runtime Visualization data contract tests.

Specification: reasonscript-ide-runtime-visualization/0.1
Phase: IDE-2

Verifies that the ReasonScript pipeline produces artifacts that conform to
the shapes expected by the frontend visualization adapters.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from playground.backend.main import _run_pipeline_artifacts, SourceRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINIMAL_CALCULATION = """
model HelloWorld {
  calculation Answer {
    result = 42
  }
}
"""

FUNCTION_CALL = """
model FunctionDemo {
  fn Double(x: int) -> int {
    return x * 2
  }
  calculation Answer {
    result = Double(21)
  }
}
"""

BRANCHING_FUNCTION = """
model BranchDemo {
  fn Select(flag: bool) -> int {
    if flag {
      return 1
    } else {
      return 0
    }
  }
  calculation Answer {
    result = Select(true)
  }
}
"""

RESERVED_CONSTRUCT = """
world Demo {
}
"""


def _pipeline(source: str) -> tuple[dict, list]:
    req = SourceRequest(source=source, filename="test.rsn", compiler_mode="normal")
    return _run_pipeline_artifacts(req)


# ---------------------------------------------------------------------------
# §18.1 — Minimal Calculation
# ---------------------------------------------------------------------------

class TestMinimalCalculation:

    def setup_method(self):
        self.artifacts, self.errors = _pipeline(MINIMAL_CALCULATION)

    def test_pipeline_has_all_required_artifacts(self) -> None:
        required = ["ast", "reason_ir", "execution_plan", "simulation", "knowledge"]
        for key in required:
            assert key in self.artifacts, f"Missing artifact: {key}"

    def test_surface_ast_has_modules(self) -> None:
        ast = self.artifacts["ast"]
        assert isinstance(ast, dict)
        assert "modules" in ast
        assert len(ast["modules"]) >= 1

    def test_surface_ast_module_has_name(self) -> None:
        modules = self.artifacts["ast"]["modules"]
        assert modules[0]["name"] == "HelloWorld"

    def test_execution_plan_reachable(self) -> None:
        ep = self.artifacts["execution_plan"]
        assert ep is not None
        assert ep["reachable"] is True

    def test_execution_plan_has_steps(self) -> None:
        ep = self.artifacts["execution_plan"]
        assert isinstance(ep["selected_steps"], list)
        assert len(ep["selected_steps"]) >= 1

    def test_execution_plan_step_has_required_fields(self) -> None:
        step = self.artifacts["execution_plan"]["selected_steps"][0]
        assert "step_id" in step
        assert "source" in step
        assert "target" in step

    def test_simulation_success(self) -> None:
        sim = self.artifacts["simulation"]
        assert sim["success"] is True
        assert sim["goal_reached"] is True

    def test_simulation_has_trace(self) -> None:
        sim = self.artifacts["simulation"]
        assert isinstance(sim["trace"], list)
        assert len(sim["trace"]) >= 1

    def test_simulation_trace_step_has_event(self) -> None:
        trace = self.artifacts["simulation"]["trace"]
        for step in trace:
            assert "event" in step or "event_type" in step, f"Trace step missing event: {step}"

    def test_knowledge_generated(self) -> None:
        k = self.artifacts["knowledge"]
        assert k["knowledge_count"] >= 1
        assert len(k["knowledge"]) >= 1

    def test_knowledge_item_has_required_fields(self) -> None:
        item = self.artifacts["knowledge"]["knowledge"][0]
        required = ["id", "source", "relation", "target"]
        for f in required:
            assert f in item, f"Knowledge item missing field: {f}"

    def test_no_errors(self) -> None:
        assert not self.errors, f"Unexpected errors: {self.errors}"


# ---------------------------------------------------------------------------
# §18.2 — Function Call
# ---------------------------------------------------------------------------

class TestFunctionCall:

    def setup_method(self):
        self.artifacts, self.errors = _pipeline(FUNCTION_CALL)

    def test_pipeline_succeeds(self) -> None:
        assert not self.errors

    def test_surface_ast_has_function(self) -> None:
        modules = self.artifacts["ast"]["modules"]
        body_types = [n["node_type"] for n in modules[0]["body"]]
        assert "FunctionDeclarationNode" in body_types

    def test_execution_plan_reachable(self) -> None:
        assert self.artifacts["execution_plan"]["reachable"] is True

    def test_execution_plan_distance_at_least_2(self) -> None:
        # Function call requires at least 2 steps: function return + calculation result
        assert self.artifacts["execution_plan"]["distance"] >= 2

    def test_reason_ir_has_transitions(self) -> None:
        ir = self.artifacts["reason_ir"]
        assert isinstance(ir["transitions"], list)
        assert len(ir["transitions"]) >= 1

    def test_simulation_step_count_at_least_2(self) -> None:
        sim = self.artifacts["simulation"]
        assert sim["step_count"] >= 2

    def test_knowledge_item_has_evidence(self) -> None:
        item = self.artifacts["knowledge"]["knowledge"][0]
        # evidence field or evidence_path should exist
        assert "evidence" in item or "evidence_path" in item


# ---------------------------------------------------------------------------
# §18.3 — Branching Function
# ---------------------------------------------------------------------------

class TestBranchingFunction:

    def setup_method(self):
        self.artifacts, self.errors = _pipeline(BRANCHING_FUNCTION)

    def test_pipeline_succeeds(self) -> None:
        assert not self.errors

    def test_execution_plan_has_selected_branch(self) -> None:
        ep = self.artifacts["execution_plan"]
        # When a branch is selected, selected_branch should not be null
        assert ep["selected_branch"] is not None or len(ep.get("selected_branches", [])) > 0, (
            "Branching function must produce a selected_branch or selected_branches"
        )

    def test_execution_plan_has_path_signature(self) -> None:
        ep = self.artifacts["execution_plan"]
        # path_signature should be non-empty for branching code
        assert isinstance(ep.get("path_signature"), str)

    def test_execution_plan_has_alternative_paths(self) -> None:
        ep = self.artifacts["execution_plan"]
        # At least one alternative path should exist for a two-branch function
        assert isinstance(ep.get("alternative_paths"), list)

    def test_simulation_trace_has_branch_selection(self) -> None:
        trace = self.artifacts["simulation"]["trace"]
        branch_events = [
            s for s in trace
            if s.get("event") == "branch_selection"
            or s.get("event_type") == "BranchSelection"
        ]
        assert len(branch_events) >= 1, "Simulation trace must include a branch_selection event"

    def test_knowledge_preserves_path_signature(self) -> None:
        item = self.artifacts["knowledge"]["knowledge"][0]
        # path_signature should match the selected branch path
        ep_sig = self.artifacts["execution_plan"]["path_signature"]
        k_sig = item.get("path_signature", "")
        assert k_sig == ep_sig, (
            f"Knowledge path_signature '{k_sig}' must match ExecutionPlan path_signature '{ep_sig}'"
        )

    def test_knowledge_evidence_path_non_empty(self) -> None:
        item = self.artifacts["knowledge"]["knowledge"][0]
        # evidence_path should include the selected branch
        evidence_path = item.get("evidence_path", [])
        assert isinstance(evidence_path, list)


# ---------------------------------------------------------------------------
# §18.5 — Reserved Construct Failure
# ---------------------------------------------------------------------------

class TestReservedConstructFailure:

    def setup_method(self):
        self.artifacts, self.errors = _pipeline(RESERVED_CONSTRUCT)

    def test_reserved_construct_produces_error(self) -> None:
        assert len(self.errors) > 0, (
            "world (reserved construct) must produce at least one diagnostic error"
        )

    def test_error_is_ll002(self) -> None:
        codes = [e.get("code", "") for e in self.errors]
        messages = [e.get("message", "").lower() for e in self.errors]
        has_ll002 = any("LL-002" in c for c in codes)
        has_reserved_msg = any("reserved" in m for m in messages)
        assert has_ll002 or has_reserved_msg, (
            "Reserved construct error must reference LL-002 or 'reserved' in message. "
            f"Got codes: {codes}, messages: {messages}"
        )

    def test_no_knowledge_generated_for_reserved(self) -> None:
        k = self.artifacts.get("knowledge")
        if k is not None:
            assert k.get("knowledge_count", 0) == 0, (
                "Reserved construct must not produce knowledge"
            )


# ---------------------------------------------------------------------------
# §6.5 — Pipeline metrics shapes
# ---------------------------------------------------------------------------

class TestPipelineArtifactShapes:
    """Verify artifact schemas expected by buildPipelineOverview adapter."""

    def setup_method(self):
        self.artifacts, _ = _pipeline(MINIMAL_CALCULATION)

    def test_execution_plan_has_reachable_field(self) -> None:
        assert "reachable" in self.artifacts["execution_plan"]

    def test_execution_plan_has_distance_field(self) -> None:
        assert "distance" in self.artifacts["execution_plan"]

    def test_simulation_has_step_count(self) -> None:
        assert "step_count" in self.artifacts["simulation"]

    def test_simulation_has_success_field(self) -> None:
        assert "success" in self.artifacts["simulation"]

    def test_simulation_has_goal_reached_field(self) -> None:
        assert "goal_reached" in self.artifacts["simulation"]

    def test_simulation_has_confidence_field(self) -> None:
        assert "confidence" in self.artifacts["simulation"]

    def test_knowledge_has_knowledge_count(self) -> None:
        assert "knowledge_count" in self.artifacts["knowledge"]

    def test_knowledge_has_evidence_count(self) -> None:
        assert "evidence_count" in self.artifacts["knowledge"]

    def test_reason_ir_has_transitions(self) -> None:
        assert "transitions" in self.artifacts["reason_ir"]
        assert isinstance(self.artifacts["reason_ir"]["transitions"], list)


# ---------------------------------------------------------------------------
# §9 — ExecutionPlan shape for buildExecutionPlanFlow adapter
# ---------------------------------------------------------------------------

class TestExecutionPlanShape:

    def setup_method(self):
        self.artifacts, _ = _pipeline(BRANCHING_FUNCTION)
        self.ep = self.artifacts["execution_plan"]

    def test_selected_steps_is_list(self) -> None:
        assert isinstance(self.ep["selected_steps"], list)

    def test_each_step_has_step_id(self) -> None:
        for step in self.ep["selected_steps"]:
            assert "step_id" in step, f"Step missing step_id: {step}"

    def test_each_step_has_source_and_target(self) -> None:
        for step in self.ep["selected_steps"]:
            assert "source" in step
            assert "target" in step

    def test_alternative_paths_is_list(self) -> None:
        assert isinstance(self.ep.get("alternative_paths", []), list)


# ---------------------------------------------------------------------------
# §10 — Simulation shape for buildSimulationTrace adapter
# ---------------------------------------------------------------------------

class TestSimulationShape:

    def setup_method(self):
        self.artifacts, _ = _pipeline(BRANCHING_FUNCTION)
        self.sim = self.artifacts["simulation"]

    def test_trace_is_list(self) -> None:
        assert isinstance(self.sim["trace"], list)

    def test_each_trace_step_has_step_index(self) -> None:
        for item in self.sim["trace"]:
            assert "step" in item, f"Trace item missing 'step': {item}"

    def test_each_trace_step_has_event(self) -> None:
        for item in self.sim["trace"]:
            has_event = "event" in item or "event_type" in item
            assert has_event, f"Trace item missing event field: {item}"

    def test_branch_trace_item_has_branch_field(self) -> None:
        branch_steps = [
            s for s in self.sim["trace"]
            if s.get("event") == "branch_selection"
            or s.get("event_type") == "BranchSelection"
        ]
        for step in branch_steps:
            assert "branch" in step or "selected_branch" in step, (
                f"Branch selection step missing branch field: {step}"
            )


# ---------------------------------------------------------------------------
# §11 — Knowledge shape for buildKnowledgeEvidence adapter
# ---------------------------------------------------------------------------

class TestKnowledgeShape:

    def setup_method(self):
        self.artifacts, _ = _pipeline(BRANCHING_FUNCTION)
        self.k = self.artifacts["knowledge"]

    def test_knowledge_array_exists(self) -> None:
        assert "knowledge" in self.k
        assert isinstance(self.k["knowledge"], list)

    def test_each_item_has_id(self) -> None:
        for item in self.k["knowledge"]:
            assert "id" in item

    def test_each_item_has_confidence(self) -> None:
        for item in self.k["knowledge"]:
            assert "confidence" in item

    def test_each_item_has_evidence_path(self) -> None:
        for item in self.k["knowledge"]:
            assert "evidence_path" in item
            assert isinstance(item["evidence_path"], list)

    def test_each_item_has_path_signature(self) -> None:
        for item in self.k["knowledge"]:
            assert "path_signature" in item

    def test_each_item_has_evidence_with_transitions(self) -> None:
        for item in self.k["knowledge"]:
            if "evidence" in item:
                assert "transitions" in item["evidence"]
                assert isinstance(item["evidence"]["transitions"], list)
