"""Phase 7 strict native dispatch (building on the Phase 6 Rust default).

Covers that production execution always selects the Rust computation host.
Unsupported programs, missing capabilities, and native runtime failures are
reported as structured diagnostics and never execute the Python reference
evaluator.

Tests that require the compiled Rust binary skip (not fail) if it hasn't
been built, matching the other `computation_ir_tests` parity suites.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from frontend.computation_ir.rust_bridge import find_binary
from scripts.reason_cli import _run_result

_BINARY = find_binary()


def _write(directory: Path, name: str, source: str) -> Path:
    path = directory / name
    path.write_text(source, encoding="utf-8")
    return path


@unittest.skipUnless(_BINARY is not None, "reason-computation-runtime binary not built")
class RustFirstDispatchTests(unittest.TestCase):
    def test_product_dispatch_has_no_python_evaluator_import(self):
        repository = Path(__file__).resolve().parents[1]
        product_dispatch = (
            repository / "scripts/reason_cli.py",
            repository / "toolchain/run_cmd.py",
            repository / "toolchain/project_validation.py",
        )
        forbidden = (
            "frontend.integrated_computation_runtime",
            "frontend.computation_ir.interpreter",
        )
        for path in product_dispatch:
            source = path.read_text(encoding="utf-8")
            for module in forbidden:
                self.assertNotIn(module, source, f"{path} imports {module}")

    def test_missing_native_host_is_a_diagnostic_not_a_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _write(
                Path(directory),
                "native_required.rsn",
                """
                module M {
                    calculation Answer {
                        result = 42
                    }
                }
                """,
            )
            with mock.patch(
                "frontend.computation_ir.rust_bridge.find_binary",
                return_value=None,
            ):
                result = _run_result(source, "normal", include_trace=False)
        self.assertFalse(result["ok"])
        self.assertEqual(result["execution_mode"], "integrated-rust")
        self.assertEqual(result["diagnostics"][-1]["code"], "RTH-HOST-001")
        self.assertEqual(
            result["artifacts"]["runtime_dispatch"]["selected"],
            "rust_computation_vm",
        )

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
        self.assertEqual(
            result["artifacts"]["runtime_dispatch"],
            {
                "attempted": "rust_computation_vm",
                "selected": "rust_computation_vm",
            },
        )

    def test_softmax_now_uses_rust(self):
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
        self.assertEqual(result["execution_mode"], "integrated-rust")
        self.assertNotIn("fallback_reason", result["artifacts"]["runtime_dispatch"])

    def test_tensor_trace_now_uses_rust(self):
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
        self.assertEqual(result["execution_mode"], "integrated-rust")
        self.assertIn("trace", result)
        self.assertNotIn("fallback_reason", result["artifacts"]["runtime_dispatch"])

    def test_phase5_vision_trace_uses_in_process_rust(self):
        fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/vision_language"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("model.json", "observation.json", "image.bin"):
                shutil.copyfile(fixture / name, root / name)
            source = _write(
                root,
                "vision.rsn",
                (fixture / "vision_pipeline.rsn").read_text(encoding="utf-8"),
            )
            result = _run_result(
                source,
                "normal",
                include_trace=True,
                allow_read=True,
                allow_write=True,
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["execution_mode"], "integrated-rust")
            self.assertEqual(
                [item["operation"] for item in result["runtime_result"]["vision_trace"]],
                ["vision_infer", "vision_build_ruo"],
            )
            self.assertTrue((root / "output/solar-observation.ruo").is_file())

    def test_phase5_complete_ruo_operation_uses_rust(self):
        fixture = (
            Path(__file__).resolve().parents[1]
            / "artifacts/reasonunit_language/ruo_n2/fixtures/objects/complete.ruo"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "objects").mkdir()
            shutil.copyfile(fixture, root / "objects/complete.ruo")
            source = _write(
                root,
                "ruo.rsn",
                '''model X {
  reason_object object from "objects/complete.ruo" mode strict;
  calculation Query {
    result = ruo.query(object, "{\\"query\\":\\"all\\"}")
  }
}''',
            )
            result = _run_result(
                source,
                "normal",
                include_trace=False,
                allow_read=True,
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["execution_mode"], "integrated-rust")
            self.assertIn("ruo:object:universal-fixture", result["runtime_output"][0]["entity_ids"])

    def test_tensor_io_without_capability_is_rejected_by_rust(self):
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
            # The Rust host owns capability enforcement; no Python evaluator
            # is invoked by the production path.
            run_result = _run_result(source, "normal", include_trace=False)
            self.assertFalse(run_result["ok"])
            self.assertEqual(run_result["execution_mode"], "integrated-rust")
            self.assertEqual(run_result["diagnostics"][-1]["code"], "TIO-001")
            self.assertEqual(
                run_result["artifacts"]["runtime_dispatch"]["selected"],
                "rust_computation_vm",
            )

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
            result = _run_result(
                source,
                "normal",
                include_trace=False,
                allow_read=True,
                allow_write=True,
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["execution_mode"], "integrated-rust")
            self.assertTrue((Path(directory) / "out.rstensor").is_file())

    def test_native_result_is_stable_without_shadow_execution(self):
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
            result = _run_result(source, "normal", include_trace=False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["execution_mode"], "integrated-rust")
        self.assertEqual(result["runtime_output"], [[6.0, 8.0]])


if __name__ == "__main__":
    unittest.main()
