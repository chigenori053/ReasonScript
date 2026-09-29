"""Numeric & data foundation behavior through the production execution path.

Every case runs ReasonScript source through `reason run` (static
validation, Computation IR lowering, and the native Rust runtime). No
helper here computes, serializes, or writes the values under test.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def native_runtime_host() -> Path:
    from frontend.computation_ir.rust_bridge import find_binary

    binary = find_binary()
    if binary is not None:
        return binary
    completed = subprocess.run(
        ["cargo", "build", "-p", "reasonscript-computation-runtime-cli"],
        cwd=ROOT / "ReasonRuntime",
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    binary = find_binary()
    assert binary is not None
    return binary


def _run(tmp_path: Path, body: str, *, allow_write: bool = False, name: str = "main.rsn") -> dict[str, Any]:
    from scripts.reason_cli import _run_result

    source = tmp_path / name
    source.write_text(f"module Foundation {{\n{body}\n}}\n", encoding="utf-8")
    return _run_result(source, "normal", include_trace=False, allow_write=allow_write)


def _values(tmp_path: Path, body: str, **options: Any) -> dict[str, Any]:
    result = _run(tmp_path, body, **options)
    assert result["ok"], result["diagnostics"]
    assert result["execution_mode"] == "integrated-rust"
    return result["runtime_result"]["calculations"]


def _error(tmp_path: Path, body: str, **options: Any) -> dict[str, Any]:
    result = _run(tmp_path, body, **options)
    assert not result["ok"]
    return result["diagnostics"][-1]


def _runtime_error(tmp_path: Path, body: str, **options: Any) -> str:
    diagnostic = _error(tmp_path, body, **options)
    assert diagnostic["stage"] == "runtime", diagnostic
    return diagnostic["code"]


def _static_error(tmp_path: Path, body: str) -> str:
    """`reason check` must reject the source before anything executes."""
    diagnostic = _error(tmp_path, body)
    assert diagnostic["stage"] != "runtime", diagnostic
    return f"{diagnostic['code']} {diagnostic['message']}"


def _calc(name: str, result_type: str, expression: str) -> str:
    return f"  calculation {name} -> {result_type} {{\n    result = {expression}\n  }}\n"


# ------------------------------------------------------------ GND-1 / GND-2


def test_mixed_numeric_arithmetic_promotes_to_float(tmp_path: Path) -> None:
    # Groups A-E and the §50 mandatory expressions.
    body = "".join([
        _calc("A", "int", "2 + 3"),
        _calc("B", "float", "1.5 + 2.25"),
        _calc("C1", "float", "2 + 0.5 * 4"),
        _calc("C2", "float", "1 + 0.25"),
        _calc("D", "float", "1.5 + 2"),
        _calc("E1", "float", "3 * 0.5"),
        _calc("E2", "float", "5.0 / 2"),
        _calc("E3", "float", "7 / 2"),
        _calc("E4", "float", "7 % 2.5"),
    ])
    values = _values(tmp_path, body)
    assert values == {
        "A": 5, "B": 3.75, "C1": 4.0, "C2": 1.25, "D": 3.5,
        "E1": 1.5, "E2": 2.5, "E3": 3.5, "E4": 2.0,
    }
    assert isinstance(values["A"], int)
    assert all(isinstance(values[key], float) for key in ("C1", "C2", "D", "E1", "E2"))


def test_mixed_numeric_arithmetic_through_bindings(tmp_path: Path) -> None:
    # Not constant-folded: the runtime itself must promote.
    body = """
  fn Scale(count: int, factor: float) -> float {
    return count * factor + count
  }
  calculation Mixed -> float {
    let count = 3
    let factor = 0.5
    result = Scale(count, factor) - count / 2
  }
"""
    assert _values(tmp_path, body) == {"Mixed": 3.0}


def test_same_type_comparison_rules_are_unchanged(tmp_path: Path) -> None:
    assert "TYPE-V005" in _static_error(tmp_path, _calc("Mixed", "bool", '1 == "1"'))
    assert "TYPE-V005" in _static_error(tmp_path, _calc("Mixed", "bool", "1.0 < true"))


def test_mixed_numeric_comparison(tmp_path: Path) -> None:
    # Group F.
    body = "".join([
        _calc("Less", "bool", "1 < 1.5"),
        _calc("GreaterEqual", "bool", "2.0 >= 2"),
        _calc("Equal", "bool", "3 == 3.0"),
        _calc("NotEqual", "bool", "3 != 3.5"),
    ]) + """
  calculation Runtime -> bool {
    let whole = 9007199254740993
    let near = 9007199254740992.0
    result = whole > near
  }
