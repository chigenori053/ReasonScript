import unittest

from conformance.framework import validate_reason_ir
from conformance.schema_validator import SchemaValidator
from frontend.ast import to_reason_ir
from frontend.parser import parse
from frontend.parser_conformance.framework import ROOT, VALID_FIXTURES, load_source


class ParserLoweringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = SchemaValidator(ROOT / "schemas")

    def test_every_source_lowers_to_valid_reason_ir(self):
        for path in sorted(VALID_FIXTURES.glob("*.rsn")):
            reason_ir = to_reason_ir(parse(load_source(path)))
            self.schema.validate_file(reason_ir, "reason_ir.schema.json")
            validate_reason_ir(reason_ir)

    def test_source_to_reason_ir_is_deterministic(self):
        for path in sorted(VALID_FIXTURES.glob("*.rsn")):
            source = load_source(path)
            self.assertEqual(
                to_reason_ir(parse(source)), to_reason_ir(parse(source)), path.name
            )


if __name__ == "__main__":
    unittest.main()
