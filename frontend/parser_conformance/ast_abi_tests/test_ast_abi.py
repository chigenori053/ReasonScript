import unittest

from frontend.ast import to_json_value
from frontend.ast_validator import validate_document
from frontend.parser import parse
from frontend.parser_conformance.framework import VALID_FIXTURES, load_source


class ParserAstAbiTests(unittest.TestCase):
    def test_every_generated_ast_satisfies_the_ast_abi(self):
        for path in sorted(VALID_FIXTURES.glob("*.rsn")):
            validate_document(to_json_value(parse(load_source(path))))


if __name__ == "__main__":
    unittest.main()
