import unittest

from conformance.framework import validate_reason_ir
from conformance.schema_validator import SchemaValidator
from frontend.compiler import compile_document
from frontend.compiler_conformance.framework import ROOT, VALID_FIXTURES, load_json


class CompilerReasonIrCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = SchemaValidator(ROOT / "schemas")

    def test_all_outputs_pass_reason_ir_schema_and_semantics(self):
        for path in sorted(VALID_FIXTURES.glob("*.ast.json")):
            output = compile_document(load_json(path))
            self.schema.validate_file(output, "reason_ir.schema.json")
            validate_reason_ir(output)

    def test_compiler_has_no_runtime_dependency(self):
        compiler_root = ROOT / "frontend" / "compiler"
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in compiler_root.glob("*.py")
        )
        self.assertNotIn("HybridRuntime", source)
        self.assertNotIn("RuntimeReal", source)
        self.assertNotIn("execute_reason_ir", source)


if __name__ == "__main__":
    unittest.main()
