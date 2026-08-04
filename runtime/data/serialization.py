"""JSON-safe, deterministic public serialization for data-analysis results."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .backend import DataBackend
from .model import DataError, DatasetRef, MissingValue, Table

RESULT_SCHEMA_VERSION = "reasonscript-titanic-analysis-result/1.0"


def _json_value(value: Any, path: str = "result") -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DataError("DAF-SER-009", "Non-finite float in result envelope", path=path)
        return value
    if isinstance(value, MissingValue):
        return _json_value(value.to_dict(), path)
    if isinstance(value, Enum):
        return _json_value(value.value, path)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item, f"{path}.{key}") for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if is_dataclass(value):
        return _json_value(asdict(value), path)
    raise DataError("DAF-SER-009", f"Unsupported custom value: {type(value).__name__}", path=path)


def serialize_backend_metadata(backend: DataBackend) -> dict[str, str]:
    if not isinstance(backend, DataBackend):
        raise DataError("DAF-SER-005", "Backend metadata serialization failed")
    return {"id": "python-reference", "version": "0.1",
            "implementation": "runtime.data.backend.DataBackend"}


def serialize_dataset_ref(dataset: DatasetRef, table: Table, *, project_root: str | Path | None = None) -> dict[str, Any]:
    source_path = dataset.source_path
    if source_path is not None:
        candidate = Path(source_path)
        root = Path(project_root).resolve() if project_root is not None else None
        if candidate.is_absolute() and root is not None:
            try: source_path = candidate.resolve().relative_to(root).as_posix()
            except ValueError: source_path = candidate.name
        else:
            source_path = candidate.as_posix()
    return {"dataset_id": dataset.dataset_id, "source_kind": dataset.source_kind,
            "source_path": source_path, "sha256": dataset.sha256, "size_bytes": dataset.size_bytes,
            "row_count": table.row_count, "column_count": len(dataset_columns(table)),
            "schema_id": dataset.schema_id}


def dataset_columns(table: Table) -> tuple[Any, ...]:
    return tuple(column for column in table.columns if not column.derived_from)


def serialize_table_summary(table: Table) -> dict[str, Any]:
    if not isinstance(table, Table):
        raise DataError("DAF-SER-002", "Table serialization failed")
    columns = [{"column_id": column.column_id, "name": column.name, "dtype": column.dtype.value.split(".")[-1],
                "nullable": column.nullable, "position": column.position} for column in table.columns]
    return {"table_id": table.table_id, "row_count": table.row_count, "column_count": table.column_count,
            "schema_id": table.schema.schema_id, "columns": columns,
            "source_ref": table.source_ref.dataset_id,
            "provenance_ref": table.provenance[-1]["operation_id"] if table.provenance else None,
            "artifact": "table.json"}


def serialize_knowledge(knowledge: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    try: return _json_value(list(knowledge), "knowledge")
    except DataError as error: raise DataError("DAF-SER-003", error.message, **error.details) from error


def serialize_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    try: return _json_value(evidence, "evidence")
    except DataError as error: raise DataError("DAF-SER-004", error.message, **error.details) from error


def serialize_analysis_result(*, status: str, input_mode: str, backend: DataBackend, table: Table,
                              metrics: Mapping[str, Any], knowledge: Sequence[Mapping[str, Any]],
                              evidence: Mapping[str, Any], project_root: str | Path | None = None,
                              diagnostics: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    result = {"schema_version": RESULT_SCHEMA_VERSION, "status": status, "input_mode": input_mode,
              "backend": serialize_backend_metadata(backend),
              "dataset": serialize_dataset_ref(table.source_ref, table, project_root=project_root),
              "table": serialize_table_summary(table), "metrics": _json_value(metrics, "metrics"),
              "knowledge": serialize_knowledge(knowledge), "evidence": serialize_evidence(evidence),
              "diagnostics": _json_value(list(diagnostics), "diagnostics")}
    validate_analysis_result(result)
    return result


def canonicalize_analysis_result(result: Mapping[str, Any]) -> dict[str, Any]:
    value = _json_value(result)
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))


def validate_analysis_result(result: Mapping[str, Any]) -> None:
    required = ("schema_version", "status", "input_mode", "backend", "dataset", "table", "metrics",
                "knowledge", "evidence", "diagnostics")
    if result.get("schema_version") != RESULT_SCHEMA_VERSION or any(key not in result for key in required):
        raise DataError("DAF-SER-006", "Public result schema validation failed")
    if result.get("status") not in {"pass", "error"}:
        raise DataError("DAF-SER-006", "Public result status is invalid", path="status")
    try: json.dumps(_json_value(result), ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise DataError("DAF-SER-001", "Public result contains a non-serializable value") from error
