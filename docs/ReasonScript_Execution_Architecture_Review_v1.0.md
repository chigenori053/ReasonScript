# ReasonScript Execution Architecture v1.0 Review

Status: REVIEW COMPLETE

Review version: `execution-architecture-review/0.1`

Architecture version: `reasonscript-execution-architecture/1.0`

Related interfaces:

- `reasonscript-operational-semantics/0.1`
- `reasonscript-language/0.1`
- `reason-ir/0.1`
- `planner/0.1`
- `world-model-sdk/0.4`

## 1. Scope

This review fixes the platform execution model for current and future
ReasonScript development. It does not add language features. It classifies
the existing execution behavior across Language Core, Compiler, Reason IR,
ExecutionPlan, Runtime, Runtime SDK, and World Model SDK as Implemented,
Partially Implemented, Missing, or Rejected.

The normative execution path for v1.0 is:

```text
Source
  -> Parser
  -> AST
  -> Compiler
  -> Reason IR
  -> ExecutionCoordinator
  -> ExecutionPlan
  -> Runtime Invocation
  -> TransactionModel / WorldDelta
  -> ReasoningTrace
  -> InferenceResult / WorldSimulationResult
```

## 2. Review Summary

| Area | Classification | Finding |
|---|---|---|
| ExecutionContext | Partially Implemented | RuntimeReal has graph execution context; operational semantics define frozen context; no single platform context owns bindings, runtime values, snapshots, and temporaries. |
| ExecutionScope | Partially Implemented | Language surface validates function, block, and loop scoping; no runtime ExecutionScope type exists. |
| CallStack | Missing | Functions parse and project, but no CallFrame or CallStack runtime model is implemented. |
| ExecutionCoordinator | Missing | Pipeline stages exist, but no explicit orchestration layer owns plan generation, runtime dispatch, trace identity, and result assembly. |
| TransactionModel | Implemented | HybridRuntime TransactionKernel implements prepare, validate, commit, rollback, transaction records, and trace-linked deltas. WorldDelta is implemented separately for World Model simulation. |
| RuntimeInvocationModel | Partially Implemented | Runtime operation registry and sync dispatch exist for search, simulate, predict, and plan; async and formal capability discovery are not implemented. |
| RuntimeCapabilityRegistry | Partially Implemented | RuntimeEngineRegistry is a static optional registry for current capabilities. Dynamic discovery and versioned capability metadata are missing. |
| Trace Architecture | Partially Implemented | Core Trace schema, RuntimeReal TraceEvent, SimulationTrace, and ReconstructionTrace exist independently. A unified ReasoningTrace adapter contract is missing. |

## 3. ExecutionContext Specification

ExecutionContext is the per-execution state container. It MUST distinguish
language bindings from committed domain state and runtime outputs.

```text
ExecutionContext =
  <execution_id,
   source_module?,
   reason_ir,
   frozen_context_refs,
   root_scope,
   call_stack,
   runtime_values,
   snapshots,
   temporaries,
   transaction_model?,
   trace>
```

Rules:

1. Variables are stored in ExecutionScope bindings, not directly in committed State.
2. Constants are immutable bindings with reassignment rejected before execution.
3. Runtime values use the RuntimeValue family for scalar, structured, Goal,
   State, Constraint, ReasonGraph, and ExecutionPlan values.
4. Snapshots are immutable values. Committed State snapshots belong to the
   TransactionModel; World snapshots belong to World Model SDK results.
5. Temporary values are execution-local and MUST NOT escape their owning scope
   or call frame unless returned or explicitly committed.
6. Frozen external context is resolved before first read and remains stable for
   the execution.

Current evidence:

- `RuntimeReal/src/executor/execution_context.rs` stores active graph nodes,
  history, timestamp, dynamics context, and trace events.
- `RuntimeReal/src/runtime_binding.rs` defines RuntimeValue for language-visible
  runtime values.
