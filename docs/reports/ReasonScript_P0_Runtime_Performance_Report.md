# ReasonScript P0 Runtime Performance Report

- 対象仕様: [ReasonScript_P0_Runtime_Performance_v1_0.md](../specifications/ReasonScript_P0_Runtime_Performance_v1_0.md)
- 修正前: ReasonScript v0.5.5.15 `reason-runtime-host`（`~/.reasonscript/versions/0.5.5.15/bin/reason-runtime-host`）
- 修正後: 本ブランチの `ReasonRuntime/target/release/reason-runtime-host`
- データセット: ReasonScript_SpecTest v1.3 `get_dataset()` の79ケース（stage1 10、scaling 60、stage5 1、sqrt probe 8）。プログラム（Model A/B/D）は v1.3 のものを無変更で使用。
- 再現: `python3 scripts/benchmark_p0_runtime.py --samples 3 --cli-samples 1 --out artifacts/runtime_profile`
- 生成物: `artifacts/runtime_profile/{baseline.json, optimized.json, comparison.csv, summary.json}`
- 計測日: 2026-09-18、Apple Silicon（macOS）、release build

## 1. 結論

| Level | 内容 | 判定 |
|---|---|---|
| P0-A | 固定10,000 loop limitによる不要停止の解消 | **達成**。修正前に `RT-LOOP-001` で停止した5ケース（sqrt 30k〜100k）がすべて完走。 |
| P0-B | Model Dの結果・推論イベント・pruning結果の一致 | **達成**。比較可能な74ケースすべてで結果、`reasoning_trace`、`loop_trace`、pruning件数が修正前とバイト一致。 |
| P0-C | Model D wall time 20%以上短縮 | **Runtime実行時間では達成、プロセス全体wall timeでは未達**。VM内実行時間（`runtime_execution_ns`）は実行が1ms以上の12ケースで中央値1.98倍高速。host process wall time は同12ケースで中央値1.45倍（1.23〜1.67倍）。79ケース全体の中央値は1.03倍で、これは入力が小さいケースの wall time（約2.3ms）がプロセス起動とリクエストJSONデコードで占められるため。 |
| P0-D | Model D が wheel-6 と同等以下の wall time を1ケース以上 | **形式的には達成、実質的には未達**。VM内実行時間で D ≤ B となるのは `basic_*` と `repeated_*`（2のべき乗）の16ケースのみで、いずれも候補空間の構築が発生しない自明なケース。候補空間を持つすべてのケースで D は B の1.4〜60倍。 |
| P0-E | 探索圧縮率と wall time 改善率の正の相関 | **未達**。Pearson r = 0.02（圧縮率 vs 修正前後の改善率）、r = −0.31（圧縮率 vs wheel-6 に対する実行時間優位）。 |
| P0-F | 推論圧縮の実時間上の優位性 | **未達**。 |
| Determinism | 3回実行の一致 | **達成**（全79ケース、B/D とも）。 |
| Regression | 既存テスト | `reason ci` を参照（§7）。 |

要約すると、Runtime の単位コスト（P0-1/P0-3）は約2倍改善し、固定loop limit（P0-2）は解消したが、Model D の実行時間は**仮説検証の回数ではなく候補空間の物理的な構築量**に支配されているため、探索圧縮が実時間短縮に変換されなかった。詳細は §5。

## 2. 実施内容

仕様§31の順序で実施した。すべて Rust host（`ReasonRuntime/crates/computation-ir`, `runtime-cli`）と CLI 配線の変更で、アルゴリズム・言語仕様・IR JSON スキーマは変更していない。

