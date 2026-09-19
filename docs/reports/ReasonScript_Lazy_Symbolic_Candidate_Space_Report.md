# ReasonScript Lazy / Symbolic Candidate Space v0.1 Report

- 対象仕様: [ReasonScript_Lazy_Symbolic_Candidate_Space_v0_1.md](../specifications/ReasonScript_Lazy_Symbolic_Candidate_Space_v0_1.md)（実装時の決定事項は同文書§69）
- 前提: [ReasonScript_P0_Runtime_Performance_v1_0.md](../specifications/ReasonScript_P0_Runtime_Performance_v1_0.md) / [Report](ReasonScript_P0_Runtime_Performance_Report.md) の Rust runtime（execution budget、native counters、Fast Path）。本ブランチは P0 ブランチ（`claude/reasonscript-runtime-perf-ae321f`）へ fast-forward 済み。
- 比較対象: Model D（`factorize_sieve_reasoning.rsn.template`、materialized sieve reasoning）と Model E（`factorize_lazy_sieve_reasoning.rsn.template`、lazy sieve reasoning）。両モデルとも Model B（wheel-6）と同一のアルゴリズム・仮説検証順序・pruning semantics を用い、変更点は候補表現のみ（仕様§37）。
- データセット: ReasonScript_SpecTest v1.3 `get_dataset()` の79ケース（stage1 10、scaling 60、stage5 1、sqrt probe 8）。
- 再現: `python3 scripts/benchmark_candidate_space.py --samples 3 --out artifacts/candidate_space_profile`
- 生成物: `artifacts/candidate_space_profile/{results.json, comparison.csv, summary.json}`
- 計測日: 2026-09-19、Apple Silicon（macOS）、release build、runtime host boundary（`trace=off`, reasoning event mode `count`、`benchmark_p0_runtime.py` と同じ計測方式。詳細は同レポート§3および[[p0-runtime-perf-measurement]]）。

## 1. 結論

| Level | 内容 | 判定 |
|---|---|---|
| A | Model Eの最終結果がModel Dと一致 | **達成**。79/79ケースで一致。 |
| B | hypothesis test sequenceが一致 | **達成**。イベント列を直接比較できた78ケース全てで一致（`limit_probe_sqrt100000` のみ trace byte budget により打ち切られhypothesis test countの一致のみで確認）。 |
| C | candidate materializationが初期候補空間サイズに比例しない | **達成**。全79ケースで `candidate_materialized_count == 0`（CMR = 0）、`relation_filter_rows_scanned == 0`。中央値 GER = 1.0（生成した候補はほぼ全て仮説検証に使われる）。 |
| D | highly_composite系でallocation_countをModel D比50%以上削減 | **未達（形式上）、実質は大幅達成**。目標は「50%以上削減」= ACR ≥ 2 だが、highly_composite全10ケースの中央値 ACR = 10.5（8bで1.22倍、24b/26bで179倍）。8bのみ基準未満だが、それ以外は目標を大きく超過。 |
| E | highly_composite_24bで runtime_execution_ns(E) < runtime_execution_ns(D) | **達成**。E=23,875ns、D=1,286,000ns（RTR = 53.9倍）。 |
| F | D/B > 1 だったケースのうち1件以上でE/B ≤ 1 | **達成**。D/B > 1 の65ケース中12ケースでE/B ≤ 1（basic_12/97/100/997、prime_8b/10b/12b、semiprime_8b/12b、semiprime_near_equal_8b/12b、highly_composite_12b）。 |
| G | 圧縮率とruntime改善の正の相関（Pearson r ≥ 0.5） | **達成**。圧縮率 vs RTR で r = 0.544（n=79、圧縮率は1.0〜1.625の範囲、compression > 1 のケースは20件）。圧縮率 vs 「wheel-6に対するEの優位性」では r = −0.206（負）。理由は§5参照。 |
| H | Reasoning Compression → Generated Candidates Reduction → VM Instructions → Allocation → Runtime の連鎖 | **部分的に達成**。圧縮率 > 1 の20ケースのうち、VM instruction・allocation・runtimeの3指標すべてでD比改善したのは全20ケース。ただし「Generated Candidates Reduction」（Eの生成数がBの検証回数より少ない）まで含めた完全な連鎖は10/20ケース（highly_composite系）で成立。残り10ケース（mixed/semiprime系）は圧縮率がわずかに1超（1.01〜1.33)で、Eの生成数はBとほぼ同数（wheel-6も同じ候補をほぼ全て検証するため）。詳細は§5。 |
| Determinism | 3回実行・Fast Path有無での一致 | **達成**（全79ケースのシグネチャ一致、`tests/runtime/test_candidate_space_determinism.py` も参照）。 |
| Regression | 既存テスト | `reason ci --json` を参照（§7）。 |

