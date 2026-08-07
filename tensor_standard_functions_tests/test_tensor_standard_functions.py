from pathlib import Path

import pytest

from frontend.tensor import TensorError, TensorPolicy, TensorRuntime


def test_registry_contains_complete_required_set():
    runtime = TensorRuntime()
    assert len(runtime.function_ids()) == 65
    assert "tensor.create" in runtime.function_ids()
    assert "tensor.matmul" in runtime.function_ids()
    assert {
        "tensor.relu",
        "tensor.softmax",
        "tensor.linear",
        "tensor.conv2d",
        "tensor.max_pool2d",
        "tensor.avg_pool2d",
        "tensor.grad",
        "tensor.load",
        "tensor.save",
    } <= set(runtime.function_ids())
    assert {contract.version for contract in runtime.contracts.values()} == {
        "0.1",
        "0.2",
    }
    assert all(contract.deterministic for contract in runtime.contracts.values())
    assert {
        name
        for name, contract in runtime.contracts.items()
        if contract.side_effects
    } == {"tensor.load", "tensor.save"}


def test_create_metadata_and_external_runtime_value():
    runtime = TensorRuntime()
    value = runtime.call("tensor.create", [[1, 2], [3, 4]], dtype="f32")
    assert value.metadata() == {
        "tensor_id": "tensor_0001",
        "shape": [2, 2],
        "rank": 2,
        "dtype": "f32",
        "device": "cpu",
        "backend": "python",
        "storage_ref": "runtime://tensor/tensor_0001",
        "lifecycle": "available",
    }
    assert value.runtime_value()["value_kind"] == "external"
    assert runtime.call("tensor.to_array", value) == [[1.0, 2.0], [3.0, 4.0]]


def test_creation_inspection_shape_operations():
    runtime = TensorRuntime()
    value = runtime.create([[1, 2, 3], [4, 5, 6]])
    assert runtime.shape(value) == [2, 3]
    assert runtime.rank(value) == 2
    assert runtime.size(value) == 6
    assert runtime.dimension(value, -1) == 3
    assert runtime.to_array(runtime.reshape(value, [3, -1])) == [[1, 2], [3, 4], [5, 6]]
    assert runtime.shape(runtime.flatten(value)) == [6]
    assert runtime.to_array(runtime.transpose(value, 0, 1)) == [[1, 4], [2, 5], [3, 6]]
    assert runtime.shape(runtime.squeeze(runtime.unsqueeze(value, -1))) == [2, 3]
    assert runtime.shape(runtime.concat([value, value], 0)) == [4, 3]
    assert runtime.shape(runtime.stack([value, value], 0)) == [2, 2, 3]


def test_elementwise_broadcast_comparison_and_reductions():
    runtime = TensorRuntime()
    matrix = runtime.create([[1.0, 2.0], [3.0, 4.0]])
    vector = runtime.create([10.0, 20.0])
    assert runtime.to_array(runtime.add(matrix, vector)) == [[11.0, 22.0], [13.0, 24.0]]
    assert runtime.to_array(runtime.multiply(matrix, 2)) == [[2.0, 4.0], [6.0, 8.0]]
    assert runtime.to_array(runtime.greater(matrix, 2)) == [
        [False, False],
        [True, True],
    ]
    assert runtime.to_array(runtime.sum(matrix, axis=0)) == [4.0, 6.0]
    assert runtime.to_array(runtime.mean(matrix, axis=-1, keep_dims=True)) == [
        [1.5],
        [3.5],
    ]
    assert runtime.scalar(runtime.max(matrix)) == 4.0
    assert runtime.scalar(runtime.argmax(matrix)) == 3


