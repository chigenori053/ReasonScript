# Playground Match Semantic Integration Audit

MSI-001 is connected through the existing function semantic pipeline.

| Layer | Status | Evidence |
| --- | --- | --- |
| Surface parse | PASS | `match x { ... }` parses as `MatchStatementNode`. |
| Function IR | PASS | Emits `MatchExpressionIRNode`, `MatchCaseIRNode`, and `MatchSelectionIRNode`. |
| Reason IR | PASS | Each case lowers to a `FunctionReturnTransition`. |
| ExecutionPlan | PASS | Selected branch and path signature preserve `Select.match.*`. |
| Simulation | PASS | Emits `MatchEvaluation` before `BranchSelection`. |
| Knowledge | PASS | Preserves `branch_id`, `evidence_path`, and `match_evidence`. |
| Validation | PASS | Duplicate patterns and default ordering use MSI error codes. |

Acceptance coverage is in `tests/test_match_semantic_integration.py`.
