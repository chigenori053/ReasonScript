import unittest

from frontend.language_surface import (
    AssignmentStatementNode,
    LetStatementNode,
    ResultStatementNode,
    SurfaceSyntaxError,
    parse,
)


class LayerDOrderingTests(unittest.TestCase):
    def test_d_001_statement_order_is_preserved(self):
        calculation = parse(
            """
            module ordered {
                calculation Score {
                    let a = 1
                    let b = 2
                    a = a + b
                    result = a
                }
            }
            """
        ).modules[0].body[0]
        self.assertEqual(
            tuple(type(item) for item in calculation.body),
            (
                LetStatementNode,
                LetStatementNode,
                AssignmentStatementNode,
                ResultStatementNode,
            ),
        )

    def test_d_002_result_must_be_last(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CAL-012"):
            parse(
                """
                module invalid {
                    calculation Score {
                        result = 1
                        let x = 2
                    }
                }
                """
            )

    def test_d_003_single_result(self):
        for body in ("let x = 1", "result = 1\nresult = 2"):
            expected = "CAL-010" if body == "let x = 1" else "CAL-011"
            with self.subTest(body=body), self.assertRaisesRegex(
                SurfaceSyntaxError, expected
            ):
                parse(
                    f"""
                    module invalid {{
                        calculation Score {{
                            {body}
                        }}
                    }}
                    """
                )

    def test_st_003_duplicate_immutable_binding_is_rejected(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "CAL-021"):
            parse(
                """
                module invalid {
                    calculation Score {
                        let x = 1
                        let x = 2
                        result = x
                    }
                }
                """
            )


if __name__ == "__main__":
    unittest.main()
