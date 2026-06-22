import unittest

from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    RuntimeCallExpressionNode,
    RuntimeCallKind,
    compile_program,
    from_json_value,
    parse,
    to_json_value,
)
from frontend.runtime_integration import (
    RuntimeResult,
    RuntimeValue,
    execute_runtime_operations,
    runtime_value_to_plain,
)


SOURCE = """
module io {
    fn run() {
        let value = input()
        print(value)
        return value
    }
}
"""


class RuntimeIoSurfaceTests(unittest.TestCase):
    def test_rio_001_surface_shorthand_parses_as_runtime_calls(self):
        program = parse(SOURCE)
        statements = program.modules[0].body[0].body

        input_call = statements[0].expression.expression
        print_call = statements[1].expression.expression

        self.assertIsInstance(input_call, RuntimeCallExpressionNode)
        self.assertEqual(input_call.method, "input")
        self.assertEqual(input_call.kind, RuntimeCallKind.INPUT)
        self.assertEqual(input_call.arguments, ())
        self.assertIsInstance(print_call, RuntimeCallExpressionNode)
        self.assertEqual(print_call.method, "print")
        self.assertEqual(print_call.kind, RuntimeCallKind.PRINT)

    def test_rio_002_schema_round_trip_accepts_input_and_print(self):
        program = parse(SOURCE)
        value = to_json_value(program)

        SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
            value, "language_surface_ast.schema.json"
        )
        self.assertEqual(from_json_value(value), program)

    def test_rio_003_reason_ir_metadata_contains_io_operations(self):
        reason_ir = compile_program(parse(SOURCE))[0]
        operations = reason_ir["metadata"]["runtime_operations"]

        self.assertEqual(
            [(item["operation"], item["kind"]) for item in operations],
            [("input", "InputCall"), ("print", "PrintCall")],
        )
        self.assertEqual(operations[0]["argument"], None)
        self.assertEqual(operations[1]["source_state"], "value")

    def test_rio_004_runtime_io_executor_emits_state_and_output_event(self):
        class IoExecutor:
            def input(self):
                return RuntimeResult(True, RuntimeValue.input_state(42))

            def print(self, request):
                return RuntimeResult(
                    True,
                    RuntimeValue.output_event("value", runtime_value_to_plain(request)),
                )

        reason_ir = compile_program(parse(SOURCE))[0]
        report = execute_runtime_operations(reason_ir, IoExecutor())

        self.assertEqual(report.diagnostics, ())
        self.assertEqual(
            [result.operation for result in report.results],
            ["input", "print"],
        )
        self.assertEqual(report.results[0].language_value.kind, "InputState")
        self.assertEqual(report.results[1].language_value.kind, "OutputEvent")
        self.assertEqual(
            report.results[1].language_value.value["projection"],
            "canonical",
        )


if __name__ == "__main__":
    unittest.main()
