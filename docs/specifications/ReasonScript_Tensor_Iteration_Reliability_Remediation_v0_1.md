# ReasonScript Tensor Iteration Reliability Remediation v0.1

Status: IMPLEMENTED

## Scope

This specification corrects four failures found while implementing iterative
image-recognition models with ReasonScript Base v0.5.4.4:

1. unreachable Tensor backend values accumulated until `TSF-013`;
2. loop trace snapshots materialized complete Tensor arrays and could raise
   `TSF-020`;
3. decimal scientific notation was split into unrelated tokens;
4. integrated Tensor runtime diagnostics omitted their source line and column.

## Required behavior

- The integrated evaluator shall treat calculation environments, prior
  calculation results, nested-function caller environments, and the current
  returned value as Tensor reachability roots.
- After a statement or scope completes, Tensor values not reachable from those
  roots shall be removed from both the runtime reference registry and backend
  storage.
- Loop `previous_state` and `updated_state` snapshots shall preserve ordinary
  scalar and collection values. Tensor values shall use the external Tensor
  metadata representation and shall not call `tensor.to_array`.
- Numeric literals shall accept an optional exponent suffix matching
  `[eE][+-]?\d+`. A literal containing a decimal point or exponent is a float.
- A Tensor call parsed from ReasonScript source shall carry a one-based line and
  column into runtime diagnostics and the Tensor trace `source_ref`.
- Explicit public serialization, including result serialization and an
  explicit `tensor.to_array`, remains subject to `inline_elements`.

## Compatibility

The `TSF-013` policy remains enforced for values that are genuinely live.
Loop trace keys and non-Tensor snapshot values remain unchanged. Tensor snapshot
values change from inline arrays to the existing
`TensorValueRef.runtime_value()` external-value contract.

## Acceptance

- A 20 by 20 Tensor can participate in at least 1,100 loop iterations without
  `TSF-020` or `TSF-013`.
- Overwritten Tensor values are absent from the runtime registry after their
  last reachable binding is gone.
- `7.9e-05` and `1E+3` parse as float literals.
- An integrated runtime Tensor failure reports the Tensor call's source line and
  column.
- The canonical `reason ci --json` pipeline passes.
