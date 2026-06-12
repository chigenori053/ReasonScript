# Conformance Report v0.1

Generated: 2026-06-13

ABI: `reason-ir/0.1`

## Layer Results

| Layer | Suite | Result | Notes |
|---|---|---|---|
| 0 | `schema_conformance_tests` | PASS |  |
| 1 | `dto_conformance_tests` | PASS |  |
| 2 | `runtime_conformance_tests` | PASS |  |
| 3 | `transaction_conformance_tests` | PASS |  |
| 4 | `platform_conformance_tests` | PASS | contains skipped toolchains |

## SDK Certification

| SDK | Level | Certification |
|---|---:|---|
| rust | 3 | ReasonScript SDK Level 3 Certified |
| python | 1 | ReasonScript SDK Level 1 Certified |
| typescript | 0 | Schema Compatible |
| go | 0 | Schema Compatible |
| java | 0 | Schema Compatible |

## Limitations

- Layer 4 compares Rust, Python, and TypeScript in this environment.
- Go remains unverified when the Go toolchain is unavailable.
- Java DTO declarations compile, but a JSON codec adapter is not implemented.
- Full Compatible certification requires all five SDKs to pass Layer 4.

The framework is complete, but Full Compatible certification is withheld
until Go and Java provide executable DTO codecs and all five SDKs pass
the same Layer 4 fixture run.
