# ReasonScript IDE Phase 3 — Local Workspace Editing Foundation

## Purpose

Phase 3 extends the Playground-first IDE from editing a temporary in-memory
`source` string to editing real workspace files. It builds on the Phase 2
`/api/analyze` contract (see `analyze_api_contract.md`) without changing it.

## Workflow

```
Workspace Explorer
  -> open workspace root (POST /api/workspace/list)
  -> select .rsn / .reason file
  -> read file        (POST /api/workspace/read)
  -> bind Source Editor
  -> edit               (dirty state tracked client-side)
  -> save               (POST /api/workspace/save)
  -> analyze            (POST /api/analyze with source_context)
  -> pipeline / artifacts / diagnostics shown for that file
```

## Two source modes

- **Temporary mode** — no file selected. The editor holds an in-memory
  string, exactly as in Phase 1/2. `POST /api/analyze` is called without
  `source_context`. This mode is always available (COMPAT3-009).
- **File-backed mode** — a workspace file is selected. The editor is bound
  to that file's content. `POST /api/analyze` is called with
  `source_context: { workspace_root, relative_path, dirty }`.

The two modes are mutually exclusive per editor buffer: selecting a file
switches into file-backed mode; loading an example or clearing the
selection returns to temporary mode.

## Scope

In scope: workspace file selection, read/save, dirty tracking, per-file
analyze, per-file diagnostics, per-file artifact identity, missing-file
handling, path traversal protection.

Out of scope (see the Phase 3 spec's Non-Goals): Desktop IDE full
implementation, terminal emulator, full LSP, multi-file semantic linking,
package manager, git integration, advanced runtime replay.

## Related contracts

- `file_operation_contract.md` — the `/api/workspace/*` endpoints.
- `editor_state_contract.md` — selected-file state shape and dirty rule.
- `per_file_artifact_contract.md` — artifact identity and persistence.
- `per_file_diagnostics_contract.md` — diagnostic-to-file association.
- `workspace_contract.md` — scan limits and ignore rules (Phase 1, inherited unchanged).
- `analyze_api_contract.md` — the base `/api/analyze` contract Phase 3 extends.
