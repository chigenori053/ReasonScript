# Workspace Diagnostics — Phase 5.1

## Status

REVIEWED

## Summary

Adds workspace-level diagnostics to the official IDE: scan status, valid /
invalid / unsupported file counts, ignored paths, and scan-limit warnings.

## Data Contract

`apps/reasonscript-ide/ui/src/viewModels/workspaceDiagnostics.ts` derives
`WorkspaceDiagnosticsViewModel` purely from the existing `WorkspaceState`
already produced by `/api/workspace/list` (no new endpoint):

- `scanStatus` from `WorkspaceState.scan_status`
- `validFileCount` / `invalidFileCount` / `unsupportedFileCount` /
  `ignoredPaths` from walking `WorkspaceState.files`
- `scanTruncated` when `scan_status === "partial"`
- `diagnostics: PlatformDiagnostic[]` for scan failures, truncation, and
  invalid files, exposed via `workspaceDiagnosticsAsPlatformDiagnostics()`

Missing workspace state (`workspace === null`) returns a stable
`unavailable` shape and never throws.

## UI Placement

- **Workspace Explorer**: ignored-path count and scan-truncation notice
  (`apps/reasonscript-ide/ui/src/views/WorkspaceExplorerView.tsx`)
- **Overview**: `WorkspaceDiagnosticsSummaryView` section
- **Problems**: workspace-level diagnostics merged into the Problems list
  (`apps/reasonscript-ide/ui/src/App.tsx`, `workspaceDiagnosticsList`)
- **Output**: "Workspace / Project Validation Logs" block

## Acceptance

- [x] workspace diagnostics summary exists
- [x] ignored paths are visible
- [x] scan limits are visible
- [x] workspace-level diagnostics appear in Problems
- [x] missing workspace state does not crash the UI
