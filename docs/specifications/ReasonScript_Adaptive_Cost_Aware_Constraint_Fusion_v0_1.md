# ReasonScript Adaptive / Cost-Aware Constraint Fusion v0.1 Specification

## 1. 文書情報

- 文書名: ReasonScript Adaptive / Cost-Aware Constraint Fusion v0.1 Specification
- バージョン: v0.1
- 対象: ReasonScript CandidateSpace / Constraint Fusion / Reasoning Runtime / Runtime Optimizer
- 前提仕様: Lazy / Symbolic Candidate Space v0.1、Constraint Fusion v0.1、Reasoning-to-Resource Efficiency Test v1.0
- 優先度: P0後続 / Runtime Resource Optimization
- 目的: Constraint Fusionを常時適用するのではなく、予測される削減効果とFusion再構築コストを比較し、Fusion / Residual Constraintのどちらを採用するかをRuntimeが動的に選択する。
- 実装レポート: [ReasonScript_Adaptive_Cost_Aware_Constraint_Fusion_Report.md](../reports/ReasonScript_Adaptive_Cost_Aware_Constraint_Fusion_Report.md)（実装時の決定事項と実測結果は同文書、特に§7）。

## 2-3. 背景・前工程で確認された問題

Constraint Fusion v0.1では、Fusion可能なConstraintに対して原則Fusionを実行する。この判断にはremaining search size / expected exclusion / rebuild cost / future constraint evaluationsが考慮されておらず、探索対象が10件しか残っていない場合でも数千residueを持つGeneratorの再構築を実行し得る。

## 4-6. 中心命題・目標構造・非目標

Fusion可能か、ではなく「Fusionすることで残りの推論全体の実行コストが低下する可能性が高いか」を判断する。`Evidence → Constraint → Fusion Candidate → Cost Estimator → (FUSE | RESIDUAL)`。機械学習・動的プロファイル学習・JIT/AOT・GPU・並列探索・一般SAT/SMT最適化・DSN本体統合・全PredicateのFusion・高度なQuery Optimizer・完全なHardware Cost Modelは非目標。v0.1では決定論的な軽量Estimatorに限定する。

## 7-9. Adaptive Fusion Mode / 後方互換性 / Model G

`context.constraint_fusion` を `off` / `always` / `adaptive` へ拡張する。デフォルトは引き続き `off`。Model G = Model E + Adaptive/Cost-Aware Constraint Fusion。Model Gは新しいアルゴリズムではなく、Evidence/Hypothesis/Factor verification/CandidateSpace semantics/Terminationは Model Eと同一。違いはConstraintの実行表現選択のみ。

## 10-31. Cost Model

```text
Benefit = Future Constraint Evaluation Saved Cost + Future Candidate Generation Saved Cost
Cost    = Generator Rebuild Cost + Fusion Metadata Cost
```

v0.1簡易モデル: `expected_removed ≈ remaining × (1 - predicted_residue_count/current_residue_count)`。`predicted_new_modulus`/`predicted_new_residue_count` はFusionを実際に実行せず安価に算出する。EstimatorはO(1)（またはそれに準ずる定数時間）とし、residue全走査は禁止。

```text
saved_generation = remaining × (1 - newR/currentR)
saved_eval = remaining
benefit = saved_generation × GENERATION_WEIGHT + saved_eval × CONSTRAINT_WEIGHT
cost = currentR × REBUILD_READ_WEIGHT + newR × REBUILD_WRITE_WEIGHT
```

Fusion条件: `benefit > cost × FUSION_MARGIN`（`FUSION_MARGIN = 1.25`初期値）。Hysteresisはv0.1では不要。一度Fusionした Constraintは解除しない（Fused → Residual への逆変換なし）。

## 32-40. Fallback / Decision Reason / Metrics

