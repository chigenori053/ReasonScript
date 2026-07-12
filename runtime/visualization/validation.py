"""Visualization contract, resource, and encoding validation."""
from __future__ import annotations
from runtime.data import DataType, Table
from .model import VisualizationError, VisualizationSpec

CHART_TYPES = {"line", "bar", "bar_horizontal", "scatter", "histogram", "box", "pie", "grouped_bar",
               "stacked_bar", "area", "heatmap", "error_bar", "distribution", "correlation_matrix"}
MISSING_POLICIES = {"reject", "drop", "zero", "category", "interpolate"}
NUMERIC = {DataType.INT, DataType.FLOAT}


def validate(spec: VisualizationSpec, table: Table | None = None) -> list[dict]:
    try: validate_or_raise(spec, table)
    except VisualizationError as error: return [error.diagnostic()]
    return []


def validate_or_raise(spec: VisualizationSpec, table: Table | None = None) -> None:
    if spec.chart_type not in CHART_TYPES: raise VisualizationError("VSL-ENC-003", "Unsupported chart type")
    if spec.missing_policy not in MISSING_POLICIES: raise VisualizationError("VSL-MIS-001", "Missing policy required")
    if not (1 <= spec.render.width <= 8192 and 1 <= spec.render.height <= 8192 and 1 <= spec.render.dpi <= 600):
        raise VisualizationError("VSL-RND-004", "Invalid image dimensions")
    if any(fmt not in {"png", "svg"} for fmt in spec.render.formats):
        raise VisualizationError("VSL-RND-003", "Unsupported output format")
    if spec.encoding.bins is not None and not 1 <= spec.encoding.bins <= 1000:
        raise VisualizationError("VSL-RES-002", "Invalid histogram bin count")
    if table is None: return
    fields = {field.name: field for field in table.schema.fields}
    names = [x for x in (spec.encoding.x, spec.encoding.y, spec.encoding.category, spec.encoding.value, spec.encoding.group) if x]
    for name in names:
        if name not in fields: raise VisualizationError("VSL-SRC-003", f"Column not found: {name}")
    numeric_names = []
    if spec.chart_type in {"line", "scatter", "area", "error_bar"}: numeric_names.append(spec.encoding.y)
    if spec.chart_type == "heatmap": numeric_names.append(spec.encoding.value)
    if spec.chart_type in {"histogram", "box", "distribution"}: numeric_names.append(spec.encoding.value or spec.encoding.x)
    if spec.chart_type in {"bar", "bar_horizontal", "grouped_bar", "stacked_bar", "pie"}: numeric_names.append(spec.encoding.value or spec.encoding.y)
    for name in filter(None, numeric_names):
        if fields[name].dtype not in NUMERIC: raise VisualizationError("VSL-TYPE-001", f"Numeric field required: {name}")
