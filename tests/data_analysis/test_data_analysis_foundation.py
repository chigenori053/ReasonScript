import json
from pathlib import Path
import pytest
from runtime.data import AggregationSpec, DataBackend, DataError, Field, ResourceLimits, Schema, analyze_titanic, is_missing
from toolchain.data_artifacts import data_artifacts

SCHEMA = Schema((Field("id", "int"), Field("group", "string"), Field("value", "float", True)))

@pytest.fixture
def source(tmp_path):
    (tmp_path / "sample.csv").write_text('id,group,value\r\n1,"a",2.0\r\n2,a,\r\n3,b,4.0\r\n', encoding="utf-8")
    return tmp_path

def test_csv_table_missing_ids_and_determinism(source):
    backend = DataBackend(project_root=source)
    first = backend.load_csv("sample.csv", SCHEMA); second = backend.load_csv("sample.csv", SCHEMA)
    assert first.serialize() == second.serialize() and first.row_count == 3 and first.column_count == 3
    assert backend.count_missing(first, "value") == 1 and is_missing(first.rows[1].values[2])
    assert len({row.row_id for row in first.rows}) == 3

def test_json_external_operations_and_aggregations(tmp_path):
    records = [{"id": 1, "group": "b", "value": 4.0}, {"id": 2, "group": "a", "value": None},
               {"id": 3, "group": "a", "value": 2.0}]
    (tmp_path / "x.json").write_text(json.dumps(records), encoding="utf-8")
    backend = DataBackend(project_root=tmp_path); table = backend.load_json("x.json", SCHEMA)
    assert backend.select(table, ["group", "id"]).column_names == ("group", "id")
    filtered = backend.filter(table, lambda row: row["group"] == "a", name="group-a", referenced_columns=("group",))
    derived = backend.derive_column(filtered, "twice", "int", False, lambda row: row["id"] * 2, referenced_columns=("id",))
    assert [r.values[-1] for r in derived.rows] == [4, 6]
    result = backend.aggregate(backend.group_by(table, ["group"]),
        [AggregationSpec("count", None, "n"), AggregationSpec("mean", "value", "avg")])
    assert [r.values[0] for r in result.rows] == ["a", "b"] and result.rows[0].values[1:] == (2, 2.0)
    assert backend.from_external({"version": "reasonscript-external-table/0.1", "records": records}, SCHEMA).row_count == 3

def test_missing_empty_aggregation_artifacts(source):
    backend = DataBackend(project_root=source); table = backend.load_csv("sample.csv", SCHEMA)
    assert backend.missing_rate(table, "value") == pytest.approx(1 / 3)
    filled = backend.fill_missing(table, "value", 6.0); assert backend.mean(filled, "value") == 4.0
    assert backend.drop_missing(table, ["value"]).row_count == 2
    empty = backend.filter(table, lambda _: False, name="none")
    assert backend.count(empty) == 0 and is_missing(backend.mean(empty, "value"))
    artifacts = data_artifacts(filled, backend, knowledge=[{"statement": "filled", "value": True}])
    assert {"table.json", "data_provenance.json", "reason_ir.json", "execution_plan.json", "knowledge.json"} <= artifacts.keys()

def test_diagnostics_and_limits(tmp_path):
    backend = DataBackend(project_root=tmp_path, limits=ResourceLimits(max_rows=1))
    (tmp_path / "x.csv").write_text("id,group,value\n1,a,1\n2,b,2\n")
    with pytest.raises(DataError, match="DAF-RES-001"): backend.load_csv("x.csv", SCHEMA)
    with pytest.raises(DataError, match="DAF-SRC-005"): backend.load_csv("../escape.csv", SCHEMA)
    with pytest.raises(DataError, match="DAF-MIS-001"): backend.from_external([{"x": None}], Schema((Field("x", "int"),)))

def test_titanic_direct_regression_when_dataset_available():
    path = Path("/Users/chigenori/ReasonScriptProjects/kaggle-titanic-validation/data/raw/train.csv")
    if not path.is_file(): pytest.skip("external Titanic validation dataset is not installed")
    result = analyze_titanic(path); metrics = result["metrics"]
    assert result["input_mode"] == "CSV_DIRECT" and metrics["row_count"] == 891 and metrics["column_count"] == 12
    assert metrics["age_missing_count"] == 177 and metrics["cabin_missing_count"] == 687
    assert metrics["overall_survival_rate"] == pytest.approx(0.3838383838383838, abs=1e-9)
    assert len(result["knowledge"]) == 7 and result["evidence"]["evidence_id"].startswith("evd_")