Cost判断でFusionしない場合は `COST_REJECTED` として、budget fallback / overflow fallback / unsupported fallback と区別する。内部理由コード: `FUSION_SELECTED`, `FUSION_REJECTED_COST`, `FUSION_REJECTED_MODULUS_BUDGET`, `FUSION_REJECTED_RESIDUE_BUDGET`, `FUSION_REJECTED_OVERFLOW`, `FUSION_REJECTED_UNSUPPORTED`。追加Metrics: `fusion_candidate_count`, `fusion_selected_count`, `fusion_rejected_cost_count`, `fusion_estimated_benefit_total`, `fusion_estimated_cost_total`, `fusion_score_total`, `fusion_remaining_candidate_estimate_total`, `fusion_expected_removed_total`。

## 41-70. Model比較・成功条件・Cost Estimator Accuracy

比較対象: Model B（Numerical Wheel-6）、Model E（Fusion Off）、Model F（Always Fusion）、Model G（Adaptive）。`result_E == result_F == result_G` および hypothesis sequence一致が必須。Fusion Selection PrecisionをRecallより優先する（誤ってFusionして大幅regressionする方が危険なため）。初期実装ではFusion選択を保守的にし、疑わしい場合はRESIDUALを選ぶ。

## 71-80. Conservative Policy / Guard

`remaining_candidates < MIN_REMAINING_FOR_FUSION`（初期案1024）や `predicted_residue_count > remaining_candidates` の場合はFusion抑制を検討できる。Rebuild-Amortization Ratio `RAR = remaining_candidates / predicted_rebuild_ops` を新指標として定義。Incremental Rebuild・`unvisited_count()`最適化・Bitset化は別工程とし、本仕様では変更しない。

## 81-98. 実装対象・新型・出力・可視化

```text
FusionPolicy { Off, Always, Adaptive }
FusionEstimate { possible, remaining_candidates, current/predicted_modulus, current/predicted_residue_count, expected_removed, estimated_benefit, estimated_cost, score }
FusionDecision { Fuse(FusionEstimate), Residual(FusionEstimate, FusionRejectReason) }
FusionRejectReason { Cost, ModulusBudget, ResidueBudget, Overflow, Unsupported, Duplicate }
```

Cost Modelは浮動小数を必須とせず、`u64`/`i128`で決定論的に計算する。Overflow時は`checked_mul`/`checked_add`または`i128`を使い、失敗時はResidualへ安全にfallbackする。Benchmark出力CSV/summary.jsonは§91-93の指定項目を含む。可視化: k vs RTER（E/F/G比較）、search space vs runtime（E/F/G比較）、Search Space×k のModel G RTER heatmap、Estimated Fusion Score vs 実測改善率の関係。

## 99-108. テスト

Rust unit tests: adaptive rejects tiny search space / adaptive selects large search space / off・always・adaptiveの意味論一致 / cost rejection reason / overflow fallback / budget rejection / residue budget rejection / deterministic estimate / duplicate constraint / cursor preservation。Integration: Model E/F/G result equality、Hypothesis Sequence一致、Determinism、Fast Path on/off一致。Performance Regression Fixture: `synthetic_sqrt1000000_k6`, `synthetic_sqrt1000000_k8`, `highly_composite_24b`。Positive Fixture: `sqrt(N)=10,000,000` の `k=4,5,6`。過剰保守禁止（`fusion_selected_count > 0` 必須）。

## 109-122. 完了判定・失敗条件

完了判定1（Semantic equivalence, Mandatory）、2（Worst-case regression recovery, Mandatory）、3（Model E保護 95%以内, Target）、4（Fusion opportunity利用, Mandatory）、5（Reasoning-favorable region G>=E, Important）、6（G>E, Target）、7（Oracle Efficiency median>=0.9, Target）、8（RCR-RTER correlationがFより改善, Mandatory target）、9（k0/k1でoverhead非支配, Target）。失敗条件A（G≈F: Cost Model too optimistic）、B（G≈E: too conservative）、C（判断コスト自体が支配的）、D（予測と実測の相関がほぼない: remaining candidate count/residue countだけでは不十分）。

