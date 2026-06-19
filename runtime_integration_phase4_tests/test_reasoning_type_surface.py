import unittest

from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    ConstraintNode,
    ExecutionPlanDeclarationNode,
    GoalNode,
    PlanStepNode,
    ReasonGraphDeclarationNode,
    StateDeclarationNode,
    SurfaceSyntaxError,
    compile_program,
    from_json_value,
    parse,
    to_json_value,
)
from frontend.runtime_integration import (
    execute_runtime_operations_with_registry,
    runtime_real_registry,
)


PHASE4_SOURCE = """
package world

module route {
    goal Destination {
        description: Reach the destination
    }
    state Start {
        label: Origin
    }
    constraint MaxCost {
        cost <= 10.0
    }
    reason_graph RouteGraph {
        state Start
        state Waypoint
        state Destination
        transition Start -> Waypoint
        transition Waypoint -> Destination
    }
    execution_plan RoutePlan {
        step Start -> Waypoint
        step Waypoint -> Destination
    }
    fn run() {
        let found = runtime.search(Destination)
        let planned = runtime.plan(Destination)
        let simulation = runtime.simulate(RoutePlan)
        let prediction = runtime.predict(Start)
        return found
    }
}
"""


class RuntimeIntegrationPhase4Tests(unittest.TestCase):
    def test_ri4_001_through_ri4_006_parse_reasoning_declarations(self):
        program = parse(PHASE4_SOURCE)
        body = program.modules[0].body

        self.assertIsInstance(body[0], GoalNode)
        self.assertEqual(body[0].metadata, (("description", "Reach the destination"),))
        self.assertIsInstance(body[1], StateDeclarationNode)
        self.assertEqual(body[1].metadata, (("label", "Origin"),))
        self.assertIsInstance(body[2], ConstraintNode)
        self.assertEqual(body[2].expression, "cost <= 10.0")
        self.assertIsInstance(body[3], ReasonGraphDeclarationNode)
        self.assertEqual([state.name for state in body[3].states], ["Start", "Waypoint", "Destination"])
        self.assertIsInstance(body[4], ExecutionPlanDeclarationNode)
        self.assertTrue(all(isinstance(step, PlanStepNode) for step in body[4].steps))

    def test_ri4_007_schema_and_json_round_trip_include_reasoning_surface(self):
        program = parse(PHASE4_SOURCE)
        value = to_json_value(program)

        SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
            value, "language_surface_ast.schema.json"
        )
        self.assertEqual(from_json_value(value), program)

    def test_ri4_009_through_ri4_012_metadata_and_runtime_execution(self):
        program = parse(PHASE4_SOURCE)
        reason_ir = compile_program(program)[0]
        metadata = reason_ir["metadata"]

        declarations = metadata["reasoning_declarations"]
        self.assertEqual([item["name"] for item in declarations["goals"]], ["Destination"])
        self.assertEqual([item["name"] for item in declarations["states"]], ["Start"])
        self.assertEqual([item["name"] for item in declarations["constraints"]], ["MaxCost"])
        self.assertEqual([item["name"] for item in declarations["reason_graphs"]], ["RouteGraph"])
        self.assertEqual([item["name"] for item in declarations["execution_plans"]], ["RoutePlan"])
        self.assertEqual(
            [item["operation"] for item in metadata["runtime_operations"]],
            ["search", "plan", "simulate", "predict"],
        )

        report = execute_runtime_operations_with_registry(reason_ir, runtime_real_registry())
        self.assertEqual(report.diagnostics, ())
        self.assertEqual([result.operation for result in report.results], ["search", "plan", "simulate", "predict"])

    def test_ri4_013_invalid_reason_graph_transition(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "InvalidReasonGraphTransition"):
            parse(
                """
                package world
                module bad {
                    reason_graph BadGraph {
                        state Start
                        transition Start -> Missing
                    }
                }
                """
            )

    def test_ri4_014_invalid_execution_plan_step(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "InvalidExecutionPlanStep"):
            parse(
                """
                package world
                module bad {
                    state Start
                    execution_plan BadPlan {
                        step Start -> Missing
                    }
                }
                """
            )

    def test_ri4_015_invalid_constraint_expression_and_runtime_type(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "InvalidConstraintExpression"):
            parse(
                """
                package world
                module bad {
                    constraint BadConstraint {
                        cost
                    }
                }
                """
            )

        with self.assertRaisesRegex(SurfaceSyntaxError, "RuntimeReasoningTypeMismatch"):
            parse(
                """
                package world
                module bad {
                    goal Destination
                    fn run() {
                        return runtime.predict(Destination)
                    }
                }
                """
            )


if __name__ == "__main__":
    unittest.main()
