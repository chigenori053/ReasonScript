# ReasonScript 0.5.5.1 Release Notes

ReasonScript 0.5.5.1 introduces the Reason Entity Foundation and Surface
Model v0.1 and merges in the independent `v0.5.4.7`–`v0.5.4.9` language
and runtime fixes.

## Reason Entity Foundation and Surface Model v0.1

- `ru:`/`rus:`/`ruo:`/`derive:` declarations and `<-` state transitions,
  with Canonical Entity IDs and an RUO-U1 compatibility projection for
  existing code.
- RU Slot runtime representation with propose/validate/commit atomicity
  and on-read derive evaluation with dependency-revision memoization.
- Declaration-anchored type diagnostics `TYPE-020` (unresolved parameter
  type) and `TYPE-021` (unresolved function return type), replacing the
  prior distant-use-site `FCF-004` diagnostic for the cases the full-corpus
  measurement confirmed were safe to tighten.

## Merged v0.5.4.7–v0.5.4.9 language and runtime fixes

- Cross-package-source `module::function` linking and cross-module
  function resolution.
- Package-wide `reason run` execution compiled directly from `src/`,
  with `--entry` selection, sparse optional Tensor arguments, and
  checksum-addressed external Tensor results.
- Functional optimizers and learning-rate schedulers.
- `tensor.scalar` surface typing, division type/runtime alignment, and
  symmetric Unknown assignment compatibility corrections.
- `reason init <name> --template agent` project template.

## Package

The local macOS arm64 development update package is:

`release/v0.5.5.1/reasonscript-0.5.5.1-macos-arm64.zip`

Runtime compatibility remains `>=0.5.0,<0.6.0`.
