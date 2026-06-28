# Struct Pattern Matching Audit

MSI-006 is covered by `tests/test_struct_pattern_matching.py` and fixtures `tests/spm_001.rsn` through `tests/spm_008.rsn`.

Implemented surfaces:

- Parser accepts literal, binding, mixed, empty, and nested struct patterns.
- AST/JSON includes `StructPatternNode`, `StructFieldPatternNode`, and `StructBindingPatternNode`.
- Validation rejects unknown fields, duplicate fields, duplicate binding names, and matched-type mismatches.
- Function return contexts receive branch-local struct field bindings.
- ExecutionPlan, Simulation, and Knowledge preserve deterministic struct branch identifiers and `struct_match_evidence`.
