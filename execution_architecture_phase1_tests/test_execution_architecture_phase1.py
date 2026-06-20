import unittest

from frontend.runtime_integration import (
    CallFrame,
    CallFrameStatus,
    CallStack,
    EXECUTION_ARCHITECTURE_SCHEMA,
    ExecutionCoordinator,
    ExecutionFailureType,
    ExecutionRequest,
    ExecutionResult,
    RuntimeEngineRegistry,
    RuntimeValue,
    SearchResult,
    StackOverflow,
    runtime_real_registry,
    runtime_value_to_plain,
)


def valid_plan():
    return {
        "schema_version": "execution-plan/0.1",
        "selected_steps": [
            {
                "step_id": "step-1",
                "transition_id": "t1",
                "source": "A",
                "target": "B",
            }
        ],
        "alternative_paths": [],
        "expected_cost": 1.0,
        "evidence_refs": [],
        "planner_version": "ea1-test/0.1",
    }


def reason_ir():
    return {
        "schema_version": "reason-ir/0.1",
        "metadata": {
            "runtime_operations": [
                {"operation": "search", "argument": "DestinationGoal"},
                {"operation": "simulate", "argument": "RoutePlan"},
                {"operation": "predict", "argument": "StartState"},
                {"operation": "plan", "argument": "DestinationGoal"},
            ]
        },
    }


