# Runtime Rust Consolidation Phase 0

- Added `reason runtime-manifest [--json] [--out DIR] [--check]`.
- Froze 103 runtime namespace operations, current standalone/project/install
  dispatch paths, Rust coverage, fallback reasons, retirement candidates, and
  deletion gates.
- Added observable `artifacts.runtime_dispatch` data to standalone runs so a
  Python fallback has a stable reason instead of being silent.
- Added contract and dispatch regression tests.

The committed baseline is
`docs/reports/runtime_consolidation_manifest.json` using schema
`reasonscript-runtime-consolidation-manifest/1.0`.
