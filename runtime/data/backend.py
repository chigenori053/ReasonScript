"""Standard-library-only Python reference backend for tabular analysis."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Any, Callable, Iterable, Mapping, Sequence

from .model import (AggregationSpec, Column, DataError, DataType, DatasetRef, Field, Group, GroupedTable,
                    MissingValue, ResourceLimits, Row, Schema, Table, canonical_json, is_missing, stable_id)


class DataBackend:
    def __init__(self, *, project_root: str | Path = ".", limits: ResourceLimits | None = None,
                 lineage_level: str = "aggregate"):
        self.project_root = Path(project_root).resolve()
        self.limits = limits or ResourceLimits()
        if lineage_level not in {"none", "aggregate", "full"}:
            raise DataError("DAF-PRV-003", f"Unsupported lineage level: {lineage_level}")
        self.lineage_level = lineage_level

    def load_csv(self, path: str | Path, schema: Schema | None = None, options: Mapping[str, Any] | None = None) -> Table:
        opts = {"delimiter": ",", "quote": '"', "escape": None, "encoding": "utf-8", "has_header": True,
                "null_values": [], "trim_whitespace": False, "strict_columns": True, "infer_schema": False,
                "max_rows": None, **dict(options or {})}
        source = self._safe_path(path)
        payload = self._read_source(source)
        try:
            text = payload.decode(opts["encoding"])
        except (LookupError, UnicodeDecodeError) as error:
            raise DataError("DAF-SRC-002", f"Unsupported encoding: {opts['encoding']}") from error
        try:
            reader = csv.reader(text.splitlines(), delimiter=opts["delimiter"], quotechar=opts["quote"],
                                escapechar=opts["escape"], strict=True)
            records = list(reader)
        except csv.Error as error:
            raise DataError("DAF-SRC-003", f"Invalid CSV: {error}") from error
        if not records:
            header, values = [], []
        elif opts["has_header"]:
            header, values = records[0], records[1:]
        else:
            values = records
            width = len(values[0]) if values else len(schema.fields) if schema else 0
            header = [f"column_{i + 1}" for i in range(width)]
        if opts["trim_whitespace"]:
            header = [x.strip() for x in header]
            values = [[x.strip() for x in row] for row in values]
        effective_limit = min(self.limits.max_rows, opts["max_rows"] or self.limits.max_rows)
        if len(values) > effective_limit:
            raise DataError("DAF-RES-001", "Maximum rows exceeded", actual=len(values), limit=effective_limit)
        schema = schema or self._infer_schema(header, values, enabled=opts["infer_schema"])
        if schema.strict and tuple(header) != tuple(f.name for f in schema.fields):
            raise DataError("DAF-TBL-004", "CSV header does not match schema")
        nulls = set(opts["null_values"])
        raw = [dict(zip(header, row)) for row in values]
        if opts["strict_columns"] and any(len(row) != len(header) for row in values):
            raise DataError("DAF-TBL-003", "Row length mismatch")
        return self._from_records(raw, schema, source_kind="csv", source_path=str(Path(path)), payload=payload,
                                  source_numbers=range(2 if opts["has_header"] else 1, len(raw) + (2 if opts["has_header"] else 1)),
                                  null_values=nulls | {""})

    def load_json(self, path: str | Path, schema: Schema | None = None, options: Mapping[str, Any] | None = None) -> Table:
        source = self._safe_path(path); payload = self._read_source(source)
        try: value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DataError("DAF-SRC-004", f"Invalid JSON records: {error}") from error
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise DataError("DAF-SRC-004", "JSON source must be an array of objects")
        if len(value) > self.limits.max_rows: raise DataError("DAF-RES-001", "Maximum rows exceeded")
        schema = schema or self._infer_records(value, enabled=bool((options or {}).get("infer_schema", False)))
        return self._from_records(value, schema, source_kind="json", source_path=str(Path(path)), payload=payload,
                                  source_numbers=range(1, len(value) + 1), null_values={None})

    def from_external(self, external_value: Mapping[str, Any] | Sequence[Mapping[str, Any]], schema: Schema | None = None) -> Table:
        if isinstance(external_value, Mapping):
            if external_value.get("version") != "reasonscript-external-table/0.1":
                raise DataError("DAF-TBL-004", "Invalid external table contract version")
            records = external_value.get("records")
        else: records = external_value
        if not isinstance(records, Sequence) or not all(isinstance(x, Mapping) for x in records):
            raise DataError("DAF-TBL-005", "External table records are invalid")
        schema = schema or self._infer_records(records, enabled=True)
        payload = canonical_json(records).encode()
        return self._from_records(records, schema, source_kind="external", source_path=None, payload=payload,
                                  source_numbers=range(1, len(records) + 1), null_values={None})

    def inspect(self, table: Table, head: int = 5) -> dict[str, Any]:
        return {"row_count": table.row_count, "column_count": table.column_count, "columns": list(table.column_names),
                "schema": table.schema.to_dict(), "head": [table.row_dict(r) for r in table.rows[:head]]}

    def select(self, table: Table, columns: Sequence[str]) -> Table:
        indices = [table.column_names.index(name) if name in table.column_names else self._unknown(name) for name in columns]
        fields = tuple(table.schema.field(name) for name in columns); schema = Schema(fields)
        rows = [tuple(row.values[i] for i in indices) for row in table.rows]
        return self._derived(table, "select", rows, schema, referenced_columns=columns, expression=list(columns))

    def filter(self, table: Table, predicate: Callable[[Mapping[str, Any]], bool], *, name: str | None = None,
               referenced_columns: Sequence[str] = ()) -> Table:
        kept = []
        for row in table.rows:
            result = predicate(table.row_dict(row))
            if not isinstance(result, bool): raise DataError("DAF-OP-002", "Filter must return bool")
            if result: kept.append(row.values)
        return self._derived(table, "filter", kept, table.schema, referenced_columns=referenced_columns,
                             expression=name or getattr(predicate, "__name__", "predicate"),
                             extra={"predicate_name": name or getattr(predicate, "__name__", "predicate"),
                                    "input_row_count": table.row_count, "output_row_count": len(kept)})

    def map(self, table: Table, mapper: Callable[[Mapping[str, Any]], Mapping[str, Any]], *, name: str | None = None) -> Table:
        output = []
        for row in table.rows:
            value = mapper(table.row_dict(row))
            if not isinstance(value, Mapping) or set(value.keys()) != set(table.column_names):
                raise DataError("DAF-OP-003", "Mapper returned invalid row")
            output.append(tuple(self._validate_value(value[f.name], f) for f in table.schema.fields))
        return self._derived(table, "map", output, table.schema, referenced_columns=table.column_names,
                             expression=name or getattr(mapper, "__name__", "mapper"))

    def derive_column(self, table: Table, name: str, dtype: DataType | str, nullable: bool,
                      evaluator: Callable[[Mapping[str, Any]], Any], *, referenced_columns: Sequence[str] = (),
                      expression: str | None = None) -> Table:
        if name in table.column_names: raise DataError("DAF-OP-005", f"Duplicate derived column: {name}")
        field = Field(name, dtype, nullable, table.column_count)
        output = []
        for row in table.rows:
            try: value = self._validate_value(evaluator(table.row_dict(row)), field)
            except DataError as error: raise DataError("DAF-OP-004", f"Derived column type mismatch: {name}") from error
            output.append((*row.values, value))
        schema = Schema((*table.schema.fields, field))
        return self._derived(table, "derive_column", output, schema, referenced_columns=referenced_columns,
                             expression=expression or getattr(evaluator, "__name__", name), extra={"output_column": name})

    def rename_column(self, table: Table, old_name: str, new_name: str) -> Table:
        if old_name not in table.column_names: self._unknown(old_name)
        if new_name in table.column_names: raise DataError("DAF-TBL-001", f"Duplicate column name: {new_name}")
        fields = tuple(Field(new_name if f.name == old_name else f.name, f.dtype, f.nullable, f.position,
                             f.default, f.missing_policy) for f in table.schema.fields)
        return self._derived(table, "rename_column", [r.values for r in table.rows], Schema(fields),
                             referenced_columns=(old_name,), expression={"old": old_name, "new": new_name})

    def count_missing(self, table: Table, column: str) -> int:
        index = self._column_index(table, column); return sum(is_missing(r.values[index]) for r in table.rows)

    def missing_rate(self, table: Table, column: str) -> float:
        return self.count_missing(table, column) / table.row_count if table.row_count else 0.0

    def drop_missing(self, table: Table, columns: Sequence[str], mode: str = "any") -> Table:
        if mode not in {"any", "all"}: raise DataError("DAF-MIS-003", f"Unsupported missing mode: {mode}")
        indices = [self._column_index(table, x) for x in columns]
        rows = [r.values for r in table.rows if not (any if mode == "any" else all)(is_missing(r.values[i]) for i in indices)]
        return self._derived(table, "drop_missing", rows, table.schema, referenced_columns=columns, expression=mode)

    def fill_missing(self, table: Table, column: str, value: Any) -> Table:
        index = self._column_index(table, column); field = table.schema.field(column)
        try: value = self._validate_value(value, Field(field.name, field.dtype, False, field.position))
        except DataError as error: raise DataError("DAF-MIS-002", f"Invalid fill type for {column}") from error
        rows = [tuple(value if i == index and is_missing(x) else x for i, x in enumerate(r.values)) for r in table.rows]
        return self._derived(table, "fill_missing", rows, table.schema, referenced_columns=(column,), expression=value)

    def group_by(self, table: Table, keys: Sequence[str]) -> GroupedTable:
        indices = [self._column_index(table, key) for key in keys]; buckets: dict[tuple[Any, ...], list[Row]] = {}
        for row in table.rows: buckets.setdefault(tuple(row.values[i] for i in indices), []).append(row)
        if len(buckets) > self.limits.max_groups: raise DataError("DAF-AGG-003", "Group limit exceeded")
        groups = tuple(Group(key, tuple(rows), stable_id("rows", [r.row_id for r in rows]))
                       for key, rows in sorted(buckets.items(), key=lambda item: tuple(self._sort_key(v) for v in item[0])))
        provenance = self._operation(table, "group_by", keys, list(keys), {"group_count": len(groups)})
        return GroupedTable(stable_id("grp", table.table_id, list(keys)), table, tuple(keys), groups, provenance)

    def aggregate(self, value: Table | GroupedTable, specs: Sequence[AggregationSpec]) -> Table:
        table = value.source if isinstance(value, GroupedTable) else value
        groups = value.groups if isinstance(value, GroupedTable) else (Group((), table.rows, stable_id("rows", [r.row_id for r in table.rows])),)
        keys = value.key_columns if isinstance(value, GroupedTable) else ()
        output_fields = [table.schema.field(key) for key in keys]
        for spec in specs:
            source = table.schema.field(spec.source_column) if spec.source_column else None
            if spec.operation != "count" and (source is None or source.dtype not in {DataType.INT, DataType.FLOAT}):
                raise DataError("DAF-AGG-001", "Numeric aggregation requires numeric column")
            dtype = DataType.INT if spec.operation == "count" or (spec.operation == "sum" and source.dtype == DataType.INT) else source.dtype
            nullable = spec.operation in {"mean", "median", "min", "max"}
            output_fields.append(Field(spec.output_column, dtype, nullable, len(output_fields)))
        output_rows = []
        aggregation_refs = []
        for group in groups:
            results = []
            for spec in specs:
                raw = list(group.rows) if spec.source_column is None else [r.values[self._column_index(table, spec.source_column)] for r in group.rows]
                missing_count = sum(is_missing(x) for x in raw)
                if missing_count and spec.missing_policy == "error": raise DataError("DAF-MIS-003", "Missing value in aggregation")
                present = [x for x in raw if not is_missing(x)]
                result = self._aggregate_values(spec.operation, present, len(raw) if spec.missing_policy == "include" else len(present))
                results.append(result)
                aggregation_refs.append({"operation": spec.operation, "source_column": spec.source_column,
                    "output_column": spec.output_column, "input_count": len(raw), "missing_count": missing_count,
                    "missing_policy": spec.missing_policy, "result": result, "group_key": list(group.group_key)})
            output_rows.append((*group.group_key, *results))
        schema = Schema(tuple(output_fields))
        result = self._derived(table, "aggregate", output_rows, schema, referenced_columns=tuple(filter(None, (s.source_column for s in specs))),
                               expression=[s.__dict__ for s in specs], extra={"group_id": getattr(value, "group_id", None),
                               "aggregation_refs": aggregation_refs})
        return result

    def count(self, table: Table, column: str | None = None, missing_policy: str = "skip") -> int:
        return self._scalar(table, AggregationSpec("count", column, "value", missing_policy))
    def sum(self, table: Table, column: str, missing_policy: str = "skip") -> Any:
        return self._scalar(table, AggregationSpec("sum", column, "value", missing_policy))
    def mean(self, table: Table, column: str, missing_policy: str = "skip") -> Any:
        return self._scalar(table, AggregationSpec("mean", column, "value", missing_policy))
    def median(self, table: Table, column: str, missing_policy: str = "skip") -> Any:
        return self._scalar(table, AggregationSpec("median", column, "value", missing_policy))
    def min(self, table: Table, column: str, missing_policy: str = "skip") -> Any:
        return self._scalar(table, AggregationSpec("min", column, "value", missing_policy))
    def max(self, table: Table, column: str, missing_policy: str = "skip") -> Any:
        return self._scalar(table, AggregationSpec("max", column, "value", missing_policy))

    def provenance(self, table: Table) -> dict[str, Any]:
        return {"version": "0.1", "schema": "reasonscript-data-provenance/0.1", "dataset_refs": [table.source_ref.to_dict()],
                "column_refs": [c.to_dict() for c in table.columns], "operation_refs": [dict(x) for x in table.provenance],
                "lineage_level": self.lineage_level, "source_digest": table.source_ref.sha256}

    def evidence(self, table: Table, *, operation_refs: Sequence[str] = (), group_refs: Sequence[Any] = (),
                 aggregation_refs: Sequence[Any] = ()) -> dict[str, Any]:
        columns = sorted({name for op in table.provenance for name in op.get("referenced_columns", [])})
        basis = [table.source_ref.dataset_id, list(operation_refs), columns, list(group_refs), self.lineage_level]
        return {"evidence_id": stable_id("evd", *basis), "dataset_refs": [table.source_ref.dataset_id],
                "column_refs": [c.column_id for c in table.columns if c.name in columns], "operation_refs": list(operation_refs),
                "filter_refs": [op["operation_id"] for op in table.provenance if op["operation_type"] == "filter"],
                "group_refs": list(group_refs), "aggregation_refs": list(aggregation_refs),
                "lineage_level": self.lineage_level, "source_digest": table.source_ref.sha256}

    def serialize_table(self, table: Table) -> str:
        result = table.serialize()
        if len(result.encode("utf-8")) > self.limits.max_artifact_bytes:
            raise DataError("DAF-RES-005", "Maximum artifact size exceeded")
        return result
    def serialize_provenance(self, table: Table) -> str:
        result = json.dumps(self.provenance(table), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if len(result.encode("utf-8")) > self.limits.max_artifact_bytes:
            raise DataError("DAF-RES-005", "Maximum artifact size exceeded")
        return result
    def explain(self, table: Table) -> tuple[Mapping[str, Any], ...]: return table.provenance
    def lineage(self, table: Table) -> dict[str, Any]:
        if self.lineage_level == "full":
            if table.row_count > self.limits.max_lineage_rows: raise DataError("DAF-PRV-004", "Lineage row limit exceeded")
            return {"level": "full", "row_ids": [r.row_id for r in table.rows]}
        return {"level": self.lineage_level, "row_count": table.row_count,
                "row_digest": stable_id("rows", [r.row_id for r in table.rows])}

    def _safe_path(self, path: str | Path) -> Path:
        candidate = (self.project_root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
        if candidate != self.project_root and self.project_root not in candidate.parents:
            raise DataError("DAF-SRC-005", "Path escapes project root")
        if not candidate.is_file(): raise DataError("DAF-SRC-001", f"File not found: {path}")
        return candidate

    def _read_source(self, path: Path) -> bytes:
        size = path.stat().st_size
        if size > self.limits.max_file_bytes: raise DataError("DAF-SRC-006", "File size limit exceeded")
        return path.read_bytes()

    def _from_records(self, records: Sequence[Mapping[str, Any]], schema: Schema, *, source_kind: str,
                      source_path: str | None, payload: bytes, source_numbers: Iterable[int], null_values: set[Any]) -> Table:
        if len(schema.fields) > self.limits.max_columns: raise DataError("DAF-RES-002", "Maximum columns exceeded")
        digest = hashlib.sha256(payload).hexdigest(); dataset_id = stable_id("ds", source_kind, digest, schema.schema_id)
        source = DatasetRef(dataset_id, source_kind, source_path, digest, len(payload), source_kind, schema.schema_id)
        columns = tuple(Column(stable_id("col", dataset_id, f.name, f.position), f.name, f.position, f.dtype, f.nullable, dataset_id) for f in schema.fields)
        rows = []
        for ordinal, (record, number) in enumerate(zip(records, source_numbers)):
            if schema.strict and set(record) != {f.name for f in schema.fields}: raise DataError("DAF-TBL-003", "Row fields mismatch")
            preliminary = [self._convert(record.get(f.name), f, null_values) for f in schema.fields]
            row_id = stable_id("row", dataset_id, number, preliminary)
            values = tuple(MissingValue(v.reason, v.source_token, columns[i].column_id, row_id) if is_missing(v) else v for i, v in enumerate(preliminary))
            rows.append(Row(row_id, ordinal, values, number))
        table_id = stable_id("tbl", dataset_id, schema.schema_id, [r.row_id for r in rows])
        provenance = ({"operation_id": stable_id("op", dataset_id, "load"), "operation_type": "load",
                       "source_path": source_path, "input_row_count": len(rows), "output_row_count": len(rows),
                       "referenced_columns": list(f.name for f in schema.fields)},)
        return Table(table_id, schema, tuple(rows), columns, source, provenance, {"format": source_kind})

    def _convert(self, value: Any, field: Field, null_values: set[Any]) -> Any:
        if value in null_values:
            if not field.nullable: raise DataError("DAF-MIS-001", f"Missing in non-nullable column: {field.name}")
            return MissingValue("empty_field" if value == "" else "explicit_null", None if value is None else str(value))
        try:
            if field.dtype == DataType.STRING: converted = str(value)
            elif field.dtype == DataType.INT:
                if isinstance(value, bool): raise ValueError
                converted = int(value)
                if isinstance(value, float) and value != converted: raise ValueError
            elif field.dtype == DataType.FLOAT: converted = float(value)
            elif field.dtype == DataType.BOOL:
                if isinstance(value, bool): converted = value
                elif str(value).lower() in {"true", "1"}: converted = True
                elif str(value).lower() in {"false", "0"}: converted = False
                else: raise ValueError
            elif field.dtype == DataType.NULL: converted = MissingValue("explicit_null")
            else: raise ValueError
            return self._validate_value(converted, field)
        except (ValueError, TypeError, OverflowError) as error:
            raise DataError("DAF-TBL-002", f"Invalid value for {field.name}: {value!r}") from error

    def _validate_value(self, value: Any, field: Field) -> Any:
        if is_missing(value):
            if not field.nullable: raise DataError("DAF-MIS-001", f"Missing in non-nullable column: {field.name}")
            return value
        valid = ((field.dtype == DataType.INT and isinstance(value, int) and not isinstance(value, bool)) or
                 (field.dtype == DataType.FLOAT and isinstance(value, (int, float)) and not isinstance(value, bool)) or
                 (field.dtype == DataType.BOOL and isinstance(value, bool)) or
                 (field.dtype == DataType.STRING and isinstance(value, str)))
        if not valid: raise DataError("DAF-TBL-002", f"Invalid value for {field.name}")
        if isinstance(value, float) and not math.isfinite(value): raise DataError("DAF-TBL-005", "NaN and Infinity are unsupported")
        if len(str(value).encode()) > self.limits.max_cell_bytes: raise DataError("DAF-RES-003", "Maximum cell size exceeded")
        return float(value) if field.dtype == DataType.FLOAT else value

    def _derived(self, source: Table, kind: str, values: Sequence[Sequence[Any]], schema: Schema, *,
                 referenced_columns: Sequence[str], expression: Any, extra: Mapping[str, Any] | None = None) -> Table:
        if len(source.provenance) >= self.limits.max_operations: raise DataError("DAF-RES-004", "Maximum operations exceeded")
        extra = dict(extra or {})
        op = self._operation(source, kind, referenced_columns, expression, {"output_row_count": len(values), **extra})
        table_id = stable_id("tbl", source.table_id, op["operation_id"], schema.schema_id, values)
        columns = tuple(Column(stable_id("col", table_id, f.name, f.position), f.name, f.position, f.dtype, f.nullable,
                               source.source_ref.dataset_id, tuple(referenced_columns) if kind == "derive_column" and f.name == extra.get("output_column") else ())
                        for f in schema.fields)
        rows = tuple(Row(stable_id("row", table_id, i, row), i, tuple(row), None) for i, row in enumerate(values))
        return Table(table_id, schema, rows, columns, source.source_ref, (*source.provenance, op), source.metadata)

    def _operation(self, table: Table, kind: str, columns: Sequence[str], expression: Any, extra: Mapping[str, Any]) -> dict[str, Any]:
        basis = [table.table_id, kind, list(columns), expression, extra]
        return {"operation_id": stable_id("op", *basis), "operation_type": kind, "input_table_id": table.table_id,
                "referenced_columns": list(columns), "expression": expression, "input_row_count": table.row_count, **dict(extra)}

    def _infer_schema(self, header: Sequence[str], rows: Sequence[Sequence[Any]], *, enabled: bool) -> Schema:
        records = [dict(zip(header, row)) for row in rows]; return self._infer_records(records, enabled=enabled)

    def _infer_records(self, records: Sequence[Mapping[str, Any]], *, enabled: bool) -> Schema:
        names = list(records[0].keys()) if records else []
        fields = []
        for i, name in enumerate(names):
            values = [r.get(name) for r in records]; nullable = any(v is None or v == "" for v in values)
            dtype = DataType.STRING
            if enabled:
                present = [v for v in values if v is not None and v != ""]
                if present and all(self._looks_bool(v) for v in present): dtype = DataType.BOOL
                elif present and all(self._looks_int(v) for v in present): dtype = DataType.INT
                elif present and all(self._looks_float(v) for v in present): dtype = DataType.FLOAT
            fields.append(Field(name, dtype, nullable, i))
        return Schema(tuple(fields), inference_policy="validated" if enabled else "string_fallback")

    @staticmethod
    def _looks_bool(v: Any) -> bool: return isinstance(v, bool) or str(v).lower() in {"true", "false"}
    @staticmethod
    def _looks_int(v: Any) -> bool:
        try: return str(int(v)) == str(v) or isinstance(v, int)
        except (ValueError, TypeError): return False
    @staticmethod
    def _looks_float(v: Any) -> bool:
        try: return math.isfinite(float(v))
        except (ValueError, TypeError): return False
    @staticmethod
    def _sort_key(value: Any) -> tuple[Any, ...]:
        if isinstance(value, bool): return (0, value)
        if isinstance(value, int): return (1, value)
        if isinstance(value, float): return (2, value)
        if isinstance(value, str): return (3, value)
        return (4, canonical_json(value))
    @staticmethod
    def _aggregate_values(operation: str, values: list[Any], count: int) -> Any:
        if operation == "count": return count
        if operation == "sum": return sum(values) if values else 0
        if not values: return MissingValue("empty_input")
        return {"mean": statistics.fmean, "median": statistics.median, "min": min, "max": max}[operation](values)
    def _scalar(self, table: Table, spec: AggregationSpec) -> Any:
        return self.aggregate(table, (spec,)).rows[0].values[0]
    def _column_index(self, table: Table, name: str) -> int:
        if name not in table.column_names: return self._unknown(name)
        return table.column_names.index(name)
    @staticmethod
    def _unknown(name: str): raise DataError("DAF-OP-001", f"Unknown column: {name}")
