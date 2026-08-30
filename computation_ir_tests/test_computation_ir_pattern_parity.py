"""Phase 1 executable enum, Optional, and match parity gates."""

from __future__ import annotations

import unittest

from frontend.computation_ir import interpret_program, lower_program, validate_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import execute_program
from frontend.language_surface import parse


_BINARY = find_binary()


class PatternParityTests(unittest.TestCase):
    def assert_parity(self, source: str, expected: object) -> None:
        program = parse(source)
        ir = lower_program(program)
        self.assertEqual(validate_program(ir), [])
        ast_results = execute_program(program).to_dict()["calculations"]
        python_results = interpret_program(ir).to_dict()["calculations"]
        self.assertEqual(ast_results, python_results)
        self.assertEqual(python_results["Answer"], expected)
        if _BINARY is not None:
            rust = run_ir(ir, binary=_BINARY)
            self.assertTrue(rust.ok, rust.error_message)
            self.assertEqual(rust.calculation_results, python_results)

    def test_enum_value_equality_and_match(self) -> None:
        self.assert_parity(
            """
            module M {
              enum Color {
                Red
                Blue
              }
              fn score(color: Color) -> int {
                match color {
                  Color.Red when Color.Red == Color.Red => return 10
                  Color.Red => return 9
                  Color.Blue => return 0
                }
              }
              calculation Answer {
                result = score(Color.Red)
              }
            }
            """,
            10,
        )

    def test_optional_some_binding_and_none(self) -> None:
        self.assert_parity(
            """
            module M {
              fn score(value: optional<int>) -> int {
                match value {
                  some(x) when x > 10 => return x
                  some(_) => return 1
                  none => return 0
                }
              }
              calculation Answer {
                result = score(some(42))
              }
            }
            """,
            42,
        )

    def test_struct_nested_binding_and_guard(self) -> None:
        self.assert_parity(
            """
            module M {
              struct Point { x: int y: int }
              struct Box { point: Point }
              fn score(value: Box) -> int {
                match value {
                  Box { point: Point { x, y } } when x > y => return x
                  default => return 0
                }
              }
              calculation Answer {
                result = score(Box { point: Point { x: 8, y: 3 } })
              }
            }
            """,
            8,
        )

    def test_range_and_or_patterns(self) -> None:
        self.assert_parity(
            """
            module M {
              fn score(value: int) -> int {
                match value {
                  1 | 2 => return 5
                  3..10 => return 7
                  default => return 0
                }
              }
              calculation Answer {
                result = score(6)
              }
            }
            """,
            7,
        )

    def test_optional_result_has_stable_tagged_json(self) -> None:
        source = """
        module M {
          calculation Answer {
            result = some(3)
          }
        }
        """
        program = parse(source)
        ir = lower_program(program)
        expected = {"optional": "some", "value": 3}
        self.assertEqual(interpret_program(ir).to_dict()["calculations"]["Answer"], expected)
        if _BINARY is not None:
            rust = run_ir(ir, binary=_BINARY)
            self.assertTrue(rust.ok, rust.error_message)
            self.assertEqual(rust.calculation_results["Answer"], expected)


if __name__ == "__main__":
    unittest.main()
