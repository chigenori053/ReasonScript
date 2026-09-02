"""Phase 5 gate: Rust autograd (tape/VJP/gradient accumulation) vs.
Python, for the ops `tensor_dispatch.rs` tapes (see its module doc for
the exact list -- everything Phase 4 implements except comparisons,
creation, inspection, RNG, and I/O, which are non-differentiable or
don't produce floats).

Same differential pattern as the other `computation_ir_tests` parity
suites: lower once, run through both `interpret_program` and the Rust
CLI, assert `calculation_results` / error codes agree. Skips (doesn't
fail) if the Rust binary isn't built.

Optimizers (SGD/Momentum/Adam/AdamW) are covered separately in
`test_computation_ir_optimizer_functions.py`: they are pure `optimizer.*`
step functions, not part of this file's autograd tape/VJP surface (their
output is a fresh, untracked Tensor, never wired onto the grad tape).
"""

from __future__ import annotations

import unittest

from frontend.computation_ir import interpret_program, lower_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import IntegratedRuntimeError, LoopLimitError
from frontend.language_surface import parse
from frontend.tensor import TensorError

_BINARY = find_binary()


def _python_outcome(source: str):
    program = parse(source)
    ir = lower_program(program)
    try:
        result = interpret_program(ir)
    except (IntegratedRuntimeError, LoopLimitError) as error:
        return None, getattr(error, "code", None)
    except TensorError as error:
        return None, error.diagnostic.code
    return dict(result.calculation_results), None


def _rust_outcome(source: str):
    program = parse(source)
    ir = lower_program(program)
    outcome = run_ir(ir, binary=_BINARY)
    if outcome.ok:
        return outcome.calculation_results, None
    return None, outcome.error_code


