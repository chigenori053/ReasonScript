"""Exercise the public native plot command and its SVG artifact."""

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples/visualization/plot.json"


def invoke(spec: Path, output: Path) -> tuple[int, dict]:
    result = subprocess.run(
        [str(ROOT / "reason"), "visualization", "plot", str(spec), "--output", str(output), "--json"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    return result.returncode, json.loads(result.stdout)


def test_native_plot_svg_is_deterministic_and_well_formed(tmp_path):
    first, second = tmp_path / "first.svg", tmp_path / "second.svg"
    for path in (first, second):
        status, report = invoke(EXAMPLE, path)
        assert status == 0 and report["ok"] and report["bytes"] == path.stat().st_size
    assert first.read_bytes() == second.read_bytes()
    root = ET.parse(first).getroot()
    ns = {"svg": "http://www.w3.org/2000/svg"}
    assert len(root.findall('.//svg:rect[@class="heatmap-cell"]', ns)) == 6
    assert len(root.findall('.//svg:polyline[@class="plot-line"]', ns)) == 1
    assert len(root.findall('.//svg:circle[@class="plot-point"]', ns)) == 3
    assert {node.text for node in root.findall('.//svg:text[@class="heatmap-label"]', ns)} == {"A", "B", "C", "low", "high"}


def test_invalid_heatmap_rejects_output(tmp_path):
    spec = tmp_path / "bad.json"
    spec.write_text(json.dumps({"schema_version": "reasonscript-plot/0.1", "heatmap": {"values": [[1, 2], [3]]}}))
    output = tmp_path / "bad.svg"
    status, report = invoke(spec, output)
    assert status == 1 and report["diagnostics"][0]["code"] == "PLOT-001"
    assert not output.exists()
