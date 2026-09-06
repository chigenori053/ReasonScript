# OSS Handwritten Acceptance & Compatibility Verification Specification
# OSS 手書き利用の統合受入・互換性検証仕様書

## Overview / 概要

### English
This document defines the Release Gate acceptance criteria and verification protocol for ReasonScript OSS handwritten developer experience (RS-DXLI-001, Issue #51). It establishes a machine-executable matrix that determines whether ReasonScript satisfies all P0, P1, and Phase 1/Phase 2 LSP requirements for an Experimental / Early Alpha public release.

### 日本語 (Japanese)
本文書は、ReasonScript の OSS 手書き開発者体験（RS-DXLI-001, Issue #51）におけるリリース判定ゲート（Release Gate）の受入基準および検証プロトコルを定めます。ReasonScript が Experimental / Early Alpha 公開に必要なすべての P0、P1、および Phase 1/Phase 2 LSP 要件を満たしているかを機械的かつ客観的に判定するための受入マトリクスを規定します。

---

## Acceptance Matrix / 自動受入マトリクス

| ID | Category / 分類 | Description (EN) | 説明 (JA) | Automated Test / 検証方法 |
|---|---|---|---|---|
| **ACC-01** | Zero-Config Workflow | `reason init` creates only `.rsn` files, and `init` -> `check` -> `build` -> `run` succeeds immediately out-of-the-box. | `reason init` が `.rsn` のみを生成し、初期化直後に `init` → `check` → `build` → `run` がゼロ設定で即座に成功する。 | `test_init_workflow_zero_config` |
| **ACC-02** | VS Code Extension Scope | Extension strictly targets `.rsn` and never binds to `.re` / `.res` files. | VS Code 拡張が `.rsn` のみを対象とし、`.re` や `.res` などの他言語拡張子を横取りしない。 | `test_vscode_extension_scope_isolation` |
| **ACC-03** | Diagnostic Coverage | Compiler emits actionable diagnostics for missing module, missing manifest, unsupported extensions, ReScript syntax, and `Js.*` APIs. | missing module, missing manifest, 旧拡張子, ReScript 構文, `Js.*` API に対し、具体的で修正可能な診断を発行する。 | `test_actionable_diagnostics_coverage` |
| **ACC-04** | CLI / LSP Parity | CLI (`reason check`) and LSP (`CompilerFrontend`) produce identical diagnostic codes, ranges, and severities. | CLI と LSP で診断コード、範囲（行・列）、重大度が完全に一致する（パリティ保証）。 | `test_cli_and_lsp_diagnostic_parity` |
| **ACC-05** | LSP Lifecycle & Standalone | LSP reliably processes `didOpen`, `didChange`, `didSave`, supports standalone `.rsn` files, and recovers gracefully from errors. | LSP が文書変更イベントを正確に処理し、ワークスペース外スタンドアロンファイルに対応し、エラーから安全に復旧する。 | `test_lsp_lifecycle_and_standalone` |
| **ACC-06** | LSP Navigation & Editing | Hierarchical Document Symbols, Hover markdown, Go to Definition, Rename, and Formatting operate reliably. | 階層シンボル、ホバー、定義ジャンプ、リネーム、フォーマットが仕様通り確実に動作する。 | `test_lsp_navigation_and_editing` |
| **ACC-07** | Standard Output API | `print` / `Console.log` route to stdout, `Console.warn` / `Console.error` route to stderr, preserving order and stringification. | `print`/`Console.log` は stdout、`Console.warn`/`Console.error` は stderr へ出力され、順序と型文字列表現が決定論的である。 | `test_standard_output_api_contract` |
| **ACC-08** | Multi-Entry Resolution | Auto-executes single calculation, prioritizes `Main`, reports candidates when ambiguous, and respects explicit entry specification. | 単一 calculation を自動実行し、`Main` を優先し、曖昧時は候補を提示し、明示的指定に従って実行する。 | `test_multi_entry_resolution_and_ambiguity` |
| **ACC-09** | Artifact Non-Regression | Reasoning artifacts (`.ruo`, `.ruot`, `.vwm`) and runtime engines maintain strict backward compatibility. | `.ruo`, `.ruot`, `.vwm` 等の推論アーティファクトおよび既存ランタイムとの完全な下位互換性を維持する。 | `test_reasoning_artifacts_non_regression` |
| **ACC-10** | Execution Determinism | Multiple executions with identical input produce byte-identical diagnostics, outputs, and exit codes. | 同一入力に対する複数回実行において、診断、出力、終了コードが完全に決定論的（再現可能）である。 | `test_execution_determinism` |

---

## Acceptance Verification Protocol / 受入検証手順

### English
1. **Automated Suite Execution**:
   Run the dedicated OSS acceptance test suite:
   ```sh
   python3 -m pytest tests/integration/test_oss_handwritten_acceptance.py -v
   ```
2. **Canonical CI Gate**:
   Execute the full canonical CI command to guarantee workspace, diagnostics, artifacts, golden, and test suites pass:
   ```sh
   ./reason ci --json
   ```
3. **Early Alpha Gate Decision**:
   If all 10 acceptance checks (ACC-01 through ACC-10) pass and CI reports `"status": "PASS"`, the release candidate is marked `COMPLETED` and approved for Early Alpha OSS distribution.

### 日本語 (Japanese)
1. **自動テストスイートの実行**:
   専用の OSS 統合受入テストスイートを実行します:
   ```sh
   python3 -m pytest tests/integration/test_oss_handwritten_acceptance.py -v
   ```
2. **Canonical CI ゲートの通過**:
   ワークスペース、診断、アーティファクト、Golden、および全テストの健全性を保証するため、Canonical CI コマンドを実行します:
   ```sh
   ./reason ci --json
   ```
3. **Early Alpha リリース判定**:
   10 項目の受入マトリクス（ACC-01 〜 ACC-10）がすべて成功し、CI レポートが `"status": "PASS"` を記録した場合に、本リリース候補を `COMPLETED` と判定し、Early Alpha OSS 公開承認とします。
