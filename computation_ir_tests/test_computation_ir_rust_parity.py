"""Phase 3 gate: Rust VM vs. Python IR interpreter, for Tensor-less programs.

"ゲート: Tensorなしcalculationのpython/Rust一致" -- lowers a program to IR
once, then runs it through both `frontend.computation_ir.interpret_program`
and the compiled `reason-computation-runtime` Rust binary
(`frontend.computation_ir.rust_bridge`), and asserts they agree on
`calculation_results` / error code.

The whole module is skipped if the Rust binary hasn't been built (e.g. a
plain `pytest` run in a sandbox without a `cargo build` step first) --
build it with:
    cargo build --manifest-path ReasonRuntime/Cargo.toml
or via `python3 scripts/test_platform.py test`, which builds and
`cargo test`s `ReasonRuntime` before running pytest.
"""

from __future__ import annotations

import unittest

from frontend.computation_ir import interpret_program, lower_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import IntegratedRuntimeError, LoopLimitError
from frontend.language_surface import parse

_BINARY = find_binary()


def _python_outcome(source: str):
    program = parse(source)
    ir = lower_program(program)
    try:
        result = interpret_program(ir)
    except (IntegratedRuntimeError, LoopLimitError) as error:
        return None, getattr(error, "code", None)
    return dict(result.calculation_results), None


def _rust_outcome(source: str):
    program = parse(source)
    ir = lower_program(program)
    outcome = run_ir(ir, binary=_BINARY)
    if outcome.ok:
        return outcome.calculation_results, None
    return None, outcome.error_code


@unittest.skipUnless(_BINARY is not None, "reason-computation-runtime binary not built")
class RustParityTests(unittest.TestCase):
    def assert_parity(self, source: str):
        python_results, python_error = _python_outcome(source)
        rust_results, rust_error = _rust_outcome(source)
        self.assertEqual(python_error, rust_error, f"error code mismatch for:\n{source}")
        if python_error is None:
            self.assertEqual(python_results, rust_results, f"result mismatch for:\n{source}")
        return python_results

    def test_integer_division_is_float(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    result = 7 / 2
  }
}
"""
        )
        self.assertEqual(results["Answer"], 3.5)

    def test_negative_modulo_matches_python_floor_semantics(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = 0
    let b = 7
    result = a - b % 3
  }
}
"""
        )
        self.assertEqual(results["Answer"], -1)

    def test_division_by_zero_error_code_matches(self):
        self.assert_parity(
            """module M {
  calculation Answer {
    let a = 1
    let b = 0
    result = a / b
  }
}
"""
        )

    def test_if_elif_else_and_while_loop(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let x = 5
    let label = "small"
    if x > 8 {
      label = "big"
    } elif x > 2 {
      label = "mid"
    } else {
      label = "small"
    }
    let total = 0
    let i = 0
    while i < 10 {
      i = i + 1
      if i == 3 {
        continue
      }
      if i > 7 {
        break
      }
      total = total + i
    }
    result = total
  }
}
"""
        )
        self.assertEqual(results["Answer"], 25)

    def test_function_calls_and_for_loop(self):
        results = self.assert_parity(
            """module M {
  fn square(x) {
    return x * x
  }
  calculation Answer {
    let values = [1, 2, 3, 4]
    let total = 0
    for v in values {
      total = total + square(v)
    }
    result = total
  }
}
"""
        )
        self.assertEqual(results["Answer"], 30)

    def test_qualified_functions_with_same_symbol_keep_distinct_ids(self):
        results = self.assert_parity(
            """pub module Left {
  pub fn Score(value: int) -> int {
    return value + 1
  }
}
pub module Right {
  pub fn Score(value: int) -> int {
    return value + 10
  }
}
module Main {
  calculation Answer {
    result = Left::Score(1) + Right::Score(1)
  }
}
"""
        )
        self.assertEqual(results["Answer"], 13)

    def test_array_index_out_of_range_error_code_matches(self):
        self.assert_parity(
            """module M {
  calculation Answer {
    let values = [1, 2, 3]
    result = values[10]
  }
}
"""
        )

    def test_array_append_and_struct_and_cast(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let values = [1, 2]
    let appended = array.append(values, 3)
    let n = float(appended.length)
    let m = int(n)
    result = m
  }
}
"""
        )
        self.assertEqual(results["Answer"], 3)

    def test_enum_match_selects_matching_variant(self):
        results = self.assert_parity(
            """module M {
  enum Color {
    Red
    Blue
    Green
  }

  fn Score(color: Color) -> int {
    match color {
      Color.Red => return 1
      Color.Blue => return 2
      default => return 0
    }
  }

  calculation Answer {
    result = Score(Color.Blue)
  }
}
"""
        )
        self.assertEqual(results["Answer"], 2)

    def test_optional_some_and_none_are_distinguished_from_null(self):
        results = self.assert_parity(
            """module M {
  fn Describe(value: optional<int>) -> int {
    match value {
      some(x) => return x
      none => return -1
    }
  }

  calculation Answer {
    let a = Describe(some(42))
    let b = Describe(none)
    result = a + b
  }
}
"""
        )
        self.assertEqual(results["Answer"], 41)

    def test_guard_with_struct_pattern_binding(self):
        results = self.assert_parity(
            """module M {
  struct Point {
    x: int
    y: int
  }

  fn Classify(p: Point) -> int {
    match p {
      Point { x, y } when x > y => return 1
      Point { x, y } when x == y => return 0
      default => return -1
    }
  }

  calculation Answer {
    let p = Point { x: 5, y: 2 }
    result = Classify(p)
  }
}
"""
        )
        self.assertEqual(results["Answer"], 1)

    def test_or_pattern_and_range_pattern(self):
        results = self.assert_parity(
            """module M {
  fn Grade(score: int) -> int {
    match score {
      90..100 => return 1
      0..89 => return 0
      default => return -1
    }
  }

  calculation Answer {
    result = Grade(95)
  }
}
"""
        )
        self.assertEqual(results["Answer"], 1)

    def test_nested_optional_enum_pattern(self):
        results = self.assert_parity(
            """module M {
  enum Color {
    Red
    Blue
  }

  fn Describe(value: optional<Color>) -> int {
    match value {
      some(Color.Red) => return 1
      some(Color.Blue) => return 2
      none => return 0
    }
  }

  calculation Answer {
    result = Describe(some(Color.Blue))
  }
}
"""
        )
        self.assertEqual(results["Answer"], 2)

    def test_softmax_is_implemented_by_the_rust_vm(self):
        source = """module M {
  calculation Answer {
    let a = tensor.create([1.0, 2.0], "f64")
    result = tensor.to_array(tensor.softmax(a))
  }
}
"""
        self.assert_parity(source)


if __name__ == "__main__":
    unittest.main()
