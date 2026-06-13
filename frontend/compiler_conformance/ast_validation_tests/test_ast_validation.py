import unittest

from frontend.compiler import CompilerError, CompilerErrorCode, compile_document
from frontend.compiler.validator import require_ast_document
from frontend.compiler_conformance.framework import (
    INVALID_FIXTURES,
    VALID_FIXTURES,
    load_json,
)


class CompilerAstValidationTests(unittest.TestCase):
    def test_valid_fixtures_pass_ast_validation(self):
        for path in sorted(VALID_FIXTURES.glob("*.ast.json")):
            require_ast_document(load_json(path))

    def test_invalid_fixtures_return_compiler_errors(self):
        for path in sorted(INVALID_FIXTURES.glob("*.json")):
            with self.assertRaises(CompilerError, msg=path.name) as raised:
                compile_document(load_json(path))
            self.assertIn(
                raised.exception.code,
                {
                    CompilerErrorCode.SCHEMA_VIOLATION,
                    CompilerErrorCode.UNSUPPORTED_NODE,
                },
                path.name,
            )
            self.assertEqual(raised.exception.severity.value, "error")
            self.assertTrue(raised.exception.message)

    def test_unsupported_node_has_specific_error(self):
        path = INVALID_FIXTURES / "unsupported_node.json"
        with self.assertRaises(CompilerError) as raised:
            compile_document(load_json(path))
        self.assertEqual(raised.exception.code, CompilerErrorCode.UNSUPPORTED_NODE)
        self.assertEqual(raised.exception.node_id, "runtime")


if __name__ == "__main__":
    unittest.main()
