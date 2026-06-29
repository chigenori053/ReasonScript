# ReasonScript Language Surface Phase 1.3

## Statement Validation Report v0.1

Status: PASS

Validation date: 2026-06-14

Target: Statement AST, placement, references, ordering, and projection

## 1. Executive Result

Phase 1.3 is complete for the defined Surface language. Nine canonical
Statement node types are implemented, parser placement is deterministic,
Goal and Constraint references are resolved by declaration kind, and
Calculation Result semantics are represented in statement order.

Statement AST values serialize and round-trip through a schema. Valid programs
project to the existing semantic AST and generate schema-valid Reason IR and
ExecutionPlan artifacts without platform interface changes.

## 2. Compatibility Decision

Phase 1.1 and 1.2 used provisional `LetNode`, `IfNode`, and `MatchNode` names,
stored Transition requirements/goals in side fields, and stored Calculation
Result outside the body.

Phase 1.3 normalizes these into:

- canonical `*StatementNode` names;
- Require and Goal references as ordered Statements;
- Result as the final Calculation Statement.

The old Python node names remain aliases. JSON deserialization accepts the old
node type names, while new serialization emits the canonical Phase 1.3 names.
Existing semantic AST, compiler, and Reason IR interfaces are unchanged.

## 3. Deliverables

| Artifact | Result |
|---|---|
| `docs/ReasonScript_Language_Surface_Statement_v0.1.md` | CREATED |
| Statement hierarchy in `frontend/language_surface/nodes.py` | COMPLETED |
| Placement-aware parser | COMPLETED |
| Statement validation and reference resolution | COMPLETED |
| Statement semantic projection | COMPLETED |
| `frontend/schemas/statement.schema.json` | CREATED |
| Surface AST statement schema definitions | UPDATED |
| `statement_tests/` | CREATED |
| This validation report | CREATED |

## 4. Layer A: Statement Generation

| ID | Result |
|---|---|
| A-001 Let | PASS |
| A-002 Assignment | PASS |
| A-003 Result | PASS |
| A-004 Require | PASS |
| A-005 Goal | PASS |
| A-006 Reach | PASS |
| A-007 ExpressionStatement | PASS |
| A-008 IfStatement | PASS |
| A-009 MatchStatement | PASS |

## 5. Layer B: Placement

| ID | Result |
|---|---|
| B-001 Module Body | PASS |
| B-002 Transition Body | PASS |
| B-003 Calculation Body | PASS |
| B-004 Invalid Placement | PASS, rejected |

Assignment outside Calculation is rejected. Result is restricted to the
top-level Calculation body.

## 6. Layer C: References

| ID | Result |
|---|---|
| C-001 Goal Exists | PASS |
| C-002 Constraint Exists | PASS |
| C-003 Goal Type Match | PASS |
| C-004 Constraint Type Match | PASS |

Missing and wrong-kind references fail before projection.

## 7. Layer D: Ordering

| ID | Result |
|---|---|
| D-001 Statement Order | PASS |
| D-002 Result Last | PASS |
| D-003 Single Result | PASS |

Duplicate immutable Let bindings in one statement list are also rejected.

## 8. Layer E: Compiler Compatibility

| ID | Result |
|---|---|
| E-001 Statement Serialization | PASS |
| E-002 Statement Round Trip | PASS |
| E-003 Semantic Projection | PASS |
| E-004 Reason IR Generation | PASS |
| E-005 ExecutionPlan Generation | PASS |

Require maps to a semantic guard, Goal references remain ordered effect data,
Reach selects the semantic target, and Calculation statements generate
ordered semantic Transitions.

## 9. Statement Validation

| Rule | Result |
|---|---|
| ST-V001 Known Statement Type | PASS |
| ST-V002 Valid Placement | PASS |
| ST-V003 Reference Resolution | PASS |
| ST-V004 Single Result Rule | PASS |
| ST-V005 Goal Resolution | PASS |
| ST-V006 Constraint Resolution | PASS |
| ST-V007 Statement Order Integrity | PASS |

## 10. Compatibility Audit

No interface version or schema field was changed in:

- `reasonscript-ast/0.1`;
- `parser/0.1`;
- `compiler/0.1`;
- `reason-ir/0.1`;
- `execution-plan/0.1`;
- Calculation Semantics v0.1;
- HybridRuntime.

All changes remain inside the additive Language Surface frontend and its
Surface AST schema.

## 11. Scope Boundary

Phase 1.3 does not perform type checking, type inference, optimization,
expression evaluation, Runtime execution, or planner path selection.

Statement projection establishes compiler-compatible structure; it does not
add Runtime semantics.

## 12. Verification

| Command scope | Result |
|---|---|
| Phase 1.3 Statement tests | PASS, 16 tests |
| Phase 1.2 Expression and Pattern tests | PASS, 18 tests |
| Phase 1.1 AST Mapping tests | PASS, 16 tests |
| Full Python regression suite | PASS, 164 tests, 1 skipped |
| Full HybridRuntime Cargo suite | PASS, 129 tests |
| Python bytecode compilation | PASS |
| Git whitespace validation | PASS |

The skipped Python test is an existing conditional test and is not a Phase 1.3
failure.

## 13. Exit Decision

The Phase 1.3 exit criteria are satisfied:

- Statement hierarchy fixed;
- placement fixed;
- validation fixed;
- parser tests pass;
- serialization tests pass;
- compiler compatibility passes;
- Reason IR generation passes;
- ExecutionPlan generation passes.

The Language Surface Core now contains Declaration, Expression, Pattern, and
Statement layers and may proceed to a Type or deeper Calculation Integration
phase.
