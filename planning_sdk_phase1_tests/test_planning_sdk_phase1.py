"""Planning SDK Phase 1 Conformance Tests - PS1-001 through PS1-020."""

from __future__ import annotations

import unittest

from frontend.lsp import ReasonScriptLanguageServer
from frontend.runtime_integration import PLATFORM_DIAGNOSTIC_SCHEMA, TraceEvent
from sdk import planning, reason_graph, world


class PlanningSDKPhase1Tests(unittest.TestCase):
    def _goal(self):
        return planning.create_goal("goal-1", "ReachDestination", "ReachDestination", priority=10)

    def _context(self, constraints=()):
        graph = reason_graph.create_graph("route")
        graph = reason_graph.add_state(graph, "runtime")
        graph = reason_graph.add_state(graph, "ReachDestination")
        graph = reason_graph.add_transition(graph, "runtime", "ReachDestination")
        scene = world.add_entity(world.create_scene("room"), world.create_entity("agent"))
        model = world.add_scene(world.create_world("planning-world"), scene)
        return planning.create_context(
            world=model,
            reason_graph=graph,
            constraints=constraints,
            metadata={"initial_state": "runtime"},
        )

    def test_ps1_001_goal_creation(self):
        goal = self._goal()

        self.assertEqual(goal.to_dict()["schema"], "planning-sdk-goal/0.1")
        self.assertEqual(goal.name, "ReachDestination")

    def test_ps1_002_planning_context_creation(self):
        context = self._context()

        self.assertIn("world", context.to_dict())
        self.assertIn("reason_graph", context.to_dict())

    def test_ps1_003_constraint_creation(self):
        constraint = planning.create_constraint("c1", "MaximumSteps", 3)

        self.assertEqual(constraint.constraint_type, "MaximumSteps")
        self.assertEqual(constraint.expression, 3)

    def test_ps1_004_planner_initialization(self):
        planner = planning.Planner()

        self.assertIsNotNone(planner.registry.planning_engine)

    def test_ps1_005_plan_generation(self):
        result = planning.plan(self._goal(), self._context())

        self.assertEqual(result.status, "Success")
        self.assertIsNotNone(result.selected_plan)

    def test_ps1_006_candidate_plans(self):
        result = planning.plan(self._goal(), self._context())

        self.assertEqual(len(result.candidate_plans), 1)
        self.assertEqual(result.candidate_plans[0].goal.id, "goal-1")

    def test_ps1_007_plan_evaluation(self):
        result = planning.plan(self._goal(), self._context())
        score = planning.evaluate_plan(result.selected_plan, self._context())

        self.assertEqual(score.goal_satisfaction, 1.0)
        self.assertEqual(score.cost, 1.0)

    def test_ps1_008_plan_selection(self):
        goal = self._goal()
        good = planning.Plan("p1", goal, (planning.PlanStep("s1", "runtime", "ReachDestination", "Move"),), 1.0, 1.0)
        costly = planning.Plan("p2", goal, (planning.PlanStep("s1", "runtime", "ReachDestination", "Move"),), 5.0, 1.0)

        self.assertEqual(planning.Planner().select((costly, good), self._context()).id, "p1")

    def test_ps1_009_plan_result_creation(self):
        result = planning.plan(self._goal(), self._context())
        encoded = result.to_dict()

        self.assertEqual(encoded["schema"], "planning-sdk-result/0.1")
        self.assertEqual(encoded["selected_plan"]["schema"], "planning-sdk-plan/0.1")

    def test_ps1_010_plan_validation(self):
        result = planning.plan(self._goal(), self._context())

        self.assertEqual(planning.validate_plan(result.selected_plan), ())

    def test_ps1_011_constraint_validation(self):
        constraint = planning.create_constraint("c1", "MaximumSteps", 0)
        result = planning.plan(self._goal(), self._context((constraint,)))

        self.assertEqual(result.status, "Failure")
        self.assertTrue(result.diagnostics)

    def test_ps1_012_goal_satisfaction(self):
        result = planning.plan(self._goal(), self._context())

        self.assertTrue(planning.goal_satisfied(result.selected_plan))

    def test_ps1_013_cost_calculation(self):
        result = planning.plan(self._goal(), self._context())

        self.assertEqual(planning.cost(result.selected_plan), 1.0)

    def test_ps1_014_confidence_calculation(self):
        result = planning.plan(self._goal(), self._context())

        self.assertEqual(planning.confidence(result.selected_plan), 1.0)

    def test_ps1_015_runtime_integration(self):
        result = planning.plan(self._goal(), self._context())

        self.assertEqual(result.selected_plan.metadata["source"], "runtime.plan")
        self.assertIn("plan:start", result.selected_plan.metadata["runtime_trace"])

    def test_ps1_016_world_model_integration(self):
        context = self._context()

        self.assertEqual(context.world.tick, 0)
        self.assertEqual(planning.plan(self._goal(), context).status, "Success")

    def test_ps1_017_reason_graph_integration(self):
        context = self._context()

        self.assertEqual(context.reason_graph.edges[0]["from"], "runtime")
        self.assertEqual(planning.plan(self._goal(), context).selected_plan.steps[0].source, "runtime")

    def test_ps1_018_reasoning_trace_integration(self):
        result = planning.plan(self._goal(), self._context())
        categories = [event.category for event in result.reasoning_trace.events]

        self.assertIn("Planning", categories)
        self.assertIn("PlanEvaluation", categories)
        self.assertIn("PlanSelection", categories)

    def test_ps1_019_platform_diagnostic_integration(self):
        goal = planning.create_goal("", "", "")
        result = planning.plan(goal, self._context())

        self.assertEqual(result.status, "Failure")
        self.assertEqual(result.diagnostics[0].to_dict()["schema"], PLATFORM_DIAGNOSTIC_SCHEMA)

    def test_ps1_020_end_to_end_planning(self):
        result = planning.plan(self._goal(), self._context())
        execution_plan = planning.to_execution_plan(result.selected_plan)
        server = ReasonScriptLanguageServer()
        completions = server.completion("file:///planning.rsn", 0, 0)

        self.assertEqual(result.status, "Success")
        self.assertEqual(execution_plan["schema_version"], "execution-plan/0.1")
        self.assertIn("Plan", [item.label for item in completions])


if __name__ == "__main__":
    unittest.main()
