# ReasonScript Runtime API Validation Phase 2 Report

Version: 0.1  
Validation date: 2026-06-12  
Target: Reason IR Platform ABI  
Status: COMPLETE

## 1. Executive Summary

Minimal IR、Operational IR、Platform IRを、9評価軸、5 Core Schema、
6 Validation Case、8 IR Invariant、ABI round-tripとversion migrationで比較した。

総合順位:

| Rank | Schema Model | Score | Decision |
|---:|---|---:|---|
| 1 | Model-C: Platform IR | 43 / 45 | Platform ABIとして採用 |
| 2 | Model-B: Operational IR | 35 / 45 | Platform IRのruntime subsetとして利用可能 |
| 3 | Model-A: Minimal IR | 23 / 45 | 入力helperまたはlegacy migration sourceに限定 |

ReasonScript Platform ABIにはModel-Cを採用する。

```text
ReasonScript / Goal API / Pipeline API / SDK
                      |
                      v
              Reason IR v0.1
                      |
                      v
             Execution Coordinator
                      |
            +---------+---------+
            |                   |
      Graph Planner       State Kernel
            |                   |
            +---------+---------+
                      |
                      v
       InferenceResult + Trace + StateDelta
```

Reason IRはRust Runtimeの内部構造ではなく、JSONで交換可能な
versioned Platform ABIとする。

## 2. Deliverables

実装:

```text
HybridRuntime/src/reason_ir.rs
```

検証:

```text
HybridRuntime/tests/runtime_api_phase_2_reason_ir_validation.rs
```

仕様:

```text
docs/ReasonScript_ABI_Specification_v0.1.md
```

本レポートは次を統合する。

- Reason IR Validation Report
- Schema Comparison Report
- IR Ranking
- Reason IR Recommendation

## 3. Candidate Comparison

### Model-A: Minimal IR

```text
initial_state
transitions
goal
```

利点:

- 最小実装で生成できる。
- 単純なdeterministic inferenceには十分である。

制約:

- version識別がない。
- context、constraint、policy、trace要求を伝達できない。
- MemorySpace、DBM、Tool integrationでは外部暗黙状態が必要になる。
- backward compatibilityを判定できない。

Decision: legacy入力としてv0.1へmigrationする。

### Model-B: Operational IR

```text
initial_state
goal
context
constraints
transitions
execution_policy
trace_policy
```

利点:

- Runtime executionに必要な主要情報を表現できる。
- Constraint、Context、Traceを明示できる。

制約:

- schema versionとmigration起点がない。
- Planner policyとmetadataがなく、DBM planningやproducer情報が弱い。
- contextを埋込み値に固定するとMemorySpaceとの境界が不明瞭になる。

Decision: Platform IRの一部として包含する。

### Model-C: Platform IR

```text
schema_version
initial_state
goal
context_refs
constraints
transitions
planner_policy
execution_policy
trace_policy
metadata
```

利点:

- 言語、SDK、Runtimeから独立したJSON contractになる。
- version判定、migration、policy、external context参照を保持できる。
- Graph PlannerとState Kernelの両方へprojectionできる。
- MemorySpace、DBM、WorldModel、LLM Tool Useを同じ構造で表現できる。

制約:

- validationとversion policyが必須になる。
- schemaを無制限に拡張すると相互運用性を失う。

Decision: Reason IR v0.1として採用する。

## 4. Core Schema Results

### S1: ReasonIR

実装field:

```text
schema_version       required
initial_state        required
goal                 required
context_refs         optional
constraints          optional
transitions          required
planner_policy       optional
execution_policy     required
trace_policy         required
metadata             optional
```

検証:

- required field presence: PASS
- optional field omission: PASS
- `reason-ir/0.1` round-trip: PASS
- unknown version rejection: PASS
- unversioned Minimal IR migration: PASS
- duplicate transition ID rejection: PASS
- invalid cost rejection: PASS

### S2: ExecutionPlan

実装field:

```text
selected_steps
alternative_paths
expected_cost
evidence_refs
planner_version
```

fieldはprivateとし、constructorとread-only getterだけを公開した。
生成後にstepやcostを変更するAPIは提供しない。

検証:

- serialization / deserialization: PASS
- planner version保持: PASS
- alternatives保持: PASS
- evidence reference保持: PASS
- invalid expected cost拒否: PASS

### S3: StateDelta

実装field:

```text
delta_id
before_state
after_state
applied_transition
timestamp
```

