# ReasonScript Constraint Fusion v0.1 Specification

## 1. 文書情報

- 文書名: ReasonScript Constraint Fusion v0.1 Specification
- バージョン: v0.1
- 対象: ReasonScript CandidateSpace / Reasoning Runtime / Generator / Constraint Engine
- 前提: Lazy / Symbolic Candidate Space v0.1、Reasoning-to-Resource Efficiency Test v1.0
- 優先度: P0後続 / Reasoning Runtime Optimization
- 目的: 複数のSymbolic ConstraintをGeneratorへ統合し、Constraint数増加時の候補1件あたり評価コストを削減する。
- 実装レポート: [ReasonScript_Constraint_Fusion_Report.md](../reports/ReasonScript_Constraint_Fusion_Report.md)（実装時の決定事項と実測結果は同文書、特に§7の「発見された性能問題」を参照）。

## 2. 背景

Reasoning-to-Resource Efficiency Test v1.0では、Model EがModel Bより高速になる領域が存在することを確認した。代表的には `sqrt(N) ≳ 10,000`、`RCR ≈ 1.25–2.0`、Constraint数=中程度 の領域でModel EがModel Bを最大約1.29倍上回った。一方、Constraint数を増加させると、k=2,3,4までは性能が改善するが、k>=6では性能が低下するケースが確認された。原因は現在のCandidateSpaceが候補ごとに全Constraintを評価するためである。

## 3. 現在の計算量

CandidateSpaceにC個のConstraintが存在し、G個の候補を生成する場合、`Constraint Evaluation Cost ≈ O(G × C)` となる。推論圧縮によってGが減少しても、Cが増えると `Search Reduction Benefit < Constraint Evaluation Cost` となり得る。

## 4. 中心仮説

複数のModulo Constraintを単一の生成規則へ統合すれば、Constraint数が増加しても候補生成コストをほぼO(1)に維持できる。目標: `Generator → Candidate → Constraint×C → Accept/Reject` から `Fused Generator → Valid Candidate` へ変更する。

## 5. 最終目標

`Evidence → Constraint → Constraint Fusion → Generator Update → Invalid Candidateを生成しない → Physical Operation Reduction → Runtime Reduction` を成立させる。

## 6. 対象Constraint

v0.1では主として `value % p != 0`（`NotDivisibleBy(p)`）形式をFusion対象とする。

## 7. 非対象

`value == x`, `value != x`, 順序比較, 複雑なOR, 任意のGeneric Predicate, state dependent predicate, 非整数predicateはv0.1では対象外（既存Constraint Engineへ残す）。

## 8. Hybrid Constraint Model

Fusion後もConstraintを完全廃止しない: `CandidateSpace { domain, generator, fused_constraints, residual_constraints }`。

## 9. Constraint分類

- Class A — Fusible: `value % p != 0`（Generatorへ統合可能）
- Class B — Foldable: `value > x`, `value < x`（Domainへ統合）
- Class C — Residual: Generatorに統合できないもの（既存Constraint evaluatorで評価）

## 10-14. CandidateSpace構造 / FusedConstraintSet / Wheel Fusion

```text
CandidateSpace { lower, upper, generator, fused, residual_constraints, cursor }
FusedConstraintSet { moduli, wheel_modulus, valid_residues }
```

例: `Generator::Wheel6`（`mod 6`, valid residues `{1,5}`）へ `NotDivisibleBy(5)` を追加すると `LCM(6,5)=30`、`mod 30` valid residues `{1,7,11,13,17,19,23,29}` へ展開する。さらに `NotDivisibleBy(7)` を追加すると `LCM(30,7)=210` の `mod 210` へ展開する。候補生成後のModulo Constraint評価を不要にする。

## 15-19. 候補生成 / Generator更新 / Cursor継続性 / Determinism / Canonical Fusion

