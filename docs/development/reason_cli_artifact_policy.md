# ReasonScript CLI Artifact Policy

CLI artifact output is deterministic JSON with sorted keys and stable filenames.

Required files written by `reason artifacts` and `--out`:

- `surface_ast.json`
- `semantic_ast.json`
- `reason_ir.json`
- `execution_plan.json`
- `simulation.json`
- `knowledge.json`
- `diagnostics.json`
- `validation.json`
- `project_state.json`

Diagnostics are always written. Partial artifacts are allowed when a later pipeline stage fails.

