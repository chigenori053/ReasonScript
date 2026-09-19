# ReasonScript Reasoning-to-Resource Efficiency Report

- 対象仕様: [ReasonScript_Reasoning_to_Resource_Efficiency_Test_v1_0.md](../specifications/ReasonScript_Reasoning_to_Resource_Efficiency_Test_v1_0.md)（実装時の決定事項は同文書§37）
- 前提: [ReasonScript_Lazy_Symbolic_Candidate_Space_v0_1.md](../specifications/ReasonScript_Lazy_Symbolic_Candidate_Space_v0_1.md) / [Report](ReasonScript_Lazy_Symbolic_Candidate_Space_Report.md)（Model Eの実装。本試験はRuntimeコードを変更せず、既存実装をModel Bと比較する）
- 比較対象: Model B（`factorize_reasoning.rsn.template`、numerical wheel-6 search、v1.1から無変更）と Model E（`factorize_lazy_sieve_reasoning.rsn.template`、lazy/symbolic reasoning）
- データセット: (1) ReasonScript_SpecTest v1.3 `get_dataset()` の79ケース、(2) 人工的な圧縮率×探索範囲2次元マトリクス（25ケース、§4参照）
- 再現: `python3 scripts/benchmark_reasoning_resource_efficiency.py --out artifacts/reasoning_resource_efficiency`（グラフは matplotlib を持つ別インタプリタで: `~/development/ReasonScript_SpecTest/.venv/bin/python3 scripts/make_reasoning_resource_efficiency_graphs.py`）
- 生成物: `artifacts/reasoning_resource_efficiency/{comparison.csv, summary.json, graphs/*.png}`
- 計測日: 2026-09-19、Apple Silicon（macOS）、release build、runtime host boundary（`trace=off`、reasoning event mode `count`、warm-up 3回+本計測10回、中央値で判定）

## 1. 結論

| Level | 内容 | 判定 |
|---|---|---|
| 1 | RCR>1 かつ POR>1 | **部分的達成**。圧縮のあるケース(RCR>1)41件中15件でPOR>1（36%）。 |
| 2 | RCR>1 かつ AER>1 | **達成**。圧縮のあるケース41件全てでAER>1（allocationは常に削減）。 |
| 3 | RTER>1 となるケースが存在する | **達成**。104件中35件でRTER>1（最大1.29倍、人工ケースsynthetic_k4/target=1,000,000）。 |
| 4 | RTER>1が同一問題クラスかつ複数サイズで再現する | **達成**。`repeated_factor_composite`（2件の探索範囲bucket）、`synthetic_k2`（3 bucket）、`synthetic_k3`（2 bucket）で再現。 |
| 5 | RCRとRTERに正の相関（Pearson r≥0.5） | **未達**。r=0.032（ほぼ無相関）。 |
| 6 | 明確なbreak-even pointが求められる | **未達（全体では）。探索範囲bucket別には1件のみ存在**。全体のbreak-even RCRは求められない（高RCRでRTER<1のケースが複数存在するため）。1e5-1e6 bucketのみbreak-even RCR=1.74が求まる。 |

要約: Model Eは全域でModel Bを上回るわけではない。**「探索範囲がある程度大きく（sqrt(N)≳1万）、かつ圧縮レベルが中程度（k≈2〜4、RCR≈1.25〜2.0）」という狭い領域でのみModel Bより高速**（最大1.29倍）であり、探索範囲が小さすぎる場合（sqrt(N)=1,000）や圧縮レベルが高すぎる場合（k≥6、多数のconstraintを持つ場合）はRCRが高くてもModel Bの方が高速になる。これは仕様§27の失敗条件Case B（「候補生成/制約評価コストが圧縮効果を相殺する」）に一致する現象で、v0.1のconstraint評価がO(格納constraint数)per candidateであることに起因する（§5で分析）。ReasonScriptは「常に高速」ではないが、「どの条件で構造化推論が数値探索より有利になるか」を明確に特定できた。これは仕様§31・§36が求める評価そのものである。

