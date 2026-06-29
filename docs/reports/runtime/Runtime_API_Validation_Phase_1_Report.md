# ReasonScript Runtime API Validation Phase 1 Report

Version: 0.1  
Validation date: 2026-06-12  
Target: ReasonScript Runtime Execution Model  
Status: COMPLETE

## 1. Executive Summary

Graph Runtime、State Space Runtime、Hybrid Runtimeを、共通Execution Contract、
8評価軸、6共通ケース、追加の分岐ケースで比較した。

総合順位:

| Rank | Execution Model | Score | Decision |
|---:|---|---:|---|
| 1 | Model-C: Layered Hybrid Runtime | 36 / 40 | ReasonScript Runtime v0.1に推奨 |
| 2 | Model-A: Graph Runtime | 33 / 40 | Planner / explanation engineとして採用 |
| 2 | Model-B: State Space Runtime | 33 / 40 | canonical transition kernelとして採用 |

ReasonScript Runtime v0.1の実行アーキテクチャには、
`Layered Hybrid Runtime`を採用する。

ただし、Graph RuntimeとState Space Runtimeを対等な二重Runtimeとして
常時実行する構造は採用しない。

```text
Pipeline API
    |
    v
Reason IR
    |
    v
Execution Coordinator
    |
    +-- Graph Planner          optional
    +-- Constraint Evaluator
    +-- Memory Adapter
    |
    v
State Transition Kernel       single state authority
    |
    v
InferenceResult + Trace
```

基本原則:

```text
State Space = 実行の意味論
Graph       = 探索、計画、説明、索引
Hybrid      = Graphが生成したPlanをState Kernelがcommitする構造
```

これにより、Graphの説明可能性と非局所探索能力を維持しながら、
MemorySpace、WorldModel、DBMの状態更新を一つのKernelへ集約できる。

## 2. Validation Scope

本Phaseで検証したもの:

- 3 Execution Modelの表現能力
- 共通Input / Output / Trace契約
- 6共通ケース
- 非局所分岐計画
- 128-step長期推論chain
- 既存ReasonGraph、HybridReasonUnit、Graph IRとの整合性
- Runtime v0.1の責務分離

本Phaseで検証していないもの:

- 実MemorySpaceとのI/O
- WorldModel environment実装
- DBM adapter実装
- LLM provider / Tool Runtime統合
- 大規模データでのbenchmark
- 分散実行
- Complex-valued Runtime統合

## 3. Evidence Classification

| Class | Meaning |
|---|---|
| V | 現行Runtime実装と既存testで検証済み |
| P | Phase 1の制御されたprototypeで検証 |
| A | 未実装システムに対するarchitecture assessment |

現行実装の確認結果:

| Capability | Evidence |
|---|---|
| ReasonGraph構築とPath探索 | V |
| Graph transition / multi-hop reasoning | V |
| Graph conflictとPath decision | V |
| Graph Trace | V |
| StateManagerによる状態保持 | V |
| TransitionEngineによる状態更新 | V |
| 複数遷移、分岐、合流 | V |
| Graph IR serialization / reconstruction | V |
| Real-valued Runtime | V、別Runtimeとして存在 |
| Complex-valued Runtime | 最小ReasonUnitのみ |
| MemorySpace | 未実装 |
| WorldModel | 未実装 |
| DBM adapter | 未実装 |

MemorySpace、DBM、WorldModel、LLMのscoreは性能実証値ではなく、
責務、状態所有、データフロー、IR適合性に基づく評価である。

## 4. Common Execution Contract

Phase 1 prototypeでは、全Modelに同じ宣言的transition IRを入力した。

### Input

```text
ExecutionRequest
├─ reason_unit
├─ context
├─ constraints
├─ goal
└─ transitions
```

各Transitionは次を持つ。

```text
source
relation
target
cost
evidence
guard
```

### Output

```text
InferenceResult
├─ final_state
├─ accepted
└─ trace
```

### Trace

```text
ExecutionTrace
├─ model
├─ path
├─ evidence
├─ violations
├─ explored_transitions
└─ state_updates
```

この契約により、Execution Modelを変更してもSDKへ返す
`InferenceResult`の基本形を維持できることを確認した。

## 5. Prototype Execution Semantics

検証コード:

```text
HybridRuntime/tests/runtime_api_phase_1_execution_model_validation.rs
```

### Model-A: Graph Runtime

```text
Reason IR
  -> Graph materialization
  -> enabled path enumeration
  -> minimum-cost path selection
  -> result projection
```

Graph prototypeはPathとEvidenceを生成する。
外部状態の更新は行わず、`state_updates = 0`とした。

### Model-B: State Space Runtime

```text
Reason IR
  -> current state
  -> enabled transition selection
  -> state update
  -> repeat until goal or dead end
```