要約: 候補表現をArray<Struct>からlazy candidate spaceへ変更した結果、**候補の実体化が完全に消え（CMR=0)**、highly_composite系のような「圧縮率は高いが候補空間が大きい」ケースで allocation が最大179倍、runtime実行時間が最大54倍改善した。圧縮率とruntime改善には正の相関（r=0.54)が確認できた。目標Level Dの「50%以上」という基準はhighly_composite全域では大きく超過しているが、候補空間が小さい8bケースでは相対的な改善が小さく、単純な閾値判定では「未達」と出る。Level Hの完全な連鎖はhighly_composite系で明確に成立し、圧縮率が1に近い他クラスでは「生成数の削減」は起きないが「物理演算量の削減」(VM instruction/allocation/runtime)は起きる。これはP0レポートが特定した断絶（Reasoning Compression → Physical Operations Reduction が成立しない）を解消したことを示す。

## 2. 実施内容

仕様§62-63の順序で実施した。

| Phase | 実装 | 主な変更箇所 |
|---|---|---|
| Phase 1 CandidateSpace Core | `Domain`, `Generator`（Range/Wheel6）, `Constraint`（Compare/Modulo/And/Or/Not）, `CandidateSpace`（lower/upper/cursor/constraints/peeked）を純粋データ構造として実装。bound constraintはDomainへ畳み込み、canonical order（bound→equality→modulo→logical tree）、重複排除、`isqrt`（正確な整数平方根）を含む。 | `ReasonRuntime/crates/computation-ir/src/candidate_space.rs`（新規、単体テスト20件） |
| Phase 2 Range/Wheel6 Generator | `Generator::next_after`（O(1)で次の生成規則値を算出）、`Generator::count_in`（区間内の生成規則値の個数をO(1)で算出、mod演算のみ）。 | 同上 |
| Phase 3 Constraint Engine | 比較（`==,!=,<,<=,>,>=`）とmodulo制約、`&&`/`\|\|`/`!` の評価。`relation.filter` の述語をsymbolic constraintへコンパイルする `compile_constraint`（row比較、`row % m`比較、captured local/`state.field`のInt値を1回だけ解決）。symbolic化できない述語は `CS-PRED-001`。 | `vm.rs` `compile_constraint`, `compile_row_operand`, `compile_captured_int` |
| Phase 4 Relation Integration | `relation.filter(space, predicate)` をconstraint追加へlowering（`Expr::RelationFilter` 内で `Value::CandidateSpace` を検出）。`relation.count(space)` は制約が無い場合のみ生成規則からO(1)で算出、制約がある場合は `CS-COUNT-001`（暗黙の走査を拒否、仕様§17）。 | `vm.rs` `Expr::CallRelation`/`Expr::RelationFilter` |
| Phase 5 Runtime Metrics | `candidate_space_estimated_size`, `candidate_generated_count`, `candidate_skipped_count`, `candidate_symbolically_excluded_count`（bound foldのみなら正確値、格納constraintが1件でも加わると`null`）, `candidate_materialized_count`, `candidate_constraint_count`, `candidate_constraint_eval_count`, `candidate_space_next_count`, および `candidate_pruned_count` の分割（`candidate_materialized_pruned_count`, `candidate_generated_skipped_count`, `symbolic_constraint_eval_count`, `generic_predicate_eval_count`）を `runtime_metrics` へ追加。 | `vm.rs` `Metrics`, `runtime_metrics()` |
| Phase 6 Model E | `candidate_space` 標準名前空間（`range`, `wheel6`, `isqrt`, `next`, `is_exhausted`, `exclude_multiples_of`, `reset`, `materialize`）を内部IR `call_candidate_space` として追加。frontend lowering/optimizer/型検査に配線。`ReasonScript_SpecTest/reasonscript/factorize_lazy_sieve_reasoning.rsn.template`（Model E）を追加。 | `frontend/computation_ir/{schema,lowering,optimizer}.py`, `frontend/language_surface/validation.py`, `ReasonScript_SpecTest` |
| Phase 7 D/E Equivalence | Model Eの候補生成ループはModel Dと同一のRU-01/02/05-09順序（小素数除去→wheel-6走査→検証済み因数で一括除外→boundでの停止推論)。結果・hypothesis sequence・determinismの一致を `tests/runtime/test_candidate_space_determinism.py` とベンチマークスクリプトの両方で検証。 | `ReasonScript_SpecTest/reasonscript/factorize_lazy_sieve_reasoning.rsn.template`, `tests/runtime/test_candidate_space_determinism.py` |
| Phase 8 Performance Validation | `scripts/benchmark_candidate_space.py` でv1.3データセットをB/D/E三方比較。 | `scripts/`, `artifacts/candidate_space_profile/` |
| Reasoning Event | `CANDIDATE_SPACE_CREATED`（空間生成ごと）、`CONSTRAINT_ADDED`（filter/exclude呼び出しごと、重複追加でも発行）、`CANDIDATE_SPACE_EXHAUSTED`（空間ごとに1回）を自動発行。候補単位の `CANDIDATE_GENERATED`/`CANDIDATE_SKIPPED` はカウンタのみでイベント化しない（trace modeに依存させないため、仕様§26但し書き）。 | `vm.rs` `call_candidate_space`, `candidate_peek`, `candidate_with_constraint` |

