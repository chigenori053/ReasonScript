# IDE Phase 4.5-C2-D Audit / Language Audit Matrix Migration

## Changed

- Migrated Audit and Language audit matrix workflow surfaces into the official
  IDE.
- Added audit summary and actions to Overview.
- Added language audit matrix to the Tests tool window.
- Added normalized audit issues to Problems.
- Added audit operation logs to Output.
- Added raw audit report, raw matrix JSON, and audit export result to
  Artifacts.
- Added `/api/language-audit` and `/api/language-audit/export` client
  integration without backend contract rewrites.
- Added audit export and audit freshness policy documentation.

## Notes

All `MIGRATE_REQUIRED` legacy UI features have been migrated.

Physical deletion of `playground/frontend` is still blocked by the deferred
Sample selector decision and deletion-after-removal validation planning.