@unittest.skipUnless(_BINARY is not None, "reason-computation-runtime binary not built")
class AutogradParityTests(unittest.TestCase):
    def assert_parity(self, source: str):
        python_results, python_error = _python_outcome(source)
        rust_results, rust_error = _rust_outcome(source)
        self.assertEqual(python_error, rust_error, f"error code mismatch for:\n{source}")
        if python_error is None:
            self.assertEqual(python_results, rust_results, f"result mismatch for:\n{source}")
        return python_results

    def test_broadcast_ops_gradient(self):
        for op in ("add", "subtract", "multiply", "divide", "maximum", "minimum"):
            results = self.assert_parity(
                f"""module M {{
  calculation Answer {{
    let a = tensor.parameter(tensor.create([2.0, 3.0], "f64"))
    let b = tensor.create([5.0, 1.0], "f64")
    let c = tensor.{op}(a, b)
    let loss = tensor.sum(c)
    let gradients = tensor.grad(loss, [a])
    result = tensor.to_array(gradients[0])
  }}
}}
"""
            )
            self.assertIn("Answer", results)

    def test_power_gradient(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.parameter(tensor.create([2.0, 3.0], "f64"))
    let c = tensor.power(a, tensor.create([2.0, 2.0], "f64"))
    let loss = tensor.sum(c)
    let gradients = tensor.grad(loss, [a])
    result = tensor.to_array(gradients[0])
  }
}
"""
        )
        # d(x^2)/dx = 2x
        self.assertEqual(results["Answer"], [4.0, 6.0])

    def test_unary_gradients(self):
        for op in ("negate", "abs", "exp", "log", "sqrt"):
            results = self.assert_parity(
                f"""module M {{
  calculation Answer {{
    let a = tensor.parameter(tensor.create([2.0, 3.0], "f64"))
    let c = tensor.{op}(a)
    let loss = tensor.sum(c)
    let gradients = tensor.grad(loss, [a])
    result = tensor.to_array(gradients[0])
  }}
}}
"""
            )
            self.assertIn("Answer", results)

    def test_reshape_gradient(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.parameter(tensor.create([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], "f64"))
    let c = tensor.reshape(a, [3, 2])
    let loss = tensor.sum(c)
    let gradients = tensor.grad(loss, [a])
    result = tensor.to_array(gradients[0])
  }
}
"""
        )
        self.assertEqual(results["Answer"], [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]])

    def test_flatten_gradient(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.parameter(tensor.create([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], "f64"))
    let c = tensor.flatten(a)
    let loss = tensor.sum(c)
    let gradients = tensor.grad(loss, [a])
    result = tensor.to_array(gradients[0])
  }
}
"""
        )
        self.assertEqual(results["Answer"], [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]])

    def test_squeeze_unsqueeze_gradient(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.parameter(tensor.create([[1.0, 2.0, 3.0]], "f64"))
    let squeezed = tensor.squeeze(a, 0)
    let unsqueezed = tensor.unsqueeze(squeezed, 1)
    let loss = tensor.sum(unsqueezed)
    let gradients = tensor.grad(loss, [a])
    result = tensor.to_array(gradients[0])
  }
}
"""
        )
        self.assertEqual(results["Answer"], [[1.0, 1.0, 1.0]])

    def test_cast_gradient(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.parameter(tensor.create([2.0, 3.0], "f64"))
    let c = tensor.cast(a, "f32")
    let loss = tensor.sum(c)
    let gradients = tensor.grad(loss, [a])
    result = tensor.to_array(gradients[0])
  }
}
"""
        )
        self.assertEqual(results["Answer"], [1.0, 1.0])

    def test_transpose_gradient(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.parameter(tensor.create([[1.0, 2.0], [3.0, 4.0]], "f64"))
    let c = tensor.transpose(a, 0, 1)
    let weighted = tensor.multiply(c, tensor.create([[1.0, 2.0], [3.0, 4.0]], "f64"))
    let loss = tensor.sum(weighted)
    let gradients = tensor.grad(loss, [a])
    result = tensor.to_array(gradients[0])
  }
}
"""
        )
        self.assertEqual(results["Answer"], [[1.0, 3.0], [2.0, 4.0]])

    def test_sum_mean_with_axis_gradient(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.parameter(tensor.create([[1.0, 2.0], [3.0, 4.0]], "f64"))
    let s = tensor.sum(a, [0], false)
    let m = tensor.mean(a, [1], false)
    let loss = tensor.add(tensor.sum(s), tensor.sum(m))
    let gradients = tensor.grad(loss, [a])
    result = tensor.to_array(gradients[0])
  }
}
"""
        )
        self.assertIn("Answer", results)

    def test_min_max_gradient(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.parameter(tensor.create([[1.0, 5.0], [4.0, 2.0]], "f64"))
    let mx = tensor.max(a, 1, false)
    let mn = tensor.min(a, 1, false)
    let loss = tensor.add(tensor.sum(mx), tensor.sum(mn))
    let gradients = tensor.grad(loss, [a])
    result = tensor.to_array(gradients[0])
  }
}
"""
        )
        # max picks [5,4] (indices 1,0), min picks [1,2] (indices 0,1):
        # gradient 1.0 at each selected position, 0.0 elsewhere.
        self.assertEqual(results["Answer"], [[1.0, 1.0], [1.0, 1.0]])

    def test_matmul_gradient(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.parameter(tensor.create([[1.0, 2.0], [3.0, 4.0]], "f64"))
    let b = tensor.create([[5.0, 6.0], [7.0, 8.0]], "f64")
    let c = tensor.matmul(a, b)
    let loss = tensor.sum(c)
    let gradients = tensor.grad(loss, [a])
    result = tensor.to_array(gradients[0])
  }
}
"""
        )
        self.assertEqual(results["Answer"], [[11.0, 15.0], [11.0, 15.0]])

    def test_dot_and_norm_gradient(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.parameter(tensor.create([3.0, 4.0], "f64"))
    let b = tensor.create([1.0, 1.0], "f64")
    let d = tensor.dot(a, b)
    let n = tensor.norm(a, 2)
    let loss = tensor.add(d, n)
    let gradients = tensor.grad(loss, [a])
    result = tensor.to_array(gradients[0])
  }
}
"""
        )
        # d(dot)/da = b = [1,1]; d(norm2)/da = a/||a|| = [0.6, 0.8]
        self.assertAlmostEqual(results["Answer"][0], 1.6, places=9)
        self.assertAlmostEqual(results["Answer"][1], 1.8, places=9)

    def test_parameter_detach_requires_grad(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let raw = tensor.create([1.0, 2.0], "f64")
    let p = tensor.parameter(raw)
    let tracked = tensor.requires_grad(p)
    let d = tensor.detach(p)
    let untracked = tensor.requires_grad(d)
    result = array.append([tracked], untracked)
  }
}
"""
        )
        self.assertEqual(results["Answer"], [True, False])

    def test_scalar_literal_operand_is_auto_boxed(self):
        # `tensor.multiply(x, 0.1)` -- Python auto-promotes the bare
        # scalar literal to an (untracked) Tensor via `_operand()`;
        # earlier iterations of the Rust port required an explicit
        # Tensor handle here and raised RT-CALL-005 for this exact
        # program before operand_id() was added.
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.parameter(tensor.create([2.0, 4.0], "f64"))
    let scaled = tensor.multiply(a, 0.1)
    result = tensor.to_array(scaled)
  }
}
"""
        )
        self.assertEqual(results["Answer"], [0.2, 0.4])

    def test_gradient_descent_training_loop_matches(self):
        results = self.assert_parity(
            """module IterativeAutograd {
  calculation Answer {
    let iteration = 0
    let input = tensor.create([1.0], "f64")
    let weight = tensor.parameter(tensor.create([1.0], "f64"))
    while iteration < 20 {
      let prediction = tensor.multiply(input, weight)
      let loss = tensor.mean(tensor.power(prediction, 2.0))
      let gradients = tensor.grad(loss, [weight])
      let updated = tensor.subtract(weight, tensor.multiply(gradients[0], 0.1))
      weight = tensor.parameter(tensor.detach(updated))
      iteration = iteration + 1
    }
    result = tensor.to_array(weight)
  }
}
"""
        )
        self.assertAlmostEqual(results["Answer"][0], 0.8**20, places=12)

    def test_non_scalar_loss_error_code_matches(self):
        self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.parameter(tensor.create([1.0, 2.0], "f64"))
    let loss = tensor.multiply(a, a)
    let gradients = tensor.grad(loss, [a])
    result = tensor.to_array(gradients[0])
  }
}
"""
        )

    def test_grad_of_non_parameter_error_code_matches(self):
        self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.create([1.0, 2.0], "f64")
    let loss = tensor.sum(tensor.multiply(a, a))
    let gradients = tensor.grad(loss, [a])
    result = tensor.to_array(gradients[0])
  }
}
"""
        )

    def test_parameter_of_non_float_dtype_error_code_matches(self):
        self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.create([1, 2], "i64")
    let p = tensor.parameter(a)
    result = tensor.to_array(p)
  }
}
"""
        )


if __name__ == "__main__":
    unittest.main()
