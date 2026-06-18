import unittest

from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    BreakStatementNode,
    ContinueStatementNode,
    ForStatementNode,
    FunctionDeclarationNode,
    LoopStatementNode,
    SurfaceSyntaxError,
    WhileStatementNode,
    compile_program,
    from_json_value,
    parse,
    to_json_value,
)


class CoreLanguagePhase3IterationTests(unittest.TestCase):
    def test_for_while_loop_break_continue_parse_project_and_round_trip(self):
        program = parse(
            """
            module iteration_core {
                fn find(values, target) {
                    let counter = 0
                    while counter < 10 {
                        counter = counter + 1
                        break
                    }
                    for value in values {
                        if value != target {
                            continue
                        }
                        return value
                    }
                    loop {
                        break
                    }
                    return null
                }
            }
            """
        )
        function = program.modules[0].body[0]
        self.assertIsInstance(function, FunctionDeclarationNode)
        self.assertIsInstance(function.body[1], WhileStatementNode)
        self.assertIsInstance(function.body[2], ForStatementNode)
        self.assertIsInstance(function.body[3], LoopStatementNode)
        self.assertIsInstance(function.body[1].body[-1], BreakStatementNode)
        self.assertIsInstance(function.body[2].body[0].body[0], ContinueStatementNode)
        value = to_json_value(program)
        SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
            value, "language_surface_ast.schema.json"
        )
        self.assertEqual(from_json_value(value), program)

        reason_ir = compile_program(program)[0]
        functions = reason_ir["metadata"]["function_declarations"]
        self.assertEqual(functions[0]["body"][1]["node_type"], "WhileStatementNode")
        self.assertEqual(functions[0]["body"][2]["node_type"], "ForStatementNode")

    def test_iteration_variable_is_immutable_and_scoped_to_loop(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CONST-001"):
            parse(
                """
                module invalid {
                    fn bad(values) {
                        for item in values {
                            item = 10
                        }
                        return null
                    }
                }
                """
            )
        with self.assertRaisesRegex(SurfaceSyntaxError, "undefined variable: item"):
            parse(
                """
                module invalid {
                    fn bad(values) {
                        for item in values {
                        }
                        return item
                    }
                }
                """
            )

    def test_break_and_continue_must_be_inside_loop(self):
        for keyword, code in (("break", "IV-4"), ("continue", "IV-5")):
            with self.subTest(keyword=keyword), self.assertRaisesRegex(
                SurfaceSyntaxError, code
            ):
                parse(
                    f"""
                    module invalid {{
                        fn bad() {{
                            {keyword}
                            return null
                        }}
                    }}
                    """
                )

    def test_while_condition_must_be_bool_and_for_source_iterable(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CV-1"):
            parse(
                """
                module invalid {
                    fn bad() {
                        let count = 1
                        while count {
                            break
                        }
                        return null
                    }
                }
                """
            )
        with self.assertRaisesRegex(SurfaceSyntaxError, "IV-8"):
            parse(
                """
                module invalid {
                    fn bad() {
                        let count = 1
                        for item in count {
                            break
                        }
                        return null
                    }
                }
                """
            )


if __name__ == "__main__":
    unittest.main()
