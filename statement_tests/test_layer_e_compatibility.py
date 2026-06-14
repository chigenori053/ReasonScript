import unittest

from conformance.framework import ROOT, validate_reason_ir
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    GoalStatementNode,
    RequireStatementNode,
    ResultStatementNode,
    compile_program,
    execution_plan_for,
    parse,
    statement_from_json,
    to_json_value,
)


SOURCE = """
module workflow {
    constraint Adult
    goal Approved
    transition Approve {
        Draft -> ApprovedState
        require Adult
        goal Approved
        reach Approved
        publish(order)
    }
    calculation Risk {
        let income = 100
        let factor = 2
        result = income * factor
    }
}
"""


class LayerECompilerCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.program = parse(SOURCE)
        self.frontend_schemas = SchemaValidator(ROOT / "frontend" / "schemas")
        self.schemas = SchemaValidator(ROOT / "schemas")

    def test_e_001_and_e_002_statement_serialization_round_trip(self):
        statements = (
            RequireStatementNode("Adult"),
            GoalStatementNode("Approved"),
            ResultStatementNode(
                self.program.modules[0].body[3].body[-1].expression
            ),
        )
        for statement in statements:
            with self.subTest(statement=type(statement).__name__):
                value = to_json_value(statement)
                self.frontend_schemas.validate_file(value, "statement.schema.json")
                self.assertEqual(statement_from_json(value), statement)

    def test_e_003_semantic_projection_preserves_statement_meaning(self):
        reason_ir = compile_program(self.program)[0]
        transition = next(
            item for item in reason_ir["transitions"] if item["transition_id"] == "Approve"
        )
        self.assertEqual(transition["guard"], "Adult")
        self.assertEqual(transition["target"], "Approved")
        self.assertEqual(transition["effect"]["goals"], ["Approved"])
        self.assertEqual(
            [item["node_type"] for item in transition["effect"]["body"]],
            [
                "RequireStatementNode",
                "GoalStatementNode",
                "ReachStatementNode",
                "ExpressionStatementNode",
            ],
        )

    def test_e_004_and_e_005_reason_ir_and_execution_plan(self):
        reason_ir = compile_program(self.program)[0]
        validate_reason_ir(reason_ir)
        self.schemas.validate_file(reason_ir, "reason_ir.schema.json")
        plan = execution_plan_for(reason_ir)
        self.schemas.validate_file(plan, "execution_plan.schema.json")
        calculation_relations = [
            item["relation"]
            for item in reason_ir["transitions"]
            if item["transition_id"].startswith("Risk-")
        ]
        self.assertEqual(
            calculation_relations,
            ["ExpressionTransition", "ExpressionTransition", "ResultTransition"],
        )


if __name__ == "__main__":
    unittest.main()
