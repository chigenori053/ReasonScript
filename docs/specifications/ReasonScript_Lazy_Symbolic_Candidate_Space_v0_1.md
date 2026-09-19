# ReasonScript Lazy / Symbolic Candidate Space v0.1 Specification

## 1. 文書情報

- 文書名: ReasonScript Lazy / Symbolic Candidate Space v0.1 Specification
- バージョン: v0.1
- 対象: ReasonScript Reasoning Runtime / Relation Runtime / Candidate Representation
- 策定日: 2026-09-18
- 優先度: P0後続 / Reasoning Representation改善
- 目的: 推論候補を全件実体化せず、遅延生成または制約表現として保持することで、Reasoning CompressionをPhysical Operation Reductionへ接続する。
- 実装レポート: [ReasonScript_Lazy_Symbolic_Candidate_Space_Report.md](../reports/ReasonScript_Lazy_Symbolic_Candidate_Space_Report.md)
- 実装時の決定事項: §69（本書末尾）

## 2. 背景

ReasonScript_SpecTestおよびP0 Runtime Performance検証により、ReasonScriptではEvidence-driven Dynamic Pruningが成立することが確認された。

一方、Model Dでは候補探索空間を事前に `Array<Struct>` として全件生成するため、仮説検証回数を削減しても、候補空間構築に必要な物理演算量は削減されない。

代表例では、

```text
wheel-6 candidate space: 2032
hypothesis tests: 8
```

まで推論上の検証回数を削減できるにもかかわらず、実際には2,032件の候補構築と複数回のRelation走査を先に実行している。

したがって現行構造では、

```text
Reasoning Compression
        ↓
Hypothesis Tests Reduction
```

までは成立するが、

```text
Hypothesis Tests Reduction
        ↓
Physical Operations Reduction
```

が成立しない。本仕様ではCandidate Space自体の表現方式を変更し、この断絶を解消する。

## 3. 中心命題

Candidate Spaceを「候補要素の配列」ではなく、「生成規則・範囲・制約・除外条件の組み合わせ」として保持する。

```text
CandidateSpace
=
Domain
+ Generator
+ Constraints
+ Evidence
```

候補を必要になるまで実体化しない。

## 4. 現行モデル

現行Model Dは概念的に以下である。

```text
sqrt(N)
   ↓
全候補生成
   ↓
Array<Struct>
   ↓
hypothesis test
   ↓
relation.filter
   ↓
候補削除
```

問題点:

- 候補数に比例したallocation
- 候補数に比例したStruct生成
- 配列構築ループ
- filter時の全件走査
- prune対象も事前に実体化済み
- 検証されない候補にもコストを払う

## 5. 目標モデル

```text
CandidateSpace
   │
   ├ Domain
   ├ Generator Rule
   ├ Constraints
   └ Evidence-derived exclusions
           ↓
        next()
           ↓
     Hypothesis Test
```

候補要素は必要になった時点でのみ生成する。

```text
CandidateSpace {
    lower_bound
    upper_bound
    generator
    constraints
}
```

## 6. 設計原則

1. Candidateを事前に全件materializeしない
2. Constraint追加時に既存配列を再構築しない
3. Evidenceから得た条件をCandidateSpaceへ直接追加する
4. next candidate生成時に制約を適用する
5. CandidateSpace表現自体は軽量であること
6. Deterministic iterationを保証する
7. Generic Array/Relationとの互換経路を残す
8. 推論結果・証拠・trace semanticsを維持する

## 7. CandidateSpace Core Model

```text
CandidateSpace
{
    domain
    generator
    constraints
    cursor
    metadata
}
```

最低限以下を持つ。

```text
domain:      lower_bound, upper_bound
generator:   generation_rule
constraints: ordered constraints
cursor:      current logical position
metadata:    generated_count, skipped_count, exhausted
```

## 8. Domain

Domainは探索可能な値域を表す。例: `Domain { min: 5, max: sqrt(N) }`。Domainは値配列を持たない。

## 9. Generator

Generatorは候補生成規則を表す。例: `Generator::Range { step: 1 }` または `Generator::Wheel6`（`6k - 1`, `6k + 1` を順に生成）。重要なのは `[5, 7, 11, 13, 17, ...]` という配列を事前に作らないことである。

## 10. Constraint

CandidateSpaceは複数のConstraintを保持する。例: `NotDivisibleBy(5)`, `NotDivisibleBy(7)`, `GreaterThan(11)`, `NotEqual(13)`。ConstraintはCandidate生成時に評価する。

