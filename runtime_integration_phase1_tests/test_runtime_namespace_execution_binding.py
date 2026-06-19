import unittest

from frontend.language_surface import compile_program, parse
from frontend.runtime_integration import (
    RuntimeIntegrationErrorCode,
    RuntimeResult,
    RuntimeValue,
    execute_runtime_operations,
    runtime_value_to_plain,
)


class DeterministicRuntimeExecutor:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls = []

    def search(self, request):
        self.calls.append(("search", request))
        if self.fail:
            return RuntimeResult(False, None, ("search failed",))
        return RuntimeResult(
            True,
            RuntimeValue.struct(
                {
                    "goal": RuntimeValue.string(request.value),
                    "found": RuntimeValue.bool(True),
                    "cost": RuntimeValue.float(1.0),
                    "confidence": RuntimeValue.float(0.95),
                    "trace": RuntimeValue.array([RuntimeValue.string("search")]),
                }
            ),
        )

    def simulate(self, request):
        self.calls.append(("simulate", request))
        return RuntimeResult(
            True,
            RuntimeValue.struct(
                {
                    "success": RuntimeValue.bool(True),
                    "final_state": RuntimeValue.string("simulated"),
                    "confidence": RuntimeValue.float(0.9),
                    "trace": RuntimeValue.array([RuntimeValue.string("simulate")]),
                }
            ),
        )

    def predict(self, request):
        self.calls.append(("predict", request))
        return RuntimeResult(
            True,
            RuntimeValue.struct(
                {
                    "predicted_state": RuntimeValue.string("predicted"),
                    "confidence": RuntimeValue.float(0.8),
                    "evidence": RuntimeValue.array([RuntimeValue.string("evidence")]),
                }
            ),
        )

    def plan(self, request):
        self.calls.append(("plan", request))
        return RuntimeResult(
            True,
            RuntimeValue.struct(
                {
                    "goal": RuntimeValue.string(request.value),
                    "success": RuntimeValue.bool(True),
                    "cost": RuntimeValue.float(2.0),
                    "steps": RuntimeValue.array([RuntimeValue.string("step-1")]),
                }
            ),
        )


class RuntimeIntegrationPhase1Tests(unittest.TestCase):
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

    def test_ri_001_through_ri_004_runtime_operation_bindings(self):
        executor = DeterministicRuntimeExecutor()
        report = execute_runtime_operations(self.reason_ir(), executor)

        self.assertEqual(
            [call[0] for call in executor.calls],
            ["search", "simulate", "predict", "plan"],
        )
        self.assertEqual(
            [result.operation for result in report.results],
            ["search", "simulate", "predict", "plan"],
        )
        self.assertEqual(report.diagnostics, ())

    def test_ri_005_optional_result_mapping(self):
        report = execute_runtime_operations(self.reason_ir(), DeterministicRuntimeExecutor())
        first = report.results[0].language_value

        self.assertEqual(first.kind, "Optional")
        self.assertIsNotNone(first.value)
        self.assertEqual(runtime_value_to_plain(first)["some"]["found"], True)

    def test_ri_006_runtime_failure_maps_to_none_with_diagnostics(self):
        report = execute_runtime_operations(
            self.reason_ir(), DeterministicRuntimeExecutor(fail=True)
        )
        search = report.results[0]

        self.assertEqual(search.language_value.kind, "Optional")
        self.assertIsNone(search.language_value.value)
        self.assertIn(
            RuntimeIntegrationErrorCode.RUNTIME_EXECUTION_FAILED,
            search.diagnostics,
        )

    def test_ri_007_runtime_value_conversion(self):
        operation = {
            "metadata": {
                "runtime_operations": [
                    {
                        "operation": "search",
                        "argument": {
                            "node_type": "StringLiteralNode",
                            "value": "GoalA",
                        },
                    }
                ]
            }
        }
        executor = DeterministicRuntimeExecutor()
        execute_runtime_operations(operation, executor)

        self.assertEqual(executor.calls[0][1], RuntimeValue.goal("GoalA"))

    def test_ri_008_runtime_metadata_generation(self):
        operations = self.reason_ir()["metadata"]["runtime_operations"]

        self.assertEqual(
            [operation["operation"] for operation in operations],
            ["search", "simulate", "predict", "plan"],
        )
        self.assertEqual(operations[0]["argument"]["node_type"], "IdentifierNode")

    def test_ri_009_deterministic_re_execution(self):
        first = execute_runtime_operations(
            self.reason_ir(), DeterministicRuntimeExecutor()
        )
        second = execute_runtime_operations(
            self.reason_ir(), DeterministicRuntimeExecutor()
        )

        self.assertEqual(
            [runtime_value_to_plain(result.language_value) for result in first.results],
            [runtime_value_to_plain(result.language_value) for result in second.results],
        )

    def test_ri_010_end_to_end_language_to_runtime(self):
        report = execute_runtime_operations(self.reason_ir(), DeterministicRuntimeExecutor())

        self.assertEqual(
            report.metadata["runtime_operations_executed"],
            ["search", "simulate", "predict", "plan"],
        )
        self.assertEqual(runtime_value_to_plain(report.results[3].language_value)["some"]["steps"], ["step-1"])

    def test_runtime_integration_error_paths(self):
        unknown = {
            "metadata": {
                "runtime_operations": [{"operation": "unknown", "argument": "x"}]
            }
        }
        missing = {
            "metadata": {
                "runtime_operations": [{"operation": "search", "argument": "x"}]
            }
        }
        bad_argument = {
            "metadata": {
                "runtime_operations": [{"operation": "search"}]
            }
        }
        bad_result_executor = DeterministicRuntimeExecutor()
        bad_result_executor.search = lambda request: RuntimeResult(
            True, RuntimeValue("Unsupported", object())
        )

        self.assertIn(
            RuntimeIntegrationErrorCode.UNKNOWN_RUNTIME_OPERATION,
            execute_runtime_operations(unknown, DeterministicRuntimeExecutor()).diagnostics,
        )
        self.assertIn(
            RuntimeIntegrationErrorCode.RUNTIME_BINDING_MISSING,
            execute_runtime_operations(missing, None).diagnostics,
        )
        self.assertTrue(
            execute_runtime_operations(
                bad_argument, DeterministicRuntimeExecutor()
            ).diagnostics[0].startswith(
                RuntimeIntegrationErrorCode.ARGUMENT_CONVERSION_FAILED
            )
        )
        self.assertTrue(
            execute_runtime_operations(
                missing, bad_result_executor
            ).diagnostics[0].startswith(
                RuntimeIntegrationErrorCode.RESULT_CONVERSION_FAILED
            )
        )


if __name__ == "__main__":
    unittest.main()
