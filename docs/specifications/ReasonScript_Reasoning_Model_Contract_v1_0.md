# ReasonScript Reasoning Model Contract v1.0

## Status
DRAFT FOR PHASE 8A IMPLEMENTATION

## Version
`reasonscript-reasoning-model/1.0`

## Phase
ReasonScript Phase 8A — Reasoning Model Contract

## Purpose
This specification defines the versioned contract for representing a Reasoning Model in ReasonScript.

A Reasoning Model is a structured, inspectable, and deterministic artifact that connects the existing ReasonScript reasoning pipeline to higher-level reasoning system construction.

The contract defines how the following elements are represented:

```text
InputState
  -> ReasoningPath
  -> ReasoningStep
  -> BranchDecision
  -> KnowledgeEmission
  -> EvaluationTarget
  -> Diagnostics
```

This specification does not introduce new source syntax, parser behavior, runtime execution semantics, or changes to the existing Reason IR execution model.

The purpose of Phase 8A is to establish a stable artifact contract that later phases can consume.

---

# 1. Scope

## 1.1 In Scope
Phase 8A defines:

```text
- ReasoningModel artifact structure
- InputState contract
- ReasoningPath contract
- ReasoningStep contract
- BranchDecision contract
- KnowledgeEmission contract
- EvaluationTarget contract
- Diagnostics contract
- Deterministic JSON serialization requirements
- Validation rules
- Minimal valid and invalid examples
```

## 1.2 Out of Scope
Phase 8A does not define:

```text
- New ReasonScript source syntax
- Natural language input decomposition
- Image, audio, or multimodal decomposition
- Runtime model execution
- Model training
- Probabilistic inference
- LLM behavior
- WorldModel integration
- Playground IDE visualization
- New Reason IR node semantics
```

These are deferred to later Phase 8 milestones.

---

# 2. Design Position

The Reasoning Model Contract is an artifact layer above the existing ReasonScript pipeline.

```text
Source
  -> Surface AST
  -> Semantic AST
  -> Reason IR
  -> ExecutionPlan
  -> Simulation
  -> Knowledge
  -> ReasoningModel
```

The contract is not a replacement for Reason IR, ExecutionPlan, Simulation, or Knowledge.

It is a structured envelope that allows downstream tools to inspect:

```text
- what input state was used
- which reasoning path was selected
- which steps were executed
- which branches were considered
- which knowledge was emitted
- which evaluation target should be checked
```

---

# 3. Compatibility Requirements

## 3.1 Parser Compatibility
Phase 8A must not change parser behavior.

Existing valid ReasonScript source must remain valid.
Existing invalid ReasonScript source must remain invalid unless explicitly changed by another accepted specification.

## 3.2 Runtime Compatibility
Phase 8A must not change existing runtime execution semantics.

The existing Reason IR, ExecutionPlan, Simulation, and Knowledge generation behavior must remain compatible.

## 3.3 CI Compatibility
The Reasoning Model contract validator must be callable from the canonical CI entry point.

```bash
./reason ci --json
```

Phase 8A may add a new CI validation phase, but it must not bypass or duplicate the canonical CI entry point.

---

# 4. Top-Level Artifact

## 4.1 ReasoningModel

A ReasoningModel artifact represents one inspectable reasoning model instance.

### Required Fields

```json
{
  "schema_version": "reasonscript-reasoning-model/1.0",
  "model_id": "string",
  "source_ref": {},
  "input_state": {},
  "reasoning_paths": [],
  "selected_path_id": "string",
  "knowledge_emissions": [],
  "evaluation_target": {},
  "diagnostics": []
}
```

### Field Definitions

