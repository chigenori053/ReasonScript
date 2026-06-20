import unittest

from frontend.lsp.model import Diagnostic, DiagnosticSeverity as LspSeverity, Location, point_range
from frontend.runtime_integration import (
    DiagnosticSeverity,
    DiagnosticSource,
    ExecutionCoordinator,
    ExecutionRequest,
    ExecutionScope,
    ExecutionScopeStack,
    PLATFORM_DIAGNOSTIC_SCHEMA,
    PlatformDiagnostic,
    REASONING_TRACE_SCHEMA,
    RuntimeValue,
    ScopeType,
    TraceCategory,
    aggregate_platform_diagnostics,
    normalize_trace_events,
    platform_diagnostic_from_compiler,
    platform_diagnostic_from_ide,
    platform_diagnostic_from_lsp,
    platform_diagnostic_from_runtime,
    reasoning_trace_from_world_reconstruction,
    reasoning_trace_from_world_simulation,
    runtime_real_registry,
)
from sdk import world


def valid_plan():
    return {
        "schema_version": "execution-plan/0.1",
        "selected_steps": [{"step_id": "s1", "transition_id": "t1", "source": "A", "target": "B"}],
        "alternative_paths": [],
        "expected_cost": 1.0,
        "evidence_refs": [],
        "planner_version": "ea2-test/0.1",
    }


def reason_ir():
    return {
        "schema_version": "reason-ir/0.1",
        "metadata": {
            "runtime_operations": [
                {"operation": "search", "argument": "DestinationGoal"},
                {"operation": "simulate", "argument": "RoutePlan"},
            ]
        },
    }


def request():
    return ExecutionRequest(
        "request-ea2",
        source_module="ea2",
        reason_ir=reason_ir(),
        execution_plan=valid_plan(),
        runtime_registry=runtime_real_registry(),
        metadata={
            "entry_function": "run",
            "parameters": ("goal",),
            "arguments": (RuntimeValue.goal("Destination"),),
        },
    )


