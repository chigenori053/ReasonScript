"""Regression tests for the modernization plan's Phase 1 numeric fixes.

Covers:
- L-004: `float(x)` / `int(x)` explicit conversion builtins.
- L-006 (partial): `/` always types and evaluates as Float, even for two
  Int operands (matching Python's true-division runtime semantics that
  `integrated_computation_runtime.py` already used). `//` is NOT
  introduced here: it is the ReasonScript line-comment token, so adding
  it as an integer-division operator would silently break every existing
  comment. That part of L-006 needs a dedicated lexer/parser design pass.
"""

import unittest

from frontend.integrated_computation_runtime import IntegratedRuntimeError, execute_program
from frontend.language_surface import SurfaceSyntaxError, parse, validate


class DivideAlwaysFloatTests(unittest.TestCase):
    def test_int_divided_by_int_evaluates_to_float(self):
        program = parse(
            """module DivideCheck {
  calculation Answer {
    let a = 7
    let b = 2
    result = a / b
  }
}
"""
        )
        result = execute_program(program).to_dict()["result"]
        self.assertEqual(result, 3.5)
        self.assertIsInstance(result, float)

    def test_float_typed_let_binding_accepts_int_division_result(self):
        # If `/` were still (incorrectly) typed as Int for two Int
        # operands, assigning it into an explicitly Float-typed binding
        # would fail validation with a type mismatch.
        program = parse(
            """module DivideTypeCheck {
  calculation Answer {
    let ratio: Float = 7 / 2
    result = ratio
  }
}
"""
        )
        validate(program)  # must not raise


class DivideAndModuloByZeroTests(unittest.TestCase):
    """`/` and `%` previously leaked a raw Python ZeroDivisionError instead
    of a ReasonScript diagnostic, the only arithmetic path in
    integrated_computation_runtime.py that didn't go through
    IntegratedRuntimeError like every other failure mode there."""

    def test_divide_by_zero_raises_integrated_runtime_error(self):
        program = parse(
            """module DivideByZero {
  calculation Answer {
    let a = 7
    let b = 0
    result = a / b
  }
}
"""
        )
        with self.assertRaises(IntegratedRuntimeError) as ctx:
            execute_program(program)
        self.assertEqual(ctx.exception.code, "RT-ARITH-001")

    def test_modulo_by_zero_raises_integrated_runtime_error(self):
        program = parse(
            """module ModuloByZero {
  calculation Answer {
    let a = 7
    let b = 0
    result = a % b
  }
}
"""
        )
        with self.assertRaises(IntegratedRuntimeError) as ctx:
            execute_program(program)
        self.assertEqual(ctx.exception.code, "RT-ARITH-001")


class ScalarCastTests(unittest.TestCase):
    def test_float_conversion_of_int(self):
        program = parse(
            """module FloatCast {
  calculation Answer {
    let n = 3
    result = float(n)
  }
}
"""
        )
        result = execute_program(program).to_dict()["result"]
        self.assertEqual(result, 3.0)
        self.assertIsInstance(result, float)

    def test_int_conversion_truncates_toward_zero(self):
        program = parse(
            """module IntCast {
  calculation Answer {
    result = int(3.8)
  }
}
"""
        )
        result = execute_program(program).to_dict()["result"]
        self.assertEqual(result, 3)
        self.assertIsInstance(result, int)

    def test_float_of_non_numeric_argument_is_rejected_at_validation(self):
        with self.assertRaises(SurfaceSyntaxError) as ctx:
            parse(
                """module FloatCastBad {
  calculation Answer {
    let s = "hi"
    result = float(s)
  }
}
"""
            )
        self.assertIn("CAST-002", str(ctx.exception))

    def test_float_with_wrong_argument_count_is_rejected(self):
        with self.assertRaises(SurfaceSyntaxError) as ctx:
            parse(
                """module FloatCastArity {
  calculation Answer {
    result = float(1, 2)
  }
}
"""
            )
        self.assertIn("CAST-001", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
