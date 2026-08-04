# ReasonScript v0.5.2.3 Release Definition

Specification ID: `reasonscript-release/0.5.2.3`
Status: VALIDATED
Date: 2026-07-25

ReasonScript 0.5.2.3 is the maintenance release for the two compiler and
parser defects reported during VisionWorldModel V0 development.

The canonical version is `0.5.2.3` across `VERSION`, Python package metadata,
release metadata, runtime metadata, and the validation profile. Runtime
compatibility remains `>=0.5.0,<0.6.0`.

The package must:

- update an installed ReasonScript 0.5.2.2 distribution;
- lower nested calls in inner-to-outer evaluation order;
- keep every Reason IR transition ID unique when inner and outer functions
  contain multiple return paths;
- supply literal inner return values to outer branch evaluation;
- accept typed function parameter lists spanning multiple source lines;
- preserve established single-call branch evidence and v0.5 compatibility;
- include both native runtimes and their pre-activation probes;
- carry clean release provenance and SHA-256 sidecars;
- pass source-tree CI, package validation, local update, installed validation,
  and installed reproductions for RS-VWM-001 and RS-VWM-002.

The supported update floor remains ReasonScript 0.5.0.
