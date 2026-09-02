"""Phase 4 completion gate for the formerly Python-only Tensor operations."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from frontend.computation_ir import lower_program
from frontend.computation_ir.rust_bridge import run_ir
from frontend.language_surface import parse

from computation_ir_tests.test_computation_ir_tensor_parity import (
    _BINARY,
    _python_outcome,
    _rust_outcome,
)


@unittest.skipUnless(_BINARY is not None, "reason-runtime-host binary not built")
class TensorCompleteParityTests(unittest.TestCase):
    def outcomes(self, source: str):
        python, python_error = _python_outcome(source)
        rust, rust_error = _rust_outcome(source)
        self.assertEqual(python_error, rust_error, source)
        self.assertIsNone(python_error, source)
        return python["Answer"], rust["Answer"]

    def assert_nested_close(self, left, right):
        if isinstance(left, list):
            self.assertEqual(len(left), len(right))
            for left_item, right_item in zip(left, right):
                self.assert_nested_close(left_item, right_item)
        elif isinstance(left, float):
            self.assertAlmostEqual(left, right, places=11)
        else:
            self.assertEqual(left, right)

    def test_indexing_and_shape_operations(self):
        source = """module M {
  calculation Answer {
    let a = tensor.create([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], "f64")
    let sliced = tensor.to_array(tensor.slice(a, [0, 0], [2, 3], [0, 1], [1, 2]))
    let narrowed = tensor.to_array(tensor.narrow(a, 1, 1, 2))
    let indexes = tensor.create([2, 0], "i64")
    let gathered = tensor.to_array(tensor.gather(a, indexes, 1))
    let joined = tensor.to_array(tensor.concat([a, a], 0))
    let stacked = tensor.to_array(tensor.stack([a, a], 1))
    result = [sliced, narrowed, gathered, joined, stacked]
  }
}
"""
        python, rust = self.outcomes(source)
        self.assertEqual(python, rust)

    def test_inference_operations(self):
        source = """module M {
  calculation Answer {
    let a = tensor.create([[-1.0, 0.0, 2.0], [3.0, 1.0, -2.0]], "f64")
    let relu = tensor.to_array(tensor.relu(a))
    let softmax = tensor.to_array(tensor.softmax(a, 1))
    let weight = tensor.create([[1.0, 2.0], [0.5, -1.0], [2.0, 0.0]], "f64")
    let bias = tensor.create([0.25, -0.5], "f64")
    let linear = tensor.to_array(tensor.linear(a, weight, bias))
    result = [relu, softmax, linear]
  }
}
"""
        python, rust = self.outcomes(source)
        self.assert_nested_close(python, rust)

    def test_conv_and_pool_operations(self):
        source = """module M {
  calculation Answer {
    let input = tensor.create([[[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]]], "f64")
    let weight = tensor.create([[[[1.0, 0.0], [0.0, -1.0]]]], "f64")
    let bias = tensor.create([0.5], "f64")
    let conv = tensor.to_array(tensor.conv2d(input, weight, bias, [1, 1], [0, 0], [1, 1], 1))
    let maxed = tensor.to_array(tensor.max_pool2d(input, [2, 2], [1, 1], [0, 0]))
    let averaged = tensor.to_array(tensor.avg_pool2d(input, [2, 2], [1, 1], [1, 1], true))
    result = [conv, maxed, averaged]
  }
}
"""
        python, rust = self.outcomes(source)
        self.assert_nested_close(python, rust)

    def test_new_vjps(self):
        sources = [
            "let y = tensor.concat([p, p], 0)",
            "let y = tensor.stack([p, p], 0)",
            "let y = tensor.slice(p, [0], [2])",
            "let y = tensor.narrow(p, 0, 0, 2)",
            'let indexes = tensor.create([2, 0], "i64")\n    let y = tensor.gather(p, indexes, 0)',
            "let y = tensor.softmax(p, 0)",
        ]
        for operation in sources:
            with self.subTest(operation=operation):
                source = f"""module M {{
  calculation Answer {{
    let base = tensor.create([1.0, 2.0, 3.0], "f64")
    let p = tensor.parameter(base)
    {operation}
    let loss = tensor.sum(y)
    let gradients = tensor.grad(loss, [p])
    result = tensor.to_array(gradients[0])
  }}
}}
"""
                python, rust = self.outcomes(source)
                self.assert_nested_close(python, rust)

    def test_linear_conv_and_pool_vjps(self):
        programs = [
            """let base = tensor.create([[1.0, 2.0]], "f64")
    let p = tensor.parameter(base)
    let weight = tensor.parameter(tensor.create([[2.0], [3.0]], "f64"))
    let bias = tensor.parameter(tensor.create([0.5], "f64"))
    let loss = tensor.sum(tensor.linear(p, weight, bias))""",
            """let base = tensor.create([[[[1.0, 2.0], [3.0, 4.0]]]], "f64")
    let p = tensor.parameter(base)
    let weight = tensor.parameter(tensor.create([[[[2.0]]]], "f64"))
    let loss = tensor.sum(tensor.conv2d(p, weight))""",
            """let base = tensor.create([[[[1.0, 2.0], [3.0, 4.0]]]], "f64")
    let p = tensor.parameter(base)
    let loss = tensor.sum(tensor.max_pool2d(p, [2, 2]))""",
            """let base = tensor.create([[[[1.0, 2.0], [3.0, 4.0]]]], "f64")
    let p = tensor.parameter(base)
    let loss = tensor.sum(tensor.avg_pool2d(p, [2, 2]))""",
        ]
        for setup in programs:
            with self.subTest(setup=setup):
                source = f"""module M {{
  calculation Answer {{
    {setup}
    let gradients = tensor.grad(loss, [p])
    result = tensor.to_array(gradients[0])
  }}
}}
"""
                python, rust = self.outcomes(source)
                self.assert_nested_close(python, rust)

    def test_rust_tensor_trace_and_metadata(self):
        source = """module M {
  calculation Answer {
    let a = tensor.create([1.0, 2.0], "f64")
    let b = tensor.relu(a)
    let values = tensor.to_array(b)
    result = b
  }
}
"""
        outcome = run_ir(lower_program(parse(source)), binary=_BINARY, trace_enabled=True)
        self.assertTrue(outcome.ok)
        self.assertEqual(
            [entry["function_id"] for entry in outcome.metadata["tensor_trace"]],
            ["tensor.create", "tensor.relu", "tensor.to_array"],
        )
        self.assertEqual(outcome.metadata["tensor_metadata"][0]["backend"], "rust")

    def test_rust_tensor_resource_limits(self):
        source = """module M {
  calculation Answer {
    result = tensor.to_array(tensor.ones([3], "f64"))
  }
}
"""
        ir = lower_program(parse(source))
        elements = run_ir(ir, binary=_BINARY, limits={"max_elements": 2})
        self.assertFalse(elements.ok)
        self.assertEqual(elements.error_code, "TSF-003")
        inline = run_ir(ir, binary=_BINARY, limits={"inline_elements": 2})
        self.assertFalse(inline.ok)
        self.assertEqual(inline.error_code, "TSF-020")

        liveness_source = """module M {
  calculation Answer {
    let index = 0
    let value = tensor.ones([1], "f64")
    while index < 1100 {
      value = tensor.add(value, 1.0)
      index = index + 1
    }
    result = tensor.to_array(value)
  }
}
"""
        liveness = run_ir(lower_program(parse(liveness_source)), binary=_BINARY)
        self.assertTrue(liveness.ok, liveness.error_message)

    def test_rust_tensor_io_capabilities_and_sandbox(self):
        load_source = """module M {
  calculation Answer {
    result = tensor.to_array(tensor.load("value.rstensor"))
  }
}
"""
        unsafe_source = """module M {
  calculation Answer {
    let value = tensor.ones([1], "f64")
    result = tensor.save(value, "../value.rstensor")
  }
}
"""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            load = run_ir(
                lower_program(parse(load_source)),
                binary=_BINARY,
                cwd=root,
                filesystem_read=False,
            )
            self.assertFalse(load.ok)
            self.assertEqual(load.error_code, "TIO-001")
            unsafe = run_ir(
                lower_program(parse(unsafe_source)),
                binary=_BINARY,
                cwd=root,
            )
            self.assertFalse(unsafe.ok)
            self.assertEqual(unsafe.error_code, "TIO-002")


if __name__ == "__main__":
    unittest.main()
