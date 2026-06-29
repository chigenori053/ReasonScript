# ReasonScript — Test Matrix

## Categories

| Category  | Command                                | Purpose                                    |
|-----------|----------------------------------------|--------------------------------------------|
| smoke     | `python3 scripts/dev.py test smoke`    | Minimum validation (daily dev use)         |
| backend   | `python3 scripts/dev.py test backend`  | Compiler / analyzer / compatibility tests  |
| frontend  | `python3 scripts/dev.py test frontend` | TypeScript / React build validation        |
| rust      | `python3 scripts/dev.py test rust`     | Rust runtime workspace tests               |
| ide       | `python3 scripts/dev.py test ide`      | IDE contract / visualization tests         |
| all       | `python3 scripts/dev.py test all`      | CI-equivalent full run                     |

## Smoke Test Definition

The smoke test is the minimum check that the development environment is intact.

```
tests/compatibility/     → language surface compatibility suite
playground_integration_tests/ → Playground API integration
playground/frontend/     → npm run build (TypeScript compilation)
```

Target: completes in under 5 minutes in a healthy environment.

## Backend Test Scope

```
tests/compatibility/
playground_integration_tests/
tests/playground/
```

Covers: language surface compatibility, compiler output, analyzer, Playground API.

## Frontend Test Scope

```
playground/frontend/ → npm run build
```

Validates TypeScript compilation and Vite bundle without a running server.

## Rust Test Scope

```
RuntimeReal/    → cargo test
HybridRuntime/  → cargo test
```

Covers: runtime correctness, hybrid decision logic.

## IDE Test Scope

```
ide_phase1_tests/
tests/ide/
```

Covers: IDE phase 1 contracts, workspace and visualization contracts.

## CI (all)

Runs backend → frontend → rust → ide in sequence.  
Exit code is non-zero if any category fails.

## Notes

- All Python test runs use `pytest` with `--tb=short` for readable output.
- `PYTHONPATH=.` is required; `pytest.ini` sets this automatically.
- Rust tests in `RuntimeComplex` are excluded from the standard matrix (heavy; run manually when needed).
