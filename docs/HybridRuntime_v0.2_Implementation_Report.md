# HybridRuntime v0.2 Implementation Report

**実装日:** 2026-06-11  
**Status:** Implemented  
**Crate:** `HybridRuntime/`  
**Package:** `reasonscript-hybrid-runtime 0.2.0`

## 1. Summary

HybridRuntime v0.2 Minimal Specificationに基づき、独立したRust crateとして
状態管理、曖昧度観測、期待コストによる意思決定、Identity解決、状態遷移、
監査Traceを実装した。

RuntimeRealおよびRuntimeComplexへの直接依存は持たない。
Runtimeは実数の候補確率と意味ベクトルを標準入力とし、ComplexStrategyを
交換可能なResolutionStrategyとして扱う。

## 2. Architecture

| Component | Implementation |
| --- | --- |
| HybridReasonUnit | `state.rs` |
| StateManager | `state.rs` |
| AmbiguityEvaluator | `ambiguity.rs` |
| DecisionEngine | `decision.rs` |
| IdentityResolver | `resolver.rs` |
| ResolutionStrategy | `strategy.rs` |
| TransitionEngine | `transition.rs` |
| TraceLogger | `trace.rs` |
| HybridRuntime | `runtime.rs` |

## 3. Implemented Behavior

### HybridReasonUnit

ReasonUnitは`State`だけを保持する。Decision、History、Cost、Confidence、
Metadata、TraceはRuntime側のコンポーネントに分離した。

### AmbiguityEvaluator

次の観測値を独立出力する。

```text
candidate_entropy
normalized_entropy
effective_candidate_count
top_candidate_probability
top_two_margin
semantic_candidate_density
evidence_conflict
unsupported_evidence_ratio
```

単一の`ambiguity_score`は実装していない。

### DecisionEngine

単純閾値ではなく、`RiskPolicy`に基づく期待コスト最小化を実装した。

```text
Real:
wrong_identity_cost * error_probability
+ conflict_cost * evidence_conflict
+ unsupported_evidence_cost * unsupported_evidence_ratio

Clarify:
clarify_base_cost
+ clarify_residual_risk * error_probability
+ 0.40 * evidence_conflict

Complex:
complex_base_cost
+ complex_residual_risk * error_probability
+ 0.15 * evidence_conflict
```

出力には選択戦略、代替戦略、理由、全戦略スコア、confidenceを含む。

### Resolution Strategies

- `RealStrategy`: 最大確率候補を確定する。
- `ClarifyStrategy`: 状態を維持し、追加証拠要求を返す。
- `ComplexStrategy`: 候補確率、証拠対立、候補中心性を使って再評価する。

ComplexStrategyは複素数型をRuntimeへ露出しない。将来、同じtraitを実装する
外部アルゴリズムへ差し替え可能である。

### TransitionEngine

`(source, relation) -> target`規則を登録し、StableStateを遷移させる。

```text
Dog --IsA--> Mammal --IsA--> Animal
```

### TraceLogger

次を保持し、JSONへ出力できる。

```text
candidate_distribution
ambiguity_observation
selected_strategy
alternative_strategies
decision_reason
strategy_scores
confidence
policy_version
```

## 4. Specification Adjustment

原仕様のResolutionStrategyは常に`StableState`を返すが、
ClarifyStrategyは状態保留を行うため両立しない。

実装では次の結果型を導入した。

```rust
pub enum ResolutionOutcome {
    Resolved(StableState),
    Deferred {
        state: AmbiguousState,
        requested_evidence: String,
    },
}
```

これにより、確定していない状態をStableとして偽装せずに扱える。

## 5. Validation Results

| ID | Target | Result |
| --- | --- | --- |
| HRT-01 | HybridReasonUnit生成 | PASS |
| HRT-02 | State管理 | PASS |
| HRT-03 | Ambiguity観測 | PASS |
| HRT-04 | Decision実行 | PASS |
| HRT-05 | Identity解決 | PASS |
| HRT-06 | 状態遷移 | PASS |
| HRT-07 | Trace出力 | PASS |

追加でTraceLoggerの明示的record登録を検証した。

```text
8 passed
0 failed
```

## 6. Current Limitations

- 候補生成はRuntime外部の責務。
- 意味ベクトルは入力済みであることを前提とする。
- Clarifyは追加証拠要求を返すが、外部I/Oは実行しない。
- ComplexStrategyは最小の決定論的再評価であり、大規模複素推論ではない。
- Traceはメモリ保持とJSON出力のみで、永続化先は未実装。
- Transition規則はプロセスメモリ上に保持する。

これらはv0.2のExcluded Scopeと整合する。
