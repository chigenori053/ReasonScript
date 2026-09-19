# ReasonScript Constraint Fusion Report

- 対象仕様: [ReasonScript_Constraint_Fusion_v0_1.md](../specifications/ReasonScript_Constraint_Fusion_v0_1.md)（実装時の決定事項は同文書§86）
- 前提: [ReasonScript_Lazy_Symbolic_Candidate_Space_v0_1.md](../specifications/ReasonScript_Lazy_Symbolic_Candidate_Space_v0_1.md) / [ReasonScript_Reasoning_to_Resource_Efficiency_Test_v1_0.md](../specifications/ReasonScript_Reasoning_to_Resource_Efficiency_Test_v1_0.md)
- 比較対象: Model B（numerical wheel-6）、Model E（lazy CandidateSpace, `constraint_fusion=false`）、Model F（同じテンプレートを `constraint_fusion=true` で実行したもの）
- データセット: 既存104ケース（79 organic + 25 synthetic）に、search space target `10,000,000` と圧縮レベル `k=5` を追加した117ケース
- 再現: `python3 scripts/benchmark_constraint_fusion.py --samples 10 --out artifacts/constraint_fusion_profile`
- 生成物: `artifacts/constraint_fusion_profile/{comparison.csv, summary.json, graphs/*.png}`
- 計測日: 2026-09-19、Apple Silicon（macOS）、release build、runtime host boundary（`trace=off`, reasoning event mode `count`、warm-up 3回+本計測10回、中央値で判定）

## 1. 結論

| 完了判定 | 内容 | 判定 |
|---|---|---|
| A | 全結果一致（Model E == Model F） | **達成**。117/117ケースで一致。 |
| B | Hypothesis sequence一致 | **達成**（`tests/runtime/test_constraint_fusion.py::test_fusion_hypothesis_sequence_matches_non_fused` で個別検証）。 |
| C | k>=4でconstraint_eval_count_F < constraint_eval_count_E | **達成**。k>=4の8ケース全てで削減（中央値FER=4.92倍）。 |
| D | k>=6でPOR_F_B（VM instruction比）がPOR_E_Bより改善 | **未達**。k>=6の8ケース中0件で改善。 |
| E/F | target=1,000,000のk=6,8でModel FがModel Eより高速、かつRTER_F_B>1 | **未達**。両ケースともFRR<1（Fの方が遅い）、RTER_F_B<1（Bの方が速い）。 |
| G | RCR-RTER相関がModel Eより改善（目標r>=0.3、最終目標r>=0.5） | **未達**。r(E)=0.196 → r(F)=−0.381（悪化）。 |

要約: **Constraint Fusionは「物理的な制約評価回数」の削減には明確に成功したが（Level A/B/C達成）、それが「実行時間の短縮」には結びつかなかった（Level D/E/F/G未達）**。原因は、Fusionが実際に統合を行うたびに支払う「Generator再構築コスト」（O(現在のresidue数)）が、本ベンチマークで使用した候補数の少ない問題（highly_composite系、および人工的な高圧縮ケース）では償却されないためである。探索範囲が非常に大きい問題（sqrt(N)=1,000万など）ではこのコストは償却され、FがEを上回る場合もある。この結果は仕様§27の失敗条件そのものであり、「制約を減らす」設計が「制約統合コスト」という新たな支配的コストに置き換わっただけ、という重要な知見を与える。

## 2. 実施内容

