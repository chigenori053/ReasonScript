"""Backend-independent Tensor standard-function layer.

The runtime core only sees :class:`TensorValueRef`; storage and numeric work stay
behind the backend adapter.  The reference backend intentionally uses Python's
standard library so Tensor support remains optional for existing installations.
"""

from __future__ import annotations

import builtins
import hashlib
import json
import math
import os
import struct
import tempfile
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from .operations import operation_signature

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
        result = {
            "code": self.code,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "details": self.details,
        }
        # ICRIR diagnostics keep the established details object while also
        # exposing the traceability fields required by the runtime contract.
        for key in (
            "source_location",
            "operation_ref",
            "tensor_ref",
            "runtime_step",
            "recovery_hint",
        ):
            if key in self.details:
                result[key] = self.details[key]
        return result


class TensorError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        category: str = "tensor.runtime",
        **details: Any,
    ):
        severity = str(details.pop("severity", "fatal"))
        self.diagnostic = TensorDiagnostic(
            code, message, category, severity=severity, details=details
        )
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
    max_autograd_nodes: int = 100_000
    max_saved_tensor_bytes: int = 512 * 1024 * 1024


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
            "backend_operation": self.backend_operation
            or self.function_id.split(".", 1)[1],
            "lowering_policy": self.lowering_policy,
        }


@dataclass(frozen=True)
class _Tensor:
    shape: tuple[int, ...]
    dtype: str
    data: tuple[Any, ...]