`next valid fused residue` を直接算出する。Evidenceから新factorが確定した場合、`NotDivisibleBy(factor)` を `CandidateSpace.add_constraint()` 内でFusion candidateと判定しGenerator更新を行う。Fusion時にcursorを先頭へ戻してはならない。同一のDomain/Constraint insertion sequence/Evidence sequenceに対してgenerated candidate sequence/hypothesis sequence/resultは完全一致すること。Constraint追加順序に依存して最終Generatorが変化してはならない（`exclude 5, exclude 7` と `exclude 7, exclude 5` は同一の `mod 210` valid residuesを生成する）。

## 20-21. Constraint Deduplication / Composite Modulus

同一modulusは重複登録しない。`NotDivisibleBy(15)` のような合成数は、そのままresidualとするか、prime factorizationして3と5へ分解するかのいずれか（最初の実装ではprime factorのみFusion対象としてよい）。

## 22-26. Modulus上限 / Fusion Budget / Fallback

単純LCMを無制限に拡張してはならない。v0.1では `MAX_FUSED_MODULUS = 30030`（`2×3×5×7×11×13`）を初期候補とする（ベンチマーク結果で調整可能）。`FusionBudget { max_modulus, max_residue_count, max_rebuild_cost }` を持たせる。v0.1では単純閾値でよい。Fusion上限を超えた場合、`NotDivisibleBy(p)` は `residual_constraints` へ格納する（Fusion failureはエラーにしない）。

## 27-29. Candidate Generation Complexity / Residue探索 / 保存形式

目標: 現行 `O(C) per candidate` → Fusion後 `O(1) or O(log R)`（Rは residue count）。`current_cycle`/`current_residue_index` を保持し `cycle * modulus + residues[index]` で直接算出する方式を推奨する。v0.1では `Vec<i64>` でよい（将来的にbitset/compressed residues/precomputed jump tableを検討可能）。

## 30. CandidateSpace Metrics

追加: `constraint_fusion_count`, `constraint_fusion_rebuild_count`, `fused_constraint_count`, `residual_constraint_count`, `fused_modulus`, `fused_residue_count`, `fused_candidate_generated_count`, `residual_constraint_eval_count`, `fusion_fallback_count`。

## 31. 既存Metrics

継続: `candidate_generated_count`, `candidate_skipped_count`, `candidate_constraint_eval_count`, `vm_instruction_count`, `allocation_count`, `allocated_bytes`, `runtime_execution_ns`, `hypothesis_test_count`。

## 32-34. Fusion Effectiveness Ratio / Constraint Evaluation Ratio / Fusion Runtime Ratio

```text
FER = candidate_constraint_eval_count_before / candidate_constraint_eval_count_after
CER = residual_constraint_eval_count / candidate_generated_count   (目標 CER → 0)
FRR = runtime_execution_ns_before / runtime_execution_ns_after
```

## 35-38. Benchmark比較 / Model F / Model E/F等価性 / Candidate Sequence

比較対象: Model B（Numerical Wheel-6）、Model E（Lazy CandidateSpace without Fusion）、Model F（Lazy CandidateSpace with Constraint Fusion）。Model FはModel Eと同じ推論アルゴリズムを使用し、変更してよいのはConstraint execution representationのみ（same Evidence, same Hypothesis, same CandidateSpace semantics, same result）。必須: `result_E == result_F`, `hypothesis_sequence_E == hypothesis_sequence_F`, candidate logical sequence equivalent。Fでは物理的にskip候補を生成しないため `candidate_generated_count` はEと異なってよいが、Hypothesis Test対象候補は一致すること。

## 39-41. テスト対象

既存104ケース（79 organic + 25 synthetic）をそのまま再利用する。Constraint数の影響をより明確にするため `k = 0,1,2,3,4,5,6,8,10,12` を可能な範囲で追加する。Search Spaceは `sqrt(N) ≈ 1,000/10,000/100,000/1,000,000` を維持し、可能なら `10,000,000` を追加する。