`StateDelta`の直接constructorは公開せず、`StateKernel::apply`から生成する。

検証:

- State Kernel apply: PASS
- source state mismatch拒否: PASS
- target state mismatch拒否: PASS
- rollback delta生成: PASS
- state restoration: PASS
- JSON round-trip: PASS

### S4: InferenceResult

実装field:

```text
status
final_state
state_deltas
proof
violations
alternatives
trace_id
```

検証:

- API共通result形状: PASS
- proof / alternatives保持: PASS
- violation保持: PASS
- SDK中立JSON round-trip: PASS

### S5: Trace

実装field:

```text
request_id
reason_ir_version
planner_version
policy_version
events
```

event type:

```text
plan_selected
state_delta_applied
constraint_violation
evidence_observed
tool_invoked
```

検証:

- 全StateDeltaに対応eventがある場合: PASS
- StateDelta event欠落検出: PASS
- planner / policy / IR version保持: PASS
- JSON round-trip: PASS

## 5. Validation Cases

### Case-1: Basic Inference

```text
Dog -> Mammal -> Animal
```

結果:

```text
selected steps = 2
state deltas = 2
final state = Animal
trace delta events = 2
```

Result: PASS

### Case-2: Constraint Validation

```text
Hypothesis -> ConstraintCheck -> Reject
```

`ConstraintSpec`、`InferenceStatus::Rejected`、`Violation`、
`constraint_violation` trace eventを保持した。

Result: PASS

### Case-3: MemorySpace Query

```text
Query -> Retrieve -> MemoryResult -> Integrate -> Output
```

MemorySpaceをIRへ埋め込まず、次の参照として保持した。

```text
context_id = memory-taxonomy
context_type = memory_space
uri = memory://shm/taxonomy
```

ExecutionPlanの`evidence_refs`へcontext IDを引き継いだ。

Result: PASS at schema level

### Case-4: DBM Planning

```text
Goal -> Hypothesis -> Validation -> Selection -> Output
```

4 transitionをExecutionPlanとStateDelta列に変換し、
planner policyとdomain metadataを保持した。

Result: PASS

### Case-5: WorldModel Simulation

```text
StateA --Action--> StateB
```

Transition effectへposition changeを格納し、
StateDeltaでbefore / after stateを保持した。

Result: PASS at schema level

### Case-6: Tool Integration

```text
Goal -> ToolCall -> ToolResult -> Integrate -> UpdatedState
```

Transition effectへtool referenceを格納し、
Traceへ`tool_invoked` eventとresult referenceを記録した。

Result: PASS at schema level

## 6. IR Invariants

| Invariant | Enforcement | Result |
|---|---|---|
| 1. 言語非依存 | JSON値と文字列IDだけをwire contractに使用 | PASS |
| 2. SDK非依存 | SDK class名やcallbackをschemaに含めない | PASS |
| 3. Runtime内部構造を非公開 | GraphRuntime、StateManager等をJSONに含めない | PASS |
| 4. ExecutionPlan immutable | private field + read-only getter | PASS |
| 5. State変更はState Kernelのみ | StateDelta constructor非公開、Kernel applyで生成 | PASS |
| 6. 全StateDeltaにTrace Event | `Trace::validate_deltas`で検証 | PASS |
| 7. Constraint Failure記録 | Violation + constraint event | PASS |
| 8. Version管理可能 | version dispatch、migration、unknown拒否 | PASS |

## 7. ABI Validation

### Serialization

ReasonIR、ExecutionPlan、StateDelta、InferenceResult、Traceについて
serde JSON round-tripを実行した。

Result: PASS

### Deserialization

required fieldと型をserdeで検証し、意味制約を`ReasonIR::validate`で検証した。

Result: PASS

### Version Migration

対象:

```text
Minimal IR (unversioned) -> reason-ir/0.1
```

migration時に次を補完する。

- schema version
- default execution policy
- default trace policy
- empty context / constraints / metadata
- `metadata.migrated_from`

Result: PASS

### Backward Compatibility

v0.1 readerは次を受理する。

- exact `reason-ir/0.1`
- unversioned Minimal IR
- unknown optional metadata

v0.1 readerは未知の明示versionを推測せず拒否する。

Result: PASS

### SDK Compatibility

Rust以外の実SDK生成は本Phase対象外である。
ただしwire contractは次のみで構成される。

- object
- array
- string
- number
- boolean
- null

