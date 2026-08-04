# ReasonScript RUO-U1 Universal ReasonUnit Object Data Model v1.0

Status: IMPLEMENTED

Date: 2026-07-20

This repository implements the normative RUO-U1 specification supplied for Phase RUO-U1. The universal logical model defines stable Object, Unit, Payload, State, Relation, Evidence, Constraint, Revision, Transaction, and Projection identities; explicit ownership and acyclic containment; nine typed Payload profiles; state and knowledge-status distinctions; evidence and dependency invalidation; immutable revisions and atomic Object transactions; deterministic partial-loading queries; namespaced extension retention; and derived Runtime Execution Projections.

The implementation is a JSON-compatible reference model and validation carrier. It does not introduce ReasonScript syntax, a native Runtime type, a final `.ruo` byte format, Tensor storage, network behavior, or WorldModel integration.

Canonical validation is provided by:

```sh
reason reasonunit-object generate
reason reasonunit-object validate
reason ci --json
```

The mandatory RUO-U1 matrix is `RUO-U1-T001` through `RUO-U1-T065`. Successful validation produces 38 canonical artifacts and the transition `PROCEED_TO_RUO-F1`.
