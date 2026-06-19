import unittest

from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    FunctionDeclarationNode,
    MatchStatementNode,
    NoneLiteralNode,
    OptionalPatternNode,
    OptionalTypeNode,
    SomeExpressionNode,
    SurfaceSyntaxError,
    compile_program,
    from_json_value,
    parse,
    to_json_value,
)


class CoreLanguagePhase6OptionalTests(unittest.TestCase):
    def test_optional_bindings_match_collections_and_round_trip(self):
        program = parse(
            """
            module optional_core {
                struct Player {
                    name: string
                    score: optional<int>
                }

                fn find_player(): optional<Player> {
                    return none
                }

                fn use_optional() {
                    let fallback = Player {
                        name: "default"
                        score: none
                    }
                    let alice = Player {
                        name: "Alice"
                        score: some(10)
                    }
                    let maybe: optional<Player> = some(alice)
                    let values: [optional<int>] = [some(1), none, some(3)]
                    match maybe {
                        some(player) => return player.name
                        none => return fallback.name
                    }
                }
            }
            """
        )
        player = program.modules[0].body[0]
        function = program.modules[0].body[1]
        use_optional = program.modules[0].body[2]

        self.assertIsInstance(player.fields[1].field_type, OptionalTypeNode)
        self.assertIsInstance(function, FunctionDeclarationNode)
        self.assertIsInstance(function.return_type, OptionalTypeNode)
        self.assertIsInstance(function.body[0].expression.expression, NoneLiteralNode)
        self.assertIsInstance(use_optional.body[2].type_annotation, OptionalTypeNode)
        self.assertIsInstance(use_optional.body[2].expression.expression, SomeExpressionNode)
        self.assertIsInstance(use_optional.body[4], MatchStatementNode)
        self.assertIsInstance(use_optional.body[4].arms[0].pattern.pattern, OptionalPatternNode)

        value = to_json_value(program)
        SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
            value, "language_surface_ast.schema.json"
        )
        self.assertEqual(from_json_value(value), program)

        reason_ir = compile_program(program)[0]
        functions = reason_ir["metadata"]["function_declarations"]
        self.assertEqual(
            functions[0]["return_type"]["node_type"],
            "OptionalTypeNode",
        )

    def test_optional_validation_errors(self):
        cases = (
            (
                "OV-1",
                """
                module invalid {
                    fn bad() {
                        let value = none
                        return null
                    }
                }
                """,
            ),
            (
                "OV-1",
                """
                module invalid {
                    fn bad() {
                        let values = [some(1), none]
                        return null
                    }
                }
                """,
            ),
            (
                "OV-1",
                """
                module invalid {
                    fn bad() {
                        return none
                    }
                }
                """,
            ),
            (
                "OV-3",
                """
                module invalid {
                    fn bad() {
                        let value: optional<int> = some(10)
                        value = 10
                        return null
                    }
                }
                """,
            ),
            (
                "OV-4",
                """
                module invalid {
                    fn bad() {
                        let value: optional<int> = some(10)
                        let next = value + 1
                        return next
                    }
                }
                """,
            ),
            (
                "OV-5",
                """
                module invalid {
                    fn bad() {
                        let value: optional<int> = some(10)
                        match value {
                            some(inner) => return inner
                        }
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