def test_linear_algebra_and_nn_forward_trace():
    runtime = TensorRuntime()
    inputs = runtime.call("tensor.create", [[1.0, -2.0]])
    w1 = runtime.call("tensor.create", [[1.0, 2.0], [3.0, 1.0]])
    b1 = runtime.call("tensor.create", [0.0, 1.0])
    w2 = runtime.call("tensor.create", [[2.0], [1.0]])
    hidden = runtime.call("tensor.add", runtime.call("tensor.matmul", inputs, w1), b1)
    relu = runtime.call("tensor.maximum", hidden, 0.0)
    output = runtime.call("tensor.matmul", relu, w2)
    assert runtime.to_array(output) == [[1.0]]
    plan = runtime.execution_plan()
    assert [step["function_id"] for step in plan[-4:]] == [
        "tensor.matmul",
        "tensor.add",
        "tensor.maximum",
        "tensor.matmul",
    ]
    assert plan[-1]["output"]["shape"] == [1, 1]


def test_softmax_composition_is_stable_and_deterministic():
    def softmax(runtime, value):
        maximum = runtime.max(value, axis=-1, keep_dims=True)
        shifted = runtime.subtract(value, maximum)
        exponential = runtime.exp(shifted)
        return runtime.divide(
            exponential, runtime.sum(exponential, axis=-1, keep_dims=True)
        )

    first, second = TensorRuntime(), TensorRuntime()
    left = softmax(first, first.create([[1000.0, 1001.0]]))
    right = softmax(second, second.create([[1000.0, 1001.0]]))
    assert first.to_array(left) == second.to_array(right)
    assert sum(first.to_array(left)[0]) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "action,code",
    [
        (lambda runtime: runtime.create([[1], [2, 3]]), "TSF-017"),
        (lambda runtime: runtime.reshape(runtime.create([1, 2]), [3]), "TSF-007"),
        (
            lambda runtime: runtime.matmul(
                runtime.create([[1, 2]]), runtime.create([[1, 2]])
            ),
            "TSF-008",
        ),
        (lambda runtime: runtime.dimension(runtime.create([1]), 2), "TSF-005"),
        (
            lambda runtime: runtime.add(
                runtime.create([1, 2]), runtime.create([1, 2, 3])
            ),
            "TSF-006",
        ),
    ],
)
def test_required_diagnostics(action, code):
    with pytest.raises(TensorError) as error:
        action(TensorRuntime())
    assert error.value.diagnostic.code == code


def test_artifact_inline_and_external_storage(tmp_path: Path):
    runtime = TensorRuntime(policy=TensorPolicy(inline_elements=2))
    small = runtime.create([1, 2])
    large = runtime.create([1, 2, 3])
    assert runtime.artifact(small, tmp_path)["inline_data"] == [1, 2]
    metadata = runtime.artifact(large, tmp_path)
    assert metadata["checksum"].startswith("sha256:")
    assert Path(metadata["storage_ref"]).exists()
    assert metadata["byte_size"] > 0


def test_trace_has_backend_independent_tensor_metadata():
    runtime = TensorRuntime()
    result = runtime.call("tensor.add", runtime.create([1.0]), 2.0)
    entry = runtime.trace[-1]
    assert entry["output"] == {
        "tensor_id": result.tensor_id,
        "shape": [1],
        "dtype": "f64",
        "device": "cpu",
        "backend": "python",
    }


def test_backend_failures_and_resource_limits_are_normalized(tmp_path: Path):
    runtime = TensorRuntime(policy=TensorPolicy(max_shape_dimension=2))
    with pytest.raises(TensorError) as shape_error:
        runtime.zeros([3])
    assert shape_error.value.diagnostic.code == "TSF-003"

    runtime = TensorRuntime(
        policy=TensorPolicy(inline_elements=0, max_artifact_bytes=2)
    )
    value = runtime.create([123])
    with pytest.raises(TensorError) as artifact_error:
        runtime.artifact(value, tmp_path)
    assert artifact_error.value.diagnostic.code == "TSF-020"

    with pytest.raises(TensorError) as backend_error:
        runtime.call("tensor.divide", value, 0)
    assert backend_error.value.diagnostic.code == "TSF-012"
