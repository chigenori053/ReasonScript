import json
import unittest

from conformance.framework import ROOT, validate_reason_ir
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    compile_program,
    execution_plan_for,
    from_json_value,
    parse,
    project_program,
    to_json_value,
)


SOURCE = """
pub module finance {
    concept Person
    object User
    goal RiskComplete
    User IsA Person
    calculation RiskScore {
        let income = 100
        let factor = 2
        result = income * factor
    }
}
"""


class LayerDCompilerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.schemas = SchemaValidator(ROOT / "schemas")
        self.surface_schemas = SchemaValidator(ROOT / "frontend" / "schemas")
        self.program = parse(SOURCE)

    def test_d_001_ast_to_reason_ir(self):
        reason_ir = compile_program(self.program)[0]
        validate_reason_ir(reason_ir)
        self.schemas.validate_file(reason_ir, "reason_ir.schema.json")
        self.assertEqual(reason_ir["schema_version"], "reason-ir/0.1")
        self.assertEqual(
            [item["relation"] for item in reason_ir["transitions"]],
            ["IsA", "ExpressionTransition", "ExpressionTransition", "ResultTransition"],
        )

    def test_d_002_ast_to_execution_plan(self):
        reason_ir = compile_program(self.program)[0]
        plan = execution_plan_for(reason_ir)
        self.schemas.validate_file(plan, "execution_plan.schema.json")
        self.assertEqual(len(plan["selected_steps"]), len(reason_ir["transitions"]))

    def test_d_003_ast_stability(self):
        first = project_program(self.program)
        second = project_program(parse(SOURCE))
        self.assertEqual(first, second)
        self.assertEqual(compile_program(self.program), compile_program(self.program))

    def test_d_004_ast_serialization_round_trip(self):
        value = to_json_value(self.program)
        self.assertEqual(json.loads(json.dumps(value)), value)
        self.surface_schemas.validate_file(
            value, "language_surface_ast.schema.json"
        )
        self.assertEqual(from_json_value(value), self.program)


if __name__ == "__main__":
    unittest.main()
