# Per-file Diagnostics Contract

Extends `diagnostics_pipeline_mapping.md` for workspace file-backed
analysis.

## `relative_path` on diagnostics

When `POST /api/analyze` is called with `source_context.relative_path`
set, every diagnostic in the response's `diagnostics` array is stamped
with that same `relative_path`:

```json
{
  "code": "CAL-020",
  "message": "undefined variable",
  "severity": "error",
  "stage": "semantic_ast",
  "source_range": { "start_line": 3, "start_col": 14, "end_line": 3, "end_col": 21 },
  "relative_path": "examples/test.rsn"
}
```

When no `source_context` is given (temporary-source mode), diagnostics are
returned exactly as in the Phase 2 contract — no `relative_path` field is
added, preserving `analyze_api_contract.md` unchanged for existing
callers.

## Frontend filtering

The frontend does not currently maintain diagnostics for multiple files
simultaneously in a single view — the `results` state (and therefore the
Diagnostics tab) always reflects whichever file is currently selected
(`editor_state_contract.md`). `relative_path` on each diagnostic exists so
that any future multi-file or workspace-wide diagnostics summary (PFD-005,
not implemented in Phase 3) can attribute diagnostics correctly without a
schema change.

## Stage mapping unchanged

Diagnostic-to-pipeline-stage classification (`_stage_for_diagnostic` in
`playground/backend/main.py`) is untouched by Phase 3 — only the
`relative_path` field is added on top.
