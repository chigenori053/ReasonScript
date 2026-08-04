# IDE Phase 4.5-C2-C Export / Import / Diff Migration

## Changed

- Migrated Export, Import, and Diff workflow surfaces into the official IDE
  Artifacts tab.
- Added artifact workflow summary to Overview.
- Added normalized artifact workflow issues to Problems.
- Added export/import/diff operation logs to Output.
- Added `/api/export`, `/api/import`, and `/api/diff` client integration
  without backend contract rewrites.
- Added validation-first import safety policy documentation.

## Notes

Physical deletion of `playground/frontend` is still out of scope.

Artifact workflow migrated; deletion gate remains NOT CLOSED.
