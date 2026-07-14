"""Visualization provenance and evidence projection."""
from __future__ import annotations
from dataclasses import asdict
from typing import Mapping
from runtime.data import Table, stable_id
from .model import VisualizationEvidence, VisualizationSpec
from .serialization import export_spec


def evidence(spec: VisualizationSpec, table: Table, backend: str, digests: Mapping[str, str]) -> VisualizationEvidence:
    fields = tuple(filter(None, (spec.encoding.x, spec.encoding.y, spec.encoding.category, spec.encoding.value, spec.encoding.group)))
    columns = tuple(c.column_id for c in table.columns if c.name in fields)
    operations = tuple(item["operation_id"] for item in table.provenance)
    eid = stable_id("viz_evidence", spec.visualization_id, table.table_id, backend, dict(digests))
    return VisualizationEvidence(eid, table.source_ref.dataset_id, table.table_id, columns, operations,
                                 export_spec(spec)["encoding"], backend, dict(digests))


def explain(spec: VisualizationSpec, table: Table) -> dict:
    return {"visualization_id": spec.visualization_id, "source_dataset": table.source_ref.dataset_id,
            "source_table": table.table_id, "columns": list(filter(None, (spec.encoding.x, spec.encoding.y,
            spec.encoding.category, spec.encoding.value, spec.encoding.group))), "chart_type": spec.chart_type,
            "missing_policy": spec.missing_policy}
provenance = explain
