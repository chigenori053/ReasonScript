# Diagnostics Pipeline Mapping

Every diagnostic returned by `/api/analyze` has:

- `code`
- `message`
- `severity`
- `stage`
- `source_range`

Severity values are normalized to `error`, `warning`, or `info`.

Stage mapping:

| Diagnostic Source | Stage |
| --- | --- |
| lexer / parser error | `surface_ast` |
| namespace error | `semantic_ast` |
| type validation error | `semantic_ast` |
| calculation dependency error | `reason_ir` or `execution_plan` |
| planning failure | `execution_plan` |
| simulation failure | `simulation` |
| knowledge evidence error | `knowledge` |
| artifact parse error | corresponding artifact stage |
| environment or unknown error | `diagnostics` |

Unknown diagnostics are classified as `diagnostics` so Pipeline Overview can still show a stable status.
