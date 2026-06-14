import unittest

from calculation_semantics_tests.model import (
    NumericMode,
    NumericPolicyError,
    RESULT_STATUSES,
    evaluate_expression,
    parse_expression,
    result_state,
    result_as_inference_dto,
    structured_eigen_state,
)
from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator


class ResultStateTests(unittest.TestCase):
    def test_cs_08_composite_result_is_one_structured_state(self):
        result = structured_eigen_state([3, 2], [[1, 0], [0, 1]])
        self.assertEqual(result.status, "Solved")
        self.assertEqual(result.value["state_type"], "EigenState")
        self.assertEqual(set(result.value), {"state_type", "values", "vectors"})

    def test_cs_09_all_calculation_statuses_map_without_runtime_changes(self):
        schemas = SchemaValidator(ROOT / "schemas")
        for status in sorted(RESULT_STATUSES):
            with self.subTest(status=status):
                result = result_state(status, trace=("step-1",))
                self.assertEqual(result.status, status)
                self.assertEqual(result.trace, ("step-1",))
                schemas.validate_file(
                    result_as_inference_dto(result), "inference_result.schema.json"
                )

    def test_cs_10_numeric_policy_rejects_real_and_solves_complex(self):
        expression = parse_expression("sqrt(-1)")
        with self.assertRaises(NumericPolicyError):
            evaluate_expression(expression, {}, NumericMode.REAL)
        value = evaluate_expression(expression, {}, NumericMode.COMPLEX)
        self.assertEqual(value, 1j)


if __name__ == "__main__":
    unittest.main()
