# ReasonScript Calculation Semantics v0.1

Status: VALIDATED FOR THE DEFINED LANGUAGE SURFACE

Semantic version: `reasonscript-calculation-semantics/0.1`

Compatible interfaces:

- `reasonscript-language/0.1`
- `reasonscript-operational-semantics/0.1`
- `reasonscript-computation-model/0.1`
- `reason-ir/0.1`
- `execution-plan/0.1`
- HybridRuntime v0.2

## 1. Purpose

This specification defines the deterministic lowering of the adopted
Calculation Language Surface into the existing ReasonScript runtime model:

```text
Calculation source
  -> immutable Calculation AST
  -> Calculation IR
  -> Reason IR 0.1
  -> ExecutionPlan 0.1
  -> Runtime
```

It introduces no new Runtime commit, planning, StateDelta, or InferenceResult
behavior. Calculation is a surface representation of State transition
computation.

## 2. Calculation Unit

A calculation has one stable name, one Goal annotation, an ordered body, and
exactly one `result` assignment:

```text
pub calculation Name goal:value {
    statements
    result = expression
}
```

The Calculation AST is immutable. Source order is preserved inside one
calculation. Calculation order across a program is determined by the
dependency graph, with lexical calculation name as the deterministic
tie-breaker for independent nodes.

## 3. Binding Semantics

```text
let x = expression
```

lowers to an immutable binding State entry:

```text
Binding(
  binding_id = "<Calculation>.binding.<name>",
  state_id   = "<Calculation>.state.<name>",
  name,
  value
)
```

Binding IDs are derived only from the calculation and binding names. A
binding does not add a Runtime commit step; it is part of the complete input
State snapshot. Rebinding the same lexical name is invalid at language
validation time.

## 4. Expression Semantics

Every non-literal calculation expression has a canonical tree form:

```text
(TransitionType, attributes, canonical operands)
```

Operands of commutative `AddTransition` and `MultiplyTransition` nodes are
ordered by canonical structural representation. Therefore `x + y` and
`y + x`, and likewise multiplication, produce equivalent expression graphs.
Non-commutative operand order is preserved.

References to local bindings or assignments become explicit Transition input
references. A bare calculation name resolves to that calculation's sole
Result State:

```text
Area -> Area.result -> Area.state.result
```

## 5. Transition Mapping

### 5.1 Arithmetic

| Surface operator | Calculation IR relation |
|---|---|
| `+` | `AddTransition` |
| `-` | `SubtractTransition` |
| `*` | `MultiplyTransition` |
| `/` | `DivideTransition` |
| `^` | `PowerTransition` |
| `%` | `ModuloTransition` |

Arithmetic expressions MUST NOT bypass Transition generation.

### 5.2 Mathematical Functions

| Surface function | Calculation IR relation |
|---|---|
| `differentiate(x)` | `DifferentiateTransition` |
| `integrate(x)` | `IntegrateTransition` |
| `det(x)` | `DeterminantTransition` |
| `inverse(x)` | `InverseTransition` |
| `eigen(x)`, `eigenvalues(x)` | `EigenvalueTransition` |
| `simplify(x)` | `SimplifyTransition` |
| `sqrt(x)` | `SquareRootTransition` |

These relations identify operation semantics. Concrete mathematical
algorithms remain evaluator responsibilities under the Computation Model.

### 5.3 Decisions

Conditional syntax normalizes to:

```text
CompareTransition
  -> DecisionTransition
```

`if`, `elseif`, `else`, and `match` are surface forms over the same explicit
comparison and decision-node model. Each branch that joins MUST assign the
same target State. Equal frozen inputs and numeric policy select the same
branch.

## 6. Dependency Graph

A calculation reference creates a directed dependency edge:

```text
DependencyEdge(
  source_calculation,
  target_calculation,
  source_state = "<source>.state.result"
)
```

The graph is validated before Reason IR or ExecutionPlan generation. A
topological sort determines execution order. A cycle is a lowering failure;
the Runtime is not invoked and no StateDelta is produced.

## 7. Reason IR Mapping

The complete calculation program lowers to one existing Reason IR document:

- bindings are stored in `initial_state.data.bindings`;
- numeric mode is stored in `initial_state.data.numeric_mode`;
- each Calculation IR operation becomes a Reason IR Transition;
- the operation type is the Transition `relation`;
- canonical expression and input edges are stored in Transition `effect`;
- the last calculation Result State is the existing `reach_state` Goal;
- semantic version and calculation order are Metadata.

The Reason IR Transition chain is continuous. The first calculation starts at
its binding State. Each later calculation starts at the previously committed
calculation Result State. No Reason IR field or schema version is added.

## 8. ExecutionPlan Mapping

ExecutionPlan steps are emitted in deterministic topological and statement
order. Every step references exactly one generated Transition. Step IDs are
the one-based sequence `step-1`, `step-2`, and so on.

The selected path is acyclic because:

1. the calculation dependency graph is acyclic;
2. assignment targets produce new State identities;
3. generated steps preserve a continuous source/target chain.

Binding initialization does not create plan steps. For BuildingCost, the
normative selected relations are:

```text
MultiplyTransition
MultiplyTransition
MultiplyTransition
AddTransition
```

## 9. Result and Failure Mapping

Each calculation has exactly one Result State. Scalar values are stored
directly. Composite results are one structured State, for example:

```text
EigenState {
  values,
  vectors
}
```

Calculation status is carried in `final_state.data` without changing the
InferenceResult schema:

| Calculation status | InferenceResult status |
|---|---|
| `Solved` | `completed` |
| `Partial` | `decision_required` |
| `Unresolved` | `decision_required` |
| `MultipleCandidates` | `decision_required` |
| `Contradiction` | `rejected` |
| `Impossible` | `rejected` |

The Result State also carries `value`, `confidence`, and `trace`. This is
domain State data, not a new Runtime status enumeration.

## 10. Numeric Policy

Numeric policy is frozen before lowering or evaluation:

- Real mode rejects results outside the real domain.
- Complex mode admits complex results and represents them as structured,
  JSON-compatible values at the DTO boundary.

For `sqrt(-1)`, Real mode produces a validation rejection before commit;
Complex mode produces `Solved` with value `i`.

## 11. Determinism Boundary

Equal source, calculation names, evaluator version, numeric policy, and frozen
inputs MUST produce structurally equal:

- Calculation AST;
- Calculation IR and binding IDs;
- dependency edges and topological order;
- Reason IR;
- ExecutionPlan;
- Result State mapping.

The existing Operational Semantics determinism boundary applies after
lowering.

## 12. Compatibility

The validation adds no interface version and changes no existing Runtime,
frontend AST, DTO, or schema file. Generated documents conform to
`reason_ir.schema.json`, `execution_plan.schema.json`, and
`inference_result.schema.json`.

This validation establishes the Calculation lowering contract. It does not
define a type system, collections, iteration, units, MemorySpace, WorldModel,
DBM, distributed execution, or mathematical solver completeness.

## 13. Conformance

The executable reference is
`calculation_semantics_tests/model.py`. Required suites are:

```text
calculation_semantics_tests/
binding_lowering_tests/
expression_lowering_tests/
decision_transition_tests/
dependency_graph_tests/
result_state_tests/
execution_plan_tests/
```

A conforming implementation MUST pass these suites and the existing Language,
Operational Semantics, Computation Model, schema, conformance, and
HybridRuntime regressions.
