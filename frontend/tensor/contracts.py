"""Backend-neutral Tensor Standard Function contracts.

This module is safe for compiler and manifest tooling to import. It contains no
Python Tensor evaluator and constructs no runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DTYPES = frozenset({"bool", "i32", "i64", "f32", "f64"})


@dataclass(frozen=True)
class TensorFunctionContract:
    function_id: str
    inputs: tuple[str, ...]
    output: str
    shape_policy: str
    dtype_policy: str = "promote"
    version: str = "0.1"
    deterministic: bool = True
    side_effects: bool = False
    device_policy: str = "cpu"
    broadcasting_policy: str = "numpy"
    backend_policy: str = "abstract"
    diagnostic_policy: str = "TSF"
    artifact_policy: str = "metadata_only"
    argument_contract: tuple[dict[str, Any], ...] = ()
    return_contract: dict[str, Any] = field(default_factory=dict)
    backend_operation: str | None = None
    lowering_policy: str = "native"

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_id": self.function_id,
            "qualified_name": self.function_id,
            "namespace": "tensor",
            "name": self.function_id.split(".", 1)[1],
            "version": self.version,
            "inputs": list(self.inputs),
            "output": self.output,
            "shape_policy": self.shape_policy,
            "dtype_policy": self.dtype_policy,
            "device_policy": self.device_policy,
            "broadcasting_policy": self.broadcasting_policy,
            "deterministic": self.deterministic,
            "side_effects": self.side_effects,
            "backend": self.backend_policy,
            "diagnostic_policy": self.diagnostic_policy,
            "artifact_policy": self.artifact_policy,
            "callable": True,
            "argument_contract": list(self.argument_contract),
            "return_contract": dict(self.return_contract),
            "backend_operation": self.backend_operation or self.function_id.split(".", 1)[1],
            "lowering_policy": self.lowering_policy,
        }


def tensor_function_contracts() -> dict[str, TensorFunctionContract]:
    v02 = {
        "slice", "narrow", "gather", "random_uniform", "random_normal",
        "random_bernoulli", "random_permutation", "load", "save",
        "parameter", "detach", "requires_grad", "grad", "conv2d",
        "max_pool2d", "avg_pool2d",
    }
    groups = {
        "creation": "create zeros ones full",
        "random": "random_uniform random_normal random_bernoulli random_permutation",
        "inspection": "shape rank size dtype dimension",
        "shape": "reshape flatten transpose squeeze unsqueeze concat stack slice narrow gather",
        "broadcast": "add subtract multiply divide power maximum minimum equal not_equal greater greater_equal less less_equal",
        "elementwise": "negate abs exp log sqrt",
        "reduction": "sum mean min max argmax argmin",
        "linear_algebra": "dot matmul norm",
        "inference": "relu softmax linear conv2d max_pool2d avg_pool2d",
        "autograd": "parameter detach requires_grad grad",
        "io": "load save",
        "conversion": "cast to_array scalar",
    }
    result: dict[str, TensorFunctionContract] = {}
    for policy, names in groups.items():
        for name in names.split():
            function_id = f"tensor.{name}"
            result[function_id] = TensorFunctionContract(
                function_id=function_id,
                inputs=("data_or_shape",) if name in {"create", "zeros", "ones", "full"} else ("value",),
                output=_contract_output(name),
                shape_policy=policy,
                version="0.2" if name in v02 else "0.1",
                side_effects=name in {"load", "save"},
                diagnostic_policy=(
                    "TIO" if name in {"load", "save"} else
                    "RNG" if name.startswith("random_") else
                    "AD" if name in {"parameter", "detach", "requires_grad", "grad"} else "TSF"
                ),
                argument_contract=_argument_contract(name),
                return_contract=_return_contract(name),
                backend_operation=name,
                lowering_policy="primitive_or_native" if name in {
                    "relu", "softmax", "linear", "conv2d", "max_pool2d", "avg_pool2d"
                } else "native",
            )
    return result


def _contract_output(name: str) -> str:
    if name == "grad": return "Array<Tensor>"
    if name == "requires_grad": return "Bool"
    if name == "save": return "TensorArtifactReceipt"
    if name == "shape": return "Array<Int>"
    if name in {"rank", "size", "dimension"}: return "Int"
    if name == "dtype": return "String"
    if name == "scalar": return "Scalar"
    if name == "to_array": return "Array"
    return "Tensor"


def _return_contract(name: str) -> dict[str, Any]:
    output = _contract_output(name)
    if output == "Tensor": return {"kind": "tensor", "shape": "inferred", "dtype": "inferred"}
    if output == "Array<Tensor>": return {"kind": "array", "element_kind": "tensor"}
    return {"kind": output.lower()}


def _argument_contract(name: str) -> tuple[dict[str, Any], ...]:
    if name == "create":
        return (
            {"name": "values", "kind": "nested_numeric", "required": True},
            {"name": "dtype", "kind": "dtype", "required": False},
            {"name": "device", "kind": "string", "required": False},
        )
    if name == "softmax":
        return ({"name": "input", "kind": "tensor", "required": True}, {"name": "axis", "kind": "int", "required": False, "default": -1})
    if name == "linear":
        return ({"name": "input", "kind": "tensor", "required": True}, {"name": "weight", "kind": "tensor", "required": True}, {"name": "bias", "kind": "tensor", "required": False})
    if name == "relu":
        return ({"name": "input", "kind": "tensor", "required": True},)
    if name == "conv2d":
        return (
            {"name": "input", "kind": "tensor", "required": True},
            {"name": "weight", "kind": "tensor", "required": True},
            {"name": "bias", "kind": "tensor", "required": False},
            {"name": "stride", "kind": "shape2", "required": False},
            {"name": "padding", "kind": "shape2", "required": False},
            {"name": "dilation", "kind": "shape2", "required": False},
            {"name": "groups", "kind": "int", "required": False},
        )
    if name in {"max_pool2d", "avg_pool2d"}:
        result = [
            {"name": "input", "kind": "tensor", "required": True},
            {"name": "kernel", "kind": "shape2", "required": True},
            {"name": "stride", "kind": "shape2", "required": False},
            {"name": "padding", "kind": "shape2", "required": False},
        ]
        if name == "avg_pool2d":
            result.append({"name": "count_include_pad", "kind": "bool", "required": False})
        return tuple(result)
    if name == "grad":
        return ({"name": "loss", "kind": "tensor", "required": True}, {"name": "parameters", "kind": "tensor_array", "required": True})
    return ()
