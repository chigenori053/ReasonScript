# ReasonScript Adaptive / Cost-Aware Constraint Fusion Report

- 対象仕様: [ReasonScript_Adaptive_Cost_Aware_Constraint_Fusion_v0_1.md](../specifications/ReasonScript_Adaptive_Cost_Aware_Constraint_Fusion_v0_1.md)（実装時の決定事項は同文書§134）
- 前提: [ReasonScript_Constraint_Fusion_v0_1.md](../specifications/ReasonScript_Constraint_Fusion_v0_1.md) / [Report](ReasonScript_Constraint_Fusion_Report.md)
- 比較対象: Model B（numerical wheel-6）、Model E（`constraint_fusion=off`）、Model F（`always`）、Model G（`adaptive`）
- データセット: Constraint Fusion v0.1と同一の117ケース（79 organic + synthetic 2Dマトリクス）
- 再現: `python3 scripts/benchmark_adaptive_fusion.py --samples 10 --out artifacts/adaptive_fusion_profile`
- 生成物: `artifacts/adaptive_fusion_profile/{comparison.csv, summary.json, graphs/*.png}`
- 計測日: 2026-09-19、Apple Silicon（macOS）、release build、runtime host boundary（`trace=off`, reasoning event mode `count`、warm-up 3回+本計測10回、中央値で判定）

## 1. 結論

| 完了判定 | 内容 | 判定 |
|---|---|---|
| 1 | 全結果一致（E == F == G） | **達成**（Mandatory）。117/117ケースで一致。 |
| 2 | 既知の最悪regressionケースでG<F | **部分達成**（Mandatory、厳密には未達）。3件中2件（`highly_composite_24b`: 103,563ns→32,521ns、`synthetic_sqrt1000000_k6`: 163,229ns→161,709ns）で改善したが、`synthetic_sqrt1000000_k8`（105,813ns→105,876ns）はほぼ無改善。 |
| 3 | 95%以上のケースでG<=1.10×E | **未達**（Target）。75%（116件中87件）。 |
| 4 | Fusion opportunityの利用（fusion_selected_count>0） | **達成**（Mandatory）。全体で118回選択。 |
| 5/6 | Reasoning-favorable region: G>=E、G>E | **未達**（Important/Target）。G favorable=29 < E favorable=32。 |
| 7 | Oracle Efficiency中央値>=0.9 | **達成**（Target）。0.988。 |
| 8 | RCR-RTER相関がModel Fより改善 | **達成**（Mandatory target）。r(F)=−0.360 → r(G)=−0.266。 |
| 9 | k=0,1でoverhead非支配（G<=1.05×E） | **達成**（Target）。該当ケース全てで規定内。 |

要約: **Adaptive Fusionは「Always Fusionの最悪の性能退行を大幅に緩和する」ことには明確に成功した**が、「Fusion無効時と同等以上の安全性を全ケースで保証する」ところまでは到達しなかった。中央値で見るとModel Gの実行時間（40,917ns）はModel Fの半分以下（92,500ns）であり、Oracle Efficiency中央値0.988という高い値は「典型的なケースではE/Fのうち良い方にほぼ匹敵する判断ができている」ことを示す。しかし一部の中〜大規模な合成ケース（特に`sqrt(N)`が10万〜100万で圧縮レベルk>=5の領域）では、コスト見積もりが依然としてAlways Fusionと同じ判断を下し続け、regressionが解消されなかった。原因はコスト見積もりが持つ本質的な視野の限界であり、§4で分析する。

## 2. 実施内容

