import json
from pathlib import Path

import pytest

from runtime import visual
from runtime.data import DataBackend, Field, Schema

SCHEMA = Schema((Field("category", "string"), Field("group", "string"), Field("x", "float"),
                 Field("y", "float", True)))


@pytest.fixture
def table(tmp_path):
    backend = DataBackend(project_root=tmp_path)
    return backend.from_external([
        {"category":"b","group":"g2","x":2.0,"y":4.0},
        {"category":"a","group":"g1","x":1.0,"y":2.0},
        {"category":"a","group":"g2","x":3.0,"y":None},
    ], SCHEMA)


def test_models_charts_serialization_and_determinism(table):
    specs = [visual.line(table, x="x", y="y"), visual.bar(table, category="category", value="y", aggregate="mean"),
             visual.bar_horizontal(table, category="category", value="y"), visual.scatter(table, x="x", y="y", group="group"),
             visual.histogram(table, column="x"), visual.box(table, value="x"), visual.pie(table, category="category", value="x", aggregate="sum"),
             visual.area(table, x="x", y="y"), visual.heatmap(table, x="category", y="group", value="x"),
             visual.grouped(table, category="category", value="x", group="group"), visual.correlation(table)]
    for spec in specs:
        assert not visual.validate(spec, table)
        assert json.dumps(visual.export_spec(spec), allow_nan=False)
        assert visual.canonical_json(spec) == visual.canonical_json(spec)
        assert spec.visualization_id.startswith("viz_")


def test_aggregation_order_missing_and_negative_validation(table):
    spec = visual.bar(table, category="category", value="x", aggregate="mean")
    from runtime.visualization.operations import chart_data
    assert chart_data(spec, table)["series"][0]["x"] == ["a", "b"]
    rejected = visual.bar(table, category="category", value="y", missing_policy="reject")
    with pytest.raises(visual.VisualizationError, match="VSL-MIS-002"): chart_data(rejected, table)
    with pytest.raises(visual.VisualizationError, match="VSL-SRC-003"): visual.line(table, x="missing", y="y")
    with pytest.raises(visual.VisualizationError, match="VSL-TYPE-001"): visual.histogram(table, column="category")


def test_optional_backend_and_path_confinement(table, tmp_path):
    backend = visual.MatplotlibBackend(project_root=tmp_path)
    spec = visual.bar(table, category="category", value="x")
    if not backend.available():
        with pytest.raises(visual.VisualizationError, match="VSL-RND-001"): backend.render(spec, table, "artifacts")
    else:
        with pytest.raises(visual.VisualizationError, match="VSL-ART-003"): backend.render(spec, table, "../escape")


def test_png_svg_artifacts_and_schema_contract(table, tmp_path):
    backend = visual.MatplotlibBackend(project_root=tmp_path)
    if not backend.available(): pytest.skip("optional Matplotlib backend unavailable")
    spec = visual.grouped(table, category="category", value="x", group="group", title="Grouped")
    first = visual.render(spec, table, "artifacts", project_root=tmp_path, backend=backend)
    hashes = {item["format"]: item["sha256"] for item in first["artifacts"]}
    second = visual.render(spec, table, "artifacts2", project_root=tmp_path, backend=backend)
    assert hashes == {item["format"]: item["sha256"] for item in second["artifacts"]}
    assert first["status"] == "pass" and not first["diagnostics"]
    for name in ("chart.png", "chart.svg", "visualization_spec.json", "visualization_ir.json", "render_plan.json",
                 "visualization_evidence.json", "visualization_validation.json", "artifact_manifest.json"):
        assert (tmp_path / "artifacts" / name).is_file()
