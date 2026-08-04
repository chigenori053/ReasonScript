# ReasonScript Visualization Standard Library v0.1

Status: VALIDATED

Specification ID: `reasonscript-visualization-standard-library/0.1`

The `runtime.visualization` module is the `visual.*` public namespace. It defines immutable, JSON-safe,
backend-independent chart specifications and a lazily loaded Matplotlib reference backend. Supported v0.1
charts are line, bar, horizontal bar, scatter, histogram, box, pie, grouped/stacked bar, area, heatmap,
error-bar data, distribution, correlation matrix, and missingness.

Typed `runtime.data.Table` values are validated for column existence, dtype, missing policy, deterministic
ordering, and resource limits. Rendering is confined to a project root and emits PNG/SVG together with
Visualization Spec, IR, Render Plan, Evidence, Validation, and Artifact Manifest JSON documents. Public
render results contain only JSON-safe metadata and artifact references. Matplotlib remains an optional
dependency (`reasonscript[visualization]`), so non-visualization Core execution is unchanged when absent.

Normative schemas are the `schemas/visualization_*.schema.json` documents.