| Phase | 実装 | 主な変更箇所 |
|---|---|---|
| Policy拡張 | `FusionPolicy { Off, Always, Adaptive }`。`context.constraint_fusion`は文字列（`"off"/"always"/"adaptive"`）と真偽値（後方互換）の両方を受理する。 | `candidate_space.rs`, `vm.rs`, `runtime-cli/src/main.rs` |
| Cost Estimator | `CandidateSpace::plan_fusion(p, budget) -> Result<FusionEstimate, FusionRejectReason>`。O(1)（residue走査なし）: `remaining_candidates`は密度ベース見積もり、`predicted_modulus`/`predicted_residue_count`はcoprimeなふるいの恒等式により厳密値を即座に算出。`FusionEstimate::should_fuse()`が`benefit×4 > cost×5`（FUSION_MARGIN=1.25）で判定。 | `candidate_space.rs` |
| VM統合 | `Added::Fused`/`Added::Stored`に`estimate: Option<FusionEstimate>`と`reject_reason: Option<FusionRejectReason>`を追加。`fusion_candidate_count`, `fusion_selected_count`, `fusion_rejected_cost_count`, `fusion_estimated_benefit_total`, `fusion_estimated_cost_total`, `fusion_score_total`をruntime_metricsへ追加。`FUSION_SELECTED`/`FUSION_REJECTED_COST`イベントを追加。 | `vm.rs` |
| Benchmark | `scripts/benchmark_adaptive_fusion.py`（B/E/F/G四方比較、117ケース）、`scripts/make_adaptive_fusion_graphs.py`（4グラフ）。 | `scripts/` |
| Tests | Rust単体テスト7件（tiny/large search space判断、off/always/adaptive一致、cost/budget/overflow reason区別、決定性、重複、cursor保存）、Python統合テスト7件。 | `candidate_space.rs`（テストモジュール）, `tests/runtime/test_adaptive_constraint_fusion.py` |

## 3. Cost Estimatorの数学的性質

`p`が現在のfused modulusと互いに素であるとき（本経路に到達する`p`は常にこの条件を満たす。すでにmodulusを割り切る`p`は§34の通り別経路で無条件にFuseする）、拡張後のresidue集合はふるいの乗法的性質により正確に

```text
predicted_residue_count = current_residue_count × (p - 1)
predicted_modulus = current_modulus × p
```

となる。これは近似ではなく、`FusedConstraintSet::try_fuse`が実際に構築・フィルタして得る値と厳密に一致する（例: wheel-6 (residues=2) + 5 → 2×4=8、+7 → 8×6=48。実測値と完全一致）。この部分にはO(1)の恒等式のみを用い、residueを一切走査しない。

唯一の近似は`remaining_candidates`である。正確な値は`unvisited_count()`（O(residue数)）が必要だが、これはEstimator用に禁止されているため（仕様§79）、現在の密度（`residue_count / modulus`）を`cursor`から`upper`までの残り区間長に乗じるO(1)推定を用いる。

## 4. 分析: なぜ一部のケースでAdaptiveがAlwaysと同じ判断をしてしまうのか

`remaining_candidates`の密度ベース見積もりは、CandidateSpaceの**静的なドメイン上限（`upper`）**を基準にしている。しかし本ベンチマークで使う素因数分解プログラム（`factorize_lazy_sieve_reasoning.rsn.template`）は、CandidateSpace自身の`upper`とは**別に**、ReasonScriptプログラム側の変数`remaining`（除算のたびに縮小する）を使って `if c * c > remaining { searching = false }` という形で独自に探索を打ち切る。この打ち切りタイミングはCandidateSpaceからは一切観測できない。

その結果、実際には数個の候補しかテストされずに探索が終わる状況でも、Cost Estimatorは「`upper`までの区間がまだ大量に残っている」という前提で`remaining_candidates`を計算し、`benefit`（`remaining`に比例）を過大評価してしまう。`synthetic_sqrt1000000_k8`（`sqrt(N)≈1,000,000`）を調べると、Model Gは4件のFusion候補全てを選択していた（`fusion_rejected_cost_count=0`）。これはAlways Fusionと完全に同じ判断であり、実際には8個ほどの候補しかテストされない探索に対して、`remaining_candidates`を数十万〜百万のオーダーで見積もってしまったことを意味する。

これは仕様§122が想定していた失敗条件D（「予測と実測の相関がほぼない。remaining candidate count/residue countだけでは不十分」）に正確に一致する。ヒートマップ（`graphs/rter_heatmap.png`）でも、`target=100,000〜1,000,000`かつ`k=5〜8`の領域だけが赤く（B比で不利に）残っており、他の領域（低k、または`target=10,000,000`のように候補数が実際に多いケース）では緑（有利）になっていることが視覚的に確認できる。

対照的に、`highly_composite_24b`（`sqrt(N)≈14,936`）ではFusion候補4件中1件を正しくコスト却下し、実行時間をModel Fの103,563nsから32,521nsまで改善できた——このケースでは相対的に候補数が少なく密度推定の誤差が判断を覆すのに十分だったためと考えられる。

## 5. 好意的に見た場合の成果

