import copy
import unittest

from conformance.framework import (
    ConformanceError,
    execute_reason_ir,
    execute_transaction_fixture,
)
from conformance.schema_validator import SchemaValidator
from conformance.framework import ROOT


def state(state_id):
    return {
        "state_id": state_id,
        "state_type": "symbolic",
        "data": {"identity": state_id},
    }


class RuntimeSchemaSemantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas = SchemaValidator(ROOT / "schemas")

    def test_execution_plan_state_delta_result_and_trace_contracts(self):
        plan = {
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
        }
        delta = {
            "delta_id": "delta-1",
            "before_state": state("A"),
            "after_state": state("B"),
            "applied_transition": "t1",
            "timestamp": 1,
        }
        result = {
            "status": "completed",
            "final_state": state("B"),
            "state_deltas": [delta],
            "proof": {
                "selected_step_ids": ["step-1"],
                "evidence_refs": [],
            },
            "violations": [],
            "alternatives": [],
            "trace_id": "request-1",
        }
        trace = {
            "request_id": "request-1",
            "reason_ir_version": "reason-ir/0.1",
            "planner_version": "planner/0.1",
            "policy_version": "policy/0.1",
            "events": [
                {
                    "event_type": "plan_selected",
                    "step_ids": ["step-1"],
                    "expected_cost": 1,
                },
                {
                    "event_type": "state_delta_applied",
                    "delta_id": "delta-1",
                    "transition_id": "t1",
                },
            ],
        }

        self.schemas.validate_file(plan, "execution_plan.schema.json")
        self.schemas.validate_file(delta, "state_delta.schema.json")
        self.schemas.validate_file(result, "inference_result.schema.json")
        self.schemas.validate_file(trace, "trace.schema.json")

    def test_result_requires_trace_identity_and_complete_final_state(self):
        invalid = {
            "status": "failed",
            "final_state": state("A"),
            "state_deltas": [],
            "proof": None,
            "violations": [],
            "alternatives": [],
        }
        with self.assertRaises(ConformanceError):
            self.schemas.validate_file(invalid, "inference_result.schema.json")


class RuntimeExecutionSemantics(unittest.TestCase):
    def test_constraint_rejection_is_deterministic_and_input_is_unchanged(self):
        reason_ir = {
            "schema_version": "reason-ir/0.1",
            "initial_state": {
                "state_id": "Person",
                "state_type": "entity",
                "data": {"age": 17},
            },
            "goal": {"kind": "reach_state", "target": "Adult"},
            "constraints": [
                {
                    "constraint_id": "adult-only",
                    "kind": "numeric",
                    "expression": "age >= 18",
                }
            ],
            "transitions": [
                {
                    "transition_id": "become-adult",
                    "source": "Person",
                    "relation": "Action",
                    "target": "Adult",
                    "expected_cost": 0,
                }
            ],
            "execution_policy": {
                "max_steps": 10,
                "rollback_on_failure": True,
                "constraint_mode": "reject",
            },
            "trace_policy": {
                "level": "standard",
                "include_alternatives": True,
                "include_state_data": True,
            },
        }
        original = copy.deepcopy(reason_ir)

        first = execute_reason_ir(reason_ir)
        second = execute_reason_ir(reason_ir)

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "rejected")
        self.assertEqual(first["final_state_id"], "Person")
        self.assertEqual(first["state_delta_count"], 0)
        self.assertEqual(first["applied_transition_ids"], [])
        self.assertEqual(reason_ir, original)

    def test_transaction_commit_and_rollback_are_auditable_deltas(self):
        fixture = {
            "initial_state": "A",
            "operations": [
                {
                    "op": "prepare",
                    "candidate_id": "candidate-1",
                    "source": "A",
                    "target": "B",
                    "transition_id": "t1",
                },
                {
                    "op": "validate",
                    "candidate_id": "candidate-1",
                    "accepted": True,
                },
                {"op": "commit", "candidate_id": "candidate-1"},
                {"op": "rollback", "source_delta_id": "delta-1"},
            ],
        }

        result = execute_transaction_fixture(fixture)

        self.assertEqual(result["final_state_id"], "A")
        self.assertEqual(result["delta_count"], 2)
        self.assertEqual(result["trace_delta_ids"], ["delta-1", "delta-2"])
        self.assertEqual(
            result["record_statuses"],
            ["prepared", "accepted", "committed", "rolled_back"],
        )


if __name__ == "__main__":
    unittest.main()