| Phase | 実装 | 主な変更箇所 |
|---|---|---|
| P0-1 Measurement | `runtime_metrics` に native counter を追加（`vm_instruction_count`, `reasoning_step_count`, `reasoning_event_count`, `reasoning_event_type_counts`, `hypothesis_test_count`, `candidate_pruned_count`, `relation_dispatch_count`, `relation_filter_count`, `relation_filter_rows_scanned`, `relation_predicate_eval_count`, `relation_count_count`, `array_read_count`, `array_write_count`, `struct_field_read_count`, `struct_field_write_count`, `allocation_count`, `allocated_bytes`, `peak_live_bytes`, `state_transition_count`, `branch_count`, `loop_iteration_count`, `fast_path_count`, `runtime_execution_ns`）。`--profile-runtime` で `predicate_execution_ns`, `relation_execution_ns`, `reasoning_event_ns`, `trace_execution_ns` を追加。allocation は global allocator（`alloc_counter.rs`）で実測。`allocation_ns` は allocator 内で安価に計測できないため未実装。 | `vm.rs` `Metrics`, `alloc_counter.rs`, `main.rs` |
| P0-2 Execution Budget | `DEFAULT_MAX_LOOP_ITERATIONS` を削除し `ExecutionBudget { max_loop_iterations, max_reasoning_steps, max_vm_instructions, max_wall_time_ms, max_allocated_bytes }` を導入。停止優先順位は wall time → memory → VM instruction → reasoning step → loop iteration。`RT-BUDGET-001..005` と `termination_reason` を結果に出力（失敗時も `runtime_metrics` を同梱）。CLI `--max-*`、`reason.toml [runtime]` に対応。`reason run` は既定で `REASONSCRIPT_RUNTIME_TIMEOUT`（30s）を wall time budget として渡す。 | `vm.rs`, `main.rs`, `runtime_dispatch.py`, `manifest.py`, `__main__.py`, `reason_cli.py` |
| P0-3 relation.count Fast Path | `relation.count(Array<Struct>)` を配列長へ短絡（先頭要素の型のみ検査、型検査済みの同種配列を前提。非同種の偽造IRのみ Generic Path と差が出る）。 | `vm.rs` `CallRelation` |
| P0-3 Array/Struct access | env・struct field・block map を FxHash（`value::FxHasher`）へ変更。代入は `get_mut` によるin-place上書き（代入ごとのキーString確保を削除）。 | `value.rs`, `vm.rs` |
| P0-4 Predicate Fast Path | `row.field <op> value`, `row.field % m <op> value`, `&&`/`\|\|`/`!`、捕捉変数と `state.field` を1回解決してコンパイルする `FastPredicate`。happy path を外れる行は Generic Path で再評価するため診断は同一。行バインディングは呼び出しフレームにin-placeで設置・復元（フレーム全体のcloneを廃止）。 | `vm.rs` |
| P0-5 reasoning.event | `ReasoningEventMode::{Off, Count, Full}`（`--reasoning-events`、`context.reasoning.event_mode`）。`Count` はイベント種別カウンタのみ、イベントJSONは `Full` かつ trace 有効時にのみ遅延生成。既定は trace 有効なら `full`、無効なら `count`（従来挙動と同一）。`--trace=summary` を追加。 | `vm.rs` `semantic_event`, `state_trace.rs` |
| P0-6 Allocation | 文字列リテラルの `Rc<str>` を Expr ノードにキャッシュ、ブロック訪問カウンタ（`HashMap<String,u64>` と `to_string()`）を削除、tensor が無いときの temporary root push を省略、結果出力を `BufWriter` 経由に変更。 | `ir.rs`, `vm.rs`, `main.rs` |
| P0-7 Re-validation | `scripts/benchmark_p0_runtime.py` で v1.3 データセットを修正前後の host で再実行。 | `scripts/`, `artifacts/runtime_profile/` |

## 3. 計測方法

