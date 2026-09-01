"""Phase 4 ("制御された再帰"): direct and mutual recursion are allowed,
bounded by a stable, deterministic `max_call_depth` -- `FN-007`'s
unconditional rejection is gone, and every evaluator already had the
call-depth bookkeeping (`RT-CALL-003`) needed to make this safe, since it
already applied to ordinary (non-recursive) nested calls.

Same differential/parity pattern as every other `computation_ir_tests`
suite: lower once, run through the AST oracle, the Python IR interpreter,
and the Rust CLI, and assert they agree exactly. Rust comparisons are
skipped (not failed) if the binary isn't built.
"""

from __future__ import annotations

import unittest

from frontend.computation_ir import interpret_program, lower_program, validate_program
from frontend.computation_ir.differential import assert_same_outcome
from frontend.computation_ir.optimizer import classify_pure_functions, optimize_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import IntegratedRuntimeError, LoopLimitError
from frontend.language_surface import parse

_BINARY = find_binary()


def _lower(source: str):
    return lower_program(parse(source))


def _python_outcome(source: str):
    ir = optimize_program(_lower(source))
    try:
        result = interpret_program(ir)
    except (IntegratedRuntimeError, LoopLimitError) as error:
        return None, getattr(error, "code", None)
    return dict(result.calculation_results), None


def _rust_outcome(source: str):
    ir = optimize_program(_lower(source))
    outcome = run_ir(ir, binary=_BINARY)
    if outcome.ok:
        return outcome.calculation_results, None
    return None, outcome.error_code


class RecursionParityMixin:
    def assert_parity(self, source: str):
        ir = optimize_program(_lower(source))
        self.assertEqual(validate_program(ir), [])
        python_results, python_error = _python_outcome(source)
        if _BINARY is not None:
            rust_results, rust_error = _rust_outcome(source)
            self.assertEqual(python_error, rust_error, f"error code mismatch for:\n{source}")
            if python_error is None:
                self.assertEqual(python_results, rust_results, f"result mismatch for:\n{source}")
        return python_results, python_error


