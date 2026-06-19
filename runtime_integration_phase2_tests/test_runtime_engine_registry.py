import unittest

from frontend.language_surface import compile_program, parse
from frontend.runtime_integration import (
    RuntimeEngineRegistry,
    RuntimeIntegrationErrorCode,
    RuntimeResult,
    RuntimeValue,
    execute_runtime_operations,
    execute_runtime_operations_with_registry,
    hybrid_runtime_registry,
    runtime_real_registry,
    runtime_value_to_plain,
)


class RuntimeIntegrationPhase2Tests(unittest.TestCase):
    def reason_ir(self):
        program = parse(
            """
            package world
            module app {
                fn run(goal) {
                    let found = runtime.search(goal)
                    let simulation = runtime.simulate(goal)
                    let prediction = runtime.predict(goal)
                    let plan = runtime.plan(goal)
                    return found
                }
            }
            """
        )
        return compile_program(program)[0]

    def test_ri2_001_through_ri2_004_engine_bindings(self):
        report = execute_runtime_operations_with_registry(
            self.reason_ir(), runtime_real_registry()
        )

        self.assertEqual(
            [entry["operation"] for entry in report.metadata["runtime_execution"]],
            ["search", "simulate", "predict", "plan"],
        )
        self.assertEqual(
            [entry["engine"] for entry in report.metadata["runtime_execution"]],
            [
                "RuntimeReal SearchEngine",
                "RuntimeReal SemanticSimulationEngine",
                "RuntimeReal PredictionEngine",
                "RuntimeReal PlanningEngine",
            ],
        )

    def test_ri2_005_runtime_real_backend_execution(self):
        report = execute_runtime_operations(self.reason_ir(), runtime_real_registry())

        self.assertEqual(report.metadata["runtime_execution"][0]["backend"], "RuntimeReal")
        self.assertEqual(
            runtime_value_to_plain(report.results[0].language_value)["some"]["found"],
            True,
        )

    def test_ri2_006_hybrid_runtime_backend_execution(self):
        report = execute_runtime_operations(self.reason_ir(), hybrid_runtime_registry())

        self.assertEqual(report.metadata["runtime_execution"][0]["backend"], "HybridRuntime")
        self.assertEqual(report.metadata["runtime_execution"][3]["operation"], "plan")

    def test_ri2_007_request_mapping_and_ri2_008_result_mapping(self):
        report = execute_runtime_operations_with_registry(
            self.reason_ir(), runtime_real_registry()
        )

        search = runtime_value_to_plain(report.results[0].language_value)
        plan = runtime_value_to_plain(report.results[3].language_value)
        self.assertEqual(search["some"]["goal"], "goal")
        self.assertEqual(plan["some"]["steps"], ["step-1"])

    def test_ri2_009_trace_and_ri2_010_diagnostics_preservation(self):
        class DiagnosticSearchEngine:
            engine_name = "RuntimeReal SearchEngine"

            def search(self, request):
                from frontend.runtime_integration import SearchResult

                return SearchResult(
                    RuntimeValue.string("ok"),
                    ("trace-a", "trace-b"),
                    diagnostics=("GoalNotFound",),
                )

        registry = RuntimeEngineRegistry(
            search_engine=DiagnosticSearchEngine(),
            backend="RuntimeReal",
        )
        reason_ir = {
            "metadata": {
                "runtime_operations": [
                    {"operation": "search", "argument": "GoalA"}
                ]
            }
        }
        report = execute_runtime_operations_with_registry(reason_ir, registry)

        self.assertEqual(report.results[0].trace, ("trace-a", "trace-b"))
        self.assertIn("GoalNotFound", report.results[0].diagnostics)

    def test_ri2_011_execution_plan_compatibility(self):
        report = execute_runtime_operations_with_registry(
            self.reason_ir(), runtime_real_registry()
        )
        planning = report.results[3].execution_plan

        self.assertEqual(planning["schema_version"], "execution-plan/0.1")
        self.assertIsInstance(planning["selected_steps"], list)
        self.assertIn("expected_cost", planning)

    def test_ri2_012_end_to_end_runtime_execution_is_deterministic(self):
        first = execute_runtime_operations_with_registry(
            self.reason_ir(), runtime_real_registry()
        )
        second = execute_runtime_operations_with_registry(
            self.reason_ir(), runtime_real_registry()
        )

        self.assertEqual(first.metadata, second.metadata)
        self.assertEqual(
            [runtime_value_to_plain(result.language_value) for result in first.results],
            [runtime_value_to_plain(result.language_value) for result in second.results],
        )

    def test_registry_validation_errors(self):
        missing = execute_runtime_operations_with_registry(
            {
                "metadata": {
                    "runtime_operations": [{"operation": "search", "argument": "GoalA"}]
                }
            },
            RuntimeEngineRegistry(backend="RuntimeReal"),
        )
        self.assertIn(
            RuntimeIntegrationErrorCode.RUNTIME_ENGINE_MISSING,
            missing.diagnostics,
        )

        class BadPlanEngine:
            engine_name = "RuntimeReal PlanningEngine"

            def plan(self, request):
                from frontend.runtime_integration import PlanningResult

                return PlanningResult(
                    RuntimeValue.string("bad"),
                    ("plan:start",),
                    {"schema_version": "invalid", "selected_steps": [], "expected_cost": 0},
                )

        incompatible = execute_runtime_operations_with_registry(
            {
                "metadata": {
                    "runtime_operations": [{"operation": "plan", "argument": "GoalA"}]
                }
            },
            RuntimeEngineRegistry(planning_engine=BadPlanEngine(), backend="RuntimeReal"),
        )
        self.assertTrue(
            any(
                item.startswith(RuntimeIntegrationErrorCode.EXECUTION_PLAN_INCOMPATIBLE)
                for item in incompatible.diagnostics
            )
        )

        class NoTraceEngine:
            engine_name = "RuntimeReal SearchEngine"

            def search(self, request):
                from frontend.runtime_integration import SearchResult

                return SearchResult(RuntimeValue.string("ok"))

        trace_missing = execute_runtime_operations_with_registry(
            {
                "metadata": {
                    "runtime_operations": [{"operation": "search", "argument": "GoalA"}]
                }
            },
            RuntimeEngineRegistry(search_engine=NoTraceEngine(), backend="RuntimeReal"),
        )
        self.assertIn(RuntimeIntegrationErrorCode.TRACE_MISSING, trace_missing.diagnostics)


if __name__ == "__main__":
    unittest.main()