- **Runtime 計測（仕様§23の標準）**: `trace=off`、reasoning event `count`。同一の computation IR（本ブランチの frontend で lowering。frontend の lowering は本修正で変更していない）をリクエストJSONとして両 host に渡し、プロセス起動から終了までの wall time を Python 側で3回計測して中央値を取る（`wall_time_ms`）。修正後 host は VM 内の実行時間 `runtime_execution_ns` も報告する。CPU 時間と peak RSS は `/usr/bin/time -l` による追加1回。
- **正しさ・決定性**: `trace=delta`、event `full` で3回実行し、結果・`reasoning_trace`・`loop_trace`・pruning件数・`termination_reason` のハッシュを比較。修正前 host の同モード出力と比較して P0-B を判定。
- **v1.3 互換の参考値**: `reason run file.rsn --trace=off --json`（Python CLI 経由）の wall time を各1回。
- 修正前 host は 10,000 loop cap の既定値のまま実行（それが「修正前」の状態であるため）。修正後は loop limit なし、`max_wall_time_ms=60000`。

## 4. 結果

### 4.1 P0-A: loop limit

| ケース | sqrt(N) | 修正前 | 修正後（host wall / VM 実行） |
|---|---|---|---|
| limit_probe_sqrt30000 | 30,010 | `RT-LOOP-001` | 完走 16.3 ms / 12.0 ms |
| limit_probe_sqrt40000 | 40,010 | `RT-LOOP-001` | 完走 21.2 ms / 15.8 ms |
| limit_probe_sqrt50000 | 50,020 | `RT-LOOP-001` | 完走 25.4 ms / 20.9 ms |
| limit_probe_sqrt70000 | 70,000 | `RT-LOOP-001` | 完走 33.3 ms / 27.9 ms |
| limit_probe_sqrt100000 | 100,000 | `RT-LOOP-001` | 完走 45.7 ms / 39.2 ms |

補足: sqrt ≈ 1,000,000（N = 1000003 × 1000033、666,674 loop iterations）でも修正後 host は 378 ms（修正前 host に `max_loop_iterations=10,000,000` を与えた場合 712 ms）で完走する。

### 4.2 P0-C/P0-D: wall time（VM 実行が 1 ms 以上のケース）

| ケース | bits | wheel-6 tests | sieve tests | 圧縮率 | D 修正前 → 修正後 (ms, host wall) | 改善 | D VM実行 (ms) | B VM実行 (ms) | D/B (VM) |
|---|---|---|---|---|---|---|---|---|---|
| prime_24b | 24 | 1182 | 1182 | 1.00 | 5.26 → 4.18 | 1.26× | 1.31 | 0.43 | 3.06 |
| semiprime_near_equal_24b | 24 | 1182 | 1182 | 1.00 | 5.71 → 4.07 | 1.40× | 1.35 | 0.45 | 3.01 |
| highly_composite_24b | 28 | 13 | 8 | 1.63 | 5.84 → 3.99 | 1.46× | 1.36 | 0.023 | 60.3 |
| mixed_24b | 24 | 78 | 77 | 1.01 | 4.21 → 3.45 | 1.22× | 0.78 | 0.041 | 19.3 |
| prime_26b | 26 | 2364 | 2364 | 1.00 | 8.43 → 5.30 | 1.59× | 2.60 | 0.88 | 2.96 |
| semiprime_near_equal_26b | 26 | 2367 | 2367 | 1.00 | 8.11 → 5.61 | 1.45× | 2.64 | 0.88 | 3.01 |
| highly_composite_26b | 28 | 13 | 8 | 1.63 | 5.98 → 4.57 | 1.31× | 1.39 | 0.026 | 53.3 |
| stage5_boundary | 27 | 3335 | 3335 | 1.00 | 10.38 → 6.64 | 1.56× | 3.71 | 1.23 | 3.01 |
| limit_probe_sqrt15000 | 28 | 5004 | 5004 | 1.00 | 14.23 → 9.00 | 1.58× | 5.64 | 1.88 | 3.01 |
| limit_probe_sqrt20000 | 29 | 6670 | 6670 | 1.00 | 18.21 → 10.91 | 1.67× | 7.74 | 2.48 | 3.12 |
| limit_probe_sqrt25000 | 30 | 8337 | 8337 | 1.00 | 22.18 → 13.37 | 1.66× | 9.79 | 3.09 | 3.17 |
| limit_probe_sqrt100000 | 34 | 33334 | 33334 | 1.00 | LOOP_LIMIT → 45.71 | – | 39.2 | 12.7 | 3.09 |

