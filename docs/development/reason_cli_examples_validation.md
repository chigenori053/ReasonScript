# ReasonScript CLI Examples Validation

The Phase 6 examples corpus lives in `examples/v0_5`.

Valid examples:

- `001_minimal_module.rsn`
- `002_single_calculation.rsn`
- `003_calculation_dependency.rsn`
- `004_function_call.rsn`
- `005_branching_function.rsn`
- `006_runtime_input_print.rsn`
- `007_runtime_operation.rsn`
- `008_struct_pattern.rsn`
- `009_optional_match.rsn`

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