class DirectRecursionTests(RecursionParityMixin, unittest.TestCase):
    def test_factorial_computes_correctly(self):
        results, error = self.assert_parity(
            """
            module M {
                fn Factorial(n: int) -> int {
                    if n <= 1 {
                        return 1
                    }
                    return n * Factorial(n - 1)
                }

                calculation Answer {
                    result = Factorial(5)
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 120)

    def test_fibonacci_branching_recursion_computes_correctly(self):
        # Each call spawns two further recursive calls (not a single
        # linear chain like Factorial), stressing multiple concurrently
        # active frames of the same function at different depths.
        results, error = self.assert_parity(
            """
            module M {
                fn Fib(n: int) -> int {
                    if n <= 1 {
                        return n
                    }
                    return Fib(n - 1) + Fib(n - 2)
                }

                calculation Answer {
                    result = Fib(10)
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], 55)

    def test_unbounded_recursion_stops_with_rt_call_003_on_both_backends(self):
        _, error = self.assert_parity(
            """
            module M {
                fn Loop(n: int) -> int {
                    return Loop(n + 1)
                }

                calculation Answer {
                    result = Loop(0)
                }
            }
            """
        )
        self.assertEqual(error, "RT-CALL-003")


class MutualRecursionTests(RecursionParityMixin, unittest.TestCase):
    def test_is_even_is_odd_computes_correctly(self):
        results, error = self.assert_parity(
            """
            module M {
                fn IsEven(n: int) -> bool {
                    if n == 0 {
                        return true
                    }
                    return IsOdd(n - 1)
                }

                fn IsOdd(n: int) -> bool {
                    if n == 0 {
                        return false
                    }
                    return IsEven(n - 1)
                }

                calculation Answer {
                    result = IsEven(10)
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], True)

    def test_unbounded_mutual_recursion_stops_with_rt_call_003(self):
        _, error = self.assert_parity(
            """
            module M {
                fn PingForever(n: int) -> int {
                    return PongForever(n + 1)
                }

                fn PongForever(n: int) -> int {
                    return PingForever(n + 1)
                }

                calculation Answer {
                    result = PingForever(0)
                }
            }
            """
        )
        self.assertEqual(error, "RT-CALL-003")


class RecursiveResourceLivenessTests(RecursionParityMixin, unittest.TestCase):
    """A Tensor handle bound in a caller's frame before a deep recursive
    call chain begins must still be correct once that chain fully
    unwinds -- Tensor data lives in a separate `TensorStore`
    (`collect_tensors`'s mark-and-sweep, not plain `Rc` ownership), so a
    liveness bug specific to *stacked frames of the same function*
    (rather than ordinary nested calls to different functions, which the
    pre-existing test suite already covered) would show up as either a
    crash or the caller's Tensor silently returning stale/wrong data.

    RUO/ReasonObject resources have no such risk to test here: they're
    plain `Rc`-owned values (see `collect_tensor_ids` in `vm.rs`, which
    only ever walks `Value::Tensor`/`Array`/`Struct` -- ReasonObject
    values are never part of that sweep), so standard Rust ownership
    already guarantees they survive any call depth without a
    recursion-specific mechanism to verify.
    """

    def test_caller_tensor_survives_a_five_level_recursive_call_chain(self):
        results, error = self.assert_parity(
            """
            module M {
                fn RecurseSum(t: Tensor, n: int) -> Tensor {
                    if n <= 0 {
                        return t
                    }
                    let step = tensor.create([1.0], "f64")
                    let combined = tensor.add(t, step)
                    return RecurseSum(combined, n - 1)
                }

                calculation Answer {
                    let caller_tensor = tensor.create([5.0], "f64")
                    let start = tensor.create([0.0], "f64")
                    let recursed = RecurseSum(start, 5)
                    let final_tensor = tensor.add(caller_tensor, recursed)
                    result = tensor.to_array(final_tensor)
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], [10.0])


class SurfaceValidationTests(unittest.TestCase):
    """FN-007 no longer rejects a function calling itself, directly or
    mutually -- `parse()` (which runs full language-surface validation)
    must succeed on both shapes."""

    def test_direct_recursion_is_accepted(self):
        parse(
            """
            module M {
                fn Factorial(n: int) -> int {
                    if n <= 1 {
                        return 1
                    }
                    return n * Factorial(n - 1)
                }

                calculation Answer {
                    result = Factorial(5)
                }
            }
            """
        )

    def test_mutual_recursion_is_accepted(self):
        parse(
            """
            module M {
                fn IsEven(n: int) -> bool {
                    if n == 0 {
                        return true
                    }
                    return IsOdd(n - 1)
                }

                fn IsOdd(n: int) -> bool {
                    if n == 0 {
                        return false
                    }
                    return IsEven(n - 1)
                }

                calculation Answer {
                    result = IsEven(10)
                }
            }
            """
        )


class OptimizerRecursionTests(unittest.TestCase):
    """The optimizer's fast-path scalar inlining already had to guard
    against recursive functions (an inlining pass can't terminate against
    a call graph with a cycle) before Phase 4 ever made recursion
    reachable from real source -- this just confirms that guard still
    correctly recognizes both direct and mutual recursion now that it
    can actually be exercised end-to-end, instead of only having ever run
    against non-recursive fixtures."""

    def test_classify_pure_functions_marks_direct_recursion_as_recursive(self):
        ir = _lower(
            """
            module M {
                fn Factorial(n: int) -> int {
                    if n <= 1 {
                        return 1
                    }
                    return n * Factorial(n - 1)
                }

                calculation Answer {
                    result = Factorial(5)
                }
            }
            """
        )
        classifications = classify_pure_functions(ir)
        self.assertTrue(classifications["M::Factorial"].recursive)
        self.assertFalse(classifications["M::Factorial"].eligible_for_fast_path)

    def test_classify_pure_functions_marks_mutual_recursion_as_recursive(self):
        ir = _lower(
            """
            module M {
                fn IsEven(n: int) -> bool {
                    if n == 0 {
                        return true
                    }
                    return IsOdd(n - 1)
                }

                fn IsOdd(n: int) -> bool {
                    if n == 0 {
                        return false
                    }
                    return IsEven(n - 1)
                }

                calculation Answer {
                    result = IsEven(10)
                }
            }
            """
        )
        classifications = classify_pure_functions(ir)
        self.assertTrue(classifications["M::IsEven"].recursive)
        self.assertTrue(classifications["M::IsOdd"].recursive)

    def test_recursive_function_survives_optimize_program_without_hanging(self):
        ir = _lower(
            """
            module M {
                fn Factorial(n: int) -> int {
                    if n <= 1 {
                        return 1
                    }
                    return n * Factorial(n - 1)
                }

                calculation Answer {
                    result = Factorial(5)
                }
            }
            """
        )
        optimized = optimize_program(ir)
        outcome = assert_same_outcome(
            """
            module M {
                fn Factorial(n: int) -> int {
                    if n <= 1 {
                        return 1
                    }
                    return n * Factorial(n - 1)
                }

                calculation Answer {
                    result = Factorial(5)
                }
            }
            """
        )
        self.assertEqual(outcome.calculations["Answer"], 120)
        del optimized


if __name__ == "__main__":
    unittest.main()
