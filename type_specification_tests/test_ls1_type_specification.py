import json
import unittest

from conformance.framework import ROOT, validate_reason_ir
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    PrimitiveKind,
    PrimitiveTypeNode,
    StateKind,
    StateTypeNode,
    SurfaceSyntaxError,
    compile_program,
    execution_plan_for,
    from_json_value,
    parse,
    to_json_value,
    type_from_json,
)


def calculation(body: str, return_type: str = ""):
    arrow = f" -> {return_type}" if return_type else ""
    return parse(
        f"""
        module typed {{
            goal Done
            constraint Adult
            object User
            calculation Check{arrow} {{
                {body}
            }}
        }}
        """
    )


class LayerATypeNodeTests(unittest.TestCase):
    def test_a_001_primitive_type_round_trip(self):
        node = PrimitiveTypeNode(PrimitiveKind.INT)
        value = to_json_value(node)
        self.assertEqual(value["node_type"], "PrimitiveTypeNode")
        self.assertEqual(type_from_json(value), node)

    def test_a_002_state_type_round_trip(self):
        node = StateTypeNode(StateKind.GOAL)
        value = to_json_value(node)
        self.assertEqual(value["node_type"], "StateTypeNode")
        self.assertEqual(type_from_json(value), node)

    def test_a_003_annotations_parse_and_program_round_trip(self):
        program = calculation(
            "let score: Float = 0.8\nresult = score",
            return_type="Float",
        )
        typed = program.modules[0].body[-1]
        self.assertEqual(typed.body[0].type_annotation.kind, PrimitiveKind.FLOAT)
        self.assertEqual(typed.return_type.kind, PrimitiveKind.FLOAT)
        value = to_json_value(program)
        self.assertEqual(from_json_value(json.loads(json.dumps(value))), program)


class LayerBVariableTypingTests(unittest.TestCase):
    def test_b_001_through_b_004_primitive_assignments(self):
        cases = (
            ("Int", "20"),
            ("Float", "0.8"),
            ("Bool", "true"),
            ("String", '"ready"'),
        )
        for type_name, value in cases:
            with self.subTest(type_name=type_name):
                calculation(f"let value: {type_name} = {value}\nresult = value")


class LayerCExpressionTypingTests(unittest.TestCase):
    def test_c_001_arithmetic(self):
        calculation("let value: Int = 1 + 2\nresult = value", "Int")
        calculation("let value: Float = 1.0 + 2.0\nresult = value", "Float")

    def test_c_002_comparison(self):
        calculation("let value: Bool = 2 > 1\nresult = value", "Bool")

    def test_c_003_logical(self):
        calculation("let value: Bool = true && false\nresult = value", "Bool")


class LayerDInvalidTypeTests(unittest.TestCase):
    def assert_type_error(self, body: str, code: str, return_type: str = ""):
        with self.assertRaisesRegex(SurfaceSyntaxError, code):
            calculation(body, return_type)

    def test_d_001_unknown_type(self):
        self.assert_type_error(
            "let value: Number = 1\nresult = value",
            "TYPE-V001",
        )

    def test_d_002_assignment_mismatch(self):
        self.assert_type_error(
            'let value: Int = "wrong"\nresult = value',
            "TYPE-V003",
        )
        self.assert_type_error(
            "let value = 1\nresult = value",
            "TYPE-V003",
            return_type="String",
        )

    def test_d_003_arithmetic_mismatch(self):
        self.assert_type_error(
            "let value = 1 + 2.0\nresult = value",
            "TYPE-V004",
        )

    def test_d_004_logical_mismatch(self):
        self.assert_type_error(
            "let value = 1 && true\nresult = value",
            "TYPE-V006",
        )

    def test_goal_and_constraint_state_integrity(self):
        calculation("let target: Goal = Done\nresult = target", "Goal")
        calculation("let rule: Constraint = Adult\nresult = rule", "Constraint")
        self.assert_type_error(
            "let target: Goal = Adult\nresult = target",
            "TYPE-V007",
        )
        self.assert_type_error(
            "let rule: Constraint = Done\nresult = rule",
            "TYPE-V008",
        )


class LayerECompilerCompatibilityTests(unittest.TestCase):
    def test_e_001_through_e_004_projection_ir_and_plan(self):
        program = calculation(
            "let score: Float = 0.8\nresult = score",
            return_type="Float",
        )
        value = to_json_value(program)
        SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
            value, "language_surface_ast.schema.json"
        )
        reason_ir = compile_program(program)[0]
        validate_reason_ir(reason_ir)
        result = reason_ir["transitions"][-1]
        self.assertEqual(result["effect"]["return_type"]["kind"], "Float")
        plan = execution_plan_for(reason_ir)
        SchemaValidator(ROOT / "schemas").validate_file(
            plan, "execution_plan.schema.json"
        )


if __name__ == "__main__":
    unittest.main()
