# ReasonScript P0 Runtime Performance Improvement Specification v1.0

## 1. 文書情報

- 文書名: ReasonScript P0 Runtime Performance Improvement Specification
- バージョン: v1.0
- 対象: ReasonScript Runtime / ReasonRuntime / Computation IR / Reasoning Runtime
- 策定日: 2026-09-18
- 優先度: P0
- 目的: ReasonScriptにおける推論圧縮を、実際の実行時間・計算資源削減へ接続するためのRuntime基盤改善

実装結果は [docs/reports/ReasonScript_P0_Runtime_Performance_Report.md](../reports/ReasonScript_P0_Runtime_Performance_Report.md) に記録する。

## 2. 背景

ReasonScript_SpecTestにおける素因数分解性能検証では、ReasonScript v0.5.5.15までに以下が確認された。

v1.3では、`relation.filter(rows, predicate)`、`array.builder()`、`reasoning.event()` 等の追加により、実行時に獲得した証拠を用いて探索候補を動的に削減する、Evidence-driven Dynamic Pruningが成立した。代表例では、静的なwheel-6探索空間が2,032候補である問題に対して、実際のHypothesis Testを8回まで削減できた。

したがって、ReasonScriptが状態・証拠・仮説を用いて探索空間を圧縮できることについては一定の実証が得られている。

一方で、論理的な探索量を大幅に削減した場合でも、ReasonScriptのwall timeは単純なwheel-6実装より1.03〜3.4倍程度大きく、Rust実装との差も依然として大きい。また、ReasonRuntimeには10,000回の固定loop iteration limitが存在し、アルゴリズム上は継続可能な処理であっても `RT-LOOP-001` により強制終了する。

したがって現在の主要課題は、推論能力そのものではなく、推論処理1ステップを実行するRuntimeコストにある。本仕様では、この問題をP0として修正する。

## 3. 修正対象

- P0-1 Reasoning Runtime単位コスト削減: `reasoning.event`、`relation.filter`、`relation.count`、Array / Struct access、Predicate evaluation、Reason state更新、VM instruction dispatch、Intermediate Value生成、Runtime内部allocation について、1 Reasoning Step当たりの実行コストを削減する。
- P0-2 固定10,000 loop limitの廃止: `DEFAULT_MAX_LOOP_ITERATIONS = 10_000` による固定制御を廃止または縮退し、Execution Budgetによる制御へ変更する。
- P0-3 Reasoning Primitive Dispatch最適化: Reasoning処理が通常の算術演算と比較して過大なRuntime dispatchを発生させている問題を改善する。

## 4. 修正目標

「推論ステップを減らした場合に、実際の計算時間または計算資源も減るRuntime」を最終目標とする。重要なのは、

```text
Reasoning Compression
        ↓
Executed Operations Reduction
        ↓
Runtime Cost Reduction
```

という関係を成立させることである。本修正では絶対速度のみではなく、推論圧縮率とRuntimeコストの相関を主要評価対象とする。

## 5. 非目標

新しい数学アルゴリズムの追加、DSNアルゴリズム本体の変更、MIRPの機能拡張、RU/RUS/RUO言語仕様全体の再設計、JIT Compilerの本格導入、LLVM Backendの導入、GPU Runtimeの導入、Cluster Runtimeの性能改善、分散推論の実装、新しいDSL Syntax追加は行わない。本フェーズではRuntime内部改善に限定する。

## 6. P0-1 Reasoning Runtime単位コスト削減

ReasonScript v0.5.5.15のSpecTestでは、探索候補数を削減してもwall time削減に結びついていない。推定される主要コストは VM dispatch → Array indexing → relation dispatch → predicate evaluation → reasoning.event → state/event creation → trace handling であり、複数のRuntime層を1 Reasoning Stepごとに通過するため、論理演算そのものより管理処理の割合が大きくなっている可能性がある。

## 7. Runtime Native Counter導入

最適化前に、Runtime内部コストを計測可能にする。以下をRuntime native counterとして追加する。

```text
vm_instruction_count, reasoning_step_count, reasoning_event_count,
relation_dispatch_count, relation_filter_count, relation_filter_rows_scanned,
relation_predicate_eval_count, relation_count_count,
array_read_count, array_write_count, struct_field_read_count, struct_field_write_count,
allocation_count, allocated_bytes, state_transition_count, branch_count, loop_iteration_count
```

可能な場合は `runtime_execution_ns`, `predicate_execution_ns`, `relation_execution_ns`, `reasoning_event_ns`, `trace_execution_ns`, `allocation_ns` も追加する。時間計測そのものが性能に影響する場合、`--profile-runtime` 指定時のみ有効化し、通常実行時には無効とする。

## 8. Counter出力形式

JSON出力の `runtime_metrics` に追加する。Counter値は推定ではなく、Runtime内部から直接取得する。

