"""Declarative chart constructors and deterministic Table projection."""
from __future__ import annotations
from dataclasses import replace
from typing import Any, Mapping, Sequence
from runtime.data import Table, is_missing
from .model import (AxisSpec, EncodingSpec, LayoutSpec, LegendSpec, RenderSpec, SeriesSpec, TitleSpec,
                    VisualizationError, VisualizationSpec)
from .validation import validate_or_raise


def create(table: Table, chart_type: str, *, encoding: EncodingSpec, title: str = "", missing_policy: str = "drop",
           render: RenderSpec | None = None, layout: LayoutSpec | None = None) -> VisualizationSpec:
    spec = VisualizationSpec(chart_type, {"table_ref": table.table_id, "dataset_ref": table.source_ref.dataset_id},
        encoding, TitleSpec(title), layout=layout or LayoutSpec(), render=render or RenderSpec(), missing_policy=missing_policy)
    validate_or_raise(spec, table); return spec


def line(table: Table, *, x: str, y: str, title: str = "", group: str | None = None, **kw) -> VisualizationSpec:
    return create(table, "line", encoding=EncodingSpec(x=x, y=y, group=group), title=title, **kw)
def bar(table: Table, *, category: str, value: str, title: str = "", group: str | None = None,
        aggregate: str | None = None, **kw) -> VisualizationSpec:
    return create(table, "bar", encoding=EncodingSpec(category=category, value=value, group=group, aggregate=aggregate), title=title, **kw)
def bar_horizontal(table: Table, **kw) -> VisualizationSpec:
    spec = bar(table, **kw); return replace(spec, chart_type="bar_horizontal", layout=replace(spec.layout, orientation="horizontal"))
def scatter(table: Table, *, x: str, y: str, group: str | None = None, title: str = "", **kw) -> VisualizationSpec:
    return create(table, "scatter", encoding=EncodingSpec(x=x, y=y, group=group), title=title, **kw)
def histogram(table: Table, *, column: str, bins: int = 20, title: str = "", **kw) -> VisualizationSpec:
    return create(table, "histogram", encoding=EncodingSpec(value=column, bins=bins), title=title, **kw)
def box(table: Table, *, value: str, category: str | None = None, title: str = "", **kw) -> VisualizationSpec:
    return create(table, "box", encoding=EncodingSpec(value=value, category=category), title=title, **kw)
def pie(table: Table, *, category: str, value: str, title: str = "", aggregate: str | None = None, **kw) -> VisualizationSpec:
    return create(table, "pie", encoding=EncodingSpec(category=category, value=value, aggregate=aggregate), title=title, **kw)
def area(table: Table, *, x: str, y: str, title: str = "", group: str | None = None, **kw) -> VisualizationSpec:
    return create(table, "area", encoding=EncodingSpec(x=x, y=y, group=group), title=title, **kw)
def heatmap(table: Table, *, x: str, y: str, value: str, title: str = "", aggregate: str | None = "mean", **kw) -> VisualizationSpec:
    return create(table, "heatmap", encoding=EncodingSpec(x=x, y=y, value=value, aggregate=aggregate), title=title, **kw)
def error_bar(table: Table, *, x: str, y: str, title: str = "", group: str | None = None, **kw) -> VisualizationSpec:
    return create(table, "error_bar", encoding=EncodingSpec(x=x, y=y, group=group), title=title, **kw)
def distribution(table: Table, *, column: str, bins: int = 20, title: str = "", **kw) -> VisualizationSpec:
    return create(table, "distribution", encoding=EncodingSpec(value=column, bins=bins), title=title, **kw)
def grouped(table: Table, *, category: str, value: str, group: str, title: str = "", aggregate: str = "mean", **kw):
    return create(table, "grouped_bar", encoding=EncodingSpec(category=category, value=value, group=group, aggregate=aggregate), title=title, **kw)
def stacked(table: Table, *, category: str, value: str, group: str, title: str = "", aggregate: str = "mean", **kw):
    return create(table, "stacked_bar", encoding=EncodingSpec(category=category, value=value, group=group, aggregate=aggregate), title=title, **kw)
def correlation(table: Table, *, columns: Sequence[str] | None = None, title: str = "Correlation Matrix", **kw):
    selected = tuple(columns or [f.name for f in table.schema.fields if f.dtype.value in {"data.int", "data.float"}])
    return create(table, "correlation_matrix", encoding=EncodingSpec(), title=title,
                  layout=LayoutSpec(category_order=selected), **kw)
def missingness(table: Table, *, title: str = "Missing Values", **kw):
    series = SeriesSpec("missing", tuple(table.column_names), tuple(sum(is_missing(r.values[i]) for r in table.rows) for i in range(table.column_count)))
    spec = create(table, "bar", encoding=EncodingSpec(), title=title, **kw)
    return replace(spec, series=(series,))
from_table = create


def titanic_charts(table: Table) -> dict[str, VisualizationSpec]:
    """Seven canonical VSL-0.1 Titanic regressions, without external pre-aggregation."""
    return {
        "titanic_survival_by_sex": bar(table, category="Sex", value="Survived", aggregate="mean", title="Survival Rate by Sex"),
        "titanic_survival_by_class": bar(table, category="Pclass", value="Survived", aggregate="mean", title="Survival Rate by Class"),
        "titanic_age_histogram": histogram(table, column="Age", bins=20, title="Age Distribution"),
        "titanic_fare_histogram": histogram(table, column="Fare", bins=20, title="Fare Distribution"),
        "titanic_sex_class_heatmap": heatmap(table, x="Pclass", y="Sex", value="Survived", title="Survival by Sex and Class"),
        "titanic_family_survival": bar(table, category="FamilySize", value="Survived", aggregate="mean", title="Survival by Family Size"),
        "titanic_missing_values": missingness(table, title="Missing Values"),
    }