State Space prototypeはcurrent stateを唯一の実行状態として更新する。
Graph全体のPath planningは行わない。

### Model-C: Hybrid Runtime

```text
Reason IR
  -> Graph path planning
  -> selected transition plan
  -> sequential state update
  -> result and provenance
```

Hybrid prototypeはGraphでPlanを生成し、Plan上の各Transitionを
State Spaceへcommitする。

## 6. Validation Results

### Case-1: ReasonGraph Inference

```text
Dog -> Mammal -> Animal
```

| Model | Result | Assessment |
|---|---|---|
| Graph | PASS | Path探索と説明が直接的 |
| State Space | PASS | 線形遷移として実行可能 |
| Hybrid | PASS | Path選択後に2 state updates |

Graphはこのケースの自然な表現である。
State Spaceでも実行可能だが、taxonomy queryの索引機能は別途必要になる。

### Case-2: Constraint Validation

```text
Hypothesis
  -> ConstraintCheck
  -> Reject
```

入力contextとconstraintの両方に`DogCanFly`を設定した。

全Modelで次を確認した。

```text
final_state = Reject
accepted = false
violations = ["constraint violated: DogCanFly"]
```

ConstraintはGraph NodeまたはStateそのものへ埋め込まず、
Execution Coordinatorの共通Evaluatorとして扱うべきである。

### Case-3: MemorySpace Query

```text
Query
  -> MemoryRetrieval
  -> Integration
  -> Output
```

全Modelが共通契約上の処理chainを実行できた。

ただし実MemorySpaceは未実装であり、次は未検証である。

- SHM / CHM / DHMの一貫性
- retrieval latency
- concurrent update
- persistence
- memory identity resolution

Architecture上は、retrieval結果をStateへ統合し、Graphを索引または
provenanceとして使用するHybridが最も適合する。

### Case-4: DBM Planning

```text
Goal
  -> HypothesisGeneration
  -> Validation
  -> Selection
  -> Output
```

全Modelが線形DBM flowを実行した。

追加分岐ケースでは次を設定した。

```text
Goal --cost 0--> DeadEnd
Goal --cost 1--> Hypothesis -> Output
```

結果:

| Model | Final State | Result |
|---|---|---|
| Graph | Output | PASS |
| State Space | DeadEnd | Planning不足を検出 |
| Hybrid | Output | PASS |

純State Spaceの局所transition選択だけでは、非局所Goalへの到達性を
保証できない。DBM PlanningにはGraph searchまたは同等のPlannerが必要である。

### Case-5: WorldModel Simulation

```text
StateA --Transition--> StateB
```

全ModelでPathを生成できた。

状態更新数:

| Model | State Updates |
|---|---:|
| Graph | 0 |
| State Space | 1 |
| Hybrid | 1 |

GraphだけではPathは説明できるが、Environment stateのcommit主体が存在しない。
WorldModelではState Transition Kernelをcanonical authorityとする必要がある。

### Case-6: Long Reasoning Chain

```text
State0 -> State1 -> ... -> State128
```

全Modelで次を確認した。

```text
final_state = State128
path length = 129
evidence count = 128
```

これは機能上のchain execution確認であり、scalability benchmarkではない。
現行Graph Runtimeの`all_paths`は単純Path列挙であるため、
branching factorが高い大規模Graphでは探索量が急増する。

## 7. Test Summary

Phase 1 test:

| ID | Validation | Result |
|---|---|---|
| REM-01 | ReasonGraph inference common contract | PASS |
| REM-02 | Constraint validation common contract | PASS |
| REM-03 | MemorySpace flow common contract | PASS |
| REM-04 | DBM planning common contract | PASS |
| REM-05 | WorldModel transition common contract | PASS |
| REM-06 | 128-step reasoning chain | PASS |
| REM-07 | Model semantics separation | PASS |
| REM-08 | Common result shape | PASS |
| REM-09 | Nonlocal branch planning | PASS |

```text
9 passed
0 failed
```

Full regression:

```text
cargo test --offline
```

| Scope | Passed | Failed |
|---|---:|---:|
| Existing HybridRuntime suites | 83 | 0 |
| Phase 1 execution model suite | 9 | 0 |
| **Total** | **92** | **0** |

Quality checks:

```text
cargo clippy --offline --all-targets -- -D warnings
cargo fmt -- --check
```

両方ともPASSした。

## 8. Evaluation Scores

全scoreは5が最良である。

E1は`5 = Runtime実装負荷が低い`として評価した。

| Criterion | A: Graph | B: State Space | C: Hybrid |
|---|---:|---:|---:|
| E1 Runtime Simplicity | 5 | 4 | 2 |
| E2 Explainability | 5 | 3 | 5 |
| E3 MemorySpace Compatibility | 4 | 5 | 5 |
| E4 DBM Compatibility | 4 | 4 | 5 |
| E5 WorldModel Compatibility | 3 | 5 | 5 |
| E6 LLM Compatibility | 4 | 4 | 5 |
| E7 Scalability | 3 | 4 | 4 |
| E8 Reason IR Compatibility | 5 | 4 | 5 |
| **Total** | **33** | **33** | **36** |