- **中央値ベースでは明確な改善**: 全117ケースの中央値実行時間はE=31,729ns、F=92,500ns、G=40,917nsであり、GはFの2.26倍高速、Eからの乖離もわずか1.29倍にとどまる。
- **Oracle Efficiency**: `best(E,F)/G`の中央値は0.988。これは「典型的なケースでは、Adaptive判断は事後的に最良と分かる選択にほぼ匹敵している」ことを意味する（仕様§66-67の目標0.9を上回る）。
- **相関の改善**: RCR-RTER相関はModel Fの−0.360からModel Gの−0.266へ改善した（仕様§63の最低条件`r_G > r_F`を満たす。ただし`r_G >= 0`という次の目標は未達）。
- **保守的な安全域（k=0,1）は完全維持**: 圧縮対象の制約が0〜1件しかない場合、Adaptiveのオーバーヘッドは無視できるレベルにとどまり、regressionは1件も発生しなかった。

## 6. Reasoning-favorable Regionの変化

Model B比でRTER>1となるケース数はE=32、F=29、G=29（`artifacts/adaptive_fusion_profile/summary.json`）。Gで新たに有利になった2ケース（`basic_97`, `semiprime_8b`）に対し、Eでは有利だったがGでは失われた5ケース（`synthetic_sqrt10000000_k8`, `synthetic_sqrt1000000_k6`, `synthetic_sqrt100000_k4/k5`, `synthetic_sqrt10000_k3`）が存在し、差し引きでGはEよりわずかに狭い（完了判定5/6未達）。これらの「失われた」ケースはいずれも§4で分析した密度推定バイアスの影響を受ける中間規模の合成ケースである。

## 7. Regression / Determinism

- Fusion無効時（デフォルト）: 既存の96テスト（`test_candidate_*.py`, `test_constraint_fusion.py`）が完全に不変のまま合格することを確認した。
- Rust単体テスト36件全て合格（Adaptive関連7件を含む）。
- 決定性: `test_adaptive_constraint_fusion.py::test_adaptive_determinism_across_runs_and_fast_path_modes`で3回実行およびFast Path有無の完全一致を確認。
- `RTH-PROTO-006`: 未知の`constraint_fusion`値（文字列）に対する診断を追加し、テストで確認。
- 本変更はcandidate_space.rs/vm.rs/main.rs、および`frontend/computation_ir/rust_bridge.py`の型ヒント更新のみで、IRスキーマ・フロントエンドの検証ロジックは変更していない。

## 8. 成果物

- `docs/specifications/ReasonScript_Adaptive_Cost_Aware_Constraint_Fusion_v0_1.md`
- `docs/reports/ReasonScript_Adaptive_Cost_Aware_Constraint_Fusion_Report.md`（本書）
- `ReasonRuntime/crates/computation-ir/src/{candidate_space.rs, vm.rs}`, `runtime-cli/src/main.rs`, `lib.rs`
- `frontend/computation_ir/rust_bridge.py`
- `scripts/benchmark_adaptive_fusion.py`, `scripts/make_adaptive_fusion_graphs.py`
- `tests/runtime/test_adaptive_constraint_fusion.py`
- `artifacts/adaptive_fusion_profile/{comparison.csv, summary.json, graphs/*.png}`

## 9. 次段階

- **`remaining_candidates`推定の改善（最優先）**: §4で特定した通り、現在の推定はCandidateSpaceの静的な`upper`しか見ておらず、プログラム側の動的な打ち切り条件（本ケースでは`remaining`変数の縮小）を捉えられない。改善案:
  - 直近の`generate_next`呼び出し間隔（前回のFusion以降に実際何個の候補が生成されたか）から実測的に密度を補正する適応的推定（仕様§47「将来のHardware-aware Mode」とは別に、実行履歴ベースの補正は本仕様の範囲内で検討可能）。
  - `MIN_REMAINING_FOR_FUSION`（仕様§72-73）に加えて、直近のFusion呼び出し頻度が高い（＝factorが頻繁に見つかっている＝探索がまだ浅い段階）ことを考慮したヒューリスティックの追加。
- 仕様§75-77のRebuild-Amortization Ratio（RAR）を実際に導入し、単純な閾値よりも精緻な判断へ発展させる。
- Fusion Selection Precision/Recall（仕様§68-69）を`fusion_decisions[]`のper-decisionトレース（debug/profileモード限定、仕様§38）と組み合わせて正式に計測できるようにする。
