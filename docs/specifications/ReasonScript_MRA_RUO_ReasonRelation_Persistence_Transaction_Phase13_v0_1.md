# MRA RUO / ReasonRelation — Persistence Transaction Phase 13 v0.1

Status: ACCEPTED
Specification ID: MRA-RUO-RR-PERSIST-0.1
Date: 2026-08-12

## Purpose

Phase 13 applies the validated GraphTransaction model to existing canonical
RGO-F1 files. It provides compare-and-commit persistence without partial
publication.

## Contract

The caller supplies a proposal, expected GraphHash, and `ruo:transaction:*`
identity. The graph is decoded and validated before the copy-on-write proposal
is evaluated. Rejected or stale proposals retain the exact original file bytes.
A valid proposal is published atomically through the RGO-F1 writer.

## Out of scope

Multi-file or distributed transactions, locking across processes, conflict
resolution policy, native graph mutation, ReasonScript syntax, and execution.
