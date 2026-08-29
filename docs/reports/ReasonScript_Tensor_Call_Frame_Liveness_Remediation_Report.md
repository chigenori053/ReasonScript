# ReasonScript Tensor Call-Frame Liveness Remediation Report
# ReasonScript Tensor コールフレーム生存性修正レポート

**Specification / 仕様書:** [`docs/specifications/ReasonScript_Tensor_Call_Frame_Liveness_Remediation_v0_1.md`](file:///Users/chigenori/development/ReasonScript/docs/specifications/ReasonScript_Tensor_Call_Frame_Liveness_Remediation_v0_1.md)  
**Status / 状態:** `VALIDATED`  
**Issue:** [GitHub #9](https://github.com/chigenori053/ReasonScript/issues/9)  
**Classification / 分類:** Rust computation VM Tensor-lifetime correctness remediation (v0.5.5 patch)  
**Distribution Status / 配布状況:** DEFERRED by scope decision (Repository fixed & validated; distribution package deferred)

---

## 1. Executive Summary / 要約

### English
This report confirms the resolution and verification of the Rust computation VM Tensor-lifetime correctness defect (GitHub Issue #9). Previously, garbage collection during user-function (callee) execution derived roots solely from the callee's local environment, causing live Tensors in suspended caller frames, prior calculation results, and evaluated arguments to be prematurely reclaimed and leading to false `TSF-001 unknown Tensor handle` errors upon function return.

With this remediation:
- The active frame environments are tracked using memory-safe `Rc<RefCell<HashMap<String, Value>>>` structures and RAII guards (`FrameGuard`), completely eliminating raw pointers and `unsafe` dereferencing blocks.
- Temporary roots (`TempRootGuard`) protect intermediate expressions, argument evaluations, and return-value handoffs.
- Retained prior calculation results are tracked safely in `active_calculations` without raw pointer reconstruction.
- Collection points compute the union of all active frame environments, retained calculation results, temporary roots, and native autograd states.
- Container traversal (`collect_tensor_ids`) safely traverses arrays and struct fields with cycle and pointer-aliasing protection (`visited_arrays`, `visited_structs`).
- The canonical regression fixture verbatim matches the Issue #9 LayerNorm-plus-attention pipeline (`random_normal([16, 32])`, `gamma`/`beta` [32], `wq` [32, 32], `bias` [16, 16], full LayerNorm ops, and full attention ops `linear` -> `narrow` -> `transpose` -> `matmul` -> `divide` -> `add` -> `softmax` -> `matmul` -> assert `[16, 16]`).
- All 13 required lifetime acceptance scenarios, `reason project-validate`, platform runner, and `reason ci` have fully passed.

### 日本語
本レポートは、Rust computation VM における Tensor 生存性（ライフタイム）の正確性に関する欠陥（GitHub Issue #9）の安全な修正と検証完了を報告するものです。従来、ユーザー定義関数（callee）の実行中に発生するガベージコレクションにおいて、現在実行中の callee のローカル環境のみから root set を導出していたため、呼び出し元（caller frame）で保持されている Tensor、過去の計算結果、評価中の引数・戻り値が誤って解放され、関数復帰後に `TSF-001 unknown Tensor handle` が発生していました。

本修正により：
- アクティブフレームの環境はメモリ安全な `Rc<RefCell<HashMap<String, Value>>>` および RAII ガード（`FrameGuard`）によって追跡され、生のポインタや `unsafe` な参照外しブロックは完全に排除されました。
- 一時ルート（`TempRootGuard`）により、中間式、引数評価リスト、関数戻り値のハンドオフを確実に保護します。
- 過去の計算結果は `active_calculations` により安全に管理されます。
- コレクション実行時は、全アクティブフレーム、計算結果、一時ルート、ネイティブ autograd 状態の Union から root set を構築します。
- コンテナ走査（`collect_tensor_ids`）では、ポインタ訪問管理（`visited_arrays`, `visited_structs`）により配列や構造体フィールドの循環参照・共有コンテナを安全に走査します。
- 正式な再現フィクスチャは、Issue #9 の LayerNorm と Attention パイプライン（`random_normal([16, 32])`、`gamma`/`beta` [32]、`wq` [32, 32]、`bias` [16, 16]、LayerNorm 演算群、および `linear` -> `narrow` -> `transpose` -> `matmul` -> `divide` -> `add` -> `softmax` -> `matmul` -> `[16, 16]` 形状アサーション）を完全に保持します。
- 仕様書で要求された 13 項目の生存性シナリオ、`reason project-validate`、プラットフォームテスト、`reason ci` の全通過を確認しました。

---

## 2. Safe Active-Frame Root Management Design / 安全なアクティブフレームルート管理の設計

```
+-------------------------------------------------------------------------+
|                                  Vm                                     |
|                                                                         |
|  active_frames: RefCell<Vec<Rc<RefCell<HashMap<String, Value>>>>>       |
|    |                                                                    |
|    +-- [0] Caller frame env (e.g. {h, gamma, beta, wq, bias})           |
|    +-- [1] Nested caller frame env                                      |
|    +-- [2] Callee frame env (e.g. LayerNorm local vars)                 |
|                                                                         |
|  active_calculations: RefCell<Vec<Value>>                               |
|    +-- Retained results from preceding calculations                     |
|                                                                         |
|  temporary_roots: RefCell<Vec<Value>>                                   |
|    +-- In-progress arguments, return value handoff, intermediate exprs  |
|                                                                         |
|  tensors: RefCell<TensorStore>                                          |
|    +-- autograd.live_tensor_ids() + roots -> safe retain / collect      |
+-------------------------------------------------------------------------+
```

### Key Safety Highlights / 主要な安全性
1. **Zero `unsafe` dereferencing:** Active frames and calculation vectors use managed reference types (`Rc<RefCell<...>>`), guaranteeing lifetime, ownership, and borrow safety directly through the Rust compiler.
2. **RAII root management:** `FrameGuard` and `TempRootGuard` guarantee deterministic cleanup across normal returns, error propagation (`?`), traps, recursion, and limits.
3. **Cycle-safe traversal:** `collect_tensor_ids` prevents infinite loops on shared/cyclic arrays and structs using `visited_arrays` and `visited_structs` pointer sets.

---

## 3. Changed Files & Components / 変更されたファイルおよびコンポーネント

| Component / コンポーネント | File / ファイル | Description / 変更内容 |
| :--- | :--- | :--- |
| **Rust Computation VM** | [`ReasonRuntime/crates/computation-ir/src/vm.rs`](file:///Users/chigenori/development/ReasonScript/ReasonRuntime/crates/computation-ir/src/vm.rs) | Safe active frame management with `Rc<RefCell<...>>`, RAII guards, calculation result roots, and zero `unsafe` dereferencing. |
| **Canonical Regression Fixture** | [`canonical_fixtures/issue_9_layernorm_attention/src/main.rsn`](file:///Users/chigenori/development/ReasonScript/canonical_fixtures/issue_9_layernorm_attention/src/main.rsn) | Verbatim Issue #9 LayerNorm & attention regression program. |
| **Liveness Test Suite** | [`computation_ir_tests/test_computation_ir_tensor_liveness.py`](file:///Users/chigenori/development/ReasonScript/computation_ir_tests/test_computation_ir_tensor_liveness.py) | Comprehensive 13-scenario test suite covering Issue #9 verbatim, caller-only roots, return handoffs, nested frames, recursion, error cleanup, trace parity, cross-calc retention, and limits. |
| **Specification** | [`docs/specifications/ReasonScript_Tensor_Call_Frame_Liveness_Remediation_v0_1.md`](file:///Users/chigenori/development/ReasonScript/docs/specifications/ReasonScript_Tensor_Call_Frame_Liveness_Remediation_v0_1.md) | Updated Status to `VALIDATED`. |

---

## 4. Validation Results / 検証結果

### 4.1 Exact Issue #9 Canonical Fixture Execution
- **Command:** `./reason run canonical_fixtures/issue_9_layernorm_attention/src/main.rsn --allow-read --allow-write`
  ```
  ReasonScript run passed
  file: canonical_fixtures/issue_9_layernorm_attention/src/main.rsn
  goal_reached: true
  trace_steps: 18
  knowledge_items: 7
  ```
- **Command (JSON):** `./reason run canonical_fixtures/issue_9_layernorm_attention/src/main.rsn --allow-read --allow-write --json`
  - Output calculation result: `true` (`tensor.shape(context) == [16, 16]`).
  - Diagnostic count: 0 (No `TSF-001` or `TSF-013`).

### 4.2 Project Validation
- **Command:** `./reason project-validate canonical_fixtures/issue_9_layernorm_attention`
  ```
  Project validation passed.
  Sources: 1/1
  ```

### 4.3 Focused 13 Lifetime Scenarios Matrix
- **Command:** `python3 -m pytest computation_ir_tests/test_computation_ir_tensor_liveness.py -v`
  - `test_01_exact_issue_9_fixture`: **PASSED** (verbatim fixture via Rust host)
  - `test_02_caller_only_root_regression`: **PASSED** (caller-only tensor survives callee)
  - `test_03_return_value_handoff_and_safe_points`: **PASSED** (direct, nested, array, struct returns across collection)
  - `test_04_at_least_three_nested_active_frames`: **PASSED** (deep nested call chain)
  - `test_05_bounded_recursive_call`: **PASSED** (bounded recursive calls preserving caller tensor)
  - `test_06_earlier_evaluated_arg_survives_later_arg_eval`: **PASSED** (argument list evaluation liveness)
  - `test_07_cleanup_after_normal_return_and_runtime_error`: **PASSED** (frame cleanup on error unwind)
  - `test_08_trace_disabled_and_enabled_parity`: **PASSED** (trace parity)
  - `test_09_shared_and_cyclic_containers`: **PASSED** (cyclic and shared container traversal)
  - `test_10_cross_calculation_tensor_handle_retention`: **PASSED** (cross-calculation Tensor handle retention)
  - `test_11_incremental_reclamation_long_loop`: **PASSED** (1,100 iteration loop reclamation)
  - `test_12_explicit_proof_unreachable_intermediates_removed`: **PASSED** (intermediates removed under tight budget)
  - `test_13_genuine_max_live_tensors_exhaustion_emits_tsf013`: **PASSED** (genuine limit enforcement)

### 4.4 Cargo Workspace Tests
- **Command:** `cargo test --manifest-path ReasonRuntime/Cargo.toml` -> **All 33 tests passed across all crates**.

### 4.5 Full CI Pipeline
- **Command:** `./reason ci` -> **PASS across all 9 phases (checkout, environment_setup, workspace, diagnostics, artifacts, golden, agent_protocol, compatibility, tests)**.

---

## 5. Explicit Distribution Deferral / 配布タスクの明示的延期

This remediation is complete and validated in repository source code. Building an install archive, updating `~/.reasonscript`, and verifying installed packages are explicitly deferred to a separate distribution task. The repository does not claim installed v0.5.5.5 contains this fix until the deferred distribution phase is executed.
