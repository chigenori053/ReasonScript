"""Phase 9's `NumericMode::NativeFast` (real f32 rounding + `rayon`
parallel op paths), selected via `REASONSCRIPT_NUMERIC_MODE=native-fast`
on the Rust CLI. Scoped down (per an explicit scope decision) from the
plan's full "true f32/parallel CPU/BLAS/GPU/cost model" to just true f32
rounding and parallel CPU: no GPU is available in this environment, and
no system BLAS library was found either -- see AGENTS.md.

The default mode (`CompatReference`, no env var set) is untouched:
every other `computation_ir_tests` parity suite already exercises it
without ever setting this variable, so this file only needs to cover
what's new -- native-fast's own numeric behavior and determinism, plus
one explicit regression proving the default is unaffected.
"""

from __future__ import annotations

import json
import os
import subprocess
import unittest

from frontend.computation_ir import lower_program
from frontend.computation_ir.rust_bridge import find_binary
from frontend.language_surface import parse

_BINARY = find_binary()


def _lower(source: str) -> dict:
    return lower_program(parse(source))


def _run(payload: str, mode: str | None) -> dict:
    env = dict(os.environ)
    if mode is not None:
        env["REASONSCRIPT_NUMERIC_MODE"] = mode
    else:
        env.pop("REASONSCRIPT_NUMERIC_MODE", None)
    result = subprocess.run(
        [str(_BINARY)], input=payload, capture_output=True, text=True, env=env, check=True
    )
    return json.loads(result.stdout)


