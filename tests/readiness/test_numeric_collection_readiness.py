"""Native CLI probes for the general-purpose readiness report."""

import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name("numeric_collection.rsn")


def run(source: Path):
    process = subprocess.run(
        [str(ROOT / "reason"), "run", str(source), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return process.returncode, json.loads(process.stdout)


def test_native_scenarios_are_deterministic():
    runs = [run(SOURCE) for _ in range(3)]
    assert all(code == 0 and output["runtime_result"]["status"] == "success" for code, output in runs)
    results = [output["runtime_result"]["calculations"] for _, output in runs]
    assert results[0] == results[1] == results[2]
    result = results[0]
    assert result["RealArithmetic"] is False  # IEEE-style exact comparison
    assert len(result["FloatSequence"]) == 200
    assert result["FloatSequence"][0] == -10.0
    assert result["FloatSequence"][-1] == 9.900000000000002
    assert result["MapFilterReduce"] == 41
    assert result["Mapped"] == [1, 4, 9, 16]
    assert result["Filtered"] == [4, 5]
    assert len(result["PointCollection"]) == 100
    assert result["PointCollection"][37]["fields"] == {"x": 37.0, "y": 1369.0}
    dataset = result["RangeAndDataset"]["fields"]
    assert len(dataset["x"]) == len(dataset["y"]) == 100
    assert dataset["y"][37] == 85.5625
    assert result["ThousandIterations"] == 499500
    metrics = runs[0][1]["runtime_result"]["runtime_metrics"]
    assert metrics["loop_iterations"] >= 1000
    assert metrics["builder_appends"] == 506
    assert metrics["peak_live_bytes"] > 0


def test_cli_serialization_is_byte_stable():
    outputs = [
        subprocess.run(
            [str(ROOT / "reason"), "run", str(SOURCE), "--json"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        for _ in range(3)
    ]
    marker = b'  "runtime_result": '
    def runtime_bytes(output):
        tail = output[output.index(marker) + len(marker):]
        _, end = json.JSONDecoder().raw_decode(tail.decode())
        return tail[:end]

    assert runtime_bytes(outputs[0]) == runtime_bytes(outputs[1]) == runtime_bytes(outputs[2])


@pytest.mark.parametrize("size", [10, 73])
def test_generated_size_is_not_fixture_specific(tmp_path, size):
    source = SOURCE.read_text().replace("while i < 100", f"while i < {size}")
    generated = tmp_path / "different_size.rsn"
    generated.write_text(source)
    code, output = run(generated)
    assert code == 0, output.get("diagnostics")
    result = output["runtime_result"]["calculations"]
    assert len(result["PointCollection"]) == size
    assert len(result["RangeAndDataset"]["fields"]["x"]) == size
    assert result["PointCollection"][-1]["fields"]["y"] == float((size - 1) ** 2)


def test_out_of_bounds_is_an_error(tmp_path):
    source = tmp_path / "bounds.rsn"
    source.write_text("module Bounds { calculation Test -> int { let xs = [1, 2, 3]\n result = xs[10] } }\n")
    code, output = run(source)
    assert code != 0
    assert output["diagnostics"]


def test_infinite_loop_is_bounded(tmp_path):
    source = tmp_path / "loop.rsn"
    source.write_text("module Loop {\n calculation Test -> int {\n let i = 0\n while true {\n i = i + 1\n }\n result = i\n }\n}\n")
    code, output = run(source)
    assert code != 0
    assert output["diagnostics"][0]["code"] == "RT-LOOP-001"


@pytest.mark.parametrize(
    ("expression", "code"),
    [
        ("2 + 0.5 * 4", "IR-EXEC-008"),
        ("range(0, 10, 1)", "RT-CALL-001"),
        ("sin(0.5)", "RT-CALL-001"),
        ("1.0 / 0.0", "RT-ARITH-001"),
    ],
)
def test_current_blockers_are_classified(tmp_path, expression, code):
    source = tmp_path / "blocker.rsn"
    source.write_text(f"module Probe {{\n calculation Test {{\n result = {expression}\n }}\n}}\n")
    status, output = run(source)
    assert status != 0
    assert output["diagnostics"][0]["code"] == code


def test_string_conversion_and_escaping(tmp_path):
    source = tmp_path / "strings.rsn"
    source.write_text(
        'module Strings {\n'
        ' calculation Format -> string {\n result = string.concat("value = ", string.from_float(-1.25))\n }\n'
        ' calculation Escape -> string {\n result = "A\\nB"\n }\n'
        ' calculation NegativeZero -> string {\n result = string.from_float(-0.0)\n }\n'
        '}\n'
    )
    status, output = run(source)
    assert status == 0, output.get("diagnostics")
    assert output["runtime_result"]["calculations"] == {
        "Format": "value = -1.25",
        "Escape": "A\nB",
        "NegativeZero": "-0.0",
    }
