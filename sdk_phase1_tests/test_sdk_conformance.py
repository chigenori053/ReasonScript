"""SDK Phase 1 Conformance Tests — SDK1-001 through SDK1-015."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from frontend.runtime_integration import (
    RuntimeValue,
    runtime_real_registry,
    hybrid_runtime_registry,
)
from sdk.runtime.search import search_goal
from sdk.runtime.simulation import simulate_plan
from sdk.runtime.prediction import predict_state
from sdk.runtime.planning import plan_goal
from sdk import reason_graph as rg
from sdk import execution_plan as ep
from sdk.metadata import build_sdk_metadata, inject_sdk_usage, extract_sdk_usage


class SDK1001RuntimeSearchSDK(unittest.TestCase):
    """SDK1-001: Runtime Search SDK."""

    def test_search_goal_returns_result(self):
        result = search_goal("my_goal")
        self.assertIsNotNone(result)

    def test_search_goal_found_true(self):
        result = search_goal("my_goal")
        self.assertTrue(result.found)

    def test_search_goal_has_trace(self):
        result = search_goal("my_goal")
        self.assertIsInstance(result.trace, tuple)

    def test_search_goal_preserves_goal_name(self):
        result = search_goal("navigation_goal")
        self.assertEqual(result.goal, "navigation_goal")

    def test_search_goal_accepts_runtime_value(self):
        v = RuntimeValue.goal("typed_goal")
        result = search_goal(v)
        self.assertIsNotNone(result)

    def test_search_goal_with_explicit_registry(self):
        reg = runtime_real_registry()
        result = search_goal("my_goal", registry=reg)
        self.assertIsNotNone(result)


class SDK1002RuntimeSimulationSDK(unittest.TestCase):
    """SDK1-002: Runtime Simulation SDK."""

    def _make_plan(self) -> dict:
        return {
            "schema_version": "execution-plan/0.1",
            "selected_steps": [
                {"step_id": "s1", "transition_id": "a->b", "source": "a", "target": "b"}
            ],
            "alternative_paths": [],
            "expected_cost": 1.0,
            "evidence_refs": [],
            "planner_version": "test/0.1",
        }

    def test_simulate_plan_returns_result(self):
        result = simulate_plan(self._make_plan())
        self.assertIsNotNone(result)

    def test_simulate_plan_has_trace(self):
        result = simulate_plan(self._make_plan())
        self.assertIsInstance(result.trace, tuple)

    def test_simulate_plan_accepts_runtime_value(self):
        v = RuntimeValue.execution_plan(self._make_plan())
        result = simulate_plan(v)
        self.assertIsNotNone(result)

    def test_simulate_plan_with_explicit_registry(self):
        reg = runtime_real_registry()
        result = simulate_plan(self._make_plan(), registry=reg)
        self.assertIsNotNone(result)


class SDK1003RuntimePredictionSDK(unittest.TestCase):
    """SDK1-003: Runtime Prediction SDK."""

    def test_predict_state_returns_result(self):
        result = predict_state("start_state")
        self.assertIsNotNone(result)

    def test_predict_state_has_trace(self):
        result = predict_state("start_state")
        self.assertIsInstance(result.trace, tuple)

    def test_predict_state_preserves_name(self):
        result = predict_state("my_state")
        self.assertEqual(result.state, "my_state")

    def test_predict_state_accepts_runtime_value(self):
        v = RuntimeValue.state("typed_state")
        result = predict_state(v)
        self.assertIsNotNone(result)

    def test_predict_state_with_explicit_registry(self):
        reg = runtime_real_registry()
        result = predict_state("start_state", registry=reg)
        self.assertIsNotNone(result)


class SDK1004RuntimePlanningSDK(unittest.TestCase):
    """SDK1-004: Runtime Planning SDK."""

    def test_plan_goal_returns_result(self):
        result = plan_goal("navigation_goal")
        self.assertIsNotNone(result)

    def test_plan_goal_planned_true(self):
        result = plan_goal("navigation_goal")
        self.assertTrue(result.planned)

    def test_plan_goal_has_trace(self):
        result = plan_goal("navigation_goal")
        self.assertIsInstance(result.trace, tuple)

    def test_plan_goal_preserves_goal_name(self):
        result = plan_goal("my_goal")
        self.assertEqual(result.goal, "my_goal")

    def test_plan_goal_with_explicit_registry(self):
        reg = runtime_real_registry()
        result = plan_goal("navigation_goal", registry=reg)
        self.assertIsNotNone(result)


class SDK1005ReasonGraphBuilder(unittest.TestCase):
    """SDK1-005: ReasonGraph Builder."""

    def test_create_graph(self):
        g = rg.create_graph("test_graph")
        self.assertIsNotNone(g)
        self.assertEqual(g.name, "test_graph")

    def test_add_state(self):
        g = rg.create_graph("g")
        g2 = rg.add_state(g, "state_a")
        self.assertIn("state_a", [n.get("id") for n in g2.nodes])

    def test_add_state_does_not_mutate_original(self):
        g = rg.create_graph("g")
        rg.add_state(g, "state_a")
        self.assertEqual(len(g.nodes), 0)

    def test_add_transition(self):
        g = rg.create_graph("g")
        g = rg.add_state(g, "a")
        g = rg.add_state(g, "b")
        g = rg.add_transition(g, "a", "b")
        self.assertEqual(len(g.edges), 1)

    def test_add_transition_does_not_mutate_original(self):
        g = rg.create_graph("g")
        g = rg.add_state(g, "a")
        g = rg.add_state(g, "b")
        before_edges = g.edges
        rg.add_transition(g, "a", "b")
        self.assertEqual(g.edges, before_edges)

    def test_to_dict_has_nodes_and_edges(self):
        g = rg.create_graph("g")
        g = rg.add_state(g, "a")
        g = rg.add_state(g, "b")
        g = rg.add_transition(g, "a", "b")
        d = g.to_dict()
        self.assertIn("nodes", d)
        self.assertIn("edges", d)

    def test_duplicate_state_ignored(self):
        g = rg.create_graph("g")
        g = rg.add_state(g, "a")
        g = rg.add_state(g, "a")
        self.assertEqual(len(g.nodes), 1)

    def test_duplicate_transition_ignored(self):
        g = rg.create_graph("g")
        g = rg.add_state(g, "a")
        g = rg.add_state(g, "b")
        g = rg.add_transition(g, "a", "b")
        g = rg.add_transition(g, "a", "b")
        self.assertEqual(len(g.edges), 1)


class SDK1006ReasonGraphValidation(unittest.TestCase):
    """SDK1-006: ReasonGraph Validation."""

    def _valid_graph(self):
        g = rg.create_graph("g")
        g = rg.add_state(g, "a")
        g = rg.add_state(g, "b")
        return rg.add_transition(g, "a", "b")

    def test_valid_graph_passes(self):
        self.assertTrue(rg.validate(self._valid_graph()))

    def test_empty_graph_passes(self):
        g = rg.create_graph("g")
        self.assertTrue(rg.validate(g))

    def test_transition_to_nonexistent_state_fails(self):
        from sdk.reason_graph.builder import ReasonGraph
        g = ReasonGraph(
            name="bad",
            nodes=({"id": "a"},),
            edges=({"from": "a", "to": "z"},),
        )
        self.assertFalse(rg.validate(g))

    def test_deterministic(self):
        g = self._valid_graph()
        r1 = rg.validate(g)
        r2 = rg.validate(g)
        self.assertEqual(r1, r2)


class SDK1007ReasonGraphQuery(unittest.TestCase):
    """SDK1-007: ReasonGraph Query."""

    def _graph(self):
        g = rg.create_graph("g")
        g = rg.add_state(g, "a")
        g = rg.add_state(g, "b")
        return rg.add_transition(g, "a", "b")

    def test_states_returns_list(self):
        g = self._graph()
        self.assertEqual(rg.states(g), ["a", "b"])

    def test_transitions_returns_list(self):
        g = self._graph()
        self.assertIn("a -> b", rg.transitions(g))

    def test_states_does_not_mutate(self):
        g = self._graph()
        nodes_before = g.nodes
        rg.states(g)
        self.assertEqual(g.nodes, nodes_before)

    def test_transitions_does_not_mutate(self):
        g = self._graph()
        edges_before = g.edges
        rg.transitions(g)
        self.assertEqual(g.edges, edges_before)


class SDK1008ExecutionPlanBuilder(unittest.TestCase):
    """SDK1-008: ExecutionPlan Builder."""

    def test_create_plan(self):
        p = ep.create_plan("my_plan")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "my_plan")

    def test_add_step(self):
        p = ep.create_plan("p")
        p = ep.add_step(p, "start", "end")
        self.assertEqual(ep.length(p), 1)

    def test_add_step_does_not_mutate_original(self):
        p = ep.create_plan("p")
        ep.add_step(p, "start", "end")
        self.assertEqual(ep.length(p), 0)

    def test_to_dict_has_schema_version(self):
        p = ep.create_plan("p")
        d = p.to_dict()
        self.assertEqual(d["schema_version"], "execution-plan/0.1")

    def test_to_dict_has_expected_cost(self):
        p = ep.create_plan("p")
        p = ep.add_step(p, "a", "b")
        d = p.to_dict()
        self.assertIn("expected_cost", d)

    def test_expected_cost_accumulates(self):
        p = ep.create_plan("p")
        p = ep.add_step(p, "a", "b", step_cost=2.0)
        p = ep.add_step(p, "b", "c", step_cost=3.0)
        self.assertAlmostEqual(p.expected_cost, 5.0)


class SDK1009ExecutionPlanValidation(unittest.TestCase):
    """SDK1-009: ExecutionPlan Validation."""

    def _valid_plan(self):
        p = ep.create_plan("p")
        p = ep.add_step(p, "a", "b")
        return ep.add_step(p, "b", "c")

    def test_valid_plan_passes(self):
        self.assertTrue(ep.validate(self._valid_plan()))

    def test_valid_plan_dict_passes(self):
        self.assertTrue(ep.validate(self._valid_plan().to_dict()))

    def test_empty_plan_passes(self):
        p = ep.create_plan("p")
        self.assertTrue(ep.validate(p))

    def test_wrong_schema_version_fails(self):
        d = self._valid_plan().to_dict()
        d["schema_version"] = "wrong/0.0"
        self.assertFalse(ep.validate(d))

    def test_discontinuous_steps_fail(self):
        d = self._valid_plan().to_dict()
        # Break continuity
        d["selected_steps"][0]["target"] = "z"
        self.assertFalse(ep.validate(d))

    def test_deterministic(self):
        p = self._valid_plan()
        r1 = ep.validate(p)
        r2 = ep.validate(p)
        self.assertEqual(r1, r2)


class SDK1010ExecutionPlanQuery(unittest.TestCase):
    """SDK1-010: ExecutionPlan Query."""

    def _plan(self):
        p = ep.create_plan("p")
        p = ep.add_step(p, "a", "b")
        return ep.add_step(p, "b", "c")

    def test_steps_returns_list(self):
        self.assertIsInstance(ep.steps(self._plan()), list)

    def test_steps_count(self):
        self.assertEqual(len(ep.steps(self._plan())), 2)

    def test_length(self):
        self.assertEqual(ep.length(self._plan()), 2)

    def test_steps_does_not_mutate(self):
        p = self._plan()
        before = p.selected_steps
        ep.steps(p)
        self.assertEqual(p.selected_steps, before)

    def test_length_does_not_mutate(self):
        p = self._plan()
        before = p.selected_steps
        ep.length(p)
        self.assertEqual(p.selected_steps, before)


class SDK1011SDKMetadataGeneration(unittest.TestCase):
    """SDK1-011: SDK Metadata Generation."""

    def test_build_sdk_metadata(self):
        meta = build_sdk_metadata(["runtime.search", "reason_graph.builder"])
        self.assertEqual(meta["sdk_usage"], ["runtime.search", "reason_graph.builder"])

    def test_inject_sdk_usage(self):
        meta = {"package": "hello"}
        result = inject_sdk_usage(meta, ["runtime.search"])
        self.assertIn("runtime.search", result["sdk_usage"])
        self.assertEqual(result["package"], "hello")

    def test_inject_deduplicates(self):
        meta = inject_sdk_usage({}, ["runtime.search"])
        result = inject_sdk_usage(meta, ["runtime.search"])
        self.assertEqual(result["sdk_usage"].count("runtime.search"), 1)

    def test_extract_sdk_usage(self):
        ir = {"metadata": {"sdk_usage": ["runtime.search"]}}
        self.assertEqual(extract_sdk_usage(ir), ["runtime.search"])

    def test_extract_sdk_usage_empty(self):
        self.assertEqual(extract_sdk_usage({}), [])


class SDK1012RuntimeCompatibility(unittest.TestCase):
    """SDK1-012: Runtime Compatibility — RuntimeReal and HybridRuntime."""

    def test_search_with_real_backend(self):
        r = search_goal("goal", registry="RuntimeReal")
        self.assertIsNotNone(r)

    def test_search_with_hybrid_backend(self):
        r = search_goal("goal", registry="HybridRuntime")
        self.assertIsNotNone(r)

    def test_plan_with_real_backend(self):
        r = plan_goal("goal", registry="RuntimeReal")
        self.assertIsNotNone(r)

    def test_plan_with_hybrid_backend(self):
        r = plan_goal("goal", registry="HybridRuntime")
        self.assertIsNotNone(r)

    def test_execution_plan_abi_compliance(self):
        p = ep.create_plan("p")
        p = ep.add_step(p, "a", "b")
        d = p.to_dict()
        self.assertEqual(d["schema_version"], "execution-plan/0.1")
        self.assertIsInstance(d["selected_steps"], list)
        self.assertIn("expected_cost", d)

    def test_reason_graph_runtime_value_wrapping(self):
        g = rg.create_graph("g")
        g = rg.add_state(g, "a")
        g = rg.add_state(g, "b")
        g = rg.add_transition(g, "a", "b")
        v = RuntimeValue.reason_graph(g.to_dict())
        self.assertEqual(v.kind, "ReasonGraphValue")


class SDK1013EndToEndSearchWorkflow(unittest.TestCase):
    """SDK1-013: End-to-End Search Workflow."""

    def test_search_workflow(self):
        # Build graph → validate → search
        g = rg.create_graph("navigation")
        g = rg.add_state(g, "start")
        g = rg.add_state(g, "end")
        g = rg.add_transition(g, "start", "end")
        self.assertTrue(rg.validate(g))

        result = search_goal("navigation_goal")
        self.assertIsNotNone(result)
        self.assertTrue(result.found)
        self.assertIsInstance(result.trace, tuple)

    def test_search_is_deterministic(self):
        r1 = search_goal("goal_x")
        r2 = search_goal("goal_x")
        self.assertEqual(r1.found, r2.found)
        self.assertEqual(r1.cost, r2.cost)
        self.assertEqual(r1.confidence, r2.confidence)


class SDK1014EndToEndPlanningWorkflow(unittest.TestCase):
    """SDK1-014: End-to-End Planning Workflow."""

    def test_planning_workflow(self):
        # Build plan → validate → run
        p = ep.create_plan("route")
        p = ep.add_step(p, "start", "mid")
        p = ep.add_step(p, "mid", "end")
        self.assertTrue(ep.validate(p))
        self.assertEqual(ep.length(p), 2)

        result = plan_goal("route_goal")
        self.assertIsNotNone(result)
        self.assertTrue(result.planned)

    def test_planning_is_deterministic(self):
        r1 = plan_goal("goal_y")
        r2 = plan_goal("goal_y")
        self.assertEqual(r1.planned, r2.planned)
        self.assertEqual(r1.cost, r2.cost)


class SDK1015EndToEndSimulationWorkflow(unittest.TestCase):
    """SDK1-015: End-to-End Simulation Workflow."""

    def test_simulation_workflow(self):
        p = ep.create_plan("sim_route")
        p = ep.add_step(p, "a", "b")
        p = ep.add_step(p, "b", "c")
        self.assertTrue(ep.validate(p))

        result = simulate_plan(p.to_dict())
        self.assertIsNotNone(result)
        self.assertIsInstance(result.trace, tuple)

    def test_simulation_is_deterministic(self):
        p = ep.create_plan("p")
        p = ep.add_step(p, "x", "y")
        d = p.to_dict()
        r1 = simulate_plan(d)
        r2 = simulate_plan(d)
        self.assertEqual(r1.cost, r2.cost)
        self.assertEqual(r1.confidence, r2.confidence)


if __name__ == "__main__":
    unittest.main()