"""
    assert _values(tmp_path, body) == {
        "Less": True, "GreaterEqual": True, "Equal": True, "NotEqual": True,
        # Exact comparison: 2^53 + 1 is not rounded to 2^53 first.
        "Runtime": True,
    }


def test_exact_and_approximate_float_equality(tmp_path: Path) -> None:
    # Groups G and H.
    body = "".join([
        _calc("Exact", "bool", "0.1 + 0.2 == 0.3"),
        _calc("Approx", "bool", "math.approx_equal(0.1 + 0.2, 0.3, 1.0e-12)"),
        _calc("Outside", "bool", "math.approx_equal(1.0, 1.1, 0.01)"),
        _calc("Boundary", "bool", "math.approx_equal(1, 1.5, 0.5)"),
        _calc("LargeDistinct", "bool", "math.approx_equal(9007199254740992, 9007199254740993, 0)"),
        _calc("MixedDistinct", "bool", "math.approx_equal(9007199254740993, 9007199254740992.0, 0.0)"),
        _calc("LargeWithin", "bool", "math.approx_equal(9007199254740992, 9007199254740993, 1)"),
    ])
    assert _values(tmp_path, body) == {
        "Exact": False, "Approx": True, "Outside": False, "Boundary": True,
        "LargeDistinct": False, "MixedDistinct": False, "LargeWithin": True,
    }
    assert _runtime_error(tmp_path, _calc("Bad", "bool", "math.approx_equal(1.0, 1.0, -0.1)")) == "MATH-004"


def test_division_by_zero_is_explicit(tmp_path: Path) -> None:
    # Group I.
    for expression in ("1 / zero", "1.0 / zero", "1 / 0.0", "5 % zero"):
        body = f"""
  calculation Divide -> bool {{
    let zero = 0
    result = {expression} > 0
  }}
"""
        assert _runtime_error(tmp_path, body) == "RT-ARITH-001", expression


@pytest.mark.parametrize(
    "expression",
    [
        "1.0e308 * 10.0",
        "large * large",
        "9223372036854775807 + 1",
        "limit * 2",
        "0 - limit - 2",
    ],
)
def test_overflow_is_a_numeric_diagnostic(tmp_path: Path, expression: str) -> None:
    # Group J: never IR-DECODE-001, never wrapped or infinite values.
    body = f"""
  calculation Overflow -> bool {{
    let large = 1.0e200
    let limit = 9223372036854775807
    let value = {expression}
    result = value > 0
  }}
"""
    assert _runtime_error(tmp_path, body) == "RT-NUM-OVERFLOW"


def test_underflow_and_signed_zero_are_defined(tmp_path: Path) -> None:
    # Groups K and L (-0.0).
    body = "".join([
        _calc("Subnormal", "float", "1.0e-300 * 1.0e-10"),
        _calc("Zero", "float", "1.0e-300 * 1.0e-300"),
        _calc("NegativeZero", "string", "serialize.json(-1.0e-300 * 1.0e-300)"),
        _calc("Small", "float", "1.0e-300"),
        _calc("Large", "float", "1.0e300"),
    ])
    values = _values(tmp_path, body)
    assert values["Subnormal"] == 1e-310
    assert values["Zero"] == 0.0
    assert values["NegativeZero"] == "-0.0"
    assert values["Small"] == 1e-300 and values["Large"] == 1e300


def test_non_finite_values_never_enter_computation(tmp_path: Path) -> None:
    # Group L: literals are rejected statically, operations at runtime.
    assert "FloatLiteralNode.value is invalid" in _static_error(tmp_path, _calc("Literal", "float", "1.0e400"))
    assert "must fit int64" in _static_error(tmp_path, _calc("Literal", "int", "99999999999999999999"))
    assert _runtime_error(tmp_path, _calc("Exp", "float", "math.exp(1000.0)")) == "RT-NUM-OVERFLOW"


def test_float_to_int_conversion_truncates_and_rejects_out_of_range(tmp_path: Path) -> None:
    body = "".join([
        _calc("Down", "int", "int(2.9)"),
        _calc("TowardZero", "int", "int(-2.9)"),
        _calc("Widen", "float", "float(3)"),
        _calc("Identity", "int", "int(9007199254740993)"),
    ])
    assert _values(tmp_path, body) == {
        "Down": 2, "TowardZero": -2, "Widen": 3.0, "Identity": 9007199254740993,
    }
    body = """
  calculation TooLarge -> int {
    let value = 1.0e19
    result = int(value)
  }