class ExecutionArchitecturePhase2Tests(unittest.TestCase):
    def test_ea2_001_execution_scope_creation(self):
        scope = ExecutionScope("module", ScopeType.MODULE, variables={"x": RuntimeValue.int(1)})

        self.assertEqual(scope.to_dict()["schema"], "reasonscript-execution-architecture/1.2")
        self.assertEqual(scope.to_dict()["scope_type"], ScopeType.MODULE)

    def test_ea2_002_scope_push(self):
        stack = ExecutionScopeStack().push_scope(ScopeType.MODULE, "module")

        self.assertEqual(stack.current_scope().scope_id, "module")
        self.assertEqual(stack.trace_events[-1].operation, "ScopeCreated")

    def test_ea2_003_scope_pop(self):
        stack = ExecutionScopeStack().push_scope(ScopeType.MODULE, "module")
        stack, popped = stack.pop_scope()

        self.assertEqual(popped.destroyed_at, 1)
        self.assertIsNone(stack.current_scope())
        self.assertEqual(stack.trace_events[-1].operation, "ScopeDestroyed")

    def test_ea2_004_variable_resolution(self):
        stack = ExecutionScopeStack().push_scope(ScopeType.MODULE, "module")
        stack = stack.bind_variable("x", RuntimeValue.int(7))
        value, stack = stack.lookup("x")

        self.assertEqual(value.value, 7)
        self.assertEqual(stack.trace_events[-1].operation, "VariableResolved")

    def test_ea2_005_nested_scope(self):
        stack = ExecutionScopeStack().push_scope(ScopeType.MODULE, "module")
        stack = stack.bind_variable("x", RuntimeValue.int(1))
        stack = stack.push_scope(ScopeType.BLOCK, "block")
        stack = stack.bind_variable("y", RuntimeValue.int(2))

        x_value, stack = stack.lookup("x")
        y_value, _ = stack.lookup("y")
        self.assertEqual((x_value.value, y_value.value), (1, 2))

    def test_ea2_006_scope_lifetime(self):
        stack = ExecutionScopeStack().push_scope(ScopeType.FUNCTION, "fn")
        stack, popped = stack.pop_scope()

        self.assertEqual(popped.created_at, 0)
        self.assertEqual(popped.destroyed_at, 1)

    def test_ea2_007_scope_trace(self):
        stack = ExecutionScopeStack().push_scope(ScopeType.MODULE, "module")
        stack = stack.bind_variable("x", RuntimeValue.int(1))
        _, stack = stack.lookup("x")
        stack, _ = stack.pop_scope()

        self.assertEqual(
            [event.operation for event in stack.trace_events],
            ["ScopeCreated", "VariableBound", "VariableResolved", "ScopeDestroyed"],
        )

    def test_ea2_008_reasoning_trace_creation(self):
        result = ExecutionCoordinator(runtime_real_registry()).execute(request())

        self.assertEqual(result.reasoning_trace.to_dict()["schema"], REASONING_TRACE_SCHEMA)
        self.assertEqual(result.reasoning_trace.request_id, "request-ea2")

    def test_ea2_009_trace_event_normalization(self):
        events = normalize_trace_events("trace-a", TraceCategory.RUNTIME, ("runtime:start",))

        self.assertEqual(events[0].category, TraceCategory.RUNTIME)
        self.assertEqual(events[0].operation, "runtime")

    def test_ea2_010_trace_determinism(self):
        coordinator = ExecutionCoordinator(runtime_real_registry())

        self.assertEqual(
            coordinator.execute(request()).reasoning_trace.to_dict(),
            coordinator.execute(request()).reasoning_trace.to_dict(),
        )

    def test_ea2_011_platform_diagnostic_creation(self):
        diagnostic = PlatformDiagnostic("P1", DiagnosticSeverity.ERROR, "bad", DiagnosticSource.RUNTIME)

        self.assertEqual(diagnostic.to_dict()["schema"], PLATFORM_DIAGNOSTIC_SCHEMA)
        self.assertEqual(diagnostic.to_dict()["severity"], DiagnosticSeverity.ERROR)

    def test_ea2_012_diagnostic_aggregation(self):
        diagnostics = aggregate_platform_diagnostics(("bad",), source=DiagnosticSource.TOOLCHAIN)

        self.assertEqual(diagnostics[0].source, DiagnosticSource.TOOLCHAIN)

    def test_ea2_013_compiler_diagnostic_adapter(self):
        diagnostic = platform_diagnostic_from_compiler({"code": "C1", "message": "syntax"})

        self.assertEqual(diagnostic.source, DiagnosticSource.COMPILER)
        self.assertEqual(diagnostic.code, "C1")

    def test_ea2_014_runtime_diagnostic_adapter(self):
        diagnostic = platform_diagnostic_from_runtime("runtime failed")

        self.assertEqual(diagnostic.source, DiagnosticSource.RUNTIME)
        self.assertEqual(diagnostic.severity, DiagnosticSeverity.ERROR)

    def test_ea2_015_lsp_diagnostic_adapter(self):
        lsp_diagnostic = Diagnostic(
            LspSeverity.WARNING,
            "L1",
            "warn",
            Location("file:///a.rsn", point_range(0, 0)),
        )

        diagnostic = platform_diagnostic_from_lsp(lsp_diagnostic)
        self.assertEqual(diagnostic.source, DiagnosticSource.LSP)
        self.assertEqual(diagnostic.severity, DiagnosticSeverity.WARNING)

    def test_ea2_016_ide_diagnostic_adapter(self):
        lsp_diagnostic = Diagnostic(
            LspSeverity.ERROR,
            "I1",
            "ide error",
            Location("file:///a.rsn", point_range(0, 0)),
        )

        diagnostic = platform_diagnostic_from_ide(lsp_diagnostic)
        self.assertEqual(diagnostic.source, DiagnosticSource.IDE)

    def test_ea2_017_coordinator_integration(self):
        result = ExecutionCoordinator(runtime_real_registry()).execute(request())

        categories = [event.category for event in result.reasoning_trace.events]
        self.assertIn(TraceCategory.EXECUTION, categories)
        self.assertIn(TraceCategory.SCOPE, categories)

    def test_ea2_018_runtime_integration(self):
        result = ExecutionCoordinator(runtime_real_registry()).execute(request())

        runtime_events = [
            event for event in result.reasoning_trace.events if event.category == TraceCategory.RUNTIME
        ]
        self.assertTrue(runtime_events)

    def test_ea2_019_world_model_integration(self):
        scene = world.add_entity(world.create_scene("room"), world.create_entity("agent"))
        model = world.add_scene(world.create_world("w"), scene)
        event = world.create_event("move", "move", target="agent", payload={"scene_id": "room", "position": (1, 0, 0)})
        simulation = world.simulate_step(model, (event,))
        simulation_reasoning = reasoning_trace_from_world_simulation("world-sim", world.trace(simulation))
        reconstruction_reasoning = reasoning_trace_from_world_reconstruction(
            "world-rec",
            world.reconstruction_trace(world.reconstruct_scene(scene)),
        )

        self.assertEqual(simulation_reasoning.events[0].category, TraceCategory.SIMULATION)
        self.assertEqual(reconstruction_reasoning.events[0].category, TraceCategory.RECONSTRUCTION)

    def test_ea2_020_end_to_end_execution_trace(self):
        encoded = ExecutionCoordinator(runtime_real_registry()).execute(request()).to_dict()

        self.assertEqual(encoded["status"], "completed")
        self.assertTrue(encoded["reasoning_trace"]["events"])
        self.assertTrue(
            any(event["operation"] == "ScopeCreated" for event in encoded["reasoning_trace"]["events"])
        )


if __name__ == "__main__":
    unittest.main()
