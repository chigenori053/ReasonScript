import json

import pytest

from frontend.language_surface.integration import compile_program
from frontend.language_surface.parser import SurfaceSyntaxError, parse


def _compile(source: str):
    return compile_program(parse(source))[0]


TWO_COLOR_DEFAULT_SOURCE = """
module Basic {
    enum Color {
        Red
        Blue
    }

    fn Score(color: Color) -> int {
        match color {
            Color.Red => return 1
            default => return 0
        }
    }

    calculation Result {
        result = Score(Color.Blue)
    }
}
"""


THREE_COLOR_DEFAULT_SOURCE = """
module Basic {
    enum Color {
        Red
        Blue
        Green
    }

    fn Score(color: Color) -> int {
        match color {
            Color.Red => return 1
            default => return 0
        }
    }

    calculation Result {
        result = Score(Color.Green)
    }
}
"""


def _match_node(ir: dict):
    return ir["metadata"]["function_ir"][0]["body"][0]


def test_msi_301_default_satisfies_remaining_enum_variant():
    ir = _compile(TWO_COLOR_DEFAULT_SOURCE)

    coverage = _match_node(ir)["coverage"]
    assert coverage == {
        "enum_name": "Color",
        "explicit_variants": ["Color.Red"],
        "default_present": True,
        "covered_variants": ["Color.Red", "Color.Blue"],
        "missing_variants": [],
    }


def test_msi_302_default_covers_multiple_remaining_enum_variants():
    ir = _compile(THREE_COLOR_DEFAULT_SOURCE)

    coverage = _match_node(ir)["coverage"]
    assert coverage["default_present"] is True
    assert coverage["covered_variants"] == [
        "Color.Red",
        "Color.Blue",
        "Color.Green",
    ]
    assert coverage["missing_variants"] == []


def test_msi_303_missing_variant_is_reported_deterministically():
    with pytest.raises(
        SurfaceSyntaxError,
        match=r"TV-7 NonExhaustiveMatch Missing: Color\.Blue",
    ):
        _compile(
            """
            module Basic {
                enum Color {
                    Red
                    Blue
                }

                fn Score(color: Color) -> int {
                    match color {
                        Color.Red => return 1
                    }
                }

                calculation Result {
                    result = Score(Color.Red)
                }
            }
            """
        )


def test_msi_304_missing_variant_reporting_keeps_enum_order():
    with pytest.raises(
        SurfaceSyntaxError,
        match=r"TV-7 NonExhaustiveMatch Missing: Color\.Green",
    ):
        _compile(
            """
            module Basic {
                enum Color {
                    Red
                    Blue
                    Green
                }

                fn Score(color: Color) -> int {
                    match color {
                        Color.Red => return 1
                        Color.Blue => return 2
                    }
                }

                calculation Result {
                    result = Score(Color.Red)
                }
            }
            """
        )


def test_msi_305_default_does_not_hide_duplicate_pattern_error():
    with pytest.raises(SurfaceSyntaxError, match="MSI-001"):
        _compile(
            """
            module Basic {
                enum Color {
                    Red
                    Blue
                    Green
                }

                fn Score(color: Color) -> int {
                    match color {
                        Color.Red => return 1
                        Color.Red => return 2
                        default => return 0
                    }
                }

                calculation Result {
                    result = Score(Color.Red)
                }
            }
            """
        )


def test_msi_306_repeated_compilation_produces_identical_coverage():
    first = _compile(THREE_COLOR_DEFAULT_SOURCE)
    second = _compile(THREE_COLOR_DEFAULT_SOURCE)

    assert json.dumps(_match_node(first)["coverage"], sort_keys=True) == json.dumps(
        _match_node(second)["coverage"],
        sort_keys=True,
    )
