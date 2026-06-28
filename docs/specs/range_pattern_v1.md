# ReasonScript Range Pattern Specification v1.0

Specification ID: `range-pattern/1.0`

Phase: MSI-009

Status: Draft

## Purpose

Range Pattern Matching lets numeric match inputs select deterministic value
intervals through the existing Match Semantic Pipeline. It introduces no new
execution model; range patterns lower to normal match selections and function
return transitions.

## Syntax

Inclusive range:

```reason
0..100
```

Half-open range:

```reason
0..<100
```

Range patterns may be used with guards and OR patterns:

```reason
80..100 when passed => return 1
0..10 | 90..100 => return 1
```

## Semantics

- `a..b` matches `a <= value <= b`.
- `a..<b` matches `a <= value < b`.
- v1.0 supports `Int` and `Float` endpoints.
- Empty ranges are invalid.
- Numeric ranges are not exhaustive over unbounded input domains; a fallback is required for full coverage.

## IR

Range patterns lower to:

```json
{
  "node_type": "RangePatternIRNode",
  "lower": 80,
  "upper": 100,
  "lower_inclusive": true,
  "upper_inclusive": true
}
```

Function return transitions use canonical paths:

- Inclusive: `Score.match.range.80_100`
- Half-open: `Score.match.range.80_lt_100`

## Pattern Identity

The selected range exposes the standard Pattern Identity:

```json
{
  "pattern_id": "Score.match.range.80_100",
  "pattern_type": "Range",
  "canonical_path": "Score.match.range.80_100"
}
```

For guarded ranges, `pattern_type` is `Guard` and the guard suffix is appended
to the canonical path.

## Runtime Artifacts

Simulation emits `RangeEvaluation` before `BranchSelection`.

Knowledge stores `range_evidence` with the evaluated value, endpoints,
inclusivity, and match result.

## Validation Rules

- `RP-001`: Range endpoints must have identical numeric types.
- `RP-002`: Only `Int` and `Float` are supported.
- `RP-003`: Lower bound must not exceed upper bound; half-open equal endpoints are empty.
- `RP-004`: Duplicate ranges are rejected by normal duplicate pattern validation.
- `RP-005`: Overlapping ranges remain deterministic by left-to-right selection.
- `RP-006`: Pattern Identity must equal the canonical range path.
- `RP-007`: Range metadata must be deterministic.

## Acceptance

`tests/rp_001.rsn` through `tests/rp_008.rsn` and
`tests/test_range_pattern.py` cover inclusive, half-open, float, invalid,
guarded, OR, identity propagation, range evidence, and deterministic metadata.
