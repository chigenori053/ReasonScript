"""Source-level RCP construction through native Domain DSN delivery."""
import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]

@pytest.fixture(scope="module")
def native():
    subprocess.run(["cargo", "build", "--manifest-path", "ReasonRuntime/Cargo.toml", "-p", "reasonscript-native-reasonunit-runtime", "--bin", "reasonunit-runtime-native"], cwd=ROOT, check=True, capture_output=True, timeout=180)
    return ROOT / "ReasonRuntime/target/debug/reasonunit-runtime-native"

@pytest.fixture(scope="module")
def source_result():
    completed = subprocess.run([str(ROOT / "reason"), "run", "examples/rcp/foundation.rsn", "--json"], cwd=ROOT, check=True, capture_output=True, text=True, timeout=60)
    report = json.loads(completed.stdout)
    assert report["ok"] and report["execution_mode"] == "integrated-rust"
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
