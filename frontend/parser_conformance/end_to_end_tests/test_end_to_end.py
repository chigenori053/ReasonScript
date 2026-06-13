import unittest

from conformance.framework import execute_reason_ir
from frontend.ast import to_reason_ir
from frontend.parser import parse
from frontend.parser_conformance.framework import VALID_FIXTURES, load_source

EXPECTED_STATUS = {
    "basic_inference.rsn": "completed",
    "constraint.rsn": "failed",
    "context.rsn": "failed",
    "tool_integration.rsn": "completed",
    "worldmodel_transition.rsn": "completed",
    "dbm_planning.rsn": "completed",
}


class ParserEndToEndTests(unittest.TestCase):
    def test_source_to_inference_result(self):
        for path in sorted(VALID_FIXTURES.glob("*.rsn")):
            result = execute_reason_ir(to_reason_ir(parse(load_source(path))))
            self.assertEqual(result["status"], EXPECTED_STATUS[path.name], path.name)

    def test_basic_inference_applies_both_transitions(self):
        path = VALID_FIXTURES / "basic_inference.rsn"
        result = execute_reason_ir(to_reason_ir(parse(load_source(path))))
        self.assertEqual(result["final_state_id"], "Animal")
        self.assertEqual(
            result["applied_transition_ids"],
            ["Dog-IsA-Mammal", "Mammal-IsA-Animal"],
        )


if __name__ == "__main__":
    unittest.main()