## 42-51. 成功条件・Break-even Surface

第一〜第七成功条件（結果一致、hypothesis sequence一致、k>=4でconstraint_eval削減、k>=6でPOR_F_B改善、k=6/8でEよりF高速、target=1,000,000のk=6/8でRTER_F_B>1、RCR-RTER相関の改善目標r>=0.3/0.5）を定める。単一RCR break-evenは使用せず、`RTER = f(RCR, search_space, constraint_count)` のBreak-even Surfaceとして扱う。

## 52-59. 可視化・重要ケース・Regression・Fusion Disabled Mode・Semantics優先順位・Fusion Event

Graph A（k vs RTER, E/F比較）、B（k vs candidate_constraint_eval_count）、C（search space vs runtime, B/E/F比較）、D（Search Space×k RTER heatmap）を生成する。`context.constraint_fusion = false` でFusionを無効化できるようにする（E/F比較・regression・debugging・determinism verificationのため）。Model E相当のConstraint EngineをGeneric Pathとして維持する。優先順位: `Correctness > Determinism > Semantic Equivalence > Physical Operation Reduction > Runtime Speed`。追加イベント候補: `CONSTRAINT_FUSED`, `GENERATOR_REBUILT`, `FUSION_FALLBACK`（count modeではcounterのみでよい）。

## 60-67. 実装方針

主実装対象: `ReasonRuntime/crates/computation-ir/src/candidate_space.rs`（必要に応じて `vm.rs`）。Surface Syntax追加は不要（既存の `relation.filter(space, row % factor != 0)` から自動Fusionする）。v0.1では新しい公開IR op追加は必須としない。Fusion可否判定: `modulus != 0`, `comparison == !=`, `remainder == 0`, integer semantics, no side effects。既存の `floor_mod` 定義を共有する。LCM計算は `i128` 等で一時計算しoverflow検出、overflow時はFusion fallback（panic禁止）。residue count過大時もFusionしない（Generator rebuild costとMemory costのため）。

## 68-71. テスト計画

Rust unit tests: wheel6+5 fusion, wheel30+7 fusion, constraint order invariance, duplicate constraint, cursor preservation, overflow fallback, modulus limit fallback, residue limit fallback, fusion disabled。Integration tests: Model E vs F result equivalence, hypothesis sequence equivalence, determinism, Fast Path on/off, Fusion on/off。Performance tests: k=0,2,4,6,8でconstraint eval/VM instructions/allocation/runtimeを測定する。

## 72-73. 出力

CSV/summary.jsonの必須列は§72-73の指定通り（本実装では列名の一部を実装都合で拡張。§7参照）。

## 74-80. 完了判定

A（全結果一致、必須）、B（Hypothesis sequence一致、必須）、C（k>=6でConstraint評価回数がE比50%以上削減、目標）、D（k>=6人工ケースでModel FがModel Eより高速、必須目標）、E（Reasoning-favorable regionがModel Eより拡大、重要）、F（高Constraint領域でのperformance collapseが解消/緩和）、G（Evidence→Constraint→Fusion→Generator specialization→Reduced physical operations→Reduced runtimeの成立）。

## 81-84. 非目標・次段階・DSNへの意味・研究上の中心命題

GPU/parallel search/SAT-SMT solver/arbitrary symbolic algebra/generic non-integer CandidateSpace/DSN本体への統合/Auto cost model完全実装/JIT/AOT compiler/Rust-native CLI移行は本フェーズで扱わない。次段階候補: Adaptive Fusion, Cost Model, Generator Specialization, Compiled CandidateSpace, Reasoning Planner。本工程で検証する本質は「推論制約を増やせば探索対象は減るが、制約評価コストが増える、というトレードオフを、制約そのものを生成規則へコンパイルすることで解消できるか」である。

## 85. 最終判定

ReasonScript Constraint Fusion v0.1は、Constraintを「候補生成後に判定する条件」から「候補生成そのものを定義する規則」へ変換するためのRuntime最適化である。

