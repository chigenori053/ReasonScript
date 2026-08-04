# ReasonScript Computation Model v0.1

Status: VALIDATED FOR THE DEFINED WITNESS SUITE

Semantic version: `reasonscript-computation-model/0.1`

Related specifications:

- `reasonscript-operational-semantics/0.1`
- `reason-ir/0.1`
- `reasonscript-language/0.1`

## 1. Purpose

This specification defines how mathematical computation is represented by the
existing ReasonScript execution model. It validates semantic expressiveness;
it does not specify a computer algebra system, numerical error standard,
algorithm-selection policy, or performance requirement.

The computation rule is:

```text
State_i --Transition_i--> State_i+1
```

A solution procedure is:

```text
Reason IR -> Planner -> ExecutionPlan -> Executor
          -> ordered StateDelta chain -> InferenceResult
```

No mathematical operation receives a second commit mechanism.

## 2. Normative Mapping

### 2.1 Mathematical State

A mathematical State is an OS-02 complete immutable snapshot:

```text
MathematicalState = <state_id, state_type, data>
```

`data` MAY contain any JSON-compatible representation required by the domain,
including:

- scalar, complex, rational, and symbolic values;
- expressions, equations, functions, and domain restrictions;
- vectors, matrices, tensors, decompositions, and vector fields;
- sets, graphs, algebraic structures, premises, and proof facts.

Intermediate expressions and structures are valid States. An implementation
MUST publish a new complete snapshot at each commit and MUST NOT mutate an
observed input snapshot.

### 2.2 Mathematical Transition

A mathematical operation is an OS-03 Transition:

```text
MathematicalTransition =
  <transition_id, source, relation, target, expected_cost, guard?, effect?>
```

The relation identifies the mathematical rule or algorithmic step. The effect
is a deterministic, side-effect-free candidate-state function for equal
frozen inputs and evaluator versions:

```text
effect(State_i.data) -> candidate State_i+1.data
```

Examples include polynomial rewrite, differentiation, row elimination,
identity application, graph-node visitation, and logical inference.

### 2.3 Mathematical Procedure

Every finite solution procedure MUST be represented by an immutable ordered
ExecutionPlan. Each step references exactly one declared Transition. The
source and target identities MUST form a continuous chain from the initial
State to a Goal-satisfying State.

Algorithm-internal progress that affects semantic reproducibility or proof
evidence SHOULD be represented as intermediate States. An implementation MAY
use hidden local calculations inside one atomic Transition when those
calculations have no separately observable commit boundary.

### 2.4 Result and Proof

Every committed mathematical step produces exactly one StateDelta. Adjacent
deltas MUST satisfy:

```text
delta[i].after_state = delta[i+1].before_state
```

InferenceResult carries the final State, the complete ordered delta chain, and
proof step references. A proof is evidence about executed steps; it is not an
alternative mutation path.

## 3. Domain Coverage

The v0.1 validation witnesses cover:

| Domain | Required witnesses |
|---|---|
| Advanced algebra | expansion, factorization, cubic, quartic, complex roots, rational simplification |
| Calculus | differentiation, partial differentiation, integration, multiple integration, ODE |
| Linear algebra | multiplication, inverse, determinant, eigenpairs, LU, QR, SVD |
| Trigonometry | sin/cos/tan, inverse functions, identities, transformations |
| Multivariable mathematics | gradient, Jacobian, Hessian, optimization, vector fields |
| Abstract mathematics | graph traversal, logic, sets, groups, rings, category composition |

Passing a witness establishes representability for that operation and
procedure shape. It does not establish completeness of a general-purpose
solver for every input in the mathematical domain.

## 4. Determinism

Mathematical execution is deterministic inside the OS-10 determinism boundary.
Equal initial State, Goal, Transition definitions, ExecutionPlan, evaluator
version, policies, and frozen external inputs MUST produce structurally equal
semantic results.

Floating-point approximation is deterministic only relative to a fixed
numeric evaluator and policy. Approximation error and platform portability are
outside this semantic validation.

## 5. Output Projection

Output policy is applied after computation to an InferenceResult:

```text
project(InferenceResult, OutputPolicy) -> Presentation
```

Supported validation projections are:

- numeric;
- rational;
- symbolic;
- State identity;
- proof/Transition chain.

Projection MUST NOT mutate the InferenceResult, recompute the procedure, alter
the ExecutionPlan, or add a StateDelta. Multiple projections MAY be produced
from the same completed result.

## 6. Operational Semantics Preservation

This model adds no new meaning to Goal, State, Transition, Constraint,
ExecutionPlan, StateDelta, or InferenceResult. Mathematical effects are bound
by OS-01 through OS-10, including:

- immutable complete State snapshots;
- prepare/validate/commit separation;
- commit-only mutation;
- immutable ordered plans;
- one delta per commit;
- continuous delta chains;
- auditable proof step references;
- deterministic outcomes for equal frozen inputs.

The executable witness model serializes its plans and results to the existing
`execution_plan.schema.json` and `inference_result.schema.json` contracts.

## 7. Conformance

Run the computation validation:

```sh
python3 -m unittest discover -s . -p 'test_*.py' -t . -v
```

The computation-specific directories are:

```text
computation_model_tests/
advanced_algebra_tests/
calculus_tests/
linear_algebra_tests/
trigonometry_tests/
multivariable_tests/
abstract_math_tests/
output_policy_tests/
```

A conforming v0.1 implementation MUST pass all computation witnesses and the
Operational Semantics regression suites without changing existing semantic
contracts.

## 8. Validation Claim

The validated claim is:

```text
Every computation exercised by the v0.1 witness suite is representable as
an ordered State -> Transition -> State procedure under Operational
Semantics v0.1.
```

The universal statement "all computations are state transitions" is the
architectural hypothesis supported by these results. Finite executable tests
cannot constitute a mathematical proof over every possible computation.
