import unittest

from conformance.framework import execute_reason_ir
from frontend.ast import from_json_value, to_reason_ir
from frontend.conformance.framework import VALID_FIXTURES, load_json


class AstReasonIrCompatibilityTests(unittest.TestCase):
    def test_required_node_mappings_are_preserved(self):
        source = load_json(VALID_FIXTURES / "tool_integration.json")
        reason_ir = to_reason_ir(from_json_value(source))
        self.assertEqual(reason_ir["goal"]["target"], "WeatherAnswer")
        self.assertEqual(reason_ir["initial_state"]["state_id"], "WeatherQuery")
        self.assertEqual(reason_ir["context_refs"][0]["context_id"], "weather-tool")
        self.assertEqual(reason_ir["transitions"][0]["transition_id"], "invoke-weather")
        self.assertEqual(reason_ir["metadata"]["producer"], "fixture/0.1")

    def test_executable_fixtures_reach_their_goals(self):
        for name in (
            "basic_inference.json",
            "constraint.json",
            "tool_integration.json",
            "worldmodel_transition.json",
            "dbm_planning.json",
        ):
            reason_ir = to_reason_ir(from_json_value(load_json(VALID_FIXTURES / name)))
            self.assertEqual(execute_reason_ir(reason_ir)["status"], "completed", name)


if __name__ == "__main__":
    unittest.main()
