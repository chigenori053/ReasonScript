"""Phase 6 ("Rust主実行器"): `scripts/reason_cli.py`'s Rust-first dispatch.

Covers the "Rust default, Python fallback" architecture added to
`_run_result`/`_try_rust_execution`: the Rust computation runtime is
tried first for programs it can fully handle, and execution transparently
falls back to the Python AST evaluator for anything it can't (an
unsupported Tensor function, or `tensor.load`/`save` without filesystem
capabilities granted) -- with identical `calculations` either way.

Tests that require the compiled Rust binary skip (not fail) if it hasn't
been built, matching the other `computation_ir_tests` parity suites.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from frontend.computation_ir.rust_bridge import find_binary
from frontend.language_surface import parse
from scripts.reason_cli import _run_result, _try_rust_execution, _uses_tensor_io

_BINARY = find_binary()


def _write(directory: Path, name: str, source: str) -> Path:
    path = directory / name
    path.write_text(source, encoding="utf-8")
    return path


@unittest.skipUnless(_BINARY is not None, "reason-computation-runtime binary not built")
class RustFirstDispatchTests(unittest.TestCase):
    def test_fully_supported_program_uses_rust(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _write(
                Path(directory),
                "matmul.rsn",
                """
                module M {
                    calculation Answer {
                        let a = tensor.create([[1.0, 2.0], [3.0, 4.0]], "f64")
                        let b = tensor.create([[5.0, 6.0], [7.0, 8.0]], "f64")
                        result = tensor.to_array(tensor.matmul(a, b))
                    }
                }
                """,
            )
            result = _run_result(source, "normal", include_trace=False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["execution_mode"], "integrated-rust")
        self.assertEqual(result["runtime_output"], [[[19.0, 22.0], [43.0, 50.0]]])

    def test_unsupported_tensor_function_falls_back_to_python(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _write(
                Path(directory),
                "softmax.rsn",
                """
                module M {
                    calculation Answer {
                        let a = tensor.create([1.0, 2.0, 3.0], "f64")
                        result = tensor.to_array(tensor.softmax(a))
                    }
                }
                """,
            )
            result = _run_result(source, "normal", include_trace=False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["execution_mode"], "integrated")

    def test_include_trace_always_uses_python(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _write(
                Path(directory),
                "trace.rsn",
                """
                module M {
                    calculation Answer {
                        let a = tensor.create([1.0, 2.0], "f64")
                        result = tensor.to_array(a)
                    }
                }
                """,
            )
            result = _run_result(source, "normal", include_trace=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["execution_mode"], "integrated")
        self.assertIn("trace", result)

    def test_tensor_io_without_capability_falls_back_to_python(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _write(
                Path(directory),
                "io.rsn",
                """
                module M {
                    calculation Answer {
                        let a = tensor.create([1.0, 2.0], "f64")
                        let receipt = tensor.save(a, "out.rstensor", true)
                        result = receipt
                    }
                }
                """,
            )
            program = parse(source.read_text(encoding="utf-8"))
            # No filesystem_read/write capability granted -> Rust must
            # not be attempted (it has no equivalent capability gate, so
            # it would silently perform the write Python's TIO-001 check
            # is supposed to block).
            self.assertIsNone(_try_rust_execution(program, Path(directory), False, False))

    def test_tensor_io_with_capability_uses_rust(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _write(
                Path(directory),
                "io_ok.rsn",
                """
                module M {
                    calculation Answer {
                        let a = tensor.create([1.0, 2.0], "f64")
                        let receipt = tensor.save(a, "out.rstensor", true)
                        result = receipt
                    }
                }
                """,
            )
            program = parse(source.read_text(encoding="utf-8"))
            result = _try_rust_execution(program, Path(directory), True, True)
            self.assertIsNotNone(result)
            self.assertTrue((Path(directory) / "out.rstensor").is_file())

    def test_uses_tensor_io_detects_load_and_save(self):
        from frontend.computation_ir import lower_program

        loads = parse(
            """
            module M {
                calculation Answer {
                    result = tensor.load("x.rstensor")
                }
            }
            """
        )
        no_io = parse(
            """
            module M {
                calculation Answer {
                    result = tensor.to_array(tensor.create([1.0], "f64"))
                }
            }
            """
        )
        self.assertTrue(_uses_tensor_io(lower_program(loads)))
        self.assertFalse(_uses_tensor_io(lower_program(no_io)))

    def test_shadow_mode_agrees_silently_and_does_not_change_result(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _write(
                Path(directory),
                "shadow.rsn",
                """
                module M {
                    calculation Answer {
                        let a = tensor.create([2.0, 3.0], "f64")
                        let b = tensor.create([4.0, 5.0], "f64")
                        result = tensor.to_array(tensor.add(a, b))
                    }
                }
                """,
            )
            with mock.patch.dict(os.environ, {"REASONSCRIPT_SHADOW_MODE": "1"}), mock.patch(
                "builtins.print"
            ) as mock_print:
                result = _run_result(source, "normal", include_trace=False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["execution_mode"], "integrated-rust")
        self.assertEqual(result["runtime_output"], [[6.0, 8.0]])
        # Rust and Python agree on this program, so shadow mode must stay
        # silent -- no mismatch warning printed to stderr.
        mock_print.assert_not_called()


if __name__ == "__main__":
    unittest.main()
