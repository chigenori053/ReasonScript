# File-level Diagnostic Mapping — Phase 5.2

## Status

REVIEWED

## Summary

Maps compiler / analyzer / runtime / audit / artifact / workspace diagnostics
to workspace file paths and source ranges, and surfaces them as Workspace
Explorer badges and a filterable Problems view.

## Data Contract

`apps/reasonscript-ide/ui/src/viewModels/fileDiagnosticsMapping.ts` defines
the normalized diagnostic model from the Phase 5 spec:

```ts
export type IdeDiagnosticSeverity = "error" | "warning" | "info";
export interface IdeSourceRange { startLine?; startColumn?; endLine?; endColumn?; }
export interface IdeDiagnostic { id; severity; code?; message; source; relativePath?; sourceRange?; stage?; evidence?; }
```

`buildFileDiagnosticsMapping(diagnostics, activeRelativePath)` groups
`PlatformDiagnostic[]` by `relativePath`, with an `UNKNOWN_PATH_GROUP`
fallback bucket for diagnostics that carry no path. `filterByScope(mapping,
scope)` supports `"current" | "workspace" | "all"`. `severityBadgeForPath`
returns the worst severity for a given file, used for Explorer badges.

## UI Placement

- **Workspace Explorer**: per-file severity dot badge
  (`WorkspaceExplorerView.tsx`, `TreeNode`)
- **Problems**: scope filter (current file / workspace / all) in
  `BottomToolWindow` (`StandardLayoutViews.tsx`)
- **Artifacts**: raw diagnostics remain available via existing `raw` /
  `validation` tabs

## Acceptance

- [x] file diagnostics are grouped by relativePath
- [x] selected file diagnostics can be filtered
- [x] workspace diagnostics can be shown globally
- [x] unknown path diagnostics remain visible (`UNKNOWN_PATH_GROUP`)
- [x] file tree badges reflect diagnostic severity
