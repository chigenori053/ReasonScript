from frontend.tensor import TensorRuntime


def test_ops_on_parameters_inside_no_grad_record_no_autograd_nodes():
    runtime = TensorRuntime()
    weight = runtime.call(
        "tensor.parameter", runtime.call("tensor.create", [1.0, 2.0], dtype="f64")
    )
    other = runtime.call("tensor.create", [3.0, 4.0], dtype="f64")

    with runtime.no_grad():
        runtime.call("tensor.add", weight, other)
        runtime.call("tensor.multiply", weight, other)

    assert runtime._grad_nodes == {}
    assert runtime._autograd_roots == set()


def test_no_grad_does_not_affect_calls_outside_the_block():
    runtime = TensorRuntime()
    weight = runtime.call(
        "tensor.parameter", runtime.call("tensor.create", [1.0, 2.0], dtype="f64")
    )
    other = runtime.call("tensor.create", [3.0, 4.0], dtype="f64")

    with runtime.no_grad():
        runtime.call("tensor.add", weight, other)
    assert runtime._grad_nodes == {}

    runtime.call("tensor.multiply", weight, other)
    assert runtime._grad_nodes != {}


def test_no_grad_nests_safely():
    runtime = TensorRuntime()
    weight = runtime.call(
        "tensor.parameter", runtime.call("tensor.create", [1.0, 2.0], dtype="f64")
    )
    other = runtime.call("tensor.create", [3.0, 4.0], dtype="f64")

    with runtime.no_grad():
        with runtime.no_grad():
            runtime.call("tensor.add", weight, other)
        # still inside the outer no_grad block
        runtime.call("tensor.multiply", weight, other)
    assert runtime._grad_nodes == {}

    runtime.call("tensor.subtract", weight, other)
    assert runtime._grad_nodes != {}
