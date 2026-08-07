"""CLI for canonical `.rstensor` import, inspection, and verification."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from frontend.tensor.runtime import TensorError, TensorRuntime


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
            raise TensorError(
                "TIO-006", "NumPy is required for --from npy"
            ) from error
        array = numpy.load(path, allow_pickle=False)
        dtype = {
            "bool": "bool",
            "int32": "i32",
            "int64": "i64",
            "float32": "f32",
            "float64": "f64",
        }.get(str(array.dtype))
        if dtype is None:
            raise TensorError(
                "TIO-006", f"unsupported NumPy dtype: {array.dtype}"
            )
        return array.tolist(), dtype
    raise TensorError("TIO-006", f"unsupported Tensor import format: {format_name}")


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
                raise TensorError(
                    "TIO-006",
                    "tensor import requires --from, --input, and --output",
                )
            source, target = _path(source_value), _path(target_value)
            values, inferred_dtype = _source_values(source, format_name)
            dtype = _option(args, "--dtype") or inferred_dtype
            runtime = TensorRuntime(
                resource_root=target.parent,
                filesystem_write=True,
            )
            tensor = runtime.create(values, dtype=dtype)
            receipt = runtime.save(
                tensor, target.name, overwrite="--overwrite" in args
            )
            result = {
                "command": "import",
                "ok": True,
                "source": str(source),
                **receipt,
                "shape": list(tensor.shape),
                "dtype": tensor.dtype,
            }
        else:
            if len(args) < 2:
                raise TensorError("TIO-006", "Tensor file path is required")
            source = _path(args[1])
            runtime = TensorRuntime(
                resource_root=source.parent,
                filesystem_read=True,
            )
            tensor = runtime.load(source.name)
            result = {
                "command": operation,
                "ok": True,
                "path": str(source),
                "shape": list(tensor.shape),
                "rank": tensor.rank,
                "dtype": tensor.dtype,
                "byte_size": source.stat().st_size,
            }
    except (OSError, ValueError, TensorError) as error:
        code = (
            error.diagnostic.code
            if isinstance(error, TensorError)
            else "TIO-006"
        )
        result = {
            "command": operation,
            "ok": False,
            "diagnostics": [{"code": code, "message": str(error)}],
        }
    if json_output:
        print(
            json.dumps(
                result,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
        )
    elif result["ok"]:
        print(
            f"Tensor {operation} passed: "
            f"shape={result.get('shape')} dtype={result.get('dtype')}"
        )
    else:
        diagnostic = result["diagnostics"][0]
        print(f"{diagnostic['code']}: {diagnostic['message']}")
    return 0 if result["ok"] else 1
