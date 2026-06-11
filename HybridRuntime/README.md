# HybridRuntime v0.2

ReasonScriptの状態遷移型推論Runtime。

## Components

- `StateManager`
- `AmbiguityEvaluator`
- `DecisionEngine`
- `IdentityResolver`
- `RealStrategy`
- `ClarifyStrategy`
- `ComplexStrategy`
- `TransitionEngine`
- `TraceLogger`
- `ReasonGraph`
- `ReasonGraphRuntime`
- `GraphTraceLogger`

## Minimal Flow

```rust
use reasonscript_hybrid_runtime::{
    Candidate, Evidence, HybridReasonUnit, HybridRuntime, State,
};

let state = State::ambiguous(
    vec![
        Candidate::new("Dog", 0.95, vec![0.9, 0.9]),
        Candidate::new("Wolf", 0.05, vec![0.9, 0.8]),
    ],
    vec![Evidence::supported("Domestic", vec![0.95, 0.05])],
);

let mut runtime = HybridRuntime::new(HybridReasonUnit::new(state));
let outcome = runtime.resolve_identity()?;
# Ok::<(), reasonscript_hybrid_runtime::RuntimeError>(())
```

## Decision Policy

v0.2は単一の曖昧度スコアや単純閾値を使用しない。
`DecisionEngine`は各戦略の期待コストを計算し、最小コストの戦略を選択する。

`RiskPolicy`により誤決定、矛盾、未対応証拠、追加確認、複雑処理のコストを変更できる。

## Clarify Outcome

ClarifyはIdentityを確定しないため、戦略結果は常に`StableState`ではなく、
次のいずれかを返す。

```rust
pub enum ResolutionOutcome {
    Resolved(StableState),
    Deferred {
        state: AmbiguousState,
        requested_evidence: String,
    },
}
```

## Validation

```text
cargo test --offline
```

HRT-01からHRT-07を`tests/hrt_v02.rs`で検証する。

ReasonGraph Phase 0のRG-01からRG-14は
`tests/reason_graph_validation.rs`で検証する。

```text
cargo test --offline --test reason_graph_validation
```

検証結果の詳細は
`../docs/ReasonGraph_Validation_Phase_0_Report.md`を参照。