| Phase | 実装 | 主な変更箇所 |
|---|---|---|
| Core | `FusedConstraintSet { modulus, residues: Rc<Vec<i64>> }`。Wheel6/Rangeの既存stepping規則も統一表現へ移行（`Generator::next_after`を廃止し、`FusedConstraintSet::next_after`の二分探索方式に一本化）。 | `candidate_space.rs` |
| Fusion判定 | `Constraint::Modulo{Ne,0}` かつ `is_small_prime(m)` の場合のみ`try_fuse`を試みる。LCM計算は`i128`でoverflow検出。`FusionBudget{max_modulus:30030, max_residue_count:30030}`を超える場合は`residual_constraints`へfallback。 | `candidate_space.rs` `add`, `try_fuse`, `would_fuse` |
| VM統合 | `context.constraint_fusion`（デフォルト`false`）を`Vm`に追加。`candidate_with_constraint`でFused/Fallbackを判定し、`CONSTRAINT_FUSED`/`GENERATOR_REBUILT`/`FUSION_FALLBACK`イベントとメトリクスを発行。 | `vm.rs`, `runtime-cli/src/main.rs` |
| Metrics | `constraint_fusion_count`, `constraint_fusion_rebuild_count`, `fusion_fallback_count`, `fused_modulus`, `fused_residue_count`, `fused_constraint_count`, `residual_constraint_count` を`runtime_metrics`へ追加。 | `vm.rs` |
| Model F | 新規テンプレート追加なし。`factorize_lazy_sieve_reasoning.rsn.template`を`constraint_fusion=true`で実行するのみ。 | なし（既存テンプレート再利用） |
| Benchmark | `scripts/benchmark_constraint_fusion.py`（B/E/F三方比較、117ケース）、`scripts/make_constraint_fusion_graphs.py`（4グラフ）。 | `scripts/` |
| Tests | Rust単体テスト9件（fusion成功/順序不変/重複/cursor保存/overflow・budget fallback/合成数residual/fusion無効時の完全一致）、Python統合テスト7件。 | `candidate_space.rs`（テストモジュール）, `tests/runtime/test_constraint_fusion.py` |

## 3. 実装過程で発見・修正した2つの性能バグ

最初の実装（`FusedConstraintSet::residues: Vec<i64>`をそのまま`CandidateSpace`にvalueで持つ）をk=8の合成ケースでベンチマークしたところ、**Model FがModel Eより5.8倍遅い**という結果になった。原因を2段階で特定・修正した。

### 3.1 `CandidateSpace::clone()`のO(residue数)化

`CandidateSpace`は`relation.filter`/`exclude_multiples_of`のたびに`space.borrow().clone()`で新しいイミュータブルなハンドルを作る設計（ArrayBuilderと同様の永続データ構造）。`residues: Vec<i64>`をvalueで持つと、modulusが30,030（residue数5,760）まで成長した**後**の全ての`relation.filter`呼び出し（fusionが成功してもbudget超過でfallbackしても関係なく）が、5,760要素のVecを毎回ディープコピーしていた。**修正**: `residues`を`Rc<Vec<i64>>`でラップし、clone自体をO(1)にした（`allocated_bytes`が255,655→67,087バイトへ減少）。

### 3.2 `unvisited_count()`の不要呼び出し

`candidate_symbolically_excluded_count`メトリクス（正確な除外数）を計算するため、制約追加のたびに`unvisited_count()`（residue数に比例するO(R)計算、`i128`除算をresidue数回行う）を呼んでいた。当初はこれを**制約の種類やFusionの成否に関わらず毎回**呼んでいたため、budget超過でfallbackするだけの呼び出しでも、既に大きくなったresidue集合に対するO(R)計算を無駄に払っていた。**修正**: `FusedConstraintSet::would_fuse()`（O(1)のLCM+budget事前判定、residuesに触れない）を追加し、実際にFusionが成立する可能性がある場合のみ`unvisited_count()`を呼ぶよう変更した。

この2つの修正で、k=8ケースの実行時間は225,875ns→123,333ns（約1.8倍改善）まで縮小したが、それでもModel Eの41,542nsと比べると約3倍遅いままだった（§4参照）。

## 4. 残存する性能特性: なぜFusionは「遅い」ままなのか

2つのバグを修正した後も、**Fusionが実際に成立するたびに支払う「Generator再構築コスト」自体（`try_fuse`のO(residue数)ループ、`unvisited_count()`の前後2回のO(residue数)呼び出し）は本質的に必要なコスト**であり、これはmodulusがbudget上限（30,030、residue数5,760）に達するまでの4〜6回の統合で合計約2〜3万回のi128演算を要する。この固定コストは、

