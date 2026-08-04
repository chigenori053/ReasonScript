# ReasonScript Phase RUO-N2: ReasonUnit Object Language and CLI Integration v1.0

Status: ACCEPTED — implementation target  
Date: 2026-07-20

This repository adopts the supplied RUO-N2 specification as the normative
contract. It adds explicit nested `reason_object` bindings to active `model`
and compatibility `module` constructs, typed AST/Reason IR/Execution Plan
mappings, filesystem capabilities, direct RUO-N1 native binding, the versioned
`ruo.*` function registry, deterministic formatting and diagnostics, and the
consolidated `reason object` CLI.

RUO-N1 historical artifact bytes remain immutable. Its implementation status
is interpreted as `IMPLEMENTED` while its phase remains `VALIDATED`, through
the additive RUO-N2 normalization artifact.

Validation is RUO-N2-T001 through T067, 56 canonical artifacts, three-run byte
equality, earlier-phase preservation, Agent Protocol, and `reason ci --json`.
Success transitions to `PROCEED_TO_RUO-M1`.

