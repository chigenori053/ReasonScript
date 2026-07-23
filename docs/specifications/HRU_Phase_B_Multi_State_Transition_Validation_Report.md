# HRU Phase B Multi-State Transition Validation Report

**Version:** 0.1  
**実行日:** 2026-06-11  
**Target:** HybridRuntime v0.2  
**Status:** VALIDATED

## 1. Executive Summary

HRU Phase B Specificationに基づき、多重状態遷移、分岐、合流、
複数ReasonUnit、Unit間関係、遷移競合、Graph状況下のTraceを検証した。

```text
HRU-B-01 PASS
HRU-B-02 PASS
HRU-B-03 PASS
HRU-B-04 PASS
HRU-B-05 PASS
HRU-B-06 PASS
HRU-B-07 PASS
HRU-B-08 PASS
HRU-B-09 PASS
HRU-B-10 PASS
HRU-B-11 PASS
HRU-B-12 PASS
```

Phase Bの全12項目が成功した。

本検証範囲では、HybridReasonUnitがGraph状況下でもStateのみを保持し、
複数遷移とUnit間関係をRuntime側へ分離したまま、推論状態遷移の最小単位として
機能することが確認された。

## 2. Pre-Validation Gap Analysis

Phase B開始時点のTransitionEngineは次の制約を持っていた。

```text
(source, relation) -> single target
```

この構造では次を表現できなかった。

- `Dog --IsA--> Mammal`
- `Dog --IsA--> Canine`
- 同一Stateからの複数分岐
- 遷移候補の期待コスト比較
- 同率候補の競合検出
- Parents関係照会
- Graph遷移Decisionの完全Trace

検証のため、次を追加した。

| Addition | Purpose |
| --- | --- |
| `TransitionCandidate` | source/relation/target/costを保持 |
| 複数規則の`Vec`管理 | 同一source/relationから複数targetを許可 |
| `outgoing` | Stateの全遷移候補を取得 |
| `parents` | IsA親関係を照会 |
| `relation_count` | Runtime管理関係数を取得 |
| `TransitionDecisionInput/Result` | DecisionEngineによる遷移選択 |
| `decide_and_transition` | 列挙、選択、更新、Traceを統合 |
| `TransitionDecisionRequired` | 同率競合時に自動選択を禁止 |
| `TransitionConflict` Trace | 競合時にも監査情報を保存 |

## 3. Transition Decision Model

Phase Bでは、各TransitionCandidateが`expected_cost`を持つ。

DecisionEngineは候補を期待コスト昇順で比較し、最小コスト候補を選択する。

```text
selected_transition = argmin(expected_cost)
```

同率最小候補が存在する場合は決定論的な名前順選択を行わず、
`TransitionDecisionRequired`を返す。

これは単純なrelation一致ではなく、Runtime側の意思決定として実行される。

## 4. Detailed Results

### HRU-B-01 Multiple Outgoing Transition

**結果:** PASS

登録規則:

```text
Dog --IsA--> Mammal
Dog --IsPet--> Pet
Dog --IsA--> Canine
```

観測:

```text
outgoing transition count = 3
runtime relation count = 3
current state = Dog
```

候補列挙だけではReasonUnitのStateは変更されなかった。

### HRU-B-02 Branch Selection

**結果:** PASS

制御された期待コスト:

| Transition | Cost |
| --- | ---: |
| Dog --IsPet--> Pet | 0.10 |
| Dog --IsA--> Canine | 0.30 |
| Dog --IsA--> Mammal | 0.50 |

DecisionEngineは`IsPet -> Pet`を選択した。

Trace:

- available transitions: 3
- selected transition: `Dog --IsPet--> Pet`
- alternative transitions: 2
- decision reason: `minimum expected transition cost`
- selected-to-next gap: `0.20`

### HRU-B-03 Sequential Branch Chain

**結果:** PASS

```text
Dog
  -> DecisionEngine
  -> Pet
  -> RefinesTo
  -> CompanionAnimal
```

最終Stateは`CompanionAnimal`、Trace件数は2件だった。

### HRU-B-04 Converging Transition

**結果:** PASS

```text
Dog  --IsA--> Mammal
Wolf --IsA--> Mammal
```

異なる初期ReasonUnitから同一StableStateへ合流した。
両経路の最終Stateは構造的に等しかった。

### HRU-B-05 Multi-Hop Transition

**結果:** PASS

```text
Dog
 -> Canine
 -> Mammal
 -> Animal
 -> LivingThing
```

観測:

```text
successful transitions = 4
trace records = 4
final state = LivingThing
```

全遷移とTrace件数が一致した。

### HRU-B-06 Multiple ReasonUnit Network

**結果:** PASS

```text
Primary Unit = Dog
Unit B = Mammal
Unit C = Animal
```

StateManagerの`unit_count`は3だった。

