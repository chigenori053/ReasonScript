from __future__ import annotations

import json
import subprocess
from pathlib import Path

from toolchain.reasonunit_file import write_file
from toolchain.reasonunit_object.model import validate_object
from toolchain.reasonunit_tensor import validate_tensor


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/vision_runtime/solar_observation.json"


def run_reason(*args: str) -> tuple[int, dict]:
    completed = subprocess.run(
        [str(ROOT / "reason"), "vision", *args, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_observation_validation_and_native_provenance() -> None:
    status, result = run_reason("validate-observation", str(FIXTURE))
    assert status == 0 and result["ok"] is True
    status, result = run_reason("verify-native")
    assert status == 0 and result["unsafe_blocks"] == 0


def test_generated_vision_object_is_valid_u1_and_t1(tmp_path: Path) -> None:
    status, result = run_reason("generate", "--output", str(tmp_path))
    assert status == 0 and result["phase_status"] == "VALIDATED"
    object_value = json.loads((tmp_path / "vision_object.json").read_text(encoding="utf-8"))
    language = json.loads((tmp_path / "vision_language_profile.json").read_text(encoding="utf-8"))
    assert language["profile"] == "reasonscript-vision-language-integration/0.1"
    assert validate_object(object_value) == []
    tensors = [payload for payload in object_value["payloads"] if payload["profile_id"] == "ruo.payload.tensor/1"]
    assert {payload["value"]["extensions"]["reasonscript.vision"]["role"] for payload in tensors} == {"detections", "embeddings"}
    for payload in tensors:
        resource = (tmp_path / payload["value"]["storage"]["locator"]).read_bytes()
        assert validate_tensor(payload, resource_bytes=resource)["ok"] is True


def test_vision_object_python_ruo_writer_to_native_reader(tmp_path: Path) -> None:
    status, result = run_reason("generate", "--output", str(tmp_path))
    assert status == 0 and result["phase_status"] == "VALIDATED"
    object_value = json.loads(
        (tmp_path / "vision_object.json").read_text(encoding="utf-8")
    )
    object_path = tmp_path / "earth_surface.ruo"
    assert write_file(object_value, object_path)["ok"]
    binary = ROOT / "NativeReasonUnitRuntime/target/debug/reasonunit-runtime-native"
    completed = subprocess.run(
        [str(binary), "load", str(object_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    native = json.loads(completed.stdout)
    assert completed.returncode == 0, completed.stderr
    assert native["ok"] and native["object_id"] == object_value["object_identity"]["entity_id"]


def test_tensor_axis_mapping_uses_stable_ruo_identity(tmp_path: Path) -> None:
    status, _ = run_reason("build-ruo", str(FIXTURE), "--output", str(tmp_path))
    assert status == 0
    object_value = json.loads((tmp_path / "vision_object.json").read_text(encoding="utf-8"))
    detection_tensor = next(payload for payload in object_value["payloads"] if payload.get("value", {}).get("extensions", {}).get("reasonscript.vision", {}).get("role") == "detections")
    ids = detection_tensor["value"]["axes"][0]["identity_mapping"]["ordered_ids"]
    assert ids and all(value.startswith("ruo:unit:vision-track:") for value in ids)
    assert ids == sorted(ids)