## 9. Fast Path導入

頻出するReasoning Primitive（`relation.count`、array index read、array length、numeric comparison、modulo predicate、boolean predicate、`reasoning.event`）について、汎用dispatchを回避するFast Pathを追加する。

## 10. relation.count最適化

`relation.count(Array<T>)` を `ARRAY_LEN` へloweringする。結果は従来実装と完全一致、Determinism維持、Observable semanticsを変更しない、relation API自体は維持可能、を要件とする。

## 11. Predicate Execution最適化

`field == value`, `field != value`, `field < value`, `field <= value`, `field > value`, `field >= value`, `field % value == 0`, `field % value != 0` について専用IRへのloweringを許可する（例: `candidate.value % factor != 0` → `FILTER_MOD_NE`）。ユーザー向けSyntaxは変更しない。

## 12. reasoning.event最適化

イベント処理を OFF（イベントオブジェクトを生成しない）/ COUNT（イベント種別とcounterのみ保持）/ FULL（現在と同等の詳細イベント）の3モードへ分離する。デフォルトはCOUNTを推奨し、完全な推論過程を取得する場合のみFULLを使用する。

## 13. Event Lazy Materialization

FULLモードを除き `ReasoningEvent Object` を毎回生成しない。COUNTモードでは `reasoning_event_count += 1; event_type_count[type] += 1` のみ実行し、必要になるまで subject / evidence / affected_entities の構造を生成しない。

## 14. P0-2 Execution Budget設計

`DEFAULT_MAX_LOOP_ITERATIONS = 10_000` によりRuntimeが固定的に停止する。この制約は安全機構としては有用だが、問題規模やアルゴリズムによらず同じ値が適用されるため、推論モデルの能力上限そのものになっている。

## 15. Execution Budget導入

固定loop limitを `ExecutionBudget`（`max_loop_iterations`, `max_reasoning_steps`, `max_vm_instructions`, `max_wall_time_ms`, `max_allocated_bytes`）へ置換する。将来的拡張候補: `max_branch_count`, `max_relation_scans`, `max_state_transitions`, `max_hypotheses`。

## 16. Budgetの優先順位

1. explicit cancellation
2. wall-time budget
3. memory budget
4. VM instruction budget
5. reasoning-step budget
6. loop iteration budget

停止理由を明確に区別する。

## 17. Error Code

既存の `RT-LOOP-001` は互換性のため残してよい。新規に `RT-BUDGET-001`（Wall Time）、`RT-BUDGET-002`（Memory）、`RT-BUDGET-003`（VM Instruction）、`RT-BUDGET-004`（Reasoning Step）、`RT-BUDGET-005`（Loop Iteration）を定義する。Runtime終了結果には `termination_reason` を必ず出力する。

## 18. デフォルト設定

10,000 loop固定上限を削除し、単純に上限値を増加させるのではなく、Execution Budgetを主制御とする。loop limitは無限loop防止用の補助安全制約として扱う。

```text
reason run program.rsn --max-reasoning-steps 100000 --max-wall-time-ms 30000
```

設定ファイル対応も許可する。

## 19. P0-3 Dispatch最適化

実行パスを Generic Path（既存互換性を維持）と Fast Path（頻出かつ型が確定したprimitive）に分離する。

## 20. Fast Path適用条件

型がcompile/semantic analysis時に確定、operation semanticsが静的に確定、side effectが限定的、provenance/evidence semanticsを破壊しない、deterministic resultを保証できる場合のみFast Pathを使用し、条件を満たさない場合はGeneric Pathへfallbackする。

## 21. Computation IR拡張候補

内部命令として `ARRAY_LEN`, `ARRAY_GET_FAST`, `STRUCT_GET_FAST`, `FILTER_MOD_EQ`, `FILTER_MOD_NE`, `FILTER_COMPARE`, `REASON_EVENT_COUNT`, `STATE_TRANSITION_FAST` を追加してよい。外部ReasonScript Syntaxには露出させない。

## 22. Allocation削減

Runtime Profileによりallocationが主要コストであることが確認された場合、Temporary Value再利用、Small Value stack allocation、Event object lazy creation、Array builder reuse、Predicate context reuse、immutable cloneの削減、reference-counted valueの不要clone削減を実施する。意味論を変更するようなin-place mutationは原則禁止する。

## 23. Traceとの分離

`--trace=off` / `--trace=summary` / `--trace=delta` / `--trace=full` を分離する。Performance Benchmarkの標準は `trace=off`、Reasoning correctness verificationでは `trace=delta` を標準とする。

## 24. 性能検証方法

ReasonScript_SpecTest v1.3の同一データセットを再利用し、Model A（Rust baseline）、Model B（ReasonScript wheel-6）、Model D（ReasonScript sieve-reasoning）を比較する。アルゴリズムは変更せず、変更可能なのはRuntimeのみとする。