host wall time にはプロセス起動・リクエストデコード・結果出力の約2.3 ms（修正前後で同じコード）が含まれる。これを差し引いた VM 実行時間の修正前後比（導出値: 修正前 wall − 修正後の非VM時間）は上記12ケースで中央値 **1.98×**（1.67〜2.36×）。

### 4.3 単位コスト（修正後）

| ケース | モデル | loop iteration あたり | VM instruction あたり | allocation 回数 |
|---|---|---|---|---|
| limit_probe_sqrt25000 | B (wheel-6) | 376 ns | 37.5 ns | 123 |
| limit_probe_sqrt25000 | D (sieve) | 578 ns | 57.8 ns | 91,845 |
| limit_probe_sqrt100000 | B | 375 ns | 37.5 ns | 123 |
| limit_probe_sqrt100000 | D | 588 ns | 58.8 ns | 366,804 |
| highly_composite_24b | D | 685 ns | 75.9 ns | 20,457 |

修正前の D は sqrt25000 で約1.1 µs / iteration（sample profile: SipHash 26%、malloc/free 24%、tree-walk dispatch 18%）。修正後の残余コストは tree-walking dispatch と、D 固有の1候補あたり1 struct（HashMap 1つ + key String 1つ）の allocation。

### 4.4 問題クラス別（修正後、各クラスの中央値）

| problem_class | n | 圧縮率 (B tests / D tests) | D/B VM 実行比 | CTE | POS (VM instr / reasoning step) | RCRS (ns / step) |
|---|---|---|---|---|---|---|
| prime | 10 | 1.00 | 2.40 | 0.42 | 20.0 | 1,188 |
| semiprime | 10 | 1.00 | 3.71 | 0.28 | 42.3 | 5,024 |
| semiprime_near_equal | 19 | 1.00 | 3.01 | 0.33 | 20.0 | 1,186 |
| repeated_factor_composite | 10 | 1.00 | 0.79 | 1.27 | 7.4 | 1,032 |
| highly_composite | 10 | 1.50 | 4.56 | 0.33 | 90.2 | 7,841 |
| mixed_factor_composite | 10 | 1.02 | 4.98 | 0.21 | 66.3 | 5,416 |
| mixed (basic_*) | 10 | 1.00 | 0.94 | 1.06 | 14.5 | 4,093 |

CTE > 1 は候補空間の構築が発生しない `repeated`（2のべき乗）と `basic_*` のみ。圧縮率が最も高い `highly_composite` で POS が最大（1候補も検証していない 2,032 候補の構築と 8,583 行の predicate 走査が VM instruction を占める）。

### 4.5 trace=delta と CLI 経由の wall time（参考）

- `trace=delta`（v1.3 の計測モード）の host wall time は修正前後で変化なし（中央値比 1.00）。例: highly_composite_24b 145 → 147 ms、limit_probe_sqrt25000 626 → 626 ms。delta モードのコストは state trace の JSON 化・SHA-256・出力（sqrt25000 で 17 MB）であり、VM 実行ではない。`--profile-runtime` の `trace_execution_ns` で分離して測れる。
- `reason run --trace=off --json`（Python CLI 経由）は全ケースで約175 ms が Python 側の起動・parse・lowering・JSON 出力で占められ、runtime 改善（数ms）は観測できない（中央値比 1.00）。v1.3 が観測した「D は B の 1.03〜3.4 倍」の大部分はこの固定費と trace=delta のペイロードであり、VM 単体では D/B は 3 倍前後（半素数）〜60 倍（highly composite）。

## 5. 分析: なぜ探索圧縮が実時間に変換されないか

Model D の物理的な処理量は次の3項の和で、仮説検証回数はそのうち最小の項にしか効かない。

