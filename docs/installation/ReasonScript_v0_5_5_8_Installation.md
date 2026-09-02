# ReasonScript v0.5.5.8 Installation / インストール・更新手順

---

## English

The macOS arm64 update package is `reasonscript-0.5.5.8-macos-arm64.zip`.
Validate the package before activation, then update the local installation:

```sh
reason update package-validate dist/reasonscript-0.5.5.8-macos-arm64.zip --json
reason update --package dist/reasonscript-0.5.5.8-macos-arm64.zip --json
reason --version
reason doctor
reason install-validate
```

For a locally built package with development provenance, add `--allow-development-package`. A clean release package can be installed directly without that flag.

### Highlights in v0.5.5.8
- Enforced executable check contracts.
- Unified enum, optional, and pattern matching in Computation IR and Rust VM.
- Full `string.*` and collection standard functions.
- First-class `reason test` command with assertions.
- Controlled recursion analysis and `max_call_depth` runtime guards.
- Robust native ReasonGraph and module transactions.

---

## 日本語 (Japanese)

macOS arm64 用のアップデートパッケージは `reasonscript-0.5.5.8-macos-arm64.zip` です。
アクティベーション前にパッケージを検証し、ローカルインストールを更新します。

```sh
reason update package-validate dist/reasonscript-0.5.5.8-macos-arm64.zip --json
reason update --package dist/reasonscript-0.5.5.8-macos-arm64.zip --json
reason --version
reason doctor
reason install-validate
```

開発ビルド（dirtyワーキングツリー等）で生成されたパッケージをインストールする場合は `--allow-development-package` を指定してください。クリーンなリリースパッケージは通常通り更新できます。

### v0.5.5.8 の主な更新内容
- 構造化実行可能チェック契約の適用
- 列挙型、Optional、パターンマッチングのランタイム・Rust VM統合
- `string.*` およびコレクション標準関数の提供
- `assert` / `assert_eq` をサポートする `reason test` テストランナーの導入
- コールグラフ解析とスタックガード付きの制御された再帰機能
- ネイティブ ReasonGraph およびモジュールトランザクションの強化
