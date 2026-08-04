# ReasonScript v0.5.2.1

ReasonScript 0.5.2.1 packages Integrated Runtime Completeness v0.2 and the
Native ReasonUnit Runtime distribution remediation.

Highlights:

- scalar-only calculations execute numerically through `reason run`;
- array indexing and assignment, user functions, and struct member operations
  execute in the integrated runtime;
- `array.append` and `--result-output` support single-run frame-series output;
- `reasonunit-runtime-native` is built, packaged, checksummed, installed, and
  smoke-validated alongside `reason-vision`;
- `reason object` explicitly remains a canonical Object interface rather than
  a numerical physics evaluator;
- version validation accepts the four-component `0.5.2.1` maintenance version.

The update-and-install package supports upgrades from 0.5.0 and fresh
installation from the same artifact.