1. 候補空間の構築: wheel-6 間隔で `sqrt(remaining)` までの候補を `array.builder()` に materialize する。候補1つにつき struct 1個（HashMap + key String の allocation）と loop iteration 1回。highly_composite_24b では 2,032 候補 / 2,047 iterations。
2. 一括 pruning: 検証された因数ごとに `relation.filter` が残候補全体を走査する。highly_composite_24b では 6 回のフィルタで 8,583 行（Fast Path で 27 ns/行、合計 0.23 ms）。
3. 仮説検証: `HYPOTHESIS_VERIFIED/REJECTED` イベントと剰余判定。highly_composite_24b では 8 回。

`--profile-runtime` による highly_composite_24b の内訳: VM 実行 1.44 ms のうち relation 0.23 ms、reasoning event 0.0005 ms、残り約 1.2 ms（83%）が候補構築ループ。wheel-6 は同じ問題を 13 iterations（0.023 ms）で終える。つまり探索圧縮は「検証回数」を 13 → 8 に減らすが、「実行された物理演算」は候補空間サイズ O(√N) で決まり、これは圧縮率と無関係。仕様§4 の連鎖のうち Reasoning Compression → Executed Operations Reduction が成立していない。

半素数クラスでは D と B の検証回数は同じ（圧縮率 1.0）で、D は構築ループ + 走査ループの 2 パス（loop iteration が B の 2 倍）に加え候補ごとの struct allocation を払うため、VM 実行で 3 倍。これは Runtime の dispatch コストではなく表現のコスト（配列・struct で候補を持つ）である。

Runtime 側で残るコストは tree-walking dispatch（37〜58 ns / VM instruction）で、Fast Path 導入後も支配的。

## 6. Regression / Determinism

- Fast Path と Generic Path（`context.fast_path=false`）: 8 プログラム × 2 trace モードで結果・`reasoning_trace`・`loop_trace`・全カウンタが一致（`tests/runtime/test_fast_path_equivalence.py`、`scripts` 実行時の同等性チェック）。
- 修正前 host との一致: 74 ケースで結果・イベント列・state trace・`trace_bytes` がバイト一致。
- 決定性: 全 79 ケース、B/D とも 3 回の署名が一致。`runtime_metrics` のうち時間・メモリ値（`*_ns`, `allocation_count`, `allocated_bytes`, `peak_live_bytes`）は `toolchain.runtime_dispatch.MEASUREMENT_METRIC_KEYS` として決定性ハッシュから除外（仕様§29）。
- 出力の決定性: `reason run --json` の既定出力は ACC-10（execution determinism）とソース／インストール版パリティで byte 一致が要求されるため、時間・メモリ系の値（`runtime_execution_ns`, `*_ns`, `allocation_count`, `allocated_bytes`, `peak_live_bytes`）は `--profile-runtime` 指定時のみ CLI 出力に含める。host エンベロープ（`metadata.runtime_metrics`）は常に全値を報告し、本レポートの計測はそこから取得している。仕様§7 は allocation counter を標準 counter としているが、値がプロセス環境（パス長など）に依存するため CLI 既定出力からは除外した（§29 の除外方針と整合）。
- 互換性: `RT-LOOP-001` は `RT-BUDGET-005` に置換（`toolchain_phase1_tests` の該当テストを更新、CHANGELOG 記載）。`runtime_metrics` の既存キーは維持。結果エンベロープの `metadata` に `termination_reason` と（失敗時も）`runtime_metrics` を追加。
- 新規テスト: `tests/runtime/`（execution budget 8、counters 3、fast path equivalence 15、event modes 7）。
- `reason ci --json`: 本レポート末尾の「検証結果」を参照。

## 7. 仕様§34 に基づく判断

