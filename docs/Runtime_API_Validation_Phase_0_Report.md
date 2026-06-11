# ReasonScript Runtime API Validation Phase 0 Report

Version: 0.1  
Validation date: 2026-06-12  
Target: ReasonScript Core Runtime Research  
Status: COMPLETE (design validation)

## 1. Executive Summary

Runtime API候補4方式を、7評価軸と5共通ケースで比較した。

総合順位:

| Rank | Candidate | Score | Result |
|---:|---|---:|---|
| 1 | API-D: Pipeline API | 30 / 35 | v0.1標準APIとして推奨 |
| 2 | API-C: Goal API | 28 / 35 | 高水準Convenience APIとして採用 |
| 3 | API-A: Graph API | 27 / 35 | Advanced / Diagnostic APIとして採用 |
| 4 | API-B: ReasonUnit API | 25 / 35 | データモデルとして採用、単独入口には不採用 |

結論は、4方式から1方式だけを残すことではない。

4候補は同一レイヤーの代替案ではなく、役割が異なる。

```text
Goal API       User intent facade
Pipeline API   Standard composition API
Graph API      Advanced execution and inspection API
ReasonUnit API Runtime data model
```

ReasonScript Runtime v0.1の標準利用者APIには、明示性、DBM適合性、
LLM Tool Useとの整合性、多言語SDK化のバランスが最も良い
`Pipeline API`を推奨する。

内部では全APIを共通のReason IRへloweringし、Graph Runtimeで実行する。
Goal APIはPipelineを生成する薄い入口、ReasonUnitはPipelineとGraphの間で
受け渡す最小推論単位とする。

```text
Goal / Pipeline / Graph / ReasonUnit API
                  |
                  v
              Reason IR
                  |
                  v
          Rust Graph Runtime
                  |
                  v
       Trace / Result / RuntimeError
```

## 2. Validation Method

### 2.1 Score Definition

全評価軸を、数値が大きいほど望ましい方向へ統一した。

| Score | Meaning |
|---:|---|
| 5 | Excellent |
| 4 | Good |
| 3 | Acceptable |
| 2 | Weak |
| 1 | Poor |

E2は名称が`Runtime Complexity`であるため注意が必要である。
本レポートでは次のように評価する。

```text
E2 = 5: Runtime実装負荷が低い
E2 = 1: Runtime実装負荷が高い
```

仕様に重み指定がないため、E1からE7は等重みとした。

### 2.2 Evidence Classes

評価根拠を次の3段階に分離した。

| Class | Definition |
|---|---|
| V | 現行Runtimeとテストで検証済み |
| P | Phase 0のAPIプロトタイプで表現可能性を確認 |
| A | 将来システムとのarchitecture assessment |

MemorySpace、DBM、WorldModel、LLM Runtimeは現リポジトリで完成していない。
したがって、それらの互換性スコアは実行性能の実証値ではなく、
責務分離、データフロー、状態表現、SDK境界に基づく設計評価である。

### 2.3 Repository Evidence

現行コードから次を確認した。

| Evidence | Status |
|---|---|
| ReasonUnitを最小状態単位として保持 | V |
| ReasonGraphのNode / Relation構築 | V |
| 単一および複数Edgeの推論 | V |
| costによるPath選択と競合検出 | V |
| Resolution / Transition / Graph Trace | V |
| Semantic constraint validation | V (限定実装) |
| Goal API | 未実装 |
| Pipeline API | 未実装 |
| MemorySpace / DBM / WorldModel / LLM統合 | 未実装 |

### 2.4 Verification Results

実行コマンド:

```text
cd HybridRuntime
cargo test --offline --test reason_graph_validation
cargo test --offline --test hybrid_reason_unit_validation

cd RuntimeReal
cargo test --offline --test semantic_constraint_tests
```

結果:

| Suite | Passed | Failed |
|---|---:|---:|
| ReasonGraph validation | 14 | 0 |
| HybridReasonUnit validation | 10 | 0 |
| Semantic constraint validation | 2 | 0 |
| **Total** | **26** | **0** |

