# ReasonScript v0.5.2.4 Release Definition

Specification ID: `reasonscript-release/0.5.2.4`
Status: IN_PROGRESS
Date: 2026-07-25

ReasonScript 0.5.2.4 is the maintenance release for the three defects reported
during generic structure recognition.

The canonical version is `0.5.2.4` across `VERSION`, Python package metadata,
release metadata, runtime metadata, and the validation profile. Runtime
compatibility remains `>=0.5.0,<0.6.0`.

The package must:

- update an installed ReasonScript 0.5.2.3 distribution;
- apply the same empty-corpus policy to `reason golden` and `reason ci`;
- report a missing Golden corpus as `GT-011`;
- keep repository-specific Phase 8 fixtures out of project-independent CI;
- accept compact single-line struct declarations, including nested composite
  types;
- report malformed compact structs as `PARSE-001`;
- support `reason --help`, `reason -h`, and `reason help` with exit status 0;
- preserve multiline struct, unknown-command, Phase 8, and v0.5 compatibility;
- include both native runtimes and their pre-activation probes;
- carry clean release provenance and SHA-256 sidecars;
- pass source-tree CI, package validation, local update, installed validation,
  and installed regressions for RS-GSR-001 through RS-GSR-003.

The supported update floor remains ReasonScript 0.5.0.