## 123-132. 次段階・DSNへの接続・研究上の意味

本仕様成功後: Incremental Fusion Rebuild、Bitset Generator、Compiled CandidateSpaceを検討する。DSN一般化: `OptimizationCandidate { expected_search_reduction, transformation_cost, future_evaluation_cost }` を比較する Reasoning Cost Planner へ発展させる。新しい中心命題: Minimum Reasoning StepsではなくMinimum Effective Reasoning Costを目標とする。

## 133. 本仕様の最終判定

「Fusionできるか」ではなく「Fusionすべきか」をReasoning Runtimeが判断する最初のCost-aware Optimization機構とする。

## 134. 実装時の決定事項と実測結果の要約（v0.1）

詳細と全データは[レポート](../reports/ReasonScript_Adaptive_Cost_Aware_Constraint_Fusion_Report.md)を参照。要点のみ記す。

| 項 | 決定・結果 |
|---|---|
| `context.constraint_fusion`の値（§7, 88） | 文字列 `"off"`/`"always"`/`"adaptive"`を受け付ける。後方互換のためJSONの真偽値も引き続き受け付ける（`true`→`always`、`false`→`off`）。未知の値は`RTH-PROTO-006`診断を返す。 |
| Model Gの実体（§9, 61-62） | Model E/Fと同じテンプレートを`constraint_fusion="adaptive"`で実行したものであり、新規`.rsn`テンプレート・新規Surface構文は追加していない。 |
| remaining_candidates見積もり（§16-18, 25） | `CandidateSpace::unvisited_count()`（O(residue数)）は使わず、O(1)の密度ベース見積もり `range_left × current_residue_count / current_modulus`（`range_left`はcursorから`upper`までの残り区間長）を採用した。 |
| predicted_residue_count / predicted_modulus（§21-23） | pがcurrent modulusと互いに素という前提（実際、この経路に到達するpは常にそう）のもとで、`current_residue_count × (p - 1)` は近似ではなく厳密な値である（coprimeな法の拡張では、展開後の値のうち正確に1/pがpの倍数になるという乗法的ふるいの恒等式による）。`predicted_modulus = current_modulus × p` も同様に厳密。 |
| Cost Model重み（§27, 46, 86） | `GENERATION_WEIGHT = CONSTRAINT_WEIGHT = REBUILD_READ_WEIGHT = REBUILD_WRITE_WEIGHT = 1`、`FUSION_MARGIN = 1.25`（整数演算 `benefit×4 > cost×5` として実装）。ハードウェア較正は行わない。 |
| Fusion実行順序（§34） | `p`が現在のmodulusを割り切る場合（重複除去、またはwheel-6が既に除外している2/3など）はコスト見積もりを行わず常にFuseする（この経路はGeneratorを成長させないため再構築コストの懸念がなく、§79がEstimator用の新規O(R)走査を禁じている対象でもない）。modulusを新たに成長させる経路（LCM展開）のみコスト判定の対象とする。 |
| 保守性（§70-71） | 見積もり計算やbudget/overflow判定に失敗した場合は必ずResidualへfallackする（`checked_mul`/`checked_add`失敗時も同様）。 |
| **実測結果（重要）** | 117ケースの完全ベンチマークで、結果とhypothesis sequenceはE/F/G全て一致（完了判定1達成）。Model Gの中央値実行時間（40,917ns）はModel F（92,500ns）の半分以下まで改善し、Oracle Efficiency中央値は0.988（完了判定7達成）で、既知のConstraint Fusion v0.1最悪ケース3件中2件（`highly_composite_24b`, `synthetic_sqrt1000000_k6`）で明確な改善を確認した。一方、`synthetic_sqrt1000000_k8`を含む一部の中〜大規模な合成ケースでは、コスト見積もりが依然としてAlways Fusionと同じ判断を下し、regressionが解消されなかった（完了判定2/3/5/6は未達）。原因分析は§7参照。 |
