"""Comprehensive differential and liveness tests for Controlled Recursion (Phase 4).

Validates:
1. Direct recursion across AST evaluator, IR interpreter, and Rust VM host.
2. Mutual recursion across all execution environments.
3. Strict enforcement of max_call_depth and RT-CALL-003 error code parity.
4. Tensor resource liveness and caller-frame root retention across recursive call stacks.
5. Clean unwind and error recovery on call depth exhaustion.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from frontend.computation_ir import interpret_program, lower_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import (
    IntegratedComputationResult,
    IntegratedRuntimeError,
    LoopLimitError,
    execute_program,
)
from frontend.language_surface import parse
from frontend.tensor import TensorError

_BINARY = find_binary()


def _ast_outcome(source: str, *, max_call_depth: int = 128) -> tuple[dict[str, Any] | None, str | None]:
    program = parse(source)
    try:
        result = execute_program(program, max_call_depth=max_call_depth)
        return dict(result.calculation_results), None
    except (IntegratedRuntimeError, LoopLimitError) as error:
        return None, getattr(error, "code", None)
    except TensorError as error:
        return None, error.diagnostic.code


def _ir_outcome(source: str, *, max_call_depth: int = 128) -> tuple[dict[str, Any] | None, str | None]:
    program = parse(source)
    ir = lower_program(program)
    try:
        result = interpret_program(ir, max_call_depth=max_call_depth)
        return dict(result.calculation_results), None
    except (IntegratedRuntimeError, LoopLimitError) as error:
        return None, getattr(error, "code", None)
    except TensorError as error:
        return None, error.diagnostic.code


def _rust_outcome(
    source: str,
    *,
    limits: dict[str, int] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    program = parse(source)
    ir = lower_program(program)
    outcome = run_ir(ir, binary=_BINARY, limits=limits)
    if outcome.ok:
        return outcome.calculation_results, None
    return None, outcome.error_code


@unittest.skipUnless(_BINARY is not None, "reason-runtime-host binary not built")
class ControlledRecursionTests(unittest.TestCase):
    def test_01_direct_recursion_factorial(self):
        """Direct recursion calculates factorial correctly across AST, IR, and Rust."""
        source = """module FactorialModule {
  fn factorial(n: Int): Int {
    if n <= 1 {
      return 1
    }
    return n * factorial(n - 1)
  }

  calculation Answer {
    let f5 = factorial(5)
    let f7 = factorial(7)
    result = f5 + f7
  }
}
"""
        ast_res, ast_err = _ast_outcome(source)
        ir_res, ir_err = _ir_outcome(source)
        rust_res, rust_err = _rust_outcome(source)

        self.assertIsNone(ast_err)
        self.assertIsNone(ir_err)
        self.assertIsNone(rust_err)

        expected = {"Answer": 120 + 5040}
        self.assertEqual(ast_res, expected)
        self.assertEqual(ir_res, expected)
        self.assertEqual(rust_res, expected)

    def test_02_direct_recursion_fibonacci(self):
        """Direct branching recursion (Fibonacci) matches across all runtimes."""
        source = """module FibModule {
  fn fib(n: Int): Int {
    if n <= 0 {
      return 0
    }
    if n == 1 {
      return 1
    }
    return fib(n - 1) + fib(n - 2)
  }

  calculation Answer {
    result = fib(10)
  }
}
"""
        ast_res, ast_err = _ast_outcome(source)
        ir_res, ir_err = _ir_outcome(source)
        rust_res, rust_err = _rust_outcome(source)

        self.assertIsNone(ast_err)
        self.assertIsNone(ir_err)
        self.assertIsNone(rust_err)

        expected = {"Answer": 55}
        self.assertEqual(ast_res, expected)
        self.assertEqual(ir_res, expected)
        self.assertEqual(rust_res, expected)

    def test_03_mutual_recursion_even_odd(self):
        """Mutual recursion between two functions matches across all runtimes."""
        source = """module MutualRecursionModule {
  fn is_even(n: Int): Bool {
    if n == 0 {
      return true
    }
    return is_odd(n - 1)
  }

  fn is_odd(n: Int): Bool {
    if n == 0 {
      return false
    }
    return is_even(n - 1)
  }

  calculation Answer {
    let e10 = is_even(10)
    let o10 = is_odd(10)
    let e7 = is_even(7)
    let o7 = is_odd(7)
    result = e10 && !o10 && !e7 && o7
  }
}
"""
        ast_res, ast_err = _ast_outcome(source)
        ir_res, ir_err = _ir_outcome(source)
        rust_res, rust_err = _rust_outcome(source)

        self.assertIsNone(ast_err)
        self.assertIsNone(ir_err)
        self.assertIsNone(rust_err)

        expected = {"Answer": True}
        self.assertEqual(ast_res, expected)
        self.assertEqual(ir_res, expected)
        self.assertEqual(rust_res, expected)

    def test_04_max_call_depth_exceeded_default(self):
        """Infinite recursion triggers RT-CALL-003 at default max_call_depth=128."""
        source = """module InfiniteRecursionModule {
  fn loop_rec(x: Int): Int {
    return loop_rec(x + 1)
  }

  calculation Answer {
    result = loop_rec(0)
  }
}
"""
        ast_res, ast_err = _ast_outcome(source)
        ir_res, ir_err = _ir_outcome(source)
        rust_res, rust_err = _rust_outcome(source)

        self.assertEqual(ast_err, "RT-CALL-003")
        self.assertEqual(ir_err, "RT-CALL-003")
        self.assertEqual(rust_err, "RT-CALL-003")

    def test_05_max_call_depth_exceeded_custom_limit(self):
        """Custom max_call_depth correctly limits recursion depth."""
        source = """module ShallowRecursionModule {
  fn count_down(x: Int): Int {
    if x <= 0 {
      return 0
    }
    return 1 + count_down(x - 1)
  }

  calculation Answer {
    result = count_down(15)
  }
}
"""
        # Depth 15 exceeds limit of 10
        ast_res, ast_err = _ast_outcome(source, max_call_depth=10)
        ir_res, ir_err = _ir_outcome(source, max_call_depth=10)
        rust_res, rust_err = _rust_outcome(source, limits={"max_call_depth": 10})

        self.assertEqual(ast_err, "RT-CALL-003")
        self.assertEqual(ir_err, "RT-CALL-003")
        self.assertEqual(rust_err, "RT-CALL-003")

        # Depth 15 succeeds with limit of 20
        ast_res2, ast_err2 = _ast_outcome(source, max_call_depth=20)
        ir_res2, ir_err2 = _ir_outcome(source, max_call_depth=20)
        rust_res2, rust_err2 = _rust_outcome(source, limits={"max_call_depth": 20})

        self.assertIsNone(ast_err2)
        self.assertIsNone(ir_err2)
        self.assertIsNone(rust_err2)
        self.assertEqual(ast_res2, {"Answer": 15})
        self.assertEqual(ir_res2, {"Answer": 15})
        self.assertEqual(rust_res2, {"Answer": 15})

    def test_06_tensor_accumulation_across_recursion_frames(self):
        """Tensors created and accumulated across recursive frames remain live and valid."""
        source = """module TensorRecursionModule {
  fn recursive_tensor_sum(n: Int, base: Tensor): Tensor {
    if n <= 0 {
      return base
    }
    let next_val = tensor.add(base, 1.0)
    let recurse_res = recursive_tensor_sum(n - 1, next_val)
    return tensor.add(base, recurse_res)
  }

  calculation Answer {
    let initial = tensor.create([1.0, 2.0], "f64")
    let final_tensor = recursive_tensor_sum(4, initial)
    result = tensor.to_array(final_tensor)
  }
}
"""
        ast_res, ast_err = _ast_outcome(source)
        ir_res, ir_err = _ir_outcome(source)
        rust_res, rust_err = _rust_outcome(source)

        self.assertIsNone(ast_err)
        self.assertIsNone(ir_err)
        self.assertIsNone(rust_err)

        self.assertEqual(ast_res, ir_res)
        self.assertEqual(ir_res, rust_res)
        self.assertIsNotNone(rust_res)

    def test_07_tensor_caller_frame_root_protection_during_recursion(self):
        """Caller frame holding active Tensors is protected during recursive callee iterations."""
        source = """module CallerRootRecursionModule {
  fn recursive_helper(n: Int): Int {
    if n <= 0 {
      return 0
    }
    let temp_tensor = tensor.ones([10, 10], "f64")
    let s = tensor.scalar(tensor.sum(temp_tensor))
    return int(s) + recursive_helper(n - 1)
  }

  calculation Answer {
    let important_tensor = tensor.create([[10.0, 20.0], [30.0, 40.0]], "f64")
    let recursive_sum = recursive_helper(10)
    let combined = tensor.add(important_tensor, float(recursive_sum))
    result = tensor.to_array(combined)
  }
}
"""
        ast_res, ast_err = _ast_outcome(source)
        ir_res, ir_err = _ir_outcome(source)
        rust_res, rust_err = _rust_outcome(source)

        self.assertIsNone(ast_err)
        self.assertIsNone(ir_err)
        self.assertIsNone(rust_err)

        self.assertEqual(ast_res, ir_res)
        self.assertEqual(ir_res, rust_res)

    def test_08_recursion_error_unwind_cleans_resources(self):
        """When an error happens deep in recursion, stack unwinding succeeds without crash."""
        source = """module RecursionErrorModule {
  fn recurse_and_fail(n: Int): Float {
    if n <= 0 {
      let bad = 10 / 0
      return bad
    }
    let t = tensor.ones([5, 5], "f64")
    return recurse_and_fail(n - 1)
  }

  calculation Answer {
    result = recurse_and_fail(8)
  }
}
"""
        ast_res, ast_err = _ast_outcome(source)
        ir_res, ir_err = _ir_outcome(source)
        rust_res, rust_err = _rust_outcome(source)

        self.assertEqual(ast_err, "RT-ARITH-001")
        self.assertEqual(ir_err, "RT-ARITH-001")
        self.assertEqual(rust_err, "RT-ARITH-001")

    def test_09_ruo_resource_access_across_recursion_frames(self):
        """RUO object queries and transactions across recursive frames maintain resource integrity."""
        ruo_fixture_dir = Path(__file__).resolve().parents[1] / "artifacts/reasonunit_language/ruo_n2/fixtures"
        if not ruo_fixture_dir.exists():
            return
        source = """model RuoRecursionModel {
  reason_object object from "objects/complete.ruo" mode strict;

  fn recursive_ruo_query(n: Int): StableId {
    if n <= 0 {
      return ruo.object_id(object)
    }
    let dummy = ruo.resolve(object, "ruo:unit:root")
    return recursive_ruo_query(n - 1)
  }

  calculation Answer {
    result = recursive_ruo_query(5)
  }
}
"""
        program = parse(source)
        ir = lower_program(program)
        ir_res = interpret_program(ir, resource_root=ruo_fixture_dir, filesystem_read=True)
        rust_run = run_ir(ir, binary=_BINARY, cwd=ruo_fixture_dir, filesystem_read=True)

        self.assertTrue(rust_run.ok)
        self.assertEqual(dict(ir_res.calculation_results), rust_run.calculation_results)
        self.assertEqual(rust_run.calculation_results.get("Answer"), "ruo:object:universal-fixture")


if __name__ == "__main__":
    unittest.main()
