# ReasonScript v0.5.5.8 Release Definition / リリース定義書

Specification ID: `reasonscript-release/0.5.5.8`
Status: VALIDATED
Date: 2026-08-30

---

## English

ReasonScript 0.5.5.8 is a feature-complete, compatibility-preserving runtime, toolchain, and standard library release incorporating Modernization Phases 0 through 5. The canonical version is `0.5.5.8` across `VERSION`, Python package metadata, release metadata, runtime metadata, and the validation profile. Runtime compatibility remains `>=0.5.0,<0.6.0`.

### Scope & Requirements

The release incorporates and validates:

- **Executable Check Contract (Phase 0):** Enforced structured check contracts across CLI and toolchain.
- **Unified Enum, Optional & Pattern Matching (Phase 1):** Language and native runtime support for algebraic enums, Optionals, and exhaustive/wildcard pattern matching.
- **String & Collection Standard Library (Phase 2):** Native standard library additions (`string.*`, collections/map/set operations) across Python and Rust runtimes.
- **Execution-Based Test Framework (Phase 3):** CLI `reason test` runner supporting `assert` and `assert_eq` execution contracts.
- **Controlled Recursion & Static Call Graph (Phase 4):** Call graph cycle detection, explicit recursion bounds (`max_call_depth`), and runtime stack safety.
- **Module, Manifest & ReasonGraph Parity (Phase 5):** Unified transaction handling and parity for native module manifests and ReasonGraphs.
- **Deterministic Packaging & Install Foundation 1.1:** Provenance verification, clean release packaging, and local in-place update validation.

---

## 日本語 (Japanese)

ReasonScript 0.5.5.8 は、現代化フェーズ0から5（モダン言語機能、標準ライブラリ拡充、テストフレームワーク、制御された再帰、ネイティブモジュール・ReasonGraph整合性）を統合した、後方互換性を維持するリリースです。`VERSION`、Pythonパッケージメタデータ、リリースメタデータ、ランタイムメタデータ、バリデーションプロファイルの正準バージョンは一貫して `0.5.5.8` となります。ランタイム互換性は `>=0.5.0,<0.6.0` を維持します。

### リリース要件とスコープ

- **実行可能チェック契約 (Phase 0):** CLIおよびツールチェーン全体での構造化チェック契約の強制。
- **列挙型・Optional・パターンマッチング統合 (Phase 1):** 代数的Enum、Optional型、ワイルドカード/網羅的パターンマッチングの言語およびネイティブ実行時サポート。
- **文字列・コレクション標準ライブラリ (Phase 2):** `string.*` およびコレクション操作等の標準ライブラリ関数のネイティブサポート。
- **実行ベーステストフレームワーク (Phase 3):** `assert` / `assert_eq` を用いた `reason test` ランナーの提供。
- **制御された再帰と静的コールグラフ (Phase 4):** コールグラフ循環解析、最大呼び出し深度（`max_call_depth`）によるスタック安全性保証。
- **モジュール・マニフェスト・ReasonGraph整合性 (Phase 5):** ネイティブトランザクション管理とRGO/マニフェストの一貫性保証。
- **決定的パッケージングとローカル更新 (Install Foundation 1.1):** 真正性検証（Provenance）、クリーンビルドパッケージ生成、ローカルインストールの安全なアトミック更新。