## 2. 実装中に発見・修正した問題

**人工データセット生成の設計ミス**: 当初、探索範囲サイズを制御する大きな素数`q`を`next_prime(target^2)`として選んでいた。しかしModel B/E双方の候補走査上限（`candidate_space.isqrt(remaining)` および Model Bの `candidate * candidate <= remaining`）は、小因数`p1..pk`を**除去する前**の`remaining`（RU-01/02で2と3のみ除去した直後の値、すなわち`N`そのもの）を使って一度だけ計算される。したがって実際の探索範囲は`sqrt(q)`ではなく`sqrt(prefix × q)`（`prefix = p1×...×pk`）になり、`k`が大きいほど探索範囲が指数関数的に膨張してしまっていた。実例: `target=1,000,000, k=6` で意図した探索範囲は100万だったが、実際の探索範囲は12.7億に達し、Model Bだけで3,790万回の候補テスト・1回あたり13.7秒という外れ値ケースを生んでいた。

修正: `q = next_prime(target^2 // prefix)` として、`N = prefix × q ≈ target^2` となるよう選び直した。これにより探索範囲サイズ（`sqrt(N)`）は`k`によらず`target`にほぼ一致するようになった（§4の表を参照）。修正前のデータでは「圧縮率が高いケースほど探索範囲も（バグにより）比例して大きくなる」という交絡が生じており、これが見かけ上の正の相関（Pearson r=0.36、break-even RCR=1.74）を作り出していた。修正後（探索範囲と圧縮率を真に独立させた後）は相関がほぼ消失する（r=0.03、§4参照）。これは本試験そのものが検出した重要な方法論的知見であり、末尾に隠さず報告する。

**Model Bの因数抽出セマンティクスの相違**: `basic_100`（N=100=2²×5²）で Model Bの戻り値が5、Model Eの戻り値が1となり不一致が生じた。原因はModel B（v1.1で凍結された `factorize_reasoning.rsn.template`）が「同一candidateについて1回割ってから外側ループの境界を再チェックする」設計であるのに対し、Model D/Eは「同一candidateについて割り切れなくなるまで内側whileループで割り切る」設計であるため。`remaining`がちょうど`candidate²`のとき（本ケースの唯一の該当）、Bは外側ループの境界チェックが先に不成立となり、`candidate`自身をこれ以上割らずに`remaining=candidate`のまま終了する。これはModel Bという凍結済み参照実装が元々持つ性質であり、本試験のために変更すべきではない（過去のv1.0-v1.4比較実験との整合性を壊すため）。該当1ケース（`basic_100`）はCSVには残すが、集計統計・相関・レベル判定からは除外した（`summary.json`の`excluded_result_mismatches`）。

## 3. 人工データセット設計（修正後）

`N = p1 × ... × pk × q`。`p1..pk`は5以上のwheel-6適合素数（`5,7,11,13,17,19,23,29,...`から重複なくk個）、`q = next_prime(target² / prefix)`。`target ∈ {1,000, 10,000, 100,000, 1,000,000}`、`k ∈ {0,1,2,3,4,6,8,10,12}`（`i64`安全域`2^62`を超える組み合わせ、または`target²/prefix < 2`となる組み合わせはスキップ）。実際に生成されたのは25ケース（k=10,12は全targetでスキップ、k=6/8は小さいtargetでスキップ）。

## 4. 結果: 圧縮率と探索範囲を分離した場合の挙動

修正後の人工データ（探索範囲は`k`に依らずtargetに一致、§2参照）における RTER（Model B / Model E 実行時間比）の全体像:

| k \\ target | 1,000 | 10,000 | 100,000 | 1,000,000 |
|---|---|---|---|---|
| 0（無圧縮） | 0.83 | 0.81 | 0.82 | 0.82 |
| 1 | 0.90 | 0.96 | 1.01 | 1.00 |
| 2 | 0.93 | 1.06 | 1.08 | 1.13 |
| 3 | 0.88 | 1.07 | 1.21 | 1.22 |
| 4 | 0.85 | 0.96 | 1.18 | **1.29**（最大） |
| 6 | — | 0.82 | 0.86 | 1.22 |
| 8 | — | — | 1.08 | 0.80 |

（`artifacts/reasoning_resource_efficiency/graphs/break_even_map.png` の元データ）

観察された2つの独立した傾向:

1. **探索範囲が大きいほどModel Eが有利になる**（同一kで横に見ると、target=1,000では常にRTER<1だが、target=1,000,000では同じkでRTER>1に転じる）。これは固定オーバーヘッド（CandidateSpaceハンドルの生成・cursor管理）が絶対候補数の多い探索でこそ償却されるため。
2. **圧縮レベルkには最適点があり、単調ではない**。同一targetで縦に見ると、k=2〜4付近でRTERが最大化し、k=6以上では低下する（target=1,000,000でもk=8でRTER=0.80まで低下）。原因は§5で分析する。

この結果、RCR単体（=B候補テスト数/E仮説テスト数）とRTERの相関は**ほぼゼロ**（r=0.032、Level 5未達）になる。RCRはkのみで決まり探索範囲に依存しないが、RTERはkと探索範囲の**両方**に依存するため、RCR単体を横軸にとった散布図（`graphs/rcr_vs_rter.png`）は同じRCR値で全く異なるRTERを持つ点群（探索範囲違い）が重なり合い、単純な相関を示さない。

## 5. 分析: なぜ圧縮レベルkに最適点があるのか

Model Eの`candidate_space.next`は、生成した各候補値に対して**格納されている全constraint**を評価する（`Constraint::accepts`はconjunctionの全項を評価、`candidate_constraint_eval_count`で計測）。kが増えるほど格納constraint数（`candidate_constraint_count`）も増え、生存候補1件あたりの評価コストがO(k)で増加する。一方、各追加constraintが実際に除外する候補数（`candidate_symbolically_excluded_count`または`candidate_skipped_count`の増分）は、追加する素数が大きくなるほど同じ探索範囲内での倍数の出現頻度が下がるため**逓減する**（例: 5の倍数はtarget=100,000以下に2万個あるが、79の倍数は1,266個しかない）。したがって、

```text
k を増やす追加コスト = O(生存候補数 × 1)   （evaluationが線形に増える）
k を増やす追加便益   = O(target / p_k)      （p_kの倍数を除外できる数、逓減）
```

の交点を過ぎると、追加のconstraintはむしろRTERを悪化させる。これは仕様§27の失敗条件Case B（「Candidate generation / constraint evaluationが圧縮効果を相殺」）に正確に一致する現象であり、v0.1仕様§14でExperimentalとされた **Constraint Fusion**（複数のmodulo constraintを単一のgenerator則へ統合し、評価コストをO(1)に保つ）が未実装であることの直接的な帰結である。Constraint Fusionが実装されれば、この最適点は消え、kが増えるほど単調にRTERが改善すると予想される。

## 6. 既存79ケース（organic dataset）での結果

Model Bはwheel-6探索そのもの（アルゴリズム上RCR=1、圧縮なし）とほぼ同じコストであり、Model Eの候補生成オーバーヘッドがそのまま不利に働くケースが大半を占める。中央値RTER=0.85（organicのみ、`basic_100`除く）。

