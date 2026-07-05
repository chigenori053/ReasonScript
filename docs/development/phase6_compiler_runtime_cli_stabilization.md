# Phase 6 Compiler / Runtime CLI Stabilization

Phase 6 stabilizes `python3 scripts/dev.py reason` as the official non-IDE entry point for ReasonScript source validation, analysis, execution, artifact export, and example validation.

The CLI reuses `playground.backend.main.analyze_endpoint`, which is also the backend path used by the official IDE. This keeps parser, semantic validation, Reason IR, ExecutionPlan, Simulation, Knowledge, and diagnostics behavior aligned.

## Commands

```bash
python3 scripts/dev.py reason check <file.rsn>
python3 scripts/dev.py reason analyze <file.rsn> [--json] [--out <dir>] [--compiler-mode normal|strict]
python3 scripts/dev.py reason run <file.rsn> [--json] [--out <dir>] [--trace] [--compiler-mode normal|strict]
python3 scripts/dev.py reason artifacts <file.rsn> --out <dir>
python3 scripts/dev.py reason examples [--json] [--out <dir>]
python3 scripts/dev.py reason build <project-dir>
python3 scripts/dev.py reason test
```

## Result Schemas

The stable CLI wrapper schemas are:

- `reasonscript-cli-check/0.1`
- `reasonscript-cli-analyze/0.1`
- `reasonscript-cli-run/0.1`
- `reasonscript-cli-examples/0.1`

`analyze` includes the backend ProjectState-compatible payload under `project_state`.