"""
    assert _runtime_error(tmp_path, body) == "RT-NUM-CONVERSION"


# ------------------------------------------------------------------ GND-3


def test_integer_and_negative_step_sequences(tmp_path: Path) -> None:
    # Groups M and O plus empty-direction cases.
    body = "".join([
        _calc("Up", "[int]", "sequence.range(0, 5, 1)"),
        _calc("Down", "[int]", "sequence.range(5, 0, -1)"),
        _calc("Stride", "[int]", "sequence.range(0, 10, 3)"),
        _calc("Empty", "[int]", "sequence.range(0, 0, 1)"),
        _calc("Opposite", "[int]", "sequence.range(0, 5, -1)"),
    ])
    assert _values(tmp_path, body) == {
        "Up": [0, 1, 2, 3, 4],
        "Down": [5, 4, 3, 2, 1],
        "Stride": [0, 3, 6, 9],
        "Empty": [],
        "Opposite": [],
    }


def test_floating_sequence_is_index_based(tmp_path: Path) -> None:
    # Group N: value(i) = start + step * i, end exclusive.
    body = "".join([
        _calc("Tenths", "[float]", "sequence.range(0.0, 1.0, 0.1)"),
        _calc("Mixed", "[float]", "sequence.range(0, 1, 0.25)"),
        _calc("Falling", "[float]", "sequence.range(1.0, 0.0, -0.5)"),
    ])
    values = _values(tmp_path, body)
    assert len(values["Tenths"]) == 10
    assert values["Tenths"][:4] == [0.0, 0.1, 0.2, 0.30000000000000004]
    assert values["Tenths"][-1] == 0.9
    assert values["Mixed"] == [0.0, 0.25, 0.5, 0.75]
    assert values["Falling"] == [1.0, 0.5]


def test_zero_step_fails_immediately(tmp_path: Path) -> None:
    # Group P: a literal zero step is rejected by `reason check`; a
    # computed one by the runtime, before any element is produced.
    assert "SEQ-004" in _static_error(tmp_path, _calc("Zero", "[int]", "sequence.range(0, 10, 0)"))
    body = """
  calculation Zero -> [float] {
    let step = 0.0
    result = sequence.range(0.0, 10.0, step)
  }
