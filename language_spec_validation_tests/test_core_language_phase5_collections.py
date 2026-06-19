import unittest

from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    ArrayLiteralNode,
    ArrayTypeNode,
    IndexAccessNode,
    IndexAssignmentStatementNode,
    MapLiteralNode,
    SetLiteralNode,
    SurfaceSyntaxError,
    TupleLiteralNode,
    compile_program,
    from_json_value,
    parse,
    to_json_value,
)


class CoreLanguagePhase5CollectionTests(unittest.TestCase):
    def test_collections_access_assignment_iteration_and_round_trip(self):
        program = parse(
            """
            module collections_core {
                fn use_collections() {
                    let values: [int] = [1, 2, 3]
                    values[0] = 10
                    let first = values[0]
                    let point: (int, int) = (10, 20)
                    let x = point.0
                    let tags: set<string> = set {
                        "science",
                        "ai"
                    }
                    let scores: map<string,int> = map {
                        "alice": 10,
                        "bob": 20
                    }
                    scores["alice"] = 50
                    for value in values {
                        observe(value)
                    }
                    return scores["alice"]
                }
            }
            """
        )
        function = program.modules[0].body[0]
        self.assertIsInstance(function.body[0].type_annotation, ArrayTypeNode)
        self.assertIsInstance(function.body[0].expression.expression, ArrayLiteralNode)
        self.assertIsInstance(function.body[1], IndexAssignmentStatementNode)
        self.assertIsInstance(function.body[2].expression.expression, IndexAccessNode)
        self.assertIsInstance(function.body[3].expression.expression, TupleLiteralNode)
        self.assertIsInstance(function.body[5].expression.expression, SetLiteralNode)
        self.assertIsInstance(function.body[6].expression.expression, MapLiteralNode)

        value = to_json_value(program)
        SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
            value, "language_surface_ast.schema.json"
        )
        self.assertEqual(from_json_value(value), program)
        reason_ir = compile_program(program)[0]
        self.assertEqual(
            reason_ir["metadata"]["function_declarations"][0]["body"][0]["expression"]["expression"]["node_type"],
            "ArrayLiteralNode",
        )

    def test_collection_validation_errors(self):
        cases = (
            (
                "CV5-1",
                """
                module invalid {
                    fn bad() {
                        let values = [1, "two"]
                        return null
                    }
                }
                """,
            ),
            (
                "CV5-3",
                """
                module invalid {
                    fn bad() {
                        let tags = set {
                            "a",
                            "a"
                        }
                        return null
                    }
                }
                """,
            ),
            (
                "CV5-5",
                """
                module invalid {
                    fn bad() {
                        let scores = map {
                            "a": 1,
                            "a": 2
                        }
                        return null
                    }
                }
                """,
            ),
            (
                "CV5-6",
                """
                module invalid {
                    fn bad() {
                        let values = [1, 2]
                        return values["first"]
                    }
                }
                """,
            ),
            (
                "CV5-9",
                """
                module invalid {
                    fn bad() {
                        const values = [1, 2]
                        values[0] = 3
                        return null
                    }
                }
                """,
            ),
        )
        for code, source in cases:
            with self.subTest(code=code), self.assertRaisesRegex(
                SurfaceSyntaxError, code
            ):
                parse(source)


if __name__ == "__main__":
    unittest.main()
