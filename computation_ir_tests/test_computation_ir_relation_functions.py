"""The `relation.*` namespace: Phase 8's "relational algebra core".

Implements the *selection* half of relational algebra
(`filter_eq`/`filter_ne`/`filter_gt`/`filter_gte`/`filter_lt`/`filter_lte`,
plus `count`/`distinct_by`/`sort_by`) over `Array<Struct>` --
ReasonScript's existing "array of same-shaped structs" IS a relation's
tuple set, so no new data type was introduced. `join`/`project`
(projection) are deliberately not implemented: both change a row's field
shape, which needs a new struct type the static type checker has no way
to synthesize (see `frontend/relation/integration.py`'s module docstring
for the full rationale) -- a real, separate design decision, not made
here.

Same differential pattern as every other `computation_ir_tests` parity
suite: lower once, run through both `interpret_program` and the Rust
CLI, assert `calculation_results` / error codes agree exactly. Rust
comparisons are skipped (not failed) if the binary isn't built.
"""

from __future__ import annotations

import unittest

from frontend.computation_ir import interpret_program, lower_program, validate_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import IntegratedRuntimeError, LoopLimitError
from frontend.language_surface import parse
from frontend.language_surface.parser import SurfaceSyntaxError

_BINARY = find_binary()

_ROWS_FIXTURE = """
            struct Row {
                name: string
                age: int
            }
            calculation Answer {
                let rows = [
                    Row { name: "alice", age: 30 },
                    Row { name: "bob", age: 20 },
                    Row { name: "carol", age: 20 },
                    Row { name: "dave", age: 10 }
                ]
"""


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


class RelationParityMixin:
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


