"""Projection of Data Foundation values into canonical ReasonScript artifacts."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from runtime.data import DataBackend, Table, stable_id


DATA_ARTIFACT_SCHEMAS = {
    "table.json": "reasonscript-table/0.1",
    "table_schema.json": "reasonscript-table-schema/0.1",
    "data_source.json": "reasonscript-data-source/0.1",
    "data_operations.json": "reasonscript-data-operations/0.1",
    "aggregation.json": "reasonscript-aggregation/0.1",
    "data_provenance.json": "reasonscript-data-provenance/0.1",
    "data_evidence.json": "reasonscript-data-evidence/0.1",
    "titanic_analysis_result.json": "reasonscript-titanic-analysis-result/1.0",
}


def data_artifacts(table: Table, backend: DataBackend, *, knowledge: Sequence[Mapping[str, Any]] = (),
                   analysis_result: Mapping[str, Any] | None = None) -> dict[str, Any]:
    operations = [dict(item) for item in table.provenance]
    aggregations = [ref for item in operations for ref in item.get("aggregation_refs", [])]
    evidence = backend.evidence(table, operation_refs=[item["operation_id"] for item in operations],
                                aggregation_refs=[stable_id("agg", item) for item in aggregations])
    artifacts = {
        "table.json": table.to_dict(),
        "table_schema.json": table.schema.to_dict(),
        "data_source.json": table.source_ref.to_dict(),
        "data_operations.json": {"operations": operations},
        "aggregation.json": {"aggregations": aggregations},
        "data_provenance.json": backend.provenance(table),
        "data_evidence.json": evidence,
        "reason_ir.json": {"data_units": _reason_ir_units(table, evidence)},
        "execution_plan.json": {"steps": _execution_steps(operations, knowledge)},
        "simulation.json": {"events": _simulation_events(table, operations, knowledge)},
        "knowledge.json": {"items": [_knowledge_item(item, table, evidence) for item in knowledge]},
    }
    if analysis_result is not None:
        artifacts["titanic_analysis_result.json"] = dict(analysis_result)
    return artifacts


def _reason_ir_units(table: Table, evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    units = [{"unit_type": "DataSourceUnit", "function": f"data.load_{table.source_ref.format}",
              "path": table.source_ref.source_path, "format": table.source_ref.format,
              "schema_ref": table.schema.schema_id, "dataset_ref": table.source_ref.dataset_id}]
    for op in table.provenance[1:]:
        units.append({"unit_type": "AggregationUnit" if op["operation_type"] == "aggregate" else "TableOperationUnit",
                      **dict(op)})
    units.append({"unit_type": "DataEvidenceUnit", **dict(evidence)})
    return units


def _execution_steps(operations: Sequence[Mapping[str, Any]], knowledge: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    steps = []
    for index, operation in enumerate(operations):
        kind = operation["operation_type"]
        steps.append({"step_id": operation["operation_id"], "ordinal": index,
                      "kind": f"step.data.{kind}" if kind == "load" else f"step.table.{kind}", "status": "completed"})
    for item in knowledge:
        steps.append({"step_id": stable_id("step", "knowledge", item.get("knowledge_id")), "ordinal": len(steps),
                      "kind": "step.knowledge.emit", "status": "completed"})
    return steps


def _simulation_events(table: Table, operations: Sequence[Mapping[str, Any]], knowledge: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    events = [{"event": "dataset_loaded", "dataset_id": table.source_ref.dataset_id},
              {"event": "schema_validated", "schema_id": table.schema.schema_id},
              {"event": "table_shape", "row_count": table.row_count, "column_count": table.column_count}]
    for op in operations:
        events.extend(({"event": "operation_start", "operation_id": op["operation_id"]},
                       {"event": "operation_end", "operation_id": op["operation_id"],
                        "input_row_count": op.get("input_row_count"), "output_row_count": op.get("output_row_count")}))
    events.extend({"event": "knowledge_emission", "knowledge_id": item.get("knowledge_id")} for item in knowledge)
    return events


def _knowledge_item(item: Mapping[str, Any], table: Table, evidence: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(item)
    value.setdefault("knowledge_id", stable_id("kn", value.get("statement"), value.get("value")))
    value.setdefault("unit", None); value.setdefault("confidence", 1.0)
    value.setdefault("evidence_refs", [evidence["evidence_id"]]); value.setdefault("dataset_refs", [table.source_ref.dataset_id])
    return value
