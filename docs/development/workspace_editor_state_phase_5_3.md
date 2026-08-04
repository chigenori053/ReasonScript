# Workspace / Editor State Consistency — Phase 5.3

## Status

REVIEWED

## Summary

Classifies the current editor source into one of four kinds so the
Workspace Explorer, dirty-state indicator, and diagnostics attribution stay
consistent as the user switches between workspace files, samples, and
unsaved content.

## Data Contract

`apps/reasonscript-ide/ui/src/viewModels/editorWorkspaceState.ts`:

```ts
export type EditorSourceKind = "workspace_file" | "sample" | "unsaved" | "missing";
export interface EditorWorkspaceState { sourceKind; relativePath?; sampleId?; dirty; sourceHash?; selectedFileExists; lastSavedHash?; }
```

`deriveEditorWorkspaceState({ selectedPath, activeFilePath, sampleId, source,
savedSource, workspace })`:

- `workspace_file` when a selected/active path resolves to a node in the
  current `WorkspaceState.files` tree
- `missing` when that path no longer resolves (workspace refreshed and the
  selected file was deleted)
- `sample` when no workspace path is selected but a sample was loaded
- `unsaved` otherwise (fresh/default editor content)

`hashSource()` is a small FNV-1a string hash used for dirty/staleness
comparisons (shared with Phase 5.4 artifact freshness).

## UI Placement

- **Workspace Explorer**: source-kind + dirty indicator strip above the file
  tree (`WorkspaceExplorerView.tsx`)
- **App state**: `App.tsx` recomputes `editorWorkspaceState` via `useMemo`
  whenever selection, sample, or source/savedSource change

## Acceptance

- [x] editor clearly distinguishes workspace file and sample source
- [x] dirty editor content is visible
- [x] file switching does not misattribute diagnostics (mapping keyed by
      `relativePath`, independent of editor state)
- [x] deleted selected file produces a stable `missing` warning
- [x] failed refresh does not corrupt editor state (derivation is a pure
      function of current props, not mutated in place)
