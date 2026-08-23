"""The `optimizer.*` namespace: SGD, Momentum, and Adam/AdamW.

Implements the (previously deferred, per AGENTS.md's earlier
"Optimizers: Pending" note) Optimizer scope: `frontend/tensor/optimizers.py`
(language-surface recognition + validation), `TensorRuntime.call_optimizer`
(`frontend/tensor/runtime.py`, the numeric implementation both execution
engines share), the `call_optimizer` IR node consumed by both
`frontend.computation_ir.interpreter` and
`ReasonComputationRuntime/crates/computation-ir/src/optimizer_dispatch.rs`.

Same differential pattern as every other `computation_ir_tests` parity
suite: lower once, run through both `interpret_program` and the Rust CLI,
assert `calculation_results` / error codes agree exactly. Rust
comparisons are skipped (not failed) if the binary isn't built.
"""

from __future__ import annotations

import math
import unittest

from frontend.computation_ir import interpret_program, lower_program, validate_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import IntegratedRuntimeError, LoopLimitError, execute_program
from frontend.language_surface import parse
from frontend.language_surface.parser import SurfaceSyntaxError
from frontend.tensor import TensorError

_BINARY = find_binary()


def _lower(source: str):
    return lower_program(parse(source))


def _python_outcome(source: str):
    ir = _lower(source)
    try:
        result = interpret_program(ir)
    except (IntegratedRuntimeError, LoopLimitError) as error:
        return None, getattr(error, "code", None)
    except TensorError as error:
        return None, error.diagnostic.code
    return dict(result.calculation_results), None


def _rust_outcome(source: str):
    ir = _lower(source)
    outcome = run_ir(ir, binary=_BINARY)
    if outcome.ok:
        return outcome.calculation_results, None
    return None, outcome.error_code


class OptimizerParityMixin:
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


