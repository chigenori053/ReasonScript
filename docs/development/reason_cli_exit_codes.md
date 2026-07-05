# ReasonScript CLI Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | ReasonScript diagnostics failure |
| 2 | CLI usage error |
| 3 | Filesystem error |
| 4 | Internal compiler/runtime error |
| 5 | Deterministic contract violation |

The Phase 6 implementation maps parser, semantic, validation, and runtime diagnostics to exit code `1`.

