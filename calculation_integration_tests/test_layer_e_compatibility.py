import json
import unittest

from conformance.framework import ROOT, validate_reason_ir
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    calculation_from_json,
    compile_program,
    execution_plan_for,
    parse,
    project_program,
    to_json_value,
)


SOURCE = """
module finance {
    attribute income
    attribute factor
    goal RiskEvaluation
    pub calculation RiskScore goal:RiskEvaluation {
        let score = income * factor
        score = score + 1
        result = score
    }
}
"""


class LayerECompilerCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.program = parse(SOURCE)
        self.calculation = self.program.modules[0].body[-1]
        self.schemas = SchemaValidator(ROOT / "schemas")
        self.frontend_schemas = SchemaValidator(ROOT / "frontend" / "schemas")

    def test_e_001_semantic_projection(self):
        semantic = project_program(self.program)[0]
        calculation_transitions = [
            item
            for item in semantic.declarations
            if getattr(item, "transition_id", "").startswith("RiskScore-")
        ]
        self.assertEqual(
            [item.relation for item in calculation_transitions],
            ["MultiplyTransition", "StateUpdateTransition", "ResultTransition"],
        )
        self.assertEqual(calculation_transitions[-1].target, "RiskScore.state.result")

    def test_e_002_and_e_003_reason_ir_and_execution_plan(self):
        reason_ir = compile_program(self.program)[0]
        validate_reason_ir(reason_ir)
        self.schemas.validate_file(reason_ir, "reason_ir.schema.json")
        plan = execution_plan_for(reason_ir)
        self.schemas.validate_file(plan, "execution_plan.schema.json")
        calculation_transitions = [
            item
            for item in reason_ir["transitions"]
            if item["transition_id"].startswith("RiskScore-")
        ]
        calculation_steps = [
            item
            for item in plan["selected_steps"]
            if item["transition_id"].startswith("RiskScore-")
        ]
        self.assertEqual(
            [item["transition_id"] for item in calculation_steps],
            [item["transition_id"] for item in calculation_transitions],
        )

    def test_e_004_and_e_005_serialization_round_trip(self):
        value = to_json_value(self.calculation)
        self.assertEqual(json.loads(json.dumps(value)), value)
        self.frontend_schemas.validate_file(value, "calculation.schema.json")
        self.assertEqual(calculation_from_json(value), self.calculation)


if __name__ == "__main__":
    unittest.main()
