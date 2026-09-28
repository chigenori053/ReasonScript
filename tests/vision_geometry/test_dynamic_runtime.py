"""Public generic DynamicClusterRuntime contract and CLI boundary."""
import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_generic_runtime_contract_and_cli(tmp_path):
    observation = json.loads((ROOT / "tests/fixtures/vision_runtime/solar_observation.json").read_text())
    tasks = [
        {"schema_version": "reasonscript-runtime-task/1.0", "task_id": "generated-vision", "runtime_type": "VISION",
         "goal": "EXTRACT_OBJECTS", "input_state": observation, "dependencies": [], "resource_hint": {}, "provenance": ["source"]},
        {"schema_version": "reasonscript-runtime-task/1.0", "task_id": "generated-geometry", "runtime_type": "GEOMETRY",
         "goal": "CALCULATE_SPATIAL_RELATIONS", "input_state": None, "dependencies": ["generated-vision"], "resource_hint": {}, "provenance": []},
    ]
    task_schema = json.loads((ROOT / "schemas/runtime_task.schema.json").read_text())
    output_schema = json.loads((ROOT / "schemas/runtime_output.schema.json").read_text())
    for task in tasks:
        jsonschema.validate(task, task_schema)
    source = tmp_path / "tasks.json"
    source.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
    result = subprocess.run([str(ROOT / "reason"), "cluster", "dynamic", "runtime", str(source), "--json"],
                            cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr + result.stdout
    output = json.loads(result.stdout)
    assert output["status"] == "COMPLETED"
    assert output["decision"] == "cluster"
    assert output["semantic_state"]["schema"] == "mra-mirp-graph-fragment/0.1"
    for item in output["task_outputs"]:
        jsonschema.validate(item, output_schema)
        assert item["trace"]["worker_id"] == f'worker:{item["runtime_type"]}:{item["task_id"]}'
    tasks[0]["runtime_type"] = "MATH"
    source.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
    result = subprocess.run([str(ROOT / "reason"), "cluster", "dynamic", "runtime", str(source), "--json"],
                            cwd=ROOT, text=True, capture_output=True)
    assert result.returncode != 0
    assert json.loads(result.stdout)["status"] == "UNSUPPORTED"


def test_canonical_task_schema_rejects_missing_and_future_fields():
    schema = json.loads((ROOT / "schemas/runtime_task.schema.json").read_text())
    task = {"schema_version": "reasonscript-runtime-task/1.0", "task_id": "generated",
            "runtime_type": "GEOMETRY", "goal": "CALCULATE_SPATIAL_RELATIONS",
            "input_state": None, "dependencies": [], "resource_hint": {}, "provenance": []}
    jsonschema.validate(task, schema)
    for field in task:
        invalid = task.copy()
        del invalid[field]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid, schema)
    for version in ("reasonscript-runtime-task/2.0", "future"):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({**task, "schema_version": version}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**task, "dependencies": ["same", "same"]}, schema)
