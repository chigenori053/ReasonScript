# ReasonScript Language Surface Phase 1.1

## AST Mapping Validation Report v0.1

Status: PASS

Validation date: 2026-06-14

Target: Language Surface syntax to deterministic AST mapping

## 1. Executive Result

The Phase 1.1 Language Surface constructs map deterministically to immutable
AST nodes. Source order is preserved, invalid forms are rejected before
compilation, JSON serialization is stable, and valid Surface AST values
project into the existing `reasonscript-ast/0.1` ABI.

The projected AST compiles to schema-valid `reason-ir/0.1`. A schema-valid
ExecutionPlan can be generated from its transitions without changing an
existing AST, parser, compiler, Reason IR, or Runtime interface version.

## 2. Compatibility Decision

The draft describes `ProgramNode` as the root while the validated
`reasonscript-ast/0.1` ABI uses one semantic `ModuleNode` root. Replacing that
root would violate the stated compatibility requirement.

The validation therefore establishes:

```text
Surface ProgramNode
  -> Surface ModuleNode[]
  -> semantic ModuleNode[] using reasonscript-ast/0.1
```

This is an additive frontend layer. Existing parser/compiler consumers remain
unchanged.

## 3. Deliverables

| Artifact | Result |
|---|---|
| `docs/ReasonScript_Language_Surface_AST_Mapping_v0.1.md` | CREATED |
| `frontend/language_surface/lexer.py` | CREATED |
| `frontend/language_surface/nodes.py` | CREATED |
| `frontend/language_surface/parser.py` | CREATED |
| `frontend/language_surface/validation.py` | CREATED |
| `frontend/language_surface/integration.py` | CREATED |
| `frontend/schemas/language_surface_ast.schema.json` | CREATED |
| `language_surface_ast_mapping_tests/` | CREATED |
| `Language_Surface_Phase_1_1_AST_Mapping_Validation_Report.md` | CREATED |

## 4. Layer Results

### Layer A: Node Generation

| ID | Result |
|---|---|
| A-001 ProgramNode | PASS |
| A-002 ModuleNode | PASS |
| A-003 ImportNode | PASS |
| A-004 State declaration nodes | PASS |
| A-005 RelationNode | PASS |
| A-006 TransitionNode | PASS |
| A-007 CalculationNode | PASS |
| A-008 MatchNode | PASS |

All nodes are frozen dataclasses. Mutation raises
`FrozenInstanceError`. Ordered tuple fields retain source order.

### Layer B: Syntax to AST

| ID | Result |
|---|---|
| B-001 Single Module | PASS |
| B-002 Multiple Module | PASS |
| B-003 Nested Statements | PASS |
| B-004 Conditional | PASS |
| B-005 Match | PASS |
| B-006 Calculation | PASS |
| B-007 Transition | PASS |

Repeated parsing of equal source produces structurally equal AST values.

### Layer C: Invalid Inputs

| ID | Result |
|---|---|
| C-001 Missing Identifier | PASS, rejected |
| C-002 Missing Relation Target | PASS, rejected |
| C-003 Missing Transition State | PASS, rejected |
| C-004 Missing Calculation Result | PASS, rejected |
| C-005 Empty Match | PASS, rejected |

AST-V004 unresolved relation references are also rejected.

### Layer D: Compiler Integration

| ID | Result |
|---|---|
| D-001 AST to Reason IR | PASS |
| D-002 AST to ExecutionPlan | PASS |
| D-003 AST Stability | PASS |
| D-004 AST Serialization | PASS |

Generated Reason IR validates against `reason_ir.schema.json`. Generated
plans validate against `execution_plan.schema.json`. Serialized Surface AST
validates against `language_surface_ast.schema.json` and round-trips without
loss.

## 5. Validation Rules

| Rule | Result |
|---|---|
| AST-V001 Node Type Validity | PASS |
| AST-V002 Identifier Validity | PASS |
| AST-V003 Module Integrity | PASS |
| AST-V004 Reference Resolution | PASS |
| AST-V005 Calculation Integrity | PASS |
| AST-V006 Transition Integrity | PASS |
| AST-V007 Match Integrity | PASS |

## 6. Mapping Observations

The validation preserves the distinction between source-facing declarations
and Runtime semantic concepts:

- Concept, Object, Event, Action, and Attribute are Surface AST declarations.
- They are recorded in the semantic initial State declaration inventory.
- Relation, Transition, and Calculation operations become semantic
  Transition nodes.
- A Surface Goal selects the semantic Goal target.
- Calculation `result` is stored once in the Surface AST and emits one final
  semantic Transition.

This mapping keeps exactly one semantic initial State and one semantic Goal,
as required by `reasonscript-ast/0.1`.

## 7. Scope Boundary

The parser validates the constructs defined by this Phase 1.1 draft. It does
not implement:

- optimization;
- macros;
- type inference;
- expression evaluation;
- planner path selection;
- Runtime execution semantics;
- a complete future Language Surface grammar.

Expression and pattern content is preserved as immutable source text for later
language phases.

## 8. Verification Record

Phase 1.1 validation:

```text
Ran 16 tests
OK
```

Complete Python regression:

```text
Ran 130 tests
OK (skipped=1)
```

The skip is the pre-existing optional Go adapter comparison because the Go
toolchain is not installed.

HybridRuntime regression:

```text
129 passed
0 failed
```

`python3 -m py_compile` and `git diff --check` completed without errors.

## 9. Exit Decision

The Phase 1.1 exit criteria are satisfied for the defined validation surface:

- Node definitions fixed;
- mappings fixed;
- AST validation passes;
- Surface parser passes;
- existing compiler accepts projected AST;
- Reason IR generation succeeds;
- ExecutionPlan artifact generation succeeds;
- serialization and stability pass.

The Language Surface may proceed to the next specification phase without an
AST, compiler, Reason IR, or Runtime interface version change.
