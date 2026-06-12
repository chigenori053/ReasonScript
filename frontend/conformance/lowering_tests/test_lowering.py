import unittest

from conformance.framework import validate_reason_ir
from conformance.schema_validator import SchemaValidator
from frontend.ast import from_json_value, to_reason_ir
from frontend.conformance.framework import ROOT, VALID_FIXTURES, load_json


class AstLoweringConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reason_ir_schema = SchemaValidator(ROOT / "schemas")

    def test_every_valid_fixture_lowers_to_reason_ir(self):
        for path in sorted(VALID_FIXTURES.glob("*.json")):
            reason_ir = to_reason_ir(from_json_value(load_json(path)))
            self.reason_ir_schema.validate_file(reason_ir, "reason_ir.schema.json")
            validate_reason_ir(reason_ir)

    def test_lowering_is_deterministic(self):
        for path in sorted(VALID_FIXTURES.glob("*.json")):
            ast = from_json_value(load_json(path))
            self.assertEqual(to_reason_ir(ast), to_reason_ir(ast), path.name)


if __name__ == "__main__":
    unittest.main()