### E1 Runtime Simplicity

Graphは現行資産を再利用でき、最も実装可能性が高い。
State Spaceも小さなtransition kernelとして実装しやすい。
Hybridはplanner、state commit、整合性保証が必要なため最も複雑である。

### E2 Explainability

GraphとHybridはselected path、alternatives、cost、evidenceを自然に保持できる。
State Spaceはhistoryを記録できるが、未選択経路や非局所判断の説明が弱い。

### E3 MemorySpace Compatibility

Memory retrievalとintegrationは状態更新として扱うのが自然である。
Graphはmemory relation indexとprovenanceに適する。
両者を役割分離するHybridが最も適合する。

### E4 DBM Compatibility

DBMはGoal探索と状態更新の両方を必要とする。
追加分岐ケースにより、純State SpaceにはPlannerが必要であることを確認した。

### E5 WorldModel Compatibility

Environmentのcanonical state、simulation、transition commitは
State Spaceが最も自然である。
Graph単独ではstate authorityが不足する。

### E6 LLM Compatibility

LLM RuntimeはContext state、Tool result、planning graph、evidence traceを必要とする。
HybridはTool executionをState update、reasoning planをGraphとして分離できる。

### E7 Scalability

純Graphの全Path列挙はlarge branching graphに弱い。
State Spaceはcurrent stateだけなら低負荷だが、Goal planning機能が不足する。
Hybridは必要時だけPlannerを起動することで常時二重実行を避けられる。

### E8 Reason IR Compatibility

現行Graph IRはGraph reconstructionを検証済みである。
ただしReason IRをGraph専用schemaに固定すると、Environment snapshot、
memory delta、external effectの表現が不自然になる。

Hybrid向けReason IRはState Transitionを必須、Graph planを任意とする。

## 9. Execution Model Ranking

### Rank 1: Layered Hybrid Runtime

探索、説明、状態更新の責務を分離できる。

Hybridのscoreは最高だが、実装複雑性は最大である。
そのため、GraphとStateを常に同期する一般的なdual modelではなく、
Graph PlanをState Kernelへ一方向にcommitする構造に限定する。

### Rank 2: Graph Runtime

現行資産、説明可能性、Reason IR reconstructionで強い。
Reasoning Plannerとして正式採用する。

単独のRuntime coreには不採用とする。
WorldModelとexternal effectsのstate authorityを持たないためである。

### Rank 2: State Space Runtime

MemorySpace、WorldModel、long-running executionのcanonical state管理に強い。
State Transition Kernelとして正式採用する。

単独のRuntime coreには不採用とする。
非局所探索とalternative explanationを追加すると、結果的にGraph Planner相当が
必要になるためである。

## 10. Runtime Architecture Recommendation

### 10.1 Formal Decision

ReasonScript Runtime v0.1は次を採用する。

```text
Execution Model: Layered Hybrid Runtime
State Authority: State Transition Kernel
Planner:         Optional Graph Planner
IR:              State-first Reason IR with optional Graph Plan
Trace:           Unified Execution Trace
```

### 10.2 Component Responsibilities

| Component | Responsibility |
|---|---|
| Execution Coordinator | request validation、component orchestration、budget管理 |
| State Transition Kernel | current state、transition apply、commit、rollback |
| Graph Planner | path search、planning、alternatives、cost comparison |
| Constraint Evaluator | transition前後のconstraint validation |
| Memory Adapter | SHM / CHM / DHM read、retrieval result normalization |
| Effect Executor | Tool、I/O、environment action |
| Trace Collector | path、evidence、violation、state delta、decision記録 |

### 10.3 Single State Authority Rule

Graph NodeとState Kernelの両方へmutable current stateを置かない。

```text
Forbidden:

Graph.current_node <-> StateKernel.current_state
```

この双方向同期は不整合、rollback漏れ、trace divergenceを発生させる。

採用構造:

```text
Graph Planner
  -> immutable ExecutionPlan
  -> State Transition Kernel
  -> committed StateDelta
  -> Trace
```

GraphはPlan生成後にstateを直接変更しない。

### 10.4 Planner Activation

Graph Plannerを使用する条件:

- 複数transition候補がある
- Goal-directed searchが必要
- alternative pathが必要
- cost / risk比較が必要
- provenance graphを要求された

Graph Plannerを省略する条件:

- 一意なdeterministic transition
- 明示されたPipeline stageの逐次実行
- 単一Tool call resultのcommit
- Memory retrieval resultの単純integration

これによりHybridのRuntime負荷を抑える。

