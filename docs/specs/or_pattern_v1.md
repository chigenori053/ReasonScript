# ReasonScript Or Pattern Specification v1.1

Specification ID: `or-pattern/1.1`

Phase: MSI-008

Status: Draft

## Purpose

OR patterns allow one match arm to list multiple compatible alternatives with
left-to-right evaluation. Each alternative contributes independently to
matching, exhaustiveness metadata, simulation evidence, and knowledge evidence.

## Rules

- `Pattern | Pattern` requires at least two alternatives.
- Duplicate alternatives emit `OP-004 DuplicateOrPattern`.
- Alternatives must expose identical binding names or emit
  `OP-002 IncompatibleBindingEnvironment`.
- Alternatives must use compatible pattern categories or emit `OP-003`.
- Guards run after the selected alternative binds values.
- Lowering creates independent return transitions for each selected alternative.

## IR Metadata

OR arms lower to `OrPatternIRNode` metadata with deterministic `alternatives`,
`selected_index`, `selected_pattern`, and `alternative_count` fields.

ExecutionPlan, Simulation, and Knowledge preserve the same selected-pattern
metadata:

```json
{
  "selected_index": 1,
  "selected_pattern": "Color.Blue",
  "alternative_count": 2
}
```

Runtime artifacts serialize only the selected canonical path, such as
`Score.match.Color.Blue`; the OR expression itself is retained only as semantic
metadata for auditability.

## Acceptance

`tests/op_001.rsn` through `tests/op_008.rsn` and `tests/test_or_pattern.py`
cover enum, literal, struct, optional, diagnostics, guards, and deterministic
metadata.
