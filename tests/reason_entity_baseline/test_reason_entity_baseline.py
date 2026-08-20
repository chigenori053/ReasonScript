"""Phase F0 — Reason Entity Foundation baseline freeze tests (RS-RE-FSM-001)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from toolchain.reason_entity_baseline.baseline import (
    CANONICAL_ARTIFACTS,
    DETERMINISTIC_ARTIFACTS,
    PROFILE,
    generate_baseline,
    validate_baseline,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def generated(tmp_path: Path) -> Path:
    output = tmp_path / "reason-entity-f0"
    generate_baseline(ROOT, output)
    return output


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_generate_writes_all_canonical_artifacts(generated: Path) -> None:
    for name in CANONICAL_ARTIFACTS:
        assert (generated / name).is_file(), name
    assert (generated / "run_manifest.json").is_file()
    assert (generated / "final_report.md").is_file()


def test_generated_documents_carry_the_baseline_profile(generated: Path) -> None:
    for name in CANONICAL_ARTIFACTS:
        document = read(generated / name)
        assert document["profile_version"] == PROFILE
        assert "data" in document


def test_invalid_fixture_reproduces_expected_diagnostic(generated: Path) -> None:
    inventory = read(generated / "diagnostic_code_inventory.json")
    invalid_fixtures = inventory["data"]["invalid_fixtures"]
    assert invalid_fixtures
    for entry in invalid_fixtures:
        assert entry["matches_expected"], entry


def test_tensor_numeric_baseline_is_self_contained_and_finite(generated: Path) -> None:
    tensor_baseline = read(generated / "tensor_numeric_baseline.json")
    fixtures = tensor_baseline["data"]["fixtures"]
    assert fixtures
    for entry in fixtures:
        assert isinstance(entry["result_value"], float)
        assert entry["result_value"] == entry["result_value"]  # not NaN


def test_three_independent_generations_are_byte_identical(tmp_path: Path) -> None:
    runs = [tmp_path / f"run-{index}" for index in range(1, 4)]
    for run in runs:
        generate_baseline(ROOT, run)
    reference = {name: (runs[0] / name).read_bytes() for name in DETERMINISTIC_ARTIFACTS}
    for run in runs[1:]:
        for name, payload in reference.items():
            assert (run / name).read_bytes() == payload, name


def test_validate_baseline_accepts_its_own_generation(generated: Path) -> None:
    result = validate_baseline(ROOT, generated, verify_determinism=False)
    assert result["ok"], result["issues"]


def test_validate_baseline_detects_missing_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "incomplete"
    output.mkdir()
    result = validate_baseline(ROOT, output, verify_determinism=False)
    assert not result["ok"]
    assert result["issues"][0]["code"] == "RE-F0-001"
