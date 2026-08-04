# Per-file Artifact Contract

Extends `artifact_contract.md` for workspace file-backed analysis.

## Artifact identity

```python
def artifact_identity(relative_path: str) -> str:
    return hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:16]
```

Implemented in `playground/backend/workspace.py`. The identity is a
deterministic function of the file's `relative_path` only (PFA-002) — the
same file always produces the same identity across calls and sessions, and
different files produce different identities. It intentionally does not
factor in `workspace_root`, so relocating a checkout to a new path doesn't
change artifact identity for files at the same relative path.

## Output path

```
<workspace_root>/.reasonscript/artifacts/<artifact_id>/
```

This reuses the exact artifact file names from `artifact_contract.md`
(`ast.json`, `semantic_ast.json`, `reason_ir.json`, `execution_plan.json`,
`simulation.json`, `knowledge.json`, `diagnostics.json`, `validation.json`,
plus `manifest.json`) — no new schema, just a deterministic directory
keyed by file identity instead of by source filename stem (PFA-003).

## When artifacts are written

`POST /api/analyze` persists per-file artifacts **only** when the request
includes `source_context.workspace_root` and `source_context.relative_path`
(i.e. the caller is analyzing a workspace file, not a temporary source
string). The write is best-effort: any filesystem error is caught and
ignored so a persistence failure never breaks the analyze response
(PFA-004) — the API still returns the full pipeline/diagnostics/artifacts
payload either way; only the on-disk copy may be missing.

## `source_context` in the analyze response

```json
{
  "source_context": {
    "workspace_root": "/path/to/project",
    "relative_path": "examples/basic.rsn",
    "dirty": false,
    "artifact_id": "49fe3403cf685387"
  }
}
```

`artifact_id` is always included alongside `source_context` in the
response so the frontend (or any other client) can locate the artifact
directory without recomputing the hash itself.
