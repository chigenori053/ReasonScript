# Playground Default Exhaustiveness Audit

Status: Implemented

## Coverage

- `default` identifier arms and wildcard arms are treated as default coverage in enum and optional exhaustiveness checks.
- Enum match missing variants are emitted in declaration order.
- TV-7 diagnostics include the uncovered qualified variants.
- Duplicate match pattern validation still runs before default exhaustiveness expansion.
- Enum match IR exposes `coverage` metadata with explicit/default/covered/missing variants.

## Validation

Covered by `tests/test_default_exhaustiveness_integration.py` and fixtures `tests/msi_301.rsn` through `tests/msi_306.rsn`.
