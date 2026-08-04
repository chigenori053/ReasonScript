# Workspace Adapter Migration

Status: Phase 4-B DRAFT FOR ADOPTION

Phase 4-B moves workspace list, read, and save operations behind
`PlatformAdapter.workspace`.

The browser implementation keeps the existing backend contracts:

- `POST /api/workspace/list`
- `POST /api/workspace/read`
- `POST /api/workspace/save`

UI components must not call these endpoints directly. `WorkspaceExplorerView`
is a presentational tree and delegates opening, refreshing, and selection to
callbacks. `App.tsx` owns the active `PlatformAdapter` and routes:

- workspace open/refresh through `listWorkspace`
- file selection through `readFile`
- save shortcut through `saveFile`

The selected file workflow keeps Phase 3 behavior: selecting a source file
loads it into the editor, save clears dirty state by updating the saved content
snapshot and version, and analyze can attach `source_context` for file-backed
sources.
