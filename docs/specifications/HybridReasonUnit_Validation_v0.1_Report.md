# HybridReasonUnit Validation v0.1 Report

**実行日:** 2026-06-11  
**対象:** HybridRuntime v0.2  
**Package:** `reasonscript-hybrid-runtime 0.2.0`  
**結果:** VALIDATED

## 1. Executive Summary

添付されたHybridReasonUnit Validation Specificationに基づき、
HRU-01からHRU-10までを実装Runtime上で検証した。

```text
HRU-01 PASS
HRU-02 PASS
HRU-03 PASS
HRU-04 PASS
HRU-05 PASS
HRU-06 PASS
HRU-07 PASS
HRU-08 PASS
HRU-09 PASS
HRU-10 PASS
```

検証結果から、HybridReasonUnitはHybridRuntime上で次を満たす。

1. Stateだけを保持する最小単位として生成できる。
2. AmbiguousStateからRuntime側の評価・意思決定・戦略実行によりStableStateへ解決できる。
3. Clarify時にはStableStateを偽装せずAmbiguousStateを保持できる。
4. StableStateはTransitionEngineにより連続遷移できる。
5. ResolutionとTransitionの監査情報をReasonUnit外部のTraceLoggerへ保存できる。
6. 複数ReasonUnitとUnit間関係をRuntime側で管理できる。

したがって、HRU-H1からHRU-H4は本検証範囲で支持された。

## 2. Pre-Validation Gap Analysis

検証開始時点のHybridRuntime v0.2には次の不足があった。

| Gap | Impact |
| --- | --- |
| Resolution TraceのみでTransition Traceがない | HRU-07からHRU-09を監査できない |
| `evaluator_version`がTraceにない | Required Trace Fieldsを満たさない |
| `resolution_outcome`がTraceにない | Deferred理由を監査できない |
| 次点戦略とのスコア差がない | HRU-06を完全に検証できない |
| StateManagerが単一Unitのみ管理 | HRU-10を検証できない |

検証を成立させるため、次をRuntimeへ追加した。

- Resolution / Transition共通Trace schema
- `TraceEventKind`
- `test_id`
- `initial_state`
- `resolution_outcome`
- `transition_relation`
- `next_state`
- `evaluator_version`
- `selected_to_next_score_gap`
- StateManagerの名前付きReasonUnit登録
- RuntimeのTransition Trace記録

## 3. Test Implementation

検証コード:

```text
HybridRuntime/tests/hybrid_reason_unit_validation.rs
```

検証は候補生成器や外部I/Oを使用せず、仕様で与えられた候補分布と
制御された意味ベクトル・Evidenceを直接入力した。

## 4. Detailed Results

### HRU-01 Stable ReasonUnit Creation

**結果:** PASS

- `StateKind::Stable`
- Identity `Dog`
- HybridReasonUnitのJSONトップレベルキーは`state`のみ

Decision、Trace、History、CostがReasonUnitへ混入していないことを確認した。

### HRU-02 Ambiguous ReasonUnit Creation

**結果:** PASS

候補分布:

```text
Dog  0.45
Wolf 0.40
Fox  0.15
```

- `StateKind::Ambiguous`
- candidate count `3`
- 候補順序と確率値を保持

### HRU-03 Low Ambiguity Real Resolution

**結果:** PASS

期待コスト:

| Strategy | Cost |
| --- | ---: |
| Real | 0.2000 |
| Clarify | 0.5100 |
| Complex | 0.9175 |

`RealStrategy`が選択され、`Resolved(Dog)`となった。
Traceには期待コスト最小化を使用した判断理由が保存された。

### HRU-04 Medium Ambiguity Clarify Deferred

**結果:** PASS

期待コスト:

| Strategy | Cost |
| --- | ---: |
| Clarify | 0.9300 |
| Complex | 1.0400 |
| Real | 1.6000 |

`ClarifyStrategy`が選択された。

- Runtime StateはAmbiguousのまま
- `requested_evidence`は空ではない
- Traceの`resolution_outcome`にDeferred理由を保存
- StableStateへの偽装なし

### HRU-05 High Ambiguity Complex Resolution

**結果:** PASS

入力条件:

```text
Dog  0.45
Wolf 0.40
Fox  0.15
Conflict    0.00
Unsupported 0.00
```

期待コスト:

| Strategy | Cost |
| --- | ---: |
| Complex | 1.0925 |
| Clarify | 1.1100 |
| Real | 2.2000 |

`ComplexStrategy`が選択され、StableStateへ解決された。
Traceには3戦略すべてのスコアが保存された。

