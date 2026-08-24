from pathlib import Path

from toolchain.runtime_manifest import (
    DEFAULT_BASELINE_PATH,
    RUST_RUO_FUNCTIONS,
    RUST_TENSOR_FUNCTIONS,
    build_manifest,
    diff_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_runtime_consolidation_manifest_matches_frozen_baseline():
    baseline = REPO_ROOT / DEFAULT_BASELINE_PATH
    assert diff_manifest(baseline) == []


def test_phase0_manifest_does_not_claim_known_rust_gaps_are_complete():
    manifest = build_manifest()
    tensor = {item["name"]: item for item in manifest["namespaces"]["tensor"]}
    ruo = {item["name"]: item for item in manifest["namespaces"]["ruo"]}
    assert tensor["tensor.softmax"]["rust"] == "unsupported"
    assert tensor["tensor.concat"]["rust"] == "unsupported"
    assert ruo["ruo.commit"]["rust"] == "unsupported"
    assert "softmax" not in RUST_TENSOR_FUNCTIONS
    assert "ruo.commit" not in RUST_RUO_FUNCTIONS


def test_phase0_manifest_records_current_product_dispatch_split():
    paths = build_manifest()["execution_paths"]
    assert paths["standalone_source"]["primary"] == "rust_computation_vm"
    assert paths["project"]["primary"] == "python_ast_runtime"
    assert paths["installed_distribution"]["computation_vm_binary_packaged"] is False
