from __future__ import annotations

import unittest
from frontend.language_surface import parse, validate
from frontend.computation_ir import lower_program, interpret_program, validate_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import execute_program, IntegratedRuntimeError

_BINARY = find_binary()

class AssertionParityTests(unittest.TestCase):
    def assert_parity_success(self, source: str) -> None:
        program = parse(source)
        validate(program)
        ir = lower_program(program)
        self.assertEqual(validate_program(ir), [])
        ast_results = execute_program(program).to_dict()["calculations"]
        python_results = interpret_program(ir).to_dict()["calculations"]
        self.assertEqual(ast_results, python_results)
        if _BINARY is not None:
            rust = run_ir(ir, binary=_BINARY)
            self.assertTrue(rust.ok, rust.error_message)
            self.assertEqual(rust.calculation_results, python_results)

    def assert_parity_failure(self, source: str) -> None:
        program = parse(source)
        validate(program)
        ir = lower_program(program)
        self.assertEqual(validate_program(ir), [])
        
        with self.assertRaises(IntegratedRuntimeError) as ctx_ast:
            execute_program(program)
        self.assertEqual(ctx_ast.exception.code, "TEST-ASSERT-001")
        
        with self.assertRaises(IntegratedRuntimeError) as ctx_py:
            interpret_program(ir)
        self.assertEqual(ctx_py.exception.code, "TEST-ASSERT-001")
        
        if _BINARY is not None:
            rust = run_ir(ir, binary=_BINARY)
            self.assertFalse(rust.ok)
            self.assertEqual(rust.error_code, "TEST-ASSERT-001")

    def test_assert_success(self):
        source = """
        module M {
          calculation Answer {
            assert(true)
            assert_eq(10 + 5, 15)
            assert_eq("abc", "abc")
            result = 42
          }
        }
        """
        self.assert_parity_success(source)

    def test_assert_condition_failed(self):
        source = """
        module M {
          calculation Answer {
            assert(false)
            result = 42
          }
        }
        """
        self.assert_parity_failure(source)

    def test_assert_eq_failed(self):
        source = """
        module M {
          calculation Answer {
            assert_eq(10, 20)
            result = 42
          }
        }
        """
        self.assert_parity_failure(source)
