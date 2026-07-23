# ReasonScript Platform v0.1 Alpha Release Report

Status: Passed
Release date: 2026-06-13
Version: `0.1.0-alpha`

## Release Gate

| Gate | Result |
|---|---|
| Fixed interface identifiers | PASS |
| HybridRuntime test suite | PASS: 121 |
| AST validation suite | PASS: 12 |
| Platform conformance Layers 0-4 | PASS |
| AST ABI conformance Layers 0-4 | PASS |
| Parser conformance Layers 0-4 | PASS |
| Compiler conformance Layers 0-5 | PASS |
| End-to-end inference pipeline | PASS |
| Release manifest consistency | PASS |

## Evidence

- `release/v0.1-alpha/manifest.json`
- `release/v0.1-alpha/reports/release_validation_results.json`
- `conformance/reports/conformance_results_v0.1.json`
- `frontend/conformance/reports/ast_conformance_results_v0.1.json`
- `frontend/parser_conformance/reports/parser_conformance_results_v0.1.json`
- `frontend/compiler_conformance/reports/compiler_conformance_results_v0.1.json`

## Certification Boundary

The platform conformance implementation is complete. Full five-language SDK
compatibility is withheld because Go was not executable in the release
environment and Java does not yet provide a JSON codec adapter.

## Supplemental Runtime

`RuntimeReal` is a supplemental research Runtime and is not the normative
121-test release gate. Its suite was started during release validation and
contains a long-running semantic closure benchmark plus non-fatal unused-code
warnings.

## Decision

The required v0.1 Alpha interfaces and end-to-end pipeline satisfy the release
specification. ReasonScript Platform `0.1.0-alpha` is declared released.
