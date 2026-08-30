# Executable Pattern Runtime Phase 1

- Added executable enum values with stable equality semantics.
- Added distinct `some(value)` and `none` runtime values; `none` is no longer
  conflated with `null`.
- Added ordered, guarded `match` lowering through the additive Computation IR
  `pattern_branch` terminator.
- Added literal, range, enum, Optional, struct, nested, binding, wildcard,
  default, and or-pattern execution in the Python reference paths and Rust VM.
- Promoted the official struct-pattern and Optional-match examples from
  Surface-only checks to the default executable contract.
- Preserved the `reason-computation-ir/0.1` schema identifier because the new
  vocabulary is additive and existing documents remain valid.
