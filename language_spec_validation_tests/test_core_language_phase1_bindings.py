import unittest

from frontend.language_surface import (
    ConstStatementNode,
    FunctionDeclarationNode,
    LetStatementNode,
    ReturnStatementNode,
    SurfaceSyntaxError,
    compile_program,
    from_json_value,
    parse,
    to_json_value,
)


class CoreLanguagePhase1BindingTests(unittest.TestCase):
    def test_fn_const_let_and_return_parse_and_project(self):
        program = parse(
            """
            module core {
                goal Done
                fn add(a, b) {
                    const scale = 1
                    let sum = a + b
                    sum = sum + scale
                    return sum
                }
                calculation UseAdd {
                    const base = 2
                    let value = add(base, 3)
                    result = value
                }
            }
            """
        )
        function = program.modules[0].body[1]
        calculation = program.modules[0].body[2]

        self.assertIsInstance(function, FunctionDeclarationNode)
        self.assertEqual(function.parameters, ("a", "b"))
        self.assertIsInstance(function.body[0], ConstStatementNode)
        self.assertIsInstance(function.body[1], LetStatementNode)
        self.assertIsInstance(function.body[-1], ReturnStatementNode)
        self.assertIsInstance(calculation.body[0], ConstStatementNode)

        reason_ir = compile_program(program)[0]
        metadata = reason_ir["metadata"]
        self.assertEqual(metadata["function_declarations"][0]["name"], "add")

        round_tripped = from_json_value(to_json_value(program))
        self.assertEqual(round_tripped, program)

    def test_const_reassignment_is_rejected(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CONST-001"):
            parse(
                """
                module invalid {
                    fn limit() {
                        const LIMIT = 10
                        LIMIT = 20
                        return LIMIT
                    }
                }
                """
            )

    def test_function_requires_terminal_return(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "FN-010"):
            parse(
                """
                module invalid {
                    fn missing() {
                        let x = 1
                    }
                }
                """
            )

    def test_block_local_binding_does_not_escape_function_scope(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "undefined variable: x"):
            parse(
                """
                module invalid {
                    fn scoped() {
                        if true {
                            let x = 10
                        }
                        return x
                    }
                }
                """
            )


if __name__ == "__main__":
    unittest.main()
