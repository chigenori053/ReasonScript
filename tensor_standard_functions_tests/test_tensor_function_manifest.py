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


def test_public_contract_types_keep_distinct_identity_and_signatures():
    import inspect
    from frontend.tensor.contracts import TensorFunctionContract as CompilerContract
    from frontend.tensor.runtime import TensorFunctionContract as ReferenceContract

    assert ReferenceContract is not CompilerContract
    assert inspect.signature(ReferenceContract) == inspect.signature(CompilerContract)
    value = ReferenceContract('tensor.custom', (), 'Tensor', 'custom')
    assert not isinstance(value, CompilerContract)
    assert value != CompilerContract('tensor.custom', (), 'Tensor', 'custom')
    assert ReferenceContract.__module__ == 'frontend.tensor.runtime'


def test_compiler_imports_are_lazy_but_public_exports_remain_available():
    import subprocess
    import sys

    code = '''
import sys
from frontend.tensor.contracts import tensor_function_contracts
from frontend.language_surface import parse, compile_program
from toolchain.tensor_manifest import build_manifest
assert tensor_function_contracts()
compile_program(parse("""module M {
 calculation X {
  result = 1
 }
}"""))
assert build_manifest()['function_count'] > 0
assert 'frontend.tensor.runtime' not in sys.modules
import frontend.tensor as api
assert set(api.__all__) <= set(dir(api))
namespace = {}
exec('from frontend.tensor import *', namespace)
from frontend.tensor import runtime
for name in api.__all__:
    assert namespace[name] is getattr(runtime, name)
    assert getattr(api, name) is namespace[name]
import importlib
old_policy = api.TensorPolicy
importlib.reload(runtime)
assert runtime.TensorPolicy is not old_policy
importlib.reload(api)
assert api.TensorPolicy is runtime.TensorPolicy
try:
    api.missing_public_name
except AttributeError as error:
    assert str(error) == "module 'frontend.tensor' has no attribute 'missing_public_name'"
else:
    raise AssertionError('unknown attribute must fail')
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=REPO_ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
