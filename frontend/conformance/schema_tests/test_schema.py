import unittest

from frontend.ast_validator import AstDocumentError, validate_document
from frontend.conformance.framework import INVALID_FIXTURES, VALID_FIXTURES, load_json


class AstSchemaConformanceTests(unittest.TestCase):
    def test_valid_fixtures_pass(self):
        for path in sorted(VALID_FIXTURES.glob("*.json")):
            validate_document(load_json(path))

    def test_invalid_fixtures_fail(self):
        for path in sorted(INVALID_FIXTURES.glob("*.json")):
            with self.assertRaises(AstDocumentError, msg=path.name):
                validate_document(load_json(path))


if __name__ == "__main__":
    unittest.main()
