"""Phase 7 ("IR最適化"): `frontend.computation_ir.optimizer`.

Covers constant folding, dead-branch/unreachable-block elimination, dead
local elimination, and local CSE, plus differential parity: every program
here is run through `interpret_program` both unoptimized and optimized
(and, when the Rust binary is built, through the Rust VM too) and the
`calculation_results` / error code must match exactly. Optimization must
never change what a program computes -- only how many instructions it
takes to compute it.
"""

from __future__ import annotations

import unittest

from frontend.computation_ir import interpret_program, lower_program, validate_program
from frontend.computation_ir.optimizer import optimize_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import IntegratedRuntimeError, LoopLimitError
from frontend.language_surface import parse

_BINARY = find_binary()


def _lower(source: str):
    return lower_program(parse(source))


def _python_outcome(ir):
    try:
        result = interpret_program(ir)
    except (IntegratedRuntimeError, LoopLimitError) as error:
        return None, getattr(error, "code", None)
    return dict(result.calculation_results), None


def _rust_outcome(ir):
    outcome = run_ir(ir, binary=_BINARY)
    if outcome.ok:
        return outcome.calculation_results, None
    return None, outcome.error_code


class OptimizerParityMixin:
    def assert_parity(self, source: str):
        """Lowers `source` once, optimizes it, and asserts every backend
        (Python unoptimized, Python optimized, and Rust when available)
        agrees on results / error code."""
        ir = _lower(source)
        self.assertEqual(validate_program(ir), [])
        optimized = optimize_program(ir)
        self.assertEqual(validate_program(optimized), [])

        unopt_results, unopt_error = _python_outcome(ir)
        opt_results, opt_error = _python_outcome(optimized)
        self.assertEqual(unopt_error, opt_error, f"error code mismatch (python) for:\n{source}")
        self.assertEqual(unopt_results, opt_results, f"result mismatch (python) for:\n{source}")

        if _BINARY is not None:
            rust_unopt_results, rust_unopt_error = _rust_outcome(ir)
            rust_opt_results, rust_opt_error = _rust_outcome(optimized)
            self.assertEqual(unopt_error, rust_unopt_error, f"error code mismatch (rust unopt) for:\n{source}")
            self.assertEqual(unopt_results, rust_unopt_results, f"result mismatch (rust unopt) for:\n{source}")
            self.assertEqual(unopt_error, rust_opt_error, f"error code mismatch (rust opt) for:\n{source}")
            self.assertEqual(unopt_results, rust_opt_results, f"result mismatch (rust opt) for:\n{source}")

        return optimized, unopt_results


