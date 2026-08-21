from __future__ import annotations

import json
from pathlib import Path

import pytest

from frontend.integrated_computation_runtime import execute_program
from frontend.language_surface import parse
from frontend.tensor import TensorError, TensorRuntime
from toolchain.tensor_cmd import run as tensor_command


def test_slice_gather_and_stateless_random_are_deterministic() -> None:
    runtime = TensorRuntime()
    value = runtime.call(
        "tensor.create",
        [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
    )
    indexes = runtime.call("tensor.create", [2, 0], "i64")

    sliced = runtime.call("tensor.slice", value, [1], [3], [0], [1])
    gathered = runtime.call("tensor.gather", value, indexes, 0)
    first = runtime.call(
        "tensor.random_normal", [4], 0.0, 1.0, 42, 7, "f64"
    )
    second = runtime.call(
        "tensor.random_normal", [4], 0.0, 1.0, 42, 7, "f64"
    )
    changed = runtime.call(
        "tensor.random_normal", [4], 0.0, 1.0, 42, 8, "f64"
    )

    assert runtime.to_array(sliced) == [[3.0, 4.0], [5.0, 6.0]]
    assert runtime.to_array(gathered) == [[5.0, 6.0], [1.0, 2.0]]
    assert runtime.to_array(first) == runtime.to_array(second)
    assert runtime.to_array(first) != runtime.to_array(changed)


def test_rstensor_round_trip_capabilities_and_checksum(tmp_path: Path) -> None:
    denied = TensorRuntime(resource_root=tmp_path)
    value = denied.create([[1.0, 2.0]], "f32")
    with pytest.raises(TensorError, match="filesystem_write"):
        denied.call("tensor.save", value, "weights.rstensor")

    writer = TensorRuntime(
        resource_root=tmp_path,
        filesystem_read=True,
        filesystem_write=True,
    )
    value = writer.create([[1.0, 2.0]], "f32")
    receipt = writer.call("tensor.save", value, "weights.rstensor")
    loaded = writer.call("tensor.load", "weights.rstensor")

    assert receipt["profile"] == "reasonscript-tensor-file/1.0"
    assert loaded.shape == (1, 2)
    assert loaded.dtype == "f32"
    assert writer.to_array(loaded) == [[1.0, 2.0]]

    path = tmp_path / "weights.rstensor"
    corrupted = bytearray(path.read_bytes())
    corrupted[-1] ^= 1
    path.write_bytes(corrupted)
    with pytest.raises(TensorError, match="checksum"):
        writer.call("tensor.load", "weights.rstensor")


def test_reverse_mode_autograd_handles_broadcast_matmul_and_gather() -> None:
    runtime = TensorRuntime()
    weight = runtime.call(
        "tensor.parameter",
        runtime.call("tensor.create", [[1.0], [2.0]], "f64"),
    )
    bias = runtime.call(
        "tensor.parameter",
        runtime.call("tensor.create", [0.5], "f64"),
    )
    input_value = runtime.call(
        "tensor.create", [[3.0, 4.0], [5.0, 6.0]], "f64"
    )
    prediction = runtime.call("tensor.linear", input_value, weight, bias)
    loss = runtime.call("tensor.mean", prediction)
    weight_grad, bias_grad = runtime.call("tensor.grad", loss, [weight, bias])

    assert runtime.to_array(weight_grad) == [[4.0], [5.0]]
    assert runtime.to_array(bias_grad) == [1.0]
    assert runtime._grad_nodes == {}
    assert runtime._autograd_roots == set()

    source = runtime.call(
        "tensor.parameter",
        runtime.call("tensor.create", [10.0, 20.0, 30.0], "f64"),
    )
    indexes = runtime.call("tensor.create", [2, 0, 2], "i64")
    selected = runtime.call("tensor.gather", source, indexes, 0)
    selected_loss = runtime.call("tensor.sum", selected)
    source_grad = runtime.call("tensor.grad", selected_loss, [source])[0]
    assert runtime.to_array(source_grad) == [1.0, 0.0, 2.0]

    sliced = runtime.call("tensor.slice", source, [1], [3], [0], [1])
    sliced_loss = runtime.call("tensor.sum", sliced)
    sliced_grad = runtime.call("tensor.grad", sliced_loss, [source])[0]
    assert runtime.to_array(sliced_grad) == [0.0, 1.0, 1.0]


def test_autograd_matches_finite_difference_for_nonlinear_linear_chain() -> None:
    runtime = TensorRuntime()
    input_value = runtime.call("tensor.create", [[2.0, -1.0]], "f64")
    weight = runtime.call(
        "tensor.parameter",
        runtime.call("tensor.create", [[0.25], [-0.5]], "f64"),
    )
    prediction = runtime.call("tensor.matmul", input_value, weight)
    loss = runtime.call("tensor.mean", runtime.call("tensor.power", prediction, 2.0))
    analytic = runtime.to_array(runtime.call("tensor.grad", loss, [weight])[0])

    def evaluate(values: list[list[float]]) -> float:
        reference = TensorRuntime()
        x = reference.create([[2.0, -1.0]], "f64")
        w = reference.create(values, "f64")
        y = reference.matmul(x, w)
        return reference.scalar(reference.mean(reference.power(y, 2.0)))

    epsilon = 1e-6
    numeric = []
    initial = [[0.25], [-0.5]]
    for row in range(2):
        plus = [item[:] for item in initial]
        minus = [item[:] for item in initial]
        plus[row][0] += epsilon
        minus[row][0] -= epsilon
        numeric.append([(evaluate(plus) - evaluate(minus)) / (2 * epsilon)])

    assert analytic[0][0] == pytest.approx(numeric[0][0], abs=1e-6)
    assert analytic[1][0] == pytest.approx(numeric[1][0], abs=1e-6)


def test_autograd_preserves_keyword_operation_attributes() -> None:
    runtime = TensorRuntime()
    parameter = runtime.call(
        "tensor.parameter",
        runtime.call("tensor.create", [[1.0, 2.0], [3.0, 4.0]], "f64"),
    )
    reduced = runtime.call(
        "tensor.mean", parameter, axis=[0, 1], keep_dims=False
    )
    gradient = runtime.call("tensor.grad", reduced, [parameter])[0]
    assert runtime.to_array(gradient) == [[0.25, 0.25], [0.25, 0.25]]


def test_conv2d_pooling_and_spatial_gradients() -> None:
    runtime = TensorRuntime()
    input_value = runtime.call(
        "tensor.parameter",
        runtime.call(
            "tensor.create",
            [[[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]]],
            "f64",
        ),
    )
    weight = runtime.call(
        "tensor.parameter",
        runtime.call(
            "tensor.create",
            [[[[1.0, 0.0], [0.0, -1.0]]]],
            "f64",
        ),
    )
    convolved = runtime.call(
        "tensor.conv2d",
        input_value,
        weight,
        None,
        [1, 1],
        [0, 0],
        [1, 1],
        1,
    )
    pooled = runtime.call(
        "tensor.max_pool2d", convolved, [2, 2], [1, 1], [0, 0]
    )
    loss = runtime.call("tensor.sum", pooled)
    input_grad, weight_grad = runtime.call(
        "tensor.grad", loss, [input_value, weight]
    )

    assert runtime.to_array(convolved) == [[[[-4.0, -4.0], [-4.0, -4.0]]]]
    assert runtime.to_array(pooled) == [[[[-4.0]]]]
    assert runtime.to_array(weight_grad) == [[[[1.0, 2.0], [4.0, 5.0]]]]
    assert runtime.to_array(input_grad) == [
        [[[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 0.0]]]
    ]

    averaged = runtime.call(
        "tensor.avg_pool2d", input_value, [2, 2], [1, 1], [0, 0], False
    )
    average_loss = runtime.call("tensor.sum", averaged)
    average_grad = runtime.call("tensor.grad", average_loss, [input_value])[0]
    assert runtime.to_array(averaged) == [[[[3.0, 4.0], [6.0, 7.0]]]]
    assert runtime.to_array(average_grad) == [
        [[[0.25, 0.5, 0.25], [0.5, 1.0, 0.5], [0.25, 0.5, 0.25]]]
    ]


def test_reason_source_can_load_train_differentiate_and_save(
    tmp_path: Path,
) -> None:
    writer = TensorRuntime(resource_root=tmp_path, filesystem_write=True)
    images = writer.create([[[[1.0, 2.0], [3.0, 4.0]]]], "f64")
    writer.save(images, "images.rstensor")
    program = parse(
        """module FileBackedTraining {
  calculation Answer {
    let input = tensor.load("images.rstensor")
    let initial = tensor.random_normal([1, 1, 1, 1], 0.0, 0.1, 42, 0, "f64")
    let weight = tensor.parameter(initial)
    let output = tensor.conv2d(input, weight)
    let loss = tensor.mean(output)
    let gradients = tensor.grad(loss, [weight])
    let receipt = tensor.save(gradients[0], "gradient.rstensor")
    result = receipt
  }
}
"""
    )

    result = execute_program(
        program,
        resource_root=tmp_path,
        filesystem_read=True,
        filesystem_write=True,
    ).to_dict()["result"]

    assert result["profile"] == "reasonscript-tensor-file/1.0"
    assert (tmp_path / "gradient.rstensor").is_file()


def test_reason_training_loop_releases_each_autograd_tape() -> None:
    program = parse(
        """module IterativeAutograd {
  calculation Answer {
    let iteration = 0
    let input = tensor.create([1.0], "f64")
    let weight = tensor.parameter(tensor.create([1.0], "f64"))
    while iteration < 20 {
      let prediction = tensor.multiply(input, weight)
      let loss = tensor.mean(tensor.power(prediction, 2.0))
      let gradients = tensor.grad(loss, [weight])
      let updated = tensor.subtract(weight, tensor.multiply(gradients[0], 0.1))
      weight = tensor.parameter(tensor.detach(updated))
      iteration = iteration + 1
    }
    result = weight
  }
}
"""
    )

    executed = execute_program(program)

    assert executed.to_dict()["result"][0] == pytest.approx(0.8**20)
    assert executed.runtime._grad_nodes == {}
    assert executed.runtime._autograd_roots == set()
    assert len(executed.runtime._refs) == 1


def test_tensor_grad_temporary_survives_sibling_user_function_arguments() -> None:
    program = parse(
        """module TensorTemporaryLifetime {
  fn identity(value: Tensor) -> Tensor {
    let marker = 1
    return value
  }
  fn consume(value: Tensor) -> Tensor {
    let marker = 1
    return value
  }
  calculation Answer {
    let parameter = tensor.parameter(tensor.create([2.0], "f64"))
    let loss = tensor.sum(tensor.multiply(parameter, parameter))
    result = tensor.add(identity(tensor.grad(loss, [parameter])[0]), consume(parameter))
  }
}
"""
    )

    result = execute_program(program).to_dict()

    assert result["result"] == [6.0]


def test_tensor_cli_import_inspect_and_verify(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "values.json"
    source.write_text(
        json.dumps({"values": [[1.0, 2.0]], "dtype": "f32"}),
        encoding="utf-8",
    )
    target = tmp_path / "values.rstensor"

    assert tensor_command(
        [
            "import",
            "--from",
            "json",
            "--input",
            str(source),
            "--output",
            str(target),
            "--json",
        ],
        tmp_path,
    ) == 0
    capsys.readouterr()
    assert tensor_command(["inspect", str(target), "--json"], tmp_path) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["shape"] == [1, 2]
    assert inspected["dtype"] == "f32"
    assert tensor_command(["verify", str(target), "--json"], tmp_path) == 0
