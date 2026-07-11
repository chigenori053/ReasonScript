"""Backend-independent Tensor standard-function layer.

The runtime core only sees :class:`TensorValueRef`; storage and numeric work stay
behind the backend adapter.  The reference backend intentionally uses Python's
standard library so Tensor support remains optional for existing installations.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

DTYPES = {"bool", "i32", "i64", "f32", "f64"}
DTYPE_BYTES = {"bool": 1, "i32": 4, "i64": 8, "f32": 4, "f64": 8}


@dataclass(frozen=True)
class TensorDiagnostic:
    code: str
    message: str
    category: str = "tensor.runtime"
    severity: str = "error"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "details": self.details,
        }


class TensorError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        category: str = "tensor.runtime",
        **details: Any,
    ):
        self.diagnostic = TensorDiagnostic(code, message, category, details=details)
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class TensorPolicy:
    max_rank: int = 8
    max_elements: int = 10_000_000
    max_tensor_bytes: int = 256 * 1024 * 1024
    max_live_tensors: int = 1_000
    max_shape_dimension: int = 10_000_000
    max_artifact_bytes: int = 256 * 1024 * 1024
    inline_elements: int = 256


@dataclass(frozen=True)
class TensorValueRef:
    tensor_id: str
    shape: tuple[int, ...]
    dtype: str
    device: str
    backend: str
    storage_ref: str
    lifecycle: str = "available"

    @property
    def rank(self) -> int:
        return len(self.shape)

    def metadata(self) -> dict[str, Any]:
        return {
            "tensor_id": self.tensor_id,
            "shape": list(self.shape),
            "rank": self.rank,
            "dtype": self.dtype,
            "device": self.device,
            "backend": self.backend,
            "storage_ref": self.storage_ref,
            "lifecycle": self.lifecycle,
        }

    def runtime_value(self) -> dict[str, Any]:
        return {
            "value_kind": "external",
            "external_type": "tensor",
            "value_id": self.tensor_id,
            "metadata": {
                key: value
                for key, value in self.metadata().items()
                if key != "tensor_id"
            },
        }


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_id": self.function_id,
            "namespace": "tensor",
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
        }


@dataclass(frozen=True)
class _Tensor:
    shape: tuple[int, ...]
    dtype: str
    data: tuple[Any, ...]


class TensorBackend(Protocol):
    name: str

    def store(self, tensor_id: str, tensor: _Tensor) -> None: ...
    def load(self, tensor_id: str) -> _Tensor: ...
    def release(self, tensor_id: str) -> None: ...


class PythonTensorBackend:
    name = "python"

    def __init__(self) -> None:
        self._values: dict[str, _Tensor] = {}

    def store(self, tensor_id: str, tensor: _Tensor) -> None:
        self._values[tensor_id] = tensor

    def load(self, tensor_id: str) -> _Tensor:
        try:
            return self._values[tensor_id]
        except KeyError as error:
            raise TensorError(
                "TSF-018", "invalid Tensor value reference", tensor_id=tensor_id
            ) from error

    def release(self, tensor_id: str) -> None:
        self._values.pop(tensor_id, None)


def _product(shape: tuple[int, ...]) -> int:
    return math.prod(shape) if shape else 1


def _shape_and_flat(data: Any) -> tuple[tuple[int, ...], list[Any]]:
    if not isinstance(data, (list, tuple)):
        if not isinstance(data, (bool, int, float)):
            raise TensorError(
                "TSF-016", "Tensor data must be numeric, boolean, or an array"
            )
        return (), [data]
    if not data:
        return (0,), []
    children = [_shape_and_flat(value) for value in data]
    child_shape = children[0][0]
    if any(shape != child_shape for shape, _ in children[1:]):
        raise TensorError("TSF-017", "Tensor input array must be rectangular")
    return (len(data),) + child_shape, [
        item for _, values in children for item in values
    ]


def _infer_dtype(values: list[Any]) -> str:
    if all(isinstance(value, bool) for value in values):
        return "bool"
    if all(isinstance(value, (bool, int)) for value in values):
        return "i64"
    return "f64"


def _cast(value: Any, dtype: str) -> Any:
    try:
        if dtype == "bool":
            return bool(value)
        if dtype in {"i32", "i64"}:
            return int(value)
        return float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise TensorError("TSF-015", f"cannot cast value to {dtype}") from error


def _strides(shape: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(_product(shape[index + 1 :]) for index in range(len(shape)))


def _coords(index: int, shape: tuple[int, ...]) -> tuple[int, ...]:
    result = []
    for stride, dimension in zip(_strides(shape), shape):
        result.append((index // stride) % dimension if dimension else 0)
    return tuple(result)


def _flat_index(coords: tuple[int, ...], shape: tuple[int, ...]) -> int:
    return sum(coord * stride for coord, stride in zip(coords, _strides(shape)))


def _broadcast_shape(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[int, ...]:
    result = []
    for a, b in zip(reversed(left), reversed(right)):
        if a != b and a != 1 and b != 1:
            raise TensorError(
                "TSF-006",
                "Tensor shapes cannot be broadcast",
                left_shape=list(left),
                right_shape=list(right),
            )
        result.append(max(a, b))
    longer = left if len(left) > len(right) else right
    result.extend(reversed(longer[: abs(len(left) - len(right))]))
    return tuple(reversed(result))


def _broadcast_value(tensor: _Tensor, out_coords: tuple[int, ...]) -> Any:
    offset = len(out_coords) - len(tensor.shape)
    coords = tuple(
        0 if size == 1 else out_coords[offset + i]
        for i, size in enumerate(tensor.shape)
    )
    return tensor.data[_flat_index(coords, tensor.shape)]


def _normalize_axis(axis: int, rank: int, *, insertion: bool = False) -> int:
    limit = rank + 1 if insertion else rank
    if axis < 0:
        axis += limit
    if axis < 0 or axis >= limit:
        raise TensorError("TSF-005", "axis is out of range", axis=axis, rank=rank)
    return axis


class TensorRuntime:
    """Registry, adapter, trace, artifact, and lifecycle owner for one session."""

    def __init__(
        self, backend: TensorBackend | None = None, policy: TensorPolicy | None = None
    ):
        self.backend = backend or PythonTensorBackend()
        self.policy = policy or TensorPolicy()
        self._refs: dict[str, TensorValueRef] = {}
        self._next_id = 1
        self.trace: list[dict[str, Any]] = []
        self.contracts = _contracts()

    def function_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.contracts))

    def call(self, function_id: str, *args: Any, **kwargs: Any) -> Any:
        if function_id not in self.contracts:
            raise TensorError("TSF-012", f"unsupported Tensor function: {function_id}")
        method = getattr(self, function_id.split(".", 1)[1])
        started = time.perf_counter_ns()
        try:
            output = method(*args, **kwargs)
        except TensorError as error:
            self.trace.append(
                self._trace_entry(
                    function_id,
                    args,
                    None,
                    "error",
                    time.perf_counter_ns() - started,
                    [error.diagnostic.to_dict()],
                )
            )
            raise
        except Exception as error:
            normalized = TensorError(
                "TSF-013",
                "Tensor backend execution failed",
                function_id=function_id,
                backend=self.backend.name,
                error_type=type(error).__name__,
            )
            self.trace.append(
                self._trace_entry(
                    function_id,
                    args,
                    None,
                    "error",
                    time.perf_counter_ns() - started,
                    [normalized.diagnostic.to_dict()],
                )
            )
            raise normalized from error
        self.trace.append(
            self._trace_entry(
                function_id,
                args,
                output,
                "success",
                time.perf_counter_ns() - started,
                [],
            )
        )
        return output

    def _trace_entry(
        self,
        function_id: str,
        args: tuple[Any, ...],
        output: Any,
        status: str,
        duration_ns: int,
        diagnostics: list[dict[str, Any]],
    ) -> dict[str, Any]:
        def info(value: Any) -> Any:
            return (
                {
                    "tensor_id": value.tensor_id,
                    "shape": list(value.shape),
                    "dtype": value.dtype,
                    "device": value.device,
                    "backend": value.backend,
                }
                if isinstance(value, TensorValueRef)
                else value
            )

        return {
            "step_id": f"step_{len(self.trace)+1:04d}",
            "operation_type": "standard_function_call",
            "function_id": function_id,
            "inputs": [info(value) for value in args],
            "output": info(output),
            "duration_ns": duration_ns,
            "status": status,
            "diagnostics": diagnostics,
        }

    def _new(
        self, shape: tuple[int, ...], dtype: str, data: list[Any]
    ) -> TensorValueRef:
        self._validate_shape(shape, dtype)
        if len(self._refs) >= self.policy.max_live_tensors:
            raise TensorError("TSF-013", "maximum live Tensor count exceeded")
        tensor_id = f"tensor_{self._next_id:04d}"
        self._next_id += 1
        tensor = _Tensor(shape, dtype, tuple(_cast(value, dtype) for value in data))
        self.backend.store(tensor_id, tensor)
        ref = TensorValueRef(
            tensor_id,
            shape,
            dtype,
            "cpu",
            self.backend.name,
            f"runtime://tensor/{tensor_id}",
        )
        self._refs[tensor_id] = ref
        return ref

    def _validate_shape(self, shape: tuple[int, ...], dtype: str) -> None:
        if dtype not in DTYPES:
            raise TensorError("TSF-002", f"unsupported dtype: {dtype}")
        if len(shape) > self.policy.max_rank or any(
            type(value) is not int
            or value < 0
            or value > self.policy.max_shape_dimension
            for value in shape
        ):
            raise TensorError("TSF-003", "invalid Tensor shape", shape=list(shape))
        size = _product(shape)
        if (
            size > self.policy.max_elements
            or size * DTYPE_BYTES[dtype] > self.policy.max_tensor_bytes
        ):
            raise TensorError(
                "TSF-003", "Tensor shape exceeds resource policy", shape=list(shape)
            )

    def _tensor(self, value: TensorValueRef) -> _Tensor:
        if not isinstance(value, TensorValueRef):
            raise TensorError("TSF-001", "expected Tensor argument")
        if value.tensor_id not in self._refs:
            raise TensorError("TSF-018", "invalid Tensor value reference")
        if value.lifecycle == "released":
            raise TensorError("TSF-019", "Tensor value has been released")
        return self.backend.load(value.tensor_id)

    def _operand(self, value: Any, dtype: str | None = None) -> _Tensor:
        if isinstance(value, TensorValueRef):
            return self._tensor(value)
        shape, flat = _shape_and_flat(value)
        inferred = dtype or _infer_dtype(flat)
        return _Tensor(shape, inferred, tuple(_cast(item, inferred) for item in flat))

    def create(
        self, data: Any, dtype: str | None = None, device: str = "cpu"
    ) -> TensorValueRef:
        if device != "cpu":
            raise TensorError("TSF-014", f"unsupported device: {device}")
        shape, flat = _shape_and_flat(data)
        return self._new(shape, dtype or _infer_dtype(flat), flat)

    def zeros(
        self, shape: list[int] | tuple[int, ...], dtype: str = "f32"
    ) -> TensorValueRef:
        shape = tuple(shape)
        return self._new(shape, dtype, [0] * _product(shape))

    def ones(
        self, shape: list[int] | tuple[int, ...], dtype: str = "f32"
    ) -> TensorValueRef:
        shape = tuple(shape)
        return self._new(shape, dtype, [1] * _product(shape))

    def full(
        self, shape: list[int] | tuple[int, ...], value: Any, dtype: str = "f32"
    ) -> TensorValueRef:
        shape = tuple(shape)
        return self._new(shape, dtype, [value] * _product(shape))

    def shape(self, value: TensorValueRef) -> list[int]:
        return list(self._tensor(value).shape)

    def rank(self, value: TensorValueRef) -> int:
        return len(self._tensor(value).shape)

    def size(self, value: TensorValueRef) -> int:
        return len(self._tensor(value).data)

    def dtype(self, value: TensorValueRef) -> str:
        return self._tensor(value).dtype

    def dimension(self, value: TensorValueRef, axis: int) -> int:
        tensor = self._tensor(value)
        return tensor.shape[_normalize_axis(axis, len(tensor.shape))]

    def reshape(
        self, value: TensorValueRef, shape: list[int] | tuple[int, ...]
    ) -> TensorValueRef:
        tensor = self._tensor(value)
        target = list(shape)
        if target.count(-1) > 1:
            raise TensorError(
                "TSF-007", "reshape permits at most one inferred dimension"
            )
        if -1 in target:
            known = math.prod(item for item in target if item != -1)
            if known == 0 or len(tensor.data) % known:
                raise TensorError("TSF-007", "reshape element count mismatch")
            target[target.index(-1)] = len(tensor.data) // known
        if _product(tuple(target)) != len(tensor.data):
            raise TensorError("TSF-007", "reshape element count mismatch")
        return self._new(tuple(target), tensor.dtype, list(tensor.data))

    def flatten(self, value: TensorValueRef) -> TensorValueRef:
        return self.reshape(value, [self.size(value)])

    def transpose(
        self, value: TensorValueRef, axis_a: int = 0, axis_b: int = 1
    ) -> TensorValueRef:
        tensor = self._tensor(value)
        rank = len(tensor.shape)
        a, b = _normalize_axis(axis_a, rank), _normalize_axis(axis_b, rank)
        out_shape = list(tensor.shape)
        out_shape[a], out_shape[b] = out_shape[b], out_shape[a]
        out = [None] * len(tensor.data)
        for index, item in enumerate(tensor.data):
            coord = list(_coords(index, tensor.shape))
            coord[a], coord[b] = coord[b], coord[a]
            out[_flat_index(tuple(coord), tuple(out_shape))] = item
        return self._new(tuple(out_shape), tensor.dtype, out)

    def squeeze(self, value: TensorValueRef, axis: int | None = None) -> TensorValueRef:
        tensor = self._tensor(value)
        if axis is None:
            shape = tuple(size for size in tensor.shape if size != 1)
        else:
            normalized = _normalize_axis(axis, len(tensor.shape))
            if tensor.shape[normalized] != 1:
                raise TensorError(
                    "TSF-003", "cannot squeeze a dimension whose size is not one"
                )
            shape = tensor.shape[:normalized] + tensor.shape[normalized + 1 :]
        return self._new(shape, tensor.dtype, list(tensor.data))

    def unsqueeze(self, value: TensorValueRef, axis: int) -> TensorValueRef:
        tensor = self._tensor(value)
        normalized = _normalize_axis(axis, len(tensor.shape), insertion=True)
        return self._new(
            tensor.shape[:normalized] + (1,) + tensor.shape[normalized:],
            tensor.dtype,
            list(tensor.data),
        )

    def concat(self, values: list[TensorValueRef], axis: int = 0) -> TensorValueRef:
        tensors = [self._tensor(value) for value in values]
        if not tensors:
            raise TensorError("TSF-009", "concat requires at least one Tensor")
        rank = len(tensors[0].shape)
        axis = _normalize_axis(axis, rank)
        if any(
            len(t.shape) != rank
            or any(t.shape[i] != tensors[0].shape[i] for i in range(rank) if i != axis)
            for t in tensors
        ):
            raise TensorError("TSF-009", "concat shapes do not match")
        out_shape = list(tensors[0].shape)
        out_shape[axis] = sum(t.shape[axis] for t in tensors)
        out = [None] * _product(tuple(out_shape))
        offset = 0
        for tensor in tensors:
            for index, item in enumerate(tensor.data):
                coord = list(_coords(index, tensor.shape))
                coord[axis] += offset
                out[_flat_index(tuple(coord), tuple(out_shape))] = item
            offset += tensor.shape[axis]
        return self._new(tuple(out_shape), tensors[0].dtype, out)

    def stack(self, values: list[TensorValueRef], axis: int = 0) -> TensorValueRef:
        tensors = [self._tensor(value) for value in values]
        if not tensors or any(t.shape != tensors[0].shape for t in tensors):
            raise TensorError("TSF-010", "stack requires identical shapes")
        expanded = [self.unsqueeze(value, axis) for value in values]
        return self.concat(expanded, axis)

    def _binary(
        self,
        left: Any,
        right: Any,
        operation: Callable[[Any, Any], Any],
        *,
        comparison: bool = False,
    ) -> TensorValueRef:
        a, b = self._operand(left), self._operand(right)
        shape = _broadcast_shape(a.shape, b.shape)
        dtype = "bool" if comparison else _promote(a.dtype, b.dtype)
        data = [
            operation(
                _broadcast_value(a, _coords(i, shape)),
                _broadcast_value(b, _coords(i, shape)),
            )
            for i in range(_product(shape))
        ]
        return self._new(shape, dtype, data)

    def add(self, a: Any, b: Any) -> TensorValueRef:
        return self._binary(a, b, lambda x, y: x + y)

    def subtract(self, a: Any, b: Any) -> TensorValueRef:
        return self._binary(a, b, lambda x, y: x - y)

    def multiply(self, a: Any, b: Any) -> TensorValueRef:
        return self._binary(a, b, lambda x, y: x * y)

    def divide(self, a: Any, b: Any) -> TensorValueRef:
        return self._binary(a, b, lambda x, y: x / y)

    def power(self, a: Any, b: Any) -> TensorValueRef:
        return self._binary(a, b, lambda x, y: x**y)

    def maximum(self, a: Any, b: Any) -> TensorValueRef:
        return self._binary(a, b, max)

    def minimum(self, a: Any, b: Any) -> TensorValueRef:
        return self._binary(a, b, min)

    def _unary(self, value: TensorValueRef, fn: Callable[[Any], Any]) -> TensorValueRef:
        tensor = self._tensor(value)
        return self._new(tensor.shape, tensor.dtype, [fn(item) for item in tensor.data])

    def negate(self, value: TensorValueRef) -> TensorValueRef:
        return self._unary(value, lambda x: -x)

    def abs(self, value: TensorValueRef) -> TensorValueRef:
        return self._unary(value, abs)

    def exp(self, value: TensorValueRef) -> TensorValueRef:
        return self._unary(value, math.exp)

    def log(self, value: TensorValueRef) -> TensorValueRef:
        return self._unary(value, math.log)

    def sqrt(self, value: TensorValueRef) -> TensorValueRef:
        return self._unary(value, math.sqrt)

    def equal(self, a: Any, b: Any) -> TensorValueRef:
        return self._binary(a, b, lambda x, y: x == y, comparison=True)

    def not_equal(self, a: Any, b: Any) -> TensorValueRef:
        return self._binary(a, b, lambda x, y: x != y, comparison=True)

    def greater(self, a: Any, b: Any) -> TensorValueRef:
        return self._binary(a, b, lambda x, y: x > y, comparison=True)

    def greater_equal(self, a: Any, b: Any) -> TensorValueRef:
        return self._binary(a, b, lambda x, y: x >= y, comparison=True)

    def less(self, a: Any, b: Any) -> TensorValueRef:
        return self._binary(a, b, lambda x, y: x < y, comparison=True)

    def less_equal(self, a: Any, b: Any) -> TensorValueRef:
        return self._binary(a, b, lambda x, y: x <= y, comparison=True)

    def _reduce(
        self,
        value: TensorValueRef,
        axis: int | list[int] | None,
        keep_dims: bool,
        fn: Callable[[list[Any]], Any],
        dtype: str | None = None,
    ) -> TensorValueRef:
        tensor = self._tensor(value)
        rank = len(tensor.shape)
        axes = (
            tuple(range(rank))
            if axis is None
            else tuple(
                _normalize_axis(a, rank)
                for a in (axis if isinstance(axis, list) else [axis])
            )
        )
        if len(set(axes)) != len(axes):
            raise TensorError("TSF-005", "duplicate reduction axis")
        out_shape = (
            tuple(1 if i in axes else size for i, size in enumerate(tensor.shape))
            if keep_dims
            else tuple(size for i, size in enumerate(tensor.shape) if i not in axes)
        )
        groups: list[list[Any]] = [[] for _ in range(_product(out_shape))]
        for index, item in enumerate(tensor.data):
            coord = _coords(index, tensor.shape)
            out_coord = (
                tuple(0 if i in axes else c for i, c in enumerate(coord))
                if keep_dims
                else tuple(c for i, c in enumerate(coord) if i not in axes)
            )
            groups[_flat_index(out_coord, out_shape)].append(item)
        return self._new(
            out_shape, dtype or tensor.dtype, [fn(group) for group in groups]
        )

    def sum(
        self,
        value: TensorValueRef,
        axis: int | list[int] | None = None,
        keep_dims: bool = False,
    ) -> TensorValueRef:
        return self._reduce(value, axis, keep_dims, sum)

    def mean(
        self,
        value: TensorValueRef,
        axis: int | list[int] | None = None,
        keep_dims: bool = False,
    ) -> TensorValueRef:
        return self._reduce(value, axis, keep_dims, lambda xs: sum(xs) / len(xs), "f64")

    def min(
        self,
        value: TensorValueRef,
        axis: int | list[int] | None = None,
        keep_dims: bool = False,
    ) -> TensorValueRef:
        return self._reduce(value, axis, keep_dims, min)

    def max(
        self,
        value: TensorValueRef,
        axis: int | list[int] | None = None,
        keep_dims: bool = False,
    ) -> TensorValueRef:
        return self._reduce(value, axis, keep_dims, max)

    def argmax(
        self, value: TensorValueRef, axis: int | None = None, keep_dims: bool = False
    ) -> TensorValueRef:
        return self._arg_reduce(value, axis, keep_dims, max)

    def argmin(
        self, value: TensorValueRef, axis: int | None = None, keep_dims: bool = False
    ) -> TensorValueRef:
        return self._arg_reduce(value, axis, keep_dims, min)

    def _arg_reduce(
        self, value: TensorValueRef, axis: int | None, keep_dims: bool, fn: Callable
    ) -> TensorValueRef:
        tensor = self._tensor(value)
        if axis is None:
            target = fn(tensor.data)
            return self._new((), "i64", [tensor.data.index(target)])
        axis = _normalize_axis(axis, len(tensor.shape))
        out_shape = (
            tuple(1 if i == axis else s for i, s in enumerate(tensor.shape))
            if keep_dims
            else tensor.shape[:axis] + tensor.shape[axis + 1 :]
        )
        out = []
        for index in range(_product(out_shape)):
            base = list(_coords(index, out_shape))
            if not keep_dims:
                base.insert(axis, 0)
            values = []
            for position in range(tensor.shape[axis]):
                base[axis] = position
                values.append(tensor.data[_flat_index(tuple(base), tensor.shape)])
            out.append(values.index(fn(values)))
        return self._new(out_shape, "i64", out)

    def dot(self, left: TensorValueRef, right: TensorValueRef) -> TensorValueRef:
        a, b = self._tensor(left), self._tensor(right)
        if len(a.shape) != 1 or a.shape != b.shape:
            raise TensorError("TSF-008", "dot requires equal rank-1 Tensors")
        return self._new(
            (), _promote(a.dtype, b.dtype), [sum(x * y for x, y in zip(a.data, b.data))]
        )

    def matmul(self, left: TensorValueRef, right: TensorValueRef) -> TensorValueRef:
        a, b = self._tensor(left), self._tensor(right)
        if len(a.shape) != 2 or len(b.shape) != 2:
            raise TensorError("TSF-004", "v0.1 matmul requires rank-2 Tensors")
        if a.shape[1] != b.shape[0]:
            raise TensorError(
                "TSF-008",
                "tensor.matmul dimension mismatch",
                left_shape=list(a.shape),
                right_shape=list(b.shape),
            )
        data = [
            sum(
                a.data[row * a.shape[1] + k] * b.data[k * b.shape[1] + column]
                for k in range(a.shape[1])
            )
            for row in range(a.shape[0])
            for column in range(b.shape[1])
        ]
        return self._new((a.shape[0], b.shape[1]), _promote(a.dtype, b.dtype), data)

    def norm(self, value: TensorValueRef, order: int = 2) -> TensorValueRef:
        tensor = self._tensor(value)
        if order not in {1, 2}:
            raise TensorError("TSF-016", "v0.1 norm supports only orders 1 and 2")
        result = (
            sum(abs(x) for x in tensor.data)
            if order == 1
            else math.sqrt(sum(x * x for x in tensor.data))
        )
        return self._new((), "f64", [result])

    def cast(self, value: TensorValueRef, dtype: str) -> TensorValueRef:
        tensor = self._tensor(value)
        return self._new(tensor.shape, dtype, list(tensor.data))

    def to_array(self, value: TensorValueRef) -> Any:
        tensor = self._tensor(value)
        if len(tensor.data) > self.policy.inline_elements:
            raise TensorError("TSF-020", "Tensor exceeds to_array policy")
        return _nested(list(tensor.data), tensor.shape)

    def scalar(self, value: TensorValueRef) -> Any:
        tensor = self._tensor(value)
        if len(tensor.data) != 1:
            raise TensorError("TSF-011", "Tensor cannot be converted to Scalar")
        return tensor.data[0]

    def execution_plan(self) -> list[dict[str, Any]]:
        return [
            {
                key: value
                for key, value in entry.items()
                if key not in {"duration_ns", "status", "diagnostics"}
            }
            for entry in self.trace
        ]

    def artifact(self, value: TensorValueRef, directory: Path) -> dict[str, Any]:
        tensor = self._tensor(value)
        directory.mkdir(parents=True, exist_ok=True)
        metadata = value.metadata()
        if len(tensor.data) <= self.policy.inline_elements:
            metadata["inline_data"] = _nested(list(tensor.data), tensor.shape)
            return metadata
        payload = json.dumps(list(tensor.data), separators=(",", ":")).encode()
        if len(payload) > self.policy.max_artifact_bytes:
            raise TensorError(
                "TSF-020",
                "Tensor artifact exceeds resource policy",
                byte_size=len(payload),
                max_artifact_bytes=self.policy.max_artifact_bytes,
            )
        path = directory / f"{value.tensor_id}.bin"
        try:
            path.write_bytes(payload)
        except OSError as error:
            raise TensorError("TSF-020", "Tensor artifact storage failed") from error
        metadata.update(
            {
                "storage_ref": str(path),
                "checksum": f"sha256:{hashlib.sha256(payload).hexdigest()}",
                "byte_size": len(payload),
            }
        )
        return metadata


def _nested(data: list[Any], shape: tuple[int, ...]) -> Any:
    if not shape:
        return data[0]
    step = _product(shape[1:])
    return [_nested(data[i : i + step], shape[1:]) for i in range(0, len(data), step)]


def _promote(a: str, b: str) -> str:
    order = ["bool", "i32", "i64", "f32", "f64"]
    return order[max(order.index(a), order.index(b))]


def _contracts() -> dict[str, TensorFunctionContract]:
    groups = {
        "creation": "create zeros ones full",
        "inspection": "shape rank size dtype dimension",
        "shape": "reshape flatten transpose squeeze unsqueeze concat stack",
        "broadcast": "add subtract multiply divide power maximum minimum equal not_equal greater greater_equal less less_equal",
        "elementwise": "negate abs exp log sqrt",
        "reduction": "sum mean min max argmax argmin",
        "linear_algebra": "dot matmul norm",
        "conversion": "cast to_array scalar",
    }
    result = {}
    for policy, names in groups.items():
        for name in names.split():
            inputs = (
                ("value",)
                if name not in {"create", "zeros", "ones", "full"}
                else ("data_or_shape",)
            )
            result[f"tensor.{name}"] = TensorFunctionContract(
                f"tensor.{name}", inputs, "Tensor", policy
            )
    return result


def create_tensor_runtime() -> TensorRuntime:
    return TensorRuntime()
