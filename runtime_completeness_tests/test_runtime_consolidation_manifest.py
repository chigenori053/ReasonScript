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


def test_phase5_manifest_records_tensor_ruo_and_vision_completion():
    manifest = build_manifest()
    tensor = {item["name"]: item for item in manifest["namespaces"]["tensor"]}
    ruo = {item["name"]: item for item in manifest["namespaces"]["ruo"]}
    vision = {item["name"]: item for item in manifest["namespaces"]["vision"]}
    assert tensor["tensor.softmax"]["rust"] == "implemented"
    assert tensor["tensor.concat"]["rust"] == "implemented"
    assert ruo["ruo.commit"]["rust"] == "implemented"
    assert vision["vision.infer"]["rust"] == "implemented"
    assert vision["vision.build_ruo"]["rust"] == "implemented"
    assert "softmax" in RUST_TENSOR_FUNCTIONS
    assert "ruo.commit" in RUST_RUO_FUNCTIONS


def test_manifest_records_current_product_dispatch_split():
    manifest = build_manifest()
    paths = manifest["execution_paths"]
    assert paths["standalone_source"]["primary"] == "rust_computation_vm"
    assert paths["project"]["primary"] == "rust_computation_vm"
    assert paths["installed_distribution"]["computation_vm_binary_packaged"] is True
    assert paths["project"]["manifest_backend_selects_engine"] is True
    assert all(item["rust"] == "implemented" for item in manifest["namespaces"]["reasoning"])
