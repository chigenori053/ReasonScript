# ReasonScript Execution-Based Test Framework Specification v0.1
# ReasonScript 実行型テストフレームワーク仕様書 v0.1

- **Spec ID / 仕様ID:** `reasonscript-spec-test-framework/v0.1`
- **Status / 状態:** APPROVED / 確定
- **Target / 対象:** Toolchain (`reason test`), Language Surface, Computation IR (0.2), Rust VM Host

---

## 1. Overview / 概要

### English
This specification defines the execution-based testing mechanism for ReasonScript. Previously, `reason test` only performed static compilation and validation without executing code, which could incorrectly report failing runtime logic as `PASS`. Under this specification, `reason test` natively executes tests on the Rust host or Computation IR VM, introduces language-level assertion primitives (`assert`, `assert_eq`), categorizes failures into distinct error classes (`COMPILE_ERROR`, `ASSERTION_FAILURE`, `RUNTIME_ERROR`), and supports structured JSON/JUnit output formats.

### 日本語
本文書は、ReasonScriptにおける実行型テスト機構の仕様を定義します。旧来の `reason test` はコードを実行せず静的コンパイル・検査のみを行っていたため、実行時エラーやアサーション不成立を含むコードでも `PASS` と報告される課題がありました。本仕様では、テストファイルを Rust ホストまたは Computation IR VM 上で実際に実行し、言語組み込みのアサーション構文（`assert`, `assert_eq`）を提供、失敗要因を明確に分類（`COMPILE_ERROR`, `ASSERTION_FAILURE`, `RUNTIME_ERROR`）するとともに、CI連携用の JSON および JUnit XML 出力をサポートします。

---

## 2. Assertion Primitives / アサーション組み込み構文

| Primitive / 構文 | Signature / シグネチャ | Diagnostic on Failure / 失敗時診断コード |
| :--- | :--- | :--- |
| `assert(cond)` | `assert(cond: bool) -> bool` | `TEST-ASSERT-001` (`assertion failed`) |
| `assert_eq(a, b)` | `assert_eq(a: T, b: T) -> bool` | `TEST-ASSERT-001` (`assertion failed: left != right`) |

---

## 3. CLI Command Contract / CLI コマンド規約

- `reason test`: デフォルトで全テストファイルを検出・コンパイル・実行。全テスト成功時終了コード `0`、失敗時 `3`。
- `reason test --compile-only`: 旧来互換の静的コンパイル検査のみを実行（実行はスキップ）。
- `reason test --json`: 構造化テスト結果（`{"ok": bool, "passed": [...], "failed": [...]}`）を標準出力に出力。
- `reason test --junit <path>`: JUnit XML 形式のテストレポートを指定パスに書き出し。