## 86. 実装時の決定事項と実測結果の要約（v0.1）

詳細と全データは[レポート](../reports/ReasonScript_Constraint_Fusion_Report.md)を参照。要点のみ記す。

| 項 | 決定・結果 |
|---|---|
| Model Fの実体（§35-36, 61-62） | 新しい`.rsn`テンプレートは作成しない。Model Fは**Model Eと全く同じテンプレート**（`factorize_lazy_sieve_reasoning.rsn.template`）を、Runtimeリクエストの `context.constraint_fusion = true` で実行したものである。これにより「Constraint execution representationのみ変更」という制約を構造的に満たす。 |
| Surface API（§61） | 新規構文・新規`candidate_space.*`関数は追加していない。`relation.filter(space, row % p != 0)` と `candidate_space.exclude_multiples_of(space, p)` の両方が、`constraint_fusion`有効時は自動的にFusion対象として判定される。 |
| Fusion対象の判定（§6, §21） | `Constraint::Modulo { op: Ne, r: 0 }` かつ `m` が素数（`is_small_prime`によるtrial division、`FusionBudget::max_modulus`以下という前提で安価）の場合のみFusion対象とする。合成数（例: 15）は§21の「そのままresidualとする」を採用し、素因数分解は行わない（v0.1では実装しない）。 |
| FusedConstraintSet（§11-14） | `{ modulus: i64, residues: Rc<Vec<i64>> }`。Wheel6は`{modulus:6, residues:[1,5]}`、Rangeは`{modulus:1, residues:[0]}`として最初から統一表現で扱う（Fusion無効時もこの表現を使い、`Generator::next_after`という別実装を廃止した。fusion-disabled時の挙動が旧実装とbit-for-bit一致することは単体テスト`fused_set_matches_generator_stepping_exactly`で検証）。 |
| Cursor探索（§28） | `current_cycle`/`current_residue_index`方式ではなく、sorted residuesへの二分探索1回で次の値を直接算出する方式を採用（結果はO(log R)で同等、状態を追加で持つ必要がない）。 |
| Fusion Budget（§22-24） | `MAX_FUSED_MODULUS = 30_030`（`2×3×5×7×11×13`）を採用。`max_residue_count`も同じ30,030とし、modulus上限と独立の追加制限は設けていない（v0.1では単純閾値のみ、と仕様が許容する範囲）。`max_rebuild_cost`は明示的なコストモデルとして実装せず、上記2つの上限のみで代替した。 |
| Fallback（§26） | budget超過時・LCMのi64 overflow時はエラーにせず`residual_constraints`へ格納し、`fusion_fallback_count`をインクリメントし`FUSION_FALLBACK`イベントを発行する。 |
| Constraint Fusion Disabled Mode（§55） | `context.constraint_fusion`（デフォルト`false`）。省略時は本仕様導入前と完全に同一の挙動・メトリクス値になることを既存の82件のRuntimeテストで確認済み。 |
| **発見された性能問題（重要）** | ベンチマークの結果、**k>=4の合成ケースでModel FはModel Eより大幅に遅くなった**（k=8/10で4〜5倍）。原因は、Fusionが実際に統合を行うたびに支払う「Generator再構築コスト」（`unvisited_count`のO(residue数)呼び出しと`try_fuse`自身のO(residue数)再構築）が、候補数の少ない問題では償却されないため。探索範囲が大きい（候補数が多い）ほどこのコストは償却され、target=10,000,000では同じkでもFがEを上回る。詳細な原因分析・実装中に発見し修正した2つの具体的な性能バグ（`CandidateSpace::clone()`のO(residue数)化、`unvisited_count()`の不要呼び出し）はレポート§7参照。**成功条件D/F/Gは未達**（正直に報告。§74-80）。成功条件A/B/C（正しさ・hypothesis sequence一致・k>=4でのconstraint_eval削減）は達成。 |
