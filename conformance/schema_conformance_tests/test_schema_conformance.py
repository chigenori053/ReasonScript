import unittest

from conformance.framework import (
    ConformanceError,
    ROOT,
    load_json,
    validate_reason_ir,
)
from conformance.schema_validator import SchemaValidator


class SchemaConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = SchemaValidator(ROOT / "schemas")

    def test_all_valid_fixtures_pass_schema_and_semantic_validation(self):
        for path in sorted((ROOT / "fixtures" / "valid").glob("*.json")):
            value = load_json(path)
            self.validator.validate_file(value, "reason_ir.schema.json")
            validate_reason_ir(value)

    def test_all_abi_fixtures_are_rejected(self):
        for path in sorted((ROOT / "fixtures" / "invalid").glob("*.json")):
            value = load_json(path)
            with self.assertRaises(ConformanceError, msg=path.name):
                self.validator.validate_file(value, "reason_ir.schema.json")
                validate_reason_ir(value)

    def test_public_dto_examples_validate_against_every_schema(self):
        state = {"state_id": "A", "state_type": "symbolic", "data": {}}
        delta = {
            "delta_id": "delta-1",
            "before_state": state,
            "after_state": {**state, "state_id": "B"},
            "applied_transition": "t1",
            "timestamp": 1,
        }
        examples = {
            "execution_plan.schema.json": {
                "selected_steps": [
                    {
                        "step_id": "step-1",
                        "transition_id": "t1",
                        "source": "A",
                        "target": "B",
                    }
                ],
                "alternative_paths": [],
                "expected_cost": 1,
                "evidence_refs": [],
                "planner_version": "planner/0.1",
            },
            "state_delta.schema.json": delta,
            "inference_result.schema.json": {
                "status": "completed",
                "final_state": {**state, "state_id": "B"},
                "state_deltas": [delta],
                "proof": {"selected_step_ids": ["step-1"], "evidence_refs": []},
                "violations": [],
                "alternatives": [],
                "trace_id": "trace-1",
            },
            "trace.schema.json": {
                "request_id": "request-1",
                "reason_ir_version": "reason-ir/0.1",
                "planner_version": "planner/0.1",
                "policy_version": "policy/0.1",
                "events": [
                    {
                        "event_type": "state_delta_applied",
                        "delta_id": "delta-1",
                        "transition_id": "t1",
                    }
                ],
            },
            "transaction_record.schema.json": {
                "transaction_id": "tx-1",
                "execution_plan_id": "plan-1",
                "candidate_id": "candidate-1",
                "delta_id": "delta-1",
                "status": "committed",
                "commit_timestamp": 1,
                "validation_failures": [],
                "source_delta_id": None,
            },
        }
        for schema, value in examples.items():
            self.validator.validate_file(value, schema)


if __name__ == "__main__":
    unittest.main()
