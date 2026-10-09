"""Source-level RCP construction through native Domain DSN delivery."""
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
def source_result():
    subprocess.run([str(ROOT / "reason"), "build"], cwd=ROOT / "examples/rcp", check=True, capture_output=True, text=True, timeout=60)
    completed = subprocess.run([str(ROOT / "reason"), "run", "examples/rcp/foundation.rsn", "--entry", "SerializedRequest", "--json", "--trace=off"], cwd=ROOT, check=True, capture_output=True, text=True, timeout=60)
    report = json.loads(completed.stdout)
    assert report["status"] == "success" and report["execution_mode"] == "integrated-rust"
    return report["runtime_result"]["calculations"]

def test_source_unknown_policy(source_result):
    assert source_result["FoundationChecks"] is True

def test_source_to_native_dsn_and_schema(native, source_result):
    message = json.loads(source_result["SerializedRequest"])
    jsonschema.Draft202012Validator(json.loads((ROOT / "schemas/rcp_message.schema.json").read_text())).validate(message)
    session = {"cores": {"dsn:a": "core:a", "dsn:b": "core:b"}, "limits": {"messages": 8, "requests": 8, "hops": 8, "bytes": 100000}, "messages": [message]}
    outputs = []
    for _ in range(2):
        completed = subprocess.run([str(native), "rcp"], input=json.dumps(session), text=True, capture_output=True, check=True, timeout=30)
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1]
    receipt = json.loads(outputs[0])["deliveries"]["dsn:b"][0]
    assert receipt["payload"] == message["payload"]
    assert receipt["trace"] == ["dsn:a", "dsn:b"]
    session["messages"].append(message)
    rejected = subprocess.run([str(native), "rcp"], input=json.dumps(session), text=True, capture_output=True, timeout=30)
    assert rejected.returncode == 1
    assert "duplicate message" in json.loads(rejected.stdout)["diagnostics"][0]["message"]