- Runtime 単位コスト（P0-1/P0-3/P0-6）: **ケースA**。同一プログラムの VM 実行時間が約 2 倍短縮し、counter は取得可能。
- 推論圧縮 → 実時間（P0-E/P0-F）: **ケースC**。Reasoning steps ↓ に対して Runtime cost は候補空間サイズに支配されるため ≈ または ↑。Model D の候補表現（静的 wheel-6 空間の materialize）は、圧縮率に関わらず O(√N) の構築演算を先払いする。次段階は Runtime ではなく推論表現側の再検討が必要: 候補空間を配列として実体化せず、遅延生成（生成器・区間表現）や `relation.filter` の述語を候補生成に融合する形にすれば、物理演算が仮説検証回数に比例する。これは仕様§5（アルゴリズム・DSL の変更）の範囲外のため本 P0 では実施していない。
- ケースD の観点: Fast Path 導入後も VM instruction あたり 37〜58 ns の tree-walking dispatch が残余コストの主因であり、更なる Runtime 高速化には bytecode 化（変数の slot 解決、演算子の enum 化）が次候補。

## 8. 成果物

- `docs/specifications/ReasonScript_P0_Runtime_Performance_v1_0.md`
- `docs/reports/ReasonScript_P0_Runtime_Performance_Report.md`（本書）
- `artifacts/runtime_profile/baseline.json`, `optimized.json`, `comparison.csv`, `summary.json`
- `scripts/benchmark_p0_runtime.py`
- `tests/runtime/test_execution_budget.py`, `test_reasoning_counters.py`, `test_fast_path_equivalence.py`, `test_reasoning_event_modes.py`
- `ReasonRuntime/crates/computation-ir/src/{vm.rs, value.rs, ir.rs, state_trace.rs, alloc_counter.rs}`, `runtime-cli/src/main.rs`
- `frontend/computation_ir/rust_bridge.py`, `toolchain/{runtime_dispatch.py, run_cmd.py, runner_cmd.py, manifest.py, __main__.py, project_validation.py}`, `scripts/reason_cli.py`
- `docs/reference/cli.md`, `docs/standard-library.md`, `CHANGELOG.md`

## 9. 検証結果

`./reason ci --json`（2026-09-18、本ワークツリー）: checkout / environment_setup / workspace / diagnostics / artifacts / golden / agent_protocol / compatibility は PASS。`tests` フェーズは最初のステップ `cargo test`（`apps/reasonscript-ide/src-tauri`）の `compiler_bridge::tests::repo_root_ends_with_reasonscript` で FAIL する。このテストはリポジトリのディレクトリ名が `ReasonScript` であることを assert しており、git worktree（`.claude/worktrees/pytest-cleanup-files-de05aa`）では成立しない。本修正とは無関係で、`main` チェックアウトでは通過する前提のもの。

`tests` フェーズが最初のステップで停止するため、残りのステップを個別に実行した。

| ステップ | 結果 |
|---|---|
| `cargo test`（`ReasonRuntime`、全 crate） | すべて PASS（computation-ir 14、tensor-core 等） |
| pytest `unit` グループ（`tests` を含む） | 1353 passed, 3 skipped, 1 failed: `tests/lsp/test_vscode_extension_contract.py::test_vscode_extension_typescript_compiles_cleanly`（`vscode-extension/node_modules` 未インストールのため `tsc` が `vscode` 型定義を解決できない。環境要因） |
| pytest `integration` グループ | 1 failed: `vscode_extension_phase1_4_tests ... test_vsxp14_003_dependency_presence`（同じく `node_modules` 未インストール） |
| pytest `regression` / `golden` / `compatibility` / `playground` グループ | すべて PASS |
| 新規 `tests/runtime`（33 テスト） | PASS |
| `toolchain_phase1_tests`（`RT-BUDGET-005` へ更新した L-010 テストを含む）、`computation_ir_tests`、`runtime_completeness_tests`、`tests/tensor_integration`、`tests/cli/test_current_runtime_contract.py`、ACC-10 決定性、インストール版パリティ | PASS |

修正の過程で検出・修正した regression: (1) 計測値を含む `runtime_metrics` により `reason run --json` の出力が実行ごと／インストール先ごとに変化し ACC-10 とインストール版パリティが失敗 → CLI 既定出力から計測値を除外（§6）。(2) `project_validation` の決定性ハッシュ → 同じ除外を適用。
