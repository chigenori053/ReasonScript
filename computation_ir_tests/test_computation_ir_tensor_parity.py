"""Phase 4 gate: Rust Tensor forward vs. Python, for the ~50 tensor.*
functions the Rust VM implements (see
ReasonComputationRuntime/crates/computation-ir/src/tensor_dispatch.rs's
module doc for the exact list and what's deferred).

Each case lowers a program once and runs it through both the Python IR
interpreter and the Rust CLI, asserting they agree on
`calculation_results` / error code -- the same pattern as
test_computation_ir_rust_parity.py, extended to cover creation,
inspection, shape ops, broadcast/comparison/unary elementwise, reduction,
linear algebra, cast, and the four RNG functions. `.rstensor` save/load
round-tripping and cross-language interop (Rust writes, Python reads and
vice versa) are also covered here, since that's an explicit Phase 4 gate
item ("`.rstensor`...Python writer/Rust reader、Rust writer/Python reader").

Skips (doesn't fail) if the Rust binary hasn't been built, same as
test_computation_ir_rust_parity.py.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from frontend.computation_ir import interpret_program, lower_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import IntegratedRuntimeError, LoopLimitError
from frontend.language_surface import parse
from frontend.tensor import TensorError, TensorRuntime

_BINARY = find_binary()


def _python_outcome(source: str, *, resource_root: Path | None = None):
    program = parse(source)
    ir = lower_program(program)
    try:
        result = interpret_program(
            ir,
            resource_root=resource_root,
            filesystem_read=resource_root is not None,
            filesystem_write=resource_root is not None,
        )
    except (IntegratedRuntimeError, LoopLimitError) as error:
        return None, getattr(error, "code", None)
    except TensorError as error:
        return None, error.diagnostic.code
    return dict(result.calculation_results), None


def _rust_outcome(source: str, *, cwd: Path | None = None):
    program = parse(source)
    ir = lower_program(program)
    outcome = run_ir(ir, binary=_BINARY, cwd=cwd)
    if outcome.ok:
        return outcome.calculation_results, None
    return None, outcome.error_code


@unittest.skipUnless(_BINARY is not None, "reason-computation-runtime binary not built")
class TensorForwardParityTests(unittest.TestCase):
    def assert_parity(self, source: str):
        python_results, python_error = _python_outcome(source)
        rust_results, rust_error = _rust_outcome(source)
        self.assertEqual(python_error, rust_error, f"error code mismatch for:\n{source}")
        if python_error is None:
            self.assertEqual(python_results, rust_results, f"result mismatch for:\n{source}")
        return python_results

    def test_creation_shape_inspection(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.zeros([2, 3], "f64")
    let b = tensor.ones([2, 3], "f64")
    let c = tensor.full([2, 3], 5.0, "f64")
    let combined = tensor.add(tensor.add(a, b), c)
    let r = tensor.rank(combined)
    let s = tensor.size(combined)
    let d = tensor.dimension(combined, 1)
    result = r + s + d
  }
}
"""
        )
        self.assertEqual(results["Answer"], 2 + 6 + 3)

    def test_shape_ops(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.create([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], "f64")
    let reshaped = tensor.reshape(a, [2, 3])
    let transposed = tensor.transpose(reshaped, 0, 1)
    let unsq = tensor.unsqueeze(transposed, 0)
    let sq = tensor.squeeze(unsq, 0)
    let flat = tensor.flatten(sq)
    result = tensor.to_array(flat)
  }
}
"""
        )
        self.assertEqual(results["Answer"], [1.0, 4.0, 2.0, 5.0, 3.0, 6.0])

    def test_broadcast_binary_ops(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.create([[1.0, 2.0], [3.0, 4.0]], "f64")
    let b = tensor.create([10.0, 20.0], "f64")
    let added = tensor.add(a, b)
    let sub = tensor.subtract(added, b)
    let mul = tensor.multiply(sub, b)
    let div = tensor.divide(mul, b)
    let pow = tensor.power(div, tensor.create([2.0], "f64"))
    let mx = tensor.maximum(pow, tensor.create([5.0], "f64"))
    let mn = tensor.minimum(mx, tensor.create([100.0], "f64"))
    result = tensor.to_array(mn)
  }
}
"""
        )
        self.assertEqual(results["Answer"], [[5.0, 5.0], [9.0, 16.0]])

    def test_comparisons(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.create([1.0, 2.0, 3.0], "f64")
    let b = tensor.create([3.0, 2.0, 1.0], "f64")
    let eq = tensor.to_array(tensor.equal(a, b))
    let ne = tensor.to_array(tensor.not_equal(a, b))
    let gt = tensor.to_array(tensor.greater(a, b))
    let ge = tensor.to_array(tensor.greater_equal(a, b))
    let lt = tensor.to_array(tensor.less(a, b))
    let le = tensor.to_array(tensor.less_equal(a, b))
    result = array.append(array.append(array.append(array.append(array.append([eq], ne), gt), ge), lt), le)
  }
}
"""
        )
        self.assertEqual(
            results["Answer"],
            [
                [False, True, False],
                [True, False, True],
                [False, False, True],
                [False, True, True],
                [True, False, False],
                [True, True, False],
            ],
        )

    def test_unary_elementwise(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.create([-4.0, 9.0], "f64")
    let negated = tensor.to_array(tensor.negate(a))
    let absolute = tensor.to_array(tensor.abs(a))
    let sqrted = tensor.to_array(tensor.sqrt(tensor.abs(a)))
    result = array.append(array.append([negated], absolute), sqrted)
  }
}
"""
        )
        self.assertEqual(results["Answer"], [[4.0, -9.0], [4.0, 9.0], [2.0, 3.0]])

    def test_exp_log(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.create([1.0, 2.0], "f64")
    let e = tensor.exp(a)
    let back = tensor.log(e)
    result = tensor.to_array(back)
  }
}
"""
        )
        self.assertAlmostEqual(results["Answer"][0], 1.0, places=9)
        self.assertAlmostEqual(results["Answer"][1], 2.0, places=9)

    def test_reductions_with_axis_and_keep_dims(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.create([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], "f64")
    let total = tensor.to_array(tensor.sum(a))
    let mean_axis = tensor.to_array(tensor.mean(a, [0], false))
    let min_keep = tensor.to_array(tensor.min(a, 1, true))
    let max_keep = tensor.to_array(tensor.max(a, 1, true))
    result = array.append(array.append(array.append([total], mean_axis), min_keep), max_keep)
  }
}
"""
        )
        self.assertEqual(
            results["Answer"],
            [21.0, [2.5, 3.5, 4.5], [[1.0], [4.0]], [[3.0], [6.0]]],
        )

    def test_argmax_argmin(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.create([[3.0, 1.0, 2.0], [0.0, 5.0, 4.0]], "f64")
    let am = tensor.to_array(tensor.argmax(a, 1, false))
    let ai = tensor.to_array(tensor.argmin(a, 1, false))
    result = array.append([am], ai)
  }
}
"""
        )
        self.assertEqual(results["Answer"], [[0, 1], [1, 0]])

    def test_dot_matmul_norm(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.create([1.0, 2.0, 3.0], "f64")
    let b = tensor.create([4.0, 5.0, 6.0], "f64")
    let dotted = tensor.scalar(tensor.dot(a, b))
    let m1 = tensor.create([[1.0, 2.0], [3.0, 4.0]], "f64")
    let m2 = tensor.create([[5.0, 6.0], [7.0, 8.0]], "f64")
    let matmulled = tensor.to_array(tensor.matmul(m1, m2))
    let normed = tensor.scalar(tensor.norm(a, 2))
    result = array.append(array.append([dotted], matmulled), normed)
  }
}
"""
        )
        self.assertEqual(results["Answer"][0], 32.0)
        self.assertEqual(results["Answer"][1], [[19.0, 22.0], [43.0, 50.0]])
        self.assertAlmostEqual(results["Answer"][2], 14.0**0.5, places=9)

    def test_cast(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.create([1.7, 2.3], "f64")
    let casted = tensor.cast(a, "i64")
    result = tensor.to_array(casted)
  }
}
"""
        )
        self.assertEqual(results["Answer"], [1, 2])

    def test_random_uniform_and_normal_and_bernoulli_and_permutation(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let u = tensor.to_array(tensor.random_uniform([3], -1.0, 1.0, 42, 0, "f64"))
    let n = tensor.to_array(tensor.random_normal([3], 0.0, 1.0, 42, 1, "f64"))
    let b = tensor.to_array(tensor.random_bernoulli([4], 0.5, 42, 2))
    let p = tensor.to_array(tensor.random_permutation(5, 42, 3))
    result = array.append(array.append(array.append([u], n), b), p)
  }
}
"""
        )
        # Golden values are whatever the SHA-256 counter RNG deterministically
        # produces; the assertion that matters is Rust == Python, already
        # checked by assert_parity above. Sanity-check shapes/types here.
        answer = results["Answer"]
        self.assertEqual(len(answer[0]), 3)
        self.assertEqual(len(answer[1]), 3)
        self.assertEqual(len(answer[2]), 4)
        self.assertEqual(sorted(answer[3]), [0, 1, 2, 3, 4])

    def test_division_by_zero_error_code_matches(self):
        self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.create([1.0], "f64")
    let b = tensor.create([0.0], "f64")
    result = tensor.to_array(tensor.divide(a, b))
  }
}
"""
        )

    def test_broadcast_shape_mismatch_error_code_matches(self):
        self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.create([[1.0, 2.0, 3.0]], "f64")
    let b = tensor.create([1.0, 2.0], "f64")
    result = tensor.to_array(tensor.add(a, b))
  }
}
"""
        )

    def test_matmul_shape_mismatch_error_code_matches(self):
        self.assert_parity(
            """module M {
  calculation Answer {
    let a = tensor.create([[1.0, 2.0]], "f64")
    let b = tensor.create([[1.0, 2.0]], "f64")
    result = tensor.to_array(tensor.matmul(a, b))
  }
}
"""
        )

    def test_rust_writes_python_reads(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = """module M {
  calculation Answer {
    let a = tensor.create([[1, 2], [3, 4]], "i32")
    let receipt = tensor.save(a, "weights.rstensor", true)
    result = receipt
  }
}
"""
            program = parse(source)
            ir = lower_program(program)
            outcome = run_ir(ir, binary=_BINARY, cwd=tmp_path)
            self.assertTrue(outcome.ok, outcome.error_code)

            runtime = TensorRuntime(resource_root=tmp_path, filesystem_read=True)
            loaded = runtime.call("tensor.load", "weights.rstensor")
            self.assertEqual(runtime.to_array(loaded), [[1, 2], [3, 4]])
            self.assertEqual(loaded.dtype, "i32")

    def test_python_writes_rust_reads(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            runtime = TensorRuntime(
                resource_root=tmp_path, filesystem_read=True, filesystem_write=True
            )
            tensor = runtime.call("tensor.create", [1.5, 2.5, 3.5], "f32")
            runtime.call("tensor.save", tensor, "weights.rstensor", True)

            source = """module M {
  calculation Answer {
    let a = tensor.load("weights.rstensor")
    result = tensor.to_array(a)
  }
}
"""
            program = parse(source)
            ir = lower_program(program)
            outcome = run_ir(ir, binary=_BINARY, cwd=tmp_path)
            self.assertTrue(outcome.ok, outcome.error_code)
            self.assertEqual(outcome.calculation_results["Answer"], [1.5, 2.5, 3.5])


if __name__ == "__main__":
    unittest.main()
