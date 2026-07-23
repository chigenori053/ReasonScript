# Knowledge Branch Evidence Specification v1.0

Specification ID: knowledge-branch-evidence/1.0
Status: Draft

Depends on:
- semantic-simulation/0.2
- knowledge-emergence/0.2
- function-control-flow/1.0

## Purpose

Knowledge emergence is branch-aware. When multiple execution branches can produce the same target state, each knowledge item preserves the execution branch evidence that produced it.

## Identity

Previous identity:

```text
(source, relation, target)
```

New identity:

```text
(source, relation, target, evidence_path)
```

Knowledge is merged only when the target and deterministic path signature are identical.

## Branch Evidence Fields

Each knowledge item includes:

```json
{
  "evidence_path": ["Select.return.true"],
  "path_signature": "Select.return.true",
  "branch_id": "true"
}
```

For multiple branch decisions, the signature joins branch transition identifiers with `|`:

```text
CheckUser.return.true|CheckPermission.return.false
```

## Execution Plan Integration

ExecutionPlan exposes the branch selected by the planned path:

```json
{
  "selected_branch": "Select.return.true",
  "selected_branches": ["Select.return.true"],
  "path_signature": "Select.return.true"
}
```

## Simulation Integration

Simulation traces include branch selection events:

```json
{
  "event_type": "BranchSelection",
  "branch": "Select.return.true"
}
```

## Knowledge Integration

Default knowledge extraction consumes simulation branch selection and emits knowledge only for the selected path. Audit tooling may request all branch paths while preserving each distinct signature.

## Validation Rules

- KBE-001: Knowledge entries with different path signatures must not be merged.
- KBE-002: Knowledge entries with identical path signatures must be merged.
- KBE-003: Path signature generation must be deterministic.
- KBE-004: Branch evidence must be preserved during export/import.
