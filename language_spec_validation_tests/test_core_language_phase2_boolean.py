import unittest

from frontend.language_surface import (
    FunctionDeclarationNode,
    MatchStatementNode,
    PrimitiveKind,
    SurfaceSyntaxError,
    from_json_value,
    parse,
    to_json_value,
)


class CoreLanguagePhase2BooleanTests(unittest.TestCase):
    def test_bool_conditionals_and_block_match_parse(self):
        program = parse(
            """
            module boolean_core {
                fn classify(score) {
                    const passing: bool = score >= 80
                    if passing && !(score < 0) {
                        match passing {
                            true => {
                                return 1
                            }
                            _ => {
                                return 0
                            }
                        }
                    }
                    else {
                        return 0
                    }
                }
            }
            """
        )
        function = program.modules[0].body[0]
        self.assertIsInstance(function, FunctionDeclarationNode)
        self.assertEqual(function.body[0].type_annotation.kind, PrimitiveKind.BOOL)
        self.assertIsInstance(function.body[1].body[0], MatchStatementNode)
        self.assertEqual(from_json_value(to_json_value(program)), program)

    def test_condition_must_be_boolean(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CV-1"):
            parse(
                """
                module invalid {
                    fn bad(x) {
                        if x {
                            return 1
                        }
                        else {
                            return 0
                        }
                    }
                }
                """
            )

    def test_relational_comparison_requires_comparable_operands(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CV-2"):
            parse(
                """
                module invalid {
                    fn bad() {
                        const left: bool = true
                        const right: bool = false
                        if left > right {
                            return 1
                        }
                        else {
                            return 0
                        }
                    }
                }
                """
            )

    def test_match_arm_validation(self):
        invalid_sources = (
            (
                "CV-5",
                """
                module invalid {
                    fn duplicate(status) {
                        match status {
                            Ready => return 1
                            Ready => return 2
                            _ => return 0
                        }
                    }
                }
                """,
            ),
            (
                "CV-7",
                """
                module invalid {
                    fn default_first(status) {
                        match status {
                            _ => return 0
                            Ready => return 1
                        }
                    }
                }
                """,
            ),
        )
        for code, source in invalid_sources:
            with self.subTest(code=code), self.assertRaisesRegex(SurfaceSyntaxError, code):
                parse(source)

    def test_phase2_keywords_are_reserved_identifiers(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "reserved keyword: bool"):
            parse(
                """
                module invalid {
                    fn bad() {
                        let bool = true
                        return bool
                    }
                }
                """
            )


if __name__ == "__main__":
    unittest.main()
