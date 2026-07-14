# ReasonScript Install Foundation v1.0 — Distribution Completeness

- Specification ID: `reasonscript-install-distribution-completeness/1.0`
- Status: ACCEPTED
- Target: ReasonScript 0.5.x

An installation is complete only when its required files, Python packages,
schemas, standard library, runtime modules, import closure, and principal CLI
paths execute outside the source repository with a clean `PYTHONPATH`.

The required distribution includes `toolchain`, `scripts`, `schemas`,
`frontend`, `runtime`, `examples`, `standard_library`, `metadata`, `playground`,
and the transitive `conformance` dependency. The Install Manifest records each
required component and SHA-256 records for all entry points and schemas.

Before activation, the installer validates required targets, imports
`toolchain`, `scripts.reason_cli`, and `playground.backend.main` from the staged
root, and rejects repository-path resolution. `reason doctor` exposes DR-021
through DR-024. `reason install-validate` v1.1 exposes IF-VAL-011 through
IF-VAL-020 and executes an isolated init/check/run/artifacts smoke project.

Acceptance requires repository-independent init, check, run, artifacts,
manifest integrity, atomic activation, and manifest-scoped uninstall.
