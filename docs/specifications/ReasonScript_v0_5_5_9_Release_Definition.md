# ReasonScript v0.5.5.9 Release Definition / リリース定義書

Specification ID: `reasonscript-release/0.5.5.9`
Status: RELEASE_CANDIDATE
Date: 2026-09-05

---

## English

ReasonScript 0.5.5.9 consolidates the merged numeric-semantics and
Tensor-lifecycle pull requests on top of 0.5.5.8. The canonical version is
`0.5.5.9` across `VERSION`, Python package metadata, release metadata,
runtime metadata, and the validation profile. Runtime compatibility remains
`>=0.5.0,<0.6.0`.

### Scope

- Deterministic mixed numeric promotion in the parser, type checker, and
  native runtime.
- Multiline parenthesized expressions and stable transition IDs for external
  tooling.
- Deterministic cleanup of unreachable protected Tensor lifecycles.
- CI dependency preparation and playground exception-handling hardening.
- Native macOS arm64 and Windows x86_64 package generation from the same
  release commit. Windows packaging is executed separately on Windows.

## 日本語

ReasonScript 0.5.5.9 は、0.5.5.8 を基盤に数値意味論および Tensor
ライフサイクルのマージ済みPRを統合するリリースです。`VERSION`、Python
パッケージ、リリース/ランタイムメタデータ、バリデーションプロファイルの正準
バージョンをすべて `0.5.5.9` に統一します。ランタイム互換性
`>=0.5.0,<0.6.0` は維持します。

### 対象範囲

- パーサー、型検査、ネイティブランタイムにおける決定的な混在数値型昇格
- 複数行の括弧式と外部ツール向け安定した遷移ID
- 到達不能な保護 Tensor ライフサイクルの決定的解放
- CI依存関係準備とPlayground例外処理の強化
- 同一リリースコミットからの macOS arm64 / Windows x86_64 ネイティブ
  パッケージ生成（Windows版はWindows環境で別途実行）
