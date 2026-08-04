# ReasonScript — Workspace Root Contract

## Workspace Definition

The **workspace root** is the directory explicitly selected by the user when opening a ReasonScript project in the IDE.  
It is never inferred automatically; the user must confirm the selection.

## Scan Parameters

| Parameter           | Value                                       |
|---------------------|---------------------------------------------|
| Max depth           | 8                                           |
| Max files           | 5000                                        |
| Ignored directories | `.git`, `node_modules`, `target`, `dist`, `build` |
| Path traversal      | Paths outside workspace root are rejected   |
| Selected file       | Retained across workspace refresh           |

## Scan Rules

**WS-001** — The workspace root is always an explicitly selected directory.

**WS-002** — Directory scan does not descend beyond `max_depth = 8` from the workspace root.

**WS-003** — If the file count exceeds `max_files = 5000`, the scan stops and the IDE shows a warning.

**WS-004** — The following directories are never scanned:

```
.git/
node_modules/
target/
dist/
build/
```

**WS-005** — Any file path that resolves outside the workspace root is rejected.  
The backend must validate that `resolved_path.startswith(workspace_root)` before reading any file.

**WS-006** — After a workspace refresh, the IDE attempts to re-select the previously selected file by path.  
If the file no longer exists, the selection is cleared without error.

## Workspace State in IDE

The workspace root and selected file are part of IDE state and are not persisted between sessions in Phase 1.  
The user must re-select the workspace root on each launch.

## Security

Path traversal attacks (e.g., `../../etc/passwd`) are blocked by the path boundary check (WS-005).  
The workspace root itself must be an absolute path confirmed by the OS file picker.

## Future

Workspace state persistence (remembering last-opened workspace) is deferred to a future phase.
