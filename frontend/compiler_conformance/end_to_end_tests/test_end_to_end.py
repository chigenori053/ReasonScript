import unittest

from conformance.framework import execute_reason_ir
from frontend.compiler import compile, compile_document
from frontend.compiler_conformance.framework import ROOT, VALID_FIXTURES, load_json
from frontend.parser import parse

EXPECTED_STATUS = {
    "basic_inference.ast.json": "completed",
    "constraint.ast.json": "completed",
    "context_reference.ast.json": "failed",
    "dbm_planning.ast.json": "completed",
    "tool_integration.ast.json": "completed",
    "worldmodel_transition.ast.json": "completed",
}


class CompilerEndToEndTests(unittest.TestCase):
    def test_ast_to_reference_inference_result(self):
        for path in sorted(VALID_FIXTURES.glob("*.ast.json")):
            result = execute_reason_ir(compile_document(load_json(path)))
            self.assertEqual(result["status"], EXPECTED_STATUS[path.name], path.name)

    def test_basic_inference_reaches_animal(self):
        path = VALID_FIXTURES / "basic_inference.ast.json"
        result = execute_reason_ir(compile_document(load_json(path)))
        self.assertEqual(result["final_state_id"], "Animal")
        self.assertEqual(result["state_delta_count"], 2)

    def test_source_parser_compiler_runtime_chain(self):
        source = (
            ROOT / "frontend" / "parser_fixtures" / "valid" / "basic_inference.rsn"
        ).read_text(encoding="utf-8")
        result = execute_reason_ir(compile(parse(source)))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["final_state_id"], "Animal")


if __name__ == "__main__":
    unittest.main()
