# Project Validation Summary — Phase 5.5

## Status

REVIEWED

## Summary

Combines workspace diagnostics, file diagnostics, and artifact freshness
into a single at-a-glance validation summary with `canAnalyze` / `canRun`
readiness flags.

## Data Contract

`apps/reasonscript-ide/ui/src/viewModels/projectValidation.ts`:

```ts
export type ProjectValidationStatus = "valid" | "warning" | "invalid" | "unavailable";
export interface ProjectValidationSummary {
  status; workspaceRoot?; validFileCount; invalidFileCount; ignoredFileCount;
  diagnosticCount; errorCount; warningCount; artifactFreshness?; canAnalyze; canRun; reason?;
}
```

`buildProjectValidationSummary(workspace, workspaceDiagnosticsVm,
allDiagnostics, artifactFreshnessVm)`:

- `unavailable` when no workspace is open (editor-only mode remains usable —
  `canAnalyze` stays `true`)
- `invalid` when the workspace scan failed or any error-severity diagnostic
  exists
- `warning` when warnings exist, the scan was truncated, or invalid files
  were found
- `valid` otherwise

## UI Placement

- **Overview**: `ProjectValidationSummaryView` section
- **Artifacts**: `project_validation.json` in the `validation` tab

## Acceptance

- [x] Overview shows project validation status
- [x] invalid project is clearly marked
- [x] `canAnalyze` / `canRun` are visible
- [x] validation report is available in Artifacts
- [x] missing workspace produces `unavailable` status
