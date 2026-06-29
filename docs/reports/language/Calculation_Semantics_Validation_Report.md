# ReasonScript Calculation Semantics v0.1 Validation Report

Status: PASS

Validation date: 2026-06-14

Target: `reasonscript-calculation-semantics/0.1`

## 1. Executive Result

All CS-01 through CS-11 validation items pass. The adopted Calculation
Language Surface deterministically lowers through an immutable Calculation
AST and Calculation IR to existing Reason IR and ExecutionPlan documents.

Generated Reason IR executes in the existing conformance runtime without a
new Runtime behavior. The BuildingCost witness commits four ordered
StateDeltas and reaches its Result State. Existing interface versions and
schemas are unchanged.

## 2. Deliverables

| Required artifact | Result |
|---|---|
| `docs/ReasonScript_Calculation_Semantics_v0.1.md` | CREATED |
| `calculation_semantics_tests/` | CREATED |
| `binding_lowering_tests/` | CREATED |
| `expression_lowering_tests/` | CREATED |
| `decision_transition_tests/` | CREATED |
| `dependency_graph_tests/` | CREATED |
| `result_state_tests/` | CREATED |
| `execution_plan_tests/` | CREATED |
| `Calculation_Semantics_Validation_Report.md` | CREATED |

## 3. Validation Results

| ID | Result | Evidence |
|---|---|---|
| CS-01 Binding Lowering | PASS | Stable `<calculation>.binding.<name>` IDs, immutable dataclasses, equal repeated lowering |
| CS-02 Expression Lowering | PASS | Canonical expression trees and commutative operand normalization |
| CS-03 Arithmetic Transition IR | PASS | Six operators map to explicit Transition types |
| CS-04 Mathematical Transition IR | PASS | Required mathematical functions map to named Transition types |
| CS-05 Decision Transition IR | PASS | Conditional witness emits Compare then Decision |
| CS-06 Calculation Reference Resolution | PASS | `Area` resolves to `Area.result` and `Area.state.result` dependency |
| CS-07 Dependency Graph | PASS | Stable topological order; cycles fail before plan generation |
| CS-08 Result State Mapping | PASS | Eigenvalues and vectors are one structured EigenState |
| CS-09 Failure State Mapping | PASS | Six Calculation statuses embed in existing InferenceResult State data |
| CS-10 Numeric Policy | PASS | Real `sqrt(-1)` rejects; Complex mode returns `i` |
| CS-11 ExecutionPlan Generation | PASS | BuildingCost emits Multiply, Multiply, Multiply, Add |

## 4. Determinism Evidence

The witness implementation in `calculation_semantics_tests/model.py` uses:

- frozen AST and IR dataclasses;
- structural canonical expression tuples;
- sorted operands for commutative arithmetic;
- stable names derived from calculation, binding, target, and sequence;
- lexical tie-breaking in topological sorting;
- explicit dependency-cycle rejection;
- one-based stable ExecutionPlan step IDs.

Repeated parsing and lowering produce structurally equal AST, Calculation IR,
Reason IR, and ExecutionPlan values.

## 5. Runtime and ABI Compatibility

Generated documents validate against the unchanged:

- `schemas/reason_ir.schema.json`;
- `schemas/execution_plan.schema.json`;
- `schemas/inference_result.schema.json`.

Calculation-specific information is represented using existing extension
surfaces:

- State `data` for bindings, numeric policy, and Result status;
- Transition `relation` for operation identity;
- Transition `effect` for canonical expression and input references;
- Reason IR `metadata` for calculation semantic version and order.

No existing frontend AST, schema, DTO, conformance runtime, RuntimeReal,
RuntimeComplex, or HybridRuntime source file was modified.

## 6. BuildingCost Witness

The source:

```text
width = 10
height = 20
area = width * height
cost = area * 100
tax = cost * 0.1
result = cost + tax
```

lowers to:

```text
step-1 MultiplyTransition -> area
step-2 MultiplyTransition -> cost
step-3 MultiplyTransition -> tax
step-4 AddTransition      -> result
```

The existing Python conformance runtime reports:

```text
status = completed
state_delta_count = 4
```

## 7. Scope Boundary

This result validates deterministic semantic mapping for the defined v0.1
surface and witness suite. It does not claim:

- completeness of a parser for the future full Language Surface;
- completeness of symbolic or numeric mathematical solvers;
- a type, collection, iteration, or unit system;
- new Runtime support for Calculation-specific status values.

Calculation statuses remain domain State data and map to existing
InferenceResult statuses.

## 8. Verification

Calculation-specific validation:

```text
Ran 18 tests
OK
```

Complete Python regression:

```text
Ran 114 tests
OK (skipped=1)
```

The skip is the pre-existing optional Go adapter check because the Go
toolchain is not installed.

HybridRuntime regression:

```text
129 passed
0 failed
```

`python3 -m py_compile` and `git diff --check` also completed without errors.

## 9. Exit Decision

The completion criteria are satisfied. The mapping:

```text
Calculation Syntax -> Calculation IR -> Reason IR -> ExecutionPlan
```

is validated as a normative component for the ReasonScript Language Surface
Specification Phase.
