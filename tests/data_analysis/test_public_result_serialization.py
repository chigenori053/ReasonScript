import json
from pathlib import Path

from runtime.data import (
    DataBackend,
    Table,
    analyze_titanic,
    analyze_titanic_execution,
    canonicalize_analysis_result,
    validate_analysis_result,
)


def _csv(tmp_path: Path) -> Path:
    path = tmp_path / "train.csv"
    path.write_text(
        "PassengerId,Survived,Pclass,Name,Sex,Age,SibSp,Parch,Ticket,Fare,Cabin,Embarked\n"
        "1,1,1,A,female,30,0,0,T1,10,C1,S\n"
        "2,0,3,B,male,,1,0,T2,5,,C\n",
        encoding="utf-8",
    )
    return path


def _walk(value):
    assert isinstance(value, (dict, list, str, int, float, bool, type(None)))
    if isinstance(value, dict):
        for item in value.values(): _walk(item)
    elif isinstance(value, list):
        for item in value: _walk(item)


def test_public_result_is_json_safe_and_schema_valid(tmp_path):
    result = analyze_titanic(_csv(tmp_path), project_root=tmp_path)
    json.dumps(result, allow_nan=False); _walk(result)
    schema = json.loads((Path(__file__).parents[2] / "schemas/titanic_analysis_result.schema.json").read_text())
    assert schema["properties"]["schema_version"]["const"] == result["schema_version"]
    validate_analysis_result(result)
    assert result["status"] == "pass"
    assert result["backend"] == {"id": "python-reference", "version": "0.1", "implementation": "runtime.data.backend.DataBackend"}
    assert result["dataset"]["source_path"] == "train.csv"
    assert result["table"]["row_count"] == 2 and result["table"]["column_count"] == 14


def test_execution_context_is_separate_and_result_is_deterministic(tmp_path):
    path = _csv(tmp_path)
    first = analyze_titanic_execution(path, project_root=tmp_path)
    second = analyze_titanic_execution(path, project_root=tmp_path)
    assert isinstance(first.table, Table) and isinstance(first.backend, DataBackend)
    assert not any(isinstance(value, (Table, DataBackend)) for value in first.result.value.values())
    assert canonicalize_analysis_result(first.result.value) == canonicalize_analysis_result(second.result.value)
