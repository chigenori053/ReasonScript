# Common DTO Specification v0.1

Status: Draft
ABI: `reason-ir/0.1`
Serialization: UTF-8 JSON

## 1. Purpose

Common DTO is the language-independent transfer layer between the Reason IR
JSON Schema, SDKs, and Runtime. SDK-specific wire shapes are prohibited.

```text
JSON Schema -> Common DTO -> Runtime
```

## 2. Public DTOs

The public, serializable DTO set is:

- `ReasonIR`
- `ExecutionPlan`
- `StateDelta`
- `InferenceResult`
- `Trace`
- `TransactionRecord`

`PreparedDelta` is a Runtime-internal pre-commit object. It is not a public
wire DTO and must not be directly serialized by SDKs.

## 3. Immutability

DTOs are immutable after construction. Runtime collections may contain DTOs,
but consumers must not mutate a DTO in place.

The only lifecycle mutation allowed by this specification is the Runtime-owned
transition of `PreparedDelta.validation_status` and its corresponding
`validation_failures`.

## 4. Serialization

1. JSON field names are the snake_case names defined by the schemas.
2. Enum values are serialized as snake_case strings.
3. Timestamps are unsigned 64-bit integer values.
4. Arbitrary JSON in `StateSnapshot.data`, `TransitionSpec.effect`, and
   `ReasonIR.metadata` is preserved during round-trip.
5. Unknown keys inside `metadata` are preserved.
6. Runtime objects, pointers, callbacks, and implementation class names are
   forbidden in public DTO JSON.

## 5. DTO Shapes

### ReasonIR

`ReasonIR` and its component types are defined by
`schemas/reason_ir.schema.json`. `schema_version` is required and fixed to
`reason-ir/0.1`.

### ExecutionPlan

```text
selected_steps      PlanStep[]
alternative_paths   PlanPath[]
expected_cost       finite number >= 0
evidence_refs       string[]
planner_version     non-empty string
```

### StateDelta

```text
delta_id              string
before_state          StateSnapshot
after_state           StateSnapshot
applied_transition    string
timestamp             uint64
```

Every `StateDelta` in an `InferenceResult` must have a matching
`state_delta_applied` event in its `Trace`.

### InferenceResult

```text
status          completed | rejected | decision_required | failed
final_state     StateSnapshot
state_deltas    StateDelta[]
proof           Proof | null
violations      Violation[]
alternatives    PlanPath[]
trace_id        string
```

### Trace

```text
request_id          string
reason_ir_version   reason-ir/0.1
planner_version     string | null
policy_version      string
events              TraceEvent[]
```

Trace events are tagged by `event_type`.

### TransactionRecord

```text
transaction_id        string
execution_plan_id     string
candidate_id          string
delta_id              string | null
status                prepared | accepted | rejected | committed | rolled_back
commit_timestamp      uint64 | null
validation_failures   string[]
source_delta_id       string | null
```

## 6. Language Bindings

The generated/binding targets are:

```text
dto/rust
dto/python
dto/typescript
dto/go
dto/java
```

All bindings use the same JSON field names and consume the shared fixtures in
`fixtures/valid` and `fixtures/invalid`.

## 7. Compliance Levels

- Level 1: `ReasonIR`
- Level 2: Level 1 plus `InferenceResult`
- Level 3: Level 2 plus `ExecutionPlan`, `StateDelta`, and `Trace`
- Level 4: Level 3 plus `TransactionRecord`

## 8. Conformance

A conforming binding must pass:

- valid ReasonIR fixture deserialization
- invalid ReasonIR fixture rejection
- DTO to JSON serialization
- JSON to DTO deserialization
- DTO round-trip equality
- unknown metadata preservation
- 64-bit timestamp preservation
- ReasonIR version validation

Reference schemas are stored in `schemas/`. Reference conformance tests are
stored in `conformance/` and `HybridRuntime/tests/`.