@unittest.skipUnless(_BINARY is not None, "reason-computation-runtime binary not built")
class NativeFastModeTests(unittest.TestCase):
    def test_default_mode_is_compat_reference_unset_env_var(self):
        # No `REASONSCRIPT_NUMERIC_MODE` set at all -- the same
        # condition every other computation_ir_tests parity suite runs
        # under -- must behave identically to explicitly requesting
        # compat-reference.
        payload = json.dumps(
            _lower(
                """
                module M {
                    calculation Answer {
                        let a = tensor.create([1.0, 2.0], "f64")
                        let b = tensor.create([3.0, 4.0], "f64")
                        result = tensor.to_array(tensor.add(a, b))
                    }
                }
                """
            )
        )
        unset = _run(payload, None)
        explicit_compat = _run(payload, "compat-reference")
        self.assertEqual(unset, explicit_compat)
        self.assertEqual(unset["calculation_results"]["Answer"], [4.0, 6.0])

    def test_unrecognized_mode_value_falls_back_to_compat_reference(self):
        payload = json.dumps(
            _lower(
                """
                module M {
                    calculation Answer {
                        result = tensor.to_array(tensor.create([1.0], "f64"))
                    }
                }
                """
            )
        )
        default = _run(payload, None)
        garbage = _run(payload, "not-a-real-mode")
        self.assertEqual(default, garbage)

    def test_native_fast_rounds_f32_values_that_compat_reference_keeps_full_precision(self):
        # 1.0000001192092896 is exactly representable in f64 but is
        # *not* an exact f32 value; f32 rounds it down to 1.0. This is
        # the direct, minimal proof that NativeFast performs real f32
        # rounding mid-computation and CompatReference genuinely does
        # not (matching the Python reference, which never rounds an f32
        # tensor's data to f32 precision except at .rstensor/to_array
        # I/O boundaries).
        payload = json.dumps(
            _lower(
                """
                module M {
                    calculation Answer {
                        let a = tensor.create([1.0000001192092896], "f32")
                        let b = tensor.create([1.0], "f32")
                        result = tensor.to_array(tensor.add(a, b))
                    }
                }
                """
            )
        )
        compat = _run(payload, "compat-reference")
        fast = _run(payload, "native-fast")
        self.assertTrue(compat["ok"])
        self.assertTrue(fast["ok"])
        self.assertEqual(compat["calculation_results"]["Answer"], [2.0000001192092896])
        self.assertEqual(fast["calculation_results"]["Answer"], [2.0])

    def test_native_fast_f64_matmul_matches_compat_reference_exactly(self):
        # f64 has no precision-loss story in NativeFast (`round_for_mode`
        # only touches f32) -- for an f64 workload, the only difference
        # between modes is *parallel* execution, and matmul's
        # row-parallel decomposition is deterministic and
        # order-preserving (see ops.rs's `matmul_parallel` doc comment),
        # so results must still be bit-exact.
        payload = json.dumps(
            _lower(
                """
                module M {
                    calculation Answer {
                        let a = tensor.create([[1.0, 2.0], [3.0, 4.0]], "f64")
                        let b = tensor.create([[5.0, 6.0], [7.0, 8.0]], "f64")
                        result = tensor.to_array(tensor.matmul(a, b))
                    }
                }
                """
            )
        )
        compat = _run(payload, "compat-reference")
        fast = _run(payload, "native-fast")
        self.assertEqual(compat["calculation_results"], fast["calculation_results"])

    def test_native_fast_reduce_over_multiple_groups_matches_compat_reference(self):
        payload = json.dumps(
            _lower(
                """
                module M {
                    calculation Answer {
                        let a = tensor.create([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], "f64")
                        result = tensor.to_array(tensor.sum(a, [1], false))
                    }
                }
                """
            )
        )
        compat = _run(payload, "compat-reference")
        fast = _run(payload, "native-fast")
        self.assertEqual(compat["calculation_results"], fast["calculation_results"])
        self.assertEqual(compat["calculation_results"]["Answer"], [6.0, 15.0])

    def test_native_fast_is_deterministic_across_repeated_runs(self):
        # A larger, less-trivial workload (multiple ops chained), run
        # three separate process invocations -- proves the parallel
        # paths are reproducible on this machine, not just "usually the
        # same".
        payload = json.dumps(
            _lower(
                """
                module M {
                    calculation Answer {
                        let a = tensor.random_uniform([40, 40], 0.0, 1.0, 7)
                        let b = tensor.random_uniform([40, 40], 0.0, 1.0, 11)
                        let c = tensor.matmul(a, b)
                        let d = tensor.add(c, c)
                        let e = tensor.sum(d, [1], false)
                        result = tensor.to_array(e)
                    }
                }
                """
            )
        )
        first = _run(payload, "native-fast")
        second = _run(payload, "native-fast")
        third = _run(payload, "native-fast")
        self.assertEqual(first, second)
        self.assertEqual(second, third)

    def test_native_fast_matmul_is_numerically_close_to_compat_reference(self):
        # `tensor.random_uniform`'s default dtype is f32, so this
        # exercises the real f32-rounding path (not just parallel f64
        # execution): a small (~1e-7 relative) difference from
        # compat-reference is *expected* here -- each intermediate value
        # genuinely gets rounded to f32 precision in native-fast mode
        # and does not in compat-reference -- so the tolerance below is
        # deliberately loose, unlike the f64 tests above which require
        # exact equality.
        payload = json.dumps(
            _lower(
                """
                module M {
                    calculation Answer {
                        let a = tensor.random_uniform([16, 16], -1.0, 1.0, 1)
                        let b = tensor.random_uniform([16, 16], -1.0, 1.0, 2)
                        result = tensor.to_array(tensor.matmul(a, b))
                    }
                }
                """
            )
        )
        compat = _run(payload, "compat-reference")["calculation_results"]["Answer"]
        fast = _run(payload, "native-fast")["calculation_results"]["Answer"]
        flat_compat = [value for row in compat for value in row]
        flat_fast = [value for row in fast for value in row]
        self.assertEqual(len(flat_compat), len(flat_fast))
        for left, right in zip(flat_compat, flat_fast):
            self.assertAlmostEqual(left, right, delta=1e-5)


if __name__ == "__main__":
    unittest.main()