`RuntimeReal`のtest実行時に、既存の`DynamicsContext`未使用import警告が
1件出力された。テスト結果と本PhaseのAPI評価には影響しない。

## 3. Common Semantic Contract

API表現だけを比較するため、全候補で同じ意味契約を使用した。

```text
Entity:
  Animal
  Mammal
  Dog

Relation:
  Dog IsA Mammal
  Mammal IsA Animal

Constraint:
  Animal Cannot Fly

Goal:
  Given Dog, find Mammal

DBM stages:
  Input
  HypothesisGeneration
  Validation
  Selection
  Output

World transition:
  StateA --Transition--> StateB
```

全APIの戻り値は、最低限次を共有する必要がある。

```text
InferenceResult
├─ status
├─ value / final_state
├─ proof / selected_path
├─ violations
├─ alternatives
└─ trace_id
```

例外や言語固有型を公開契約の中心にせず、Reason IRと同型の
versioned DTOをSDK境界に置く。

## 4. Candidate Prototypes

以下はAPI形状を比較するためのPhase 0プロトタイプであり、
新規Runtime実装ではない。

### 4.1 API-A: Graph API

```python
graph = ReasonGraph("taxonomy")
graph.add_state("Animal")
graph.add_state("Mammal")
graph.add_state("Dog")
graph.add_transition("Dog", "IsA", "Mammal")
graph.add_transition("Mammal", "IsA", "Animal")

result = graph.infer(start="Dog", target="Animal")
```

特徴:

- RuntimeのNode、Relation、Path、Traceと直接対応する。
- Graph構造、探索方向、制約Nodeなどの知識を利用者へ要求する。
- デバッグ、可視化、WorldModel simulationに強い。

### 4.2 API-B: ReasonUnit API

```python
dog = ReasonUnit.state("Dog")
mammal = ReasonUnit.state("Mammal")

result = dog.infer(
    relation="IsA",
    target=mammal,
    context=context,
)
```

特徴:

- 単一推論単位の生成と局所操作は理解しやすい。
- 複数Unitの関係、探索、共有Context、Traceを誰が所有するかが曖昧になる。
- 多言語DTOには適するが、システム全体の入口には不足する。

### 4.3 API-C: Goal API

```python
result = runtime.solve(
    goal=Goal.find("Mammal"),
    input=Entity("Dog"),
    context=context,
)
```

特徴:

- 利用者が意図だけを指定でき、学習コストが最も低い。
- Goal解釈、探索空間、停止条件、制約、予算のdefault設計が必要になる。
- LLMやAgentの入口に適するが、再現性のため構造化Goalが必須である。

禁止する設計:

```python
runtime.solve(goal="Find Mammal")  # 文字列だけを標準契約にしない
```

文字列GoalはSDK helperとして許容できるが、Runtime coreには
typed Goalへ変換済みの入力を渡す。

### 4.4 API-D: Pipeline API

```python
result = (
    runtime.pipeline("taxonomy")
    .input(Entity("Dog"))
    .infer(Find(type="Mammal"))
    .validate(context.constraints)
    .select(MinExpectedCost())
    .output(InferenceResult)
    .run()
)
```

特徴:

- 入力、推論、検証、選択、出力を明示できる。
- DBM、LLM Tool Use、Context Controlを同一モデルで表せる。
- 単純推論には記述量が増えるため、Goal APIによる短縮が必要である。

## 5. Validation Cases

### 5.1 Case-1: Basic Inference

```text
Animal <-IsA- Mammal <-IsA- Dog
```

| API | Representation | Assessment |
|---|---|---|
| A | 3 Nodesと2 Relationsを登録しPath探索 | 最も直接的。現行Graph Runtimeで検証済み |
| B | 3 Unitを生成しUnit間推論を連鎖 | 小規模なら簡潔。関係所有者が不明瞭 |
| C | `solve(Find("Animal"), input="Dog")` | 最短。探索範囲と根拠取得optionが必要 |
| D | `input -> infer -> output` | 明示的だが単純例にはやや冗長 |

