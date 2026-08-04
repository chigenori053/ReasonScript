"""Immutable, deterministic table model for Data Analysis Foundation v0.1."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str)


def stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(canonical_json(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:24]}"


class DataType(str, Enum):
    INT = "data.int"
    FLOAT = "data.float"
    BOOL = "data.bool"
    STRING = "data.string"
    NULL = "data.null"

    @classmethod
    def parse(cls, value: DataType | str) -> DataType:
        if isinstance(value, cls):
            return value
        aliases = {"int": cls.INT, "float": cls.FLOAT, "bool": cls.BOOL, "string": cls.STRING, "null": cls.NULL}
        try:
            return aliases[value] if value in aliases else cls(value)
        except ValueError as error:
            raise DataError("DAF-TBL-002", f"Invalid column type: {value}") from error


@dataclass(frozen=True)
class MissingValue:
    reason: str
    source_token: str | None = None
    column_id: str | None = None
    row_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"missing": True, "reason": self.reason, "source_token": self.source_token,
                "column_id": self.column_id, "row_id": self.row_id}


Missing = MissingValue("explicit_null")
CellValue = int | float | bool | str | MissingValue


class DataError(ValueError):
    def __init__(self, code: str, message: str, **details: Any):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.details = code, message, details

    def to_diagnostic(self) -> dict[str, Any]:
        return {"code": self.code, "severity": "fatal", "message": self.message, "details": self.details}


@dataclass(frozen=True)
class Field:
    name: str
    dtype: DataType | str
    nullable: bool = False
    position: int = 0
    default: CellValue | None = None
    missing_policy: str = "skip"

    def __post_init__(self) -> None:
        object.__setattr__(self, "dtype", DataType.parse(self.dtype))

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "dtype": self.dtype.value, "nullable": self.nullable,
                "position": self.position, "default": encode_cell(self.default), "missing_policy": self.missing_policy}


@dataclass(frozen=True)
class Schema:
    fields: tuple[Field, ...]
    strict: bool = True
    inference_policy: str = "explicit"
    schema_id: str = ""

    def __post_init__(self) -> None:
        fields = tuple(self.fields)
        names = [item.name for item in fields]
        if len(names) != len(set(names)):
            raise DataError("DAF-TBL-001", "Duplicate column name")
        normalized = tuple(Field(f.name, f.dtype, f.nullable, i, f.default, f.missing_policy) for i, f in enumerate(fields))
        object.__setattr__(self, "fields", normalized)
        if not self.schema_id:
            object.__setattr__(self, "schema_id", stable_id("sch", [f.to_dict() for f in normalized], self.strict, self.inference_policy))

    @classmethod
    def from_mapping(cls, fields: Mapping[str, Any], *, strict: bool = True) -> Schema:
        values = []
        for i, (name, spec) in enumerate(fields.items()):
            if isinstance(spec, (str, DataType)):
                values.append(Field(name, spec, False, i))
            else:
                values.append(Field(name, spec["dtype"], bool(spec.get("nullable", False)), i,
                                    spec.get("default"), spec.get("missing_policy", "skip")))
        return cls(tuple(values), strict=strict)

    def field(self, name: str) -> Field:
        for item in self.fields:
            if item.name == name:
                return item
        raise DataError("DAF-OP-001", f"Unknown column: {name}")

    def to_dict(self) -> dict[str, Any]:
        return {"schema_id": self.schema_id, "fields": [f.to_dict() for f in self.fields],
                "strict": self.strict, "inference_policy": self.inference_policy}


@dataclass(frozen=True)
class DatasetRef:
    dataset_id: str
    source_kind: str
    source_path: str | None
    sha256: str
    size_bytes: int
    format: str
    schema_id: str
    loaded_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class Column:
    column_id: str
    name: str
    position: int
    dtype: DataType
    nullable: bool
    source_dataset_id: str
    derived_from: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "dtype": self.dtype.value, "derived_from": list(self.derived_from)}


@dataclass(frozen=True)
class Row:
    row_id: str
    ordinal: int
    values: tuple[CellValue, ...]
    source_row_number: int | None

    def to_dict(self, names: tuple[str, ...]) -> dict[str, Any]:
        return {"row_id": self.row_id, "ordinal": self.ordinal, "source_row_number": self.source_row_number,
                "values": {name: encode_cell(value) for name, value in zip(names, self.values)}}


@dataclass(frozen=True)
class ResourceLimits:
    max_rows: int = 100_000
    max_columns: int = 1_000
    max_file_bytes: int = 104_857_600
    max_cell_bytes: int = 1_048_576
    max_groups: int = 10_000
    max_operations: int = 1_000
    max_lineage_rows: int = 10_000
    max_artifact_bytes: int = 104_857_600


@dataclass(frozen=True)
class Table:
    table_id: str
    schema: Schema
    rows: tuple[Row, ...]
    columns: tuple[Column, ...]
    source_ref: DatasetRef
    provenance: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def row_count(self) -> int: return len(self.rows)
    @property
    def column_count(self) -> int: return len(self.columns)
    @property
    def column_names(self) -> tuple[str, ...]: return tuple(c.name for c in self.columns)

    def row_dict(self, row: Row) -> dict[str, CellValue]:
        return dict(zip(self.column_names, row.values))

    def to_dict(self) -> dict[str, Any]:
        return {"table_id": self.table_id, "schema": self.schema.to_dict(), "row_count": self.row_count,
                "column_count": self.column_count, "columns": [c.to_dict() for c in self.columns],
                "rows": [r.to_dict(self.column_names) for r in self.rows], "source_ref": self.source_ref.to_dict(),
                "provenance_ref": [dict(p) for p in self.provenance], "metadata": dict(self.metadata)}

    def to_canonical_dict(self) -> dict[str, Any]:
        return json.loads(canonical_json(self.to_dict()))

    def to_json(self) -> str:
        return json.dumps(self.to_canonical_dict(), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"

    def serialize(self) -> str:
        return self.to_json()


@dataclass(frozen=True)
class AggregationSpec:
    operation: str
    source_column: str | None = None
    output_column: str | None = None
    missing_policy: str = "skip"

    def __post_init__(self) -> None:
        if self.operation not in {"count", "sum", "mean", "median", "min", "max"}:
            raise DataError("DAF-AGG-005", f"Unsupported aggregation: {self.operation}")
        if self.missing_policy not in {"skip", "error", "include"}:
            raise DataError("DAF-MIS-003", f"Unsupported missing policy: {self.missing_policy}")
        if self.missing_policy == "include" and self.operation != "count":
            raise DataError("DAF-MIS-003", "include is only valid for count")
        if not self.output_column:
            object.__setattr__(self, "output_column", f"{self.operation}_{self.source_column or 'all'}")


@dataclass(frozen=True)
class Group:
    group_key: tuple[CellValue, ...]
    rows: tuple[Row, ...]
    row_digest: str


@dataclass(frozen=True)
class GroupedTable:
    group_id: str
    source: Table
    key_columns: tuple[str, ...]
    groups: tuple[Group, ...]
    provenance_ref: Mapping[str, Any]


def encode_cell(value: Any) -> Any:
    if isinstance(value, MissingValue): return value.to_dict()
    if isinstance(value, float) and not math.isfinite(value):
        raise DataError("DAF-TBL-005", "NaN and Infinity are unsupported")
    return value


def is_missing(value: Any) -> bool: return isinstance(value, MissingValue)
def is_present(value: Any) -> bool: return not is_missing(value)