"""
    assert _runtime_error(tmp_path, body) == "SEQ-004"


def test_sequence_resource_limit(tmp_path: Path) -> None:
    # Group Q: rejected before allocation, far above the default limit.
    for result_type, expression in (
        ("[int]", "sequence.range(0, 9223372036854775807, 1)"),
        ("[int]", "sequence.range(-9223372036854775807, 9223372036854775807, 2)"),
        ("[float]", "sequence.range(0.0, 1.0e300, 1.0e-300)"),
        ("[float]", "sequence.range(0.0, 2000000.0, 1)"),
    ):
        body = _calc("Huge", result_type, expression)
        assert _runtime_error(tmp_path, body) == "SEQ-005", expression


def test_sequence_limit_is_configurable(tmp_path: Path) -> None:
    from frontend.computation_ir import lower_program
    from frontend.computation_ir.optimizer import optimize_program
    from frontend.computation_ir.rust_bridge import run_ir
    from frontend.language_surface.parser import parse

    source = "module Limit {\n" + _calc("Values", "[int]", "sequence.range(0, 11, 1)") + "}\n"
    document = optimize_program(lower_program(parse(source)))
    limited = run_ir(document, cwd=tmp_path, limits={"max_sequence_elements": 10})
    assert not limited.ok and limited.error_code == "SEQ-005"
    allowed = run_ir(document, cwd=tmp_path, limits={"max_sequence_elements": 11})
    assert allowed.ok and allowed.calculation_results == {"Values": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}


# ------------------------------------------------------------------ GND-4


def test_abs_min_max_floor_ceil_round(tmp_path: Path) -> None:
    # Groups R and S, including the declared output types.
    body = "".join([
        _calc("AbsInt", "int", "math.abs(-3)"),
        _calc("AbsFloat", "float", "math.abs(-2.5)"),
        _calc("MinInt", "int", "math.min(2, 7)"),
        _calc("MaxMixed", "float", "math.max(2, 1.5)"),
        _calc("Floor", "float", "math.floor(-1.5)"),
        _calc("Ceil", "float", "math.ceil(1.2)"),
        _calc("RoundHalfUp", "float", "math.round(2.5)"),
        _calc("RoundHalfDown", "float", "math.round(-2.5)"),
        _calc("RoundInt", "int", "math.round(4)"),
    ])
    values = _values(tmp_path, body)
    assert values == {
        "AbsInt": 3, "AbsFloat": 2.5, "MinInt": 2, "MaxMixed": 2.0,
        "Floor": -2.0, "Ceil": 2.0, "RoundHalfUp": 3.0, "RoundHalfDown": -3.0,
        "RoundInt": 4,
    }
    assert isinstance(values["MaxMixed"], float) and isinstance(values["RoundInt"], int)


def test_sqrt_trig_log_exp_identities(tmp_path: Path) -> None:
    # Groups T, U, V (§53) within explicit tolerances.
    tolerance = "1.0e-12"
    checks = {
        "Sqrt": "math.sqrt(4.0), 2.0",
        "SqrtInt": "math.sqrt(2), 1.4142135623730951",
        "Sin": "math.sin(0.0), 0.0",
        "Cos": "math.cos(0.0), 1.0",
        "Tan": "math.tan(0.7853981633974483), 1.0",
        "HalfPi": "math.sin(1.5707963267948966), 1.0",
        "Exp": "math.exp(0.0), 1.0",
        "Log": "math.log(1.0), 0.0",
        "RoundTrip": "math.log(math.exp(2.5)), 2.5",
    }
    body = "".join(
        _calc(name, "bool", f"math.approx_equal({arguments}, {tolerance})")
        for name, arguments in checks.items()
    )
    assert _values(tmp_path, body) == {name: True for name in checks}
    typed = _values(tmp_path, _calc("SinInt", "float", "math.sin(0)"))
    assert typed == {"SinInt": 0.0} and isinstance(typed["SinInt"], float)


@pytest.mark.parametrize("expression", ["math.sqrt(-1)", "math.log(0)", "math.log(-1.0)"])
def test_scalar_math_domain_errors(tmp_path: Path, expression: str) -> None:
    # Group W.
    assert _runtime_error(tmp_path, _calc("Domain", "float", expression)) == "MATH-004"


def test_scalar_math_static_contract(tmp_path: Path) -> None:
    assert "MATH-003" in _static_error(tmp_path, _calc("Bad", "float", 'math.sqrt("4")'))
    assert "MATH-002" in _static_error(tmp_path, _calc("Bad", "float", "math.min(1.0)"))
    assert "MATH-001" in _static_error(tmp_path, _calc("Bad", "float", "math.cbrt(8.0)"))
    body = """
  calculation Bad -> float {
    let builder = array.builder()
    result = math.sqrt(builder)
  }
"""
    assert "MATH-003" in _static_error(tmp_path, body)
    # The declared result type is enforced statically.
    assert "sqrt" not in _static_error(tmp_path, _calc("Bad", "int", "math.sqrt(4)"))


# ------------------------------------------------------------------ GND-5


def test_primitive_serialization(tmp_path: Path) -> None:
    # Group X.
    body = "".join([
        _calc("Int", "string", "serialize.json(-42)"),
        _calc("Float", "string", "serialize.json(0.1 + 0.2)"),
        _calc("Whole", "string", "serialize.json(2.0)"),
        _calc("Large", "string", "serialize.json(1.0e21)"),
        _calc("Tiny", "string", "serialize.json(1.5e-8)"),
        _calc("Bool", "string", "serialize.json(true)"),
        _calc("Null", "string", "serialize.json(null)"),
        _calc("None", "string", "serialize.json(none)"),
        _calc("Some", "string", "serialize.json(some(3))"),
        _calc("Text", "string", 'serialize.json("line\\n\\"q\\" é")'),
        _calc("Array", "string", "serialize.json([1, 2, 3])"),
    ])
    assert _values(tmp_path, body) == {
        "Int": "-42",
        "Float": "0.30000000000000004",
        "Whole": "2.0",
        "Large": "1e21",
        "Tiny": "1.5e-8",
        "Bool": "true",
        "Null": "null",
        "None": "null",
        "Some": "3",
        "Text": '"line\\n\\"q\\" é"',
        "Array": "[1,2,3]",
    }


def test_nested_struct_serialization_is_canonical(tmp_path: Path) -> None:
    # Groups Y and Z: sorted fields, no whitespace, nested arrays/structs.
    body = """
  struct Point {
    y: float
    x: float
  }
  struct Series {
    name: string
    points: [Point]
    tags: [string]
  }
  calculation Encoded -> string {
    let series = Series {
      name: "curve"
      tags: ["b", "a"]
      points: [Point { y: 1.0, x: 0.0 }, Point { x: 0.5, y: -0.0 }]
    }
    result = serialize.json(series)
  }