## 11. Evidence-driven Constraint

ReasonScript固有機能として、Evidence → Constraint の変換を正式に扱う。`HYPOTHESIS_VERIFIED factor=5` を得た場合、`NotDivisibleBy(5)` をCandidateSpaceへ追加する。

現行: `relation.filter(candidates, candidate.value % 5 != 0)`
新構造: `candidate_space.exclude_multiples_of(5)`

この操作で既存配列走査を行わない。

## 12. Lazy Evaluation

```text
next():
loop:
    value = generator.next()
    if value > domain.max: exhausted
    if constraints.accept(value): return value
    skipped_count += 1
```

物理生成されるCandidateは、実際に検討対象となる値に限定される。

## 13. Symbolic Representation

単純なConstraintについては、Candidateごとの評価すら減らすことを目指す。`NotDivisibleBy(5)`, `NotDivisibleBy(7)` を `Wheel(2,3,5,7)` 相当へ統合可能な場合、Generator ruleへcompileする（Constraint Fusion）。

## 14. Constraint Fusion

v0.1では必須としない。v0.1では Lazy Generation + Constraint Check までを必須とし、FusionはExperimentalとする。

## 15. Candidate Materialization

必要な場合のみ明示的にmaterializeできる: `candidate_space.materialize()`。用途: Debug / Visualization / Compatibility / Export / Test。通常推論では使用しない。

## 16. Relation統合

現行Relation API（`relation.count`, `relation.filter`, `relation.exists`, `relation.first`）のCandidateSpaceに対する動作を定義する。

## 17. relation.count

Lazy CandidateSpaceに対して安易に全件生成してcountしてはならない。Exact count可能ならSymbolicに件数算出、算出困難なら `count_unknown` / Lazy count 扱い、Forced exact count は明示要求時のみ走査する。

## 18. relation.filter

CandidateSpaceへのfilterは新しいCandidateSpaceを返す（`CandidateSpace + Predicate → CandidateSpace'`）。Constraint追加として扱う。

## 19. filter semantics

`relation.filter(candidate_space, |c| c.value % factor != 0)` は可能なら `candidate_space.with_constraint(NotDivisibleBy(factor))` へloweringする。Unsupported predicateはGeneric Lazy Predicateとして保持してもよい。

## 20. Predicate分類

v0.1でSymbolic化対象とするPredicate:

```text
value == x, value != x
value < x, value <= x, value > x, value >= x
value % m == r, value % m != r
```

論理結合 `AND` / `OR` / `NOT` も対応候補とする。

## 21. Internal IR

```text
CandidateSpaceCreate
CandidateSpaceNext
CandidateSpaceAddConstraint
CandidateSpaceReset
CandidateSpaceMaterialize
CandidateSpaceIsExhausted
```

必要に応じて `CandidateConstraint` 型を定義する。

## 22. Constraint IR

```text
CandidateConstraint { kind, operand, value }
ModuloNotEqual { divisor: 5, remainder: 0 }
```

## 23. Fast Path

CandidateSpace操作はRust Runtime内で専用Fast Pathを持つ。Generic Struct/Array/HashMapへ落とさない。

```text
struct CandidateSpace {
    lower: i64,
    upper: i64,
    cursor: i64,
    generator: Generator,
    constraints: SmallVec<Constraint>,
}
```

CandidateごとにHashMapやString keyを生成してはならない。

## 24. Allocation目標

CandidateSpace自体は原則O(1)またはO(C) allocationとする（C = Constraint数）。`O(number_of_candidates)` から `O(number_of_constraints)` へ。

## 25. Execution Complexity目標

現行Model D: Candidate Construction O(S) + Filtering O(F × S) + Hypothesis O(H)。
目標: Lazy Generation O(G) + Constraint Update O(F) + Hypothesis O(H)。Gは実際に生成・確認した候補数に近づけ、最終的には `G ≈ H + skipped-by-generator` を目指す。

## 26. Reasoning Event統合

```text
CANDIDATE_SPACE_CREATED
CONSTRAINT_ADDED
CANDIDATE_GENERATED
CANDIDATE_SKIPPED
CANDIDATE_SPACE_EXHAUSTED
```

ただしイベント粒度はtrace modeで制御する。通常はcandidate単位の全イベントを記録しない。

## 27. Summary Trace

