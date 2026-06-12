# ReasonScript Conformance Framework v0.1

This directory implements the five conformance layers for the
`reason-ir/0.1` ABI.

| Layer | Suite | Purpose |
|---|---|---|
| 0 | `schema_conformance_tests` | JSON Schema, required fields, types, ABI version |
| 1 | `dto_conformance_tests` | serialization, round-trip, metadata, timestamps |
| 2 | `runtime_conformance_tests` | deterministic ReasonIR semantic results |
| 3 | `transaction_conformance_tests` | prepare, validate, commit, rollback, trace |
| 4 | `platform_conformance_tests` | normalized cross-SDK fixture comparison |

Run the complete framework and refresh the report:

```sh
python3 conformance/run_conformance.py
```

Run only the Python suites:

```sh
python3 -m unittest discover -s conformance -p 'test_*.py'
```

The framework consumes the canonical fixtures under `fixtures/` and the
versioned manifest under `conformance/fixtures/manifest.json`. A skipped SDK
toolchain is reported as unverified and never promoted to a passing
certification level.
