from frontend.tensor.runtime import TensorRuntime


def test_planned_tensor_is_released_after_its_last_use():
    runtime = TensorRuntime()
    first = runtime.execute_planned(
        {"function": "tensor.create", "execution_order": 1, "output_ref": "first", "dependencies": [], "release_after": [], "ref_count": 1},
        [1, 2],
    )
    runtime.execute_planned(
        {"function": "tensor.add", "execution_order": 2, "output_ref": "second", "dependencies": ["first"], "release_after": ["first"], "ref_count": 0},
        first,
        1,
    )
    assert runtime.lifetime_metrics()["tensor_releases"] == 1
    assert runtime.lifetime_metrics()["live_tensors"] == 1
