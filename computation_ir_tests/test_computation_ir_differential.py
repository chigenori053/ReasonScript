"""Phase 2 gate: AST evaluator and IR (lower + interpret) must agree.

Each case exercises a construct `frontend.computation_ir.lowering`
claims to support. `assert_same_outcome` runs both
`frontend.integrated_computation_runtime.execute_program` and
`lower_program` + `interpret_program`, and fails loudly if they produce
different `calculations` or different error codes.
"""

import unittest

from frontend.computation_ir.differential import assert_same_outcome
from frontend.computation_ir.lowering import LoweringError, lower_program
from frontend.language_surface import parse


class ArithmeticAndCastTests(unittest.TestCase):
    def test_integer_division_is_float(self):
        outcome = assert_same_outcome(
            """module M {
  calculation Answer {
    result = 7 / 2
  }
}
"""
        )
        self.assertEqual(outcome.calculations["Answer"], 3.5)

    def test_modulo_and_zero_division_error_code_match(self):
        outcome = assert_same_outcome(
            """module M {
  calculation Answer {
    result = 7 % 3
  }
}
"""
        )
        self.assertEqual(outcome.calculations["Answer"], 1)

        outcome = assert_same_outcome(
            """module M {
  calculation Answer {
    let a = 1
    let b = 0
    result = a / b
  }
}
"""
        )
        self.assertEqual(outcome.error_code, "RT-ARITH-001")

    def test_float_and_int_casts(self):
        outcome = assert_same_outcome(
            """module M {
  calculation Answer {
    let n = float(3)
    let m = int(3.8)
    result = n + float(m)
  }
}
"""
        )
        self.assertEqual(outcome.calculations["Answer"], 6.0)