- `docs/ReasonScript_Operational_Semantics_v0.1.md` defines frozen Context and
  immutable State boundaries.

Classification by question:

| ID | Classification | Decision |
|---|---|---|
| EC-001 | Partially Implemented | Variables are represented by language-surface bindings, but there is no unified execution binding store. |
| EC-002 | Implemented | Const reassignment is rejected by language-surface validation. |
| EC-003 | Implemented | RuntimeValue covers Goal, State, Constraint, ReasonGraph, and ExecutionPlan. World is represented by World Model SDK types. |
| EC-004 | Partially Implemented | StateSnapshot and World Snapshot exist independently. |
| EC-005 | Missing | Temporary value lifetime is not modeled as an ExecutionContext concept. |

## 4. ExecutionScope Specification

ExecutionScope defines visibility, mutability, and lifetime of language
bindings.

```text
ExecutionScope =
  <scope_id,
   kind: module | function | block | match_arm | loop,
   parent?,
   bindings>

Binding =
  <name, mutability: const | let | parameter | loop_item,
   value?, declared_type?, lifetime>
```

Rules:

1. Function parameters are bound in the function scope before body execution.
2. Function-local `let` and `const` bindings are visible after declaration
   until the function returns.
3. Block, match-arm, and loop scopes are children of the current scope.
4. Block-local bindings do not escape the block.
5. Loop item bindings are scoped to the loop body and immutable for each
   iteration.
6. Shadowing is allowed only when a child scope introduces a binding with the
   same name. Same-scope redeclaration is invalid unless a future language
   version explicitly defines it.
7. A returned value escapes by value, not by binding identity.

Current evidence:

- `language_spec_validation_tests/test_core_language_phase1_bindings.py`
  validates function body bindings, const reassignment rejection, terminal
  return, and block-local non-escape.
- `language_spec_validation_tests/test_core_language_phase3_iteration.py`
  validates loop item immutability and loop item non-escape.

Classification by question:

| ID | Classification | Decision |
|---|---|---|
| ES-001 | Partially Implemented | Function scope is validated at surface level. |
| ES-002 | Partially Implemented | Block non-escape is validated. |
| ES-003 | Missing | Match-arm scope is not formalized in current reviewed runtime surfaces. |
| ES-004 | Partially Implemented | Loop item scope and immutability are validated. |
| ES-005 | Partially Implemented | Child-scope shadowing is accepted as v1.0 architecture, but explicit implementation evidence is incomplete. |
| ES-006 | Partially Implemented | Lifetimes are validated for blocks and loops, not represented as runtime scope records. |

## 5. CallStack Specification

CallStack is required for v1.0 even though it is not currently implemented as a
runtime structure.

```text
CallFrame =
  <frame_id,
   function_name,
   arguments,
   parameter_bindings,
   local_scope,
   return_target?,
   return_value?,
   status: active | returning | completed | failed>

CallStack =
  <frames, max_depth, overflow_policy>
```

Rules:

1. A function call pushes one CallFrame.
2. Parameters are bound positionally by v1.0 surface syntax.
3. Function execution completes only through a terminal return or failure.
4. Nested calls push frames in call order and pop in reverse order.
5. Recursive calls are allowed only within `max_depth`.
6. Stack overflow is a runtime failure. It MUST NOT mutate committed State and
   MUST be traceable.
7. Return values are copied into the caller's temporary value slot or binding
   target.

Classification by question:

| ID | Classification | Decision |
|---|---|---|
| CS-001 | Partially Implemented | Function declarations and call expressions parse/project, but no runtime frame exists. |
| CS-002 | Missing | Parameter binding is validated structurally, not executed through CallFrame. |
| CS-003 | Partially Implemented | Terminal return is validated; runtime return handling is not modeled. |
| CS-004 | Missing | Nested calls have no runtime stack model. |
| CS-005 | Missing | Recursive call semantics are undefined. |
| CS-006 | Missing | Stack overflow behavior is not implemented. |

## 6. ExecutionCoordinator Specification

