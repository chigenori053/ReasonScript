# ReasonScript Operational Semantics v0.1

Status: VALIDATED

Semantic version: `reasonscript-operational-semantics/0.1`

Related interfaces: `reasonscript-language/0.1`, `reason-ir/0.1`

## 1. Scope and Terms

This specification defines the normative execution meaning of a valid
ReasonScript v0.1 Module after lowering to Reason IR. The type system,
ReasonUnit, RuntimeReal, MemorySpace, DBM, WorldModel simulation, distributed
execution, optimization, and macros are outside this specification.

The terms `MUST`, `MUST NOT`, `SHOULD`, and `MAY` are normative requirements.
A value is immutable when a conforming component cannot change the value
during the lifetime of the execution that owns or references it. A pure
operation has no externally observable effect other than its return value.

The semantic configuration is:

```text
C = <M, IR, P, EP, S, D, T>

M   source Module
IR  validated Reason IR
P   planner policy
EP  immutable ExecutionPlan
S   current committed State
D   ordered StateDelta sequence
T   ordered execution trace
```

Execution evolves only by the commit relation:

```text
<EP, S_i, D, T> --commit(step_i)--> <EP, S_i+1, D + delta_i, T + event_i>
```

Planning and validation do not change committed State.

## 2. OS-01 Goal Semantics

A Goal is an immutable terminal satisfaction condition. It defines success
but is neither a plan step nor a state mutation.

For v0.1 `reach_state`, satisfaction is:

```text
satisfies(S, Goal("reach_state", target)) iff S.state_id = target
```

Other Goal kinds require a deterministic host evaluator identified by the
Goal kind. Missing evaluators cause planning or execution to fail; a Runtime
MUST NOT guess their meaning.

Rules:

1. Each execution has exactly one Goal, inherited from its Module and Reason
   IR.
2. The Goal is copied or referenced read-only at execution start and MUST NOT
   change until the InferenceResult is produced.
3. Goal evaluation MUST be pure and deterministic for the same State and
   evaluation inputs.
4. A zero-step execution is valid when the initial State satisfies the Goal.
5. Multiple independent Goals require separate executions in v0.1. Composite
   goals are a distinct Goal kind with a registered deterministic evaluator.
6. Execution without a Goal is invalid before planning.

## 3. OS-02 State Semantics

State is the complete, owned, serializable snapshot of execution-relevant
information at one commit boundary:

```text
State = <state_id, state_type, data>
```

`state_id` identifies the domain state represented by the snapshot.
Snapshot equality is structural equality of all three fields after canonical
JSON normalization of `data`. Identity equality compares `state_id` only and
MUST NOT be substituted for snapshot equality at a commit boundary.

Rules:

1. State is immutable while observed by planning, constraint evaluation,
   guard evaluation, tracing, or result construction.
2. A Runtime MAY use mutable storage internally, but a new snapshot becomes
   observable only through an atomic commit.
3. Partial mutation of committed State is forbidden.
4. A failed prepare, validation, or commit leaves current State unchanged.
5. Every successful change produces exactly one StateDelta whose
   `before_state` equals the previously committed snapshot and whose
   `after_state` equals the newly committed snapshot.
6. State data MUST be JSON-compatible and serializable.

## 4. OS-03 Transition Semantics

A Transition is a planner-selectable declaration of a possible transformation:

```text
Transition = <id, source, relation, target, cost, guard?, effect?>
```

A Transition `tr` is applicable to State `S` under resolved Context `K` when:

```text
S.state_id = tr.source
and guard(tr, S, K) = true
and all step constraints accept(tr, S, K)
```

Application is a two-stage operation:

```text
prepare(tr, S) -> candidate after-state
validate(candidate, constraints, guard, policy, budget, state-consistency)
commit(candidate) -> StateDelta
```

Rules:

1. Source mismatch makes a Transition inapplicable and MUST NOT mutate State.
2. The candidate after-state identity MUST equal `Transition.target`.
3. More than one applicable Transition is permitted during planning.
4. Selection MUST follow Section 7. Declaration order alone is not a valid
   ambiguity rule.
5. An execution step MUST refer to exactly one Transition by stable ID and
   MUST preserve that Transition's source and target.
6. Reapplying a committed candidate is invalid.

