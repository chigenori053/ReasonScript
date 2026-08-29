"""Tests for parenthesized multiline expressions (Issue #19).

Validates multiline expression parsing across arithmetic, nested parentheses,
function-call arguments, arrays/indexing, comments/blank lines, and error diagnostics.
"""

from __future__ import annotations

import unittest

from frontend.computation_ir import interpret_program, lower_program
from frontend.language_surface import parse
from frontend.language_surface.parser import SurfaceSyntaxError


class MultilineParenthesizedExpressionTests(unittest.TestCase):
    def test_01_basic_multiline_arithmetic(self):
        """Basic multiline arithmetic expression."""
        source = """module M {
  calculation Answer {
    let a = (
      10 +
      20 *
      3
    )
    result = a
  }
}
"""
        program = parse(source)
        ir = lower_program(program)
        outcome = interpret_program(ir)
        self.assertEqual(outcome.calculation_results.get("Answer"), 70)

    def test_02_nested_parentheses(self):
        """Nested parentheses across multiple lines."""
        source = """module M {
  calculation Answer {
    let x = (
      (1 + 2) *
      (
        (3 + 4) -
        (5 - 2)
      )
    )
    result = x
  }
}
"""
        program = parse(source)
        ir = lower_program(program)
        outcome = interpret_program(ir)
        self.assertEqual(outcome.calculation_results.get("Answer"), 12)

    def test_03_multiline_function_call_arguments(self):
        """Function-call arguments spanning multiple lines."""
        source = """module M {
  fn AddThree(a, b, c) {
    return a + b + c
  }
  calculation Answer {
    let res = AddThree(
      10,
      20,
      30
    )
    result = res
  }
}
"""
        program = parse(source)
        ir = lower_program(program)
        outcome = interpret_program(ir)
        self.assertEqual(outcome.calculation_results.get("Answer"), 60)

    def test_04_arrays_indexing_and_combinations(self):
        """Arrays, indexing, and member/call combinations inside parenthesized expressions."""
        source = """module M {
  fn GetArray() {
    return [100, 200, 300]
  }
  calculation Answer {
    let val = (
      GetArray()[1] +
      [10, 20, 30][0]
    )
    result = val
  }
}
"""
        program = parse(source)
        ir = lower_program(program)
        outcome = interpret_program(ir)
        self.assertEqual(outcome.calculation_results.get("Answer"), 210)

    def test_05_blank_lines_and_comments_inside_parentheses(self):
        """Blank lines and line comments inside parenthesized regions."""
        source = """module M {
  calculation Answer {
    let total = (
      // Start with base
      100

      // Add intermediate
      + 50

      // Subtract discount
      - 20
    )
    result = total
  }
}
"""
        program = parse(source)
        ir = lower_program(program)
        outcome = interpret_program(ir)
        self.assertEqual(outcome.calculation_results.get("Answer"), 130)

    def test_06_unmatched_opening_parenthesis(self):
        """Unmatched opening parenthesis raises syntax error."""
        source = """module M {
  calculation Answer {
    let a = (
      10 + 20
    result = a
  }
}
"""
        with self.assertRaises(SurfaceSyntaxError) as context:
            parse(source)
        self.assertEqual(
            str(context.exception),
            "EX-V003 unbalanced parentheses: unclosed '(' starting at 3:13",
        )

    def test_07_unexpected_closing_parenthesis(self):
        """Unexpected closing parenthesis raises syntax error."""
        source = """module M {
  calculation Answer {
    let a = 10 + 20)
    result = a
  }
}
"""
        with self.assertRaises(SurfaceSyntaxError) as context:
            parse(source)
        self.assertEqual(
            str(context.exception),
            "EX-V003 unbalanced parentheses: unexpected ')' at 3:20",
        )

    def test_08_incomplete_operator_expression(self):
        """Incomplete operator expression inside parenthesized region raises syntax error."""
        source = """module M {
  calculation Answer {
    let a = (
      10 +
    )
    result = a
  }
}
"""
        with self.assertRaises(SurfaceSyntaxError):
            parse(source)

    def test_09_source_location_accuracy(self):
        """Call nodes retain the physical start line and column after joining."""
        source = """module M {
  fn Add(a, b) {
    return a + b
  }
  calculation Answer {
    let a = Add(
      1,
      2
    )
    result = a
  }
}
"""
        program = parse(source)
        calc = program.modules[0].body[1]
        assign = calc.body[0]
        call = assign.expression.expression
        self.assertEqual(getattr(call, "_source_location", None), {"line": 6, "column": 13})


if __name__ == "__main__":
    unittest.main()
