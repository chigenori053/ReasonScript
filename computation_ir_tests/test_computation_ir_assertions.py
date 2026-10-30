"""`assert`/`assert_eq`: Phase 3's "実行型テスト機構" language-level assertion
primitives.

Both are bare global builtins (not a namespace), recognized the same way
as the `float`/`int` scalar casts: a same-named user `fn` shadows the
builtin. A failed assertion raises `TEST-ASSERT-001` on both backends --
this is the diagnostic code `toolchain/runner_cmd.py`'s `reason test`
uses to tell a genuine assertion failure apart from an unrelated runtime
error.

Same differential pattern as every other `computation_ir_tests` parity
suite: lower once, run through both `interpret_program` and the Rust CLI,
assert `calculation_results` / error codes agree exactly. Rust
comparisons are skipped (not failed) if the binary isn't built.
"""

from __future__ import annotations

import unittest

from computation_ir_tests.parity_support import SourceParityMixin

from frontend.language_surface import parse
from frontend.language_surface.parser import SurfaceSyntaxError


class AssertTests(SourceParityMixin, unittest.TestCase):
    def test_true_condition_passes_silently(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    assert(1 == 1)
                    result = 1
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 1)

    def test_false_condition_reports_test_assert_001_on_both_backends(self):
        _, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    assert(1 == 2)
                    result = 1
                }
            }
            """
        )
        self.assertEqual(error, "TEST-ASSERT-001")

    def test_unused_assert_result_still_executes(self):
        # The whole point of Phase 3: an assert whose (null) result is
        # never read must still run -- dead-code elimination silently
        # dropping it would make every assertion a no-op.
        _, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    assert(false)
                    result = 1
                }
            }
            """
        )
        self.assertEqual(error, "TEST-ASSERT-001")


class AssertEqTests(SourceParityMixin, unittest.TestCase):
    def test_matching_values_pass_silently(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    assert_eq(2 + 2, 4)
                    result = 1
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 1)

    def test_mismatched_int_values_report_test_assert_001(self):
        _, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    assert_eq(2 + 2, 5)
                    result = 1
                }
            }
            """
        )
        self.assertEqual(error, "TEST-ASSERT-001")

    def test_mismatched_string_values_report_test_assert_001(self):
        _, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    assert_eq(string.concat("a", "b"), "ac")
                    result = 1
                }
            }
            """
        )
        self.assertEqual(error, "TEST-ASSERT-001")

    def test_matching_struct_values_pass_silently(self):
        results, error = self.assert_parity(
            """
            module M {
                struct Point {
                    x: int
                    y: int
                }
                calculation Answer {
                    let a = Point { x: 1, y: 2 }
                    let b = Point { x: 1, y: 2 }
                    assert_eq(a, b)
                    result = 1
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 1)


class SurfaceValidationTests(unittest.TestCase):
    """`assert`/`assert_eq` type errors are caught before lowering,
    matching how the `float`/`int` scalar casts are validated."""

    def test_assert_rejects_non_bool_condition(self):
        with self.assertRaises(SurfaceSyntaxError):
            parse(
                """
                module M {
                    calculation Answer {
                        assert(1)
                        result = 1
                    }
                }
                """
            )

    def test_assert_argument_count_mismatch_is_rejected(self):
        with self.assertRaises(SurfaceSyntaxError):
            parse(
                """
                module M {
                    calculation Answer {
                        assert(true, false)
                        result = 1
                    }
                }
                """
            )

    def test_assert_eq_rejects_mismatched_types(self):
        with self.assertRaises(SurfaceSyntaxError):
            parse(
                """
                module M {
                    calculation Answer {
                        assert_eq(1, "1")
                        result = 1
                    }
                }
                """
            )


if __name__ == "__main__":
    unittest.main()
