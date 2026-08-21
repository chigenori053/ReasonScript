# ReasonScript v0.5.5.1

## Added

- Reason Entity Foundation and Surface Model v0.1: `ru:`/`rus:`/`ruo:`/
  `derive:` declarations, `<-` state transitions, Canonical Entity IDs,
  RUO-U1 compatibility projection, and RU Slot runtime with
  propose/validate/commit atomicity and on-read derive evaluation.
- Declaration-anchored type diagnostics `TYPE-020`/`TYPE-021`, replacing
  the prior distant-use-site `FCF-004` diagnostic for the cases confirmed
  safe by full-corpus measurement.

## Changed

- Merged the independent `v0.5.4.7`–`v0.5.4.9` cross-module
  `module::function` linking, package-wide `reason run` (compiling
  directly from `src/`), and standalone optimizer module into this
  branch's runtime and validation pipeline.

## Preserved compatibility constraints

- Tensor autograd still requires explicit `tensor.parameter` targets.
- Statements remain single-line; multiline parameter lists remain supported.
- Explicit parameter annotations remain required for Boolean control-flow use.