| Field                 |   Type | Required | Description                                                      |
| --------------------- | -----: | -------: | ---------------------------------------------------------------- |
| `schema_version`      | string |      yes | Must be `reasonscript-reasoning-model/1.0`.                      |
| `model_id`            | string |      yes | Stable identifier for the reasoning model artifact.              |
| `source_ref`          | object |      yes | Reference to the originating source or artifact.                 |
| `input_state`         | object |      yes | Input state used by the reasoning model.                         |
| `reasoning_paths`     |  array |      yes | Candidate or executed reasoning paths.                           |
| `selected_path_id`    | string |      yes | ID of the selected reasoning path.                               |
| `knowledge_emissions` |  array |      yes | Knowledge items emitted by the reasoning process.                |
| `evaluation_target`   | object |      yes | Evaluation target for later report generation.                   |
| `diagnostics`         |  array |      yes | Diagnostics produced during artifact construction or validation. |
| `metadata`            | object |       no | Optional non-semantic metadata.                                  |

---

# 5. SourceRef Contract

## 5.1 Purpose
`source_ref` identifies the source or upstream artifact from which the ReasoningModel was produced.

## 5.2 Structure

```json
{
  "source_id": "animal_isa",
  "source_kind": "reason_script_source",
  "artifact_refs": {
    "reason_ir": "reason_ir.json",
    "execution_plan": "execution_plan.json",
    "simulation": "simulation.json",
    "knowledge": "knowledge.json"
  }
}
```

## 5.3 Required Fields

| Field           |   Type | Required | Description                                |
| --------------- | -----: | -------: | ------------------------------------------ |
| `source_id`     | string |      yes | Stable source identifier.                  |
| `source_kind`   | string |      yes | Source type.                               |
| `artifact_refs` | object |       no | Optional references to upstream artifacts. |

## 5.4 Allowed `source_kind`

```text
reason_script_source
reason_ir
execution_plan
simulation
knowledge
external_fixture
```

---

# 6. InputState Contract

## 6.1 Purpose
`input_state` represents the state given to the reasoning model.

In Phase 8A, this is a structured artifact only. It does not imply natural language decomposition or multimodal processing.

## 6.2 Structure

```json
{
  "input_id": "input_001",
  "input_kind": "structured_state",
  "units": [
    {
      "unit_id": "Dog",
      "unit_type": "object",
      "value": "Dog"
    },
    {
      "unit_id": "Animal",
      "unit_type": "object",
      "value": "Animal"
    }
  ],
  "relations": [
    {
      "relation_id": "rel_001",
      "relation_type": "IsA",
      "source": "Dog",
      "target": "Animal"
    }
  ]
}
```

## 6.3 Required Fields

| Field        |   Type | Required | Description                         |
| ------------ | -----: | -------: | ------------------------------------ |
| `input_id`   | string |      yes | Stable input identifier.            |
| `input_kind` | string |      yes | Input kind.                         |
| `units`      |  array |      yes | Input semantic or structural units. |
| `relations`  |  array |      yes | Relations between input units.      |

## 6.4 Allowed `input_kind`

Phase 8A supports the following values:

```text
structured_state
text
number
logic
```

However, Phase 8A only requires `structured_state` to be validated as fully supported.

Other kinds may be represented but must be marked as not executable unless a later specification activates them.

## 6.5 InputUnit

### Structure

```json
{
  "unit_id": "Dog",
  "unit_type": "object",
  "value": "Dog"
}
```

### Required Fields

| Field       |   Type | Required | Description             |
| ----------- | -----: | -------: | ------------------------ |
| `unit_id`   | string |      yes | Stable unit identifier. |
| `unit_type` | string |      yes | Unit classification.    |
| `value`     |    any |      yes | Unit value.             |

## 6.6 InputRelation

### Structure

```json
{
  "relation_id": "rel_001",
  "relation_type": "IsA",
  "source": "Dog",
  "target": "Animal"
}
```

### Required Fields

| Field           |   Type | Required | Description                 |
| --------------- | -----: | -------: | ---------------------------- |
| `relation_id`   | string |      yes | Stable relation identifier. |
| `relation_type` | string |      yes | Relation type.              |
| `source`        | string |      yes | Source unit ID.             |
| `target`        | string |      yes | Target unit ID.             |

---

# 7. ReasoningPath Contract

## 7.1 Purpose
A ReasoningPath represents one candidate or selected route through the reasoning process.

