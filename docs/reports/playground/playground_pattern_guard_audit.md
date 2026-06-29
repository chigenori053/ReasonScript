# Pattern Guard Audit

Specification: `pattern-guard/1.0`

MSI-007 is covered by `tests/test_pattern_guard.py` and fixtures `tests/pg_001.rsn` through `tests/pg_008.rsn`.

Coverage:

- Struct, nested struct, enum, optional, and literal guards parse and execute.
- Guard expressions are Bool-validated with branch-local bindings.
- Guard failures continue to later compatible branches.
- Guarded arms do not satisfy exhaustiveness.
- `GuardExpressionIRNode`, `GuardEvaluation`, and `guard_evidence` are emitted.
- Canonical guard paths are deterministic.