"""
    encoded = _values(tmp_path, body)["Encoded"]
    assert encoded == (
        '{"name":"curve","points":[{"x":0.0,"y":1.0},{"x":0.5,"y":-0.0}],"tags":["b","a"]}'
    )
    assert json.loads(encoded)["points"][1]["x"] == 0.5


def test_serialization_rejects_runtime_handles(tmp_path: Path) -> None:
    body = """
  calculation Handle -> string {
    let values = tensor.create([1.0, 2.0], "f64")
    result = serialize.json(values)
  }
"""
    assert "SER-003" in _static_error(tmp_path, body)
    body = """
  calculation Builder -> string {
    let builder = array.builder()
    result = serialize.json(builder)
  }
"""
    assert "SER-003" in _static_error(tmp_path, body)


def test_serialization_is_deterministic(tmp_path: Path) -> None:
    # Group AE: repeated serialization of equivalent values is identical,
    # within one run and across runs.
    body = """
  struct Row {
    label: string
    value: float
  }
  fn Encode(scale: float) -> string {
    let rows = [Row { value: 0.1 * scale, label: "a" }, Row { label: "b", value: scale / 3 }]
    return serialize.json(rows)
  }
  calculation Same -> bool {
    result = Encode(3.0) == Encode(3.0)
  }
  calculation Text -> string {
    result = Encode(3.0)
  }
"""
    first = _values(tmp_path, body)
    second = _values(tmp_path, body)
    assert first["Same"] is True
    assert first["Text"] == second["Text"] == (
        '[{"label":"a","value":0.30000000000000004},{"label":"b","value":1.0}]'
    )


# ------------------------------------------------------------------ GND-6


_WRITE = """
  calculation Written -> int {{
    let written = artifact.write_text({arguments})
    result = written.bytes_written
  }}
"""


def test_artifact_writes_utf8_text(tmp_path: Path) -> None:
    # Group AA.
    body = """
  calculation Written -> string {
    let written = artifact.write_text("note.txt", "héllo ✓\\n")
    result = string.concat(written.path, string.from_int(written.bytes_written))
  }