## 11. Reason IR Execution Basis

Reason IRをGraph IRと同義にしない。

推奨最小構造:

```text
ReasonIR
├─ schema_version
├─ initial_state
├─ goal
├─ context_refs
├─ constraints
├─ transitions
├─ planner_policy
├─ execution_policy
└─ trace_policy
```

Optional planning artifact:

```text
ExecutionPlan
├─ selected_steps
├─ alternative_paths
├─ expected_cost
├─ evidence_refs
└─ planner_version
```

Execution result:

```text
InferenceResult
├─ status
├─ final_state
├─ state_deltas
├─ proof
├─ violations
├─ alternatives
└─ trace_id
```

### IR Invariants

1. `ReasonIR`は言語SDKに依存しない。
2. `Transition`はsource、relation、target/effect、guardを持つ。
3. GraphはReason IRから構築可能だが必須ではない。
4. ExecutionPlanはimmutableである。
5. State変更はKernelのcommitからのみ発生する。
6. 全commitはTrace eventと対応する。
7. Constraint failure時は部分commit方針を明示する。
8. schema、planner、policy versionを記録する。

## 12. System Compatibility

### MemorySpace

推奨mapping:

```text
Memory query       -> Effect request
Retrieved memory  -> Evidence / ContextDelta
Integration       -> State transition
Memory relations  -> Optional Graph index
```

MemorySpace recordをGraph Nodeへ固定しない。
Graph projectionは再構築可能なindexとして扱う。

### DBM

推奨mapping:

```text
Goal                  -> Reason IR Goal
Hypothesis generation -> Planner candidate generation
Validation            -> Constraint Evaluator
Selection             -> Graph Planner / Decision policy
Execution             -> State Transition Kernel
```

### WorldModel

推奨mapping:

```text
Environment snapshot -> State
Possible actions     -> Transitions
Simulation branches -> Graph Plan
Selected action     -> ExecutionPlan
Environment update  -> State commit
```

### LLM Runtime

推奨mapping:

```text
Prompt / Context -> Context refs
Reasoning plan   -> Graph Plan
Tool call        -> Effect request
Tool result      -> Evidence + StateDelta
Guardrail        -> Constraint
Final response   -> InferenceResult projection
```

LLMのhidden chain-of-thoughtをTrace契約に要求しない。
Traceには構造化されたdecision reason、tool result、evidence reference、
selected actionを保存する。

### Multi-Language SDK

SDKはExecution Modelを再実装しない。

```text
Python / TypeScript / Go / Java
              |
              v
       Versioned Reason IR
              |
              v
       Rust Hybrid Runtime
```

Graph PlannerとState Kernelの内部差はSDKから隠蔽し、
共通`InferenceResult`だけを公開する。

## 13. Risks and Controls

| Risk | Control |
|---|---|
| Hybridの実装肥大化 | Plannerをoptionalにし、Coordinator APIを最小化 |
| GraphとStateの不整合 | State Kernelを唯一のmutable authorityとする |
| 大規模Graph探索爆発 | budget、heuristic、depth、beam、indexをReason IR policy化 |
| Trace肥大化 | trace levelとexternal evidence referenceを導入 |
| Effect失敗時の部分更新 | prepare / validate / commitとrollback policyを定義 |
| SDK divergence | versioned DTOとconformance testsを使用 |
| Graph IRとの重複 | Graph IRをReason IRのplanning projectionとして位置付ける |

## 14. Success Criteria

| Criterion | Result |
|---|---|
| 全Execution Model比較完了 | PASS |
| 評価結果定量化完了 | PASS |
| Runtime推奨構造決定 | PASS: Layered Hybrid |
| MemorySpaceとの整合性確認 | PASS: architecture level |
| DBMとの整合性確認 | PASS: prototype + architecture level |
| WorldModelとの整合性確認 | PASS: prototype + architecture level |
| Reason IR実行基盤方針決定 | PASS |

## 15. Final Decision

ReasonScript Runtime v0.1の正式実行構造を次とする。

```text
Pipeline
  ↓
Reason IR
  ↓
Execution Coordinator
  ├─ Optional Graph Planner
  ├─ Constraint Evaluator
  └─ Memory / Effect Adapters
  ↓
State Transition Kernel
  ↓
InferenceResult + Unified Trace
```

Graph Runtimeを廃止しない。
GraphをRuntime全体ではなく、探索、計画、説明の専門componentとして位置付ける。

State Space Runtimeを単独採用しない。
State Spaceを、全状態変更を管理する最小かつ唯一のexecution kernelとする。

Phase 1の結論:

```text
ReasonScript Runtime
=
State-first Layered Hybrid Runtime
```

次Phaseでは、`ReasonIR -> ExecutionPlan -> StateDelta`のversioned schema、
commit protocol、conformance testsを定義する。
