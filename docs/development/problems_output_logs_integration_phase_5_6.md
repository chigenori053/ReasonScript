# Problems / Output / Logs Final Integration — Phase 5.6

## Status

REVIEWED

## Summary

Unifies every diagnostic/log source added across Phase 4.5-C2 and Phase 5
into the existing Problems / Output / Logs bottom tool window surfaces,
with deduplication and scope filtering.

## Data Contract

`apps/reasonscript-ide/ui/src/viewModels/problemsOutputLogsIntegration.ts`:

- `mergeProblemsSources(sources: PlatformDiagnostic[][])` deduplicates by
  `(code, source/phase, relativePath, message)`, preserving first-seen order.
  Used in `App.tsx` to merge migrated analysis diagnostics, artifact
  workflow issues, language audit issues, sample browser issues, and
  workspace diagnostics into one `problemsDiagnostics` list.
- `buildLogsGroups({ backend, analyzer, runtime, ide })` groups Logs-tab
  entries into the four sources called out by the spec.

## UI Placement

- **Problems** (`BottomToolWindow`): scope filter buttons
  (current file / workspace / all) backed by
  `viewModels/fileDiagnosticsMapping.ts::filterByScope`; merged/deduped
  diagnostic count in the tab label.
- **Output**: existing runtime/artifact/audit/sample logs plus a
  "Workspace / Project Validation Logs" block.
- **Logs**: existing last-error/last-analyze `<pre>` blocks plus grouped
  Backend / Analyzer / Runtime / IDE sections via `buildLogsGroups`.

## Acceptance

- [x] duplicate diagnostics are deduplicated (`mergeProblemsSources`)
- [x] Problems supports current file / workspace / all
- [x] Output groups operation logs
- [x] Logs separate backend / analyzer / runtime / IDE logs
- [x] no existing migrated feature output disappears (all prior
      `DiagnosticsView` / `DiagnosticsAnalysisView` / `RuntimeOutputView` /
      `ArtifactOperationLogsView` / `LanguageAuditLogsView` /
      `SampleOperationLogsView` / `RuntimeOperationsView` remain rendered)