class ConstantFoldingTests(OptimizerParityMixin, unittest.TestCase):
    def test_arithmetic_is_folded_to_a_single_const(self):
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = 2 + 3 * 4
                }
            }
            """
        )
        self.assertEqual(results, {"Answer": 14})
        instructions = optimized["functions"][0]["blocks"][0]["instructions"]
        terminator = optimized["functions"][0]["blocks"][0]["terminator"]
        self.assertEqual(instructions, [])
        self.assertEqual(terminator["value"], {"op": "const", "kind": "int", "value": 14})

    def test_float_division_folds_to_float_kind(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = 7.0 / 2.0
                }
            }
            """
        )

    def test_comparison_and_logical_short_circuit_fold(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    let a = 3 > 1
                    let b = a && (5 < 2)
                    let c = false || true
                    result = b || c
                }
            }
            """
        )

    def test_cast_calls_fold_on_const_arguments(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    result = float(3) + float(2.9)
                }
            }
            """
        )

    def test_unary_negate_and_not_fold(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    let a = -(5)
                    let b = !(false)
                    result = a
                }
            }
            """
        )

    def test_divide_by_zero_is_left_unfolded_and_still_raises(self):
        optimized, _ = None, None
        ir = _lower(
            """
            module M {
                calculation Answer {
                    result = 1 / 0
                }
            }
            """
        )
        optimized = optimize_program(ir)
        terminator = optimized["functions"][0]["blocks"][0]["terminator"]
        # Left as a `binary` node -- the optimizer must not try to
        # constant-fold a division by zero into a value.
        self.assertEqual(terminator["value"]["op"], "binary")
        with self.assertRaises(IntegratedRuntimeError) as raised:
            interpret_program(optimized)
        self.assertEqual(raised.exception.code, "RT-ARITH-001")
        if _BINARY is not None:
            outcome = run_ir(optimized, binary=_BINARY)
            self.assertFalse(outcome.ok)
            self.assertEqual(outcome.error_code, "RT-ARITH-001")

    def test_modulo_by_zero_is_left_unfolded_and_still_raises(self):
        ir = _lower(
            """
            module M {
                calculation Answer {
                    result = 5 % 0
                }
            }
            """
        )
        optimized = optimize_program(ir)
        with self.assertRaises(IntegratedRuntimeError) as raised:
            interpret_program(optimized)
        self.assertEqual(raised.exception.code, "RT-ARITH-001")


class BranchAndDeadCodeTests(OptimizerParityMixin, unittest.TestCase):
    def test_true_branch_collapses_to_jump_and_removes_else_block(self):
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let x = 0
                    if true {
                        x = 1
                    } else {
                        x = 2
                    }
                    result = x
                }
            }
            """
        )
        self.assertEqual(results, {"Answer": 1})
        blocks = optimized["functions"][0]["blocks"]
        # Only reachable blocks survive: entry + then-branch (+ join, if
        # the lowering produces one) -- never the else-branch's block.
        for block in blocks:
            for instruction in block["instructions"]:
                if instruction["op"] == "assign":
                    self.assertNotEqual(
                        instruction.get("expr"), {"op": "const", "kind": "int", "value": 2}
                    )

    def test_false_branch_collapses_to_jump(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    let x = 0
                    if false {
                        x = 1
                    } else {
                        x = 2
                    }
                    result = x
                }
            }
            """
        )

    def test_unused_let_binding_is_eliminated(self):
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let a = 2
                    let b = 3
                    let unused = 999
                    result = a + b
                }
            }
            """
        )
        self.assertEqual(results, {"Answer": 5})
        for block in optimized["functions"][0]["blocks"]:
            for instruction in block["instructions"]:
                self.assertNotEqual(instruction.get("target"), "unused")

    def test_tensor_save_is_never_eliminated_even_when_unused(self):
        ir = _lower(
            """
            module M {
                calculation Answer {
                    let a = tensor.create([1.0, 2.0], "f64")
                    let receipt = tensor.save(a, "unused_output.rstensor", true)
                    result = tensor.to_array(a)
                }
            }
            """
        )
        optimized = optimize_program(ir)
        save_calls = [
            instruction
            for block in optimized["functions"][0]["blocks"]
            for instruction in block["instructions"]
            if instruction.get("op") == "assign"
            and instruction["expr"].get("op") == "call_tensor"
            and instruction["expr"].get("function_id") == "tensor.save"
        ]
        self.assertEqual(len(save_calls), 1)

    def test_tensor_load_is_never_eliminated_even_when_unused(self):
        ir = _lower(
            """
            module M {
                calculation Answer {
                    let unused = tensor.load("does_not_matter.rstensor")
                    result = 1
                }
            }
            """
        )
        optimized = optimize_program(ir)
        load_calls = [
            instruction
            for block in optimized["functions"][0]["blocks"]
            for instruction in block["instructions"]
            if instruction.get("op") == "assign"
            and instruction["expr"].get("op") == "call_tensor"
            and instruction["expr"].get("function_id") == "tensor.load"
        ]
        self.assertEqual(len(load_calls), 1)


