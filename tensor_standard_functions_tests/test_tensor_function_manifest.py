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


def test_reference_runtime_preserves_contract_types_and_serialization():
    import pickle
    from dataclasses import FrozenInstanceError
    import pytest
    from frontend.tensor.contracts import tensor_function_contracts as compiler_contracts
    from frontend.tensor.runtime import TensorFunctionContract, tensor_function_contracts

    contracts = tensor_function_contracts()
    assert {k:v.to_dict() for k,v in contracts.items()} == {k:v.to_dict() for k,v in compiler_contracts().items()}
    contract = contracts['tensor.create']
    assert type(contract) is TensorFunctionContract
    restored = pickle.loads(pickle.dumps(contract))
    assert type(restored) is TensorFunctionContract and restored == contract
    with pytest.raises(FrozenInstanceError):
        contract.function_id = 'changed'
    # Callers may edit returned metadata without changing later registrations.
    contract.return_contract['kind'] = 'changed'
    assert tensor_function_contracts()['tensor.create'].return_contract['kind'] == 'tensor'
