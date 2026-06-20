"""Agent Layer Phase 1 Conformance Tests - AG1-001 through AG1-020."""

from __future__ import annotations

import unittest

from frontend.lsp import ReasonScriptLanguageServer
from frontend.runtime_integration import PLATFORM_DIAGNOSTIC_SCHEMA
from sdk import agent, planning, reason_graph, world


class AgentLayerPhase1Tests(unittest.TestCase):
    def _goal(self):
        return planning.create_goal("goal-1", "ReachDestination", "ReachDestination", priority=10)

    def _agent(self):
        return agent.create_agent(
            "agent-1",
            "NavigationAgent",
            capabilities=("Planning", "Simulation", "Search", "Prediction"),
        )

    def _context(self, constraints=()):
        graph = reason_graph.create_graph("route")
        graph = reason_graph.add_state(graph, "runtime")
        graph = reason_graph.add_state(graph, "ReachDestination")
        graph = reason_graph.add_transition(graph, "runtime", "ReachDestination")
        scene = world.add_entity(world.create_scene("room"), world.create_entity("agent"))
        model = world.add_scene(world.create_world("agent-world"), scene)
        return agent.create_context(
            self._goal(),
            world=model,
            reason_graph=graph,
            constraints=constraints,
            metadata={"initial_state": "runtime"},
        )

    def _task(self, constraints=()):
        return agent.create_task(
            "task-1",
            "Reach the destination",
            self._goal(),
            priority=10,
            constraints=constraints,
        )

    def test_ag1_001_agent_creation(self):
        value = self._agent()

        self.assertEqual(value.to_dict()["schema"], "agent-layer-agent/0.1")
        self.assertIn("Planning", value.capabilities)

    def test_ag1_002_task_creation(self):
        task = self._task()

        self.assertEqual(task.to_dict()["schema"], "agent-layer-task/0.1")
        self.assertEqual(task.goal.id, "goal-1")

    def test_ag1_003_agent_context_creation(self):
        context = self._context()

        self.assertEqual(context.goal.id, "goal-1")
        self.assertIsNotNone(context.world)
        self.assertIsNotNone(context.reason_graph)

    def test_ag1_004_decision_generation(self):
        decision, plan_result, diagnostics = agent.decide(self._agent(), self._task(), self._context())

        self.assertEqual(diagnostics, ())
        self.assertEqual(plan_result.status, "Success")
        self.assertEqual(decision.id, "decision-task-1")

    def test_ag1_005_planning_integration(self):
        result = agent.plan(self._agent(), self._task(), self._context())

        self.assertEqual(result.status, "Success")
        self.assertEqual(result.selected_plan.metadata["source"], "runtime.plan")

    def test_ag1_006_plan_selection(self):
        decision, _, _ = agent.decide(self._agent(), self._task(), self._context())

        self.assertIsNotNone(decision.selected_plan)
        self.assertEqual(decision.selected_plan.id, "plan-goal-1-1")

    def test_ag1_007_action_generation(self):
        decision, _, _ = agent.decide(self._agent(), self._task(), self._context())
        actions = agent.act(decision)

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0].target, "ReachDestination")

    def test_ag1_008_action_execution(self):
        result = agent.execute(self._agent(), self._task(), self._context())

        self.assertEqual(result.status, "Success")
        self.assertEqual(result.execution_results[0]["status"], "completed")

    def test_ag1_009_agent_result_creation(self):
        encoded = agent.execute(self._agent(), self._task(), self._context()).to_dict()

        self.assertEqual(encoded["schema"], "agent-layer-result/0.1")
        self.assertEqual(encoded["decision"]["id"], "decision-task-1")

    def test_ag1_010_capability_validation(self):
        invalid = agent.create_agent("bad", "BadAgent", capabilities=("Learning",))
        diagnostics = agent.validate_agent(invalid)

        self.assertTrue(any(item.code == "InvalidCapability" for item in diagnostics))

    def test_ag1_011_tool_registration(self):
        tool = agent.create_tool("tool-1", "RuntimePlanner", "Planning")
        registered = agent.register_tool(self._agent(), tool)

        self.assertEqual(registered.tools[0].name, "RuntimePlanner")

    def test_ag1_012_constraint_validation(self):
        constraint = planning.create_constraint("c1", "MaximumSteps", 0)
        result = agent.execute(self._agent(), self._task((constraint,)), self._context())

        self.assertEqual(result.status, "Failure")
        self.assertTrue(any(item.code == "ConstraintViolation" for item in result.diagnostics))

    def test_ag1_013_world_model_integration(self):
        context = self._context()

        self.assertEqual(context.world.tick, 0)
        self.assertEqual(agent.execute(self._agent(), self._task(), context).status, "Success")

    def test_ag1_014_reason_graph_integration(self):
        context = self._context()

        self.assertEqual(context.reason_graph.edges[0]["from"], "runtime")
        self.assertEqual(agent.execute(self._agent(), self._task(), context).plan.steps[0].source, "runtime")

    def test_ag1_015_execution_plan_conversion(self):
        result = agent.execute(self._agent(), self._task(), self._context())
        execution_plan = planning.to_execution_plan(result.plan)

        self.assertEqual(execution_plan["schema_version"], "execution-plan/0.1")
        self.assertEqual(execution_plan["selected_steps"][0]["target"], "ReachDestination")

    def test_ag1_016_reasoning_trace_integration(self):
        result = agent.execute(self._agent(), self._task(), self._context())
        categories = [event.category for event in result.reasoning_trace.events]

        self.assertIn("Task", categories)
        self.assertIn("Decision", categories)
        self.assertIn("Action", categories)
        self.assertIn("Agent", categories)

    def test_ag1_017_platform_diagnostic_integration(self):
        bad_task = agent.create_task("", "", planning.create_goal("", "", ""))
        result = agent.execute(self._agent(), bad_task, self._context())

        self.assertEqual(result.status, "Failure")
        self.assertEqual(result.diagnostics[0].to_dict()["schema"], PLATFORM_DIAGNOSTIC_SCHEMA)

    def test_ag1_018_deterministic_execution(self):
        first = agent.execute(self._agent(), self._task(), self._context()).to_dict()
        second = agent.execute(self._agent(), self._task(), self._context()).to_dict()

        self.assertEqual(first, second)

    def test_ag1_019_failure_handling(self):
        invalid = agent.create_agent("agent-1", "NoPlanner", capabilities=("Search",))
        result = agent.execute(invalid, self._task(), self._context())

        self.assertEqual(result.status, "Failure")
        self.assertTrue(any(item.code == "DecisionFailure" for item in result.diagnostics))

    def test_ag1_020_end_to_end_agent_execution(self):
        result = agent.execute(self._agent(), self._task(), self._context())
        server = ReasonScriptLanguageServer()
        completions = server.completion("file:///agent.rsn", 0, 0)

        self.assertEqual(result.status, "Success")
        self.assertEqual(agent.status(result), "Success")
        self.assertEqual(agent.decision(result).id, "decision-task-1")
        self.assertEqual(agent.actions(result)[0].target, "ReachDestination")
        self.assertIn("Agent", [item.label for item in completions])


if __name__ == "__main__":
    unittest.main()