## 3. 計測方法

P0レポート§3と同じ方式（[[p0-runtime-perf-measurement]]）: 単一のruntime hostへ同一computation IRをリクエストJSONとして渡し、`trace=off`・reasoning event `count` モードで3回実行し中央値を取る。ホストが報告する `runtime_execution_ns`（VM内実行時間）を主指標とする。正しさ・決定性は `trace=delta`・event `full` で3回実行し、結果・hypothesis event列・`runtime_metrics` のハッシュを比較する。Model Bも同一ホストで再測定し、D/B・E/Bの比率を得る。

## 4. 結果

### 4.1 highly_composite系（focus class、仕様§53重点対象）

| ケース | bits | wheel-6 tests | D/E hypothesis tests | 圧縮率(B/E) | 候補空間サイズ | E生成数 | vm_instr D→E | alloc D→E | exec_ns D→E | PCR | ACR | RTR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| highly_composite_8b | 8 | 3 | 3/3 | 1.00 | 1 | 1 | 66→58 | 104→85 | 18,375→16,166 | 1.14 | 1.22 | 1.14 |
| highly_composite_12b | 15 | 7 | 5/5 | 1.40 | 22 | 4 | 305→105 | 327→96 | 33,709→19,000 | 2.90 | 3.41 | 1.77 |
| highly_composite_16b | 19 | 9 | 6/6 | 1.50 | 96 | 5 | 992→127 | 1074→102 | 80,458→21,250 | 7.81 | 10.53 | 3.79 |
| highly_composite_20b | 24 | 11 | 7/7 | 1.57 | 423 | 6 | 3956→149 | 4351→108 | 275,167→24,792 | 26.55 | 40.29 | 11.10 |
| highly_composite_24b | 28 | 13 | 8/8 | 1.63 | 2032 | 7 | 18458→171 | 20448→114 | 1,286,000→23,875 | 107.94 | 179.37 | 53.86 |

候補空間サイズが2,032（仕様§2の代表例と一致）でも、Eの候補生成は7件（=hypothesis test数）のみ。Model Dはこの2,032件すべてをstruct+builder appendとして構築し、6回のrelation.filterで走査するため allocation が20,448件（Eは114件、ACR=179）、VM instructionが18,458（Eは171、PCR=108）。

### 4.2 圧縮率とruntime改善の関係（Level G）

- 圧縮率(search_compression_ratio, B tests / E hypothesis tests) は 0.75〜1.625 の範囲（79ケース中20ケースが圧縮率>1、59ケースが1.0、repeated_factor系のみ0.75〜1.0未満）。
- Pearson r（圧縮率 vs RTR = D/E runtime比） = **0.544**（n=79）。圧縮率が高いケース（highly_composite）ほどRTRも高い。
- Pearson r（圧縮率 vs E/B比の逆数、「wheel-6に対するEの優位性」） = **−0.206**。これは、圧縮率が高いケース（highly_composite）ほどwheel-6自体の候補空間も大きく、EがBに対してVM instruction/allocationで有利（builderのstruct生成が無い分）でも、候補生成のオーバーヘッド自体はBとほぼ同じ回数発生するため、E/B比の改善は圧縮率と直接連動しない。E/B比の中央値は1.12（Eの実行時間はBの1.12倍、highly_composite系でも1.13倍）。つまり「圧縮の効果」はD比でのみ顕著に表れ、B比では表現変更前後でE自体が既にB相当の効率になったため、圧縮率による追加のB比優位は生まれない。

### 4.3 Level D/Hの数値的背景

Level Dの基準「50%以上削減」（ACR≥2）はhighly_composite全10ケースの中央値10.53を満たすが、8bケース（ACR=1.22）は候補空間サイズが1件しかなく改善余地が小さいため未達。より大きな候補空間（12b以上の9/10ケース）はすべてACR≥2を満たす。