@dataclass(frozen=True)
class _GradNode:
    function_id: str
    output_id: str
    arguments: tuple[Any, ...]
    attributes: dict[str, Any]


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
        self,
        backend: TensorBackend | None = None,
        policy: TensorPolicy | None = None,
        *,
        resource_root: Path | None = None,
        filesystem_read: bool = False,
        filesystem_write: bool = False,
    ):
        self.backend = backend or PythonTensorBackend()
        self.policy = policy or TensorPolicy()
        self._refs: dict[str, TensorValueRef] = {}
        self._next_id = 1
        self._active_function: str | None = None
        self._active_source_location: dict[str, int] | None = None
        self._protected_roots: list[Any] = []
        self._requires_grad: set[str] = set()
        self._parameters: set[str] = set()
        self._grad_nodes: dict[str, _GradNode] = {}
        self._autograd_roots: set[str] = set()
        self._no_grad_depth = 0
        self.resource_root = (resource_root or Path.cwd()).resolve()
        self.filesystem_read = filesystem_read
        self.filesystem_write = filesystem_write
        self.trace: list[dict[str, Any]] = []
        self.contracts = _contracts()

    def function_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.contracts))

    def call(
        self,
        function_id: str,
        *args: Any,
        _source_location: dict[str, int] | None = None,
        **kwargs: Any,
    ) -> Any:
        if function_id not in self.contracts:
            raise TensorError(
                "TSF-014",
                f"Tensor operation is unsupported by the selected backend: {function_id}",
                function_id=function_id,
                backend=self.backend.name,
            )
        self._active_function = function_id
        self._active_source_location = _source_location
        started = time.perf_counter_ns()
        try:
            self._validate_argument_count(function_id, len(args), kwargs)
            method = getattr(self, function_id.split(".", 1)[1])
            output = method(*args, **kwargs)
            if function_id not in {
                "tensor.parameter",
                "tensor.detach",
                "tensor.grad",
                "tensor.requires_grad",
            }:
                self._record_autograd(function_id, args, kwargs, output)
        except TensorError as error:
            self._add_active_source_location(error)
            self._active_function = None
            self._active_source_location = None
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
            self._active_function = None
            source_location = self._active_source_location
            self._active_source_location = None
            normalized = TensorError(
                "TSF-012",
                "Tensor backend execution failed",
                function_id=function_id,
                backend=self.backend.name,
                error_type=type(error).__name__,
                **(
                    {"source_location": source_location}
                    if source_location is not None
                    else {}
                ),
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
        self._active_function = None
        self._active_source_location = None
        return output

    def _add_active_source_location(self, error: TensorError) -> None:
        if (
            self._active_source_location is not None
            and error.diagnostic.details.get("source_location") is None
        ):
            error.diagnostic.details["source_location"] = dict(
                self._active_source_location
            )

    def collect(self, *roots: Any) -> int:
        """Release tensors that are unreachable from the evaluator's live roots."""
        reachable: set[str] = set()
        visited: set[int] = set()

        def visit(value: Any) -> None:
            if isinstance(value, TensorValueRef):
                reachable.add(value.tensor_id)
                return
            if isinstance(value, (str, bytes, bool, int, float, type(None))):
                return
            identity = id(value)
            if identity in visited:
                return
            visited.add(identity)
            if isinstance(value, dict):
                for key, item in value.items():
                    visit(key)
                    visit(item)
            elif isinstance(value, (list, tuple, set, frozenset)):
                for item in value:
                    visit(item)
            elif hasattr(value, "fields") and isinstance(value.fields, dict):
                visit(value.fields)

        for root in (*self._protected_roots, *roots):
            visit(root)
        for tensor_id in self._autograd_roots:
            if tensor_id in self._refs:
                reachable.add(tensor_id)
        released = 0
        for tensor_id in tuple(self._refs):
            if tensor_id not in reachable:
                self.backend.release(tensor_id)
                del self._refs[tensor_id]
                self._requires_grad.discard(tensor_id)
                self._parameters.discard(tensor_id)
                released += 1
        return released

    @contextmanager
    def protect(self, *roots: Any):
        """Keep caller-owned values alive while a nested scope is evaluated."""
        self._protected_roots.extend(roots)
        try:
            yield
        finally:
            if roots:
                del self._protected_roots[-len(roots) :]

    def _validate_argument_count(
        self, function_id: str, positional: int, named: dict[str, Any]
    ) -> None:
        signature = operation_signature(function_id)
        if signature is None:
            return
        minimum, maximum = signature.limits
        count = positional + len(named)
        if count < minimum or count > maximum:
            raise TensorError(
                "TSF-016",
                "Tensor function argument count mismatch",
                function_id=function_id,
                minimum=minimum,
                maximum=maximum,
                actual=count,
            )

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
            if isinstance(value, TensorValueRef):
                return {
                    "tensor_id": value.tensor_id,
                    "shape": list(value.shape),
                    "dtype": value.dtype,
                    "device": value.device,
                    "backend": value.backend,
                }
            if isinstance(value, (list, tuple)):
                return [info(item) for item in value]
            if isinstance(value, dict):
                return {str(key): info(item) for key, item in value.items()}
            return value

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
        self._validate_finite(data)
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
        if size == 0 or any(dimension == 0 for dimension in shape):
            raise TensorError(
                "TSF-009",
                "Empty tensor is not allowed",
                shape=list(shape),
                source_location=self._active_source_location,
                operation_ref=self._active_function,
                tensor_ref="tensor_input",
                recovery_hint="Provide at least one finite tensor element.",
            )
        if (
            size > self.policy.max_elements
            or size * DTYPE_BYTES[dtype] > self.policy.max_tensor_bytes
        ):
            raise TensorError(
                "TSF-003", "Tensor shape exceeds resource policy", shape=list(shape)
            )

    def _validate_finite(self, data: list[Any]) -> None:
        for index, value in enumerate(data):
            if isinstance(value, float) and math.isnan(value):
                if self._active_function not in {None, "tensor.create"}:
                    raise TensorError(
                        "TSF-012",
                        "Tensor operation produced a non-finite value",
                        operation=self._active_function,
                        operation_ref=self._active_function,
                        flattened_index=index,
                        value_category="nan",
                    )
                raise TensorError(
                    "TSF-010",
                    "Tensor contains NaN",
                    flattened_index=index,
                    value_category="nan",
                    operation_ref=self._active_function,
                    tensor_ref="tensor_input",
                    source_location=self._active_source_location,
                    recovery_hint="Replace NaN with a finite value before tensor creation.",
                )
            if isinstance(value, float) and math.isinf(value):
                if self._active_function not in {None, "tensor.create"}:
                    raise TensorError(
                        "TSF-012",
                        "Tensor operation produced a non-finite value",
                        operation=self._active_function,
                        operation_ref=self._active_function,
                        flattened_index=index,
                        value_category=("positive_infinity" if value > 0 else "negative_infinity"),
                    )
                raise TensorError(
                    "TSF-011",
                    "Tensor contains Infinity",
                    flattened_index=index,
                    value_category=("positive_infinity" if value > 0 else "negative_infinity"),
                    operation_ref=self._active_function,
                    tensor_ref="tensor_input",
                    source_location=self._active_source_location,
                    recovery_hint="Replace Infinity with a finite value before tensor creation.",
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

    def slice(
        self,
        value: TensorValueRef,
        starts: list[int],
        ends: list[int],
        axes: list[int] | None = None,
        steps: list[int] | None = None,
    ) -> TensorValueRef:
        tensor = self._tensor(value)
        if len(starts) != len(ends):
            raise TensorError("TSF-021", "slice starts and ends must have equal length")
        selected_axes = list(range(len(starts))) if axes is None else list(axes)
        selected_steps = [1] * len(starts) if steps is None else list(steps)
        if not (
            len(selected_axes) == len(starts) == len(selected_steps)
            and all(isinstance(item, int) and item > 0 for item in selected_steps)
        ):
            raise TensorError("TSF-021", "invalid slice axes or steps")
        ranges = [list(range(size)) for size in tensor.shape]
        normalized_axes: set[int] = set()
        for start, end, axis, step in zip(
            starts, ends, selected_axes, selected_steps
        ):
            normalized = _normalize_axis(axis, len(tensor.shape))
            if normalized in normalized_axes:
                raise TensorError("TSF-021", "duplicate slice axis")
            normalized_axes.add(normalized)
            begin, stop, stride = builtins.slice(start, end, step).indices(
                tensor.shape[normalized]
            )
            ranges[normalized] = list(range(begin, stop, stride))
        out_shape = tuple(len(items) for items in ranges)
        if any(size == 0 for size in out_shape):
            raise TensorError("TSF-009", "Empty tensor is not allowed")
        data = [
            tensor.data[_flat_index(coord, tensor.shape)]
            for coord in _coordinate_product(ranges)
        ]
        return self._new(out_shape, tensor.dtype, data)

    def narrow(
        self, value: TensorValueRef, axis: int, start: int, length: int
    ) -> TensorValueRef:
        if not isinstance(length, int) or length <= 0:
            raise TensorError("TSF-021", "narrow length must be positive")
        return self.slice(value, [start], [start + length], [axis], [1])

    def gather(
        self, value: TensorValueRef, indices: TensorValueRef, axis: int = 0
    ) -> TensorValueRef:
        tensor = self._tensor(value)
        index_tensor = self._tensor(indices)
        if index_tensor.dtype not in {"i32", "i64"}:
            raise TensorError("TSF-023", "gather indices must use i32 or i64")
        normalized = _normalize_axis(axis, len(tensor.shape))
        normalized_indices = []
        for raw in index_tensor.data:
            index = int(raw)
            if index < 0:
                index += tensor.shape[normalized]
            if index < 0 or index >= tensor.shape[normalized]:
                raise TensorError(
                    "TSF-022",
                    "gather index is out of range",
                    index=int(raw),
                    axis=normalized,
                )
            normalized_indices.append(index)
        out_shape = (
            tensor.shape[:normalized]
            + index_tensor.shape
            + tensor.shape[normalized + 1 :]
        )
        data = []
        for out_coord in _all_coords(out_shape):
            before = out_coord[:normalized]
            index_coord = out_coord[
                normalized : normalized + len(index_tensor.shape)
            ]
            after = out_coord[normalized + len(index_tensor.shape) :]
            selected = normalized_indices[
                _flat_index(index_coord, index_tensor.shape)
            ]
            data.append(
                tensor.data[
                    _flat_index(before + (selected,) + after, tensor.shape)
                ]
            )
        return self._new(out_shape, tensor.dtype, data)

    def random_uniform(
        self,
        shape: list[int],
        low: float = 0.0,
        high: float = 1.0,
        seed: int = 0,
        stream: int = 0,
        dtype: str = "f32",
    ) -> TensorValueRef:
        target = tuple(shape)
        if dtype not in {"f32", "f64"} or not high > low:
            raise TensorError("RNG-001", "invalid random_uniform contract")
        self._validate_shape(target, dtype)
        data = [
            low
            + (high - low)
            * _random_unit("uniform", seed, stream, index)
            for index in range(_product(target))
        ]
        return self._new(target, dtype, data)

    def random_normal(
        self,
        shape: list[int],
        mean: float = 0.0,
        std: float = 1.0,
        seed: int = 0,
        stream: int = 0,
        dtype: str = "f32",
    ) -> TensorValueRef:
        target = tuple(shape)
        if dtype not in {"f32", "f64"} or std < 0:
            raise TensorError("RNG-001", "invalid random_normal contract")
        self._validate_shape(target, dtype)
        data = []
        for index in range(_product(target)):
            u1 = max(_random_unit("normal-a", seed, stream, index), 2**-53)
            u2 = _random_unit("normal-b", seed, stream, index)
            z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
            data.append(mean + std * z)
        return self._new(target, dtype, data)

    def random_bernoulli(
        self,
        shape: list[int],
        probability: float = 0.5,
        seed: int = 0,
        stream: int = 0,
    ) -> TensorValueRef:
        target = tuple(shape)
        if probability < 0 or probability > 1:
            raise TensorError("RNG-001", "probability must be in [0, 1]")
        self._validate_shape(target, "bool")
        return self._new(
            target,
            "bool",
            [
                _random_unit("bernoulli", seed, stream, index) < probability
                for index in range(_product(target))
            ],
        )

    def random_permutation(
        self, size: int, seed: int = 0, stream: int = 0
    ) -> TensorValueRef:
        if not isinstance(size, int) or size <= 0:
            raise TensorError("RNG-001", "permutation size must be positive")
        values = list(range(size))
        for index in range(size - 1, 0, -1):
            selected = int(
                _random_unit("permutation", seed, stream, size - index)
                * (index + 1)
            )
            values[index], values[selected] = values[selected], values[index]
        return self._new((size,), "i64", values)

    def load(self, path: str) -> TensorValueRef:
        if not self.filesystem_read:
            raise TensorError(
                "TIO-001", "tensor.load requires filesystem_read capability"
            )
        source = self._resolve_tensor_path(path)
        try:
            payload = source.read_bytes()
        except OSError as error:
            raise TensorError("TIO-003", "Tensor file cannot be read") from error
        return self._decode_tensor_file(payload)

    def save(
        self, value: TensorValueRef, path: str, overwrite: bool = False
    ) -> dict[str, Any]:
        if not self.filesystem_write:
            raise TensorError(
                "TIO-001", "tensor.save requires filesystem_write capability"
            )
        target = self._resolve_tensor_path(path)
        if target.exists() and not overwrite:
            raise TensorError("TIO-005", "Tensor file already exists")
        payload, checksum = self._encode_tensor_file(value)
        if len(payload) > self.policy.max_artifact_bytes:
            raise TensorError("TIO-003", "Tensor file exceeds resource policy")
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", dir=target.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, target)
        except OSError as error:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise TensorError("TIO-005", "atomic Tensor write failed") from error
        return {
            "profile": "reasonscript-tensor-file/1.0",
            "path": path,
            "byte_size": len(payload),
            "checksum": f"sha256:{checksum}",
        }

    def _resolve_tensor_path(self, path: str) -> Path:
        if not isinstance(path, str) or not path or "\\" in path:
            raise TensorError("TIO-002", "unsafe Tensor path")
        pure = PurePosixPath(path)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise TensorError("TIO-002", "unsafe Tensor path")
        candidate = (self.resource_root / pure).resolve()
        if self.resource_root != candidate and self.resource_root not in candidate.parents:
            raise TensorError("TIO-002", "Tensor path escapes resource root")
        if candidate.suffix != ".rstensor":
            raise TensorError("TIO-002", "Tensor path must use .rstensor")
        return candidate

    def _encode_tensor_file(
        self, value: TensorValueRef
    ) -> tuple[bytes, str]:
        tensor = self._tensor(value)
        body = _pack_tensor_data(tensor)
        digest = hashlib.sha256(body).hexdigest()
        header = json.dumps(
            {
                "byte_size": len(body),
                "dtype": tensor.dtype,
                "payload_sha256": digest,
                "profile": "reasonscript-tensor-file/1.0",
                "shape": list(tensor.shape),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return b"RSNTNSR1" + struct.pack("<I", len(header)) + header + body, digest

    def _decode_tensor_file(self, payload: bytes) -> TensorValueRef:
        if len(payload) < 12 or payload[:8] != b"RSNTNSR1":
            raise TensorError("TIO-003", "invalid Tensor file magic")
        header_size = struct.unpack("<I", payload[8:12])[0]
        if header_size > len(payload) - 12:
            raise TensorError("TIO-003", "invalid Tensor file header")
        try:
            header = json.loads(payload[12 : 12 + header_size])
            shape = tuple(header["shape"])
            dtype = str(header["dtype"])
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
            raise TensorError("TIO-003", "invalid Tensor file header") from error
        body = payload[12 + header_size :]
        if (
            header.get("profile") != "reasonscript-tensor-file/1.0"
            or header.get("byte_size") != len(body)
            or header.get("payload_sha256") != hashlib.sha256(body).hexdigest()
        ):
            raise TensorError("TIO-004", "Tensor file checksum or size mismatch")
        values = _unpack_tensor_data(dtype, body)
        if len(values) != _product(shape):
            raise TensorError("TSF-003", "Tensor file shape mismatch")
        return self._new(shape, dtype, values)

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

    def relu(self, value: TensorValueRef) -> TensorValueRef:
        """Return ``max(value, 0)`` while preserving semantic trace identity."""
        return self.maximum(value, 0)

    def softmax(self, value: TensorValueRef, axis: int = -1) -> TensorValueRef:
        """Numerically stable softmax over one axis."""
        tensor = self._tensor(value)
        normalized = _normalize_axis(axis, len(tensor.shape))
        maximum = self.max(value, axis=normalized, keep_dims=True)
        shifted = self.subtract(value, maximum)
        exponential = self.exp(shifted)
        denominator = self.sum(exponential, axis=normalized, keep_dims=True)
        return self.divide(exponential, denominator)

    def linear(
        self,
        value: TensorValueRef,
        weight: TensorValueRef,
        bias: TensorValueRef | None = None,
    ) -> TensorValueRef:
        """Apply the standard ``matmul(value, weight) + bias`` orientation."""
        result = self.matmul(value, weight)
        return result if bias is None else self.add(result, bias)

    def conv2d(
        self,
        input: TensorValueRef,
        weight: TensorValueRef,
        bias: TensorValueRef | None = None,
        stride: list[int] | tuple[int, int] = (1, 1),
        padding: list[int] | tuple[int, int] = (0, 0),
        dilation: list[int] | tuple[int, int] = (1, 1),
        groups: int = 1,
    ) -> TensorValueRef:
        source, kernel = self._tensor(input), self._tensor(weight)
        if len(source.shape) != 4 or len(kernel.shape) != 4:
            raise TensorError("TSF-024", "conv2d requires NCHW input and OIHW weight")
        stride_h, stride_w = _positive_pair(stride, "conv2d stride")
        dilation_h, dilation_w = _positive_pair(dilation, "conv2d dilation")
        pad_h, pad_w = _nonnegative_pair(padding, "conv2d padding")
        batch, in_channels, in_h, in_w = source.shape
        out_channels, kernel_channels, kernel_h, kernel_w = kernel.shape
        if (
            not isinstance(groups, int)
            or groups <= 0
            or in_channels % groups
            or out_channels % groups
            or kernel_channels != in_channels // groups
        ):
            raise TensorError("TSF-024", "invalid conv2d groups or channel dimensions")
        out_h = (
            in_h + 2 * pad_h - dilation_h * (kernel_h - 1) - 1
        ) // stride_h + 1
        out_w = (
            in_w + 2 * pad_w - dilation_w * (kernel_w - 1) - 1
        ) // stride_w + 1
        if out_h <= 0 or out_w <= 0:
            raise TensorError("TSF-024", "conv2d output shape is empty")
        bias_tensor = self._tensor(bias) if bias is not None else None
        if bias_tensor is not None and bias_tensor.shape != (out_channels,):
            raise TensorError("TSF-024", "conv2d bias must have shape [out_channels]")
        dtype = _promote(source.dtype, kernel.dtype)
        if dtype not in {"f32", "f64"}:
            raise TensorError("TSF-024", "conv2d requires floating-point Tensor values")
        output: list[float] = []
        channels_per_group = out_channels // groups
        for n in range(batch):
            for out_channel in range(out_channels):
                group = out_channel // channels_per_group
                for out_y in range(out_h):
                    for out_x in range(out_w):
                        total = (
                            float(bias_tensor.data[out_channel])
                            if bias_tensor is not None
                            else 0.0
                        )
                        for local_channel in range(kernel_channels):
                            in_channel = group * kernel_channels + local_channel
                            for kernel_y in range(kernel_h):
                                input_y = (
                                    out_y * stride_h
                                    - pad_h
                                    + kernel_y * dilation_h
                                )
                                if input_y < 0 or input_y >= in_h:
                                    continue
                                for kernel_x in range(kernel_w):
                                    input_x = (
                                        out_x * stride_w
                                        - pad_w
                                        + kernel_x * dilation_w
                                    )
                                    if input_x < 0 or input_x >= in_w:
                                        continue
                                    total += source.data[
                                        _flat_index(
                                            (n, in_channel, input_y, input_x),
                                            source.shape,
                                        )
                                    ] * kernel.data[
                                        _flat_index(
                                            (
                                                out_channel,
                                                local_channel,
                                                kernel_y,
                                                kernel_x,
                                            ),
                                            kernel.shape,
                                        )
                                    ]
                        output.append(total)
        return self._new((batch, out_channels, out_h, out_w), dtype, output)

    def max_pool2d(
        self,
        input: TensorValueRef,
        kernel: list[int],
        stride: list[int] | None = None,
        padding: list[int] | tuple[int, int] = (0, 0),
    ) -> TensorValueRef:
        return self._pool2d(input, kernel, stride, padding, maximum=True)

    def avg_pool2d(
        self,
        input: TensorValueRef,
        kernel: list[int],
        stride: list[int] | None = None,
        padding: list[int] | tuple[int, int] = (0, 0),
        count_include_pad: bool = False,
    ) -> TensorValueRef:
        return self._pool2d(
            input,
            kernel,
            stride,
            padding,
            maximum=False,
            count_include_pad=count_include_pad,
        )

    def _pool2d(
        self,
        input: TensorValueRef,
        kernel: list[int],
        stride: list[int] | None,
        padding: list[int] | tuple[int, int],
        *,
        maximum: bool,
        count_include_pad: bool = False,
    ) -> TensorValueRef:
        source = self._tensor(input)
        if len(source.shape) != 4 or source.dtype not in {"f32", "f64"}:
            raise TensorError("TSF-025", "pool2d requires floating-point NCHW input")
        kernel_h, kernel_w = _positive_pair(kernel, "pool2d kernel")
        stride_h, stride_w = _positive_pair(
            stride or kernel, "pool2d stride"
        )
        pad_h, pad_w = _nonnegative_pair(padding, "pool2d padding")
        batch, channels, in_h, in_w = source.shape
        out_h = (in_h + 2 * pad_h - kernel_h) // stride_h + 1
        out_w = (in_w + 2 * pad_w - kernel_w) // stride_w + 1
        if out_h <= 0 or out_w <= 0:
            raise TensorError("TSF-025", "pool2d output shape is empty")
        output = []
        for n in range(batch):
            for channel in range(channels):
                for out_y in range(out_h):
                    for out_x in range(out_w):
                        values = []
                        for kernel_y in range(kernel_h):
                            input_y = out_y * stride_h - pad_h + kernel_y
                            for kernel_x in range(kernel_w):
                                input_x = out_x * stride_w - pad_w + kernel_x
                                if 0 <= input_y < in_h and 0 <= input_x < in_w:
                                    values.append(
                                        source.data[
                                            _flat_index(
                                                (n, channel, input_y, input_x),
                                                source.shape,
                                            )
                                        ]
                                    )
                                elif not maximum and count_include_pad:
                                    values.append(0.0)
                        if not values:
                            raise TensorError("TSF-025", "pool2d window has no values")
                        output.append(
                            max(values)
                            if maximum
                            else sum(values) / len(values)
                        )
        return self._new(
            (batch, channels, out_h, out_w), source.dtype, output
        )

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

    def parameter(self, value: TensorValueRef) -> TensorValueRef:
        tensor = self._tensor(value)
        if tensor.dtype not in {"f32", "f64"}:
            raise TensorError("AD-002", "parameters must use f32 or f64")
        self._drop_graph(value.tensor_id)
        result = self._new(tensor.shape, tensor.dtype, list(tensor.data))
        self._requires_grad.add(result.tensor_id)
        self._parameters.add(result.tensor_id)
        return result

    def detach(self, value: TensorValueRef) -> TensorValueRef:
        tensor = self._tensor(value)
        self._drop_graph(value.tensor_id)
        return self._new(tensor.shape, tensor.dtype, list(tensor.data))

    def requires_grad(self, value: TensorValueRef) -> bool:
        self._tensor(value)
        return value.tensor_id in self._requires_grad

    def grad(
        self, loss: TensorValueRef, parameters: list[TensorValueRef]
    ) -> list[TensorValueRef]:
        loss_tensor = self._tensor(loss)
        if loss_tensor.dtype not in {"f32", "f64"} or len(loss_tensor.data) != 1:
            raise TensorError("AD-001", "tensor.grad requires a scalar floating loss")
        if not isinstance(parameters, list) or not parameters:
            raise TensorError("AD-003", "tensor.grad requires parameters")
        for parameter in parameters:
            self._tensor(parameter)
            if parameter.tensor_id not in self._requires_grad:
                raise TensorError("AD-003", "gradient target is not a parameter")
        gradients: dict[str, list[float]] = {
            loss.tensor_id: [1.0] * len(loss_tensor.data)
        }
        for node in reversed(tuple(self._grad_nodes.values())):
            upstream = gradients.get(node.output_id)
            if upstream is None:
                continue
            for reference, contribution in self._vjp(node, upstream):
                if reference.tensor_id in gradients:
                    gradients[reference.tensor_id] = [
                        left + right
                        for left, right in zip(
                            gradients[reference.tensor_id], contribution
                        )
                    ]
                else:
                    gradients[reference.tensor_id] = contribution
        results = []
        for parameter in parameters:
            tensor = self._tensor(parameter)
            values = gradients.get(parameter.tensor_id)
            if values is None:
                values = [0.0] * len(tensor.data)
            results.append(self._new(tensor.shape, tensor.dtype, values))
        self._clear_autograd()
        return results

    _OPTIMIZER_ARGUMENT_COUNTS: dict[str, int] = {
        "optimizer.sgd": 3,
        "optimizer.momentum_velocity": 3,
        "optimizer.momentum": 5,
        "optimizer.adam_moment1": 3,
        "optimizer.adam_moment2": 3,
        "optimizer.adam": 9,
        "optimizer.adamw": 10,
    }

    def call_optimizer(
        self,
        function_id: str,
        *args: Any,
        _source_location: dict[str, int] | None = None,
    ) -> TensorValueRef:
        """Dispatch an `optimizer.*` step function.

        Deliberately separate from `call()`/`self.contracts`: Optimizer
        functions are not Tensor Standard Functions (they are not part of
        the `tensor_function_manifest.json` stability contract), have no
        autograd/trace bookkeeping (their output is a fresh, untracked
        Tensor -- like `tensor.detach`, never wired onto the grad tape),
        and every argument is a required positional Tensor or scalar (no
        `**kwargs`, no argument_contract inference), so reusing `call()`'s
        machinery would add indirection without buying anything back.
        `_source_location` is still threaded through and attached to any
        raised `TensorError`, matching `call()`'s diagnostics.
        """
        try:
            method = getattr(self, function_id.split(".", 1)[1], None) if function_id.startswith(
                "optimizer."
            ) else None
            if method is None or function_id not in self._OPTIMIZER_ARGUMENT_COUNTS:
                raise TensorError(
                    "OPT-001", f"unknown Optimizer function: {function_id}", category="optimizer.runtime"
                )
            expected = self._OPTIMIZER_ARGUMENT_COUNTS[function_id]
            if len(args) != expected:
                raise TensorError(
                    "OPT-002",
                    f"Optimizer function argument count mismatch: {function_id} expects {expected}",
                    category="optimizer.runtime",
                )
            try:
                return method(*args)
            except TensorError:
                raise
            except ZeroDivisionError as error:
                raise TensorError(
                    "OPT-004", "Optimizer step produced a non-finite value", category="optimizer.runtime"
                ) from error
        except TensorError as error:
            if _source_location is not None and error.diagnostic.details.get("source_location") is None:
                error.diagnostic.details["source_location"] = dict(_source_location)
            raise

    def sgd(self, param: Any, grad: Any, lr: Any) -> TensorValueRef:
        return self.subtract(param, self.multiply(grad, lr))

    def momentum_velocity(self, grad: Any, velocity: Any, momentum: Any) -> TensorValueRef:
        return self.add(self.multiply(momentum, velocity), grad)

    def momentum(self, param: Any, grad: Any, velocity: Any, lr: Any, momentum: Any) -> TensorValueRef:
        new_velocity = self.momentum_velocity(grad, velocity, momentum)
        return self.subtract(param, self.multiply(lr, new_velocity))

    def adam_moment1(self, grad: Any, m: Any, beta1: Any) -> TensorValueRef:
        return self.add(self.multiply(beta1, m), self.multiply(1.0 - beta1, grad))

    def adam_moment2(self, grad: Any, v: Any, beta2: Any) -> TensorValueRef:
        return self.add(self.multiply(beta2, v), self.multiply(1.0 - beta2, self.multiply(grad, grad)))

    def _adam_update(
        self,
        param: Any,
        grad: Any,
        m: Any,
        v: Any,
        step: Any,
        lr: Any,
        beta1: Any,
        beta2: Any,
        eps: Any,
    ) -> tuple[TensorValueRef, TensorValueRef]:
        if not isinstance(step, int) or isinstance(step, bool) or step < 1:
            raise TensorError(
                "OPT-005", "Optimizer step count must be a positive Int", category="optimizer.runtime"
            )
        new_m = self.adam_moment1(grad, m, beta1)
        new_v = self.adam_moment2(grad, v, beta2)
        bias_correction1 = 1.0 - beta1**step
        bias_correction2 = 1.0 - beta2**step
        m_hat = self.divide(new_m, bias_correction1)
        v_hat = self.divide(new_v, bias_correction2)
        update = self.divide(m_hat, self.add(self.sqrt(v_hat), eps))
        return update, self.multiply(lr, update)

    def adam(
        self,
        param: Any,
        grad: Any,
        m: Any,
        v: Any,
        step: Any,
        lr: Any,
        beta1: Any,
        beta2: Any,
        eps: Any,
    ) -> TensorValueRef:
        _update, scaled = self._adam_update(param, grad, m, v, step, lr, beta1, beta2, eps)
        return self.subtract(param, scaled)

    def adamw(
        self,
        param: Any,
        grad: Any,
        m: Any,
        v: Any,
        step: Any,
        lr: Any,
        beta1: Any,
        beta2: Any,
        eps: Any,
        weight_decay: Any,
    ) -> TensorValueRef:
        update, scaled = self._adam_update(param, grad, m, v, step, lr, beta1, beta2, eps)
        decay = self.multiply(lr, self.multiply(weight_decay, param))
        return self.subtract(self.subtract(param, scaled), decay)

    @contextmanager
    def no_grad(self):
        """Suppress autograd tape recording for the duration of the block.

        Implements the "evaluationをno-gradにする" Phase 1 item: calls made
        while this is active never build `_GradNode`s, even for Tensors
        that carry `requires_grad`, so evaluation-only passes (inference,
        CI/golden checks) don't pay autograd bookkeeping cost. Nests
        safely; `tensor.grad` remains an error inside the block since no
        nodes are recorded.
        """
        self._no_grad_depth += 1
        try:
            yield
        finally:
            self._no_grad_depth -= 1

    def _record_autograd(
        self,
        function_id: str,
        arguments: tuple[Any, ...],
        attributes: dict[str, Any],
        output: Any,
    ) -> None:
        if self._no_grad_depth > 0:
            return
        if not isinstance(output, TensorValueRef):
            return
        references = list(_tensor_references((arguments, attributes)))
        if not any(ref.tensor_id in self._requires_grad for ref in references):
            return
        if output.dtype not in {"f32", "f64"}:
            return
        if len(self._grad_nodes) >= self.policy.max_autograd_nodes:
            raise TensorError("AD-005", "maximum autograd node count exceeded")
        roots = {ref.tensor_id for ref in references}
        roots.add(output.tensor_id)
        prospective = self._autograd_roots | roots
        saved_bytes = sum(
            len(self.backend.load(tensor_id).data)
            * DTYPE_BYTES[self.backend.load(tensor_id).dtype]
            for tensor_id in prospective
            if tensor_id in self._refs
        )
        if saved_bytes > self.policy.max_saved_tensor_bytes:
            raise TensorError("AD-005", "autograd saved Tensor policy exceeded")
        self._autograd_roots = prospective
        self._requires_grad.add(output.tensor_id)
        self._grad_nodes[output.tensor_id] = _GradNode(
            function_id, output.tensor_id, arguments, dict(attributes)
        )

    def _drop_graph(self, tensor_id: str) -> None:
        pending = [tensor_id]
        dropped: set[str] = set()
        while pending:
            current = pending.pop()
            if current in dropped:
                continue
            dropped.add(current)
            node = self._grad_nodes.pop(current, None)
            if node is not None:
                pending.extend(
                    ref.tensor_id
                    for ref in _tensor_references(
                        (node.arguments, node.attributes)
                    )
                )
        remaining_roots: set[str] = set()
        for node in self._grad_nodes.values():
            remaining_roots.add(node.output_id)
            remaining_roots.update(
                ref.tensor_id
                for ref in _tensor_references(
                    (node.arguments, node.attributes)
                )
            )
        self._autograd_roots = remaining_roots
        self._requires_grad = set(self._parameters) | set(self._grad_nodes)

    def _clear_autograd(self) -> None:
        self._grad_nodes.clear()
        self._autograd_roots.clear()
        self._parameters.intersection_update(self._refs)
        self._requires_grad = set(self._parameters)

    def _vjp(
        self, node: _GradNode, upstream: list[float]
    ) -> list[tuple[TensorValueRef, list[float]]]:
        name = node.function_id.removeprefix("tensor.")
        args = node.arguments
        output = self.backend.load(node.output_id)

        def argument(index: int, name: str, default: Any = None) -> Any:
            return args[index] if len(args) > index else node.attributes.get(name, default)

        def tensor(
            index: int, name: str | None = None
        ) -> tuple[TensorValueRef, _Tensor]:
            reference = argument(index, name or f"argument_{index}")
            if not isinstance(reference, TensorValueRef):
                raise TensorError("AD-004", f"{name} gradient input is unavailable")
            return reference, self._tensor(reference)

        if name in {
            "add",
            "subtract",
            "multiply",
            "divide",
            "power",
            "maximum",
            "minimum",
        }:
            results = []
            left_value, right_value = argument(0, "a"), argument(1, "b")
            left = self._operand(left_value)
            right = self._operand(right_value)
            left_grad = [0.0] * len(left.data)
            right_grad = [0.0] * len(right.data)
            shape = output.shape
            for index, grad_value in enumerate(upstream):
                coordinate = _coords(index, shape)
                left_coordinate = _broadcast_coords(coordinate, left.shape)
                right_coordinate = _broadcast_coords(coordinate, right.shape)
                left_index = _flat_index(left_coordinate, left.shape)
                right_index = _flat_index(right_coordinate, right.shape)
                x, y = left.data[left_index], right.data[right_index]
                if name == "add":
                    dx, dy = grad_value, grad_value
                elif name == "subtract":
                    dx, dy = grad_value, -grad_value
                elif name == "multiply":
                    dx, dy = grad_value * y, grad_value * x
                elif name == "divide":
                    dx, dy = grad_value / y, -grad_value * x / (y * y)
                elif name == "power":
                    dx = grad_value * y * (x ** (y - 1))
                    dy = grad_value * (x**y) * math.log(x) if x > 0 else 0.0
                elif name == "maximum":
                    dx = grad_value if x >= y else 0.0
                    dy = grad_value if y > x else 0.0
                else:
                    dx = grad_value if x <= y else 0.0
                    dy = grad_value if y < x else 0.0
                left_grad[left_index] += dx
                right_grad[right_index] += dy
            if isinstance(left_value, TensorValueRef):
                results.append((left_value, left_grad))
            if isinstance(right_value, TensorValueRef):
                results.append((right_value, right_grad))
            return results

        if name in {"negate", "abs", "exp", "log", "sqrt", "relu"}:
            reference, source = tensor(0, "input" if name == "relu" else "value")
            values = []
            for index, (item, grad_value) in enumerate(zip(source.data, upstream)):
                if name == "negate":
                    derivative = -1.0
                elif name == "abs":
                    derivative = 1.0 if item > 0 else (-1.0 if item < 0 else 0.0)
                elif name == "exp":
                    derivative = output.data[index]
                elif name == "log":
                    derivative = 1.0 / item
                elif name == "sqrt":
                    derivative = 0.5 / output.data[index]
                else:
                    derivative = 1.0 if item > 0 else 0.0
                values.append(grad_value * derivative)
            return [(reference, values)]

        if name in {"reshape", "flatten", "squeeze", "unsqueeze", "cast"}:
            reference, source = tensor(0, "value")
            return [(reference, list(upstream[: len(source.data)]))]

        if name == "transpose":
            reference, source = tensor(0, "value")
            axis_a = int(argument(1, "axis_a", 0))
            axis_b = int(argument(2, "axis_b", 1))
            a = _normalize_axis(axis_a, len(source.shape))
            b = _normalize_axis(axis_b, len(source.shape))
            values = [0.0] * len(source.data)
            for index, grad_value in enumerate(upstream):
                coordinate = list(_coords(index, output.shape))
                coordinate[a], coordinate[b] = coordinate[b], coordinate[a]
                values[_flat_index(tuple(coordinate), source.shape)] += grad_value
            return [(reference, values)]

        if name in {"sum", "mean"}:
            reference, source = tensor(0, "value")
            axis = argument(1, "axis")
            keep_dims = bool(argument(2, "keep_dims", False))
            axes = (
                tuple(range(len(source.shape)))
                if axis is None
                else tuple(
                    _normalize_axis(item, len(source.shape))
                    for item in (axis if isinstance(axis, list) else [axis])
                )
            )
            divisor = math.prod(source.shape[item] for item in axes) if name == "mean" else 1
            values = []
            for coordinate in _all_coords(source.shape):
                out_coordinate = (
                    tuple(0 if i in axes else c for i, c in enumerate(coordinate))
                    if keep_dims
                    else tuple(c for i, c in enumerate(coordinate) if i not in axes)
                )
                values.append(
                    upstream[_flat_index(out_coordinate, output.shape)] / divisor
                )
            return [(reference, values)]

        if name in {"min", "max"}:
            reference, source = tensor(0, "value")
            axis = argument(1, "axis")
            keep_dims = bool(argument(2, "keep_dims", False))
            axes = (
                tuple(range(len(source.shape)))
                if axis is None
                else tuple(
                    _normalize_axis(item, len(source.shape))
                    for item in (axis if isinstance(axis, list) else [axis])
                )
            )
            values = [0.0] * len(source.data)
            groups: dict[tuple[int, ...], list[int]] = {}
            for index in range(len(source.data)):
                coordinate = _coords(index, source.shape)
                key = (
                    tuple(0 if i in axes else c for i, c in enumerate(coordinate))
                    if keep_dims
                    else tuple(c for i, c in enumerate(coordinate) if i not in axes)
                )
                groups.setdefault(key, []).append(index)
            for key, indexes in groups.items():
                selected = (
                    min(indexes, key=lambda item: source.data[item])
                    if name == "min"
                    else max(indexes, key=lambda item: source.data[item])
                )
                values[selected] += upstream[_flat_index(key, output.shape)]
            return [(reference, values)]

        if name in {"matmul", "linear"}:
            left_ref, left = tensor(0, "value" if name == "linear" else "left")
            right_ref, right = tensor(1, "weight" if name == "linear" else "right")
            left_grad = [0.0] * len(left.data)
            right_grad = [0.0] * len(right.data)
            for row in range(left.shape[0]):
                for column in range(right.shape[1]):
                    grad_value = upstream[row * right.shape[1] + column]
                    for inner in range(left.shape[1]):
                        left_grad[row * left.shape[1] + inner] += (
                            grad_value * right.data[inner * right.shape[1] + column]
                        )
                        right_grad[inner * right.shape[1] + column] += (
                            grad_value * left.data[row * left.shape[1] + inner]
                        )
            results = [(left_ref, left_grad), (right_ref, right_grad)]
            bias_value = argument(2, "bias")
            if name == "linear" and isinstance(bias_value, TensorValueRef):
                bias_ref = bias_value
                bias = self._tensor(bias_ref)
                bias_grad = [0.0] * len(bias.data)
                for index, grad_value in enumerate(upstream):
                    bias_grad[index % right.shape[1]] += grad_value
                results.append((bias_ref, bias_grad))
            return results

        if name == "dot":
            left_ref, left = tensor(0, "left")
            right_ref, right = tensor(1, "right")
            grad_value = upstream[0]
            return [
                (left_ref, [grad_value * item for item in right.data]),
                (right_ref, [grad_value * item for item in left.data]),
            ]

        if name == "norm":
            reference, source = tensor(0, "value")
            order = int(argument(1, "order", 2))
            if order == 1:
                values = [
                    upstream[0]
                    * (1.0 if item > 0 else (-1.0 if item < 0 else 0.0))
                    for item in source.data
                ]
            else:
                denominator = output.data[0]
                values = [
                    upstream[0] * item / denominator if denominator else 0.0
                    for item in source.data
                ]
            return [(reference, values)]

        if name in {"concat", "stack"}:
            references = argument(0, "values")
            if not isinstance(references, list) or not all(
                isinstance(item, TensorValueRef) for item in references
            ):
                raise TensorError("AD-004", f"{name} gradient inputs are unavailable")
            axis = int(argument(1, "axis", 0))
            if name == "stack":
                rank = len(self._tensor(references[0]).shape) + 1
                normalized = _normalize_axis(axis, rank)
                results = []
                for position, reference in enumerate(references):
                    source = self._tensor(reference)
                    values = []
                    for coordinate in _all_coords(source.shape):
                        out_coordinate = (
                            coordinate[:normalized]
                            + (position,)
                            + coordinate[normalized:]
                        )
                        values.append(
                            upstream[_flat_index(out_coordinate, output.shape)]
                        )
                    results.append((reference, values))
                return results
            normalized = _normalize_axis(axis, len(output.shape))
            offset = 0
            results = []
            for reference in references:
                source = self._tensor(reference)
                values = []
                for coordinate in _all_coords(source.shape):
                    out_coordinate = list(coordinate)
                    out_coordinate[normalized] += offset
                    values.append(
                        upstream[_flat_index(tuple(out_coordinate), output.shape)]
                    )
                results.append((reference, values))
                offset += source.shape[normalized]
            return results

        if name == "softmax":
            reference, source = tensor(0, "value")
            axis = int(argument(1, "axis", -1))
            normalized = _normalize_axis(axis, len(source.shape))
            values = [0.0] * len(source.data)
            groups: dict[tuple[int, ...], list[int]] = {}
            for index in range(len(source.data)):
                coordinate = _coords(index, source.shape)
                key = coordinate[:normalized] + coordinate[normalized + 1 :]
                groups.setdefault(key, []).append(index)
            for indexes in groups.values():
                dot = sum(upstream[i] * output.data[i] for i in indexes)
                for i in indexes:
                    values[i] = output.data[i] * (upstream[i] - dot)
            return [(reference, values)]

        if name in {"slice", "narrow"}:
            reference, source = tensor(0, "value")
            values = [0.0] * len(source.data)
            if name == "narrow":
                start = int(argument(2, "start"))
                starts, ends, axes, steps = [start], [start + int(argument(3, "length"))], [int(argument(1, "axis"))], [1]
            else:
                starts = list(argument(1, "starts"))
                ends = list(argument(2, "ends"))
                axes_value = argument(3, "axes")
                steps_value = argument(4, "steps")
                axes = list(axes_value) if axes_value is not None else list(range(len(starts)))
                steps = list(steps_value) if steps_value is not None else [1] * len(starts)
            ranges = [list(range(size)) for size in source.shape]
            for start, end, axis, step in zip(starts, ends, axes, steps):
                normalized = _normalize_axis(axis, len(source.shape))
                ranges[normalized] = list(
                    range(*builtins.slice(start, end, step).indices(source.shape[normalized]))
                )
            for grad_value, coordinate in zip(upstream, _coordinate_product(ranges)):
                values[_flat_index(coordinate, source.shape)] += grad_value
            return [(reference, values)]

        if name == "gather":
            reference, source = tensor(0, "value")
            _, index_tensor = tensor(1, "indices")
            axis = int(argument(2, "axis", 0))
            normalized = _normalize_axis(axis, len(source.shape))
            values = [0.0] * len(source.data)
            for out_index, out_coordinate in enumerate(_all_coords(output.shape)):
                before = out_coordinate[:normalized]
                index_coordinate = out_coordinate[
                    normalized : normalized + len(index_tensor.shape)
                ]
                after = out_coordinate[normalized + len(index_tensor.shape) :]
                selected = int(
                    index_tensor.data[
                        _flat_index(index_coordinate, index_tensor.shape)
                    ]
                )
                if selected < 0:
                    selected += source.shape[normalized]
                values[
                    _flat_index(before + (selected,) + after, source.shape)
                ] += upstream[out_index]
            return [(reference, values)]

        if name == "conv2d":
            return self._conv2d_vjp(node, upstream)
        if name in {"max_pool2d", "avg_pool2d"}:
            return self._pool2d_vjp(node, upstream, maximum=name == "max_pool2d")
        raise TensorError("AD-004", f"gradient is not implemented for {name}")

    def _conv2d_vjp(
        self, node: _GradNode, upstream: list[float]
    ) -> list[tuple[TensorValueRef, list[float]]]:
        args = node.arguments
        def argument(index: int, name: str, default: Any = None) -> Any:
            return args[index] if len(args) > index else node.attributes.get(name, default)

        input_ref, weight_ref = argument(0, "input"), argument(1, "weight")
        assert isinstance(input_ref, TensorValueRef)
        assert isinstance(weight_ref, TensorValueRef)
        source, kernel = self._tensor(input_ref), self._tensor(weight_ref)
        bias_ref = argument(2, "bias")
        stride = argument(3, "stride", [1, 1])
        padding = argument(4, "padding", [0, 0])
        dilation = argument(5, "dilation", [1, 1])
        groups = int(argument(6, "groups", 1))
        stride_h, stride_w = _positive_pair(stride, "conv2d stride")
        pad_h, pad_w = _nonnegative_pair(padding, "conv2d padding")
        dilation_h, dilation_w = _positive_pair(dilation, "conv2d dilation")
        batch, in_channels, in_h, in_w = source.shape
        out_channels, kernel_channels, kernel_h, kernel_w = kernel.shape
        output = self.backend.load(node.output_id)
        _, _, out_h, out_w = output.shape
        channels_per_group = out_channels // groups
        source_grad = [0.0] * len(source.data)
        kernel_grad = [0.0] * len(kernel.data)
        bias_grad = [0.0] * out_channels
        for n in range(batch):
            for out_channel in range(out_channels):
                group = out_channel // channels_per_group
                for out_y in range(out_h):
                    for out_x in range(out_w):
                        grad_value = upstream[
                            _flat_index(
                                (n, out_channel, out_y, out_x), output.shape
                            )
                        ]
                        bias_grad[out_channel] += grad_value
                        for local_channel in range(kernel_channels):
                            in_channel = group * kernel_channels + local_channel
                            for kernel_y in range(kernel_h):
                                input_y = (
                                    out_y * stride_h
                                    - pad_h
                                    + kernel_y * dilation_h
                                )
                                if input_y < 0 or input_y >= in_h:
                                    continue
                                for kernel_x in range(kernel_w):
                                    input_x = (
                                        out_x * stride_w
                                        - pad_w
                                        + kernel_x * dilation_w
                                    )
                                    if input_x < 0 or input_x >= in_w:
                                        continue
                                    input_index = _flat_index(
                                        (n, in_channel, input_y, input_x),
                                        source.shape,
                                    )
                                    weight_index = _flat_index(
                                        (
                                            out_channel,
                                            local_channel,
                                            kernel_y,
                                            kernel_x,
                                        ),
                                        kernel.shape,
                                    )
                                    source_grad[input_index] += (
                                        grad_value * kernel.data[weight_index]
                                    )
                                    kernel_grad[weight_index] += (
                                        grad_value * source.data[input_index]
                                    )
        results = [(input_ref, source_grad), (weight_ref, kernel_grad)]
        if isinstance(bias_ref, TensorValueRef):
            results.append((bias_ref, bias_grad))
        return results

    def _pool2d_vjp(
        self,
        node: _GradNode,
        upstream: list[float],
        *,
        maximum: bool,
    ) -> list[tuple[TensorValueRef, list[float]]]:
        args = node.arguments
        def argument(index: int, name: str, default: Any = None) -> Any:
            return args[index] if len(args) > index else node.attributes.get(name, default)

        input_ref = argument(0, "input")
        assert isinstance(input_ref, TensorValueRef)
        source = self._tensor(input_ref)
        kernel = argument(1, "kernel")
        stride = argument(2, "stride") or kernel
        padding = argument(3, "padding", [0, 0])
        include_pad = bool(argument(4, "count_include_pad", False))
        kernel_h, kernel_w = _positive_pair(kernel, "pool2d kernel")
        stride_h, stride_w = _positive_pair(stride, "pool2d stride")
        pad_h, pad_w = _nonnegative_pair(padding, "pool2d padding")
        output = self.backend.load(node.output_id)
        batch, channels, in_h, in_w = source.shape
        _, _, out_h, out_w = output.shape
        values = [0.0] * len(source.data)
        for n in range(batch):
            for channel in range(channels):
                for out_y in range(out_h):
                    for out_x in range(out_w):
                        grad_value = upstream[
                            _flat_index(
                                (n, channel, out_y, out_x), output.shape
                            )
                        ]
                        indexes = []
                        for kernel_y in range(kernel_h):
                            input_y = out_y * stride_h - pad_h + kernel_y
                            for kernel_x in range(kernel_w):
                                input_x = out_x * stride_w - pad_w + kernel_x
                                if 0 <= input_y < in_h and 0 <= input_x < in_w:
                                    indexes.append(
                                        _flat_index(
                                            (n, channel, input_y, input_x),
                                            source.shape,
                                        )
                                    )
                        if maximum:
                            selected = max(indexes, key=lambda index: source.data[index])
                            values[selected] += grad_value
                        else:
                            divisor = (
                                kernel_h * kernel_w if include_pad else len(indexes)
                            )
                            for index in indexes:
                                values[index] += grad_value / divisor
        return [(input_ref, values)]

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

    def load_artifact(self, metadata: dict[str, Any]) -> TensorValueRef:
        """Validate and load an external Tensor artifact into this session."""
        try:
            shape = tuple(metadata["shape"])
            dtype = str(metadata["dtype"])
        except (KeyError, TypeError, ValueError) as error:
            raise TensorError("TSF-020", "Invalid external Tensor metadata") from error
        if "inline_data" in metadata:
            literal_shape, flat = _shape_and_flat(metadata["inline_data"])
            if literal_shape != shape:
                raise TensorError("TSF-003", "External Tensor shape mismatch")
            return self._new(shape, dtype, flat)
        storage_ref = metadata.get("storage_ref")
        if not isinstance(storage_ref, str):
            raise TensorError("TSF-020", "External Tensor storage reference is missing")
        try:
            payload = Path(storage_ref).read_bytes()
        except OSError as error:
            raise TensorError("TSF-020", "External Tensor artifact cannot be read") from error
        expected = metadata.get("checksum")
        actual = f"sha256:{hashlib.sha256(payload).hexdigest()}"
        if expected != actual:
            raise TensorError("TSF-020", "External Tensor checksum mismatch")
        if metadata.get("byte_size") not in {None, len(payload)}:
            raise TensorError("TSF-020", "External Tensor byte size mismatch")
        try:
            values = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TensorError("TSF-020", "External Tensor payload is invalid") from error
        if not isinstance(values, list) or len(values) != _product(shape):
            raise TensorError("TSF-003", "External Tensor shape mismatch")
        return self._new(shape, dtype, values)


def _nested(data: list[Any], shape: tuple[int, ...]) -> Any:
    if not shape:
        return data[0]
    step = _product(shape[1:])
    return [_nested(data[i : i + step], shape[1:]) for i in range(0, len(data), step)]


def _promote(a: str, b: str) -> str:
    order = ["bool", "i32", "i64", "f32", "f64"]
    return order[max(order.index(a), order.index(b))]


def _all_coords(shape: tuple[int, ...]):
    return product(*(range(size) for size in shape))


def _coordinate_product(ranges: list[list[int]]):
    return product(*ranges)


def _broadcast_coords(
    output_coords: tuple[int, ...], input_shape: tuple[int, ...]
) -> tuple[int, ...]:
    if not input_shape:
        return ()
    offset = len(output_coords) - len(input_shape)
    return tuple(
        0 if size == 1 else output_coords[offset + index]
        for index, size in enumerate(input_shape)
    )


def _positive_pair(value: Any, label: str) -> tuple[int, int]:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or any(not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in value)
    ):
        raise TensorError("TSF-024", f"{label} must contain two positive integers")
    return int(value[0]), int(value[1])


def _nonnegative_pair(value: Any, label: str) -> tuple[int, int]:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or any(not isinstance(item, int) or isinstance(item, bool) or item < 0 for item in value)
    ):
        raise TensorError("TSF-024", f"{label} must contain two non-negative integers")
    return int(value[0]), int(value[1])


def _random_unit(function: str, seed: int, stream: int, counter: int) -> float:
    if (
        not isinstance(seed, int)
        or isinstance(seed, bool)
        or not isinstance(stream, int)
        or isinstance(stream, bool)
        or seed < 0
        or stream < 0
    ):
        raise TensorError("RNG-001", "seed and stream must be non-negative integers")
    digest = hashlib.sha256(
        f"reasonscript-rng/1\0{function}\0{seed}\0{stream}\0{counter}".encode()
    ).digest()
    integer = int.from_bytes(digest[:8], "little") >> 11
    return integer / float(1 << 53)


def _tensor_references(value: Any):
    if isinstance(value, TensorValueRef):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _tensor_references(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _tensor_references(item)


_DTYPE_STRUCT = {
    "bool": "?",
    "i32": "i",
    "i64": "q",
    "f32": "f",
    "f64": "d",
}


def _pack_tensor_data(tensor: _Tensor) -> bytes:
    try:
        code = _DTYPE_STRUCT[tensor.dtype]
        return struct.pack("<" + code * len(tensor.data), *tensor.data)
    except (KeyError, struct.error, OverflowError) as error:
        raise TensorError("TIO-003", "Tensor payload cannot be encoded") from error


def _unpack_tensor_data(dtype: str, payload: bytes) -> list[Any]:
    if dtype not in _DTYPE_STRUCT:
        raise TensorError("TSF-002", f"unsupported dtype: {dtype}")
    width = DTYPE_BYTES[dtype]
    if len(payload) % width:
        raise TensorError("TIO-003", "Tensor payload alignment is invalid")
    try:
        return list(
            struct.unpack("<" + _DTYPE_STRUCT[dtype] * (len(payload) // width), payload)
        )
    except struct.error as error:
        raise TensorError("TIO-003", "Tensor payload cannot be decoded") from error


def tensor_function_contracts() -> dict[str, TensorFunctionContract]:
    """Public accessor for the frozen Tensor Standard Functions contract set."""
    return _contracts()


def _contracts() -> dict[str, TensorFunctionContract]:
    v02_functions = {
        "slice",
        "narrow",
        "gather",
        "random_uniform",
        "random_normal",
        "random_bernoulli",
        "random_permutation",
        "load",
        "save",
        "parameter",
        "detach",
        "requires_grad",
        "grad",
        "conv2d",
        "max_pool2d",
        "avg_pool2d",
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
    result = {}
    for policy, names in groups.items():
        for name in names.split():
            inputs = (
                ("value",)
                if name not in {"create", "zeros", "ones", "full"}
                else ("data_or_shape",)
            )
            result[f"tensor.{name}"] = TensorFunctionContract(
                f"tensor.{name}",
                inputs,
                _contract_output(name),
                policy,
                argument_contract=_argument_contract(name),
                return_contract=_return_contract(name),
                backend_operation=name,
                version="0.2" if name in v02_functions else "0.1",
                side_effects=name in {"load", "save"},
                diagnostic_policy=(
                    "TIO"
                    if name in {"load", "save"}
                    else (
                        "RNG"
                        if name.startswith("random_")
                        else (
                            "AD"
                            if name
                            in {"parameter", "detach", "requires_grad", "grad"}
                            else "TSF"
                        )
                    )
                ),
                lowering_policy=(
                    "primitive_or_native"
                    if name
                    in {
                        "relu",
                        "softmax",
                        "linear",
                        "conv2d",
                        "max_pool2d",
                        "avg_pool2d",
                    }
                    else "native"
                ),
            )
    return result


def _contract_output(name: str) -> str:
    if name == "grad":
        return "Array<Tensor>"
    if name == "requires_grad":
        return "Bool"
    if name == "save":
        return "TensorArtifactReceipt"
    if name == "shape":
        return "Array<Int>"
    if name in {"rank", "size", "dimension"}:
        return "Int"
    if name == "dtype":
        return "String"
    if name == "scalar":
        return "Scalar"
    if name == "to_array":
        return "Array"
    return "Tensor"


def _return_contract(name: str) -> dict[str, Any]:
    output = _contract_output(name)
    if output == "Tensor":
        return {"kind": "tensor", "shape": "inferred", "dtype": "inferred"}
    if output == "Array<Tensor>":
        return {"kind": "array", "element_kind": "tensor"}
    return {"kind": output.lower()}


def _argument_contract(name: str) -> tuple[dict[str, Any], ...]:
    if name == "create":
        return (
            {"name": "values", "kind": "nested_numeric", "required": True},
            {"name": "dtype", "kind": "dtype", "required": False},
            {"name": "device", "kind": "string", "required": False},
        )
    if name == "softmax":
        return (
            {"name": "input", "kind": "tensor", "required": True},
            {"name": "axis", "kind": "int", "required": False, "default": -1},
        )
    if name == "linear":
        return (
            {"name": "input", "kind": "tensor", "required": True},
            {"name": "weight", "kind": "tensor", "required": True},
            {"name": "bias", "kind": "tensor", "required": False},
        )
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
            result.append(
                {"name": "count_include_pad", "kind": "bool", "required": False}
            )
        return tuple(result)
    if name == "grad":
        return (
            {"name": "loss", "kind": "tensor", "required": True},
            {"name": "parameters", "kind": "tensor_array", "required": True},
        )
    return ()


def create_tensor_runtime() -> TensorRuntime:
    return TensorRuntime()
