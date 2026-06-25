import pytest

from frontend.language_surface import (
    DefaultPatternNode,
    IdentifierPatternNode,
    LiteralPatternNode,
    QualifiedPatternNode,
    WildcardPatternNode,
    parse_pattern,
)
from frontend.language_surface.integration import compile_program
from frontend.language_surface.parser import SurfaceSyntaxError, parse
from playground.backend.engine import build_execution_plan, simulate


def _pipeline(source: str):
    ir = compile_program(parse(source))[0]
    simulation = simulate(ir)
    return {
        "ir": ir,
        "plan": build_execution_plan(ir),
        "simulation": simulation,
    }


def test_pt_p001_p004_pattern_node_hierarchy():
    assert isinstance(parse_pattern("_").pattern, WildcardPatternNode)
    assert isinstance(parse_pattern("Admin").pattern, IdentifierPatternNode)
    assert isinstance(parse_pattern("Role.Admin").pattern, QualifiedPatternNode)
    assert isinstance(parse_pattern("1").pattern, LiteralPatternNode)
    assert isinstance(parse_pattern("default").pattern, DefaultPatternNode)


def test_pt_ir001_pattern_decision_node_preserves_source_order():
    result = _pipeline(
        """
        module Basic {
            fn Select(x: int) -> int {
                match x {
                    1 => return 10
                    2 => return 20
                    default => return 0
                }
            }

            calculation Result {
                result = Select(2)
            }
        }
        """
    )

    body = result["ir"]["metadata"]["function_ir"][0]["body"]
    decision = next(node for node in body if node["node_type"] == "PatternDecisionNode")
    assert [arm["branch_index"] for arm in decision["arms"]] == [0, 1, 2]
    assert [arm["pattern"] for arm in decision["arms"]] == [1, 2, "default"]
    assert result["plan"]["selected_branch"] == "Select.match.2"


def test_pt_q001_qualified_enum_pattern_resolves_and_executes():
    result = _pipeline(
        """
        module Basic {
            enum Role {
                Admin
                User
            }

            fn Score(role: Role) -> int {
                match role {
                    Role.Admin => return 1
                    Role.User => return 2
                }
            }

            calculation Result {
                result = Score(Role.Admin)
            }
        }
        """
    )

    match_node = result["ir"]["metadata"]["function_ir"][0]["body"][0]
    assert match_node["cases"][0]["pattern"] == {
        "node_type": "EnumValuePatternNode",
        "enum_name": "Role",
        "value_name": "Admin",
    }
    decision = next(
        node
        for node in result["ir"]["metadata"]["function_ir"][0]["body"]
        if node["node_type"] == "PatternDecisionNode"
    )
    assert decision["arms"][0]["pattern"] == {
        "node_type": "EnumVariantReferenceNode",
        "enum": "Role",
        "variant": "Admin",
        "symbol_id": "Role.Admin",
    }
    assert result["simulation"]["selected_branch"] == "Score.match.Role.Admin"


def test_pt_q002_unqualified_enum_pattern_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="ESR-003"):
        parse(
            """
            module Basic {
                enum Role {
                    Admin
                    User
                }

                fn Score(role: Role) -> int {
                    match role {
                        Admin => return 1
                        Role.User => return 2
                    }
                }
            }
            """
        )


def test_pt_q003_unknown_pattern_namespace_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="PT-009"):
        parse(
            """
            module Basic {
                enum Role {
                    Admin
                }

                fn Score(role: Role) -> int {
                    match role {
                        Unknown.Admin => return 1
                        default => return 0
                    }
                }
            }
            """
        )


def test_pt_q004_unknown_qualified_variant_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="PT-010"):
        parse(
            """
            module Basic {
                enum Role {
                    Admin
                }

                fn Score(role: Role) -> int {
                    match role {
                        Role.Unknown => return 1
                        default => return 0
                    }
                }
            }
            """
        )


def test_pt_q005_imported_enum_alias_pattern_resolves():
    source = """
    module Lib {
        export enum Role {
            Admin
            User
        }
    }

    module Basic {
        import Lib.Role as UserRole

        fn Score(role: UserRole) -> int {
            match role {
                UserRole.Admin => return 1
                UserRole.User => return 2
            }
        }

        calculation Result {
            result = Score(UserRole.Admin)
        }
    }
    """
    ir = compile_program(parse(source))[1]
    simulation = simulate(ir)
    result = {
        "ir": ir,
        "plan": build_execution_plan(ir),
        "simulation": simulation,
    }

    assert result["simulation"]["selected_branch"] == "Score.match.UserRole.Admin"


def test_pt_005_literal_type_mismatch_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="PT-005"):
        parse(
            """
            module Basic {
                fn Select(flag: bool) -> int {
                    match flag {
                        1 => return 1
                        default => return 0
                    }
                }
            }
            """
        )


def test_pt_004_unknown_identifier_pattern_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="PT-004"):
        parse(
            """
            module Basic {
                enum Role {
                    Admin
                }

                fn Score(role: Role) -> int {
                    match role {
                        Unknown => return 1
                        default => return 0
                    }
                }
            }
            """
        )


def test_pt_006_duplicate_wildcard_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="PT-006"):
        parse(
            """
            module Basic {
                fn Select(x: int) -> int {
                    match x {
                        _ => return 1
                        _ => return 2
                    }
                }
            }
            """
        )


def test_pt_007_wildcard_before_other_arm_is_unreachable():
    with pytest.raises(SurfaceSyntaxError, match="PT-007"):
        parse(
            """
            module Basic {
                fn Select(x: int) -> int {
                    match x {
                        _ => return 1
                        2 => return 2
                    }
                }
            }
            """
        )


def test_pt_p005_unsupported_patterns_have_dedicated_diagnostics():
    with pytest.raises(SurfaceSyntaxError, match="PT-205"):
        parse(
            """
            module Basic {
                fn Select(x: int) -> int {
                    match x {
                        Person { name: "a" } => return 1
                        default => return 0
                    }
                }
            }
            """
        )
    with pytest.raises(SurfaceSyntaxError, match="PT-206"):
        parse(
            """
            module Basic {
                fn Select(x: int) -> int {
                    match x {
                        Some(value) => return 1
                        default => return 0
                    }
                }
            }
            """
        )
