# ReasonScript Timezone-aware Timestamp Specification v1.0

Specification ID: timezone-aware-timestamp/1.0

## Purpose

All newly generated UTC timestamps use timezone-aware `datetime` objects and serialize with `datetime.isoformat()`.

Canonical UTC format:

```text
YYYY-MM-DDTHH:MM:SS.ssssss+00:00
```

## Rules

- `datetime.utcnow` is prohibited.
- Runtime-generated timestamps use `datetime.now(UTC).isoformat()`.
- Deterministic fixture timestamps use timezone-aware UTC strings, such as `1970-01-01T00:00:00+00:00`.
- Consumers may accept legacy `Z` timestamps during transition, but newly generated artifacts emit `+00:00`.

## Covered Artifacts

- Playground validation reports
- Playground export manifests
- Playground analyzer quality reports
- Language audit reports
- Knowledge JSON
