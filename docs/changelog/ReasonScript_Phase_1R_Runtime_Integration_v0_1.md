# ReasonScript Phase 1R Runtime Integration v0.1

## Added

- `.rsn` access to the public `tensor` namespace.
- `tensor.relu`, `tensor.softmax`, and `tensor.linear` contracts and runtime operations.
- Tensor semantic validation, Reason IR nodes, backend-neutral ExecutionPlan operations, runtime traces, and metadata.
- Finite-value safety diagnostics for empty, NaN, Infinity, and non-finite operation results.
- Bounded loop execution and loop-limit diagnostics.
- `reason project-validate` for standalone projects.
- `reason phase1r-validate` and canonical Phase 1R fixtures/artifacts.

## Changed

- Tensor registry size increases from 46 to 49 through additive inference functions.
- Backend/operation failures are normalized to the Phase 1R `TSF-012` contract.
- Reason IR metadata and ExecutionPlan output include deterministic Tensor integration data.

## Compatibility

No Tensor primitive was renamed or removed. Existing scalar, runtime, artifact, diagnostics, and CI entry contracts remain in place. Golden changes correspond only to the intentional specification-backed metadata additions.