class LocalCseTests(OptimizerParityMixin, unittest.TestCase):
    def test_repeated_pure_expression_is_deduplicated(self):
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let a = 2
                    let b = 3
                    let c = a + b
                    let d = a + b
                    result = c + d
                }
            }
            """
        )
        self.assertEqual(results, {"Answer": 10})
        instructions = optimized["functions"][0]["blocks"][0]["instructions"]
        d_instruction = next(instruction for instruction in instructions if instruction.get("target") == "d")
        self.assertEqual(d_instruction["expr"], {"op": "local", "name": "c"})

    def test_self_referential_assign_is_not_cached_and_does_not_poison_later_reads(self):
        # `i = i + 1` must never populate the CSE cache under the key for
        # `i + 1`: a *later*, syntactically identical `i + 1` refers to
        # the *new* value of `i` and must not collapse to plain `i`.
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let i = 0
                    i = i + 1
                    let j = i + 1
                    result = j
                }
            }
            """
        )
        self.assertEqual(results, {"Answer": 2})
        instructions = optimized["functions"][0]["blocks"][0]["instructions"]
        j_instruction = next(instruction for instruction in instructions if instruction.get("target") == "j")
        # Must still be a real binary add, not a wrongly-cached bare local.
        self.assertEqual(j_instruction["expr"]["op"], "binary")

    def test_reassignment_invalidates_cached_expressions_reading_old_value(self):
        optimized, results = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let x = 1
                    let a = x + 1
                    x = 5
                    let b = x + 1
                    result = a + b
                }
            }
            """
        )
        self.assertEqual(results, {"Answer": 8})
        instructions = optimized["functions"][0]["blocks"][0]["instructions"]
        b_instruction = next(instruction for instruction in instructions if instruction.get("target") == "b")
        self.assertNotEqual(b_instruction["expr"], {"op": "local", "name": "a"})

    def test_tensor_calls_are_never_deduplicated(self):
        # Both `a` and `b` are read (by the final add), so dead-local
        # elimination cannot remove either -- this isolates CSE as the
        # only pass that could merge the two structurally-identical
        # `tensor.create` calls, and confirms it deliberately does not.
        ir = _lower(
            """
            module M {
                calculation Answer {
                    let a = tensor.create([1.0], "f64")
                    let b = tensor.create([1.0], "f64")
                    result = tensor.to_array(tensor.add(a, b))
                }
            }
            """
        )
        optimized = optimize_program(ir)
        create_calls = [
            instruction
            for block in optimized["functions"][0]["blocks"]
            for instruction in block["instructions"]
            if instruction.get("op") == "assign"
            and instruction["expr"].get("op") == "call_tensor"
            and instruction["expr"].get("function_id") == "tensor.create"
        ]
        self.assertEqual(len(create_calls), 2)

    def test_optimizer_calls_are_never_deduplicated(self):
        # Same rationale as test_tensor_calls_are_never_deduplicated:
        # `optimizer.sgd` is pure (so unused results ARE eliminated, see
        # OptimizerFunctionsInteractionTests below), but a structurally
        # identical, both-read pair must not be CSE-merged -- an
        # optimizer step is exactly the kind of call whose two
        # "identical" invocations are conceptually a repeated action, not
        # interchangeable values, matching how call_tensor is treated.
        ir = _lower(
            """
            module M {
                calculation Answer {
                    let w = tensor.create([1.0], "f64")
                    let g = tensor.create([0.1], "f64")
                    let a = optimizer.sgd(w, g, 0.5)
                    let b = optimizer.sgd(w, g, 0.5)
                    result = tensor.to_array(tensor.add(a, b))
                }
            }
            """
        )
        optimized = optimize_program(ir)
        sgd_calls = [
            instruction
            for block in optimized["functions"][0]["blocks"]
            for instruction in block["instructions"]
            if instruction.get("op") == "assign"
            and instruction["expr"].get("op") == "call_optimizer"
            and instruction["expr"].get("function_id") == "optimizer.sgd"
        ]
        self.assertEqual(len(sgd_calls), 2)


class OptimizerFunctionsInteractionTests(OptimizerParityMixin, unittest.TestCase):
    """The Phase 7 IR optimizer's interaction with the `optimizer.*`
    namespace itself (added after this file was first written): an
    unused optimizer step is dead-code-eliminated, and a used one
    survives optimization with an identical result."""

    def test_unused_optimizer_step_is_eliminated(self):
        ir = _lower(
            """
            module M {
                calculation Answer {
                    let w = tensor.create([1.0], "f64")
                    let g = tensor.create([0.1], "f64")
                    let unused = optimizer.sgd(w, g, 0.9)
                    result = tensor.to_array(w)
                }
            }
            """
        )
        optimized = optimize_program(ir)
        for block in optimized["functions"][0]["blocks"]:
            for instruction in block["instructions"]:
                self.assertNotEqual(instruction.get("target"), "unused")

    def test_optimizer_step_program_survives_optimization(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    let w = tensor.create([1.0, 2.0], "f64")
                    let g = tensor.create([0.1, 0.2], "f64")
                    let unused = optimizer.sgd(w, g, 0.1)
                    let updated = optimizer.sgd(w, g, 0.5)
                    result = tensor.to_array(updated)
                }
            }
            """
        )


class TensorDifferentialTests(OptimizerParityMixin, unittest.TestCase):
    def test_matmul_program_survives_optimization(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    let a = tensor.create([[1.0, 2.0], [3.0, 4.0]], "f64")
                    let b = tensor.create([[5.0, 6.0], [7.0, 8.0]], "f64")
                    let unused = tensor.create([0.0], "f64")
                    result = tensor.to_array(tensor.matmul(a, b))
                }
            }
            """
        )

    def test_gradient_descent_step_survives_optimization(self):
        self.assert_parity(
            """
            module M {
                calculation Answer {
                    let w = tensor.parameter(tensor.create([1.0, 2.0], "f64"))
                    let target = tensor.create([2.0, 2.0], "f64")
                    let diff = tensor.subtract(w, target)
                    let loss = tensor.sum(tensor.multiply(diff, diff))
                    let grads = tensor.grad(loss, [w])
                    let updated = tensor.subtract(w, tensor.multiply(grads[0], 0.1))
                    result = tensor.to_array(updated)
                }
            }
            """
        )


if __name__ == "__main__":
    unittest.main()
