"""Phase 6 canonical artifact and CLI validation."""

import json
from pathlib import Path

from toolchain.reason_object_graph import CANONICAL_ARTIFACTS, generate_profile, validate_profile
from toolchain.reason_object_graph_cmd import run
from toolchain.reasonunit_file import write_file
from toolchain.reasonunit_object.universal import reference_object


ROOT = Path(__file__).resolve().parents[2]


def test_phase_generation_contains_the_complete_rri_matrix_and_artifact_set(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "reason-object-graph"
    result = generate_profile(ROOT, output)
    assert result["phase_status"] == "VALIDATED"
    assert {path.name for path in output.iterdir()} == set(CANONICAL_ARTIFACTS)
    summary = json.loads((output / "validation_summary.json").read_text(encoding="utf-8"))["data"]
    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))["data"]
    assert [item["test_id"] for item in summary["tests"]] == [f"RRI-{index:03}" for index in range(1, 29)]
    assert summary["summary"] == {"passed": 28, "failed": 0, "total": 28}
    assert manifest["artifacts"][-1] == {"path": "run_manifest.json", "sha256": "self_digest", "bytes": None}


def test_phase_validation_detects_tampering_and_checks_determinism(tmp_path: Path) -> None:
    output = tmp_path / "reason-object-graph"
    generate_profile(ROOT, output)
    assert validate_profile(ROOT, output, verify_determinism=True)["ok"]
    target = output / "relation_contract.json"
    target.write_bytes(target.read_bytes() + b"\n")
    assert not validate_profile(ROOT, output, verify_determinism=False)["ok"]


def test_phase_cli_generates_and_validates_the_profile(tmp_path: Path, capsys) -> None:
    output = tmp_path / "reason-object-graph"
    assert run(["generate", "--output", str(output), "--json"], ROOT) == 0
    assert json.loads(capsys.readouterr().out)["phase_status"] == "VALIDATED"
    assert run(["validate", "--output", str(output), "--json"], ROOT) == 0


def test_phase9_cli_projects_a_verified_ruo_file(tmp_path: Path, capsys) -> None:
    source, target = tmp_path / "source.ruo", tmp_path / "graph.rgraph"
    logical = reference_object()
    logical["relations"][0].update({"source_id": "ruo:unit:text", "target_id": "ruo:unit:numeric", "relation_class": "internal", "endpoint_resolution": "resolved"})
    write_file(logical, source)
    assert run(["project-ruo", str(source), "--output", str(target), "--json"], ROOT) == 0
    assert json.loads(capsys.readouterr().out)["publication"]["ok"] is True