ExecutionCoordinator is required.

```text
ExecutionCoordinator =
  <request_id,
   validated_source_or_ir,
   planner_policy,
   runtime_registry,
   transaction_model,
   trace_builder,
   result_builder>
```

Responsibilities:

1. Own request and trace identity.
2. Validate or receive validated Reason IR.
3. Resolve and freeze external Context.
4. Own ExecutionPlan construction or selection handoff.
5. Validate ExecutionPlan before runtime dispatch.
6. Dispatch runtime operations through RuntimeInvocationModel.
7. Apply committing operations through TransactionModel.
8. Collect runtime traces, world traces, transaction deltas, diagnostics, and
   violations into a final result.

The coordinator MUST NOT implement domain-specific search, planning,
prediction, simulation, or world physics. It orchestrates existing engines.

Classification by question:

| ID | Classification | Decision |
|---|---|---|
| EX-001 | Missing | ExecutionPlan ownership is split between compiler/integration tests and runtime validation. Coordinator owns it in v1.0. |
| EX-002 | Partially Implemented | RuntimeEngineRegistry dispatches operations; coordinator ownership is missing. |
| EX-003 | Missing | Trace identity is not centrally owned across traces. |
| EX-004 | Missing | Result assembly is distributed across conformance/runtime helpers. |
| EX-005 | Partially Implemented | World Model execution is owned by SDK functions; coordinator integration is missing. |

## 7. TransactionModel Specification

TransactionModel is the consistency boundary for committed symbolic State.

```text
TransactionModel =
  <current_state,
   prepared_candidates,
   committed_deltas,
   transaction_records,
   trace>
```

Rules:

1. Prepare validates transaction ID, plan ID, source state, and proposed target.
2. Validate records accepted or rejected candidate status.
3. Commit is allowed only for accepted candidates whose before state equals
   current state.
4. Rollback commits a new reverse StateDelta; it never deletes or edits prior
   deltas.
5. Every commit and rollback has a TransactionRecord and a trace-linked delta.
6. Failed prepare, validation, commit, or rollback leaves current State
   unchanged.

WorldDelta is not equivalent to Transaction. WorldDelta is a deterministic
World Model change set for simulation. It may be adapted into a transaction
record by a coordinator, but by itself it lacks prepare/validate/commit and
rollback status.

Classification by question:

| ID | Classification | Decision |
|---|---|---|
| TX-001 | Rejected | WorldDelta and Transaction are not equivalent. |
| TX-002 | Implemented | Transactions can fail during prepare, validate, commit, or rollback. |
| TX-003 | Implemented | Rollback is modeled as reverse delta commit. |
| TX-004 | Implemented | StateSnapshot boundaries are complete and immutable. World snapshots are separate SDK values. |
| TX-005 | Implemented | Runtime consistency guarantees are defined in operational semantics and TransactionKernel behavior. |

## 8. RuntimeInvocationModel Specification

Runtime invocation is synchronous in v1.0.

```text
RuntimeInvocation =
  <operation: search | plan | predict | simulate,
   argument: RuntimeValue,
   result: RuntimeResult>
```

Rules:

1. `runtime.search`, `runtime.plan`, `runtime.predict`, and `runtime.simulate`
   are synchronous calls.
2. Each operation dispatches to the registered engine for that capability.
3. Missing engine returns RuntimeResult failure and does not throw as normal
   semantic control flow.
4. RuntimeResult success carries an optional RuntimeValue. Failure carries
   diagnostics.
5. Async execution is reserved for a future architecture version and MUST NOT
   be assumed by v1.0 consumers.

Classification by question:

| ID | Classification | Decision |
|---|---|---|
| RI-001 | Implemented | Runtime operation dispatch is synchronous. |
| RI-002 | Missing | Async support is not implemented. |
| RI-003 | Partially Implemented | Capability presence can be inferred from registry fields; no discovery API exists. |
| RI-004 | Partially Implemented | Static RuntimeEngineRegistry exists. |
| RI-005 | Partially Implemented | RuntimeResult failure diagnostics exist; cross-runtime error taxonomy is incomplete. |

