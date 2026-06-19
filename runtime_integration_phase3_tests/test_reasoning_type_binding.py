import unittest

from frontend.language_surface import compile_program, parse
from frontend.runtime_integration import (
    RuntimeEngineRegistry,
    RuntimeIntegrationErrorCode,
    RuntimeValue,
    execute_runtime_operations_with_registry,
    runtime_real_registry,
    runtime_value_from_ir_expression,
    runtime_value_to_plain,
)


class RuntimeIntegrationPhase3Tests(unittest.TestCase):
    def test_ri3_001_goal_binding_and_ri3_006_search_request_mapping(self):
        report = execute_runtime_operations_with_registry(
            {
                "metadata": {
                    "runtime_operations": [
                        {
                            "operation": "search",
                            "argument": {
                                "node_type": "IdentifierNode",
                                "name": "DestinationGoal",
                            },
                        }
                    ]
                }
            },
            runtime_real_registry(),
        )

        self.assertEqual(report.diagnostics, ())
        self.assertEqual(
            runtime_value_to_plain(report.results[0].language_value)["some"]["goal"],
            "DestinationGoal",
        )

    def test_ri3_002_state_binding_and_ri3_008_prediction_request_mapping(self):
        report = execute_runtime_operations_with_registry(
            {
                "metadata": {
                    "runtime_operations": [
                        {
                            "operation": "predict",
                            "argument": {
                                "node_type": "IdentifierNode",
                                "name": "CurrentState",
                            },
                        }
                    ]
                }
            },
            runtime_real_registry(),
        )

        self.assertEqual(report.diagnostics, ())
        self.assertIn("predicted_state", runtime_value_to_plain(report.results[0].language_value)["some"])

    def test_ri3_003_constraint_binding_and_ri3_009_planning_mapping(self):
        report = execute_runtime_operations_with_registry(
            {
                "metadata": {
                    "runtime_operations": [
                        {
                            "operation": "plan",
                            "argument": {
                                "node_type": "IdentifierNode",
                                "name": "MaxCostConstraint",
                            },
                        }
                    ]
                }
            },
            runtime_real_registry(),
        )

        self.assertEqual(report.diagnostics, ())
        self.assertEqual(report.results[0].execution_plan["schema_version"], "execution-plan/0.1")

    def test_ri3_004_reason_graph_binding(self):
        graph = RuntimeValue.reason_graph({"nodes": ["Dog"], "edges": []})
        self.assertEqual(runtime_value_to_plain(graph), {"nodes": ["Dog"], "edges": []})

        report = execute_runtime_operations_with_registry(
            {
                "metadata": {
                    "runtime_operations": [
                        {"operation": "search", "argument": {"nodes": ["Dog"], "edges": []}}
                    ]
                }
            },
            runtime_real_registry(),
        )
        self.assertEqual(report.diagnostics, ())

    def test_ri3_005_execution_plan_binding_and_ri3_007_abi(self):
        plan = {
            "schema_version": "execution-plan/0.1",
            "selected_steps": [],
            "alternative_paths": [],
            "expected_cost": 0,
            "evidence_refs": [],
            "planner_version": "test",
        }
        value = RuntimeValue.execution_plan(plan)
        self.assertEqual(runtime_value_to_plain(value)["schema_version"], "execution-plan/0.1")

        report = execute_runtime_operations_with_registry(
            {
                "metadata": {
                    "runtime_operations": [
                        {"operation": "simulate", "argument": plan}
                    ]
                }
            },
            runtime_real_registry(),
        )
        self.assertEqual(report.diagnostics, ())

    def test_ri3_010_runtime_value_conversion_preserves_identity(self):
        goal = runtime_value_from_ir_expression(
            {"node_type": "StructLiteralNode", "type_name": "Goal", "fields": [
                {
                    "node_type": "StructLiteralFieldNode",
                    "name": "name",
                    "expression": {"node_type": "StringLiteralNode", "value": "Destination"},
                }
            ]}
        )
        self.assertEqual(goal, RuntimeValue.goal("Destination"))

    def test_ri3_011_trace_and_ri3_012_diagnostics_preservation(self):
        report = execute_runtime_operations_with_registry(
            {
                "metadata": {
                    "runtime_operations": [
                        {"operation": "search", "argument": "GoalA"}
                    ]
                }
            },
            RuntimeEngineRegistry(backend="RuntimeReal"),
        )
        self.assertIn(RuntimeIntegrationErrorCode.RUNTIME_ENGINE_MISSING, report.diagnostics)

        good = execute_runtime_operations_with_registry(
            {
                "metadata": {
                    "runtime_operations": [
                        {
                            "operation": "search",
                            "argument": {"node_type": "IdentifierNode", "name": "GoalA"},
                        }
                    ]
                }
            },
            runtime_real_registry(),
        )
        self.assertTrue(good.results[0].trace)

    def test_ri3_013_metadata_generation(self):
        program = parse(
            """
            package world
            module app {
                fn run(goal, plan, state) {
                    let found = runtime.search(goal)
                    let simulation = runtime.simulate(plan)
                    let prediction = runtime.predict(state)
                    return found
                }
            }
            """
        )
        metadata = compile_program(program)[0]["metadata"]

        self.assertEqual(
            metadata["reasoning_types"],
            ["goal", "execution_plan", "state"],
        )

    def test_ri3_014_and_ri3_015_end_to_end_goal_and_simulation(self):
        program = parse(
            """
            package world
            module app {
                fn run(goal, plan) {
                    let found = runtime.search(goal)
                    let simulation = runtime.simulate(plan)
                    return found
                }
            }
            """
        )
        report = execute_runtime_operations_with_registry(
            compile_program(program)[0], runtime_real_registry()
        )

        self.assertEqual(report.diagnostics, ())
        self.assertEqual(report.results[0].operation, "search")
        self.assertEqual(report.results[1].operation, "simulate")

    def test_reasoning_type_conversion_failure(self):
        report = execute_runtime_operations_with_registry(
            {
                "metadata": {
                    "runtime_operations": [
                        {"operation": "predict", "argument": "not-a-state"}
                    ]
                }
            },
            runtime_real_registry(),
        )

        self.assertTrue(
            any(
                item.startswith(RuntimeIntegrationErrorCode.REASONING_TYPE_CONVERSION_FAILED)
                for item in report.diagnostics
            )
        )


if __name__ == "__main__":
    unittest.main()
