import unittest

from frontend.compiler import compile_document
from frontend.compiler_conformance.framework import (
    EXPECTED_FIXTURES,
    VALID_FIXTURES,
    fixture_name,
    load_json,
)


class CompilerLoweringTests(unittest.TestCase):
    def test_compilation_matches_expected_reason_ir(self):
        for path in sorted(VALID_FIXTURES.glob("*.ast.json")):
            expected = load_json(
                EXPECTED_FIXTURES / f"{fixture_name(path)}.ir.json"
            )
            self.assertEqual(compile_document(load_json(path)), expected, path.name)

    def test_compilation_is_deterministic(self):
        for path in sorted(VALID_FIXTURES.glob("*.ast.json")):
            source = load_json(path)
            self.assertEqual(
                compile_document(source), compile_document(source), path.name
            )

    def test_state_transition_constraint_and_metadata_semantics_are_preserved(self):
        output = compile_document(
            load_json(VALID_FIXTURES / "tool_integration.ast.json")
        )
        self.assertEqual(output["initial_state"]["state_id"], "WeatherQuery")
        self.assertEqual(output["transitions"][0]["relation"], "InvokeTool")
        self.assertEqual(output["metadata"]["producer"], "compiler-fixture/0.1")
        constrained = compile_document(
            load_json(VALID_FIXTURES / "constraint.ast.json")
        )
        self.assertEqual(constrained["constraints"][0]["expression"], "age >= 18")


if __name__ == "__main__":
    unittest.main()
