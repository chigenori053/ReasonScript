from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

from toolchain.reasonunit_tensor import (
    CANONICAL_ARTIFACTS,
    DTYPES,
    TensorError,
    convert_tensor,
    decode_mask,
    decode_scalar,
    encode_mask,
    encode_scalar,
    generate_tensor_profile,
    logical_digest,
    make_dense_tensor,
    make_inline_tensor,
    select_tensor,
    validate_tensor,
    validate_tensor_profile,
    verify_ruo_f1,
)
from toolchain.reasonunit_tensor.phase import PROFILE
from toolchain.reasonunit_tensor_cmd import run as cli_run

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def generated(tmp_path: Path) -> Path:
    output = tmp_path / "ruo-t1"
    assert generate_tensor_profile(ROOT, output)["phase_status"] == "VALIDATED"
    return output


def test_f1_prerequisite_is_verified_and_required(tmp_path: Path) -> None:
    assert verify_ruo_f1(ROOT)["summary"] == {"passed": 72, "failed": 0, "total": 72}
    missing = tmp_path / "missing"; missing.mkdir()
    assert generate_tensor_profile(ROOT, tmp_path / "out", f1_directory=missing)["phase_status"] == "NOT_VALIDATED"


def test_all_registered_dtypes_roundtrip_exactly() -> None:
    values = {"bool": True, "complex64": [1.5, -2.0], "complex128": [1.5, -2.0]}
    for dtype, spec in DTYPES.items():
        value = values.get(dtype, 1.5 if spec["kind"] in {"float", "bfloat"} else 1)
        encoded = encode_scalar(dtype, value)
        assert len(encoded) == spec["width"]
        decoded = decode_scalar(dtype, encoded)
        assert encode_scalar(dtype, decoded) == encoded


def test_nonfinite_negative_zero_and_invalid_boolean_are_rejected() -> None:
    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(TensorError): encode_scalar("float32", value)
    assert encode_scalar("float32", -0.0) == b"\0\0\0\0"
    with pytest.raises(TensorError): decode_scalar("float32", b"\0\0\0\x80")
    with pytest.raises(TensorError): decode_scalar("bool", b"\x02")


def test_scalar_empty_inline_and_dense_validation() -> None:
    scalar = make_inline_tensor("int32", [], [7]); assert scalar["element_count"] == 1 and validate_tensor(scalar)["ok"]
    empty = make_inline_tensor("uint8", [2, 0, 3], []); assert empty["element_count"] == 0 and validate_tensor(empty)["ok"]
    dense, data = make_dense_tensor("float32", [2], [1.0, 2.0], chunk_rows=1)
    assert validate_tensor(dense, resource_bytes=data)["ok"]
    assert not validate_tensor(dense, resource_bytes=data + b"\0")["ok"]


def test_axes_mapping_digest_and_duplicates() -> None:
    axis = {"ordinal": 0, "size": 2, "ordering": "stable_id", "duplicate_policy": "forbidden", "partial_loading_status": "complete", "identity_mapping": {"mapping_version": "1", "ordered_ids": ["ruo:unit:a", "ruo:unit:b"], "uniqueness": "unique", "source_object_revision": "ruo:revision:1"}}
    body = make_inline_tensor("int8", [2], [1, 2], axes=[axis]); assert validate_tensor(body)["ok"]
    duplicate = copy.deepcopy(body); duplicate["axes"][0]["identity_mapping"]["ordered_ids"] = ["ruo:unit:a", "ruo:unit:a"]
    assert not validate_tensor(duplicate, require_digest=False)["ok"]


def test_dense_coo_csr_conversion_is_lossless() -> None:
    source = make_inline_tensor("int32", [2, 2], [1, 0, 0, 2])
    for target in ("coo_resource", "csr_resource"):
        converted = convert_tensor(source, target)
        assert converted["logical_digest"] == source["logical_digest"]
        assert converted["conversion"]["semantic_loss_count"] == 0
        assert validate_tensor(converted)["ok"]


def test_masks_and_partial_selection_preserve_mapping() -> None:
    assert decode_mask(encode_mask(["valid", "invalid", "unknown", "not_loaded", "redacted"])) == ["valid", "invalid", "unknown", "not_loaded", "redacted"]
    body, data = make_dense_tensor("int16", [4], [1, 2, 3, 4])
    selected = select_tensor(body, {"ranges": [[1, 3]]}, resource_bytes=data)
    assert selected["shape"] == [2] and selected["validity"]["status"] == "partial"
    assert selected["selection"]["source_logical_digest"] == body["logical_digest"]


def test_tamper_and_path_safety_are_detected(tmp_path: Path) -> None:
    body, data = make_dense_tensor("uint8", [2], [1, 2])
    assert not validate_tensor(body, resource_bytes=b"\x01\x03")["ok"]
    unsafe = copy.deepcopy(body); unsafe["storage"]["locator"] = "../tensor.ruot"
    assert not validate_tensor(unsafe, resource_bytes=data)["ok"]


def test_cli_encode_and_phase_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "tensor.json"; source.write_text(json.dumps({"dtype": "int16", "shape": [2], "values": [1, 2]}), encoding="utf-8")
    target = tmp_path / "tensor.ruot"
    assert cli_run(["encode", str(source), "--output", str(target), "--json"], ROOT) == 0
    assert json.loads(capsys.readouterr().out)["integrity_status"] == "VALID" and target.read_bytes() == b"\x01\0\x02\0"


def test_phase_generates_47_artifacts_and_74_tests(generated: Path) -> None:
    assert len(CANONICAL_ARTIFACTS) == 47 and all((generated / name).is_file() for name in CANONICAL_ARTIFACTS)
    summary = json.loads((generated / "validation_summary.json").read_text())["data"]
    assert summary["summary"] == {"passed": 74, "failed": 0, "total": 74}
    assert summary["statuses"]["transition_decision"] == "PROCEED_TO_RUO-N1"
    assert validate_tensor_profile(ROOT, generated, verify_determinism=True)["ok"]


def test_artifact_envelopes_and_manifest_inventory(generated: Path) -> None:
    for path in generated.glob("*.json"):
        value = json.loads(path.read_text()); assert value["profile_version"] == PROFILE and set(value) == {"schema_version", "profile_version", "data"}
    manifest = json.loads((generated / "run_manifest.json").read_text())["data"]
    assert manifest["artifact_count"] == 47 and manifest["file_count"] == len(manifest["files"])
