import unittest

from frontend.ast import TransitionNode, from_json_value
from frontend.compiler.expander import expand_defaults
from frontend.compiler_conformance.framework import VALID_FIXTURES, load_json


class CompilerDefaultExpansionTests(unittest.TestCase):
    def test_omitted_transition_cost_expands_to_one(self):
        for name in ("basic_inference.ast.json", "constraint.ast.json", "dbm_planning.ast.json"):
            module = from_json_value(load_json(VALID_FIXTURES / name))
            expanded = expand_defaults(module)
            transitions = [
                node
                for node in expanded.declarations
                if isinstance(node, TransitionNode)
            ]
            self.assertTrue(transitions)
            self.assertTrue(all(node.expected_cost == 1.0 for node in transitions))

    def test_expansion_is_deterministic_and_does_not_mutate_input(self):
        module = from_json_value(
            load_json(VALID_FIXTURES / "basic_inference.ast.json")
        )
        before = module
        self.assertEqual(expand_defaults(module), expand_defaults(module))
        self.assertEqual(module, before)


if __name__ == "__main__":
    unittest.main()