## 25. 必須計測値

`wall_time_ms`, `cpu_time_ms`, `peak_memory_mb`, `reasoning_step_count`, `hypothesis_test_count`, `candidate_pruned_count`, `vm_instruction_count`, `relation_dispatch_count`, `predicate_eval_count`, `allocation_count`, `allocated_bytes`, `trace_bytes`, `termination_reason`。

## 26. 新規評価指標

- Reasoning Efficiency Ratio: `RER = baseline_candidate_tests / reasoning_step_count`
- Runtime Cost per Reasoning Step: `RCRS = runtime_execution_time / reasoning_step_count`
- Compression-to-Time Efficiency: `CTE = search_compression_ratio / wall_time_ratio`（CTE > 1 を推論圧縮がRuntime overheadを上回った指標とする）
- Physical Operations per Semantic Step: `POS = vm_instruction_count / reasoning_step_count`

## 27. 成功基準

- Level P0-A（必須）: 10,000固定loop limitによる不必要な停止が解消する。
- Level P0-B（必須）: Model Dの結果・推論イベント・candidate pruning結果が修正前と一致する。
- Level P0-C（目標）: Model Dのwall timeが修正前より20%以上低下する。
- Level P0-D（重要目標）: Model Dが同一ReasonScript上のwheel-6と同等以下のwall timeを1ケース以上で達成する。
- Level P0-E（主要成功条件）: 探索圧縮率が高いケースほどwall time改善率も高くなる正の相関が確認される。
- Level P0-F（最終成功条件）: ReasonScriptの推論圧縮が、同一Runtime上の非推論アルゴリズムに対して実時間上も明確な優位性を示す。

Rustより高速であることは本フェーズの必須条件としない。

## 28. Regression条件

既存ReasonScriptコードの動作、Deterministic result、同一入力に対する同一出力、relation / array / predicate semantics、reasoning event ordering、error diagnostics、JSON API compatibility をすべて維持する。Fast PathとGeneric Pathで結果差異があってはならない。

## 29. Determinism Test

各主要テストを最低3回実行し、output、reasoning event sequence、state transition sequence、candidate pruning count、termination reason、canonical hash を比較する。時間・memory値は一致要件から除外する。

## 30. 実装フェーズ

P0-1 Measurement → P0-2 Loop Budget → P0-3 Low-risk Fast Path（`relation.count`, `array.length`, array indexing, simple comparison）→ P0-4 Predicate Fast Path → P0-5 Reason Event Optimization → P0-6 Allocation Optimization → P0-7 SpecTest Re-validation。

## 31. 実装優先順位

1. Native counters
2. Execution Budget
3. relation.count Fast Path
4. Array/Struct access Fast Path
5. Predicate Fast Path
6. reasoning.event lightweight mode
7. Allocation reduction
8. Trace separation
9. Full SpecTest rerun

測定なしで先に大規模最適化することは禁止する。

## 32. 成果物

```text
docs/specifications/ReasonScript_P0_Runtime_Performance_v1_0.md
docs/reports/ReasonScript_P0_Runtime_Performance_Report.md
artifacts/runtime_profile/baseline.json
artifacts/runtime_profile/optimized.json
artifacts/runtime_profile/comparison.csv
tests/runtime/ (execution budget, reasoning counters, fast path equivalence, reasoning event modes)
```

## 33. 完了条件

1. Runtime native metricsが取得可能
2. 固定10,000 loop limitに依存しない
3. Execution Budgetが動作する
4. Fast PathとGeneric Pathが意味的に同値
5. Model Dの推論結果が修正前と一致
6. Determinismが維持される
7. wall timeが修正前より改善
8. P0改善レポートが生成される
9. ReasonScript_SpecTestの再現データが保存される
10. 既存テストにRegressionがない

## 34. P0修正後の判断

- ケースA: Reasoning steps ↓ / Runtime cost ↓ — ReasonScriptの設計仮説を支持し、DSN等の上位モデル検証へ進む。
- ケースB: Reasoning steps ↓ / Runtime cost ≈ — さらなるRuntime最適化をP1として継続する。
- ケースC: Reasoning steps ↓ / Runtime cost ↑ — Reasoning representationそのもののRuntime実装を再検討する。
- ケースD: Fast Pathを導入してもVM dispatchが支配的である場合、AOT / Bytecode / Native execution への移行を次フェーズ候補とする。

## 35. 最終目標

本P0修正の目的は単純なベンチマーク高速化ではない。少ない推論過程によって高い推論能力を実現し、必要な計算資源そのものを削減するという設計仮説をRuntimeレベルで成立させることを目的とする。現在のSpecTestでは Search-space compression までは確認された。P0修正では次段階として Search-space compression → Physical operation reduction → Runtime resource reduction まで成立するかを検証する。
