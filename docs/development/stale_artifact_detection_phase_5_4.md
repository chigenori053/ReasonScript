# Stale Artifact Detection — Phase 5.4

## Status

REVIEWED

## Summary

Detects when the editor source has changed since the last Analyze run, so
AST / Reason IR / ExecutionPlan / Simulation / Knowledge views are not
mistaken for current state.

## Data Contract

`apps/reasonscript-ide/ui/src/viewModels/artifactFreshness.ts`:

```ts
export type ArtifactFreshnessStatus = "fresh" | "stale" | "unavailable" | "unknown";
export interface ArtifactFreshness { artifactName; status; sourceHash?; artifactSourceHash?; generatedAt?; reason?; }
```

`buildArtifactFreshness(projectState, currentSource)` hashes the live editor
source (`hashSource`, shared with Phase 5.3) and compares it against the hash
of `projectState.source_files[0].text` (the source snapshot the last
Analyze/`/api/analyze` response was generated from) for each tracked
artifact: `surface_ast`, `reason_ir`, `execution_plan`, `simulation`,
`knowledge`. A `null` artifact is `unavailable`; a hash mismatch is `stale`;
otherwise `fresh`.

Re-running Analyze refreshes `projectState`, which updates the artifact
source snapshot and clears the stale status on the next render.

## UI Placement

- **Overview**: `ArtifactFreshnessSummaryView` summary section
- **Artifacts**: `artifact_freshness.json` in the `validation` tab
  (`ArtifactsInspectorView`)

## Acceptance

- [x] source edit marks artifacts stale (hash mismatch)
- [x] Analyze refresh marks artifacts fresh (new `projectState` snapshot)
- [x] stale artifacts are not shown as current (status is explicit per
      artifact, not inferred from render order)
- [x] stale status is visible in Overview and Artifacts
- [x] stale warnings are deduplicated in Problems (freshness view model is
      not itself pushed into diagnostics/Problems, avoiding duplication with
      compiler diagnostics)