### HRU-B-07 Cross-Unit Relation

**結果:** PASS

```text
Dog IsA Mammal
Mammal IsA Animal
```

TransitionEngineの`relation_count`は2だった。
RelationはReasonUnit内ではなくRuntime側に存在する。

### HRU-B-08 Relation Query

**結果:** PASS

Query:

```text
parents("Dog")
```

Result:

```text
["Mammal"]
```

Runtime管理関係から親Stateを解決した。

### HRU-B-09 Decision Driven Transition

**結果:** PASS

DecisionEngine経由で3候補から遷移を選択した。

Traceには次を保存した。

- available transitions: 3
- selected transition
- alternative transitions: 2
- transition scores: 3
- selected-to-next score gap
- next state

### HRU-B-10 Transition Conflict

**結果:** PASS

入力:

```text
StateX --A--> Y, cost=0.25
StateX --B--> Z, cost=0.25
```

観測:

```text
result = TransitionDecisionRequired
current state = StateX
selected transition = None
score gap = 0.0
```

Runtimeは同率候補を自動選択せず、Stateを変更しなかった。

`TransitionConflict` Traceには次を保存した。

- available transitions: 2
- alternative transitions: 2
- selected transition: null
- decision reason: decision required
- transition scores
- next state: null

### HRU-B-11 Trace Completeness

**結果:** PASS

JSON Traceに次の必須フィールドが存在することを確認した。

```text
test_id
initial_state
available_transitions
selected_transition
alternative_transitions
decision_reason
next_state
trace_event_kind
policy_version
evaluator_version
```

成功遷移では`trace_event_kind = Transition`となる。
競合では`trace_event_kind = TransitionConflict`となる。

### HRU-B-12 Graph Integrity

**結果:** PASS

複数Relation登録後もHybridReasonUnitのJSONトップレベル構造は次だけだった。

```text
HybridReasonUnit {
    state
}
```

Relation、TransitionCandidate、Decision、TraceはUnitへ混入していない。

## 5. Hypothesis Evaluation

| Hypothesis | Result | Evidence |
| --- | --- | --- |
| HRU-B-H1 | Supported | 1 Stateから3遷移を保持 |
| HRU-B-H2 | Supported | Runtimeが列挙、選択、競合停止を管理 |
| HRU-B-H3 | Supported | 3 Unitと2 RelationをRuntime側で保持 |
| HRU-B-H4 | Supported | Relation追加後もUnitはStateのみ |
| HRU-B-H5 | Supported | DecisionEngineが期待コストで分岐選択 |

## 6. Trace Model

Phase B対応後のTransition Traceは次を持つ。

```text
test_id
event_kind
trace_event_kind
initial_state
available_transitions
selected_transition
alternative_transitions
transition_scores
selected_to_next_score_gap
decision_reason
transition_relation
next_state
policy_version
evaluator_version
```

Resolution Traceと同じTraceRecord schemaを維持し、イベント非該当項目は
`null`または空集合として保存する。

## 7. Verification Commands

```text
cd HybridRuntime
cargo test --offline --test hru_phase_b -- --nocapture
cargo test --offline
cargo fmt -- --check
cargo clippy --offline --all-targets -- -D warnings
cargo tree --offline
```

Phase A研究回帰:

```text
cd Test
cargo test --test hybrid_runtime_phase_a
```

## 8. Execution Results

```text
HRU Phase B: 12 passed, 0 failed
HybridRuntime complete suite: 30 passed, 0 failed
Phase A regression: 3 passed, 0 failed
Formatting: PASS
Clippy with warnings denied: PASS
```

HybridRuntimeの依存は`serde`と`serde_json`のみであり、Graph/Tensor/GPU Runtimeや
外部I/Oへの依存は追加されていない。

## 9. Limitations

本検証はReasonGraphそのものの成立を主張しない。

今回検証したGraph状況は次に限定される。

- Runtime内の有向Relation集合
- 単一プロセス内のReasonUnit管理
- 期待コストが入力済みのTransitionCandidate
- StableState間の決定論的State更新

未検証:

- cycle detection
- graph closure
- path search
- topological constraints
- concurrent Unit updates
- transaction isolation
- dynamic cost learning
- Graph IR conversion
- 永続化

特にTransition expected costは制御実験用入力であり、コスト推定器はPhase Bの対象外である。

## 10. Conclusion

本検証範囲において、次の結論を支持する。

```text
HybridReasonUnitは、
Graph状況下においても
推論状態遷移の最小単位として機能する。
```

また、実装構造として次が支持された。

```text
Graph状況
=
Stateのみを持つReasonUnit群
+
Runtimeが管理するRelation・Decision・Trace
```

ただし、これはReasonGraphの完全な成立を意味しない。
Phase Bの結論はMulti-State TransitionとMulti-ReasonUnit Managementの成立に限定する。
