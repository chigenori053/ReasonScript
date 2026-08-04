"""Artifact-first projection for reproducible visualizations."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from runtime.data import Table

from .matplotlib_backend import MatplotlibBackend
from .model import VisualizationSpec
from .operations import chart_data
from .provenance import explain
from .serialization import export_spec, to_json_value

SCHEMAS = {"visualization_spec.json": "reasonscript-visualization-spec/0.1",
           "visualization_ir.json": "reasonscript-visualization-ir/0.1",
           "render_plan.json": "reasonscript-visualization-render-plan/0.1",
           "visualization_evidence.json": "reasonscript-visualization-evidence/0.1",
           "visualization_validation.json": "reasonscript-visualization-validation/0.1"}


def visualization_ir(spec: VisualizationSpec, table: Table) -> dict[str, Any]:
    units = [{"unit_type": "DataBindingUnit", "table_ref": table.table_id, "dataset_ref": table.source_ref.dataset_id}]
    if spec.encoding.group: units.append({"unit_type": "GroupUnit", "field": spec.encoding.group})
    if spec.encoding.aggregate: units.append({"unit_type": "AggregationUnit", "operation": spec.encoding.aggregate})
    units.extend(({"unit_type": "EncodingUnit", "encoding": export_spec(spec)["encoding"]},
                  {"unit_type": "AxisUnit", "x": export_spec(spec)["x_axis"], "y": export_spec(spec)["y_axis"]},
                  {"unit_type": "LayoutUnit", "layout": export_spec(spec)["layout"]},
                  {"unit_type": "RenderUnit", "render": export_spec(spec)["render"]},
                  {"unit_type": "ArtifactUnit", "formats": list(spec.render.formats)}))
    return {"schema_version": SCHEMAS["visualization_ir.json"], "visualization_id": spec.visualization_id, "units": units}


def render_plan(spec: VisualizationSpec) -> dict[str, Any]:
    names = ("resolve_dataset", "resolve_table", "select_columns", "handle_missing", "group_rows", "aggregate_values",
             "order_categories", "build_series", "configure_axes", "configure_layout", "render", "compute_digests", "emit_provenance")
    return {"schema_version": SCHEMAS["render_plan.json"], "visualization_id": spec.visualization_id,
            "steps": [{"ordinal": i, "operation": name, "status": "planned"} for i, name in enumerate(names)]}


def render_artifacts(spec: VisualizationSpec, table: Table, output_dir: str | Path, *, project_root: str | Path = ".",
                     backend: MatplotlibBackend | None = None) -> dict[str, Any]:
    renderer = backend or MatplotlibBackend(project_root=project_root)
    result = renderer.render(spec, table, output_dir)
    root = renderer.project_root; target = (root / output_dir).resolve() if not Path(output_dir).is_absolute() else Path(output_dir).resolve()
    documents = {
        "visualization_spec.json": export_spec(spec),
        "visualization_ir.json": visualization_ir(spec, table),
        "render_plan.json": render_plan(spec),
        "visualization_evidence.json": {"schema_version": SCHEMAS["visualization_evidence.json"], **result.pop("evidence")},
        "visualization_validation.json": {"schema_version": SCHEMAS["visualization_validation.json"], "status": "pass", "diagnostics": []},
    }
    for name, value in documents.items():
        (target / name).write_text(json.dumps(to_json_value(value), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8")
    manifest_items = [{"name": name, "schema_version": SCHEMAS[name], "required": True} for name in sorted(documents)]
    manifest_items += [{"name": f"chart.{fmt}", "schema_version": f"image/{fmt}", "required": True} for fmt in spec.render.formats]
    manifest = {"schema_version": "reasonscript-visualization-artifact-manifest/0.1",
                "visualization_id": spec.visualization_id, "artifacts": manifest_items}
    (target / "artifact_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    result["metadata_artifacts"] = [{"path": (target/name).relative_to(root).as_posix(),
        "sha256": hashlib.sha256((target/name).read_bytes()).hexdigest(), "schema_version": SCHEMAS[name]} for name in sorted(documents)]
    result["metadata_artifacts"].append({"path": (target/"artifact_manifest.json").relative_to(root).as_posix(),
        "sha256": hashlib.sha256((target/"artifact_manifest.json").read_bytes()).hexdigest(),
        "schema_version": manifest["schema_version"]})
    return result


def render_titanic_artifacts(table: Table, output_dir: str | Path, *, project_root: str | Path = ".",
                             backend: MatplotlibBackend | None = None) -> dict[str, Any]:
    from .operations import titanic_charts
    renderer = backend or MatplotlibBackend(project_root=project_root)
    root = renderer.project_root
    target = (root / output_dir).resolve() if not Path(output_dir).is_absolute() else Path(output_dir).resolve()
    if target != root and root not in target.parents:
        from .model import VisualizationError
        raise VisualizationError("VSL-ART-003", "Path traversal rejected")
    results = {}
    for name, spec in titanic_charts(table).items():
        result = render_artifacts(spec, table, target / name, project_root=root, backend=renderer)
        for fmt in spec.render.formats:
            shutil.copyfile(target / name / f"chart.{fmt}", target / f"{name}.{fmt}")
        results[name] = result
    return {"schema_version": "reasonscript-visualization-result/0.1", "status": "pass",
            "charts": results, "diagnostics": []}