## 5. OS-04 Constraint Semantics

A Constraint is a pure predicate:

```text
evaluate(constraint, state, transition?, context) -> accept | reject(message)
```

Rules:

1. Constraint evaluation MUST NOT mutate State, Context, Metadata, the Goal,
   the plan, or another Constraint.
2. Evaluation inputs MUST be immutable snapshots.
3. A Runtime evaluates planning constraints while constructing candidates,
   step constraints immediately before each commit, and final constraints
   before reporting `completed`.
4. A rejected planning constraint removes the candidate path.
5. A rejected step or final constraint produces a violation and prevents the
   associated commit or successful result.
6. Repeated evaluation with equal inputs MUST return an equal decision and
   message.
7. An unknown Constraint kind or evaluation error is `failed`, not `accept`.
8. Constraints MAY read resolved Context, but MUST NOT resolve or modify it.

## 6. OS-05 Context Semantics

Context is externally owned information addressed by a stable typed reference:

```text
ContextRef = <context_id, context_type, uri?>
ResolvedContext = <context_id, revision, value>
```

Rules:

1. Required Context MUST be resolved before the first planning or evaluation
   operation that reads it.
2. A resolution failure produces `failed` and no StateDelta.
3. A resolved Context value and revision are frozen for one execution.
   External changes become visible only to a later execution.
4. Context resolution and reads MUST NOT silently copy data into State.
5. A Transition MAY explicitly integrate Context-derived data through its
   effect and commit; that integration is then represented in StateDelta.
6. Trace evidence SHOULD identify the Context reference or revision used.

## 7. OS-06 Planning Semantics

Planning is a pure function of validated Reason IR, frozen Context, and planner
policy:

```text
plan(IR, Context, Policy) -> ExecutionPlan | PlanningFailure
```

A valid plan is a finite path from the initial State identity to a
Goal-satisfying identity whose steps:

1. reference declared unique Transition IDs;
2. form a continuous chain (`step[i].target = step[i+1].source`);
3. begin at `initial_state.state_id`;
4. satisfy planning-time guards and constraints;
5. do not exceed `max_depth`, `max_steps`, or other explicit budgets; and
6. have `expected_cost` equal to the sum of selected Transition costs.

The normative `minimum_expected_cost` selection key is:

```text
(total expected cost, number of steps, ordered transition_id sequence)
```

The lexicographically least key is selected. This makes selection independent
of declaration order. Alternative valid paths are ordered by the same key and
limited by `max_alternatives`.

Planning outcomes:

| Condition | Outcome |
|---|---|
| Initial State satisfies Goal | valid empty plan |
| One least selection key | selected plan |
| Equal candidates cannot be distinguished by the policy | `decision_required` |
| No valid path | `failed` |
| Unsupported policy/evaluator, invalid IR, or Context failure | `failed` |
| Search budget exhausted before completeness can be established | `failed` with incomplete-search diagnostic |

Planner completeness is relative to explicit policy bounds. Within those
bounds, a conforming planner MUST find a valid path if one exists. v0.1 does
not claim unbounded completeness.

## 8. OS-07 ExecutionPlan Semantics

An ExecutionPlan is the immutable, ordered executor contract:

```text
ExecutionPlan =
  <selected_steps, alternative_paths, expected_cost,
   evidence_refs, planner_version>
```

Rules:

1. The plan MUST pass all Section 7 validity rules before execution.
2. The selected step order is normative and MUST NOT be changed.
3. A plan MUST NOT be modified after construction.
4. The executor MUST NOT insert, remove, replace, or reorder plan steps.
5. Every step is revalidated against current State immediately before commit.
6. A plan is invalidated by Reason IR version mismatch, planner policy version
   mismatch, changed Goal, changed initial snapshot, changed frozen Context
   revision, missing Transition, source/target mismatch, failed constraint or
   guard, or exhausted execution budget.
7. Plan selection and invalidation MUST be auditable through trace data.

## 9. OS-08 StateDelta Semantics

A StateDelta is the complete committed change record:

```text
StateDelta =
  <delta_id, before_state, after_state, applied_transition, timestamp>
```

Rules:

1. Delta IDs are unique within an execution trace.
2. `before_state` and `after_state` are complete snapshots, not patches.
3. `applied_transition` identifies the committed Transition.
4. For adjacent deltas, `D[i].after_state = D[i+1].before_state`.
5. Applying a sequence is left-to-right and is valid only when every
   `before_state` equals the current snapshot.
6. Rollback never deletes or edits prior deltas. It commits a new reverse
   delta with the current snapshot as `before_state`, the source delta's
   `before_state` as `after_state`, and an `applied_transition` prefixed by
   `rollback:`.
7. Rollback is permitted only when the current State equals the source
   delta's `after_state`, unless a future policy defines a compensating
   transition.
8. Each committed or rollback delta MUST have one matching trace event.

## 10. OS-09 InferenceResult Semantics

InferenceResult is the complete observable outcome:

```text
InferenceResult =
  <status, final_state, state_deltas, proof?,
   violations, alternatives, trace_id>
```

Status meaning:

| Status | Meaning |
|---|---|
| `completed` | Goal and final constraints are satisfied after all selected steps |
| `rejected` | A known Constraint rejected planning, a step, or final acceptance |
| `decision_required` | Valid alternatives remain and policy cannot select one |
| `failed` | Validation, Context, planning, execution, budget, or evaluator failure |

Rules:

1. `final_state` is the last committed State, including after rollback.
2. `state_deltas` is the ordered complete list of committed forward and
   rollback deltas.
3. `trace_id` is mandatory for every status.
4. `completed` requires Goal satisfaction, no unresolved violation, a
   consistent delta chain, and complete delta trace coverage.
5. `rejected` includes at least one Constraint violation.
6. `decision_required` includes auditable alternatives.
7. `failed` preserves all already committed deltas. If rollback policy
   succeeds, the rollback deltas are also included.
8. A proof, when present, identifies selected steps and evidence; it MUST NOT
   claim steps absent from the executed plan.

## 11. OS-10 Runtime Correctness

A conforming Runtime MUST preserve these invariants:

| Invariant | Required property |
|---|---|
| Goal immutability | Goal is unchanged from planning through result |
| State identity stability | Observed snapshots never change in place |
| Constraint purity | Equal inputs yield equal decisions and no mutation |
| Plan immutability | Selected steps and order never change |
| Delta traceability | Every commit has one delta and matching trace event |
| Deterministic execution | Equal frozen inputs and versions yield equal semantic outcomes |
| Commit-only mutation | Prepare and validation cannot change committed State |
| Auditability | Plan, violations, commits, rollbacks, and result share trace identity |

For each selected step `i`, correctness requires:

```text
current.state_id = step[i].source
step[i].transition_id resolves uniquely
transition.target = step[i].target
all validation checks accept
commit produces exactly one delta
delta.before_state = previous current
delta.after_state = new current
```

At termination:

```text
result.final_state = fold(apply, initial_state, result.state_deltas)
trace covers every result.state_delta
result.status = completed implies satisfies(result.final_state, goal)
```

## 12. Failure Atomicity and Determinism Boundary

Prepare, Context read, Goal evaluation, guard evaluation, Constraint
evaluation, and plan validation are non-committing operations. Failure in any
of them leaves State unchanged.

A step commit is atomic. If a Runtime cannot atomically persist State,
StateDelta, transaction record, and trace reference, it MUST expose no part of
that commit as successful.

Determinism is defined for equal:

- Reason IR and initial State;
- Goal and execution/planner policies;
- frozen Context values and revisions;
- evaluator, planner, policy, and Runtime versions; and
- externally supplied timestamps or deterministic timestamp policy.

Wall-clock timing, scheduling, and serialization formatting are not semantic
outputs unless explicitly included in policy.

## 13. Conformance

Reference semantic validation:

```sh
python3 -m unittest discover \
  -s operational_semantics_tests -p 'test_*.py' -v
```

Runtime semantic validation:

```sh
python3 -m unittest discover \
  -s runtime_semantics_validation_tests -p 'test_*.py' -v

cargo test --manifest-path HybridRuntime/Cargo.toml \
  --test operational_semantics_validation
```

The JSON contracts in `schemas/`, the immutable `ExecutionPlan` API,
`StateKernel`, `TransactionKernel`, `Trace`, and `InferenceResult` are the
normative v0.1 implementation surfaces tested by these suites.
