# ReasonScript ABI Specification v0.1

Status: VALIDATED  
ABI identifier: `reason-ir/0.1`  
Serialization: UTF-8 JSON

## 1. Scope

本仕様はReasonScript Language、SDK、Runtime間で交換するPlatform ABIを定義する。

規範型:

```text
ReasonIR
ExecutionPlan
StateDelta
InferenceResult
Trace
```

Compiler、Parser、transport、storage、distributed protocolは対象外とする。

## 2. Compatibility Rules

1. Producerは`ReasonIR.schema_version`へ`reason-ir/0.1`を設定する。
2. Consumerは未知の明示versionを拒否する。
3. Consumerは未知のmetadata keyを無視し、round-trip可能なら保持する。
4. Optional field欠落時は本仕様のdefaultを使用する。
5. Required field欠落または型不一致はvalidation errorとする。
6. IDはdocument内で一意なUTF-8 stringとする。
7. wire contractへRuntime class名、pointer、callbackを含めない。
8. JSON object field順序に意味を持たせない。

## 3. ReasonIR

```text
ReasonIR
├─ schema_version       string                 required
├─ initial_state        StateSnapshot          required
├─ goal                 GoalSpec               required
├─ context_refs         ContextRef[]           optional, default []
├─ constraints          ConstraintSpec[]       optional, default []
├─ transitions          TransitionSpec[]       required
├─ planner_policy       PlannerPolicy | null   optional
├─ execution_policy     ExecutionPolicy        required
├─ trace_policy         TracePolicy            required
└─ metadata             object                 optional, default {}
```

### StateSnapshot

```text
state_id     string   required
state_type   string   required
data         JSON     required
```

`data`はdomain payloadであり、Runtime内部objectをserializeしたものではない。

### GoalSpec

```text
kind       string   required
target     string   required
```

### ContextRef

```text
context_id     string          required
context_type   string          required
uri            string | null   optional
```

Context本体ではなく、MemorySpace、Prompt、Document、Tool Resultなどへの
参照を格納する。

### ConstraintSpec

```text
constraint_id   string   required
kind            string   required
expression      string   required
```

### TransitionSpec

```text
transition_id   string          required
source          string          required
relation        string          required
target          string          required
expected_cost   number          required, finite and >= 0
guard           string | null   optional
effect          JSON | null     optional
```

`transition_id`はReasonIR内で一意でなければならない。

### PlannerPolicy

```text
strategy           string          required
max_depth          integer | null  optional
max_alternatives   integer | null  optional
```

default:

```json
{
  "strategy": "minimum_expected_cost",
  "max_depth": 128,
  "max_alternatives": 8
}
```

Plannerを必要としないrequestではfield全体を省略できる。

### ExecutionPolicy

```text
max_steps             integer   required, > 0
rollback_on_failure   boolean   required
constraint_mode       string    required
```

default:

```json
{
  "max_steps": 128,
  "rollback_on_failure": true,
  "constraint_mode": "reject"
}
```

### TracePolicy

```text
level                  string    required
include_alternatives   boolean   required
include_state_data     boolean   required
```

default:

```json
{
  "level": "standard",
  "include_alternatives": true,
  "include_state_data": true
}
```

## 4. ExecutionPlan

```text
ExecutionPlan
├─ selected_steps      PlanStep[]
├─ alternative_paths   PlanPath[]
├─ expected_cost       number
├─ evidence_refs       string[]
└─ planner_version     string
```

ExecutionPlanは生成後immutableとする。
State KernelはPlanを変更せず、各selected stepを検証して適用する。

### PlanStep

```text
step_id         string
transition_id   string
source          string
target          string
```

### PlanPath

```text
step_ids        string[]
expected_cost   number
```

## 5. StateDelta

```text
StateDelta
├─ delta_id              string
├─ before_state          StateSnapshot
├─ after_state           StateSnapshot
├─ applied_transition    string
└─ timestamp             unsigned integer
```

規則:

1. StateDeltaはState Kernelだけが生成する。
2. `before_state`はcommit直前のcurrent stateと一致しなければならない。
3. `after_state.state_id`はTransition targetと一致しなければならない。
4. rollbackはbefore / afterを反転した新しいDeltaとして記録する。
5. Deltaの上書きまたは再利用を禁止する。
6. 全Deltaに対応するTrace eventが必要である。

## 6. InferenceResult

```text
InferenceResult
├─ status          InferenceStatus
├─ final_state     StateSnapshot
├─ state_deltas    StateDelta[]
├─ proof           Proof | null
├─ violations      Violation[]
├─ alternatives    PlanPath[]
└─ trace_id        string
```

InferenceStatus:

```text
completed
rejected
decision_required
failed
```

Proof:

```text
selected_step_ids   string[]
evidence_refs       string[]
```

