# Adapter Path Enforcement

Status: Phase 4-B DRAFT FOR ADOPTION

Phase 4-B applies `NormalizedRelativePath` validation at workspace, artifact,
and analyze boundaries.

Rules:

- paths must be relative
- paths must use `/`
- empty path segments are rejected
- `..` traversal is rejected
- absolute paths and Windows drive paths are rejected

Enforcement points:

- `WorkspaceAdapter.readFile()` validates `relativePath` before calling
  `/api/workspace/read`.
- `WorkspaceAdapter.saveFile()` validates `relativePath` before calling
  `/api/workspace/save`.
- `WorkspaceAdapter.listWorkspace()` normalizes backend file identities before
  placing them in UI state.
- file-backed analyze validates `wsStore.selectedPath` before sending
  `source_context.relative_path`.
- artifact requests validate optional `relativePath` before producing indexes
  or reads.

Invalid paths are rejected in the adapter/UI boundary and are not sent to the
backend.
