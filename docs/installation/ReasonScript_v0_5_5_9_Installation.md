# ReasonScript v0.5.5.9 Installation / インストール・更新手順

## English

The macOS arm64 update package is
`reasonscript-0.5.5.9-macos-arm64.tar.gz`. Validate it before activation,
then update the local installation:

```sh
reason update package-validate dist/reasonscript-0.5.5.9-macos-arm64.tar.gz --json
reason update --package dist/reasonscript-0.5.5.9-macos-arm64.tar.gz --json
reason --version
reason doctor
reason install-validate
```

The official package is built from the clean `0.5.5.9` release commit and
does not require development-package permission.

## 日本語

macOS arm64 用のアップデートパッケージは
`reasonscript-0.5.5.9-macos-arm64.tar.gz` です。アクティベーション前に
検証してからローカル環境を更新します。

```sh
reason update package-validate dist/reasonscript-0.5.5.9-macos-arm64.tar.gz --json
reason update --package dist/reasonscript-0.5.5.9-macos-arm64.tar.gz --json
reason --version
reason doctor
reason install-validate
```

正式パッケージはクリーンな `0.5.5.9` リリースコミットから生成するため、
`--allow-development-package` は不要です。
