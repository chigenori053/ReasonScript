import json
from pathlib import Path

import pytest

from frontend.language_surface.integration import compile_program
from frontend.language_surface.parser import SurfaceSyntaxError, parse


FIXTURE_DIR = Path(__file__).parent


def _compile(name: str):
    return compile_program(parse((FIXTURE_DIR / name).read_text()))[0]


def _match_coverage(ir: dict):
    for node in ir["metadata"]["function_ir"][0]["body"]:
        if node.get("node_type") == "MatchExpressionIRNode":
            return node["coverage"]
    raise AssertionError("MatchExpressionIRNode coverage not found")


def test_sex_001_literal_only_struct_match_is_non_exhaustive():
    with pytest.raises(SurfaceSyntaxError, match="TV-8 NonExhaustiveStructMatch"):
        parse((FIXTURE_DIR / "sex_001.rsn").read_text())


def test_sex_002_binding_pattern_is_exhaustive():
    coverage = _match_coverage(_compile("sex_002.rsn"))

    assert coverage == {
        "struct_name": "Point",
        "binding_pattern_present": True,
        "empty_pattern_present": False,
        "default_present": False,
        "coverage": "complete",
    }


def test_sex_003_empty_struct_pattern_is_exhaustive():
    coverage = _match_coverage(_compile("sex_003.rsn"))

    assert coverage == {
        "struct_name": "Point",
        "binding_pattern_present": False,
        "empty_pattern_present": True,
        "default_present": False,
        "coverage": "complete",
    }


def test_sex_004_default_branch_is_exhaustive():
    coverage = _match_coverage(_compile("sex_004.rsn"))

    assert coverage["struct_name"] == "Point"
    assert coverage["default_present"] is True
    assert coverage["coverage"] == "complete"


def test_sex_005_nested_empty_pattern_is_exhaustive():
    coverage = _match_coverage(_compile("sex_005.rsn"))

    assert coverage["struct_name"] == "Person"
    assert coverage["coverage"] == "complete"


def test_sex_006_nested_literal_only_pattern_is_non_exhaustive():
    with pytest.raises(SurfaceSyntaxError, match="TV-8 NonExhaustiveStructMatch"):
        parse((FIXTURE_DIR / "sex_006.rsn").read_text())


def test_sex_007_coverage_metadata_is_deterministic():
    first = _match_coverage(_compile("sex_007.rsn"))
    second = _match_coverage(_compile("sex_007.rsn"))

    assert first["coverage"] == "complete"
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
