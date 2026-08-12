# MRA RUO / ReasonRelation — Query Phase 11 v0.1

Status: ACCEPTED
Specification ID: MRA-RUO-RR-QUERY-0.1
Date: 2026-08-12

## Purpose

Phase 11 exposes deterministic, read-only inspection of validated ReasonGraphs
without adding ReasonScript syntax, native graph mutation, or graph execution.

## Operations

`summary`, `entity`, `outgoing`, `incoming`, and `neighbors` query a validated
graph. Every result carries the source Graph ID and GraphHash, is ordered by
stable Relation ID, and leaves the graph unchanged. The CLI accepts either an
RGO-F1 `.rgraph` file or a verified RUO-F1 `.ruo` file projected through Phase 9.

## Out of scope

Graph mutation, traversal beyond immediate adjacency, query languages, native
graph queries, ReasonScript source syntax, MIRP transport, and graph execution.