summary modeでは `candidate_space_initial_estimate`, `candidate_generated_count`, `candidate_skipped_count`, `constraint_count`, `hypothesis_test_count`, `candidate_materialized_count` のみ記録する。

## 28. Candidate Pruned再定義

`candidate_pruned_count` を `candidate_materialized_pruned_count`, `candidate_symbolically_excluded_count`, `candidate_generated_skipped_count` へ分割する。

## 29. symbolic exclusion count

正確な個数を即時計算できる場合のみ記録する。不明な場合 `null` / `unknown` を許可する。推定値を確定値として扱わない。

## 30. Determinism

同一の Domain / Generator / Constraint sequence に対して candidate sequence / hypothesis sequence / result / trace summary は一致すること。

## 31. Constraint Ordering

Constraintの適用順序によって結果集合が変化してはならない（performanceは変化し得る）。canonical order: 1. bound constraints 2. equality 3. modulo 4. generic predicate。

## 32. Non-goals

任意集合代数、SQL相当Query Optimizer、SAT/SMT Solver、distributed / GPU CandidateSpace、infinite symbolic set一般対応、probabilistic search、beam search、heuristic ranking、parallel candidate generation、advanced wheel synthesis必須化。

## 33. 互換性

既存の `Array<Struct>` / `relation.filter` / `relation.count` は維持する。新CandidateSpaceは追加型として導入し、既存プログラムを破壊しない。

## 34. Surface Syntax

v0.1では新しいユーザー向けSyntax追加を必須としない。既存コード `relation.filter(...)` をsemantic lowering時にCandidateSpaceへ変換できる場合、自動最適化する。

## 35. Experimental Surface案

```text
space candidates = range(5, sqrt(n)) |> wheel6() |> exclude(divisible_by(factor))
```

ただしv0.1では非必須。

## 36. SpecTest Model E

Model E: Lazy / Symbolic Sieve Reasoning。比較対象: Model A（Rust baseline）、Model B（ReasonScript wheel-6）、Model D（Materialized sieve-reasoning）、Model E（Lazy symbolic sieve-reasoning）。

## 37. Model Eルール

Model EはModel Dと同じ推論戦略を使用する。変更してよいのは Candidate representation のみ（same hypothesis logic / factor verification / evidence / pruning semantics）。

## 38. 主要比較目的

Representation Changeだけの効果を測定する。比較項目: hypothesis count, VM instructions, allocation count, allocated bytes, wall time, runtime_execution_ns, candidate generation count, relation scans。

## 39-46. 成功条件

| Level | 条件 | 区分 |
|---|---|---|
| A | Model Eの最終結果がModel Dと一致 | 必須 |
| B | Model Eのhypothesis test sequenceがModel Dと一致 | 必須 |
| C | Model Eのcandidate materializationが `initial_candidate_space_size` に比例しない | 必須 |
| D | highly_composite系で `allocation_count` をModel D比50%以上削減 | 目標 |
| E | highly_composite_24bで `runtime_execution_ns(E) < runtime_execution_ns(D)` | 必須目標 |
| F | D/B > 1 だったケースのうち1ケース以上で E/B <= 1 | 重要目標 |
| G | 圧縮率の高いケースほど実行時間改善が大きい正の相関（Pearson r >= 0.5、ケース数と分布を併記） | 目標 |
| H | Reasoning Compression → Generated Candidates Reduction → VM Instructions Reduction → Allocation Reduction → Runtime Reduction の連鎖を実証 | 最終成功条件 |

## 47. 必須メトリクス

追加: `candidate_space_estimated_size`, `candidate_generated_count`, `candidate_skipped_count`, `candidate_symbolically_excluded_count`, `candidate_materialized_count`, `candidate_constraint_count`, `candidate_constraint_eval_count`, `candidate_space_next_count`。
既存: `vm_instruction_count`, `allocation_count`, `allocated_bytes`, `reasoning_step_count`, `hypothesis_test_count`, `relation_filter_count`, `relation_filter_rows_scanned`, `runtime_execution_ns` も継続。

## 48-52. Physical Efficiency指標

- CMR (Candidate Materialization Ratio) = candidate_materialized_count / candidate_space_estimated_size（理想 → 0）
- GER (Generation Efficiency) = hypothesis_test_count / candidate_generated_count（1に近いほど無駄生成が少ない）
- PCR (Physical Compression Ratio) = D vm_instruction_count / E vm_instruction_count（> 1 を改善とする）
- ACR (Allocation Compression Ratio) = D allocation_count / E allocation_count
- RTR (Runtime Compression Ratio) = D runtime_execution_ns / E runtime_execution_ns