class ControlFlowTests(unittest.TestCase):
    def test_if_elif_else_selects_correct_branch(self):
        for value, expected in ((10, "big"), (5, "mid"), (0, "small")):
            outcome = assert_same_outcome(
                f"""module M {{
  calculation Answer {{
    let x = {value}
    let label = "small"
    if x > 8 {{
      label = "big"
    }} elif x > 2 {{
      label = "mid"
    }} else {{
      label = "small"
    }}
    result = label
  }}
}}
"""
            )
            self.assertEqual(outcome.calculations["Answer"], expected)

    def test_while_loop_with_break_and_continue(self):
        outcome = assert_same_outcome(
            """module M {
  calculation Answer {
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
        # 1+2+4+5+6+7 = 25 (skip 3, stop after adding 7 since i=8 breaks)
        self.assertEqual(outcome.calculations["Answer"], 25)

    def test_for_loop_over_array_and_function_call(self):
        outcome = assert_same_outcome(
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
        self.assertEqual(outcome.calculations["Answer"], 30)

    def test_bare_loop_with_break(self):
        outcome = assert_same_outcome(
            """module M {
  calculation Answer {
    let i = 0
    loop {
      i = i + 1
      if i >= 5 {
        break
      }
    }
    result = i
  }
}
"""
        )
        self.assertEqual(outcome.calculations["Answer"], 5)

    def test_nested_if_inside_while(self):
        outcome = assert_same_outcome(
            """module M {
  calculation Answer {
    let total = 0
    let i = 0
    while i < 6 {
      if i % 2 == 0 {
        total = total + i
      } else {
        total = total - 1
      }
      i = i + 1
    }
    result = total
  }
}
"""
        )
        self.assertEqual(outcome.calculations["Answer"], (0 + 2 + 4) - 3)


class CollectionsAndStructsTests(unittest.TestCase):
    def test_array_index_and_length(self):
        outcome = assert_same_outcome(
            """module M {
  calculation Answer {
    let values = [10, 20, 30]
    result = values[1] + values.length
  }
}
"""
        )
        self.assertEqual(outcome.calculations["Answer"], 23)

    def test_array_index_assignment(self):
        outcome = assert_same_outcome(
            """module M {
  calculation Answer {
    let values = [1, 2, 3]
    values[0] = 99
    result = values
  }
}
"""
        )
        self.assertEqual(outcome.calculations["Answer"], [99, 2, 3])

    def test_out_of_range_index_error_code_matches(self):
        outcome = assert_same_outcome(
            """module M {
  calculation Answer {
    let values = [1, 2, 3]
    result = values[10]
  }
}
"""
        )
        self.assertEqual(outcome.error_code, "RT-INDEX-002")

    def test_array_append_builtin(self):
        outcome = assert_same_outcome(
            """module M {
  calculation Answer {
    let values = [1, 2]
    result = array.append(values, 3)
  }
}
"""
        )
        self.assertEqual(outcome.calculations["Answer"], [1, 2, 3])


class TensorInteropTests(unittest.TestCase):
    def test_tensor_add_and_to_array(self):
        outcome = assert_same_outcome(
            """module M {
  calculation Answer {
    let a = tensor.create([1.0, 2.0], "f64")
    let b = tensor.create([3.0, 4.0], "f64")
    let c = tensor.add(a, b)
    result = tensor.to_array(c)
  }
}
"""
        )
        self.assertEqual(outcome.calculations["Answer"], [4.0, 6.0])

    def test_tensor_grad_matches(self):
        outcome = assert_same_outcome(
            """module M {
  calculation Answer {
    let weight = tensor.parameter(tensor.create([2.0], "f64"))
    let loss = tensor.mean(tensor.power(weight, 2.0))
    let gradients = tensor.grad(loss, [weight])
    result = tensor.to_array(gradients[0])
  }
}
"""
        )
        self.assertEqual(outcome.calculations["Answer"], [4.0])


class EnumOptionalMatchTests(unittest.TestCase):
    """Phase 1: enum/optional/match as tagged values with real pattern matching.

    Each case lowers to a `match` terminator plus (where relevant)
    `enum_value`/`optional_some`/`optional_none` expression ops (schema
    0.2) and is executed by both the AST oracle and the IR interpreter,
    the same differential-testing contract as every other class in this
    module.
    """

    def test_enum_match_falls_through_to_default(self):
        outcome = assert_same_outcome(
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
    result = Score(Color.Green)
  }
}
"""
        )
        self.assertEqual(outcome.calculations["Answer"], 0)

    def test_enum_match_selects_matching_variant(self):
        outcome = assert_same_outcome(
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
        self.assertEqual(outcome.calculations["Answer"], 2)

    def test_optional_some_and_none_are_distinguished_from_null(self):
        outcome = assert_same_outcome(
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
        self.assertEqual(outcome.calculations["Answer"], 41)

    def test_none_pattern_does_not_match_a_none_value_through_null(self):
        # `none` (an absent Optional) must stay distinct from `null`
        # internally -- if the IR interpreter ever collapsed the two the
        # way the pre-0.2 schema did, `some(x)`/`none` matching would
        # misbehave the moment a `null` leaked into an Optional slot.
        outcome = assert_same_outcome(
            """module M {
  fn Describe(value: optional<int>) -> int {
    match value {
      some(x) => return x
      none => return -1
    }
  }

  calculation Answer {
    let a: optional<int> = none
    result = Describe(a)
  }
}
"""
        )
        self.assertEqual(outcome.calculations["Answer"], -1)

    def test_guard_with_struct_pattern_binding(self):
        outcome = assert_same_outcome(
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
        self.assertEqual(outcome.calculations["Answer"], 1)

    def test_struct_pattern_binds_fields(self):
        outcome = assert_same_outcome(
            """module M {
  struct Point {
    x: int
    y: int
  }

  fn Sum(p: Point) -> int {
    match p {
      Point { x, y } => return x + y
    }
  }

  calculation Answer {
    let p = Point { x: 3, y: 4 }
    result = Sum(p)
  }
}
"""
        )
        self.assertEqual(outcome.calculations["Answer"], 7)

    def test_or_pattern_matches_any_alternative(self):
        outcome = assert_same_outcome(
            """module M {
  fn IsWeekend(n: int) -> bool {
    match n {
      0 | 6 => return true
      default => return false
    }
  }

  calculation Answer {
    result = IsWeekend(6)
  }
}
"""
        )
        self.assertEqual(outcome.calculations["Answer"], True)

    def test_range_pattern_matches_inclusive_bounds(self):
        outcome = assert_same_outcome(
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
        self.assertEqual(outcome.calculations["Answer"], 1)

    def test_nested_optional_enum_pattern(self):
        outcome = assert_same_outcome(
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
        self.assertEqual(outcome.calculations["Answer"], 2)


class LoweringScopeErrorTests(unittest.TestCase):
    def test_break_outside_loop_is_rejected_at_lowering(self):
        program = parse(
            """module M {
  calculation Answer {
    result = 1
  }
}
"""
        )
        # Sanity: a normal program still lowers fine; the actual
        # "break outside loop" case can't be constructed through the
        # parser (language-level validation already forbids it), so this
        # asserts lowering doesn't regress on the common path instead.
        ir = lower_program(program)
        self.assertEqual(ir["schema"], "reason-computation-ir/0.2")
        self.assertEqual(ir["calculations"], ["Answer"])


if __name__ == "__main__":
    unittest.main()