## 9. RuntimeCapabilityRegistry Specification

v1.0 uses a static capability registry.

```text
RuntimeCapabilityRegistry =
  <search_engine?,
   simulation_engine?,
   prediction_engine?,
   planning_engine?,
   versions?>
```

Required capabilities for v1.0 are Search, Plan, Predict, and Simulate.
Reconstruct, Replay, Branch, Learn, and Agent are reserved capabilities. They
MUST NOT be treated as available unless a future registry advertises them.

Rules:

1. Static registry fields define callable capabilities.
2. Missing capability dispatch returns RuntimeResult failure.
3. Version metadata SHOULD be added before dynamic or remote runtime selection.
4. Dynamic capability discovery is not part of v1.0.

Classification by question:

| ID | Classification | Decision |
|---|---|---|
| RC-001 | Partially Implemented | Current registry is static. Dynamic registry is missing. |
| RC-002 | Missing | Capability versioning is not implemented in the registry. |
| RC-003 | Missing | Discovery API is not implemented. |

## 10. Trace Architecture Specification

ReasoningTrace is required as the platform-level trace envelope.

```text
ReasoningTrace =
  <request_id,
   source: core | runtime | world_simulation | reconstruction,
   reason_ir_version?,
   planner_version?,
   policy_version?,
   events,
   evidence_refs,
   child_traces>
```

Rules:

1. Core execution MUST continue to emit schema-valid Trace objects.
2. RuntimeReal TraceEvent, World SimulationTrace, and ReconstructionTrace MAY
   remain independent internal traces.
3. ExecutionCoordinator MUST adapt independent traces into ReasoningTrace when
   producing a platform result.
4. Evidence references MUST preserve source trace identity.
5. Runtime trace integration MUST be append-only and auditable.

Classification by question:

| ID | Classification | Decision |
|---|---|---|
| TR-001 | Partially Implemented | Unified trace is required architecturally; only core Trace schema exists today. |
| TR-002 | Partially Implemented | Evidence refs exist in ExecutionPlan/Trace; reconstruction evidence is independent. |
| TR-003 | Missing | Runtime, simulation, and reconstruction trace integration is not implemented. |

## 11. Success Criteria Status

| Criterion | Status |
|---|---|
| EAR-001 Execution Context reviewed | Complete |
| EAR-002 Execution Scope reviewed | Complete |
| EAR-003 Call Stack reviewed | Complete |
| EAR-004 Execution Coordinator reviewed | Complete |
| EAR-005 Transaction Layer reviewed | Complete |
| EAR-006 Runtime Invocation reviewed | Complete |
| EAR-007 Runtime Capability reviewed | Complete |
| EAR-008 Trace Architecture reviewed | Complete |

## 12. v1.0 Decisions

1. ExecutionCoordinator is required for the stable execution model.
2. TransactionModel and WorldDelta are distinct layers.
3. Runtime invocation is synchronous for v1.0.
4. Runtime capabilities are static for v1.0.
5. CallStack is a required missing architecture component before language
   functions can be considered runtime-executable.
6. ReasoningTrace is the required envelope for cross-runtime trace integration.
7. Existing Operational Semantics v0.1 remains valid and becomes the commit
   and consistency subset of Execution Architecture v1.0.

## 13. Follow-up Implementation Backlog

| Priority | Item | Target |
|---|---|---|
| P0 | Add ExecutionCoordinator module and tests | Runtime SDK |
| P0 | Add CallFrame and CallStack runtime model | Language Core / Runtime |
| P1 | Add ExecutionScope runtime representation | Language Core |
| P1 | Add ReasoningTrace envelope and adapters | Runtime / World SDK |
| P1 | Add capability metadata and discovery API | Runtime SDK |
| P2 | Add async invocation proposal | Future architecture review |
