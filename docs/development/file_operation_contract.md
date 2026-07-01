# File Operation Contract

Implemented in `playground/backend/workspace.py` and exposed via
`playground/backend/main.py`.

## Endpoints

### `POST /api/workspace/list`

Also serves `refresh_workspace` — refreshing is simply calling this again.

Request:

```json
{ "workspace_root": "/path/to/project" }
```

Response:

```json
{
  "ok": true,
  "root": "/path/to/project",
  "files": [
    {
      "name": "examples",
      "relative_path": "examples",
      "kind": "directory",
      "extension": null,
      "is_ignored": false,
      "is_source": false,
      "children": [
        {
          "name": "basic.rsn",
          "relative_path": "examples/basic.rsn",
          "kind": "file",
          "extension": "rsn",
          "is_ignored": false,
          "is_source": true,
          "children": []
        }
      ]
    }
  ],
  "scan_status": {
    "status": "success",
    "truncated": false,
    "max_depth": 8,
    "max_files": 5000,
    "file_count": 1
  }
}
```

File nodes carry only `relative_path` — no absolute path is exposed to the
UI (FILE-004). Ignored directories (see `workspace_contract.md`) are listed
with `is_ignored: true` and empty `children`, but are not descended into.
`is_source` is `true` for `.rsn` / `.reason` files, used by the UI to grey
out unsupported files (WUI-003).

### `POST /api/workspace/read`

Request:

```json
{ "workspace_root": "/path/to/project", "relative_path": "examples/basic.rsn" }
```

Success response:

```json
{
  "ok": true,
  "relative_path": "examples/basic.rsn",
  "content": "model Basic {\n}\n",
  "version": "1719800000.1234",
  "read_only": false
}
```

`version` is the file's mtime as a string — sufficient to detect concurrent
external changes without a full version-control layer.

Error response: `{ "ok": false, "relative_path": "...", "error": { "code": "...", "message": "..." } }`
with `code` one of `PATH_TRAVERSAL`, `NOT_FOUND`, `NOT_A_FILE`, `DECODE_ERROR`.

### `POST /api/workspace/save`

Request:

```json
{
  "workspace_root": "/path/to/project",
  "relative_path": "examples/basic.rsn",
  "content": "model Basic {\n}\n",
  "expected_version": "1719800000.1234"
}
```

Success response: `{ "ok": true, "relative_path": "...", "version": "<new mtime>" }`.

Error response uses the same shape as read, with `code` one of
`PATH_TRAVERSAL`, `NOT_A_FILE`, `READ_ONLY`, `VERSION_CONFLICT` (the latter
also includes `current_version`). `expected_version` is optional — omit it
to save unconditionally.

## `select_workspace_file` has no backend endpoint

The Playground backend is stateless per HTTP request — it holds no session
or "currently selected file" concept. Selection is pure frontend state
(`selectedFile` in `App.jsx`); the frontend calls `/api/workspace/read`
whenever the user selects a new file. There is deliberately no
`/api/workspace/select` endpoint.

## Path safety

Every endpoint resolves `workspace_root` to an absolute directory and
rejects any `relative_path` that resolves outside of it
(`workspace.resolve_within_workspace`), satisfying WS-005 /
FILE-READ-002 / FILE-SAVE-001. This works even for paths that don't exist
yet (e.g. saving a new file), since path resolution doesn't require the
target to exist.
