import json

import pytest

from frontend.language_surface.integration import compile_program
from frontend.language_surface.parser import SurfaceSyntaxError, parse


def _compile(source: str):
    return compile_program(parse(source))[0]


GET_SOURCE = """
module Basic {
    enum Color {
        Red
        Blue
    }

    fn Get() -> Color {
        return VALUE
    }

    calculation Result {
        result = Get()
    }
}
"""


def test_esr_001_return_color_red_resolves():
    ir = _compile(GET_SOURCE.replace("VALUE", "Color.Red"))

    symbols = ir["metadata"]["enum_symbols"]
    assert {
        "symbol_type": "EnumVariantSymbol",
        "enum_name": "Color",
        "variant_name": "Red",
        "qualified_name": "Color.Red",
    } in symbols
    transition = next(
        item
        for item in ir["transitions"]
        if item["relation"] == "FunctionReturnTransition"
    )
    assert transition["effect"]["return_value"] == {
        "node_type": "EnumVariantIRNode",
        "enum_name": "Color",
        "variant_name": "Red",
    }


def test_esr_002_return_color_blue_resolves():
    ir = _compile(GET_SOURCE.replace("VALUE", "Color.Blue"))

    return_node = next(
        item
        for item in ir["metadata"]["function_ir"][0]["body"]
        if item["node_type"] == "ReturnIRNode"
    )
    assert return_node["semantic_reference"] == {
        "node_type": "EnumVariantReferenceNode",
        "enum_name": "Color",
        "variant_name": "Blue",
        "qualified_name": "Color.Blue",
    }


def test_esr_003_unqualified_variant_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="ESR-003"):
        _compile(GET_SOURCE.replace("VALUE", "Red"))


def test_esr_004_unknown_variant_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="ESR-001"):
        _compile(GET_SOURCE.replace("VALUE", "Color.Green"))


def test_esr_005_function_argument_resolution_sets_enum_context():
    ir = _compile(
        """
        module Basic {
            enum Color {
                Red
                Blue
            }

            fn Score(color: Color) -> int {
                return 1
            }

            calculation Result {
                result = Score(Color.Red)
            }
        }
        """
    )

    transition = next(
        item
        for item in ir["transitions"]
        if item["relation"] == "FunctionReturnTransition"
    )
    assert transition["effect"]["evaluation_context"]["color"] == {
        "enum": "Color",
        "variant": "Red",
    }
    call = ir["metadata"]["function_calls"][0]
    assert call["arguments"] == [
        {
            "node_type": "EnumVariantIRNode",
            "enum_name": "Color",
            "variant_name": "Red",
        }
    ]


def test_esr_006_repeated_compilation_is_deterministic():
    first = _compile(GET_SOURCE.replace("VALUE", "Color.Red"))
    second = _compile(GET_SOURCE.replace("VALUE", "Color.Red"))

    assert json.dumps(first, sort_keys=True, default=str) == json.dumps(
        second,
        sort_keys=True,
        default=str,
    )


def test_esr_unknown_enum_is_rejected():
    with pytest.raises(SurfaceSyntaxError, match="ESR-002"):
        _compile(GET_SOURCE.replace("VALUE", "Animal.Dog"))
