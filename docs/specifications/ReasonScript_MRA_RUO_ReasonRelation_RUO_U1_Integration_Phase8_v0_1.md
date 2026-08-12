# MRA RUO / ReasonRelation — RUO-U1 Integration Phase 8 v0.1

Status: ACCEPTED
Specification ID: MRA-RUO-RR-U1-INT-0.1
Date: 2026-08-11
Prerequisite: MRA-RUO-RR-IM-0.1 and `reasonscript-reasonunit-object-universal/1.0`

## Purpose

Phase 8 establishes an explicit, read-only boundary from a valid RUO-U1 Object
snapshot to the MRA ReasonGraph v0.1 reference model. It does not replace or
rewrite the RUO-U1 logical model.

## Normative behavior

- The input MUST validate as RUO-U1 before it is projected.
- Projection MUST NOT mutate the source value.
- U1 Units preserve their `ruo:unit:*` identities in the graph.
- A U1 Relation is promoted only when its endpoint resolution is `resolved`
  and both endpoints are U1 Units.
- A Relation with a Payload, State, Evidence, external, missing, or otherwise
  non-Unit endpoint MUST be retained in a non-critical compatibility extension.
- `lossless` describes reversibility of the original U1 snapshot; it MUST NOT
  imply `canonical_coverage`.
- Reverse projection MUST return the original snapshot only when `lossless` is
  true.

## Out of scope

RUO-F1 encoding changes, Native Runtime behavior, ReasonScript syntax or
operations, automatic migration writes, and MIRP transport are out of scope.

## Acceptance

The adapter must prove: validated Unit-to-Unit promotion, lossless retention of
non-Unit relations, rejection before projection for invalid U1 input, profile
guarding of reverse projection, deterministic graph and source digests, and
the existing RUO regression suite.
