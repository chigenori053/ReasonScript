# Artifact Adapter Migration

Status: Phase 4-B DRAFT FOR ADOPTION

Phase 4-B uses an analyze-result backed `ArtifactAdapter`.

No persisted artifact read endpoint is added in this phase. After analyze
completes, the UI registers the latest `ProjectState` with the browser artifact
adapter. The adapter exposes stable descriptors for:

- `ast.json`
- `semantic_ast.json`
- `reason_ir.json`
- `execution_plan.json`
- `simulation.json`
- `knowledge.json`
- `diagnostics.json`
- `validation.json`

`ArtifactsInspectorView` asks `PlatformAdapter.artifacts.getArtifactIndex()`
for descriptors and uses `readArtifact()` for per-file JSON content. The raw
analyze response remains available as the fallback "All Raw" tab.

Desktop artifact operations remain unsupported until the desktop shell phase.
