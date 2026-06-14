import unittest

from calculation_semantics_tests.model import lower_program, parse_calculations
from conformance.framework import ROOT, execute_reason_ir, validate_reason_ir
from conformance.schema_validator import SchemaValidator


BUILDING_COST = """
pub calculation BuildingCost goal:value {
    let width = 10
    let height = 20
    area = width * height
    cost = area * 100
    tax = cost * 0.1
    result = cost + tax
}
"""


class ExecutionPlanTests(unittest.TestCase):
    def test_cs_11_expected_plan_is_ordered_deterministic_and_acyclic(self):
        first = lower_program(parse_calculations(BUILDING_COST))
        second = lower_program(parse_calculations(BUILDING_COST))
        relations = [
            transition.relation for transition in first.calculations[0].transitions
        ]
        self.assertEqual(
            relations,
            [
                "MultiplyTransition",
                "MultiplyTransition",
                "MultiplyTransition",
                "AddTransition",
            ],
        )
        self.assertEqual(first.execution_plan, second.execution_plan)
        targets = [
            step["target"] for step in first.execution_plan["selected_steps"]
        ]
        self.assertEqual(len(targets), len(set(targets)))

    def test_reason_ir_and_execution_plan_conform_to_existing_schemas(self):
        lowered = lower_program(parse_calculations(BUILDING_COST))
        validate_reason_ir(lowered.reason_ir)
        schemas = SchemaValidator(ROOT / "schemas")
        schemas.validate_file(lowered.reason_ir, "reason_ir.schema.json")
        schemas.validate_file(lowered.execution_plan, "execution_plan.schema.json")
        runtime_result = execute_reason_ir(lowered.reason_ir)
        self.assertEqual(runtime_result["status"], "completed")
        self.assertEqual(runtime_result["state_delta_count"], 4)


if __name__ == "__main__":
    unittest.main()
