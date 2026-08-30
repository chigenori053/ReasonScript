# ReasonScript CLI Examples Validation

The Phase 6 examples corpus lives in `examples/v0_5`.

Executable examples (validated by the default `reason check` contract):

- `001_minimal_module.rsn`
- `002_single_calculation.rsn`
- `003_calculation_dependency.rsn`
- `004_function_call.rsn`
- `005_branching_function.rsn`
- `008_struct_pattern.rsn`
- `009_optional_match.rsn`

Surface-only examples (valid syntax and semantics, not currently executable
through Computation IR/Rust):

- `006_runtime_input_print.rsn` — runtime I/O lowering is not implemented
- `007_runtime_operation.rsn` — runtime input lowering is not implemented

Invalid examples:

- `invalid/missing_module.rsn`
- `invalid/duplicate_symbol.rsn`
- `invalid/undefined_dependency.rsn`
- `invalid/calculation_cycle.rsn`
- `invalid/reserved_top_level_construct.rsn`
- `invalid/function_missing_return.rsn`

Validate with:

```bash
python3 scripts/dev.py reason examples
python3 scripts/dev.py reason examples --json
```

The JSON report records `check_mode` for every example and reports separate
`executable_total` and `surface_only_total` counts. Directly running default
`reason check` on a Surface-only example intentionally returns its canonical
`IR-LOWER-*` diagnostic; use `--surface-only` only when inspecting that
language layer.