- **`repeated_factor_composite`**（Nが2の冪など、wheel-6走査が空またはごく短い）は10/10ケースでRTER>1（Model Eが有利）。これはwheel-6フェーズ自体がほぼ発生せず、`candidate_space`ハンドルの生成コストがModel Bの変数初期化コストよりわずかに低いため（§4のk=0行が示す全体的な逆の傾向とは異なり、こちらは「探索が事実上ゼロ」という別の理由による）。
- **`highly_composite`/`mixed_factor_composite`**（Model D比較では大きな優位を示したクラス）はModel B比では**RTER<1**（0.76〜0.95）になる。理由は、Model Bの1候補あたりのコスト（`candidate = candidate + 2/4`という単純な増分）がModel Eの1候補あたりのコスト（cursor管理＋格納constraint評価）より低く、これらのクラスの絶対候補数が小さい（highly_composite_24bで候補テスト数は各モデルとも1桁〜2桁）ため、固定オーバーヘッドの差が支配的になるため。[Lazy Symbolic Candidate Spaceレポート](ReasonScript_Lazy_Symbolic_Candidate_Space_Report.md)で確認したModel D比の優位性（allocation最大179倍、実行時間最大54倍）は、**Model Dという「候補を毎回structとして実体化する」実装との比較でのみ大きく現れる**ものであり、Model Bという「候補をscalarのまま扱う」実装と比べると、その優位性の大半は失われる。これは前回レポート§5で報告した「圧縮率とB比優位性の負相関」（r=−0.206）と整合する。

## 7. 3つの評価区分（仕様§31）

`artifacts/reasoning_resource_efficiency/summary.json`の`regions`より（104ケース中）:

- Numerical-favorable region（RTER<0.95）: 59ケース（主にorganicのsemiprime/prime/highly_composite/mixed_factor_composite、および人工k=0または高k）
- Break-even region（0.95≤RTER≤1.05）: 14ケース
- Reasoning-favorable region（RTER>1.05）: 30ケース（人工k=2〜4×target≥1万、および一部のrepeated_factor_composite/mixed）

## 8. Regression / Determinism

本試験はRuntime・frontendのコードを変更していない（新規ベンチマークスクリプトとドキュメントのみ）。Model B/EテンプレートおよびRust runtimeは[Lazy Symbolic Candidate Spaceレポート](ReasonScript_Lazy_Symbolic_Candidate_Space_Report.md)で検証済みのものをそのまま使用した。全104ケースで`termination_B`/`termination_E`はいずれも`completed`（budget超過・エラーなし）。

## 9. 成果物

- `docs/specifications/ReasonScript_Reasoning_to_Resource_Efficiency_Test_v1_0.md`
- `docs/reports/ReasonScript_Reasoning_to_Resource_Efficiency_Report.md`（本書）
- `scripts/benchmark_reasoning_resource_efficiency.py`, `scripts/make_reasoning_resource_efficiency_graphs.py`
- `artifacts/reasoning_resource_efficiency/{comparison.csv, summary.json}`
- `artifacts/reasoning_resource_efficiency/graphs/{rcr_vs_rter.png, search_space_vs_runtime.png, rcr_vs_vm_ratio.png, break_even_map.png}`

## 10. 次段階

- **Constraint Fusion**（v0.1仕様§14・§66で次段階とされていたもの）の実装が最優先候補である。§5の分析どおり、これが実装されればk増加に伴うRTER低下（k≥6での退行）が解消され、圧縮率とRTERの間に単調な正の相関が生まれると予想される。実装後に本試験を再実行し、Level 5/6の再判定を行うことを推奨する。
- 探索範囲が小さい（sqrt(N)<1,000程度）問題では、圧縮率によらずModel Eの固定オーバーヘッドがModel Bの単純さに勝てない。これはCandidateSpaceハンドル生成やcursor管理自体をさらに軽量化するか、小さな探索範囲では自動的にModel B相当のインライン走査へfallbackする最適化（v0.1仕様§14のFusion同様、Experimentalな最適化候補）が有効な可能性がある。
- 10 samplesでも一部の小さいケース（µs〜数十µs域）では測定ノイズの影響が残る（`comparison.csv`のp25/p75/min/max列を参照）。より安定した判定にはサンプル数を増やすか、in-process複数回実行方式（プロセス起動オーバーヘッドを含まない計測）への移行が有効。