Result: 全APIで表現可能。

### 5.2 Case-2: Constraint Validation

```text
Claim: Dog CanFly
Constraint: Animal CannotFly
```

| API | Representation | Assessment |
|---|---|---|
| A | Constraint relationをGraphへ登録しPath上で評価 | 根拠追跡に強いがconstraint schemaが必要 |
| B | Dog Unitへconstraint contextを渡す | Unit外Contextが必須。単独APIの利点が低下 |
| C | GoalとContextへclaim / constraintを渡す | 簡潔だが検証順序が隠れる |
| D | `infer -> validate -> reject/output` | 検証境界と失敗処理が最も明確 |

Expected result:

```text
status = Rejected
violations = ["Dog inherits Animal CannotFly"]
```

Result: Dが最適。Aは低水準表現として有効。

### 5.3 Case-3: Goal Search

```text
Input: Dog
Goal: Find Mammal
```

| API | Representation | Assessment |
|---|---|---|
| A | DogからMammalへのPath探索 | 実行は明確だが利用者がtarget Nodeを理解する必要あり |
| B | Dog Unitからrelationを辿る | 複数候補と探索budgetの配置が困難 |
| C | Goalを直接solve | 最も自然 |
| D | `input -> infer(goal) -> select -> output` | Goalに加えて制御条件を明示可能 |

Result: Cが最短、Dが最も制御可能。

### 5.4 Case-4: DBM Style Reasoning

```text
Input
  -> Hypothesis Generation
  -> Validation
  -> Selection
  -> Output
```

Pipeline prototype:

```python
result = (
    runtime.pipeline("dbm")
    .input(observation)
    .generate_hypotheses(strategy)
    .validate(constraints)
    .select(MinExpectedCost())
    .output(DecisionResult)
    .run()
)
```

| API | Assessment |
|---|---|
| A | 各段階をsubgraph化できるがworkflow記述が低水準 |
| B | Unit群だけではstage ordering、branch、failure policyが不足 |
| C | DBM全体をGoalとして委譲できるが中間状態の制御が弱い |
| D | stage、branch、validation、selection、traceが自然に対応 |

Result: Dが明確に優位。

### 5.5 Case-5: WorldModel Transition

```text
StateA --Transition--> StateB
```

| API | Assessment |
|---|---|
| A | State / Transition / simulation branchを直接表現できる |
| B | 単一遷移は簡潔。環境全体と分岐管理は外部機構が必要 |
| C | desired stateは表せるがsimulation semanticsが隠れる |
| D | simulation stageを構成できるが内部Graphモデルが必要 |

Result: Aが最適。DはAを実行基盤として利用する場合に有効。

## 6. Case Fitness

各ケースについて、5を最適として表現適合性を評価した。

| API | Basic | Constraint | Goal | DBM | WorldModel | Total |
|---|---:|---:|---:|---:|---:|---:|
| A: Graph | 5 | 5 | 4 | 3 | 5 | 22 / 25 |
| B: ReasonUnit | 5 | 3 | 2 | 2 | 4 | 16 / 25 |
| C: Goal | 5 | 3 | 5 | 4 | 3 | 20 / 25 |
| D: Pipeline | 4 | 5 | 5 | 5 | 5 | 24 / 25 |

## 7. Evaluation Scores

| Criterion | A: Graph | B: ReasonUnit | C: Goal | D: Pipeline |
|---|---:|---:|---:|---:|
| E1 Learning Cost | 2 | 4 | 5 | 4 |
| E2 Runtime Complexity | 5 | 4 | 2 | 3 |
| E3 MemorySpace Compatibility | 5 | 4 | 3 | 4 |
| E4 DBM Compatibility | 3 | 2 | 5 | 5 |
| E5 WorldModel Compatibility | 5 | 3 | 3 | 4 |
| E6 LLM Compatibility | 3 | 3 | 5 | 5 |
| E7 SDK Expandability | 4 | 5 | 5 | 5 |
| **Total** | **27** | **25** | **28** | **30** |

