# Executable Check Contract — Phase 0

- Made the default `reason check` contract include Computation IR lowering,
  optimization, and structural validation.
- Added explicit `--surface-only` compatibility mode for parser, namespace,
  and Surface semantic validation without an executability claim.
- Shared the executable lowering implementation between `reason check` and
  `reason build`.
- Classified runtime I/O, struct-pattern, and Optional-match v0.5 examples as
  Surface-only until their Rust execution support is implemented.
- Preserved canonical `IR-LOWER-*` diagnostics and exposed the
  `computation_ir` stage in standalone JSON check results.
