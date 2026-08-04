# ReasonScript IDE Phase 4.5-B - Official IDE Command Wiring - 2026-07-04

## Status

DRAFT FOR ADOPTION

## Summary

Phase 4.5-B wires the official ReasonScript IDE UI at `apps/reasonscript-ide/ui` into the repository's developer command surface.

This phase updates `scripts/dev.py` so that the official IDE UI is reachable through `ide-ui`, included in frontend build validation, and included in smoke validation. The legacy Playground frontend remains available but is explicitly marked as legacy.

## Added

- Added `python3 scripts/dev.py ide-ui`.
- Added official IDE workflow guidance to `python3 scripts/dev.py ide`.
- Added official IDE UI build validation through `python3 scripts/dev.py test frontend`.
- Added legacy Playground frontend validation through `python3 scripts/dev.py test playground-frontend`.
- Added Phase 4.5-B command contract tests.
- Added official IDE command documentation.

## Changed

- `python3 scripts/dev.py build` now includes `apps/reasonscript-ide/ui`.
- `python3 scripts/dev.py test smoke` now includes official IDE UI build.
- `python3 scripts/dev.py test frontend` now targets official IDE UI.
- `python3 scripts/dev.py playground` is marked legacy.
- `python3 scripts/dev.py frontend` is marked legacy.
- Development docs now identify `apps/reasonscript-ide/ui` as the official IDE UI.

## Not Changed

- `playground/frontend` is not deleted.
- `playground/backend` remains unchanged.
- Parser, runtime, Reason IR, and API contracts are unchanged.
- Legacy feature migration is deferred to Phase 4.5-C.

## Deletion Gate

Partially improved but not closed.