## 7.2 Structure

```json
{
  "path_id": "path_main",
  "path_signature": "Dog.IsA.Animal",
  "status": "selected",
  "steps": [
    {
      "step_id": "step_001",
      "step_type": "relation_check",
      "source": "Dog",
      "target": "Animal",
      "operation": "IsA",
      "evidence_refs": ["rel_001"]
    }
  ]
}
```

## 7.3 Required Fields

| Field            |   Type | Required | Description                   |
| ---------------- | -----: | -------: | ------------------------------ |
| `path_id`        | string |      yes | Stable path identifier.       |
| `path_signature` | string |      yes | Deterministic path signature. |
| `status`         | string |      yes | Path status.                  |
| `steps`          |  array |      yes | Ordered reasoning steps.      |

## 7.4 Allowed `status`

```text
selected
candidate
rejected
failed
```

## 7.5 Validation Rules

```text
RM-PATH-001: path_id must be unique within reasoning_paths.
RM-PATH-002: path_signature must not be empty.
RM-PATH-003: selected_path_id must reference exactly one existing path.
RM-PATH-004: exactly one path should have status selected when diagnostics do not contain fatal errors.
RM-PATH-005: steps must be ordered deterministically.
```

---

# 8. ReasoningStep Contract

## 8.1 Purpose
A ReasoningStep represents one atomic reasoning operation inside a path.

## 8.2 Structure

```json
{
  "step_id": "step_001",
  "step_type": "relation_check",
  "source": "Dog",
  "target": "Animal",
  "operation": "IsA",
  "evidence_refs": ["rel_001"]
}
```

## 8.3 Required Fields

| Field           |   Type | Required | Description                           |
| --------------- | -----: | -------: | -------------------------------------- |
| `step_id`       | string |      yes | Stable step identifier.               |
| `step_type`     | string |      yes | Reasoning step type.                  |
| `source`        | string |      yes | Source state/unit/artifact reference. |
| `target`        | string |      yes | Target state/unit/artifact reference. |
| `operation`     | string |      yes | Operation performed by the step.      |
| `evidence_refs` |  array |      yes | Evidence references used by the step. |

## 8.4 Allowed `step_type`

```text
state_transition
relation_check
calculation
function_return
branch_selection
knowledge_emission
runtime_operation
external_reference
```

## 8.5 Validation Rules

```text
RM-STEP-001: step_id must be unique within a path.
RM-STEP-002: step_type must be one of the allowed values.
RM-STEP-003: source must not be empty.
RM-STEP-004: target must not be empty.
RM-STEP-005: operation must not be empty.
RM-STEP-006: evidence_refs must be present, even when empty.
```

---

# 9. BranchDecision Contract

## 9.1 Purpose
BranchDecision records selected and rejected alternatives.

Branch decisions are required for reasoning traceability when multiple paths or conditional branches exist.

## 9.2 Structure

```json
{
  "branch_id": "branch_001",
  "decision_point": "Select.return",
  "selected": "Select.return.true",
  "rejected": ["Select.return.false"],
  "reason": "condition_evaluated_true",
  "evidence_refs": ["step_001"]
}
```

## 9.3 Required Fields

| Field            |   Type | Required | Description                            |
| ---------------- | -----: | -------: | ---------------------------------------- |
| `branch_id`      | string |      yes | Stable branch decision identifier.     |
| `decision_point` | string |      yes | Location or logical point of decision. |
| `selected`       | string |      yes | Selected branch signature.             |
| `rejected`       |  array |      yes | Rejected branch signatures.            |
| `reason`         | string |      yes | Reason for branch selection.           |
| `evidence_refs`  |  array |      yes | Evidence used for the decision.        |

## 9.4 Placement

Branch decisions may appear in:

```text
- ReasoningPath.metadata.branch_decisions
- ReasoningModel.metadata.branch_decisions
```

Phase 8A recommends placing branch decisions under model-level metadata when they describe the complete model, and under path-level metadata when they are path-local.

---

# 10. KnowledgeEmission Contract

