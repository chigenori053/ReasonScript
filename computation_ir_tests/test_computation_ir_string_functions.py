"""The `string.*` namespace and `array.concat`: Phase 2's "String／Collection標準ライブラリ".

Minimal set: `string.concat`, `string.join`, `string.length`,
`string.from_int`, `string.from_float`, `string.slice`, plus
`array.concat` alongside the already-implemented `array.append`. `+` stays
numeric-only (see `frontend/string/integration.py`'s module docstring for
why a namespaced function set was chosen instead of extending `+`).

Same differential pattern as every other `computation_ir_tests` parity
suite: lower once, run through both `interpret_program` and the Rust CLI,
assert `calculation_results` / error codes agree exactly. Rust comparisons
are skipped (not failed) if the binary isn't built.
"""

from __future__ import annotations

import unittest

from frontend.computation_ir import interpret_program, lower_program, validate_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import IntegratedRuntimeError, LoopLimitError
from frontend.language_surface import parse
from frontend.language_surface.parser import SurfaceSyntaxError

_BINARY = find_binary()


def _lower(source: str):
    return lower_program(parse(source))


def _python_outcome(source: str):
    ir = _lower(source)
    try:
        result = interpret_program(ir)
    except (IntegratedRuntimeError, LoopLimitError) as error:
        return None, getattr(error, "code", None)
    return dict(result.calculation_results), None


def _rust_outcome(source: str):
    ir = _lower(source)
    outcome = run_ir(ir, binary=_BINARY)
    if outcome.ok:
        return outcome.calculation_results, None
    return None, outcome.error_code


class StringParityMixin:
    def assert_parity(self, source: str):
        ir = _lower(source)
        self.assertEqual(validate_program(ir), [])
        python_results, python_error = _python_outcome(source)
        if _BINARY is not None:
            rust_results, rust_error = _rust_outcome(source)
            self.assertEqual(python_error, rust_error, f"error code mismatch for:\n{source}")
            if python_error is None:
                self.assertEqual(python_results, rust_results, f"result mismatch for:\n{source}")
        return python_results, python_error


class StringFunctionTests(StringParityMixin, unittest.TestCase):
    def test_concat_joins_two_strings(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = string.concat("foo", "bar")
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], "foobar")

    def test_join_uses_separator_between_every_element(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let values = ["a", "b", "c"]
                    result = string.join("-", values)
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], "a-b-c")

    def test_join_of_empty_array_is_empty_string(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let values: [string] = []
                    result = string.join(",", values)
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], "")

    def test_length_counts_characters(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = string.length("hello")
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 5)

    def test_from_int_formats_negative_numbers(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = string.from_int(-7)
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], "-7")

    def test_from_float_keeps_a_decimal_point_for_whole_numbers(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = string.from_float(2.0)
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], "2.0")

    def test_from_float_keeps_fractional_digits(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = string.from_float(3.14)
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], "3.14")

    def test_slice_extracts_a_substring(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = string.slice("hello world", 6, 11)
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], "world")

    def test_slice_of_full_range_returns_original_string(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let value = "hello"
                    result = string.slice(value, 0, string.length(value))
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], "hello")

    def test_slice_out_of_range_reports_str_004_on_both_backends(self):
        _, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = string.slice("hi", 0, 5)
                }
            }
            """
        )
        self.assertEqual(error, "STR-004")

    def test_slice_end_before_start_reports_str_004_on_both_backends(self):
        _, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = string.slice("hello", 3, 1)
                }
            }
            """
        )
        self.assertEqual(error, "STR-004")

    def test_composed_pipeline_concat_then_slice_then_length(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let whole = string.concat("hello", " world")
                    let front = string.slice(whole, 0, 5)
                    result = string.length(front)
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 5)


class ArrayConcatTests(StringParityMixin, unittest.TestCase):
    def test_concat_combines_two_arrays_in_order(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let combined = array.concat([1, 2], [3, 4])
                    result = combined
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], [1, 2, 3, 4])

    def test_concat_does_not_mutate_either_source_array(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let a = [1, 2]
                    let b = [3, 4]
                    let combined = array.concat(a, b)
                    result = a.length * 100 + b.length
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 202)

    def test_concat_with_empty_array_returns_equivalent_array(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let empty: [int] = []
                    let combined = array.concat(empty, [1, 2, 3])
                    result = combined
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], [1, 2, 3])


class SurfaceValidationTests(unittest.TestCase):
    """`string.*`/`array.concat` type errors are caught before lowering,
    matching how `array.append` and `relation.*` are validated."""

    def test_string_concat_rejects_non_string_argument(self):
        with self.assertRaises(SurfaceSyntaxError):
            parse(
                """
                module M {
                    calculation Answer {
                        result = string.concat("foo", 1)
                    }
                }
                """
            )

    def test_string_from_int_rejects_string_argument(self):
        with self.assertRaises(SurfaceSyntaxError):
            parse(
                """
                module M {
                    calculation Answer {
                        result = string.from_int("1")
                    }
                }
                """
            )

    def test_string_concat_argument_count_mismatch_is_rejected(self):
        with self.assertRaises(SurfaceSyntaxError):
            parse(
                """
                module M {
                    calculation Answer {
                        result = string.concat("only-one")
                    }
                }
                """
            )

    def test_array_concat_rejects_mismatched_element_types(self):
        with self.assertRaises(SurfaceSyntaxError):
            parse(
                """
                module M {
                    calculation Answer {
                        let a = [1, 2]
                        let b = ["x", "y"]
                        result = array.concat(a, b)
                    }
                }
                """
            )


if __name__ == "__main__":
    unittest.main()
