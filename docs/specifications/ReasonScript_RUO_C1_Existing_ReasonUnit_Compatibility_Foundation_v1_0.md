# ReasonScript RUO-C1 Existing ReasonUnit Compatibility Foundation v1.0

Status: ACCEPTED  
Date: 2026-07-20

## Purpose and Scope

RUO-C1 establishes the versioned compatibility contract between the validated
RUO-C0 Existing ReasonUnit baseline and a future formal `ReasonUnitObject`.
It adds no language syntax, native Runtime value, or `.ruo` format.

The normative implementation specification is the RUO-C1 specification accepted
for this phase. The repository implementation provides separate Object and Unit
identity domains; ownership and containment invariants; six state ownership
classes; internal, cross-payload, external, and structural relation classes; a
shared evidence registry; lifecycle and revision mappings; atomic Object
transactions; Runtime, Cluster, and Tensor projection contracts; and a lossless
Legacy Adapter reference representation.

## Required Interfaces

The compatibility module exposes `wrap_legacy_units`,
`validate_wrapped_object`, `project_existing_runtime_view`,
`unwrap_legacy_units`, and `compare_semantics`. Existing canonical Unit IDs are
never replaced by wrapping. Unknown legacy fields and project-local relations
are retained as namespaced extensions.

## Validation Contract

Generation MUST first validate RUO-C0 as 40/40 `VALIDATED`, verify every child
digest and byte size, and verify the RUO-C0 manifest self digest. RUO-C1 then
generates the specified 26 canonical artifacts. JSON uses UTF-8, LF, sorted
keys, finite values, logical paths, and the
`reasonscript-reasonunit-compatibility/1.0` profile.

RUO-C1 is `VALIDATED` only when T001–T056 pass, all preservation loss counts
are zero, three isolated generations are byte-identical, offline digest and
schema validation succeeds, existing RUO-C0 and Golden behavior is unchanged,
and canonical `reason ci --json` passes. The successful transition is
`PROCEED_TO_RUO-U1`.

## Change Protection

Lexer, parser, compiler, Runtime Core, Dynamic Cluster, Tensor Runtime,
diagnostics, existing Golden expectations, RUO-C0 artifacts, and external
project artifacts are protected and MUST NOT be modified by this phase.
