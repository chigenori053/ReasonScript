# ReasonScript Default Exhaustiveness Integration Specification v1.0

Specification ID: `default-exhaustiveness-integration/1.0`

Phase: MSI-003A

Status: Implemented

## Purpose

Enum match exhaustiveness treats a final `default` arm as coverage for all enum variants not matched explicitly.

Without default:

```reason
match color {
    Color.Red => return 1
}
```

emits:

```text
TV-7 NonExhaustiveMatch Missing: Color.Blue
```

With default:

```reason
match color {
    Color.Red => return 1
    default => return 0
}
```

passes validation because default covers the remaining variants.

## Algorithm

Given enum variants `V` and explicit enum cases `M`:

```text
missing = V - M
if default_exists:
    missing = {}
if missing:
    emit TV-7
```

Missing variants are reported in enum declaration order.

## Coverage Metadata

Enum match IR records deterministic coverage metadata:

```json
{
  "enum_name": "Color",
  "explicit_variants": ["Color.Red"],
  "default_present": true,
  "covered_variants": ["Color.Red", "Color.Blue", "Color.Green"],
  "missing_variants": []
}
```

Duplicate pattern validation remains independent and still emits `MSI-001` before default expansion can satisfy exhaustiveness.

## Acceptance Coverage

- MSI-301: default satisfies one remaining enum variant.
- MSI-302: default satisfies multiple remaining enum variants.
- MSI-303: TV-7 reports missing `Color.Blue` without default.
- MSI-304: TV-7 reports missing `Color.Green` without default.
- MSI-305: duplicate enum pattern with default still emits `MSI-001`.
- MSI-306: repeated compilation produces identical coverage metadata.