Violation:

```text
constraint_id   string
message         string
```

## 7. Trace

```text
Trace
├─ request_id          string
├─ reason_ir_version   string
├─ planner_version     string | null
├─ policy_version      string
└─ events              TraceEvent[]
```

TraceEventは`event_type`によるtagged objectとする。

v0.1 event:

```text
plan_selected
state_delta_applied
constraint_violation
evidence_observed
tool_invoked
```

`state_delta_applied`:

```text
event_type       "state_delta_applied"
delta_id         string
transition_id    string
```

全`InferenceResult.state_deltas`について同じ`delta_id`のeventが
Traceに一つ以上存在しなければならない。

## 8. Minimal Example

```json
{
  "schema_version": "reason-ir/0.1",
  "initial_state": {
    "state_id": "Dog",
    "state_type": "symbolic",
    "data": {
      "identity": "Dog"
    }
  },
  "goal": {
    "kind": "reach_state",
    "target": "Animal"
  },
  "transitions": [
    {
      "transition_id": "t1",
      "source": "Dog",
      "relation": "IsA",
      "target": "Mammal",
      "expected_cost": 0.0,
      "guard": null,
      "effect": null
    },
    {
      "transition_id": "t2",
      "source": "Mammal",
      "relation": "IsA",
      "target": "Animal",
      "expected_cost": 0.0,
      "guard": null,
      "effect": null
    }
  ],
  "execution_policy": {
    "max_steps": 128,
    "rollback_on_failure": true,
    "constraint_mode": "reject"
  },
  "trace_policy": {
    "level": "standard",
    "include_alternatives": true,
    "include_state_data": true
  }
}
```

## 9. Version Migration

v0.1 consumerはunversioned Minimal IRをmigrationできる。

Legacy shape:

```text
initial_state
transitions
goal
```

Migration:

```text
schema_version = reason-ir/0.1
context_refs = []
constraints = []
planner_policy = null
execution_policy = v0.1 default
trace_policy = v0.1 default
metadata.migrated_from = minimal-ir/unversioned
```

未知の明示versionは自動migrationしない。

## 10. Multi-Language Requirements

各SDKは次を満たす。

1. JSON field名を本仕様と一致させる。
2. enum wire valueをsnake_caseで出力する。
3. 64-bit timestampをlossなく扱う。
4. arbitrary JSON metadataとstate dataを保持する。
5. unknown metadata keyを削除しない。
6. Runtime logic、Planner、State commitをSDKへ複製しない。
7. canonical conformance fixturesでround-tripを検証する。

対象:

```text
Rust
Python
TypeScript
Go
Java
```

## 11. Security and Validation

Consumerは実行前に次を検証する。

- document size
- transition count
- max steps
- finite non-negative cost
- unique IDs
- external URI scheme
- effect payload size
- unsupported version

`metadata`、`data`、`effect`を実行コードとして解釈してはならない。

## 12. Conformance

v0.1 implementationは次に成功しなければならない。

- ReasonIR JSON round-trip
- ExecutionPlan JSON round-trip
- StateDelta JSON round-trip
- InferenceResult JSON round-trip
- Trace JSON round-trip
- Minimal IR migration
- unknown version rejection
- StateDelta / Trace correspondence
- six Phase 2 validation cases

Reference implementation:

```text
HybridRuntime/src/reason_ir.rs
```

Reference tests:

```text
HybridRuntime/tests/runtime_api_phase_2_reason_ir_validation.rs
```

## 13. Transaction ABI Extension

Phase 3 Transaction Modelは`reason-ir/0.1`を変更せず、次のadditive objectを定義する。

```text
PreparedDelta
TransactionRecord
ValidationStatus
TransactionStatus
ValidationChecks
```

`PreparedDelta`はcommit前のruntime transaction objectであり、ReasonIR producerが
直接StateDeltaを生成するための型ではない。`StateDelta`のwire schemaは変更しない。

`state_delta_applied` TraceEventへ次のoptional fieldを追加する。

```text
transaction_id   string | null   optional
```

field欠落はPhase 2 producerとの互換性のため`null`として扱う。
TransactionKernelによるcommitでは必ずtransaction IDを設定する。

TransactionRecord wire shape:

```text
transaction_id        string
execution_plan_id     string
candidate_id          string
delta_id              string | null
status                prepared | accepted | rejected | committed | rolled_back
commit_timestamp      unsigned integer | null
validation_failures   string[]
source_delta_id       string | null
```

Transaction objectの保存方式、transport、distributed coordinationはABI v0.1の対象外とする。

Reference implementation:

```text
HybridRuntime/src/transaction.rs
```

Reference tests:

```text
HybridRuntime/tests/runtime_api_phase_3_transaction_validation.rs
```