class RelationAlgebraTests(RelationParityMixin, unittest.TestCase):
    def test_filter_gt_keeps_only_matching_rows(self):
        results, error = self.assert_parity(
            f"""
            module M {{{_ROWS_FIXTURE}
                let filtered = relation.filter_gt(rows, "age", 15)
                result = relation.count(filtered)
            }}
            }}
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 3)

    def test_filter_eq_matches_exact_value(self):
        results, error = self.assert_parity(
            f"""
            module M {{{_ROWS_FIXTURE}
                let filtered = relation.filter_eq(rows, "age", 20)
                result = relation.count(filtered)
            }}
            }}
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 2)

    def test_filter_ne_excludes_exact_value(self):
        results, error = self.assert_parity(
            f"""
            module M {{{_ROWS_FIXTURE}
                let filtered = relation.filter_ne(rows, "age", 20)
                result = relation.count(filtered)
            }}
            }}
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 2)

    def test_filter_gte_and_lte_are_inclusive(self):
        results, error = self.assert_parity(
            f"""
            module M {{{_ROWS_FIXTURE}
                let above = relation.filter_gte(rows, "age", 20)
                let below = relation.filter_lte(rows, "age", 20)
                result = relation.count(above) * 100 + relation.count(below)
            }}
            }}
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 300 + 3)

    def test_filter_lt_is_strict(self):
        results, error = self.assert_parity(
            f"""
            module M {{{_ROWS_FIXTURE}
                let filtered = relation.filter_lt(rows, "age", 20)
                result = relation.count(filtered)
            }}
            }}
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 1)

    def test_distinct_by_keeps_first_occurrence_in_source_order(self):
        results, error = self.assert_parity(
            f"""
            module M {{{_ROWS_FIXTURE}
                let distinct_rows = relation.distinct_by(rows, "age")
                result = distinct_rows[0].name
            }}
            }}
            """
        )
        self.assertIsNone(error)
        # alice(30) is first; bob(20) is the first row with age=20.
        self.assertEqual(results["Answer"], "alice")

    def test_sort_by_ascending_and_descending(self):
        results, error = self.assert_parity(
            f"""
            module M {{{_ROWS_FIXTURE}
                let ascending = relation.sort_by(rows, "age", false)
                let descending = relation.sort_by(rows, "age", true)
                result = ascending[0].age * 1000 + descending[0].age
            }}
            }}
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 10 * 1000 + 30)

    def test_sort_by_is_stable_for_equal_keys(self):
        # bob and carol both have age=20; ascending order must keep them
        # in their original relative order (source order), matching
        # Python's sorted()'s stability guarantee and proving the Rust
        # comparator's 3-way Less/Equal/Greater derivation doesn't
        # silently reorder equal elements.
        results, error = self.assert_parity(
            f"""
            module M {{{_ROWS_FIXTURE}
                let ascending = relation.sort_by(rows, "age", false)
                result = ascending[1].name
            }}
            }}
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], "bob")

    def test_count_of_empty_relation_is_zero(self):
        results, error = self.assert_parity(
            f"""
            module M {{{_ROWS_FIXTURE}
                let filtered = relation.filter_gt(rows, "age", 999)
                result = relation.count(filtered)
            }}
            }}
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 0)

    def test_chained_filter_distinct_sort_pipeline(self):
        results, error = self.assert_parity(
            f"""
            module M {{{_ROWS_FIXTURE}
                let filtered = relation.filter_gte(rows, "age", 20)
                let distinct_rows = relation.distinct_by(filtered, "age")
                let sorted_rows = relation.sort_by(distinct_rows, "age", true)
                result = sorted_rows[0].name
            }}
            }}
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], "alice")


class RelationErrorParityTests(RelationParityMixin, unittest.TestCase):
    def test_unknown_field_is_rejected_at_runtime(self):
        _results, error = self.assert_parity(
            f"""
            module M {{{_ROWS_FIXTURE}
                let filtered = relation.filter_gt(rows, "height", 100)
                result = relation.count(filtered)
            }}
            }}
            """
        )
        self.assertEqual(error, "REL-005")

    def test_incomparable_field_type_is_rejected_at_runtime(self):
        _results, error = self.assert_parity(
            f"""
            module M {{{_ROWS_FIXTURE}
                let filtered = relation.filter_gt(rows, "name", 5)
                result = relation.count(filtered)
            }}
            }}
            """
        )
        self.assertEqual(error, "REL-006")

    def test_non_array_argument_is_rejected_at_runtime(self):
        _results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = relation.count(5)
                }
            }
            """
        )
        self.assertEqual(error, "REL-004")

    def test_non_struct_array_argument_is_rejected_at_runtime(self):
        _results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let values = [1, 2, 3]
                    result = relation.count(values)
                }
            }
            """
        )
        self.assertEqual(error, "REL-004")

    def test_field_argument_must_be_string_literal(self):
        with self.assertRaises(SurfaceSyntaxError) as raised:
            parse(
                f"""
                module M {{{_ROWS_FIXTURE}
                    let filtered = relation.filter_gt(rows, 5, 100)
                    result = relation.count(filtered)
                }}
                }}
                """
            )
        self.assertIn("REL-003", str(raised.exception))

    def test_wrong_argument_count_is_rejected_statically(self):
        with self.assertRaises(SurfaceSyntaxError) as raised:
            parse(
                f"""
                module M {{{_ROWS_FIXTURE}
                    result = relation.count(rows, rows)
                }}
                }}
                """
            )
        self.assertIn("REL-002", str(raised.exception))

    def test_unknown_relation_function_is_rejected_statically(self):
        with self.assertRaises(SurfaceSyntaxError) as raised:
            parse(
                f"""
                module M {{{_ROWS_FIXTURE}
                    result = relation.join(rows, rows)
                }}
                }}
                """
            )
        self.assertIn("REL-001", str(raised.exception))

    def test_named_arguments_are_rejected_statically(self):
        with self.assertRaises(SurfaceSyntaxError) as raised:
            parse(
                f"""
                module M {{{_ROWS_FIXTURE}
                    let filtered = relation.filter_gt(rows=rows, field="age", value=15)
                    result = relation.count(filtered)
                }}
                }}
                """
            )
        self.assertIn("REL-002", str(raised.exception))


class RelationTensorManifestIndependenceTests(unittest.TestCase):
    """`relation.*` must stay fully outside the Tensor Standard Functions
    registry, exactly like `optimizer.*`."""

    def test_relation_functions_are_not_in_tensor_contracts(self):
        from frontend.tensor.runtime import TensorRuntime

        runtime = TensorRuntime()
        for name in (
            "relation.filter_eq",
            "relation.count",
            "relation.distinct_by",
            "relation.sort_by",
        ):
            self.assertNotIn(name, runtime.contracts)


if __name__ == "__main__":
    unittest.main()
