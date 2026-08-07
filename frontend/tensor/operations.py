"""Dependency-free declarative Tensor operation signatures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TensorOperationSignature:
    arguments: tuple[str, ...]
    required: int

    @property
    def limits(self) -> tuple[int, int]:
        return self.required, len(self.arguments)


SIGNATURES = {
    "tensor.create": TensorOperationSignature(("values", "dtype", "device"), 1),
    "tensor.relu": TensorOperationSignature(("input",), 1),
    "tensor.softmax": TensorOperationSignature(("input", "axis"), 1),
    "tensor.linear": TensorOperationSignature(("input", "weight", "bias"), 2),
    "tensor.reshape": TensorOperationSignature(("value", "shape"), 2),
    "tensor.transpose": TensorOperationSignature(("value", "axis_a", "axis_b"), 1),
    "tensor.matmul": TensorOperationSignature(("left", "right"), 2),
    "tensor.slice": TensorOperationSignature(
        ("value", "starts", "ends", "axes", "steps"), 3
    ),
    "tensor.narrow": TensorOperationSignature(
        ("value", "axis", "start", "length"), 4
    ),
    "tensor.gather": TensorOperationSignature(("value", "indices", "axis"), 2),
    "tensor.random_uniform": TensorOperationSignature(
        ("shape", "low", "high", "seed", "stream", "dtype"), 1
    ),
    "tensor.random_normal": TensorOperationSignature(
        ("shape", "mean", "std", "seed", "stream", "dtype"), 1
    ),
    "tensor.random_bernoulli": TensorOperationSignature(
        ("shape", "probability", "seed", "stream"), 1
    ),
    "tensor.random_permutation": TensorOperationSignature(
        ("size", "seed", "stream"), 1
    ),
    "tensor.load": TensorOperationSignature(("path",), 1),
    "tensor.save": TensorOperationSignature(("value", "path", "overwrite"), 2),
    "tensor.parameter": TensorOperationSignature(("value",), 1),
    "tensor.detach": TensorOperationSignature(("value",), 1),
    "tensor.requires_grad": TensorOperationSignature(("value",), 1),
    "tensor.grad": TensorOperationSignature(("loss", "parameters"), 2),
    "tensor.conv2d": TensorOperationSignature(
        (
            "input",
            "weight",
            "bias",
            "stride",
            "padding",
            "dilation",
            "groups",
        ),
        2,
    ),
    "tensor.max_pool2d": TensorOperationSignature(
        ("input", "kernel", "stride", "padding"), 2
    ),
    "tensor.avg_pool2d": TensorOperationSignature(
        ("input", "kernel", "stride", "padding", "count_include_pad"), 2
    ),
}


def operation_signature(function_id: str) -> TensorOperationSignature | None:
    return SIGNATURES.get(function_id)
