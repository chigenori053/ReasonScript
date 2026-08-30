# ReasonScript Controlled Recursion Specification v0.1 / 制御された再帰 仕様書 v0.1

- **Document ID / ドキュメントID:** `reasonscript-spec-controlled-recursion/0.1`
- **Phase / フェーズ:** Phase 4 — Controlled Recursion (制御された再帰)
- **Status / 状態:** Implemented / 実装完了
- **Date / 日付:** 2026-08-30

---

## 1. Overview / 概要

### English
This specification defines the syntax, static analysis semantics, and runtime execution contract for **Controlled Recursion** in ReasonScript. It lifts the legacy unconditional rejection (`FN-007`) and introduces:
1. Permissible direct (`f -> f`) and mutual (`f -> g -> ... -> f`) recursive function calls.
2. Static Call Graph analysis for cycle and recursion-kind detection.
3. Deterministic runtime call-depth bounding governed by `max_call_depth` (default: 128) with `RT-CALL-003` diagnostic enforcement across Python AST, Python IR, and native Rust VM hosts.
4. Guaranteed frame-liveness and root retention for Tensors and ReasonObject (RUO) resources across active caller/callee frames.

### 日本語
本仕様書は、ReasonScriptにおける「制御された再帰（Controlled Recursion）」の構文、静的解析セマンティクス、およびランタイム実行契約を定義します。旧来の無条件拒否（`FN-007`）を撤廃し、以下を導入・保証します：
1. 直接再帰（`f -> f`）および相互再帰（`f -> g -> ... -> f`）の関数呼び出しの許可。
2. 静的Call Graph（呼び出し関係グラフ）解析による閉路検出と再帰種別の分類。
3. `max_call_depth`（デフォルト: 128）によって制御される決定論的な呼び出し深さ制限と、上限超過時の安定した診断コード `RT-CALL-003` の発行（Python AST、Python IR、Rust VMホスト間での完全な挙動一致）。
4. 再帰フレーム間でのTensorおよびReasonObject（RUO）リソースの生存期間（Frame Liveness）とルート保持（Root Retention）の保証。

---

## 2. Syntax & Static Semantics / 構文と静的セマンティクス

### 2.1 Function Validation / 関数検証
- Recursive calls to functions declared within the current module or imported from sibling modules are fully validated against parameter types and return types.
- The former validation rule `FN-007` ("recursive function calls are rejected") is revised: direct and mutual recursive calls are permitted provided they type-check correctly.

### 2.2 Call Graph Analysis / 呼び出しグラフ解析
ReasonScript provides `analyze_call_graph(program: ProgramNode) -> CallGraphAnalysisResult`:
- **Callees / Callers**: Mapping of callers to their direct callees and vice-versa.
- **Direct Recursion**: Functions satisfying `f in callees[f]`.
- **Mutual Recursion**: Functions participating in call cycles of length > 1.
- **Cycles**: Canonical cyclic paths identified via DFS traversal.

---

## 3. Runtime Contract & Limits / ランタイム契約と制限

### 3.1 Call Depth Limit / 呼び出し深さ制限
- **Default Limit (`max_call_depth`)**: 128
- **Configuration**: Overridable via runtime request `context.limits.max_call_depth` or CLI/API parameters.
- **Exceeding Limit**: When `call_depth >= max_call_depth`, execution halts immediately and deterministically with:
  - Error Code: `RT-CALL-003`
  - Message: `function call depth exceeded: <max_call_depth>`

### 3.2 Resource Liveness Contract / リソース生存期間契約
1. **Caller-Root Protection**: Any Tensor or RUO resource held by a suspended caller frame remains rooted during all nested recursive callee evaluations and GC safe-points.
2. **Return Value Handoff**: Tensors or structures created in deeply nested recursive frames are cleanly handed off to caller frames upon return.
3. **Clean Error Unwinding**: Stack exhaustion (`RT-CALL-003`) or arithmetic/tensor runtime errors deep within a recursive chain cleanly release temporary frame resources without memory corruption or dangling pointers.

---

## 4. Diagnostic Code Reference / 診断コードリファレンス

| Code / コード | Category / 分類 | Description (English) | 説明 (日本語) |
|---|---|---|---|
| `RT-CALL-001` | Runtime / 実行時 | Unknown runtime function | 未知のランタイム関数 |
| `RT-CALL-002` | Runtime / 実行時 | Function argument count mismatch | 関数引数の個数不一致 |
| `RT-CALL-003` | Runtime / 実行時 | Function call depth exceeded | 関数呼び出し深さ上限超過 |
| `RT-CALL-004` | Runtime / 実行時 | Function returned no value | 関数が値を返さずに終了 |
| `FN-005` | TypeCheck / 型検査 | Function argument/return type mismatch | 関数の引数・戻り値型不一致 |