class ExecutionArchitecturePhase1Tests(unittest.TestCase):
    def request(self, registry=None):
        return ExecutionRequest(
            "request-ea1",
            source_module="ea1",
            reason_ir=reason_ir(),
            execution_plan=valid_plan(),
            runtime_registry=registry or runtime_real_registry(),
            metadata={
                "entry_function": "run",
                "parameters": ("goal",),
                "arguments": (RuntimeValue.goal("Destination"),),
                "return_target": "found",
            },
        )

    def test_ea1_001_execution_request_creation(self):
        request = self.request()
        encoded = request.to_dict()

        self.assertEqual(encoded["schema"], EXECUTION_ARCHITECTURE_SCHEMA)
        self.assertEqual(encoded["request_id"], "request-ea1")
        self.assertEqual(encoded["runtime_registry"]["backend"], "RuntimeReal")

    def test_ea1_002_execution_result_creation(self):
        result = ExecutionResult("request-ea1", "completed")

        self.assertEqual(result.to_dict()["schema"], EXECUTION_ARCHITECTURE_SCHEMA)
        self.assertEqual(result.to_dict()["status"], "completed")

    def test_ea1_003_coordinator_validation(self):
        coordinator = ExecutionCoordinator(runtime_real_registry())
        bad_request = ExecutionRequest(
            "request-ea1",
            reason_ir=reason_ir(),
            execution_plan={"schema_version": "invalid", "selected_steps": [], "expected_cost": 0},
            runtime_registry=runtime_real_registry(),
        )
        result = coordinator.execute(bad_request)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure.failure_type, ExecutionFailureType.VALIDATION_FAILED)
        self.assertTrue(any("invalid ExecutionPlan" in item for item in result.diagnostics))

    def test_ea1_004_context_freeze(self):
        result = ExecutionCoordinator(runtime_real_registry()).execute(self.request())

        self.assertIn(
            "context_frozen",
            [event["event_type"] for event in result.trace],
        )

    def test_ea1_005_and_ea1_006_call_frame_creation_and_parameter_binding(self):
        frame = CallFrame.create(
            "frame-add",
            "add",
            ("a", "b"),
            (RuntimeValue.int(1), RuntimeValue.int(2)),
        )

        self.assertEqual(frame.status, CallFrameStatus.ACTIVE)
        self.assertEqual(runtime_value_to_plain(frame.parameter_bindings["a"]), 1)
        self.assertEqual(runtime_value_to_plain(frame.parameter_bindings["b"]), 2)

    def test_ea1_007_return_handling(self):
        frame = CallFrame.create("frame-add", "add").returning(RuntimeValue.int(3)).completed()

        self.assertEqual(frame.status, CallFrameStatus.COMPLETED)
        self.assertEqual(runtime_value_to_plain(frame.return_value), 3)

    def test_ea1_008_nested_calls(self):
        stack = CallStack(max_depth=8)
        for name in ("a", "b", "c"):
            stack = stack.push(CallFrame.create(f"frame-{name}", name))

        self.assertEqual([frame.function_name for frame in stack.frames], ["a", "b", "c"])
        self.assertEqual(stack.current().function_name, "c")

    def test_ea1_009_recursive_calls(self):
        stack = CallStack(max_depth=8)
        for index in range(3):
            stack = stack.push(
                CallFrame.create(f"frame-fib-{index}", "fib", ("n",), (RuntimeValue.int(index),))
            )

        self.assertEqual(stack.depth(), 3)
        self.assertEqual([frame.function_name for frame in stack.frames], ["fib", "fib", "fib"])

    def test_ea1_010_through_ea1_013_call_stack_operations(self):
        stack = CallStack(max_depth=4)
        self.assertTrue(stack.is_empty())

        stack = stack.push(CallFrame.create("frame-a", "a"))
        stack = stack.push(CallFrame.create("frame-b", "b"))
        self.assertEqual(stack.depth(), 2)
        self.assertEqual(stack.current().function_name, "b")

        stack, popped = stack.pop()
        self.assertEqual(popped.function_name, "b")
        self.assertEqual(stack.current().function_name, "a")

    def test_ea1_014_stack_overflow(self):
        stack = CallStack(max_depth=1)
        stack = stack.push(CallFrame.create("frame-a", "a"))

        with self.assertRaises(StackOverflow):
            stack.push(CallFrame.create("frame-b", "b"))

    def test_ea1_015_runtime_dispatch(self):
        result = ExecutionCoordinator(runtime_real_registry()).execute(self.request())

        self.assertEqual(
            [item.operation for item in result.runtime_results],
            ["search", "simulate", "predict", "plan"],
        )

    def test_ea1_016_runtime_failure_handling(self):
        class DiagnosticSearchEngine:
            engine_name = "RuntimeReal SearchEngine"

            def search(self, request):
                return SearchResult(
                    RuntimeValue.string("not-found"),
                    ("search:start", "search:failed"),
                    diagnostics=("GoalNotFound",),
                )

        registry = RuntimeEngineRegistry(
            search_engine=DiagnosticSearchEngine(),
            simulation_engine=runtime_real_registry().simulation_engine,
            prediction_engine=runtime_real_registry().prediction_engine,
            planning_engine=runtime_real_registry().planning_engine,
            backend="RuntimeReal",
        )
        result = ExecutionCoordinator(registry).execute(self.request(registry))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure.failure_type, ExecutionFailureType.RUNTIME_FAILURE)
        self.assertIn("GoalNotFound", result.diagnostics)

    def test_ea1_017_trace_collection(self):
        result = ExecutionCoordinator(runtime_real_registry()).execute(self.request())
        event_types = [event["event_type"] for event in result.trace]

        self.assertIn("runtime_call", event_types)
        self.assertIn("result_assembled", event_types)

    def test_ea1_018_result_assembly(self):
        result = ExecutionCoordinator(runtime_real_registry()).execute(self.request())

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.final_result["runtime_operation_count"], 4)

    def test_ea1_019_runtime_compatibility(self):
        result = ExecutionCoordinator(runtime_real_registry()).execute(self.request())

        self.assertEqual(result.final_result["metadata"]["runtime_execution"][0]["backend"], "RuntimeReal")

    def test_ea1_020_end_to_end_execution(self):
        result = ExecutionCoordinator(runtime_real_registry()).execute(self.request())
        encoded = result.to_dict()

        self.assertEqual(encoded["schema"], EXECUTION_ARCHITECTURE_SCHEMA)
        self.assertEqual(encoded["status"], "completed")
        self.assertTrue(encoded["call_stack_trace"])
        self.assertEqual(encoded["runtime_results"][0]["language_value"]["some"]["found"], True)


if __name__ == "__main__":
    unittest.main()
