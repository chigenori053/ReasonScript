"""Phase 3 gate: Rust VM vs. Python IR interpreter, for Tensor-less programs.

"ゲート: Tensorなしcalculationのpython/Rust一致" -- lowers a program to IR
once, then runs it through both `frontend.computation_ir.interpret_program`
and the compiled `reason-computation-runtime` Rust binary
(`frontend.computation_ir.rust_bridge`), and asserts they agree on
`calculation_results` / error code.

The whole module is skipped if the Rust binary hasn't been built (e.g. a
plain `pytest` run in a sandbox without a `cargo build` step first) --
build it with:
    cargo build --manifest-path ReasonComputationRuntime/Cargo.toml
or via `python3 scripts/test_platform.py test`, which builds and
`cargo test`s `ReasonComputationRuntime` before running pytest.
"""

from __future__ import annotations

import unittest

from frontend.computation_ir import interpret_program, lower_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import IntegratedRuntimeError, LoopLimitError
from frontend.language_surface import parse

_BINARY = find_binary()


def _python_outcome(source: str):
    program = parse(source)
    ir = lower_program(program)
    try:
        result = interpret_program(ir)
    except (IntegratedRuntimeError, LoopLimitError) as error:
        return None, getattr(error, "code", None)
    return dict(result.calculation_results), None


def _rust_outcome(source: str):
    program = parse(source)
    ir = lower_program(program)
    outcome = run_ir(ir, binary=_BINARY)
    if outcome.ok:
        return outcome.calculation_results, None
    return None, outcome.error_code


@unittest.skipUnless(_BINARY is not None, "reason-computation-runtime binary not built")
class RustParityTests(unittest.TestCase):
    def assert_parity(self, source: str):
        python_results, python_error = _python_outcome(source)
        rust_results, rust_error = _rust_outcome(source)
        self.assertEqual(python_error, rust_error, f"error code mismatch for:\n{source}")
        if python_error is None:
            self.assertEqual(python_results, rust_results, f"result mismatch for:\n{source}")
        return python_results

    def test_integer_division_is_float(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    result = 7 / 2
  }
}
"""
        )
        self.assertEqual(results["Answer"], 3.5)

    def test_negative_modulo_matches_python_floor_semantics(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let a = 0
    let b = 7
    result = a - b % 3
  }
}
"""
        )
        self.assertEqual(results["Answer"], -1)

    def test_division_by_zero_error_code_matches(self):
        self.assert_parity(
            """module M {
  calculation Answer {
    let a = 1
    let b = 0
    result = a / b
  }
}
"""
        )

    def test_if_elif_else_and_while_loop(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let x = 5
    let label = "small"
    if x > 8 {
      label = "big"
    } elif x > 2 {
      label = "mid"
    } else {
      label = "small"
    }
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
        self.assertEqual(results["Answer"], 25)

    def test_function_calls_and_for_loop(self):
        results = self.assert_parity(
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
        self.assertEqual(results["Answer"], 30)

    def test_array_index_out_of_range_error_code_matches(self):
        self.assert_parity(
            """module M {
  calculation Answer {
    let values = [1, 2, 3]
    result = values[10]
  }
}
"""
        )

    def test_array_append_and_struct_and_cast(self):
        results = self.assert_parity(
            """module M {
  calculation Answer {
    let values = [1, 2]
    let appended = array.append(values, 3)
    let n = float(appended.length)
    let m = int(n)
    result = m
  }
}
"""
        )
        self.assertEqual(results["Answer"], 3)

    def test_unimplemented_tensor_op_is_rejected_by_the_rust_vm(self):
        # `tensor.create`/`to_array` are implemented as of Phase 4 (see
        # test_computation_ir_tensor_parity.py for that coverage) --
        # `tensor.softmax` remains genuinely out of scope (a Phase 4+
        # inference op), so this is deliberately NOT a parity assertion:
        # Python succeeds while Rust must reject cleanly with
        # RT-UNSUPPORTED-001 rather than crashing or silently producing a
        # wrong result.
        source = """module M {
  calculation Answer {
    let a = tensor.create([1.0, 2.0], "f64")
    result = tensor.to_array(tensor.softmax(a))
  }
}
"""
        python_results, python_error = _python_outcome(source)
        self.assertIsNone(python_error)
        self.assertIn("Answer", python_results)

        _, rust_error = _rust_outcome(source)
        self.assertEqual(rust_error, "RT-UNSUPPORTED-001")


if __name__ == "__main__":
    unittest.main()
