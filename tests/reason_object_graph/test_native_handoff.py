"""Phase 10: Native Runtime parity at the ReasonGraph handoff boundary."""

import subprocess
from pathlib import Path

from toolchain.reason_object_graph import project_native_ruo_file, validate_graph
from toolchain.reasonunit_file import write_file
from toolchain.reasonunit_object.universal import reference_object


ROOT = Path(__file__).resolve().parents[2]


def test_phase10_native_runtime_and_reason_graph_have_stable_unit_identity_parity(tmp_path: Path) -> None:
    build = subprocess.run(["cargo", "build", "--manifest-path", "ReasonRuntime/crates/reason-object-core/Cargo.toml", "--offline", "--quiet"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert build.returncode == 0, build.stderr
    logical = reference_object()
    logical["relations"][0].update({"source_id": "ruo:unit:text", "target_id": "ruo:unit:numeric", "relation_class": "internal", "endpoint_resolution": "resolved"})
    source = tmp_path / "source.ruo"
    write_file(logical, source)
    result = project_native_ruo_file(source, root=ROOT)
    assert validate_graph(result["graph"]) == []
    assert result["report"]["native_unit_identity_parity"] is True
    assert result["report"]["native_logical_digest_parity"] is True
    assert result["native_handoff"]["read_only"] is True
