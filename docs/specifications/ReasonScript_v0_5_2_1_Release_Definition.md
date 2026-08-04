# ReasonScript v0.5.2.1 Release Definition

Specification ID: `reasonscript-release/0.5.2.1`
Status: VALIDATED
Date: 2026-07-23

ReasonScript 0.5.2.1 is the installable maintenance release for Integrated
Runtime Completeness v0.2. It makes scalar `reason run` execution numerical,
adds index/function/struct/multi-frame execution, and packages the native
ReasonUnit Runtime alongside VisionRuntime.

The canonical version is `0.5.2.1` across `VERSION`, Python package metadata,
release metadata, runtime metadata, and the validation profile. Four-component
maintenance versions are accepted by version validation while runtime
compatibility remains `>=0.5.0,<0.6.0`.

The package must:

- support both update and fresh-install workflows;
- activate `versions/0.5.2.1`;
- include `reason-vision` and `reasonunit-runtime-native`;
- run both native `verify-native` smoke checks;
- include SHA-256 payload inventory and provenance metadata;
- install without Cargo or Rust when using a built package;
- pass installed-distribution tests and `reason ci --json`.

The supported update floor remains ReasonScript 0.5.0.

Validation completed on 2026-07-23: canonical CI passed with 1085 tests,
package self-validation passed, Cargo-free fresh installation passed all 36
installed checks, and both native `verify-native` probes passed.
