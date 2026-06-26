import pytest

from conformance.framework import ROOT
from conformance.schema_validator import SchemaValidator
from frontend.language_surface import (
    SemanticQualifiedPattern,
    SemanticStructPattern,
    SurfaceSyntaxError,
    parse,
    resolve_program,
    resolve_struct_pattern,
    semantic_pattern_from_json,
    semantic_pattern_to_json,
)
from frontend.language_surface.nodes import MatchStatementNode, StructPatternNode


def _module_symbols(module):
    return {
        node.name: node
        for node in module.body
        if hasattr(node, "name")
    }


def _first_struct_pattern(program, module_index=0):
    for node in program.modules[module_index].body:
        body = getattr(node, "body", ())
        for statement in body:
            if isinstance(statement, MatchStatementNode):
                pattern = statement.arms[0].pattern.pattern
                assert isinstance(pattern, StructPatternNode)
                return pattern
    raise AssertionError("struct pattern not found")


def test_sp_s001_existing_ast_accepted():
    program = parse(
        """
        module Basic {
            enum Role {
                Admin
                User
            }

            struct Person {
                role: Role
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { role: Role.Admin } => return 1
                    default => return 0
                }
            }
        }
        """
    )

    assert isinstance(_first_struct_pattern(program), StructPatternNode)


def test_sp_s002_struct_resolution():
    program = parse(
        """
        module Basic {
            enum Role {
                Admin
                User
            }

            struct Person {
                role: Role
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { role: Role.Admin } => return 1
                    default => return 0
                }
            }
        }
        """
    )
    pattern = _first_struct_pattern(program)
    semantic = resolve_struct_pattern(pattern, _module_symbols(program.modules[0]))

    assert isinstance(semantic, SemanticStructPattern)
    assert semantic.struct_symbol == "Person"
    assert semantic.fields[0].field_symbol == "role"
    assert semantic.fields[0].field_type == "Role"


def test_sp_s003_imported_struct():
    program = parse(
        """
        module Lib {
            export enum Role {
                Admin
                User
            }

            export struct Person {
                role: Role
            }
        }

        module Basic {
            import Lib.Person
            import Lib.Role as UserRole

            fn Score(person: Person) -> int {
                match person {
                    Person { role: UserRole.Admin } => return 1
                    default => return 0
                }
            }
        }
        """
    )
    _, namespaces = resolve_program(program)
    pattern = _first_struct_pattern(program, module_index=1)
    semantic = resolve_struct_pattern(
        pattern,
        _module_symbols(program.modules[1]),
        namespaces["Basic"],
    )

    assert semantic.struct_symbol == "Person"
    assert semantic.fields[0].field_type == "Role"


def test_sp_s004_qualified_enum_pattern():
    program = parse(
        """
        module Basic {
            enum Role {
                Admin
                User
            }

            struct Person {
                role: Role
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { role: Role.Admin } => return 1
                    default => return 0
                }
            }
        }
        """
    )
    semantic = resolve_struct_pattern(
        _first_struct_pattern(program),
        _module_symbols(program.modules[0]),
    )

    assert isinstance(semantic.fields[0].pattern, SemanticQualifiedPattern)
    assert semantic.fields[0].pattern.namespace == "Role"
    assert semantic.fields[0].pattern.identifier == "Admin"


def test_sp_s005_unknown_struct():
    with pytest.raises(SurfaceSyntaxError, match="SP-101"):
        parse(
            """
            module Basic {
                fn Score(person: int) -> int {
                    match person {
                        Human { } => return 1
                        default => return 0
                    }
                }
            }
            """
        )


def test_sp_s006_unknown_field():
    with pytest.raises(SurfaceSyntaxError, match="SP-102"):
        parse(
            """
            module Basic {
                struct Person {
                    role: int
                }

                fn Score(person: Person) -> int {
                    match person {
                        Person { age: 20 } => return 1
                        default => return 0
                    }
                }
            }
            """
        )


def test_sp_s007_duplicate_field():
    with pytest.raises(SurfaceSyntaxError, match="SP-001|SP-103"):
        parse(
            """
            module Basic {
                enum Role {
                    Admin
                    User
                }

                struct Person {
                    role: Role
                }

                fn Score(person: Person) -> int {
                    match person {
                        Person { role: Role.Admin role: Role.User } => return 1
                        default => return 0
                    }
                }
            }
            """
        )


def test_sp_s008_type_mismatch():
    with pytest.raises(SurfaceSyntaxError, match="SP-104"):
        parse(
            """
            module Basic {
                enum Role {
                    Admin
                    User
                }

                struct Person {
                    role: Role
                }

                fn Score(person: Person) -> int {
                    match person {
                        Person { role: 10 } => return 1
                        default => return 0
                    }
                }
            }
            """
        )


def test_sp_s009_semantic_json():
    program = parse(
        """
        module Basic {
            enum Role {
                Admin
                User
            }

            struct Person {
                role: Role
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { role: Role.Admin } => return 1
                    default => return 0
                }
            }
        }
        """
    )
    semantic = resolve_struct_pattern(
        _first_struct_pattern(program),
        _module_symbols(program.modules[0]),
    )
    value = semantic_pattern_to_json(semantic)

    assert value == {
        "node_type": "SemanticStructPattern",
        "struct_symbol": "Person",
        "fields": [
            {
                "node_type": "SemanticStructFieldPattern",
                "field_symbol": "role",
                "field_type": "Role",
                "pattern": {
                    "node_type": "SemanticQualifiedPattern",
                    "namespace": "Role",
                    "identifier": "Admin",
                },
            }
        ],
    }


def test_sp_s010_round_trip_and_schema():
    program = parse(
        """
        module Basic {
            enum Role {
                Admin
                User
            }

            struct Person {
                role: Role
            }

            fn Score(person: Person) -> int {
                match person {
                    Person { role: Role.Admin } => return 1
                    default => return 0
                }
            }
        }
        """
    )
    semantic = resolve_struct_pattern(
        _first_struct_pattern(program),
        _module_symbols(program.modules[0]),
    )
    value = semantic_pattern_to_json(semantic)

    SchemaValidator(ROOT / "frontend" / "schemas").validate_file(
        value,
        "semantic_pattern.schema.json",
    )
    assert semantic_pattern_from_json(value) == semantic
