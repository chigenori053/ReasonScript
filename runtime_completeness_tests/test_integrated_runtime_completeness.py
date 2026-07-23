import json
import tempfile
import unittest
from pathlib import Path

from frontend.integrated_computation_runtime import (
    IntegratedRuntimeError,
    execute_program,
)
from frontend.language_surface import parse
from scripts.reason_cli import _run_result, main


class IntegratedRuntimeCompletenessTests(unittest.TestCase):
    def test_scalar_calculation_uses_integrated_runtime_without_trigger_construct(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "scalar.rsn"
            source.write_text(
                """
                module Scalar {
                    calculation Run {
                        let x = 0.25
                        result = x * 2.0
                    }
                }
                """,
                encoding="utf-8",
            )
            result = _run_result(source, "normal", include_trace=False)
        self.assertTrue(result["ok"])
        self.assertEqual(result["execution_mode"], "integrated")
        self.assertEqual(result["runtime_result"]["result"], 0.5)

    def test_index_function_struct_and_array_append_execute_together(self):
        program = parse(
            """
            module Runtime {
                struct Point {
                    x: float
                    y: float
                }
                fn twice(value: float) -> float {
                    return value * 2.0
                }
                calculation Run {
                    let point = Point {
                        x: 1.5
                        y: 2.0
                    }
                    point.x = twice(point.x)
                    let values = [point.x, point.y]
                    values[1] = values[0] + values[1]
                    let frames = [[0.0, 0.0]]
                    frames = array.append(frames, values)
                    result = frames
                }
            }
            """
        )
        result = execute_program(program).to_dict()
        self.assertEqual(result["result"], [[0.0, 0.0], [3.0, 5.0]])

    def test_nine_value_state_is_accumulated_as_independent_frames(self):
        program = parse(
            """
            module Frames {
                calculation Run {
                    let state = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
                    let frames = [[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]]
                    let step = 0
                    while step < 3 {
                        state[0] = state[0] + 0.5
                        frames = array.append(frames, state)
                        step = step + 1
                    }
                    result = frames
                }
            }
            """
        )
        first = execute_program(program).to_dict()
        second = execute_program(program).to_dict()
        self.assertEqual(first, second)
        self.assertEqual(len(first["result"]), 4)
        self.assertEqual([frame[0] for frame in first["result"]], [0.0, 0.5, 1.0, 1.5])
        self.assertTrue(all(len(frame) == 9 for frame in first["result"]))

    def test_result_output_writes_only_runtime_value(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "frames.rsn"
            output = root / "frames.json"
            source.write_text(
                """
                module Output {
                    calculation Run {
                        result = [[1.0, 2.0], [3.0, 4.0]]
                    }
                }
                """,
                encoding="utf-8",
            )
            status = main(
                [
                    "run",
                    str(source),
                    "--result-output",
                    str(output),
                    "--json",
                ]
            )
            self.assertEqual(status, 0)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                [[1.0, 2.0], [3.0, 4.0]],
            )

    def test_index_failures_have_stable_runtime_codes(self):
        program = parse(
            """
            module Invalid {
                calculation Run {
                    let values = [1]
                    result = values[2]
                }
            }
            """
        )
        with self.assertRaises(IntegratedRuntimeError) as raised:
            execute_program(program)
        self.assertEqual(raised.exception.code, "RT-INDEX-002")


if __name__ == "__main__":
    unittest.main()
