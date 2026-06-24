# Playground Knowledge Branch Evidence Audit

Specification: knowledge-branch-evidence/1.0

## Summary

Knowledge emergence now carries branch-aware evidence. Execution plans, simulations, and knowledge items share branch identifiers such as `Select.return.true`.

## Matrix

| ID | Expected | Status |
| --- | --- | --- |
| KBE-001 | Different branch signatures remain distinguishable | IMPLEMENTED |
| KBE-002 | Identical path signatures merge | IMPLEMENTED |
| KBE-003 | Path signatures are deterministic | IMPLEMENTED |
| KBE-004 | Evidence path survives JSON export/import | IMPLEMENTED |

## Evidence Fields

Knowledge items include:

- `evidence_path`
- `path_signature`
- `branch_id`

Execution plans include:

- `selected_branch`
- `selected_branches`
- `path_signature`

Simulation traces include `BranchSelection` events.
