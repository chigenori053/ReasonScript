"""CLI for native `.rstensor` import, inspection, and verification."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from frontend.language_surface.parser import parse
from toolchain.runtime_dispatch import RustDispatchError, execute_rust_program


class TensorCommandError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _option(args: list[str], name: str) -> str | None:
    if name not in args:
        return None
    index = args.index(name)
    return args[index + 1] if index + 1 < len(args) else None


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path.cwd() / path


def _source_values(path: Path, format_name: str) -> tuple[Any, str | None]:
    if format_name == "json":
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            return value.get("values"), value.get("dtype")
        return value, None
    if format_name == "csv":
        rows = []
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.reader(handle):
                if row:
                    rows.append([float(item) for item in row])
        return rows, None
    if format_name == "npy":
        try:
            import numpy
        except ImportError as error:
            raise TensorCommandError(
                "TIO-006", "NumPy is required for --from npy"
            ) from error
        array = numpy.load(path, allow_pickle=False)
        dtype = {
            "bool": "bool", "int32": "i32", "int64": "i64",
            "float32": "f32", "float64": "f64",
        }.get(str(array.dtype))
        if dtype is None:
            raise TensorCommandError(
                "TIO-006", f"unsupported NumPy dtype: {array.dtype}"
            )
        return array.tolist(), dtype
    raise TensorCommandError(
        "TIO-006", f"unsupported Tensor import format: {format_name}"
    )


def _literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _run_native(source: str, root: Path, *, read: bool, write: bool) -> dict[str, Any]:
    return execute_rust_program(
        parse(source), root, read, write, include_trace=True
    )


def _tensor_metadata(result: dict[str, Any]) -> dict[str, Any]:
    for step in result.get("tensor_trace", []):
        output = step.get("output") if isinstance(step, dict) else None
        if isinstance(output, dict) and "tensor_id" in output:
            return output
    raise TensorCommandError("TIO-006", "native Tensor metadata is unavailable")


def run(args: list[str], root: Path) -> int:
    operations = {"import", "inspect", "verify"}
    if not args or args[0] not in operations:
        print("Usage: reason tensor <import|inspect|verify> ...")
        return 1
    operation = args[0]
    json_output = "--json" in args
    try:
        if operation == "import":
            source_value = _option(args, "--input")
            target_value = _option(args, "--output")
            format_name = _option(args, "--from")
            if not source_value or not target_value or not format_name:
                raise TensorCommandError(
                    "TIO-006",
                    "tensor import requires --from, --input, and --output",
                )
            source, target = _path(source_value), _path(target_value)
            values, inferred_dtype = _source_values(source, format_name)
            dtype = _option(args, "--dtype") or inferred_dtype
            dtype_argument = f", {_literal(dtype)}" if dtype else ""
            native = _run_native(
                "module TensorImport {\n"
                "  calculation Command {\n"
                f"    let value = tensor.create({_literal(values)}{dtype_argument})\n"
                f"    let receipt = tensor.save(value, {_literal(target.name)}, "
                f"{'true' if '--overwrite' in args else 'false'})\n"
                "    result = receipt\n"
                "  }\n"
                "}\n",
                target.parent,
                read=False,
                write=True,
            )
            receipt = native["result"]
            metadata = _tensor_metadata(native)
            result = {
                "command": "import", "ok": True, "source": str(source),
                **receipt, "shape": metadata["shape"], "dtype": metadata["dtype"],
            }
        else:
            if len(args) < 2:
                raise TensorCommandError("TIO-006", "Tensor file path is required")
            source = _path(args[1])
            native = _run_native(
                "module TensorInspect {\n"
                "  calculation Command {\n"
                f"    let value = tensor.load({_literal(source.name)})\n"
                "    result = tensor.size(value)\n"
                "  }\n"
                "}\n",
                source.parent,
                read=True,
                write=False,
            )
            metadata = _tensor_metadata(native)
            shape = metadata["shape"]
            result = {
                "command": operation, "ok": True, "path": str(source),
                "shape": shape, "rank": len(shape), "dtype": metadata["dtype"],
                "byte_size": source.stat().st_size,
            }
    except (OSError, ValueError, TensorCommandError, RustDispatchError) as error:
        if isinstance(error, RustDispatchError):
            code = error.code
        elif isinstance(error, TensorCommandError):
            code = error.code
        else:
            code = "TIO-006"
        result = {
            "command": operation, "ok": False,
            "diagnostics": [{"code": code, "message": str(error)}],
        }
    if json_output:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    elif result["ok"]:
        print(f"Tensor {operation} passed: shape={result.get('shape')} dtype={result.get('dtype')}")
    else:
        diagnostic = result["diagnostics"][0]
        print(f"{diagnostic['code']}: {diagnostic['message']}")
    return 0 if result["ok"] else 1
