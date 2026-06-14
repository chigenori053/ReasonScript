import dataclasses
import unittest

from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator
from computation_model_tests.model import (
    MathState,
    MathTransition,
    assert_valid_delta_chain,
    plan_as_dto,
    result_as_dto,
    run_procedure,
)


class CoreComputationModelValidation(unittest.TestCase):
    def setUp(self):
        self.initial = MathState.create("Input", {"value": 2})
        self.rules = (
            MathTransition(
                "square", "Input", "Squared", "Arithmetic", lambda d: {"value": d["value"] ** 2}
            ),
            MathTransition(
                "increment",
                "Squared",
                "Solved",
                "Arithmetic",
                lambda d: {"value": d["value"] + 1},
            ),
        )

    def test_cm_h1_computation_is_an_ordered_state_delta_chain(self):
        plan, result = run_procedure(self.initial, "Solved", self.rules)
        self.assertEqual(result.final_state.data["value"], 5)
        self.assertEqual(len(plan.selected_steps), 2)
        assert_valid_delta_chain(self, result)

    def test_cm_h2_arithmetic_is_deterministic(self):
        first = run_procedure(self.initial, "Solved", self.rules)
        second = run_procedure(self.initial, "Solved", self.rules)
        self.assertEqual(first, second)

    def test_cm_h3_symbolic_and_numeric_steps_share_the_model(self):
        rules = (
            MathTransition(
                "normalize-symbols",
                "Input",
                "Normalized",
                "SymbolicRewrite",
                lambda d: {"expression": "2 + 2"},
            ),
            MathTransition(
                "evaluate",
                "Normalized",
                "Solved",
                "Arithmetic",
                lambda d: {"expression": d["expression"], "value": 4},
            ),
        )
        _, result = run_procedure(MathState.create("Input", {}), "Solved", rules)
        self.assertEqual(result.final_state.data["value"], 4)
        assert_valid_delta_chain(self, result)

    def test_cm_h5_execution_plan_is_immutable_and_complete(self):
        plan, _ = run_procedure(self.initial, "Solved", self.rules)
        self.assertEqual(plan.expected_cost, 2)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            plan.expected_cost = 3

    def test_state_snapshot_is_deeply_isolated(self):
        source = {"matrix": [[1, 2], [3, 4]]}
        state = MathState.create("Matrix", source)
        source["matrix"][0][0] = 99
        observed = state.data
        observed["matrix"][0][0] = 88
        self.assertEqual(state.data["matrix"][0][0], 1)

    def test_invalid_or_incomplete_plan_is_rejected(self):
        with self.assertRaises(ValueError):
            run_procedure(self.initial, "MissingGoal", self.rules)

    def test_outputs_conform_to_existing_platform_dto_schemas(self):
        plan, result = run_procedure(self.initial, "Solved", self.rules)
        schemas = SchemaValidator(ROOT / "schemas")
        schemas.validate_file(plan_as_dto(plan), "execution_plan.schema.json")
        schemas.validate_file(result_as_dto(result), "inference_result.schema.json")


if __name__ == "__main__":
    unittest.main()
