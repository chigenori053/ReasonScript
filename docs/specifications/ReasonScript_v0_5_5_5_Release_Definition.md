# ReasonScript v0.5.5.5 Release Definition

Specification ID: `reasonscript-release/0.5.5.5`
Status: VALIDATED
Date: 2026-08-28

ReasonScript 0.5.5.5 is a compatibility-preserving runtime and toolchain
maintenance release. The canonical version is `0.5.5.5` across `VERSION`,
Python package metadata, release metadata, runtime metadata, and the validation
profile. Runtime compatibility remains `>=0.5.0,<0.6.0`.

The release must:

- preserve the accepted `--result-output` value-only contract;
- preserve the machine-readable `--json` runtime trace contract;
- keep standalone and multi-file package execution on the strict Rust host;
- preserve Tensor/autograd state across calculation boundaries within one run;
- attach source locations to optimizer runtime diagnostics;
- keep trace-unavailable diagnostics non-blocking;
- preserve frozen artifact schemas and deterministic project validation;
- accept explicit backslash line continuation without changing ordinary
  newline semantics; and
- pass focused regression tests, the Rust workspace, artifact validation,
  Golden tests, canonical `reason ci`, package validation, and installed smoke
  validation.
