# ReasonScript Module, Manifest & ReasonGraph Contract Specification v0.1
# ReasonScript モジュール・マニフェスト・ReasonGraph契約仕様書 v0.1

- **Spec ID / 仕様ID:** `reasonscript-spec-module-manifest-rgo/v0.1`
- **Status / 状態:** APPROVED / 確定
- **Target / 対象:** Module System, Manifest (`reason.toml`), ReasonGraph Native Persistence

---

## 1. Module & Multi-file Architecture / モジュールとマルチファイル構成

### English
- **Single Module Per File Rule:** ReasonScript strictly enforces one module per file. Splitting a module across multiple files remains prohibited (`NS-001`, `NS-V002`).
- **Standard Project Structure:** The official recommended design pattern is multi-module composition with `pub` visibility and file-level imports (`import package.module`).

### 日本語
- **1ファイル1モジュール原則:** ReasonScriptでは1ファイルにつき1モジュールを厳格に要求します。同一モジュールを複数ファイルに分割する partial module は引き続き禁止されます（`NS-001`, `NS-V002`）。
- **標準プロジェクト構成:** 公開関数・型の `pub` 宣言とファイル間 `import`（`import package.module`）によるモジュール連携を正式な推奨構成とします。

---

## 2. Manifest (`reason.toml`) Validation / マニフェスト検証

- **Recognized Sections:** `[package]`, `[compiler]`, `[runtime]`, `[dependencies]`, `[capabilities]`.
- **Unknown Section Policy:** Any unhandled top-level section emits a deterministic warning or error to prevent silent configuration misinterpretation.
- **Capability Policy:** Capabilities are granted by the executing CLI/environment, not automatically escalated by manifest declarations alone.

---

## 3. ReasonGraph Transaction Parity / ReasonGraph トランザクションパリティ

### English
- **Full Operation Parity (v0.2 Profile):** Rust native `reason-object-core` transactions now fully match Python `GraphTransaction` capabilities, supporting `unit_additions`, `relation_additions`, `unit_updates`, `relation_updates`, and `graph_updates` (`root_refs`, `lifecycle`, `provenance`, `metadata`).
- **Persistence Profile:** Native persistence uses `reasonscript-reason-object-graph-native-persistence/0.2` with canonical JSON serialization.

### 日本語
- **完全操作パリティ (v0.2 プロファイル):** Rust ネイティブ `reason-object-core` のトランザクション処理が Python `GraphTransaction` と完全同等となり、`unit_additions`、`relation_additions`、`unit_updates`、`relation_updates`、`graph_updates`（`root_refs`, `lifecycle`, `provenance`, `metadata`）の全操作集合をサポートします。
- **永続化プロファイル:** 正規化 JSON シリアライズを用いた `reasonscript-reason-object-graph-native-persistence/0.2` プロファイルを採用します。
