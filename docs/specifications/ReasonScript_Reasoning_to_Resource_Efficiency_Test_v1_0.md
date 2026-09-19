# ReasonScript Reasoning-to-Resource Efficiency Test v1.0

## 1. 目的

ReasonScriptにおける、

> 少ない推論過程が、実際の物理演算量・実行時間・メモリ使用量の削減につながるか

を検証する。

本試験では、同一問題に対して以下を比較する。

```text
Model B
Numerical Wheel-6 Search

vs

Model E
Lazy / Symbolic Reasoning
```

主要評価対象は、ReasonScript内部における、

```text
Reasoning Compression
        ↓
Physical Operation Reduction
        ↓
Runtime Resource Reduction
```

の成立可否とする。

実装レポート: [ReasonScript_Reasoning_to_Resource_Efficiency_Report.md](../reports/ReasonScript_Reasoning_to_Resource_Efficiency_Report.md)（実装時の決定事項は同文書§10）。

## 2. 背景

これまでの検証では以下が確認された。

### Model D

Evidence-driven pruningによってHypothesis Test数は削減できたが、候補空間を `Array<Struct>` として事前実体化していたため、物理演算削減にはつながらなかった。

### P0 Runtime改善

VM内部実行コストを約2倍改善し、固定10,000 loop limitをExecution Budgetへ変更した。

### Model E

Lazy / Symbolic Candidate Spaceを導入し、

```text
candidate_materialized_count = 0
relation_filter_rows_scanned = 0
```

を達成した。

代表ケースではModel Dに対して、

```text
VM instructions:
18,458 → 171

allocations:
20,448 → 114

runtime:
約53.9倍改善
```

した。

したがって次の検証対象は、

> Model Eが単純な数値探索Model Bより、実計算資源上で有利になれるか

である。

## 3. 検証仮説

### H1

Hypothesis Test数がModel BのCandidate Test数より少ない場合、`E vm_instruction_count < B vm_instruction_count` となる。

### H2

推論圧縮率が高いほど、`E/B runtime ratio` が改善する。

### H3

一定以上の推論圧縮が得られる問題では、`runtime_execution_ns(E) < runtime_execution_ns(B)` となる。

### H4

Runtime優位が発生するbreak-even pointを測定可能である。

## 4. 比較モデル

### Model B — Numerical Wheel-6

候補値を順番に数値的に検査する（`5, 7, 11, 13, 17, 19, ...`）。各候補について `remaining % candidate` を実行する。EvidenceやCandidateSpaceは使用しない。

### Model E — Lazy Symbolic Reasoning

`CandidateSpace` / `Generator` / `Constraint` / `Evidence` / `Hypothesis` を使用する。EvidenceからConstraintを追加し、将来検査する候補を動的に削減する。

## 5. 公平性条件

Model BとModel Eで以下を統一する: 入力N、small-prime処理、factor extraction semantics、arithmetic type、Rust Runtime、Runtime build、Execution Budget、trace mode、reasoning event mode、compiler/frontend version、process境界、benchmark machine。アルゴリズム上の差は「B: sequential numeric candidate search」「E: evidence-driven symbolic candidate search」だけとする。

## 6. 計測境界

主計測は `reason-runtime-host` 内部で行う。Python CLI全体のwall timeは主評価に使用しない（Python startup/parse/lowering/JSON handlingがRuntimeの数十µs〜数msの差より大きいため）。

## 7. 主評価指標

必須: `candidate_tests_B`, `hypothesis_tests_E`, `candidate_generated_E`, `candidate_skipped_E`, `vm_instruction_count`, `allocation_count`, `allocated_bytes`, `runtime_execution_ns`, `loop_iteration_count`, `relation_dispatch_count`, `constraint_eval_count`。可能なら追加: `cpu_time_ns`, `peak_live_bytes`, `branch_count`, `state_transition_count`。

## 8. 推論圧縮率

```text
RCR = candidate_tests_B / hypothesis_tests_E
```

RCR=1: 圧縮なし。RCR>1: Model Eの推論検証回数が少ない。RCR>>1: 高圧縮。

## 9. Physical Operation Ratio

```text
POR = vm_instruction_count_B / vm_instruction_count_E
```

POR>1: Model Eの物理VM演算が少ない。

## 10. Allocation Efficiency Ratio

```text
AER = allocation_count_B / allocation_count_E
```

## 11. Runtime Efficiency Ratio

```text
RTER = runtime_execution_ns_B / runtime_execution_ns_E
```

RTER>1: Model Eが高速。RTER=1: break-even。RTER<1: Model Bが高速。

## 12. Resource Efficiency Index

```text
REI = geometric_mean(POR, AER, RTER)
```