## 10.1 Purpose
KnowledgeEmission records knowledge produced by the reasoning process.

It does not replace the existing Knowledge artifact.

It references or summarizes emitted knowledge in the ReasoningModel artifact.

## 10.2 Structure

```json
{
  "knowledge_id": "knowledge_001",
  "source_step_id": "step_001",
  "relation": "IsA",
  "source": "Dog",
  "target": "Animal",
  "evidence_path": ["step_001"],
  "path_signature": "Dog.IsA.Animal"
}
```

## 10.3 Required Fields

| Field            |   Type | Required | Description                                   |
| ---------------- | -----: | -------: | ----------------------------------------------- |
| `knowledge_id`   | string |      yes | Stable knowledge emission identifier.         |
| `source_step_id` | string |      yes | Step that emitted or justified the knowledge. |
| `relation`       | string |      yes | Knowledge relation.                           |
| `source`         | string |      yes | Source entity/state.                          |
| `target`         | string |      yes | Target entity/state.                          |
| `evidence_path`  |  array |      yes | Ordered evidence path.                        |
| `path_signature` | string |      yes | Signature of the reasoning path.              |

## 10.4 Validation Rules

```text
RM-KNOW-001: knowledge_id must be unique.
RM-KNOW-002: source_step_id should reference an existing step.
RM-KNOW-003: evidence_path must not be empty when the model is successful.
RM-KNOW-004: path_signature must match one existing reasoning path signature.
```

---

# 11. EvaluationTarget Contract

## 11.1 Purpose
EvaluationTarget defines what later evaluation must check.

Phase 8A only defines the target.

The actual EvaluationReport is implemented in Phase 8B or later.

## 11.2 Structure

```json
{
  "target_id": "eval_001",
  "goal": "Animal",
  "expected_relation": {
    "relation": "IsA",
    "source": "Dog",
    "target": "Animal"
  },
  "required_checks": [
    "reachability",
    "determinism",
    "evidence_completeness",
    "consistency"
  ]
}
```

## 11.3 Required Fields

| Field             |   Type | Required | Description                                          |
| ----------------- | -----: | -------: | ------------------------------------------------------ |
| `target_id`       | string |      yes | Stable evaluation target identifier.                 |
| `goal`            | string |      yes | Goal state or target concept.                        |
| `required_checks` |  array |      yes | Checks that a future evaluation report must perform. |

## 11.4 Optional Fields

| Field               |   Type | Description                           |
| ------------------- | -----: | ---------------------------------------- |
| `expected_relation` | object | Expected relation to validate.        |
| `expected_value`    |    any | Expected scalar or structured result. |
| `success_criteria`  | object | Additional criteria.                  |

## 11.5 Allowed `required_checks`

```text
reachability
determinism
evidence_completeness
consistency
minimality
branch_traceability
```

---

# 12. Diagnostics Contract

## 12.1 Purpose
Diagnostics describe validation or construction issues in the ReasoningModel artifact.

## 12.2 Structure

```json
{
  "code": "RM-001",
  "severity": "error",
  "message": "missing model_id",
  "location": "model_id"
}
```

## 12.3 Required Fields

| Field      |   Type | Required | Description                        |
| ---------- | -----: | -------: | ------------------------------------- |
| `code`     | string |      yes | Diagnostic code.                   |
| `severity` | string |      yes | Diagnostic severity.               |
| `message`  | string |      yes | Human-readable diagnostic message. |
| `location` | string |       no | Artifact path or source location.  |

## 12.4 Severity Levels

```text
info
warning
error
fatal
```

---

# 13. Diagnostic Codes

## 13.1 Top-Level Model Diagnostics

```text
RM-001: missing schema_version
RM-002: unsupported schema_version
RM-003: missing model_id
RM-004: invalid model_id
RM-005: missing source_ref
RM-006: missing input_state
RM-007: missing reasoning_paths
RM-008: missing selected_path_id
RM-009: selected_path_id does not reference an existing path
RM-010: missing evaluation_target
```

## 13.2 Input Diagnostics