### 7.1 API-A Assessment

Strengths:

- 現行`ReasonGraphRuntime`と最も直接対応する。
- Graph管理、Path選択、競合、Traceの実装負荷が予測可能。
- MemorySpaceのentity/relation参照とWorldModelの状態遷移を表現しやすい。

Risks:

- 一般SDK利用者へGraph構築を強制すると学習コストが高い。
- DBMやLLM workflowではboilerplateが増える。
- Graph storage schemaを公開APIと同一視すると将来の内部変更を妨げる。

Decision: 公開するが標準入口にはしない。

### 7.2 API-B Assessment

Strengths:

- ReasonScriptの最小概念と一致する。
- immutable / serializable DTOにすれば全SDKへ展開しやすい。
- 局所的な状態と候補表現に適する。

Risks:

- Graph、Context、探索、制約、Traceの責務をUnitへ入れると肥大化する。
- Unitへ`infer()`を持たせると、data objectとruntime serviceの責務が混在する。
- 大規模推論のownershipとlifecycleを表現できない。

Decision: `ReasonUnit`はデータモデルとし、top-level Runtime APIにはしない。

### 7.3 API-C Assessment

Strengths:

- 最小の学習コスト。
- Agent、LLM、interactive useから呼びやすい。
- typed Goalなら各言語で安定したSDK契約を作れる。

Risks:

- Goal decomposition、探索、validation、selectionがRuntimeへ集中する。
- default policyが暗黙だと、同じGoalでも結果が再現しにくい。
- 自然言語文字列をcore契約にすると、多言語SDKではなくLLM依存APIになる。

Decision: Pipelineを生成するConvenience APIとして採用する。

### 7.4 API-D Assessment

Strengths:

- DBMの各段階と直接対応する。
- validation、selection、context、budget、traceを明示できる。
- LLM tool orchestrationと通常のdeterministic workflowを同じ形で扱える。
- builderをReason IR command listへ変換すれば多言語展開しやすい。

Risks:

- stage typeと順序制約の設計が必要。
- arbitrary callbackを許すとSDK間の互換性が崩れる。
- 単純推論では冗長になる。

Decision: v0.1標準Runtime APIとして採用する。

## 8. Runtime API Ranking

### Rank 1: API-D Pipeline

総合バランスが最も良い。ReasonScriptが対象とする推論、検証、選択、
状態遷移を明示的なstageとして保持できる。

### Rank 2: API-C Goal

利用者体験は最良だが、単独で標準APIにするとRuntimeの暗黙責務が大きい。
Pipelineへloweringする入口として使用する。

### Rank 3: API-A Graph

現行実装との整合性とWorldModel適合性は最良である。
ただし一般利用者へ内部実行モデルを直接要求するため、標準入口にはしない。

### Rank 4: API-B ReasonUnit

重要なcore conceptであるが、API全体を構成するには不足する。
順位はReasonUnit自体の否定ではなく、top-level API候補としての順位である。

## 9. Runtime v0.1 Recommendation

### 9.1 Recommended Public Surface

```rust
pub trait Runtime {
    fn pipeline(&self, spec: PipelineSpec) -> Pipeline;
    fn solve(&self, request: SolveRequest) -> Result<InferenceResult, RuntimeError>;
    fn execute_graph(
        &self,
        request: GraphExecutionRequest,
    ) -> Result<InferenceResult, RuntimeError>;
}
```

`solve()`は独立した推論engineを持たない。

```text
solve(request)
  -> compile_goal(request)
  -> PipelineSpec
  -> Reason IR
  -> execute
```

`Pipeline`も独自の推論意味論を持たない。

```text
PipelineSpec
  -> validate stage order
  -> Reason IR
  -> Graph execution plan
  -> execute
```

### 9.2 API Ownership

| Component | Responsibility |
|---|---|
| ReasonUnit | 状態、候補、evidenceなどの最小値表現 |
| Goal API | 利用者意図をtyped Goalとして受理 |
| Pipeline API | 推論処理、制約、選択、出力の構成 |
| Graph API | Node / Relation / Pathの高度操作とinspection |
| Reason IR | APIと言語に依存しないcanonical contract |
| Rust Runtime | validation、探索、状態更新、trace生成 |

