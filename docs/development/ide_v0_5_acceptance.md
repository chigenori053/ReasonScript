# ReasonScript IDE V0.5 Acceptance — Phase 5.7

## Status

REVIEWED

## Summary

Fixes the acceptance matrix that defines "ReasonScript IDE V0.5" as
complete, enforced by
`tests/ide/test_ide_v0_5_acceptance.py`.

## Acceptance Test Matrix

- [x] official IDE UI exists
- [x] playground/frontend does not exist
- [x] workspace explorer exists
- [x] sample browser exists
- [x] editor state model exists
- [x] workspace diagnostics model exists
- [x] file-level diagnostics mapping exists
- [x] stale artifact detection exists
- [x] project validation summary exists
- [x] Problems final integration exists
- [x] Output final integration exists
- [x] Artifacts include validation report
- [x] commands.md points to official IDE
- [x] test_matrix.md points to official IDE
- [x] scripts/dev.py test frontend targets official IDE UI

## Validation Commands

```
python3 -m pytest tests/ide -q
python3 scripts/dev.py test ide
python3 scripts/dev.py test frontend
python3 scripts/dev.py test smoke
python3 scripts/dev.py test backend
python3 scripts/dev.py build
git diff --check
```
