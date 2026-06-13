import unittest

from frontend.ast import GoalNode, StateNode, TransitionNode
from frontend.parser import ParserError, ParserErrorCode, parse
from frontend.parser_conformance.framework import (
    INVALID_FIXTURES,
    VALID_FIXTURES,
    load_source,
)

EXPECTED_ERRORS = {
    "missing_goal.rsn": ParserErrorCode.MISSING_GOAL,
    "missing_state.rsn": ParserErrorCode.MISSING_INITIAL_STATE,
    "duplicate_goal.rsn": ParserErrorCode.DUPLICATE_GOAL,
    "invalid_transition.rsn": ParserErrorCode.MISSING_ARGUMENT,
    "invalid_uri.rsn": ParserErrorCode.INVALID_URI,
    "unknown_keyword.rsn": ParserErrorCode.UNKNOWN_KEYWORD,
}


class ParserConformanceTests(unittest.TestCase):
    def test_valid_fixtures_produce_module_nodes(self):
        for path in sorted(VALID_FIXTURES.glob("*.rsn")):
            module = parse(load_source(path))
            self.assertEqual(module.version, "reasonscript-ast/0.1")
            self.assertEqual(
                sum(isinstance(node, GoalNode) for node in module.declarations), 1
            )
            self.assertEqual(
                sum(isinstance(node, StateNode) for node in module.declarations), 1
            )

    def test_invalid_fixtures_return_structured_errors(self):
        for path in sorted(INVALID_FIXTURES.glob("*.rsn")):
            with self.assertRaises(ParserError, msg=path.name) as raised:
                parse(load_source(path))
            error = raised.exception
            self.assertEqual(error.code, EXPECTED_ERRORS[path.name], path.name)
            self.assertGreaterEqual(error.line, 1)
            self.assertGreaterEqual(error.column, 1)
            self.assertEqual(error.severity.value, "error")
            self.assertTrue(error.message)

    def test_ast_generation_is_deterministic(self):
        for path in sorted(VALID_FIXTURES.glob("*.rsn")):
            source = load_source(path)
            self.assertEqual(parse(source), parse(source), path.name)

    def test_transition_ids_and_node_ids_are_stable(self):
        module = parse(load_source(VALID_FIXTURES / "basic_inference.rsn"))
        transitions = [
            node for node in module.declarations if isinstance(node, TransitionNode)
        ]
        self.assertEqual(
            [node.transition_id for node in transitions],
            ["Dog-IsA-Mammal", "Mammal-IsA-Animal"],
        )
        self.assertEqual(
            [node.node_id for node in transitions], ["transition-1", "transition-2"]
        )

    def test_duplicate_state_and_reserved_argument_are_rejected(self):
        with self.assertRaises(ParserError) as duplicate:
            parse("goal B\nstate A\nstate B\n")
        self.assertEqual(
            duplicate.exception.code, ParserErrorCode.DUPLICATE_INITIAL_STATE
        )
        with self.assertRaises(ParserError) as reserved:
            parse("goal state\nstate A\n")
        self.assertEqual(reserved.exception.code, ParserErrorCode.MALFORMED_STATEMENT)


if __name__ == "__main__":
    unittest.main()
