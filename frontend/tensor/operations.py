"""Dependency-free declarative Tensor operation signatures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TensorOperationSignature:
    arguments: tuple[str, ...]
    required: int
    defaults: tuple[tuple[str, object], ...] = ()

    @property
    def limits(self) -> tuple[int, int]:
        return self.required, len(self.arguments)

    def default_for(self, argument: str) -> object:
        for name, value in self.defaults:
            if name == argument:
                return value
        raise KeyError(argument)


SIGNATURES = {
    "tensor.create": TensorOperationSignature(("values", "dtype", "device"), 1, (("dtype", None), ("device", "cpu"))),
    "tensor.relu": TensorOperationSignature(("input",), 1),
    "tensor.softmax": TensorOperationSignature(("input", "axis"), 1, (("axis", -1),)),
    "tensor.linear": TensorOperationSignature(("input", "weight", "bias"), 2, (("bias", None),)),
    "tensor.reshape": TensorOperationSignature(("value", "shape"), 2),
    "tensor.transpose": TensorOperationSignature(("value", "axis_a", "axis_b"), 1, (("axis_a", 0), ("axis_b", 1))),
    "tensor.matmul": TensorOperationSignature(("left", "right"), 2),
    "tensor.slice": TensorOperationSignature(
        ("value", "starts", "ends", "axes", "steps"), 3, (("axes", None), ("steps", None))
    ),
    "tensor.narrow": TensorOperationSignature(
        ("value", "axis", "start", "length"), 4
    ),
    "tensor.gather": TensorOperationSignature(("value", "indices", "axis"), 2, (("axis", 0),)),
    "tensor.random_uniform": TensorOperationSignature(
        ("shape", "low", "high", "seed", "stream", "dtype"), 1,
        (("low", 0.0), ("high", 1.0), ("seed", 0), ("stream", 0), ("dtype", "f32")),
    ),
    "tensor.random_normal": TensorOperationSignature(
        ("shape", "mean", "std", "seed", "stream", "dtype"), 1,
        (("mean", 0.0), ("std", 1.0), ("seed", 0), ("stream", 0), ("dtype", "f32")),
    ),
    "tensor.random_bernoulli": TensorOperationSignature(
        ("shape", "probability", "seed", "stream"), 1,
        (("probability", 0.5), ("seed", 0), ("stream", 0))
    ),
    "tensor.random_permutation": TensorOperationSignature(
        ("size", "seed", "stream"), 1, (("seed", 0), ("stream", 0))
    ),
    "tensor.load": TensorOperationSignature(("path",), 1),
    "tensor.save": TensorOperationSignature(("value", "path", "overwrite"), 2, (("overwrite", False),)),
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
        ), 2,
        (("bias", None), ("stride", (1, 1)), ("padding", (0, 0)), ("dilation", (1, 1)), ("groups", 1)),
    ),
    "tensor.max_pool2d": TensorOperationSignature(
        ("input", "kernel", "stride", "padding"), 2,
        (("stride", None), ("padding", (0, 0)))
    ),
    "tensor.avg_pool2d": TensorOperationSignature(
        ("input", "kernel", "stride", "padding", "count_include_pad"), 2,
        (("stride", None), ("padding", (0, 0)), ("count_include_pad", False))
    ),
}


def operation_signature(function_id: str) -> TensorOperationSignature | None:
    return SIGNATURES.get(function_id)
