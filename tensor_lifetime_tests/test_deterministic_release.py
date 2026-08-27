from frontend.tensor.runtime import TensorRuntime


def test_temporary_tensor_is_explicitly_released_and_traced():
    runtime = TensorRuntime()
    value = runtime.create([1.0])
    assert runtime.release(value)
    assert value.tensor_id not in runtime._refs
    assert runtime.lifecycle_trace[-1]["operation_type"] == "tensor_release"


def test_persistent_values_are_not_released_by_collection():
    runtime = TensorRuntime()
    value = runtime.classify(runtime.create([1.0]), "Persistent")
    assert runtime.collect() == 0
    assert value.tensor_id in runtime._refs