Rust固有UUID、enum layout、trait object、closure、pointerを含まないため、
Python、TypeScript、Go、Javaで表現可能と評価した。

Result: PASS at schema level

## 8. Quantitative Evaluation

全項目は5が最良である。

| Criterion | A: Minimal | B: Operational | C: Platform |
|---|---:|---:|---:|
| E1 Schema Simplicity | 5 | 4 | 3 |
| E2 Extensibility | 2 | 4 | 5 |
| E3 MemorySpace Compatibility | 2 | 4 | 5 |
| E4 DBM Compatibility | 2 | 4 | 5 |
| E5 WorldModel Compatibility | 3 | 4 | 5 |
| E6 LLM Compatibility | 2 | 4 | 5 |
| E7 SDK Compatibility | 4 | 4 | 5 |
| E8 Version Compatibility | 1 | 3 | 5 |
| E9 Traceability | 2 | 4 | 5 |
| **Total** | **23** | **35** | **43** |

## 9. IR Ranking

### Rank 1: Platform IR

Platform ABIに必要なversion、external reference、policy、metadataを持ち、
全validation caseを一つのcontractで表現できる。

複雑性を抑えるため、context data本体ではなく`context_refs`を使用し、
planner policyをoptionalとした。

### Rank 2: Operational IR

単一Runtime内のexecution requestには十分である。
ただしPlatform全体の長期互換性とproducer間交換にはversionとmetadataが不足する。

### Rank 3: Minimal IR

単純推論とmigration sourceには有効である。
標準ABIにすると暗黙のcontext、policy、trace contractが増えるため不採用とする。

## 10. Reason IR Recommendation

ReasonScript Platform ABI v0.1を次の構成で確定する。

```text
Input ABI:
  ReasonIR

Planning ABI:
  ExecutionPlan

Mutation ABI:
  StateDelta

Output ABI:
  InferenceResult

Audit ABI:
  Trace
```

`GraphIR`は廃止しない。
GraphIRはReason IRから生成されるplanner projectionとして位置付ける。

```text
Reason IR
  ├─> Graph IR / ExecutionPlan
  └─> State Transition Kernel
```

## 11. Compatibility Conclusions

### MemorySpace

`ContextRef`と`EvidenceRef`により、memory本体をABIへ複製せず参照できる。
actual retrieval、consistency、persistenceは未検証である。

### DBM

Goal、transition stages、planner policy、constraints、alternatives、
proofを保持できる。

### WorldModel

StateSnapshot、Transition effect、StateDeltaにより、
environment stateのbefore / afterを表現できる。
simulation engine自体は未検証である。

### LLM Runtime

Tool callをTransition effect、tool resultをEvidence reference、
contextをContextRef、guardrailをConstraintとして表現できる。
LLM provider実行は未検証である。

## 12. Test Results

Phase 2:

```text
15 passed
0 failed
```

Test coverage:

- S1-S5 Core Schema
- 6 Validation Cases
- 8 IR Invariants
- serialization / deserialization
- migration
- backward compatibility
- invalid version / invalid field rejection

Full regression:

| Scope | Passed | Failed |
|---|---:|---:|
| Existing HybridRuntime suites | 83 | 0 |
| Phase 1 Execution Model | 9 | 0 |
| Phase 2 Reason IR | 15 | 0 |
| **Total** | **107** | **0** |

Quality checks:

```text
cargo clippy --offline --all-targets -- -D warnings
cargo fmt -- --check
```

両方ともPASSした。

## 13. Success Criteria

| Criterion | Result |
|---|---|
| Reason IR候補比較完了 | PASS |
| Schema定量評価完了 | PASS |
| 推奨Schema決定 | PASS: Platform IR |
| Platform ABI確立 | PASS: reason-ir/0.1 |
| MemorySpace適合確認 | PASS at schema level |
| DBM適合確認 | PASS |
| WorldModel適合確認 | PASS at schema level |
| LLM Runtime適合確認 | PASS at schema level |

## 14. Final Decision

ReasonScript Platformの共通契約を次とする。

```text
ReasonScript / Multi-Language SDK
              |
              v
       Reason IR v0.1
              |
              v
      Execution Coordinator
              |
              v
     State Transition Kernel
```

採用Schema:

```text
Model-C: Platform IR
```

ABI version:

```text
reason-ir/0.1
```

次Phaseでは、StateDeltaのprepare、validate、commit、rollback、
consistency、Trace synchronizationを検証する。