```text
RM-IN-001: missing input_id
RM-IN-002: missing input_kind
RM-IN-003: unsupported input_kind
RM-IN-004: duplicate input unit_id
RM-IN-005: duplicate input relation_id
RM-IN-006: relation source does not reference an existing unit
RM-IN-007: relation target does not reference an existing unit
```

## 13.3 Path Diagnostics

```text
RM-PATH-001: duplicate path_id
RM-PATH-002: empty path_signature
RM-PATH-003: missing path status
RM-PATH-004: invalid path status
RM-PATH-005: no selected path
RM-PATH-006: multiple selected paths
```

## 13.4 Step Diagnostics

```text
RM-STEP-001: duplicate step_id within path
RM-STEP-002: invalid step_type
RM-STEP-003: missing step source
RM-STEP-004: missing step target
RM-STEP-005: missing step operation
RM-STEP-006: missing evidence_refs
```

## 13.5 Knowledge Diagnostics

```text
RM-KNOW-001: duplicate knowledge_id
RM-KNOW-002: source_step_id does not reference an existing step
RM-KNOW-003: empty evidence_path in successful model
RM-KNOW-004: path_signature does not reference an existing path signature
```

## 13.6 Evaluation Diagnostics

```text
RM-EVAL-001: missing target_id
RM-EVAL-002: missing goal
RM-EVAL-003: missing required_checks
RM-EVAL-004: invalid required_check
```

---

# 14. Deterministic JSON Serialization

## 14.1 Requirement
ReasoningModel artifacts must serialize deterministically.

Given identical semantic content, serialization must produce identical JSON output.

## 14.2 Rules

```text
DJ-001: Top-level fields must be emitted in the canonical order.
DJ-002: Arrays representing ordered execution must preserve execution order.
DJ-003: Arrays representing unordered collections must be sorted by stable ID.
DJ-004: Object keys must be sorted where no semantic order is defined.
DJ-005: Null fields should be omitted unless required by schema.
DJ-006: Metadata must not affect semantic validation.
```

## 14.3 Canonical Top-Level Field Order

```text
schema_version
model_id
source_ref
input_state
reasoning_paths
selected_path_id
knowledge_emissions
evaluation_target
diagnostics
metadata
```

---

# 15. Minimal Valid Example

```json
{
  "schema_version": "reasonscript-reasoning-model/1.0",
  "model_id": "AnimalReasoner",
  "source_ref": {
    "source_id": "animal_isa",
    "source_kind": "reason_script_source",
    "artifact_refs": {
      "reason_ir": "reason_ir.json",
      "execution_plan": "execution_plan.json",
      "simulation": "simulation.json",
      "knowledge": "knowledge.json"
    }
  },
  "input_state": {
    "input_id": "input_001",
    "input_kind": "structured_state",
    "units": [
      {
        "unit_id": "Animal",
        "unit_type": "object",
        "value": "Animal"
      },
      {
        "unit_id": "Dog",
        "unit_type": "object",
        "value": "Dog"
      }
    ],
    "relations": [
      {
        "relation_id": "rel_001",
        "relation_type": "IsA",
        "source": "Dog",
        "target": "Animal"
      }
    ]
  },
  "reasoning_paths": [
    {
      "path_id": "path_main",
      "path_signature": "Dog.IsA.Animal",
      "status": "selected",
      "steps": [
        {
          "step_id": "step_001",
          "step_type": "relation_check",
          "source": "Dog",
          "target": "Animal",
          "operation": "IsA",
          "evidence_refs": [
            "rel_001"
          ]
        }
      ]
    }
  ],
  "selected_path_id": "path_main",
  "knowledge_emissions": [
    {
      "knowledge_id": "knowledge_001",
      "source_step_id": "step_001",
      "relation": "IsA",
      "source": "Dog",
      "target": "Animal",
      "evidence_path": [
        "step_001"
      ],
      "path_signature": "Dog.IsA.Animal"
    }
  ],
  "evaluation_target": {
    "target_id": "eval_001",
    "goal": "Animal",
    "expected_relation": {
      "relation": "IsA",
      "source": "Dog",
      "target": "Animal"
    },
    "required_checks": [
      "reachability",
      "determinism",
      "evidence_completeness",
      "consistency"
    ]
  },
  "diagnostics": []
}
```