"""
    # "héllo ✓\n" is 11 UTF-8 bytes (é is 2 bytes, ✓ is 3).
    assert _values(tmp_path, body, allow_write=True) == {"Written": "note.txt11"}
    assert (tmp_path / "note.txt").read_bytes() == "héllo ✓\n".encode("utf-8")
    assert [path.name for path in tmp_path.iterdir() if path.name.startswith(".")] == []


def test_artifact_overwrite_is_explicit(tmp_path: Path) -> None:
    # Group AB.
    target = tmp_path / "out.txt"
    target.write_text("original", encoding="utf-8")
    body = _WRITE.format(arguments='"out.txt", "replacement"')
    assert _runtime_error(tmp_path, body, allow_write=True) == "ART-006"
    assert target.read_text(encoding="utf-8") == "original"
    body = _WRITE.format(arguments='"out.txt", "replacement", false')
    assert _runtime_error(tmp_path, body, allow_write=True) == "ART-006"
    body = _WRITE.format(arguments='"out.txt", "replacement", true')
    assert _values(tmp_path, body, allow_write=True) == {"Written": 11}
    assert target.read_text(encoding="utf-8") == "replacement"


@pytest.mark.parametrize(
    ("path", "code"),
    [
        ('"../escape.txt"', "ART-005"),
        ('"nested/../../escape.txt"', "ART-005"),
        ('"/tmp/absolute.txt"', "ART-005"),
        ('""', "ART-005"),
        ('"a\\\\b.txt"', "ART-005"),
        ('"missing/dir.txt"', "ART-007"),
    ],
)
def test_artifact_rejects_invalid_paths(tmp_path: Path, path: str, code: str) -> None:
    # Group AC.
    body = _WRITE.format(arguments=f'{path}, "data"')
    assert _runtime_error(tmp_path, body, allow_write=True) == code
    assert not (tmp_path.parent / "escape.txt").exists()


def test_artifact_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    (project / "link").symlink_to(outside, target_is_directory=True)
    source = project / "main.rsn"
    source.write_text(
        "module Foundation {\n" + _WRITE.format(arguments='"link/x.txt", "data"') + "}\n",
        encoding="utf-8",
    )
    from scripts.reason_cli import _run_result

    result = _run_result(source, "normal", include_trace=False, allow_write=True)
    assert not result["ok"] and result["diagnostics"][-1]["code"] == "ART-005"
    assert not (outside / "x.txt").exists()


def test_artifact_writes_into_existing_subdirectory(tmp_path: Path) -> None:
    (tmp_path / "out").mkdir()
    body = _WRITE.format(arguments='"out/data.json", "{}"')
    assert _values(tmp_path, body, allow_write=True) == {"Written": 2}
    assert (tmp_path / "out" / "data.json").read_text(encoding="utf-8") == "{}"


def test_artifact_requires_write_permission(tmp_path: Path) -> None:
    # Group AD.
    body = _WRITE.format(arguments='"denied.txt", "data"')
    assert _runtime_error(tmp_path, body, allow_write=False) == "ART-004"
    assert not (tmp_path / "denied.txt").exists()


def test_artifact_static_contract(tmp_path: Path) -> None:
    assert "ART-003" in _static_error(tmp_path, _WRITE.format(arguments='"x.txt", 42'))
    assert "ART-003" in _static_error(tmp_path, _WRITE.format(arguments='"x.txt", "a", 1'))
    assert "ART-002" in _static_error(tmp_path, _WRITE.format(arguments='"x.txt"'))


# ------------------------------------------------------------------- GND-7


@pytest.mark.parametrize("size", [37, 73, 100, 257])
def test_end_to_end_dataset_generation(tmp_path: Path, size: int) -> None:
    # Group AF (§47/§48): sequence -> scalar math via a reusable function
    # -> structured Dataset -> serialize.json -> artifact.write_text.
    body = """
  struct Dataset {
    name: string
    x: [float]
    y: [float]
  }

  fn Wave(x: float) -> float {
    return math.sin(x)
  }

  calculation Written -> int {
    let xs = sequence.range(0.0, END, 0.1)
    let ys = array.builder()
    for x in xs {
      ys.append(Wave(x))
    }
    let dataset = Dataset { name: "sin", x: xs, y: ys.finish() }
    let encoded = serialize.json(dataset)
    let written = artifact.write_text("dataset.json", encoded)
    result = written.bytes_written
  }

  calculation Expected -> [float] {
    let ys = array.builder()
    for x in sequence.range(0.0, END, 0.1) {
      ys.append(math.sin(x))
    }
    result = ys.finish()
  }
""".replace("END", f"{size / 10:.1f}")
    runs = []
    for index in range(3):
        run_dir = tmp_path / f"run-{index}"
        run_dir.mkdir()
        values = _values(run_dir, body, allow_write=True)
        raw = (run_dir / "dataset.json").read_bytes()
        assert values["Written"] == len(raw)
        runs.append((values, raw))
    assert runs[0] == runs[1] == runs[2]
    values, raw = runs[0]
    dataset = json.loads(raw.decode("utf-8"))
    assert list(dataset) == ["name", "x", "y"]
    assert dataset["name"] == "sin"
    assert len(dataset["x"]) == len(dataset["y"]) == len(values["Expected"]) == size
    assert dataset["x"][0] == 0.0
    assert dataset["x"][1:4] == [0.1, 0.2, 0.30000000000000004]
    assert dataset["x"][-1] == 0.1 * (size - 1)
    assert all(-1.0 <= y <= 1.0 for y in dataset["y"])
    assert all(abs(actual - expected) <= 1e-12 for actual, expected in zip(dataset["y"], values["Expected"]))
    assert abs(dataset["y"][0]) < 1e-12
    if size > 20:
        assert abs(dataset["y"][10] - 0.8414709848078965) < 1e-12
        assert abs(dataset["y"][20] - 0.9092974268256817) < 1e-12
    # Re-running without overwrite refuses to clobber the artifact.
    assert _runtime_error(tmp_path / "run-0", body, allow_write=True) == "ART-006"
    assert (tmp_path / "run-0" / "dataset.json").read_bytes() == raw
