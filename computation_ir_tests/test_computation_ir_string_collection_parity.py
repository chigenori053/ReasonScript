from __future__ import annotations

import unittest
from frontend.language_surface import parse, validate
from frontend.language_surface.validation import SurfaceValidationError
from frontend.language_surface.parser import SurfaceSyntaxError
from frontend.computation_ir import lower_program, interpret_program, validate_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import execute_program

_BINARY = find_binary()

class StringCollectionParityTests(unittest.TestCase):
    def assert_parity(self, source: str, expected: object) -> None:
        program = parse(source)
        validate(program)
        ir = lower_program(program)
        self.assertEqual(validate_program(ir), [])
        ast_results = execute_program(program).to_dict()["calculations"]
        python_results = interpret_program(ir).to_dict()["calculations"]
        self.assertEqual(ast_results, python_results)
        self.assertEqual(python_results["Answer"], expected)
        if _BINARY is not None:
            rust = run_ir(ir, binary=_BINARY)
            self.assertTrue(rust.ok, rust.error_message)
            self.assertEqual(rust.calculation_results, python_results)

    def test_string_concat_parity(self):
        source = """
        module M {
          calculation Answer {
            let a: string = "Hello, "
            let b: string = "world!"
            let res: string = string.concat(a, b)
            result = res
          }
        }
        """
        self.assert_parity(source, "Hello, world!")

    def test_string_join_parity(self):
        source = """
        module M {
          calculation Answer {
            let sep: string = " - "
            let items: [string] = ["alpha", "beta", "gamma"]
            let res: string = string.join(sep, items)
            result = res
          }
        }
        """
        self.assert_parity(source, "alpha - beta - gamma")

    def test_string_length_parity(self):
        source = """
        module M {
          calculation Answer {
            let s1: string = "ReasonScript"
            let s2: string = "日本語"
            let l1: int = string.length(s1)
            let l2: int = string.length(s2)
            result = [l1, l2]
          }
        }
        """
        self.assert_parity(source, [12, 3])

    def test_string_from_int_and_float_parity(self):
        source = """
        module M {
          calculation Answer {
            let s_int: string = string.from_int(42)
            let s_flt: string = string.from_float(3.14)
            result = [s_int, s_flt]
          }
        }
        """
        self.assert_parity(source, ["42", "3.14"])

    def test_string_slice_parity(self):
        source = """
        module M {
          calculation Answer {
            let s: string = "abcdefgh"
            let part: string = string.slice(s, 2, 5)
            result = part
          }
        }
        """
        self.assert_parity(source, "cde")

    def test_array_concat_and_append_parity(self):
        source = """
        module M {
          calculation Answer {
            let arr1: [int] = [1, 2]
            let arr2: [int] = [3, 4]
            let combined: [int] = array.concat(arr1, arr2)
            let appended: [int] = array.append(combined, 5)
            result = [combined, appended]
          }
        }
        """
        self.assert_parity(source, [[1, 2, 3, 4], [1, 2, 3, 4, 5]])

    def test_string_type_error_diagnostics(self):
        source = """
        module M {
          calculation Answer {
            let res: string = string.concat("hello", 42)
            result = res
          }
        }
        """
        with self.assertRaises((SurfaceValidationError, SurfaceSyntaxError)) as ctx:
            parse(source)
        self.assertIn("STR-002", str(ctx.exception))

    def test_array_concat_type_error_diagnostics(self):
        source = """
        module M {
          calculation Answer {
            let a: [int] = [1, 2]
            let b: [string] = ["x", "y"]
            let res: [int] = array.concat(a, b)
            result = res
          }
        }
        """
        with self.assertRaises((SurfaceValidationError, SurfaceSyntaxError)) as ctx:
            parse(source)
        self.assertIn("COLL-003", str(ctx.exception))