---

# 16. Invalid Example: Missing model_id

```json
{
  "schema_version": "reasonscript-reasoning-model/1.0",
  "source_ref": {
    "source_id": "animal_isa",
    "source_kind": "reason_script_source"
  },
  "input_state": {
    "input_id": "input_001",
    "input_kind": "structured_state",
    "units": [],
    "relations": []
  },
  "reasoning_paths": [],
  "selected_path_id": "path_main",
  "knowledge_emissions": [],
  "evaluation_target": {
    "target_id": "eval_001",
    "goal": "Animal",
    "required_checks": [
      "reachability"
    ]
  },
  "diagnostics": []
}
```

Expected diagnostic:

```text
RM-003: missing model_id
```

---

# 17. Invalid Example: Duplicate step_id

```json
{
  "schema_version": "reasonscript-reasoning-model/1.0",
  "model_id": "InvalidDuplicateStep",
  "source_ref": {
    "source_id": "duplicate_step",
    "source_kind": "external_fixture"
  },
  "input_state": {
    "input_id": "input_001",
    "input_kind": "structured_state",
    "units": [
      {
        "unit_id": "A",
        "unit_type": "object",
        "value": "A"
      },
      {
        "unit_id": "B",
        "unit_type": "object",
        "value": "B"
      }
    ],
    "relations": []
  },
  "reasoning_paths": [
    {
      "path_id": "path_main",
      "path_signature": "A.to.B",
      "status": "selected",
      "steps": [
        {
          "step_id": "step_001",
          "step_type": "state_transition",
          "source": "A",
          "target": "B",
          "operation": "transition",
          "evidence_refs": []
        },
        {
          "step_id": "step_001",
          "step_type": "state_transition",
          "source": "B",
          "target": "A",
          "operation": "transition",
          "evidence_refs": []
        }
      ]
    }
  ],
  "selected_path_id": "path_main",
  "knowledge_emissions": [],
  "evaluation_target": {
    "target_id": "eval_001",
    "goal": "B",
    "required_checks": [
      "reachability"
    ]
  },
  "diagnostics": []
}
```

Expected diagnostic:

```text
RM-STEP-001: duplicate step_id within path
```

---

# 18. Contract Validator Requirements

Phase 8A must provide a validator that can be called by tests and CI.

## 18.1 Required Validator Behavior

The validator must:

```text
- accept a JSON object or JSON file path
- validate top-level required fields
- validate enum values
- validate uniqueness constraints
- validate references
- produce deterministic diagnostics
- return structured validation result
```

## 18.2 Suggested Validation Result

```json
{
  "schema_version": "reasonscript-reasoning-model-validator/1.0",
  "valid": true,
  "diagnostics": []
}
```

## 18.3 Invalid Validation Result

```json
{
  "schema_version": "reasonscript-reasoning-model-validator/1.0",
  "valid": false,
  "diagnostics": [
    {
      "code": "RM-003",
      "severity": "error",
      "message": "missing model_id",
      "location": "model_id"
    }
  ]
}
```

---

# 19. Test Requirements

Phase 8A implementation must include tests for the following cases.

## 19.1 Valid Cases

```text
RM-T001: minimal valid model passes
RM-T002: valid model with artifact_refs passes
RM-T003: valid model with empty diagnostics passes
RM-T004: valid model serializes deterministically
```

## 19.2 Invalid Cases

```text
RM-T101: missing schema_version fails
RM-T102: unsupported schema_version fails
RM-T103: missing model_id fails
RM-T104: missing source_ref fails
RM-T105: missing input_state fails
RM-T106: duplicate input unit_id fails
RM-T107: relation source missing fails
RM-T108: relation target missing fails
RM-T109: missing reasoning_paths fails
RM-T110: duplicate path_id fails
RM-T111: selected_path_id missing target fails
RM-T112: duplicate step_id fails
RM-T113: invalid step_type fails
RM-T114: duplicate knowledge_id fails
RM-T115: knowledge source_step_id missing target fails
RM-T116: missing evaluation_target fails
RM-T117: invalid required_check fails
```

