# ReasonScript Language Surface Phase 1.6

## Calculation Integration Validation Report v0.1

Status: PASS

Validation date: 2026-06-14

## 1. Executive Result

The Calculation path from Language Surface through Statement AST, Calculation
AST, Semantic AST, Reason IR, and ExecutionPlan is implemented and validated.

Calculation visibility and Goal annotations are preserved, local variables
are resolved before lowering, invalid body statements are rejected, and each
execution path must terminate in one Result. Result lowering now uses an
explicit `ResultTransition`.

## 2. Deliverables

| Artifact | Result |
|---|---|
| `docs/ReasonScript_Language_Surface_Calculation_Integration_v0.1.md` | CREATED |
| Calculation visibility and serialization | COMPLETED |
| Calculation scope and Result validation | COMPLETED |
| Goal annotation resolution | COMPLETED |
| Semantic and Reason IR projection | COMPLETED |
| `frontend/schemas/calculation.schema.json` | CREATED |
| `calculation_integration_tests/` | CREATED |

## 3. Validation Matrix

| Layer | Items | Result |
|---|---|---|
| A Declaration | A-001 through A-003 | PASS |
| B Statement Integration | B-001 through B-005 | PASS |
| C Scope | C-001 through C-003 | PASS |
| D Invalid Calculation | D-001 through D-005 | PASS |
| E Compiler Compatibility | E-001 through E-005 | PASS |

## 4. Validation Rules

| Rule | Result |
|---|---|
| CAL-V001 Valid Calculation Node | PASS |
| CAL-V002 Allowed Statements Only | PASS |
| CAL-V003 Exactly One Result | PASS |
| CAL-V004 Result Finality | PASS |
| CAL-V005 Variable Resolution | PASS |
| CAL-V006 Expression Validity | PASS |
| CAL-V007 Statement Ordering | PASS |
| CAL-V008 Goal Annotation Validity | PASS |

## 5. Compatibility

No Semantic AST, Reason IR, ExecutionPlan, compiler, or Runtime schema version
was changed. Calculation data uses existing semantic transition fields and
the transition effect extension.

Older serialized Calculation nodes without `visibility` remain readable and
default to `Private`.

## 6. Control-Flow Decision

The draft combines an exactly-one-Result rule with examples containing one
Result in each Match branch. Validation therefore applies the rule per
execution path:

- sequential duplicate Results are invalid;
- a direct Result must be last;
- a terminal If requires Result on every branch and an Else;
- a terminal Match requires Result on every arm.

This is the deterministic interpretation that accepts the specified control
flow without allowing a Result-less execution path.

## 7. Exit Decision

The Phase 1.6 exit criteria are satisfied:

- Calculation syntax fixed;
- Calculation validation fixed;
- Calculation projection fixed;
- Calculation serialization fixed;
- compiler compatibility passes;
- Reason IR generation passes;
- ExecutionPlan generation passes.

## 8. Verification

| Scope | Result |
|---|---|
| Phase 1.6 Calculation Integration | PASS, 16 tests |
| Existing Calculation Semantics suite | PASS |
| Full Python regression | PASS, 180 tests, 1 skipped |
| Full HybridRuntime regression | PASS, 129 tests |
| Python bytecode compilation | PASS |
| Git whitespace validation | PASS |

The skipped Python test is an existing conditional test and is not a Phase 1.6
failure. No test failed.