def test_cli_session_and_invalid_input(native, source_result, tmp_path):
    message = json.loads(source_result["SerializedRequest"])
    path = tmp_path / "session.json"
    session = {"cores": {"dsn:a": "core:a", "dsn:b": "core:b"}, "limits": {"messages": 8, "requests": 8, "hops": 8, "bytes": 100000}, "messages": [message]}
    path.write_text(json.dumps(session))
    completed = subprocess.run([str(ROOT / "reason"), "rcp", "run", str(path), "--json"], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stdout
    assert json.loads(completed.stdout)["deliveries"]["dsn:b"][0]["payload"] == message["payload"]
    path.write_text("{}")
    rejected = subprocess.run([str(ROOT / "reason"), "rcp", "run", str(path), "--json"], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert rejected.returncode == 1
    assert json.loads(rejected.stdout)["ok"] is False

@pytest.fixture(scope="module")
def structural_result():
    completed = subprocess.run([str(ROOT / "reason"), "run", "standard_library/reasoning_structure.rsn", "--json"], cwd=ROOT, check=True, capture_output=True, text=True, timeout=60)
    report = json.loads(completed.stdout)
    assert report["ok"] and report["execution_mode"] == "integrated-rust"
    assert report["runtime_result"]["calculations"]["StructuralChecks"] is True
    return json.loads(report["runtime_result"]["calculations"]["SerializedStructureMessage"])


def deliver(native, message):
    session = {"cores": {"dsn:a": "core:a", "dsn:b": "core:b"}, "limits": {"messages": 8, "requests": 8, "hops": 8, "bytes": 100000}, "messages": [message]}
    return subprocess.run([str(native), "rcp"], input=json.dumps(session), capture_output=True, text=True, timeout=30)


def test_structure_and_spatial_roundtrip(native, structural_result):
    schema = json.loads((ROOT / "schemas/rcp_message.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(structural_result)
    outputs = [deliver(native, structural_result) for _ in range(2)]
    assert all(result.returncode == 0 for result in outputs), outputs[0].stdout
    assert outputs[0].stdout == outputs[1].stdout
    payload = json.loads(outputs[0].stdout)["deliveries"]["dsn:b"][0]["payload"]
    assert payload == structural_result["payload"]
    bodies = {record["reference"]["kind"]: record["value"] for record in payload["records"]}
    assert "placements" not in bodies["RUS"]
    assert bodies["RUO"]["placements"][1]["position"] == [1.0, 2.0, 3.0]
    assert bodies["RUO"]["placements"][0]["direction"] == [1.0, 0.0, 0.0]
    assert bodies["RUO"]["structure_refs"] == [bodies["RUS"]["id"]]


@pytest.mark.parametrize("kind", ["RU", "RUS", "RUO"])
def test_unknown_origins_each_structural_form(native, structural_result, source_result, kind):
    import copy
    message = copy.deepcopy(structural_result)
    reference = next(record["reference"] for record in message["payload"]["records"] if record["reference"]["kind"] == kind)
    message["kind"] = "UNKNOWN_REPORT"
    reevaluation = json.loads(source_result["SerializedReevaluation"])
    unit = copy.deepcopy(reevaluation["payload"]["unknowns"][0])
    unit["id"] = "unknown:structural"
    unit["origins"] = [reference]
    message["payload"]["records"].append(reevaluation["payload"]["records"][1])
    message["payload"]["unknowns"] = [unit]
    result = deliver(native, message)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["deliveries"]["dsn:b"][0]["payload"]["unknowns"] == message["payload"]["unknowns"]


@pytest.mark.parametrize("damage", ["state_as_structure", "container_as_object", "2d", "missing_placement", "zero_direction", "domain_mix", "missing_member", "wrong_manifest", "contained_missing_unit"])
def test_reject_structural_corruption(native, structural_result, damage):
    import copy
    message = copy.deepcopy(structural_result)
    records = message["payload"]["records"]
    rus = next(record for record in records if record["reference"]["kind"] == "RUS")
    ruo = next(record for record in records if record["reference"]["kind"] == "RUO")
    if damage == "state_as_structure":
        rus["value"] = {"id": rus["reference"]["id"], "revision": 1}
    elif damage == "container_as_object":
        ruo["value"] = {"id": ruo["reference"]["id"], "reason_unit_ref": "ru:a"}
    elif damage == "2d":
        ruo["value"]["placements"][0]["position"] = [0.0, 1.0]
    elif damage == "missing_placement":
        ruo["value"]["placements"].pop()
    elif damage == "zero_direction":
        ruo["value"]["placements"][0]["direction"] = [0.0, 0.0, 0.0]
    elif damage == "domain_mix":
        rus["value"]["relation_refs"] = ["relation:spatial"]
        rus["references"][-1]["id"] = "relation:spatial"
    elif damage == "missing_member":
        rus["value"]["unit_refs"][1] = "ru:missing"
    elif damage == "wrong_manifest":
        ruo["references"][0]["kind"] = "RUS"
    else:
        ruo["value"]["unit_refs"] = ["ru:a"]
        ruo["value"]["placements"] = [placement for placement in ruo["value"]["placements"] if placement["target"]["id"] != "ru:b"]
    result = deliver(native, message)
    assert result.returncode == 1, result.stdout
    assert json.loads(result.stdout)["ok"] is False


def test_removed_legacy_wire_is_rejected(native):
    message = {"schema": "reasonscript-rcp-message/0.1", "protocol_version": "0.1", "message_id": "message:legacy", "source": "dsn:a", "destination": "dsn:b", "kind": "REQUEST", "correlation_id": "conversation:legacy", "causation_id": None, "trace": [], "payload": {"records": [{"reference": {"kind": "RUS", "id": "rus:legacy"}, "value": {"id": "rus:legacy", "revision": 1}, "references": []}], "unknowns": []}}
    rejected = deliver(native, message)
    assert rejected.returncode == 1
    assert "unsupported schema or protocol version" in rejected.stdout
    message["schema"] = "reasonscript-rcp-message/0.2"
    message["protocol_version"] = "0.2"
    assert deliver(native, message).returncode == 1


@pytest.mark.parametrize("kind", ["RuntimeState", "RuntimeObject", "RuntimeRelation"])
def test_removed_runtime_record_kinds_are_rejected(native, structural_result, kind):
    import copy
    message = copy.deepcopy(structural_result)
    message["payload"]["records"][0]["reference"]["kind"] = kind
    schema = json.loads((ROOT / "schemas/rcp_message.schema.json").read_text())
    assert not jsonschema.Draft202012Validator(schema).is_valid(message)
    result = deliver(native, message)
    assert result.returncode == 1
    assert "unknown variant" in json.loads(result.stdout)["diagnostics"][0]["message"]


def test_p1_source_reevaluation_roundtrip_and_determinism(native, source_result):
    message = json.loads(source_result["SerializedReevaluation"])
    jsonschema.Draft202012Validator(json.loads((ROOT / "schemas/rcp_message.schema.json").read_text())).validate(message)
    unit = message["payload"]["unknowns"][0]
    assert [revision["state"] for revision in unit["history"]] == [
        "OPEN", "IN_PROGRESS", "OPEN", "IN_PROGRESS", "CANDIDATE", "OPEN",
        "IN_PROGRESS", "CANDIDATE", "RESOLVED", "REOPENED", "OPEN", "BLOCKED"]
    assert unit["history"][4]["candidate"] == unit["history"][8]["candidate"] == "answer"
    assert unit["history"][8]["evidence"] == unit["grounds"]
    assert unit["origins"] == [{"kind": "RU", "id": "ru:request"}]
    outputs = [deliver(native, message) for _ in range(2)]
    assert all(result.returncode == 0 for result in outputs), outputs[0].stdout
    assert outputs[0].stdout == outputs[1].stdout
    assert json.loads(outputs[0].stdout)["deliveries"]["dsn:b"][0]["payload"] == message["payload"]


@pytest.mark.parametrize("damage", ["skip_reopened", "resume_blocked", "changed_resolution", "candidate_on_retry"])
def test_p1_reject_corrupted_reevaluation(native, source_result, damage):
    import copy
    message = copy.deepcopy(json.loads(source_result["SerializedReevaluation"]))
    history = message["payload"]["unknowns"][0]["history"]
    if damage == "skip_reopened":
        del history[9]
    elif damage == "resume_blocked":
        history.append({"state": "OPEN", "candidate": None, "evidence": []})
    elif damage == "changed_resolution":
        history[8]["candidate"] = "different"
    else:
        history[2]["candidate"] = "premature"
    result = deliver(native, message)
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


def test_p1_common_builder_preserves_all_structural_records(native, structural_result, tmp_path):
    """A separate .rsn consumer imports the common API with its own domain bodies."""
    import shutil
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    for source in (ROOT / "standard_library/rcp").glob("*.rsn"):
        shutil.copyfile(source, source_dir / source.name)
    (tmp_path / "reason.toml").write_text('[package]\nname = "Consumer"\nversion = "0.1.0"\n[source]\nentry = "consumer.rsn"\n')
    reference = lambda item: f'Reference {{ kind: {json.dumps(item["kind"])}, id: {json.dumps(item["id"])} }}'
    records = []
    for item in structural_result["payload"]["records"]:
        references = ", ".join(reference(ref) for ref in item["references"])
        value = json.dumps(json.dumps(item["value"], separators=(",", ":")))
        records.append(f'Record {{ reference: {reference(item["reference"])}, value_json: {value}, references: [{references}] }}')
    source = '''module Consumer {
  import RCPReference
  import RCPMessage
  calculation Send {
    result = RCPMessage::Encode(RCPMessage::Request("message:structure", "dsn:a", "dsn:b", "conversation:structure", Payload { records: RECORDS, unknowns: [] }))
  }
}
'''.replace("RECORDS", "[" + ", ".join(records) + "]")
    (tmp_path / "consumer.rsn").write_text(source)
    command = [str(ROOT / "reason"), "run", "--entry", "Send", "--json", "--trace=off"]
    runs = [subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=True, timeout=60) for _ in range(2)]
    reports = [json.loads(run.stdout) for run in runs]
    messages = [json.loads(report["runtime_result"]["calculations"]["Send"]) for report in reports]
    assert all(report["execution_mode"] == "integrated-rust" for report in reports)
    assert messages[0] == messages[1]
    assert messages[0]["payload"] == structural_result["payload"]
    result = deliver(native, messages[0])
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["deliveries"]["dsn:b"][0]["payload"] == messages[0]["payload"]
