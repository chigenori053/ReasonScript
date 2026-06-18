import unittest

from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    EnumDeclarationNode,
    FieldAssignmentStatementNode,
    FunctionDeclarationNode,
    MemberAccessNode,
    NamedTypeNode,
    StructDeclarationNode,
    StructLiteralNode,
    SurfaceSyntaxError,
    compile_program,
    from_json_value,
    parse,
    to_json_value,
)


class CoreLanguagePhase4CompositeTests(unittest.TestCase):
    def test_struct_enum_field_access_assignment_and_round_trip(self):
        program = parse(
            """
            module composite_core {
                struct Position {
                    x: float
                    y: float
                }
                struct Player {
                    position: Position
                    score: int
                }
                enum Status {
                    Ready
                    Running
                    Finished
                }
                fn update(status) {
                    let player = Player {
                        position: Position {
                            x: 1.0
                            y: 2.0
                        }
                        score: 0
                    }
                    player.score = 10
                    let x = player.position.x
                    match status {
                        Status.Ready => return x
                        Status.Running => return 1.0
                        Status.Finished => return 2.0
                    }
                }
            }
            """
        )
        struct = program.modules[0].body[0]
        enum = program.modules[0].body[2]
        function = program.modules[0].body[3]
        self.assertIsInstance(struct, StructDeclarationNode)
        player_struct = program.modules[0].body[1]
        self.assertIsInstance(player_struct.fields[0].field_type, NamedTypeNode)
        self.assertIsInstance(enum, EnumDeclarationNode)
        self.assertIsInstance(function, FunctionDeclarationNode)
        self.assertIsInstance(function.body[0].expression.expression, StructLiteralNode)
        self.assertIsInstance(function.body[1], FieldAssignmentStatementNode)
        self.assertIsInstance(function.body[2].expression.expression, MemberAccessNode)

        value = to_json_value(program)
        SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
            value, "language_surface_ast.schema.json"
        )
        self.assertEqual(from_json_value(value), program)

        reason_ir = compile_program(program)[0]
        composites = reason_ir["metadata"]["composite_declarations"]
        self.assertEqual(composites[0]["node_type"], "StructDeclarationNode")
        self.assertEqual(composites[2]["node_type"], "EnumDeclarationNode")

    def test_struct_literal_requires_all_and_only_known_fields(self):
        cases = (
            ("TV-5", "x: 1.0"),
            ("TV-6", "x: 1.0\ny: 2.0\nz: 3.0"),
        )
        for code, fields in cases:
            with self.subTest(code=code), self.assertRaisesRegex(
                SurfaceSyntaxError, code
            ):
                parse(
                    f"""
                    module invalid {{
                        struct Position {{
                            x: float
                            y: float
                        }}
                        fn bad() {{
                            let pos = Position {{
                                {fields}
                            }}
                            return pos.x
                        }}
                    }}
                    """
                )

    def test_field_assignment_requires_mutable_binding(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "TV-10"):
            parse(
                """
                module invalid {
                    struct Player {
                        score: int
                    }
                    fn bad() {
                        const player = Player {
                            score: 0
                        }
                        player.score = 1
                        return player.score
                    }
                }
                """
            )

    def test_recursive_struct_and_non_exhaustive_enum_match_rejected(self):
        with self.assertRaisesRegex(SurfaceSyntaxError, "TV-8"):
            parse(
                """
                module invalid {
                    struct Node {
                        next: Node
                    }
                }
                """
            )
        with self.assertRaisesRegex(SurfaceSyntaxError, "NonExhaustiveMatch"):
            parse(
                """
                module invalid {
                    enum Status {
                        Ready
                        Running
                    }
                    fn bad() {
                        let status: Status = Status.Ready
                        match status {
                            Ready => return 1
                        }
                    }
                }
                """
            )


if __name__ == "__main__":
    unittest.main()
