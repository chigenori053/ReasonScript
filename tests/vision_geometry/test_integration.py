"""End-to-end native Vision → Geometry → MIRP and cluster equivalence."""
import hashlib
import json
import subprocess
from pathlib import Path

import jsonschema
import pytest
from toolchain.reason_object_graph.model import canonicalize_graph, validate_graph

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tests/fixtures/vision_language"


def reason(*args):
    result = subprocess.run([str(ROOT / "reason"), *map(str, args), "--json"], cwd=ROOT, text=True, capture_output=True)
    assert result.stdout, result.stderr
    return result.returncode, json.loads(result.stdout)


def test_real_image_to_mirp_and_cluster_three_runs(tmp_path):
    status, vision = reason("vision", "infer", SOURCE / "model.json", SOURCE / "image.bin")
    assert status == 0 and vision["ok"]
    observation = vision["observation"]
    source = tmp_path / "observation.json"
    source.write_text(json.dumps(observation), encoding="utf-8")
    tasks = {"tasks": [
        {"task_id": "vision", "runtime_type": "VISION", "input_state": observation, "goal": "EXTRACT_OBJECTS", "dependencies": [], "provenance": ["image.bin"], "resource_hint": {"estimated_operations": 10}},
        {"task_id": "geometry", "runtime_type": "GEOMETRY", "input_state": None, "goal": "CALCULATE_SPATIAL_RELATIONS", "dependencies": ["vision"], "provenance": [], "resource_hint": {"estimated_operations": 10}},
    ]}
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps(tasks), encoding="utf-8")
    task_schema = json.loads((ROOT / "schemas/visual_runtime_task.schema.json").read_text())
    for task in tasks["tasks"]:
        jsonschema.validate(task, task_schema)
    expected = None
    for _ in range(3):
        status, local = reason("geometry", "run", source)
        assert status == 0 and local["ok"]
        assert local["vision_trace"]["runtime"] == "VISION"
        assert local["trace"]["runtime"] == "GEOMETRY"
        for field, schema in (("observation", "visual_spatial_observation"), ("geometry_state", "geometry_state")):
            jsonschema.validate(local[field], json.loads((ROOT / f"schemas/{schema}.schema.json").read_text()))
        assert validate_graph(local["mirp"]["graph"]) == []
        fragment = {k: v for k, v in local["mirp"].items() if k != "fragment_hash"}
        assert local["mirp"]["fragment_hash"] == "sha256:" + hashlib.sha256(canonicalize_graph(fragment).encode()).hexdigest()
        status, clustered = reason("cluster", "dynamic", "visual", path)
        assert status == 0 and clustered["status"] == "COMPLETED"
        assert clustered["semantic_state"] == local["semantic_state"]
        assert clustered["decision"] == "cluster"
        if expected is None:
            expected = clustered["semantic_state"]
        assert clustered["semantic_state"] == expected


def test_invalid_vision_and_resource_boundary(tmp_path):
    observation = json.loads((SOURCE / "observation.json").read_text())
    observation["detections"][0]["confidence"] = 1.1
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(observation), encoding="utf-8")
    status, response = reason("geometry", "run", source)
    assert status != 0 and response["status"] == "ERROR"
    observation["detections"][0]["confidence"] = 0.5
    tasks = {"tasks": [{"task_id": "vision", "runtime_type": "VISION", "input_state": observation, "goal": "EXTRACT_OBJECTS", "dependencies": [], "provenance": []}], "limits": {"max_workers": 1, "max_operations": 1, "max_memory": 1, "timeout_ms": 1000, "max_state_size": 1, "local_threshold": 1}}
    path = tmp_path / "limited.json"
    path.write_text(json.dumps(tasks), encoding="utf-8")
    status, response = reason("cluster", "visual", path)
    assert status != 0 and response["status"] == "RESOURCE_LIMIT"


def test_rus_mirp_delta_schema_and_unknown_boundary(tmp_path):
    observation = json.loads((SOURCE / "observation.json").read_text())
    source = tmp_path / "observation.json"
    source.write_text(json.dumps(observation), encoding="utf-8")
    status, local = reason("geometry", "run", source)
    assert status == 0
    state = tmp_path / "state.json"
    state.write_text(json.dumps(local["geometry_state"]), encoding="utf-8")
    steps = tmp_path / "steps.json"
    steps.write_text(json.dumps([{"ru": "DistanceRU", "arguments": ["missing:centroid", "det:earth:language:42:centroid"]}]), encoding="utf-8")
    status, result = reason("geometry", "rus", state, steps)
    assert status == 0 and result["results"][0]["status"] == "UNKNOWN"
    jsonschema.validate(result["mirp_delta"], json.loads((ROOT / "schemas/geometry_mirp_delta.schema.json").read_text()))


def test_versioned_schema_rejects_invalid_coordinates_and_runtime_type():
    coordinate_schema = json.loads((ROOT / "schemas/visual_spatial_observation.schema.json").read_text())
    task_schema = json.loads((ROOT / "schemas/visual_runtime_task.schema.json").read_text())
    status, result = reason("geometry", "observe", ROOT / "tests/fixtures/vision_runtime/solar_observation.json")
    assert status == 0
    invalid = result["observation"]
    invalid["coordinate_system"]["y_direction"] = "UP"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, coordinate_schema)
    invalid_task = {"task_id": "x", "runtime_type": "OTHER", "input_state": None, "goal": "EXTRACT_OBJECTS", "dependencies": [], "provenance": []}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_task, task_schema)
