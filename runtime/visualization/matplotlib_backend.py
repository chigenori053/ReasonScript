"""Optional Matplotlib reference renderer with deterministic policy."""
from __future__ import annotations
from dataclasses import asdict
from io import BytesIO
import hashlib, importlib.util
from pathlib import Path
from typing import Any
from runtime.data import Table
from .backend import VisualizationBackend
from .model import VisualizationArtifact, VisualizationError, VisualizationSpec
from .operations import chart_data
from .provenance import evidence
from .serialization import export_spec
from .validation import validate_or_raise


class MatplotlibBackend(VisualizationBackend):
    id = "matplotlib"
    def __init__(self, *, project_root: str | Path = "."):
        self.project_root = Path(project_root).resolve()

    def available(self) -> bool: return importlib.util.find_spec("matplotlib") is not None

    def render(self, spec: VisualizationSpec, table: Table, output_dir: str | Path) -> dict[str, Any]:
        validate_or_raise(spec, table)
        if not self.available(): raise VisualizationError("VSL-RND-001", "Matplotlib backend unavailable")
        target = (self.project_root / output_dir).resolve() if not Path(output_dir).is_absolute() else Path(output_dir).resolve()
        if target != self.project_root and self.project_root not in target.parents:
            raise VisualizationError("VSL-ART-003", "Path traversal rejected")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        payload = chart_data(spec, table); rendered: dict[str, bytes] = {}
        try:
            with matplotlib.rc_context({"svg.hashsalt": "reasonscript-vsl-0.1", "font.family": "DejaVu Sans"}):
                fig, ax = plt.subplots(figsize=(spec.render.width/spec.render.dpi, spec.render.height/spec.render.dpi), dpi=spec.render.dpi)
                self._draw(ax, spec, payload)
                self._style(ax, spec)
                fig.tight_layout()
                for fmt in spec.render.formats:
                    stream = BytesIO(); metadata = {"Creator": "ReasonScript VSL 0.1"}
                    if fmt == "svg": metadata["Date"] = None
                    fig.savefig(stream, format=fmt, dpi=spec.render.dpi, metadata=metadata)
                    data = stream.getvalue()
                    if len(data) > 100 * 1024 * 1024: raise VisualizationError("VSL-RES-004", "Artifact size limit exceeded")
                    rendered[fmt] = data
                plt.close(fig)
        except VisualizationError: raise
        except Exception as error: raise VisualizationError("VSL-RND-002", f"Render failed: {error}") from error
        target.mkdir(parents=True, exist_ok=True)
        artifacts = []
        for fmt, data in rendered.items():
            path = target / f"chart.{fmt}"; path.write_bytes(data)
            artifacts.append(VisualizationArtifact(fmt, path.relative_to(self.project_root).as_posix(), hashlib.sha256(data).hexdigest(), len(data)))
        digests = {a.format: a.sha256 for a in artifacts}; ev = evidence(spec, table, self.id, digests)
        return {"schema_version": "reasonscript-visualization-result/0.1", "status": "pass",
                "visualization_id": spec.visualization_id,
                "backend": {"id": self.id, "version": matplotlib.__version__},
                "chart": {"type": spec.chart_type, "title": spec.title.text},
                "artifacts": [asdict(a) for a in artifacts], "evidence_refs": [ev.evidence_id],
                "diagnostics": [], "evidence": asdict(ev)}

    @staticmethod
    def _draw(ax, spec, data):
        kind = spec.chart_type
        if kind in {"histogram", "distribution"}:
            if data.get("groups"):
                for group in data["groups"]: ax.hist(group["values"], bins=spec.encoding.bins or 20, alpha=.55, label=group["name"])
            else: ax.hist(data["values"], bins=spec.encoding.bins or 20)
        elif kind == "box": ax.boxplot(data["values"])
        elif kind in {"heatmap", "correlation_matrix"}:
            image = ax.imshow(data["matrix"], aspect="auto", interpolation="nearest")
            ax.set_xticks(range(len(data["x"])), [str(x) for x in data["x"]]); ax.set_yticks(range(len(data["y"])), [str(y) for y in data["y"]])
            ax.figure.colorbar(image, ax=ax)
        elif kind == "pie":
            series = data["series"][0];
            if any(v < 0 for v in series["y"]): raise VisualizationError("VSL-ENC-003", "Pie values must be non-negative")
            ax.pie(series["y"], labels=[str(x) for x in series["x"]], autopct="%1.1f%%")
        else:
            series = data["series"]; width = .8 / max(1, len(series))
            for index, item in enumerate(series):
                label = item["name"]
                if kind in {"line", "error_bar"}: ax.errorbar(item["x"], item["y"], yerr=item.get("errors") or None, label=label)
                elif kind == "scatter": ax.scatter(item["x"], item["y"], label=label)
                elif kind == "area": ax.fill_between(item["x"], item["y"], label=label, alpha=.7)
                elif kind == "bar_horizontal": ax.barh(item["x"], item["y"], label=label)
                elif kind == "stacked_bar": ax.bar(item["x"], item["y"], label=label, bottom=[sum(s["y"][j] for s in series[:index]) for j in range(len(item["y"]))])
                else:
                    positions = [j - .4 + width/2 + index*width for j in range(len(item["x"]))]
                    ax.bar(positions, item["y"], width=width, label=label); ax.set_xticks(range(len(item["x"])), [str(x) for x in item["x"]])

    @staticmethod
    def _style(ax, spec):
        ax.set_title(spec.title.text)
        if spec.x_axis.label: ax.set_xlabel(spec.x_axis.label)
        if spec.y_axis.label: ax.set_ylabel(spec.y_axis.label)
        if spec.x_axis.minimum is not None or spec.x_axis.maximum is not None: ax.set_xlim(spec.x_axis.minimum, spec.x_axis.maximum)
        if spec.y_axis.minimum is not None or spec.y_axis.maximum is not None: ax.set_ylim(spec.y_axis.minimum, spec.y_axis.maximum)
        ax.grid(spec.x_axis.grid or spec.y_axis.grid)
        handles, _ = ax.get_legend_handles_labels()
        if spec.legend.visible and handles: ax.legend(title=spec.legend.title)
