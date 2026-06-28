# Struct Exhaustiveness Audit

Specification: `struct-exhaustiveness/1.0`

MSI-006A is covered by `tests/test_struct_exhaustiveness.py` and fixtures `tests/sex_001.rsn` through `tests/sex_007.rsn`.

Coverage:

- Literal-only struct patterns emit `TV-8 NonExhaustiveStructMatch`.
- Binding-only patterns pass.
- Empty struct patterns pass.
- `default` branches pass.
- Nested struct coverage is evaluated recursively.
- Struct coverage metadata is deterministic across repeated compilation.
