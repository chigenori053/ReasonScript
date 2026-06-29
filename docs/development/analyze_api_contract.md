# Analyze API Contract

`POST /api/analyze` accepts:

```json
{
  "source": "module Test { calculation Value { result = 42 } }",
  "compiler_mode": "default"
}
```

The response contains:

```json
{
  "ok": true,
  "compiler_mode": "default",
  "pipeline": { "stages": [] },
  "artifacts": {},
  "views": {},
  "diagnostics": []
}
```

`pipeline.stages` always includes these stage ids:

- `source`
- `surface_ast`
- `semantic_ast`
- `reason_ir`
- `execution_plan`
- `simulation`
- `knowledge`
- `diagnostics`

Stage status values are `success`, `warning`, `error`, `skipped`, and `unavailable`.

Artifact file names are fixed:

- `ast.json`
- `semantic_ast.json`
- `reason_ir.json`
- `execution_plan.json`
- `simulation.json`
- `knowledge.json`
- `diagnostics.json`
- `validation.json`

Compiler diagnostics are returned as structured `diagnostics`. API transport or process failures should be represented separately by the caller when HTTP itself fails.