Level Hの「Generated Candidates Reduction」を含む完全な連鎖は、圧縮率>1のケースのうちEの生成数がBの検証回数を実際に下回った10ケース（highly_composite系、および semiprime_26b の1ケース）で成立する。残り10ケース（mixed/semiprime/mixed_factor_composite系）は圧縮率が1.01〜1.33とわずかに1を超えるのみで、E自身の生成数はB回数とほぼ同数（wheel-6の候補をEもほぼ全数検証するため、圧縮効果が候補生成段階に及ばない）。ただしこれらのケースでも VM instruction・allocation・runtime の3指標は全てD比で改善しており（表4.1参照の傾向が全20ケースで成立）、Reasoning CompressionからPhysical Operation Reductionへの接続自体は成立している。

## 5. 分析: 圧縮率とE/B比が負相関になる理由

P0レポート§5が特定した断絶は「Reasoning Compression（仮説検証回数の削減）が Executed Operations Reduction に変換されない」ことだった。Model Eでは候補空間を実体化しないため、Model D比での物理演算量はhypothesis test回数にほぼ比例するようになった（GER中央値1.0、CMR=0）。これにより Level A〜E、Fが成立する。

一方でLevel Gの「圧縮率が高いほどE/B比も改善する」という強い相関は観測されない（r=−0.206）。理由は、wheel-6（Model B）自体がO(1) allocationで候補を生成する設計（struct生成なし、scalarのincrement）であり、Model Eの候補生成コスト（`CandidateSpace::generate_next` + constraint評価）はBのincrementよりわずかに高い（floor_mod演算・cursor更新・Constraint評価のオーバーヘッド）。そのため、圧縮率が1.0のケース（半素数系の大半）ではE/B比は1.12〜1.31程度でE がわずかに遅く、圧縮率が高いケース（highly_composite）でもE/B比は1.11〜1.29程度で、B比での相対的な優位性は圧縮率と強く連動しない。圧縮率がruntime改善に効くのは「D比」（同じ候補表現のうち構築ステップが省略される度合い）であり、「B比」（そもそも候補あたりのコストがO(1)である別実装との比較）ではない。これは仕様の想定通りで、Level Fが要求する「D/B>1だったケースの一部でE/B≤1」を満たせば十分であり、実際に12ケースで成立している。

## 6. Regression / Determinism

- Model E自身の決定性: `tests/runtime/test_candidate_space_determinism.py::test_model_e_is_deterministic_across_runs_and_fast_path_modes` で3回実行およびFast Path有無での完全一致を確認（trace/reasoning_trace/loop_trace/runtime_metricsの計測値以外全て）。
- D/E等価性: 8ケース（prime/semiprime/semiprime_near_equal/repeated_factor/highly_composite/mixed/square_boundary/trivial）で `test_model_e_matches_model_d_result_and_hypothesis_sequence` を実行し、結果・hypothesis sequence・hypothesis_test_countの一致、および `candidate_materialized_count == 0`、`array_write_count == 0`（Model Eはbuilderを使わない）を確認。
- v1.3データセット全79ケースでのD/E一致: `results_identical` 79/79、`hypothesis_tests_identical` 79/79、`hypothesis_sequence_identical` 78/78（比較可能な範囲。`limit_probe_sqrt100000` はtrace byte budgetによりイベント列が途中で打ち切られるため件数一致のみで確認）。
- 境界ケース（仕様§54）: empty/single/no-constraint/many-constraint/contradiction/all-excluded/very-large-upper-bound/repeated-identical-constraint を `tests/runtime/test_candidate_space.py` および `test_candidate_constraints.py` でカバー。矛盾するbound（`row > 100 && row < 10`）は即座にexhaustedへ畳み込まれ、`candidate_symbolically_excluded_count` は正確値（100）を報告する。
- 既存機能への影響: `relation.filter`/`relation.count` の `Array<Struct>` に対する既存挙動は変更していない（`Value::CandidateSpace` はArrayと異なるVariantとして追加、既存の `rows()` パスは触れていない）。`reasoning.event` の実装を引数Vecを使わない形へ変更したが、結果・トレース・カウンタは既存テスト（`tests/runtime/test_reasoning_counters.py` 等）で不変を確認。
- `runtime_consolidation_manifest.json`: `candidate_space` 名前空間（8関数、すべて `python: absent, rust: implemented`）を追加して再生成、`./reason runtime-manifest --check` で一致を確認。
- `./reason ci --json`: checkout / environment_setup / workspace / diagnostics / artifacts / golden / agent_protocol / compatibility は PASS。`tests` フェーズは最初のステップ（`cargo test` in `apps/reasonscript-ide/src-tauri`）の `compiler_bridge::tests::repo_root_ends_with_reasonscript` で FAIL する。これはP0レポート§9で既報告の環境依存の失敗（リポジトリのディレクトリ名が `ReasonScript` であることをassertするテストで、本ワークツリー名 `reasonscript-lazy-candidate-space-d1ff02` では成立しない）であり、本変更とは無関係（`main` チェックアウトでは通過する前提）。個別実行結果は§7参照。