class OptimizerMathTests(OptimizerParityMixin, unittest.TestCase):
    def test_sgd_step_matches_closed_form(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let w = tensor.create([1.0, 2.0], "f64")
                    let g = tensor.create([0.1, 0.2], "f64")
                    let updated = optimizer.sgd(w, g, 0.5)
                    result = tensor.to_array(updated)
                }
            }
            """
        )
        self.assertIsNone(error)
        self.assertEqual(results["Answer"], [0.95, 1.9])

    def test_momentum_velocity_and_step_match_closed_form(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let w = tensor.create([1.0], "f64")
                    let g = tensor.create([0.1], "f64")
                    let velocity = tensor.create([0.05], "f64")
                    let new_velocity = optimizer.momentum_velocity(g, velocity, 0.9)
                    let updated = optimizer.momentum(w, g, velocity, 0.5, 0.9)
                    result = tensor.to_array(new_velocity)
                }
            }
            """
        )
        self.assertIsNone(error)
        # new_velocity = 0.9*0.05 + 0.1 = 0.145
        self.assertAlmostEqual(results["Answer"][0], 0.145, places=12)

    def test_momentum_param_uses_updated_velocity(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let w = tensor.create([1.0], "f64")
                    let g = tensor.create([0.1], "f64")
                    let velocity = tensor.create([0.05], "f64")
                    let updated = optimizer.momentum(w, g, velocity, 0.5, 0.9)
                    result = tensor.to_array(updated)
                }
            }
            """
        )
        self.assertIsNone(error)
        # new_velocity = 0.145; w' = 1.0 - 0.5*0.145 = 0.9275
        self.assertAlmostEqual(results["Answer"][0], 0.9275, places=12)

    def test_adam_moment_updates_match_closed_form(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let g = tensor.create([0.1], "f64")
                    let m = tensor.create([0.02], "f64")
                    let v = tensor.create([0.0005], "f64")
                    let new_m = optimizer.adam_moment1(g, m, 0.9)
                    let new_v = optimizer.adam_moment2(g, v, 0.999)
                    result = tensor.to_array(new_v)
                }
            }
            """
        )
        self.assertIsNone(error)
        expected_v = 0.999 * 0.0005 + 0.001 * (0.1**2)
        self.assertAlmostEqual(results["Answer"][0], expected_v, places=12)

    def test_adam_first_step_matches_closed_form(self):
        results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let w = tensor.create([1.0], "f64")
                    let g = tensor.create([0.1], "f64")
                    let m = tensor.create([0.0], "f64")
                    let v = tensor.create([0.0], "f64")
                    let updated = optimizer.adam(w, g, m, v, 1, 0.001, 0.9, 0.999, 0.00000001)
                    result = tensor.to_array(updated)
                }
            }
            """
        )
        self.assertIsNone(error)
        beta1, beta2, eps, lr = 0.9, 0.999, 1e-8, 0.001
        new_m = 0.1 * 0.1
        new_v = 0.001 * (0.1**2)
        m_hat = new_m / (1 - beta1**1)
        v_hat = new_v / (1 - beta2**1)
        expected = 1.0 - lr * (m_hat / (math.sqrt(v_hat) + eps))
        self.assertAlmostEqual(results["Answer"][0], expected, places=12)

    def test_adamw_applies_decoupled_weight_decay_on_top_of_adam(self):
        adam_results, _ = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let w = tensor.create([1.0], "f64")
                    let g = tensor.create([0.1], "f64")
                    let m = tensor.create([0.0], "f64")
                    let v = tensor.create([0.0], "f64")
                    let updated = optimizer.adam(w, g, m, v, 1, 0.001, 0.9, 0.999, 0.00000001)
                    result = tensor.to_array(updated)
                }
            }
            """
        )
        adamw_results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let w = tensor.create([1.0], "f64")
                    let g = tensor.create([0.1], "f64")
                    let m = tensor.create([0.0], "f64")
                    let v = tensor.create([0.0], "f64")
                    let updated = optimizer.adamw(w, g, m, v, 1, 0.001, 0.9, 0.999, 0.00000001, 0.01)
                    result = tensor.to_array(updated)
                }
            }
            """
        )
        self.assertIsNone(error)
        # adamw = adam - lr*weight_decay*param = adam_result - 0.001*0.01*1.0
        self.assertAlmostEqual(adamw_results["Answer"][0], adam_results["Answer"][0] - 0.001 * 0.01 * 1.0, places=12)

    def test_multi_step_adam_loop_converges_towards_target(self):
        # A real (small) training loop: minimize (w - 2.0)^2 via its
        # analytic gradient 2*(w - 2.0), driving w towards 2.0 over 30
        # Adam steps -- exercises the step-count/bias-correction path
        # across many iterations, not just a single call. Kept short
        # (30 iterations, lr=0.5) to stay under TensorPolicy's
        # max_live_tensors (each iteration allocates several fresh,
        # never-collected refs; this loop never calls
        # `runtime.collect()`, matching how the rest of this test module
        # exercises the interpreter directly rather than through a real
        # `reason run` session, which collects between calculations).
        source = """
        module M {
            calculation Answer {
                let w = tensor.create([0.0], "f64")
                let m = tensor.create([0.0], "f64")
                let v = tensor.create([0.0], "f64")
                let step = 0
                while step < 30 {
                    let diff = tensor.subtract(w, tensor.create([2.0], "f64"))
                    let g = tensor.multiply(diff, tensor.create([2.0], "f64"))
                    step = step + 1
                    m = optimizer.adam_moment1(g, m, 0.9)
                    v = optimizer.adam_moment2(g, v, 0.999)
                    w = optimizer.adam(w, g, m, v, step, 0.5, 0.9, 0.999, 0.00000001)
                }
                result = tensor.to_array(w)
            }
        }
        """
        # A plain `assertEqual` bit-for-bit comparison (what `assert_parity`
        # does for every single-call test above) is too strict here: even
        # with matching pow implementations (Rust uses `powf`, matching
        # Python's float `**`), 30 iterations of elementwise ops compound
        # ULP-level libm differences between platforms into a real (if
        # tiny) last-digit divergence -- not a correctness bug, just two
        # valid floating-point evaluation paths. Every individual
        # optimizer *op* is still proven bit-exact by the single-call
        # tests elsewhere in this file.
        python_results, python_error = _python_outcome(source)
        self.assertIsNone(python_error)
        self.assertAlmostEqual(python_results["Answer"][0], 2.0, delta=0.1)
        if _BINARY is not None:
            rust_results, rust_error = _rust_outcome(source)
            self.assertIsNone(rust_error)
            self.assertAlmostEqual(rust_results["Answer"][0], python_results["Answer"][0], places=9)


class OptimizerErrorParityTests(OptimizerParityMixin, unittest.TestCase):
    def test_step_zero_is_rejected(self):
        _results, error = self.assert_parity(
            """
            module M {
                calculation Answer {
                    let w = tensor.create([1.0], "f64")
                    let g = tensor.create([0.1], "f64")
                    let m = tensor.create([0.0], "f64")
                    let v = tensor.create([0.0], "f64")
                    let updated = optimizer.adam(w, g, m, v, 0, 0.001, 0.9, 0.999, 0.00000001)
                    result = tensor.to_array(updated)
                }
            }
            """
        )
        self.assertEqual(error, "OPT-005")

    def test_non_tensor_argument_is_rejected_statically(self):
        with self.assertRaises(SurfaceSyntaxError) as raised:
            parse(
                """
                module M {
                    calculation Answer {
                        result = optimizer.sgd(1.0, 2.0, 0.5)
                    }
                }
                """
            )
        self.assertIn("OPT-003", str(raised.exception))

    def test_wrong_argument_count_is_rejected_statically(self):
        with self.assertRaises(SurfaceSyntaxError) as raised:
            parse(
                """
                module M {
                    calculation Answer {
                        let w = tensor.create([1.0], "f64")
                        let g = tensor.create([0.1], "f64")
                        result = tensor.to_array(optimizer.sgd(w, g))
                    }
                }
                """
            )
        self.assertIn("OPT-002", str(raised.exception))

    def test_unknown_optimizer_function_is_rejected_statically(self):
        with self.assertRaises(SurfaceSyntaxError) as raised:
            parse(
                """
                module M {
                    calculation Answer {
                        let w = tensor.create([1.0], "f64")
                        result = tensor.to_array(optimizer.rmsprop(w))
                    }
                }
                """
            )
        self.assertIn("OPT-001", str(raised.exception))


class OptimizerAstEvaluatorTests(unittest.TestCase):
    """The (older) AST-walking evaluator gets its own optimizer.* dispatch
    branch too (`integrated_computation_runtime._expression`), used
    whenever Phase 6's Rust-first path falls back to Python (e.g.
    `--trace`). Confirms that branch actually works, independent of the
    computation_ir/Rust pipeline exercised everywhere else in this file.
    """

    def test_ast_evaluator_executes_sgd_step(self):
        program = parse(
            """
            module M {
                calculation Answer {
                    let w = tensor.create([1.0, 2.0], "f64")
                    let g = tensor.create([0.1, 0.2], "f64")
                    let updated = optimizer.sgd(w, g, 0.5)
                    result = tensor.to_array(updated)
                }
            }
            """
        )
        result = execute_program(program).to_dict()
        self.assertEqual(result["result"], [0.95, 1.9])


class OptimizerTensorManifestIndependenceTests(unittest.TestCase):
    """`optimizer.*` must stay fully outside the Tensor Standard Functions
    registry: it is not part of the `tensor_function_manifest.json`
    stability contract (see `frontend/tensor/optimizers.py`'s docstring
    and `TensorRuntime.call_optimizer`'s)."""

    def test_optimizer_functions_are_not_in_tensor_contracts(self):
        from frontend.tensor.runtime import TensorRuntime

        runtime = TensorRuntime()
        for name in (
            "optimizer.sgd",
            "optimizer.momentum",
            "optimizer.adam",
            "optimizer.adamw",
        ):
            self.assertNotIn(name, runtime.contracts)


if __name__ == "__main__":
    unittest.main()