### 9.3 Required v0.1 Types

```text
ReasonUnit
Goal
Constraint
PipelineSpec
PipelineStage
GraphSpec
ExecutionPolicy
ExecutionBudget
InferenceResult
Proof
Violation
TraceReference
RuntimeError
```

すべての型へschema versionを付ける。

```text
schema_version: "reason-ir/v0.1"
```

### 9.4 Pipeline Rules

v0.1では任意関数をstageとして受け取らない。
SDK間で共有できる宣言的stageだけを許可する。

Required stage classes:

```text
Input
Infer
GenerateHypotheses
Validate
Select
Transition
Output
```

Required controls:

```text
max_steps
max_cost
timeout
selection_policy
trace_level
constraint_mode
```

### 9.5 Error and Trace Contract

全APIは共通のerror taxonomyを使用する。

```text
InvalidInput
InvalidPipeline
InvalidGraph
ConstraintViolation
GoalNotFound
DecisionRequired
BudgetExceeded
ExecutionFailure
```

すべての実行は最低限次をtraceへ残す。

```text
request_id
api_origin
reason_ir_version
policy_version
initial_state
stages
visited_nodes
visited_edges
selected_path
alternatives
violations
final_state
```

## 10. Multi-Language SDK Strategy

SDKはRuntime意味論を各言語で再実装しない。

```text
Python builder ─┐
TypeScript      ├─> versioned Reason IR DTO ─> Rust Runtime
Rust            │
Go              │
Java builder  ──┘
```

推奨事項:

- Rustをreference implementationとする。
- DTOはJSON Schemaまたは同等の言語非依存schemaから生成する。
- builderは各言語の慣用表現を使用してよい。
- stage名、error code、trace field、default policyは全SDKで一致させる。
- language callback、closure、class instanceをwire contractへ含めない。
- unknown fieldとversion mismatchの処理を仕様化する。

## 11. Compatibility Conclusions

### MemorySpace

Graph APIがstorage / relation modelに最も近い。
PipelineはMemorySpace query、read、write、validationをstage化できる。
ReasonUnitをMemorySpace recordそのものにはせず、adapter境界を設ける。

### DBM

Pipeline APIが最適である。
Goal、Task、Planning、Validation、Executionをstageとartifactで表現できる。

### WorldModel

Graph APIがcanonical execution modelとして最適である。
Pipelineはsimulation workflow、Goalはdesired state、ReasonUnitはstate valueを担当する。

### LLM

Goal APIとPipeline APIの組合せが最適である。
Prompt文字列をRuntime coreへ直接埋め込まず、Prompt、Tool Call、Context、
Validationをtyped artifact / stageとして扱う。

## 12. Success Criteria Assessment

| Criterion | Result |
|---|---|
| Runtime API候補の比較完了 | PASS |
| 評価結果の定量化完了 | PASS |
| 推奨API方式決定 | PASS: Pipeline API |
| 将来のSDK戦略との整合性確認 | PASS |
| Runtime v0.1設計指針確立 | PASS |

Phase 0はdesign validationとして完了した。

ただし、次は本Phaseの結論に含めない。

```text
MemorySpace compatibilityの実動作保証
DBM end-to-end実行保証
WorldModel simulationの性能保証
LLM provider統合保証
実利用者によるLearning Cost測定
```

## 13. Decision

ReasonScript Runtime v0.1は次の方針を採用する。

```text
Standard API:    Pipeline API
Convenience API: Goal API
Advanced API:    Graph API
Core data model: ReasonUnit
Canonical ABI:   Versioned Reason IR
Reference core:  Rust Runtime
```

この構成は、単一APIへ全責務を集中させず、利用者の学習コストと
Runtimeの明示性を両立する。

Phase 1では、`PipelineSpec -> Reason IR -> Graph execution plan`の
最小schemaとconformance testsを定義する。