`cargo tree --offline`により、HybridRuntimeの直接依存は
`serde`と`serde_json`だけであり、`num-complex`やRuntimeComplexへ
依存しないことを確認した。

### HRU-06 Conflict-Aware Decision

**結果:** PASS

実測値:

```text
evidence_conflict = 0.662150
selected_strategy = Clarify
```

期待コスト:

| Strategy | Cost |
| --- | ---: |
| Clarify | 1.053260 |
| Complex | 1.098022 |
| Real | 2.121224 |

次点との差:

```text
Complex - Clarify = 0.044763
```

結果はPhase Aの観測と一致した。高ConflictだけでComplexへ固定せず、
期待コストによりClarifyが選択された。

Traceには次を保存した。

- selected strategy: Clarify
- first alternative: Complex
- 全strategy scores
- selected-to-next score gap
- decision reason

### HRU-07 Stable State Transition

**結果:** PASS

```text
Dog --IsA--> Mammal
```

- StateManager上のReasonUnit StateがMammalへ更新
- Transition Traceを1件保存
- initial state、relation、next stateを確認

### HRU-08 Chained Transition

**結果:** PASS

```text
Dog --IsA--> Mammal --IsA--> Animal
```

- 2回の連続遷移に成功
- 最終StateはAnimal
- Transition Traceは2件
- 各Traceのevent kindはTransition

### HRU-09 Ambiguous to Transition Pipeline

**結果:** PASS

```text
Ambiguous(Dog/Wolf/Fox)
  -> RealStrategy
  -> Stable(Dog)
  -> IsA
  -> Stable(Mammal)
```

同一Runtime内でIdentity ResolutionとTransitionを連結できた。

Trace event sequence:

```text
1. Resolution
2. Transition
```

### HRU-10 Multiple ReasonUnit Interaction

**結果:** PASS

```text
Primary Unit: Dog
Named Unit B: Mammal
Relation: Dog IsA Mammal
```

- StateManager unit count: `2`
- Unit BのIdentityをRuntime側で参照
- Unit間関係をTransitionEngineへ登録
- Primary UnitがMammalへ遷移
- Unit B自体はMammalを保持

関係はReasonUnit内ではなくRuntime側に保持される。

## 5. Trace Schema Validation

Resolution TraceとTransition Traceは同一schemaで次のフィールドを持つ。

```text
test_id
event_kind
initial_state
candidate_distribution
ambiguity_observation
selected_strategy
alternative_strategies
strategy_scores
selected_to_next_score_gap
decision_reason
resolution_outcome
transition_relation
next_state
policy_version
evaluator_version
```

イベントに該当しない項目もschemaから削除せず、`null`または空集合として
JSONに残ることをテストした。

## 6. Hypothesis Evaluation

| Hypothesis | Result | Evidence |
| --- | --- | --- |
| HRU-H1 | Supported | UnitはStateのみでHRU-03から09を実行可能 |
| HRU-H2 | Supported | Decision、Trace、CostはRuntime側で完結 |
| HRU-H3 | Supported | Real/ComplexでAmbiguousからStableへ変換 |
| HRU-H4 | Supported | Stableから単発・連続Transitionが成立 |

## 7. Verification Commands

```text
cd HybridRuntime
cargo test --offline --test hybrid_reason_unit_validation -- --nocapture
cargo test --offline
cargo clippy --offline --all-targets -- -D warnings
cargo tree --offline
```

関連するPhase A回帰:

```text
cd Test
cargo test --test hybrid_runtime_phase_a
```

## 8. Execution Results

```text
HybridReasonUnit Validation: 10 passed, 0 failed
HybridRuntime complete suite: 18 passed, 0 failed
Phase A regression: 3 passed, 0 failed
Clippy: PASS, warnings denied
Formatting: PASS
```

## 9. Limitations

本検証は次を証明しない。

- WorldModelの成立
- MemorySpaceの完成
- LLMまたは自然言語処理能力
- 候補生成の正確性
- 複素推論の一般化
- 永続化・分散実行・外部I/O

HRU-10は複数Unitの登録とRuntime管理関係を検証したものであり、
複数Unitの同時実行、競合更新、transaction isolationは対象外である。

ComplexStrategyはResolutionStrategyとしての統合を検証した。
複素数アルゴリズム自体の数学的妥当性は対象外である。

## 10. Conclusion

本検証範囲において、次の結論を支持する。

```text
HybridReasonUnitは、
HybridRuntime上で状態保持・Identity解決・状態遷移を行う
推論状態遷移の最小単位として機能する。
```

Decision、Trace、History、Cost、Unit間関係をReasonUnitから分離しても、
Runtime側のコンポーネントにより推論処理と監査処理を完結できる。