## 53. 検証対象ケース

prime, semiprime, semiprime_near_equal, repeated_factor_composite, highly_composite, mixed_factor_composite（特に highly_composite と mixed_factor_composite を重点対象）。

## 54. 境界ケース

empty CandidateSpace, single candidate, no constraints, many constraints, constraint contradiction, all candidates excluded, very large upper bound, repeated identical constraint。

## 55. Constraint contradiction

`value > 100` と `value < 10` を検出可能なら `CandidateSpace exhausted` へ即時変換する（v0.1ではOptional最適化）。

## 56. Constraint deduplication

同じConstraintを複数回追加しない（`NotDivisibleBy(5)` × 2 は1件へcanonicalize）。

## 57. Memory Safety

Rust実装では候補状態を借用・共有する場合でも、dangling referenceを作らない、hidden mutationをしない、iteration中のconstraint変更ルールを明確化する。

## 58. Constraint追加タイミング

iteration中にEvidenceが得られた場合、current candidate → evidence → constraint add → future candidate generationに反映する。既に処理済みCandidateを再検証しない。

## 59. Cursor Semantics

Constraint追加後にcursorを0へ戻してはならない（v1.3で修正されたindex reset問題を再発させない）。CandidateSpaceは単調前進する。

## 60. Generic Predicate

Symbolic化不能なPredicateは `GenericPredicate` として保持可能。ただし毎Candidate VM callbackになるためメトリクス（`symbolic_constraint_eval_count`, `generic_predicate_eval_count`）で区別する。

## 61. Optimization Boundary

v0.1では Correctness > Determinism > Reduced Physical Work > Absolute Speed の順で優先する。

## 62. 実装フェーズ

Phase 1 CandidateSpace Core / Phase 2 Range・Wheel6 Generator / Phase 3 Constraint Engine / Phase 4 Relation Integration / Phase 5 Runtime Metrics / Phase 6 Model E / Phase 7 D/E Equivalence / Phase 8 Performance Validation。

## 63. 実装優先順位

1. CandidateSpace Rust core 2. CandidateSpaceNext 3. Wheel6 generator 4. Modulo constraints 5. Constraint add 6. Metrics 7. Model E 8. Generic relation.filter integration 9. Optional constraint fusion。

## 64. 成果物

```text
docs/specifications/ReasonScript_Lazy_Symbolic_Candidate_Space_v0_1.md
docs/reports/ReasonScript_Lazy_Symbolic_Candidate_Space_Report.md
ReasonRuntime/ candidate_space.rs
tests/runtime/test_candidate_space.py
tests/runtime/test_candidate_constraints.py
tests/runtime/test_candidate_space_determinism.py
ReasonScript_SpecTest/ Model E, comparison D vs E
```

## 65. 完了条件

1. CandidateSpaceがRust Runtime上で動作 2. 全候補事前materialization不要 3. Evidence-derived constraintを追加可能 4. Modulo constraintが動作 5. Model EがModel Dと同じ解を返す 6. Hypothesis sequenceが一致 7. Determinism維持 8. Allocation削減を実測 9. VM instruction削減を実測 10. Performance reportを作成。

## 66. 次段階

Constraint Fusion / Generator specialization / Symbolic interval algebra / Compiled CandidateSpace / Bytecode integration。

## 67. DSNへの接続

本CandidateSpaceは素因数分解専用機能として設計しない。将来的にはDSNで Possible States / Rules / Transitions / Hypotheses をすべて実体化する代わりに、Symbolic Search Space + Constraints + Activation Conditions として保持する基盤へ発展可能とする（Mathematical Candidate だけでなく Reasoning Candidate を表現できる汎用機構）。

## 68. 最終目標

```text
Evidence → Constraint → Search Space Reduction → Generated State Reduction
→ Physical Operation Reduction → Runtime Resource Reduction
```

これをReasonScript Lazy / Symbolic Candidate Space v0.1の中心検証仮説とする。

## 69. 実装時の決定事項（v0.1）

本仕様の実装（`ReasonRuntime/crates/computation-ir/src/candidate_space.rs`, `vm.rs`, frontend `candidate_space` 名前空間）で確定した点。仕様本文が選択肢を残している箇所の解釈を記す。

