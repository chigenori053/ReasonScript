# ReasonScript Phase RUO-M1: Legacy ReasonUnit Migration v1.0

Status: ACCEPTED — implementation target  
Date: 2026-07-20

This repository adopts the supplied RUO-M1 specification as the normative
contract. Migration is a controlled program with read-only deterministic
discovery, SHA-256 source freeze, versioned analysis and mapping, dry-run,
staging-only conversion, semantic comparison, validation, explicit atomic
publication, consumer cutover evidence, and explicit rollback.

Legacy source bytes are immutable. Explicit identities are preserved;
otherwise identity derives only from the declared namespace, logical project
identity, semantic locator, and entity kind. Filesystem path, enumeration
order, host, worker, time, and tensor position never define identity.

Acceptance requires zero semantic loss or lossless retention under the
registered non-critical `legacy` extension namespace. A target is not
publishable until its source and plan digests still match and its staged RUO
file passes RUO-U1 and RUO-F1 validation. Publication and rollback require an
explicit filesystem-write capability and use project-batch atomic replacement.
Legacy inputs and migration evidence remain available after either operation.

The consolidated interface is `reason object migrate` with `discover`,
`analyze`, `plan`, `dry-run`, `convert`, `compare`, `validate`, `publish`,
`rollback`, `status`, and `validate-phase` operations. Network access and
symlink/root escapes are prohibited.

Validation is RUO-M1-T001 through T063, all 24 diagnostics, 21 fixture
classes, 57 canonical artifacts, three-run byte equality, preservation of the
immutable C0–N2 stack, Agent Protocol validation, and `reason ci --json`.
Success transitions to `PROCEED_TO_RUO-W1`.
