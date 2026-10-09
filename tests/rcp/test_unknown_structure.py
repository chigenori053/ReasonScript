"""URS-T01–T10: source constructors and native structural transport."""
import copy
import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]

@pytest.fixture(scope="module")
def native():
    subprocess.run(["cargo", "build", "--release", "--manifest-path", "ReasonRuntime/Cargo.toml", "-p", "reasonscript-native-reasonunit-runtime", "--bin", "reasonunit-runtime-native"], cwd=ROOT, check=True, capture_output=True, timeout=180)
    return ROOT / "ReasonRuntime/target/release/reasonunit-runtime-native"

@pytest.fixture(scope="module")
def source_message():
    subprocess.run([str(ROOT / "reason"), "build"], cwd=ROOT / "examples/unknown_structure", check=True, capture_output=True, timeout=60)
    command = [str(ROOT / "reason"), "run", "examples/unknown_structure/foundation.rsn", "--entry", "SerializedUnknownStructure", "--json", "--trace=off"]
    messages = []
    for _ in range(2):
        run = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True, timeout=60)
        report = json.loads(run.stdout)
        assert report["status"] == "success" and report["execution_mode"] == "integrated-rust"
        assert report["runtime_result"]["calculations"]["StructuralChecks"] is True
        messages.append(json.loads(report["runtime_result"]["calculations"]["SerializedUnknownStructure"]))
    assert messages[0] == messages[1]
    return messages[0]

def deliver(native, message):
    session = {"cores": {"dsn:a": "core:a", "dsn:b": "core:b"}, "limits": {"messages": 8, "requests": 8, "hops": 8, "bytes": 100000}, "messages": [message]}
    return subprocess.run([str(native), "rcp"], input=json.dumps(session), text=True, capture_output=True, timeout=30)

def test_urs_t01_t03_t07_t08_source_models_and_lossless_transfer(native, source_message):
    wire_schema = json.loads((ROOT / "schemas/rcp_message.schema.json").read_text())
    structure_schema = json.loads((ROOT / "schemas/unknown_reasoning_structure.schema.json").read_text())
    jsonschema.Draft202012Validator(wire_schema).validate(source_message)
    for unit in source_message["payload"]["unknowns"]:
        jsonschema.Draft202012Validator(structure_schema).validate(unit)
    records = {record["reference"]["kind"]: record["value"] for record in source_message["payload"]["records"]}
    for kind in ("URU", "URUS", "URUO", "UnknownRelation"):
        jsonschema.Draft202012Validator(structure_schema).validate(records[kind])
    assert records["URU"]["id"] == "uru:a"
    assert records["URU"]["knowledge_refs"] == ["knowledge:source"]
    assert records["URU"]["missing_information"] == "missing measurement"
    assert records["URUO"]["placements"][1]["position"] is None
    assert records["URUO"]["placements"][0]["status"] == "known"
    assert {record["value"]["kind"] for record in source_message["payload"]["records"] if record["reference"]["kind"] == "UnknownRelation"} == {"DEPENDS_ON", "CAUSED_BY", "BLOCKS", "RELATED_TO", "CONFLICTS_WITH"}
    outputs = [deliver(native, source_message) for _ in range(2)]
    assert all(output.returncode == 0 for output in outputs), outputs[0].stdout
    assert outputs[0].stdout == outputs[1].stdout
    assert json.loads(outputs[0].stdout)["deliveries"]["dsn:b"][0]["payload"] == source_message["payload"]

@pytest.mark.parametrize("damage", ["cycle", "missing_uru", "missing_description_body", "mistyped_uru", "dependency_mismatch", "outside_graph", "duplicate_member", "unknown_position", "known_position", "2d", "bad_bounds", "outside_bounds", "missing_placement", "constraint_target", "constraint_value", "bad_relation", "missing_manifest", "duplicate_uru_identity", "absent_position", "absent_bounds", "absent_constraint_value"])
def test_urs_t04_t07_reject_malformed_structure(native, source_message, damage):
    message = copy.deepcopy(source_message)
    payload = message["payload"]
    by_kind = {record["reference"]["kind"]: record for record in payload["records"]}
    graph, space = by_kind["URUS"], by_kind["URUO"]
    dependency = next(record for record in payload["records"] if record["reference"]["id"] == "unknown-relation:ba")
    a = next(unit for unit in payload["unknowns"] if unit["id"] == "uru:a")
    if damage == "cycle":
        a["dependencies"] = ["uru:c"]
    elif damage in ("missing_uru", "missing_description_body"):
        payload["unknowns"] = [unit for unit in payload["unknowns"] if unit["id"] != "uru:a"]
        if damage == "missing_uru":
            payload["records"].remove(by_kind["URU"])
    elif damage == "mistyped_uru":
        dependency["value"]["target"]["kind"] = "RU"
    elif damage == "dependency_mismatch":
        dependency["value"]["target"]["id"] = "uru:c"
    elif damage == "outside_graph":
        graph["value"]["uru_refs"].remove("uru:a")
    elif damage == "duplicate_member":
        graph["value"]["uru_refs"].append("uru:a")
    elif damage == "unknown_position":
        space["value"]["placements"][1]["position"] = [0, 0, 0]
    elif damage == "known_position":
        space["value"]["placements"][0]["position"] = None
    elif damage == "2d":
        space["value"]["placements"][0]["position"] = [0, 0]
    elif damage == "bad_bounds":
        space["value"]["coordinate_bounds"][0] = [10, -10]
    elif damage == "outside_bounds":
        space["value"]["placements"][0]["position"] = [11, 0, 0]
    elif damage == "missing_placement":
        space["value"]["placements"].pop()
    elif damage == "constraint_target":
        space["value"]["constraints"][0]["target"]["id"] = "uru:absent"
    elif damage == "constraint_value":
        space["value"]["constraints"][0]["distance"] = -1
    elif damage == "absent_position":
        del space["value"]["placements"][1]["position"]
    elif damage == "absent_bounds":
        del space["value"]["coordinate_bounds"]
    elif damage == "absent_constraint_value":
        del space["value"]["constraints"][0]["distance"]
    elif damage == "bad_relation":
        dependency["value"]["kind"] = "INFERRED_BY"
    elif damage == "missing_manifest":
        graph["references"].pop()
    else:
        payload["records"].append(copy.deepcopy(by_kind["URU"]))
    result = deliver(native, message)
    assert result.returncode == 1, result.stdout
    assert json.loads(result.stdout)["ok"] is False


def test_urs_t02_t08_preserve_complete_uru_reevaluation_history(native, source_message):
    message = copy.deepcopy(source_message)
    a = next(unit for unit in message["payload"]["unknowns"] if unit["id"] == "uru:a")
    evidence = {"kind": "Evidence", "id": "evidence:expired"}
    message["payload"]["records"].append({"reference": evidence, "value": {"id": evidence["id"], "value": "old observation"}, "references": []})
    for state in ("IN_PROGRESS", "CANDIDATE", "RESOLVED", "REOPENED", "OPEN", "BLOCKED"):
        has_candidate = state in ("CANDIDATE", "RESOLVED")
        a["history"].append({"state": state, "candidate": "answer" if has_candidate else None, "evidence": [evidence] if has_candidate else []})
    result = deliver(native, message)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["deliveries"]["dsn:b"][0]["payload"] == message["payload"]
