from pathlib import Path

from toolchain.tensor_manifest import DEFAULT_BASELINE_PATH, diff_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_tensor_contract_manifest_matches_frozen_baseline():
    baseline_path = REPO_ROOT / DEFAULT_BASELINE_PATH
    diffs = diff_manifest(baseline_path)
    assert diffs == [], (
        "Tensor Standard Functions contract drifted from the frozen Phase 0 "
        f"baseline ({baseline_path}). If this change is intentional, update "
        "the baseline with `reason tensor-manifest --out docs/reports` and "
        "record the change in the changelog. Diffs: " + "; ".join(diffs)
    )