```text
Fusion Rebuild Cost（固定、〜数十µs）
vs
Search Reduction Benefit（候補数削減、探索が大きいほど大きい）
```

というトレードオフになり、**候補数が少ない問題ではRebuild Costが支配的**になる。これは仕様§25が最初から想定していた構造（"Fusion Benefit > Fusion Rebuild Cost である場合にのみFusionする設計を将来的に検討する"）そのものであり、v0.1では単純な閾値（FusionBudget）のみを実装し、コストモデルに基づく動的な有効化判定は実装していないため、この非対称性がそのまま観測される。

### 4.1 ヒートマップ（synthetic、探索範囲×圧縮レベル、RTER_F_B）

`graphs/rter_heatmap.png` より（緑=Fが高速、赤=Bが高速）:

| k \\ target | 1,000 | 10,000 | 100,000 | 1,000,000 | 10,000,000 |
|---|---|---|---|---|---|
| 0 | 0.82 | 0.81 | 0.81 | 0.81 | 0.80 |
| 1 | 0.92 | 0.98 | 0.99 | 1.00 | 1.00 |
| 2 | 0.90 | 1.06 | 1.13 | 1.12 | 1.16 |
| 3 | 0.64 | 0.96 | 1.16 | 1.22 | 1.25 |
| 4 | 0.17 | 0.27 | 0.77 | 1.24 | 1.33 |
| 5 | 0.17 | 0.19 | 0.42 | 1.02 | 1.34 |
| 6 | — | 0.17 | 0.23 | 0.63 | 1.27 |
| 8 | — | — | 0.19 | 0.19 | 0.39 |
| 10 | — | — | — | — | 0.20 |

対角線状に「探索範囲が大きいほど、より高いkでもFusionが有利になる」という明確なパターンが見える。k=4は探索範囲100万以上で有利（1.24〜1.33倍）だが、k=8になると1,000万でもまだ不利（0.39）。**k=10のような極端な圧縮レベルでは、本ベンチマークで扱った範囲（sqrt(N)最大1,000万）ではFusionのメリットは一度も実現しなかった**。

### 4.2 既存79ケース（organic）への影響

`highly_composite`系（多数の小因数を持つ実際の合成数）は、この問題に該当する代表例である。`highly_composite_24b`ではModel D比では圧倒的優位（[Lazy Candidate Spaceレポート](ReasonScript_Lazy_Symbolic_Candidate_Space_Report.md)参照）だが、Model B比・Fusion適用では：constraint_eval_countは21→3に削減（Level C相当）されたにもかかわらず、RTER_F_B=0.18（Model Fの方が5.5倍遅い）、FRR=0.22（Model Eの方が4.5倍速い）という結果になった。これはhighly_compositeクラスの絶対候補数が小さい（wheel-6テスト回数は8bitで3、24bitでも13）ため、Fusionの固定コストが償却されないことを示す。

一方、organicデータセット全体（79ケース）の中央値ではRTER_E_B=0.819、RTER_F_B=0.804、FRR=0.982とほぼ同等（Fusionが有効になるほどconstraint数が多い実データが少ないため、影響は限定的）。`basic_997`（k=0相当、Fusion対象の制約が存在しない）はFRR=1.020とわずかにFが有利で、Fusionが不要な場面でのオーバーヘッドがほぼゼロであることも確認できた（完了判定「k=0,1での性能regressionなし」は達成、§6参照）。

## 5. Reasoning-favorable Regionの変化

Model B比でRTER>1（EまたはFがBより高速）となる領域を比較すると:

- Eで有利だがFusionで失われたケース（`lost_by_fusion`）: `synthetic_sqrt1000000_k6`, `synthetic_sqrt10000000_k8`, `synthetic_sqrt100000_k1/k4/k5`, `synthetic_sqrt10000_k3`, `mixed_20b` の7件。
- Fusionで新たに有利になったケース（`gained_by_fusion`）: `basic_997`, `synthetic_sqrt1000000_k1`, `synthetic_sqrt10000000_k1` の3件（いずれもFusionがほぼ発生しない/1回だけのケース）。

差し引きで**Reasoning-favorable regionはFusionによって縮小した**（完了判定E「拡大」は不成立）。

## 6. Regression / Determinism

- Fusion無効時（デフォルト）: 既存の`tests/runtime/test_candidate_*.py`（82テスト）が完全に不変のまま合格することを確認した（`Generator::next_after`を`FusedConstraintSet`ベースの統一実装に置き換えたが、単体テスト`fused_set_matches_generator_stepping_exactly`で新旧実装が全域で一致することを検証済み）。
- k=0, k=1（Fusion対象の制約が0〜1件）での性能regression: `performance_regression_k0_k1`は`pass: true`（`runtime_F <= 1.05 x runtime_E`を全ケースで満たす）。
- 決定性: `tests/runtime/test_constraint_fusion.py::test_fusion_determinism_across_runs_and_fast_path_modes`で3回実行およびFast Path有無の完全一致を確認。
- Constraint順序不変性: `test_fusion_is_order_invariant`（`p,q`の追加順序を入れ替えても同じ結果）で確認。Rust単体テスト`fusion_is_order_invariant`でも同様に確認。
- `./reason ci`相当のリグレッション: 本変更はcandidate_space.rs/vm.rs/main.rsのみで、フロントエンド・IRスキーマは変更していない。`cargo test -p reasonscript-computation-ir`（29件）、`pytest tests/runtime`（89件）が全てPASS。

## 7. 成果物

- `docs/specifications/ReasonScript_Constraint_Fusion_v0_1.md`
- `docs/reports/ReasonScript_Constraint_Fusion_Report.md`（本書）
- `ReasonRuntime/crates/computation-ir/src/{candidate_space.rs, vm.rs}`, `runtime-cli/src/main.rs`
- `frontend/computation_ir/rust_bridge.py`（`constraint_fusion`パラメータ追加）
- `scripts/benchmark_constraint_fusion.py`, `scripts/make_constraint_fusion_graphs.py`
- `tests/runtime/test_constraint_fusion.py`
- `artifacts/constraint_fusion_profile/{comparison.csv, summary.json, graphs/*.png}`

## 8. 次段階（仕様§82・§4のトレードオフを踏まえて）

- **Adaptive / Cost-aware Fusion**: 現在は「Fusion可能なら常にFusionする」設計。仕様§25が示唆する通り、探索範囲の推定値（`candidate_space_estimated_size`は生成時に既知）が小さい場合はFusionを見送り、residualのまま評価する方が有利な場合がある。generator推定サイズに基づく閾値（例: 見積り候補数がFusion rebuild costの償却に必要な最小値を下回ればFusionしない）を追加することで、Level D/F/Gの再挑戦が可能と考えられる。
- **Rebuild costそのものの削減**: 現在の`try_fuse`はresidue集合を毎回ゼロから再構築する（O(新residue数)）。差分更新（既存residueのうち`p`の倍数だけを除去する、というO(旧residue数)の操作で済む）や、residueをbitset（`FixedBitSet`等）で持つことで再構築定数を下げられる可能性がある。
- **`unvisited_count()`の呼び出し回数削減**: 現状、Fusion成功時に前後2回のO(R)呼び出しを払っている。`try_fuse`の内部で除外数を直接カウント（フィルタ処理と同時に集計）すれば、追加の呼び出しなしに正確な`excluded`値を得られる。
- 本レポートの結果は、v0.1仕様が課題として認識していた「Fusion Benefit > Fusion Rebuild Cost」という条件が現実に成立しない領域が広いことを実証した。次の反復では、Fusionを「常に適用する最適化」ではなく「条件付きで適用するコストベース最適化」として再設計する必要がある。