個別指標を必ず併記し、REIだけで成功判定しない。

## 13. Break-even Point

```text
RCR_break_even = RTER >= 1 を初めて継続的に満たすReasoning Compression Ratio
```

## 14. テストケース設計

既存79ケースに加え、圧縮率を意図的に変化させるケースを追加する。

- Group A — No Compression: Prime / near-equal semiprime。期待 RCR ≈ 1。目的: Reasoning overhead floor測定。
- Group B — Low Compression: 少数の因数を持つComposite。RCR ≈ 1.1–1.3。
- Group C — Medium Compression: 複数因数を持つComposite。RCR ≈ 1.3–2。
- Group D — High Compression: 多数の小因数を持つHighly Composite。RCR >= 2（人工的に生成）。
- Group E — Very Large Search Space: sqrt(N)を大きくする。目的: 固定Runtime overheadが無視できる領域で比較する。

## 15. 問題生成

人工データとして `N = p1 × p2 × ... × pk × q` を使用する（`p1..pk` = small verified factors、`q` = large prime）。kを増減させることでEvidence-driven constraintの効果を制御する。例: `k = 0, 1, 2, 4, 8, 16`。

## 16. Search Space Scaling

同じfactor構造に対しqを変化させる。`sqrt(N): 1k, 10k, 100k, 1M`。これによって compression effect と problem size effect を分離する。

## 17. 2次元テストマトリクス

X = Search Space Size、Y = Compression Ratio。

|           | Low compression | Medium | High |
| --------- | --------------: | -----: | ---: |
| sqrt 1k   |            test |   test | test |
| sqrt 10k  |            test |   test | test |
| sqrt 100k |            test |   test | test |
| sqrt 1M   |            test |   test | test |

これによりbreak-even領域を可視化する。

## 18. 反復

各ケース最低10 runsを推奨する（Runtimeがµs〜ms単位まで高速化したため、3回ではノイズの影響が大きい）。median / p25 / p75 / min / max を取得する。主判定はmedian。

## 19. Warm-up

各モデルにつき計測前に3 warm-up runsを実施する。Runtime processを毎回起動する方式とin-process方式を混同しない。

## 20-25. 成功Level 1-6

| Level | 条件 | 意味 |
|---|---|---|
| 1 | RCR>1 かつ POR>1 | 推論圧縮がVM物理演算削減につながった |
| 2 | RCR>1 かつ AER>1 | 推論圧縮がallocation削減につながった |
| 3 | RTER>1 となるケースが存在する | Reasoning modelがnumerical baselineを実時間で上回る |
| 4 | RTER>1が同一問題クラスかつ複数サイズで再現する | 単発でない |
| 5 | RCRとRTERに正の相関（Pearson r >= 0.5） | |
| 6 | 明確なbreak-even pointが求められる（例: RCR>=1.7でModel Eが継続的にModel Bを上回る） | |

## 26. 最終成功条件

`Reasoning Compression → Fewer Generated Candidates → Fewer VM Instructions → Lower Allocation → Lower Runtime` かつ `Model E < Model B` となる領域を特定する。

## 27. 失敗条件

- Case A: RCR↑, POR↑, RTER<1 → Reasoning Runtimeの1操作コストがまだ高い。
- Case B: RCR↑, POR≈1 → Candidate generation / constraint evaluationが圧縮効果を相殺。
- Case C: RCR≈1 → 問題自体に推論圧縮可能性がない（この場合はReasonScript失敗とは判定しない）。

## 28. 必須出力

CSV: `test_id, problem_class, N, sqrt_N, candidate_tests_B, hypothesis_tests_E, candidate_generated_E, RCR, vm_instr_B, vm_instr_E, POR, alloc_B, alloc_E, AER, runtime_ns_B, runtime_ns_E, RTER, peak_memory_B, peak_memory_E, termination_B, termination_E`。

## 29. Summary

`summary.json`: `cases_total, cases_RTER_gt_1, median_RCR, median_POR, median_AER, median_RTER, correlation_RCR_POR, correlation_RCR_RTER, break_even_RCR, break_even_search_space`。

## 30. 可視化

- Graph 1: X=RCR, Y=RTER（break-even Y=1を表示）
- Graph 2: X=search space size, Y=runtime ns（B/E比較）
- Graph 3: X=RCR, Y=VM instruction ratio
- Graph 4: Compression × Search Spaceのheatmap

## 31. 重要な評価区分

結果は Numerical-favorable region（B faster）/ Break-even region（B≈E）/ Reasoning-favorable region（E faster）の3種類に分ける。ReasonScriptの目的は全ケースでBを上回ることではなく、どの条件で構造化推論が数値探索より有利になるかを明確にすることである。

