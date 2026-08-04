"""Immutable, backend-independent Visualization Standard Library models."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from runtime.data import stable_id

SCHEMA_VERSION = "reasonscript-visualization-spec/0.1"


class VisualizationError(ValueError):
    def __init__(self, code: str, message: str, **details: Any):
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.details = code, message, details

    def diagnostic(self) -> dict[str, Any]:
        return {"code": self.code, "severity": "error", "message": self.message, "details": self.details}


@dataclass(frozen=True)
class AxisSpec:
    label: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    numeric_format: str | None = None
    grid: bool = False


@dataclass(frozen=True)
class SeriesSpec:
    name: str
    x: tuple[Any, ...] = ()
    y: tuple[Any, ...] = ()
    errors: tuple[float, ...] = ()


@dataclass(frozen=True)
class EncodingSpec:
    x: str | None = None
    y: str | None = None
    category: str | None = None
    value: str | None = None
    group: str | None = None
    aggregate: str | None = None
    bins: int | None = None


@dataclass(frozen=True)
class LegendSpec:
    visible: bool = True
    title: str | None = None


@dataclass(frozen=True)
class TitleSpec:
    text: str = ""


@dataclass(frozen=True)
class LayoutSpec:
    orientation: str = "vertical"
    category_order: tuple[Any, ...] = ()
    annotations: bool = False


@dataclass(frozen=True)
class RenderSpec:
    width: int = 960
    height: int = 540
    dpi: int = 100
    formats: tuple[str, ...] = ("png", "svg")


@dataclass(frozen=True)
class VisualizationSpec:
    chart_type: str
    data: Mapping[str, Any]
    encoding: EncodingSpec
    title: TitleSpec = field(default_factory=TitleSpec)
    x_axis: AxisSpec = field(default_factory=AxisSpec)
    y_axis: AxisSpec = field(default_factory=AxisSpec)
    legend: LegendSpec = field(default_factory=LegendSpec)
    layout: LayoutSpec = field(default_factory=LayoutSpec)
    render: RenderSpec = field(default_factory=RenderSpec)
    missing_policy: str = "drop"
    series: tuple[SeriesSpec, ...] = ()
    visualization_id: str = ""
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.visualization_id:
            basis = {"chart_type": self.chart_type, "data": dict(self.data), "encoding": asdict(self.encoding),
                     "title": asdict(self.title), "axes": [asdict(self.x_axis), asdict(self.y_axis)],
                     "legend": asdict(self.legend), "layout": asdict(self.layout), "render": asdict(self.render),
                     "missing_policy": self.missing_policy, "series": [asdict(x) for x in self.series]}
            object.__setattr__(self, "visualization_id", stable_id("viz", basis))


ChartSpec = VisualizationSpec


@dataclass(frozen=True)
class VisualizationArtifact:
    format: str
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class VisualizationEvidence:
    evidence_id: str
    dataset_ref: str
    table_ref: str
    column_refs: tuple[str, ...]
    operation_refs: tuple[str, ...]
    encoding: Mapping[str, Any]
    backend: str
    output_digests: Mapping[str, str]


@dataclass(frozen=True)
class VisualizationDiagnostic:
    code: str
    severity: str
    message: str
    path: str | None = None
