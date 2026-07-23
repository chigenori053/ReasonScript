# ReasonScript Match Semantic Integration v1

Specification ID: `match-semantic-integration/1.0`

This implementation connects function-level `match` statements to semantic
branching:

- `MatchExpressionIRNode`, `MatchCaseIRNode`, and `MatchSelectionIRNode` are
  emitted in function IR metadata.
- Literal integer, float, bool, and `default` cases lower to
  `FunctionReturnTransition` branches such as `Select.match.2`.
- Execution plans, simulations, and knowledge units preserve the selected
  branch as the path signature.
- Simulation emits `MatchEvaluation` followed by `BranchSelection`.
- Knowledge units preserve `match_evidence`.

Validation rules:

- `MSI-001 duplicate match pattern`
- `MSI-002 default must be final case`
- `MSI-003 duplicate default case`