---

# 20. Suggested File Layout

```text
docs/specifications/ReasonScript_Reasoning_Model_Contract_v1_0.md
frontend/schemas/reasoning_model.schema.json
toolchain/reasoning_model_contract.py
tests/reasoning_model/test_reasoning_model_contract.py
tests/fixtures/reasoning_model/valid_minimal.json
tests/fixtures/reasoning_model/invalid_missing_model_id.json
tests/fixtures/reasoning_model/invalid_duplicate_step_id.json
docs/changelog/phase8a_reasoning_model_contract.md
```

---

# 21. Changelog Entry

```markdown
# ReasonScript Reasoning Model Contract v1.0 - 2026-07-05
## Status
DRAFT FOR IMPLEMENTATION
## Added
- Added versioned ReasoningModel contract.
- Added InputState contract.
- Added ReasoningPath and ReasoningStep contracts.
- Added BranchDecision contract.
- Added KnowledgeEmission contract.
- Added EvaluationTarget contract.
- Added deterministic JSON serialization requirements.
- Added RM-* diagnostic families.
- Added Phase 8A validation requirements.
## Unchanged
- Parser behavior is unchanged.
- Runtime execution behavior is unchanged.
- Reason IR execution semantics are unchanged.
- Existing source compatibility is unchanged.
## Deferred
- Input semantic decomposition.
- Reasoning evaluation report generation.
- Runtime reasoning model prototype.
- Playground IDE reasoning overview.
- WorldModel integration.
```

---

# 22. Phase 8A Completion Criteria

Phase 8A is complete when:

```text
- The ReasoningModel v1.0 specification exists.
- The JSON schema exists.
- The contract validator exists.
- Valid and invalid fixtures exist.
- Contract tests pass.
- Deterministic serialization is tested.
- CI entry point includes or can invoke the contract validation.
- No parser/runtime semantics are changed.
```

---

# 23. Implementation Instruction

Use the following implementation instruction for the coding agent:

```text
Implement Phase 8A — Reasoning Model Contract v1.0.
Add a versioned ReasoningModel contract without changing existing parser or runtime semantics.
Scope:
- Add docs/specifications/ReasonScript_Reasoning_Model_Contract_v1_0.md
- Add frontend/schemas/reasoning_model.schema.json
- Add toolchain/reasoning_model_contract.py
- Add tests/fixtures/reasoning_model valid and invalid fixtures
- Add tests/reasoning_model/test_reasoning_model_contract.py
- Add changelog entry
The contract must define:
- ReasoningModel
- SourceRef
- InputState
- InputUnit
- InputRelation
- ReasoningPath
- ReasoningStep
- BranchDecision
- KnowledgeEmission
- EvaluationTarget
- Diagnostics
- deterministic JSON serialization rules
Validation must cover:
- valid minimal model passes
- missing schema_version fails
- unsupported schema_version fails
- missing model_id fails
- missing input_state fails
- duplicate input unit_id fails
- invalid input relation reference fails
- duplicate path_id fails
- invalid selected_path_id fails
- duplicate step_id fails
- invalid step_type fails
- duplicate knowledge_id fails
- missing evaluation target fails
- invalid required_check fails
- deterministic serialization is stable
Constraints:
- Do not activate new source syntax.
- Do not change parser behavior.
- Do not change Reason IR execution behavior.
- Keep compatibility with the canonical reason ci entry point.
```

---

# 24. Final Definition

Phase 8A establishes the artifact-level contract for Reasoning Models.

It changes ReasonScript from:

```text
a state transition language with executable reasoning artifacts
```

to:

```text
a state transition language that can represent inspectable reasoning model artifacts
```

without yet changing source syntax or runtime behavior.

The implementation is therefore a contract-first milestone.