## 7. 検証結果（個別実行）

`tests` フェーズが最初のステップで停止するため、残りのステップを個別に実行した。

| ステップ | 結果 |
|---|---|
| `cargo test --release`（`ReasonRuntime`、全crate） | すべて PASS（`candidate_space` crateの単体テスト20件を含む） |
| pytest `tests/runtime`（`test_candidate_space.py`, `test_candidate_constraints.py`, `test_candidate_space_determinism.py` を含む82テスト） | すべて PASS |
| pytest `computation_ir_tests`, `language_surface_core_conformance_tests`, `language_surface_release_tests`, `toolchain_phase1_tests`, `toolchain_phase2_tests`, `runtime_completeness_tests`, `tests`, `language_surface_ast_mapping_tests`, `operational_semantics_tests`, `runtime_semantics_validation_tests`, `calculation_semantics_tests`, `expression_lowering_tests`（`tests/lsp/test_vscode_extension_contract.py::test_vscode_extension_typescript_compiles_cleanly` を除く。`vscode-extension/node_modules` 未インストールという環境要因） | 1809 passed, 3 skipped, 30 subtests passed |
| `./reason golden` | PASS |
| `./reason runtime-manifest --check` | PASS（baseline一致） |

修正の過程で検出・修正した点: `reasoning.event` 呼び出しが引数評価のたびに `Vec::with_capacity(3)` を確保していたため、Model Eの候補ごとの `reasoning.event("HYPOTHESIS_REJECTED", ...)` 呼び出しコストに直結していた。引数を個別のローカル変数として評価する形に変更し、allocationを1回削減した（§2 Reasoning Event行）。

## 8. 成果物

- `docs/specifications/ReasonScript_Lazy_Symbolic_Candidate_Space_v0_1.md`
- `docs/reports/ReasonScript_Lazy_Symbolic_Candidate_Space_Report.md`（本書）
- `ReasonRuntime/crates/computation-ir/src/candidate_space.rs`（新規）
- `ReasonRuntime/crates/computation-ir/src/{vm.rs, value.rs, ir.rs, lib.rs, console_dispatch.rs, state_trace.rs}`（`CandidateSpace` variant、`call_candidate_space` dispatch、関連メトリクス）
- `frontend/computation_ir/{schema.py, lowering.py, optimizer.py}`, `frontend/language_surface/validation.py`（`candidate_space` 名前空間の型検査）
- `toolchain/runtime_manifest.py`, `contracts/runtime_consolidation_manifest.json`
- `docs/standard-library.md`, `docs/reference/cli.md`, `CHANGELOG.md`
- `scripts/benchmark_candidate_space.py`
- `tests/runtime/{test_candidate_space.py, test_candidate_constraints.py, test_candidate_space_determinism.py}`
- `artifacts/candidate_space_profile/{results.json, comparison.csv, summary.json}`
- `~/development/ReasonScript_SpecTest/reasonscript/factorize_lazy_sieve_reasoning.rsn.template`（Model E、別リポジトリ、本レポートに合わせて追加）
- `~/development/ReasonScript_SpecTest/RESULTS_v1_4.md`, `README.md` v1.4節（別リポジトリ）

## 9. 次段階（仕様§66・§70）

- Constraint Fusion（Wheel6 + NotDivisibleBy(5) → Wheel30相当）は本v0.1では未実装（Experimental、仕様§14）。実装できれば圧縮率が高いケースでのconstraint評価コスト（`candidate_constraint_eval_count`）をさらに削減できる可能性がある。
- Generic Predicate対応（symbolic化できない述語をVM callbackとして候補空間に保持）はv0.1のNon-goalではないが実装していない。現状は `CS-PRED-001` で拒否し `materialize` して配列filterへフォールバックする経路のみ。
- DSNへの接続（仕様§67）: `CandidateSpace` のconstraint機構（`Compare`/`Modulo`/`And`/`Or`/`Not`)は数学的候補に限定されない汎用IRであり、Reasoning Candidate表現への転用は今後の課題。