| 項 | 決定 |
|---|---|
| Surface API（§34） | 内部IR `call_candidate_space` を新設し、標準名前空間 `candidate_space` として公開する: `range(lower, upper)`, `wheel6(lower, upper)`, `isqrt(n)`, `next(space)`, `is_exhausted(space)`, `exclude_multiples_of(space, m)`, `reset(space)`, `materialize(space)`。§21 の6操作にそれぞれ対応する（AddConstraint = `exclude_multiples_of` と `relation.filter`）。新構文（§35）は追加しない。 |
| 候補の型 | CandidateSpaceの行（row）は候補値そのもの（Int）。`relation.filter(space, row % factor != 0)` のように述語中の `row` が候補値を指す（§20 の `value` に対応）。`materialize` は `[int]` を返す。 |
| Domain | `[lower, upper]` の両端を含む整数区間。`sqrt(N)` は `candidate_space.isqrt(n)`（正確な整数平方根）で与える。 |
| Generator | `Range`（step 1）と `Wheel6` のみ。§9 の `step` は不要のため持たない。 |
| Constraint | `value <op> k`, `(value % m) <op> r`, `&&`, `\|\|`, `!` の木。順序制約（`<`, `<=`, `>`, `>=`）はDomainへ畳み込み（bound fold）、`==`/`!=` と modulo は格納し候補ごとに評価、論理木は1件のsymbolic constraintとして格納する。`&&` の最上位は個別のconstraintへ分割する。`!(a == b)` は `a != b` へ正規化する。canonical order（§31）: bound fold → equality → modulo → 論理木。重複は追加しない（§56）。 |
| Generic Predicate（§19, §60） | v0.1では保持しない。symbolic化できない述語は `CS-PRED-001` で拒否し、`materialize` してから配列filterを使う互換経路を案内する。`generic_predicate_eval_count` は常に0。 |
| Cursor / lookahead | `cursor` は最後に生成した生成規則上の値。`is_exhausted` は次の受理候補を先読み（peek）して保持し、`next` がそれを返す。constraint追加時は先読み値を未訪問へ戻し（cursor を1つ戻すのみ、skip済み候補は再訪しない）、新しい制約で再判定する。cursorを起点へ戻すのは明示的な `reset` のみ（§59）。 |
| 共有と変異（§57） | CandidateSpace値は `Rc<RefCell<>>` のhandle。`next`/`is_exhausted` はhandleのcursorを進める（ArrayBuilderと同じ透過的な進行）。constraint追加と `reset` は新しいhandleを返し、元のhandleは変更しない。 |
| relation.count（§17） | 格納constraintが無い場合のみ、未訪問候補数を生成規則からO(1)で算出して返す。格納constraintがある場合は `CS-COUNT-001` を返し、暗黙の走査を行わない（Forced exact countは `materialize(space).length`）。 |
| relation.exists / first（§16） | 既存Relation APIに存在しないため対象外。 |
| Reasoning Event（§26） | `CANDIDATE_SPACE_CREATED`（生成ごと）、`CONSTRAINT_ADDED`（filter/exclude呼び出しごと、重複でも記録）、`CANDIDATE_SPACE_EXHAUSTED`（空間ごとに1回）を runtime が自動発行する。候補単位の `CANDIDATE_GENERATED` / `CANDIDATE_SKIPPED` はカウンタのみで、どのtrace modeでもイベントとして記録しない（イベント数をmodeに依存させないため）。プログラムが必要なら `reasoning.event` で明示発行できる。 |
| Metrics（§27, §28, §47, §60） | `runtime_metrics` に `candidate_space_estimated_size`, `candidate_generated_count`, `candidate_skipped_count`, `candidate_symbolically_excluded_count`（bound foldのみの空間では正確値、格納constraintが1件でも加わると以後 `null`）, `candidate_materialized_count`, `candidate_constraint_count`, `candidate_constraint_eval_count`, `candidate_space_next_count`, `candidate_materialized_pruned_count`（= 配列filterの `candidate_pruned_count`）, `candidate_generated_skipped_count`, `symbolic_constraint_eval_count`, `generic_predicate_eval_count` を追加。 |
| Execution Budget | `next`/`is_exhausted`/`materialize` 内の生成ループは1,024候補ごとにwall time / memory budget を確認する。 |
| Constraint Fusion（§13-14） | 未実装（Experimental）。 |
| 矛盾検出（§55） | bound fold により `lower > upper` となった時点で exhausted。modulo制約同士の矛盾は検出しない。 |
| Python参照実装 | `candidate_space.*` はRust専用（runtime consolidation manifest に `python: absent` として登録）。 |
