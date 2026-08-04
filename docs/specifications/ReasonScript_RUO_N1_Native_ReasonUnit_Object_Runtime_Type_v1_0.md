# ReasonScript Phase RUO-N1: Native ReasonUnit Object Runtime Type Specification v1.0

Status: ACCEPTED — implementation target  
Date: 2026-07-20

This repository adopts the supplied RUO-N1 specification as the normative
phase contract. RUO-N1 adds a safe-Rust native Object store with namespaced
stable identity, generation-checked process handles, immutable snapshots,
atomic optimistic transactions, deterministic queries, resource lifecycle,
Tensor and execution views, FFI/CLI adapters, and canonical RUO-F1/T1
compatibility. It does not add language syntax, automatic model execution,
distributed transactions, migration, or WorldModel policy.

Validation is defined by RUO-N1-T001 through RUO-N1-T074 and requires all 54
canonical artifacts, three-run byte equality, prerequisite preservation,
Agent Protocol validation, and `reason ci --json`. Successful completion is
`VALIDATED` with transition `PROCEED_TO_RUO-N2`.

