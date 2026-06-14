import json
import unittest

from conformance.framework import ROOT, validate_reason_ir
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    BinaryExpressionNode,
    BinaryOperator,
    compile_program,
    expression_from_json,
    parse,
    parse_expression,
    parse_pattern,
    pattern_from_json,
    project_program,
    ResultStatementNode,
    to_json_value,
)


class LayerECompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.schemas = SchemaValidator(ROOT / "frontend" / "schemas")

    def test_e_001_and_e_002_expression_serialization_round_trip(self):
        expression = parse_expression("risk(user.age, 1 + 2 * 3)")
        value = to_json_value(expression)
        self.schemas.validate_file(value, "expression.schema.json")
        self.assertEqual(json.loads(json.dumps(value)), value)
        self.assertEqual(expression_from_json(value), expression)

    def test_e_003_pattern_round_trip(self):
        for source in ("Draft", "42", '"ok"', "_"):
            with self.subTest(source=source):
                pattern = parse_pattern(source)
                value = to_json_value(pattern)
                self.schemas.validate_file(value, "pattern.schema.json")
                self.assertEqual(pattern_from_json(value), pattern)

    def test_e_004_and_e_005_semantic_projection_and_reason_ir(self):
        program = parse(
            """
            module finance {
                goal RiskComplete
                calculation RiskScore {
                    let income = 100
                    let factor = 2
                    result = income * factor
                }
            }
            """
        )
        result_statement = program.modules[0].body[1].body[-1]
        self.assertIsInstance(result_statement, ResultStatementNode)
        surface_result = result_statement.expression.expression
        self.assertIsInstance(surface_result, BinaryExpressionNode)
        self.assertEqual(surface_result.operator, BinaryOperator.MULTIPLY)
        semantic_module = project_program(program)[0]
        result_transition = semantic_module.declarations[-1]
        self.assertEqual(result_transition.relation, "ResultTransition")
        self.assertEqual(
            result_transition.effect["expression"]["node_type"], "ExpressionNode"
        )
        reason_ir = compile_program(program)[0]
        validate_reason_ir(reason_ir)


if __name__ == "__main__":
    unittest.main()
