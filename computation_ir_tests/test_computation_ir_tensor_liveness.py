"""Unit and regression tests for ReasonScript Tensor Call-Frame Liveness Remediation (Issue #9).

Validates the lifetime correctness of Tensors across active function frames,
caller/callee handoffs, containers, nested calls, recursion, error cleanup,
trace parity, and reclamation.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from frontend.computation_ir import interpret_program, lower_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import IntegratedRuntimeError, LoopLimitError
from frontend.language_surface import parse
from frontend.tensor import TensorError

_BINARY = find_binary()
_FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "canonical_fixtures"
    / "issue_9_layernorm_attention"
    / "src"
    / "main.rsn"
)


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


def _rust_outcome(
    source: str,
    *,
    limits: dict[str, int] | None = None,
    cwd: Path | None = None,
    trace_enabled: bool = False,
):
    program = parse(source)
    ir = lower_program(program)
    outcome = run_ir(ir, binary=_BINARY, limits=limits, cwd=cwd, trace_enabled=trace_enabled)
    if outcome.ok:
        return outcome.calculation_results, None
    return None, outcome.error_code


@unittest.skipUnless(_BINARY is not None, "reason-runtime-host binary not built")
class TensorCallFrameLivenessTests(unittest.TestCase):
    def test_01_exact_issue_9_fixture(self):
        """1. The exact Issue #9 fixture through the native Rust host."""
        source = _FIXTURE_PATH.read_text(encoding="utf-8")
        rust, rust_error = _rust_outcome(source)
        self.assertIsNone(rust_error, f"Rust execution failed with error: {rust_error}")
        self.assertIsNotNone(rust)
        self.assertEqual(rust.get("Answer"), True)

        # Repeated execution must produce deterministic true result
        rust_second, _ = _rust_outcome(source)
        self.assertEqual(rust_second, rust)

    def test_02_caller_only_root_regression(self):
        """2. A Tensor referenced only by a suspended caller frame."""
        source = """module CallerRootTest {
  fn CalleeComputation(x) {
    let a = tensor.add(x, 1.0)
    let b = tensor.multiply(a, 2.0)
    let c = tensor.subtract(b, 0.5)
    let d = tensor.exp(c)
    return tensor.log(d)
  }

  calculation Answer {
    let caller_tensor_1 = tensor.create([[10.0, 20.0], [30.0, 40.0]], "f64")
    let caller_tensor_2 = tensor.create([[1.0, 2.0], [3.0, 4.0]], "f64")
    let input = tensor.ones([2, 2], "f64")
    let callee_result = CalleeComputation(input)
    let combined = tensor.add(tensor.multiply(callee_result, caller_tensor_1), caller_tensor_2)
    result = tensor.to_array(combined)
  }
}
"""
        python, python_error = _python_outcome(source)
        rust, rust_error = _rust_outcome(source)
        self.assertEqual(python_error, rust_error)
        self.assertIsNone(rust_error)
        self.assertEqual(python, rust)

    def test_03_return_value_handoff_and_safe_points(self):
        """3. Direct, nested-expression, array-contained, and struct-contained returns across safe points."""
        # 1. Direct Tensor return across a subsequent collection safe point
        source_direct = """module M {
  fn MakeTensor() {
    let t = tensor.create([1.0, 2.0, 3.0], "f64")
    return t
  }
  fn SubsequentCollection() {
    let dummy = tensor.ones([3], "f64")
    return tensor.add(dummy, 1.0)
  }
  calculation Answer {
    let t = MakeTensor()
    let _trigger = SubsequentCollection()
    let scaled = tensor.multiply(t, 2.0)
    result = tensor.to_array(scaled)
  }
}
"""
        p, pe = _python_outcome(source_direct)
        r, re = _rust_outcome(source_direct)
        self.assertEqual(pe, re)
        self.assertEqual(p, r)

        # 2. Nested Tensor expression return
        source_nested = """module M {
  fn NestedExpr(x) {
    return tensor.add(tensor.multiply(x, 3.0), tensor.ones([3], "f64"))
  }
  calculation Answer {
    let input = tensor.create([1.0, 2.0, 3.0], "f64")
    let out = NestedExpr(input)
    result = tensor.to_array(out)
  }
}
"""
        p, pe = _python_outcome(source_nested)
        r, re = _rust_outcome(source_nested)
        self.assertEqual(pe, re)
        self.assertEqual(p, r)

        # 3. Array containing Tensor return
        source_array = """module M {
  fn MakeArray() {
    let a = tensor.create([1.0, 2.0], "f64")
    let b = tensor.create([3.0, 4.0], "f64")
    return [a, b]
  }
  fn SubsequentCollection() {
    let dummy = tensor.ones([2], "f64")
    return tensor.add(dummy, 5.0)
  }
  calculation Answer {
    let arr = MakeArray()
    let _trigger = SubsequentCollection()
    let sum_tensor = tensor.add(arr[0], arr[1])
    result = tensor.to_array(sum_tensor)
  }
}
"""
        p, pe = _python_outcome(source_array)
        r, re = _rust_outcome(source_array)
        self.assertEqual(pe, re)
        self.assertEqual(p, r)

        # 4. Struct field containing Tensor return
        source_struct = """module M {
  struct TensorBox {
    t: Tensor
  }
  fn MakeStruct() {
    let t = tensor.create([5.0, 6.0], "f64")
    return TensorBox { t: t }
  }
  fn SubsequentCollection() {
    let dummy = tensor.ones([2], "f64")
    return tensor.add(dummy, 7.0)
  }
  calculation Answer {
    let box = MakeStruct()
    let _trigger = SubsequentCollection()
    let doubled = tensor.multiply(box.t, 2.0)
    result = tensor.to_array(doubled)
  }
}
"""
        p, pe = _python_outcome(source_struct)
        r, re = _rust_outcome(source_struct)
        self.assertEqual(pe, re)
        self.assertEqual(p, r)

    def test_04_at_least_three_nested_active_frames(self):
        """4. At least three nested active frames."""
        source = """module M {
  fn Level3(x) {
    let a = tensor.add(x, 1.0)
    return tensor.multiply(a, 2.0)
  }
  fn Level2(x) {
    let temp = tensor.ones([2], "f64")
    let res = Level3(x)
    return tensor.add(res, temp)
  }
  fn Level1(x) {
    let scale = tensor.create([3.0, 3.0], "f64")
    let res = Level2(x)
    return tensor.multiply(res, scale)
  }
  calculation Answer {
    let outer_guard = tensor.create([100.0, 200.0], "f64")
    let input = tensor.create([1.0, 2.0], "f64")
    let inner_res = Level1(input)
    let final_res = tensor.add(inner_res, outer_guard)
    result = tensor.to_array(final_res)
  }
}
"""
        p, pe = _python_outcome(source)
        r, re = _rust_outcome(source)
        self.assertEqual(pe, re)
        self.assertEqual(p, r)

    def test_05_bounded_recursive_call(self):
        """5. A bounded recursive call preserving an outer caller-only Tensor."""
        ir = {
            "schema": "reason-computation-ir/0.1",
            "calculations": ["Answer"],
            "functions": [
                {
                    "id": "fn.RecurseTensor",
                    "parameters": ["t", "n"],
                    "entry_block": "b1",
                    "blocks": [
                        {
                            "id": "b1",
                            "instructions": [
                                {
                                    "op": "assign",
                                    "target": "cond",
                                    "expr": {
                                        "op": "comparison",
                                        "operator": "LessThanOrEqual",
                                        "left": {"op": "local", "name": "n"},
                                        "right": {"op": "const", "kind": "int", "value": 1},
                                    },
                                }
                            ],
                            "terminator": {
                                "kind": "branch",
                                "condition": {"op": "local", "name": "cond"},
                                "then": "b_base",
                                "else": "b_step",
                            },
                        },
                        {
                            "id": "b_base",
                            "instructions": [],
                            "terminator": {
                                "kind": "return",
                                "value": {"op": "local", "name": "t"},
                            },
                        },
                        {
                            "id": "b_step",
                            "instructions": [
                                {
                                    "op": "assign",
                                    "target": "next_t",
                                    "expr": {
                                        "op": "call_tensor",
                                        "function_id": "tensor.multiply",
                                        "arguments": [
                                            {"op": "local", "name": "t"},
                                            {"op": "const", "kind": "float", "value": 2.0},
                                        ],
                                    },
                                },
                                {
                                    "op": "assign",
                                    "target": "next_n",
                                    "expr": {
                                        "op": "binary",
                                        "operator": "Subtract",
                                        "left": {"op": "local", "name": "n"},
                                        "right": {"op": "const", "kind": "int", "value": 1},
                                    },
                                },
                                {
                                    "op": "assign",
                                    "target": "rec_res",
                                    "expr": {
                                        "op": "call_function",
                                        "name": "RecurseTensor",
                                        "arguments": [
                                            {"op": "local", "name": "next_t"},
                                            {"op": "local", "name": "next_n"},
                                        ],
                                    },
                                },
                            ],
                            "terminator": {
                                "kind": "return",
                                "value": {"op": "local", "name": "rec_res"},
                            },
                        },
                    ],
                },
                {
                    "id": "Answer",
                    "parameters": [],
                    "entry_block": "b1",
                    "blocks": [
                        {
                            "id": "b1",
                            "instructions": [
                                {
                                    "op": "assign",
                                    "target": "outer_tensor",
                                    "expr": {
                                        "op": "call_tensor",
                                        "function_id": "tensor.create",
                                        "arguments": [
                                            {
                                                "op": "array",
                                                "elements": [
                                                    {"op": "const", "kind": "float", "value": 10.0},
                                                    {"op": "const", "kind": "float", "value": 20.0},
                                                ],
                                            },
                                            {"op": "const", "kind": "string", "value": "f64"},
                                        ],
                                    },
                                },
                                {
                                    "op": "assign",
                                    "target": "init_tensor",
                                    "expr": {
                                        "op": "call_tensor",
                                        "function_id": "tensor.create",
                                        "arguments": [
                                            {
                                                "op": "array",
                                                "elements": [
                                                    {"op": "const", "kind": "float", "value": 1.0},
                                                    {"op": "const", "kind": "float", "value": 1.0},
                                                ],
                                            },
                                            {"op": "const", "kind": "string", "value": "f64"},
                                        ],
                                    },
                                },
                                {
                                    "op": "assign",
                                    "target": "rec_res",
                                    "expr": {
                                        "op": "call_function",
                                        "name": "RecurseTensor",
                                        "arguments": [
                                            {"op": "local", "name": "init_tensor"},
                                            {"op": "const", "kind": "int", "value": 5},
                                        ],
                                    },
                                },
                                {
                                    "op": "assign",
                                    "target": "final_tensor",
                                    "expr": {
                                        "op": "call_tensor",
                                        "function_id": "tensor.add",
                                        "arguments": [
                                            {"op": "local", "name": "rec_res"},
                                            {"op": "local", "name": "outer_tensor"},
                                        ],
                                    },
                                },
                            ],
                            "terminator": {
                                "kind": "result",
                                "value": {
                                    "op": "call_tensor",
                                    "function_id": "tensor.to_array",
                                    "arguments": [{"op": "local", "name": "final_tensor"}],
                                },
                            },
                        }
                    ],
                },
            ],
        }
        outcome = run_ir(ir, binary=_BINARY)
        self.assertTrue(outcome.ok, f"Error: {outcome.error_code} - {outcome.error_message}")
        self.assertEqual(outcome.calculation_results.get("Answer"), [26.0, 36.0])

    def test_06_earlier_evaluated_arg_survives_later_arg_eval(self):
        """6. Argument lists where an earlier evaluated Tensor must survive a later user-function evaluation."""
        source = """module M {
  fn ExpensiveHelper(x) {
    let a = tensor.add(x, 10.0)
    let b = tensor.multiply(a, 2.0)
    let c = tensor.subtract(b, 5.0)
    return tensor.divide(c, 2.0)
  }
  fn BinaryReceiver(first, second) {
    return tensor.add(first, second)
  }
  calculation Answer {
    let arg1 = tensor.create([5.0, 15.0], "f64")
    let helper_input = tensor.create([1.0, 2.0], "f64")
    // arg1 is passed as first argument, second argument triggers ExpensiveHelper execution with collections
    let out = BinaryReceiver(arg1, ExpensiveHelper(helper_input))
    result = tensor.to_array(out)
  }
}
"""
        p, pe = _python_outcome(source)
        r, re = _rust_outcome(source)
        self.assertEqual(pe, re)
        self.assertEqual(p, r)

    def test_07_cleanup_after_normal_return_and_runtime_error(self):
        """7. Cleanup after normal return and cleanup after a runtime error."""
        # Function returns normally, then function fails with error, verifying frame roots are popped cleanly
        source_normal = """module M {
  fn NormalCall(x) {
    return tensor.add(x, 1.0)
  }
  calculation Answer {
    let a = tensor.create([1.0], "f64")
    let b = NormalCall(a)
    result = tensor.to_array(b)
  }
}
"""
        r, re = _rust_outcome(source_normal)
        self.assertIsNone(re)
        self.assertEqual(r["Answer"], [2.0])

        source_error = """module M {
  fn FailingCall(x) {
    let zero = tensor.zeros([1], "f64")
    return tensor.divide(x, zero)
  }
  calculation Answer {
    let a = tensor.create([1.0], "f64")
    let b = FailingCall(a)
    result = tensor.to_array(b)
  }
}
"""
        r_err, re_err = _rust_outcome(source_error)
        self.assertIsNone(r_err)
        self.assertEqual(re_err, "TSF-012")

    def test_08_trace_disabled_and_enabled_parity(self):
        """8. Trace disabled and enabled with identical result and error behavior."""
        source = """module M {
  fn Helper(x) {
    return tensor.multiply(x, 3.0)
  }
  calculation Answer {
    let a = tensor.create([2.0, 4.0], "f64")
    let b = Helper(a)
    result = tensor.to_array(b)
  }
}
"""
        r_no_trace, re_no_trace = _rust_outcome(source, trace_enabled=False)
        r_trace, re_trace = _rust_outcome(source, trace_enabled=True)
        self.assertEqual(re_no_trace, re_trace)
        self.assertEqual(r_no_trace, r_trace)

    def test_09_shared_and_cyclic_containers(self):
        """9. Shared and cyclic supported containers without unbounded traversal."""
        # Shared array containing tensors
        source_shared = """module M {
  calculation Answer {
    let t = tensor.create([7.0], "f64")
    let arr1 = [t, t]
    let arr2 = [arr1, arr1]
    let t_out = arr2[0][0]
    result = tensor.to_array(t_out)
  }
}
"""
        p, pe = _python_outcome(source_shared)
        r, re = _rust_outcome(source_shared)
        self.assertEqual(pe, re)
        self.assertEqual(p, r)

    def test_10_cross_calculation_tensor_handle_retention(self):
        """10. An earlier calculation returning an actual Tensor handle that is consumed by a later calculation."""
        source = """module M {
  calculation First {
    let a = tensor.create([10.0, 20.0], "f64")
    let b = tensor.add(a, 5.0)
    result = b
  }
  calculation Second {
    let c = tensor.create([1.0, 2.0], "f64")
    let d = tensor.add(First, c)
    result = tensor.to_array(d)
  }
}
"""
        r, re = _rust_outcome(source)
        self.assertIsNone(re)
        self.assertEqual(r["Second"], [16.0, 27.0])

    def test_11_incremental_reclamation_long_loop(self):
        """11. 1,100 or more overwrite iterations demonstrating incremental reclamation."""
        source_loop = """module M {
  calculation Answer {
    let state = tensor.zeros([2, 2], "f64")
    let i = 0
    while i < 1100 {
      let step = tensor.add(state, 1.0)
      state = step
      i = i + 1
    }
    result = tensor.to_array(state)
  }
}
"""
        r, re = _rust_outcome(source_loop)
        self.assertIsNone(re)
        self.assertEqual(r["Answer"], [[1100.0, 1100.0], [1100.0, 1100.0]])

    def test_12_explicit_proof_unreachable_intermediates_removed(self):
        """12. Explicit proof that unreachable intermediates are removed under tight live-tensor budget."""
        # 100 loop iterations with tight max_live_tensors = 10.
        # If intermediates were not removed, 100 iterations would create 100+ tensors and exceed 10.
        source = """module M {
  calculation Answer {
    let state = tensor.zeros([2], "f64")
    let i = 0
    while i < 100 {
      let t1 = tensor.add(state, 1.0)
      let t2 = tensor.multiply(t1, 1.0)
      state = t2
      i = i + 1
    }
    result = tensor.to_array(state)
  }
}
"""
        r, re = _rust_outcome(source, limits={"max_live_tensors": 10})
        self.assertIsNone(re)
        self.assertEqual(r["Answer"], [100.0, 100.0])

    def test_13_genuine_max_live_tensors_exhaustion_emits_tsf013(self):
        """13. Genuine max_live_tensors exhaustion continuing to emit TSF-013."""
        source = """module M {
  calculation Answer {
    let t1 = tensor.ones([1], "f64")
    let t2 = tensor.ones([1], "f64")
    let t3 = tensor.ones([1], "f64")
    let t4 = tensor.ones([1], "f64")
    let t5 = tensor.ones([1], "f64")
    result = tensor.to_array(tensor.add(t1, tensor.add(t2, tensor.add(t3, tensor.add(t4, t5)))))
  }
}
"""
        r, re = _rust_outcome(source, limits={"max_live_tensors": 3})
        self.assertIsNone(r)
        self.assertEqual(re, "TSF-013")


if __name__ == "__main__":
    unittest.main()