def add_series(spec: VisualizationSpec, series: SeriesSpec) -> VisualizationSpec: return replace(spec, series=(*spec.series, series))
def set_title(spec: VisualizationSpec, text: str) -> VisualizationSpec: return replace(spec, title=TitleSpec(text))
def set_x_axis(spec: VisualizationSpec, axis: AxisSpec) -> VisualizationSpec: return replace(spec, x_axis=axis)
def set_y_axis(spec: VisualizationSpec, axis: AxisSpec) -> VisualizationSpec: return replace(spec, y_axis=axis)
def set_legend(spec: VisualizationSpec, legend: LegendSpec) -> VisualizationSpec: return replace(spec, legend=legend)
def set_layout(spec: VisualizationSpec, layout: LayoutSpec) -> VisualizationSpec: return replace(spec, layout=layout)
def set_render(spec: VisualizationSpec, render: RenderSpec) -> VisualizationSpec: return replace(spec, render=render)


def chart_data(spec: VisualizationSpec, table: Table) -> dict[str, Any]:
    validate_or_raise(spec, table)
    if "prepared" in spec.data: return dict(spec.data["prepared"])
    if len(spec.series) > 100: raise VisualizationError("VSL-RES-001", "Too many series")
    if any(max(len(s.x), len(s.y)) > 100_000 for s in spec.series): raise VisualizationError("VSL-RES-001", "Too many data points")
    if spec.series: return {"series": [{"name": s.name, "x": list(s.x), "y": list(s.y), "errors": list(s.errors)} for s in spec.series]}
    names = table.column_names; rows = [dict(zip(names, row.values)) for row in table.rows]
    enc = spec.encoding
    required = [x for x in (enc.x, enc.y, enc.category, enc.value, enc.group) if x]
    interpolation = {name: (sum(values) / len(values) if values else 0) for name in required
                     for values in [[r[name] for r in rows if not is_missing(r[name]) and isinstance(r[name], (int, float))]]}
    clean = []
    for row in rows:
        missing = [name for name in required if is_missing(row[name])]
        if missing and spec.missing_policy == "reject": raise VisualizationError("VSL-MIS-002", "Missing value rejected")
        if missing and spec.missing_policy == "drop": continue
        for name in missing:
            if spec.missing_policy == "zero": row[name] = 0
            elif spec.missing_policy == "interpolate": row[name] = interpolation[name]
            else: row[name] = "__MISSING__"
        clean.append(row)
    if len(clean) > 100_000: raise VisualizationError("VSL-RES-001", "Too many data points")
    if spec.chart_type == "correlation_matrix":
        fields = list(spec.layout.category_order); matrix = []
        for a in fields:
            line_values = []
            for b in fields:
                pairs = [(float(r[a]), float(r[b])) for r in clean if not is_missing(r[a]) and not is_missing(r[b])]
                line_values.append(_correlation(pairs))
            matrix.append(line_values)
        return {"x": fields, "y": fields, "matrix": matrix}
    if spec.chart_type == "heatmap":
        xs, ys = _ordered({r[enc.x] for r in clean}), _ordered({r[enc.y] for r in clean})
        if len(xs) * len(ys) > 1_000_000: raise VisualizationError("VSL-RES-002", "Too many heatmap cells")
        return {"x": xs, "y": ys, "matrix": [[_aggregate([r[enc.value] for r in clean if r[enc.x] == x and r[enc.y] == y], enc.aggregate) for x in xs] for y in ys]}
    if enc.category and enc.value:
        categories = list(spec.layout.category_order) or _ordered({r[enc.category] for r in clean})
        groups = _ordered({r[enc.group] for r in clean}) if enc.group else [None]
        if len(categories) > 10_000: raise VisualizationError("VSL-RES-002", "Too many categories")
        result = {"series": [{"name": str(group) if group is not None else enc.value, "x": categories,
            "y": [_aggregate([r[enc.value] for r in clean if r[enc.category] == category and (group is None or r[enc.group] == group)], enc.aggregate) for category in categories]} for group in groups]}
        if spec.chart_type == "pie" and any(value < 0 for value in result["series"][0]["y"]):
            raise VisualizationError("VSL-ENC-003", "Pie values must be non-negative")
        return result
    value = enc.value or enc.y
    if spec.chart_type in {"histogram", "box", "distribution"}: return {"values": [r[value] for r in clean]}
    groups = _ordered({r[enc.group] for r in clean}) if enc.group else [None]
    return {"series": [{"name": str(g) if g is not None else (value or "series"),
        "x": [r[enc.x] for r in clean if g is None or r[enc.group] == g],
        "y": [r[enc.y] for r in clean if g is None or r[enc.group] == g]} for g in groups]}


def _ordered(values): return sorted(values, key=lambda v: (type(v).__name__, str(v)))
def _aggregate(values, operation):
    if not values: return 0
    if operation in (None, "first"): return values[0]
    if operation == "count": return len(values)
    if operation == "sum": return sum(values)
    if operation == "mean": return sum(values) / len(values)
    if operation == "min": return min(values)
    if operation == "max": return max(values)
    raise VisualizationError("VSL-ENC-004", f"Incompatible aggregation: {operation}")
def _correlation(pairs):
    if len(pairs) < 2: return 0.0
    xs, ys = zip(*pairs); mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
    numerator = sum((x-mx)*(y-my) for x,y in pairs); denominator = (sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys)) ** .5
    return numerator / denominator if denominator else 0.0
