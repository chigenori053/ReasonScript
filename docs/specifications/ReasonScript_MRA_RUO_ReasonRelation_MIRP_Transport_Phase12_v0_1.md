# MRA RUO / ReasonRelation — MIRP Transport Phase 12 v0.1

Status: ACCEPTED
Specification ID: MRA-RUO-RR-MIRP-T1-0.1
Date: 2026-08-12

## Purpose

Phase 12 serializes the Phase 5 MIRP logical Graph Fragment into a canonical,
sealed local exchange message (`.mirp`). It makes fragments portable between
local processes and artifacts without defining a network protocol.

## Contract

MIRP-T1 contains canonical JSON Lines header, graph-fragment, and seal records.
It verifies record digests, a content-stream digest, Graph identity, and the
existing fragment hash. Export is atomic; import produces an RGO-F1 `.rgraph`
through its canonical writer.

## Out of scope

Network delivery, authentication, encryption, remote peers, retries, ordering,
distributed execution, graph mutation, and automatic discovery.
