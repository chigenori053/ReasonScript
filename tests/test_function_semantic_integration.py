import pytest

from frontend.ast import to_json_value as semantic_to_json_value
from frontend.language_surface.integration import compile_program, project_program
from frontend.language_surface.nodes import to_json_value as surface_to_json_value
from frontend.language_surface.parser import SurfaceSyntaxError, parse
from playground.backend.analyzer import analyze_ir
from playground.backend.engine import build_execution_plan, extract_knowledge, simulate


def _pipeline(source: str):
    program = parse(source)
    semantic = semantic_to_json_value(project_program(program)[0])
    ir = compile_program(program)[0]
    sim = simulate(ir)
    return {
        "program": program,
        "ast": surface_to_json_value(program),
        "semantic": semantic,
        "ir": ir,
        "plan": build_execution_plan(ir),
        "simulation": sim,
        "knowledge": extract_knowledge(ir, sim),
        "analysis": analyze_ir(ir, sim),
    }


def test_fsi_001_function_declaration_reaches_ast_semantic_and_ir():
    result = _pipeline(
        """
        module Basic {
            fn Value() -> int {
                return 42
            }
        }
        """
    )

    body_types = [node["node_type"] for node in result["ast"]["modules"][0]["body"]]
    semantic_functions = next(
        item["value"]
        for item in result["semantic"]["metadata"]
        if item["key"] == "semantic_functions"
    )
    assert "FunctionDeclarationNode" in body_types
    assert semantic_functions[0]["node_type"] == "SemanticFunctionNode"
    assert result["ir"]["metadata"]["function_ir"][0]["node_type"] == "FunctionIRNode"
    assert result["knowledge"]["knowledge_count"] == 0


def test_fsi_002_function_call_from_calculation_executes_and_keeps_evidence():
    result = _pipeline(
        """
        module Basic {
            fn Value() -> int {
                return 42
            }
            calculation Result {
                result = Value()
            }
        }
        """
    )

    assert result["simulation"]["success"] is True
    assert result["knowledge"]["knowledge_count"] == 1
    assert result["ir"]["metadata"]["function_calls"][0]["function"] == "Basic.Value"
    assert ["Value", "Result"] in result["analysis"]["dependency_graph"]["dependencies"]
    assert [step["target"] for step in result["plan"]["selected_steps"]] == [
        "Value.return",
        "Result.state.result",
    ]


def test_fsi_003_function_with_parameter_is_callable():
    result = _pipeline(
        """
        module Basic {
            fn Double(x: int) -> int {
                return x * 2
            }
            calculation Result {
                result = Double(10)
            }
        }
        """
    )

    assert result["simulation"]["success"] is True
    assert result["ir"]["metadata"]["function_symbols"][0]["parameters"] == [
        {"name": "x", "type": "int"}
    ]


def test_fsi_004_argument_type_mismatch_is_fn_005():
    with pytest.raises(SurfaceSyntaxError, match="FN-005"):
        parse(
            """
            module Basic {
                fn Double(x: int) -> int {
                    return x * 2
                }
                calculation Result {
                    result = Double(true)
                }
            }
            """
        )


def test_fsi_005_missing_return_is_fcf_001():
    with pytest.raises(SurfaceSyntaxError, match="FCF-001"):
        parse(
            """
            module Basic {
                fn Value() -> int {
                }
            }
            """
        )


def test_fcf_001_if_return_then_fallthrough_return_passes():
    result = _pipeline(
        """
        module Basic {
            fn Select(flag: bool) -> int {
                if flag {
                    return 1
                }
                return 0
            }
        }
        """
    )

    function_ir = result["ir"]["metadata"]["function_ir"][0]
    body_types = [node["node_type"] for node in function_ir["body"]]
    assert "ConditionalBranchIRNode" in body_types
    assert [node["path"] for node in function_ir["body"] if node["node_type"] == "ReturnIRNode"] == [
        "true",
        "false",
    ]


def test_fcf_002_missing_fallthrough_return_is_fcf_001():
    with pytest.raises(SurfaceSyntaxError, match="FCF-001"):
        parse(
            """
            module Basic {
                fn Select(flag: bool) -> int {
                    if flag {
                        return 1
                    }
                }
            }
            """
        )


def test_fcf_003_unreachable_return_is_fcf_002():
    with pytest.raises(SurfaceSyntaxError, match="FCF-002"):
        parse(
            """
            module Basic {
                fn Value() -> int {
                    return 1
                    return 2
                }
            }
            """
        )


def test_fcf_004_if_condition_must_be_bool():
    with pytest.raises(SurfaceSyntaxError, match="FCF-004"):
        parse(
            """
            module Basic {
                fn Value(x: int) -> int {
                    if x {
                        return 1
                    }
                    return 0
                }
            }
            """
        )


def test_fcf_005_function_call_keeps_branch_evidence():
    result = _pipeline(
        """
        module Basic {
            fn Select(flag: bool) -> int {
                if flag {
                    return 1
                }
                return 0
            }
            calculation Result {
                result = Select(true)
            }
        }
        """
    )

    assert result["plan"]["reachable"] is True
    assert result["plan"]["distance"] >= 2
    assert result["knowledge"]["knowledge_count"] >= 1
    assert result["plan"]["selected_steps"][0]["target"] in {
        "Select.return.true",
        "Select.return.false",
    }


def test_fsi_006_duplicate_function_is_fn_001():
    with pytest.raises(SurfaceSyntaxError, match="FN-001"):
        parse(
            """
            module Basic {
                fn Value() -> int {
                    return 1
                }
                fn Value() -> int {
                    return 2
                }
            }
            """
        )
