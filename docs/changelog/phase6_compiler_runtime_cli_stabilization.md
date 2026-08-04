# ReasonScript Phase 6 - Compiler / Runtime CLI Stabilization - 2026-07-05

## Summary

Phase 6 adds the official `scripts/dev.py reason` CLI command group for check, analyze, run, artifact export, and examples validation.

## Added

- `python3 scripts/dev.py reason check <file.rsn>`
- `python3 scripts/dev.py reason analyze <file.rsn>`
- `python3 scripts/dev.py reason run <file.rsn>`
- `python3 scripts/dev.py reason artifacts <file.rsn> --out <dir>`
- `python3 scripts/dev.py reason examples`
- CLI JSON schemas and exit code policy
- Deterministic CLI artifact writer
- `examples/v0_5` valid and invalid corpus
- CLI contract tests

## Not Changed

- Parser, compiler, Reason IR, runtime model, and backend API schemas are not intentionally changed.
- The official IDE UI remains `apps/reasonscript-ide/ui`.

