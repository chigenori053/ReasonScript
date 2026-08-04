# ReasonScript v0.5.2.2 Release Definition

Specification ID: `reasonscript-release/0.5.2.2`
Status: VALIDATED
Date: 2026-07-24

ReasonScript 0.5.2.2 is the maintenance release for RUO native
interoperability. It corrects installed native runtime discovery and removes
the Python/Rust JSON re-serialization boundary from RUO-F1 record digest
verification.

The canonical version is `0.5.2.2` across `VERSION`, Python package metadata,
release metadata, runtime metadata, and the validation profile. Runtime
compatibility remains `>=0.5.0,<0.6.0`.

The package must:

- update an installed ReasonScript 0.5.2.1 distribution;
- resolve `reasonunit-runtime-native` from the installed distribution when
  Object commands run from an unrelated project directory;
- load Python-written and Vision-derived canonical RUO-F1 files natively;
- reject tampered RUO-F1 record bodies;
- include both native runtimes and their pre-activation probes;
- carry clean release provenance and SHA-256 sidecars;
- pass fresh-install, update, installed validation, and `reason ci --json`.

The supported update floor remains ReasonScript 0.5.0.