## 32. 研究上の解釈

本試験が成功した場合、ReasonScriptについて「推論ステップを減らせる」だけでなく「問題構造を利用して不要な計算を避けることで、特定条件下では単純探索より少ない実計算資源で問題を解ける」と主張できる。

## 33. DSNへの意味

DSNでは Possible RU/State/Transition/Hypothesis の全探索を行う代わりに、Evidence → Activation → Constraint → Candidate Reduction によって探索対象を減らすことを想定する。本試験はMathematical Candidate Searchを使った、DSN Search-space Reductionの基礎実証でもある。

## 34. 実施順序

1. Model B/E benchmark専用script作成 2. 既存79ケース再測定 3. 圧縮率制御ケース追加 4. Search-space scaling追加 5. 各ケース複数回測定 6. RCR/POR/AER/RTER算出 7. break-even検出 8. correlation算出 9. グラフ生成 10. 技術レポート作成。

## 35. 完了条件

```text
docs/specifications/ReasonScript_Reasoning_to_Resource_Efficiency_Test_v1_0.md
docs/reports/ReasonScript_Reasoning_to_Resource_Efficiency_Report.md
artifacts/reasoning_resource_efficiency/comparison.csv
artifacts/reasoning_resource_efficiency/summary.json
artifacts/reasoning_resource_efficiency/graphs/rcr_vs_rter.png
artifacts/reasoning_resource_efficiency/graphs/search_space_vs_runtime.png
artifacts/reasoning_resource_efficiency/graphs/rcr_vs_vm_ratio.png
artifacts/reasoning_resource_efficiency/graphs/break_even_map.png
```

## 36. 最終判定

「少ない推論過程 → 少ない物理演算 → 少ない実計算資源」が成立する条件を特定する。成立条件が存在すれば、ReasonScriptは「常に高速な言語」ではなく「構造的推論によって探索削減が可能な問題において計算資源効率を高められるRuntime」であるという評価へ進む。

## 37. 実装時の決定事項（v1.0）

本仕様の実装で確定した点。仕様本文が選択肢を残している箇所の解釈を記す。詳細な数値と判定結果は[レポート](../reports/ReasonScript_Reasoning_to_Resource_Efficiency_Report.md)を参照。

| 項 | 決定 |
|---|---|
| 出力先（§35） | 本リポジトリに `graphs/` という新規トップレベルディレクトリを作らず、既存の慣例（`artifacts/<feature>/`）に合わせて `artifacts/reasoning_resource_efficiency/{comparison.csv, summary.json, graphs/*.png}` へ配置した。 |
| 人工ケース生成（§15-16） | `N = p1 × ... × pk × q` の `q` は `sqrt(N)` が目標search space size（1k/10k/100k/1M）に近い単一の大きな素数とし、`p1..pk` は5以上のwheel-6適合小素数（2,3を除く）から重複なくk個選ぶ。積が `i64` の安全域（`2^62`未満）を超える組み合わせ（大きいkと大きいsearch spaceの組）はスキップする（`sqrt(N)`と`k`を完全な矩形マトリクスにできない制約）。 |
| 反復回数（§18） | warm-up 3回 + 本計測10回を既存79ケースと人工ケースの両方に適用。`runtime_execution_ns`, `vm_instruction_count`, `allocation_count`, `allocated_bytes`, `peak_live_bytes` の median/p25/p75/min/maxを記録し、判定は中央値を使用する。決定的なカウント（`hypothesis_test_count`等）は1回の実行から取得する（実行間で不変であることは既存の決定性テストで確認済み）。 |
| peak_memory（§28） | `/usr/bin/time -l` による追加プロセス起動は行わず、VM自身が計測する `peak_live_bytes`（allocatorのpeak live bytes）を代替値として使用する。プロセスRSSではなくVM内allocationのpeak値である点を明記する。 |
| cpu_time_ns（§7） | プロセス起動を伴う追加計測が必要なため本試験では収集しない（§6の計測境界の趣旨に反しないよう、in-process VM時間のみで判定する）。 |
| break_even_search_space（§29） | `sqrt(N)`の桁（`10^3`未満、`10^3-10^4`、`10^4-10^5`、`10^5-10^6`、`10^6`以上の5bucket）ごとに§13と同じ手順でbreak-even RCRを求めた辞書として出力する。 |

後続: [ReasonScript_Constraint_Fusion_v0_1.md](ReasonScript_Constraint_Fusion_v0_1.md) が本試験で発見された「圧縮率が高いほどwheel-6より不利になり得る（k>=6以降）」という現象の原因分析と対策を扱う。
