# ReasonScript Install Foundation v1.1

# Cross-Platform Update Installation Specification

## 1. 文書情報

* 文書名: ReasonScript Install Foundation v1.1 — Cross-Platform Update Installation Specification
* 略称: Install Foundation v1.1
* 対象プロジェクト: ReasonScript
* 対象基準バージョン: ReasonScript v0.5系
* 前提バージョン: Install Foundation v1.0
* 対象OS:

  * macOS
  * Linux
  * Windows
* ステータス: DRAFT
* 完了状態:

  * NOT STARTED
  * IN PROGRESS
  * IMPLEMENTED
  * VALIDATED
  * BLOCKED
* 標準更新入口: `reason update`
* Repository標準検証入口: `reason ci --json`
* Standalone project標準検証入口: `reason project-validate --json`

---

# 2. 背景

ReasonScript Install Foundation v1.0では、ReasonScript CLI、Runtime、Schema、標準機能および関連コンポーネントを対象OSへ新規インストールし、以下を検証する基盤が実装された。

* `reason --version`
* `reason doctor`
* `reason install-info`
* `reason install-validate`
* `reason init`
* macOS向けインストール
* Linux向けインストールスクリプト
* Windows向けインストールスクリプト
* インストール状態検証
* RuntimeおよびCLIバージョン検証

一方、現在の運用では、ReasonScript本体または仕様を更新するたびに、既存インストールをアンインストールし、再インストールする必要がある。

現行方式:

```text
Existing installation
  ↓
Uninstall
  ↓
Remove installed files
  ↓
Install new package
  ↓
Reconfigure environment
  ↓
Validate installation
```

この方式には以下の問題がある。

* 実機検証ごとに操作手順が増える
* PATHやshell設定を再処理する必要がある
* ユーザー設定を誤って削除する危険がある
* 更新途中の失敗時に動作可能な環境が残らない
* 継続的な能力検証に不向き
* macOS、Linux、Windowsで更新手順が分岐しやすい
* ReasonScript CLIとRuntimeの部分的不整合が生じる可能性がある
* 同一環境でのバージョン遷移検証が困難になる

Install Foundation v1.1では、既存環境をアンインストールせず、動作状態とユーザーデータを維持したまま更新できる仕組みを導入する。

---

# 3. 目的

Install Foundation v1.1の目的は、ReasonScriptの既存インストール環境に対し、安全かつ決定論的な更新インストールを提供することである。

本仕様では、以下を実現する。

1. 既存インストールを自動検出する
2. 現在のバージョンと更新パッケージを比較する
3. OSおよびCPU Architectureの互換性を検証する
4. パッケージManifestおよびchecksumを検証する
5. 更新内容をstaging領域へ展開する
6. 現行環境を直接上書きせず、新バージョンを配置する
7. 設定、プロジェクト、Artifactおよびユーザーデータを保持する
8. 更新後のCLI、Runtime、Schemaおよび標準関数を検証する
9. 更新失敗時に旧バージョンへrollbackする
10. macOS、Linux、Windowsで共通のCLI、状態遷移、DiagnosticおよびJSON契約を提供する
11. OS固有処理をPlatform Adapterへ隔離する
12. 今後のReasonScript能力検証を更新済みインストール環境で継続できるようにする

---

# 4. 基本定義

## 4.1 Update Installation

Update Installationとは、既存のReasonScriptインストールを削除せず、新しいReasonScriptパッケージを導入し、active versionを切り替える処理である。

更新は単純なファイル上書きとして実装してはならない。

標準更新経路:

```text
Installed Environment Detection
  ↓
Installed State Validation
  ↓
Package Validation
  ↓
Version Compatibility Check
  ↓
Staging
  ↓
Pre-activation Validation
  ↓
Version Installation
  ↓
Atomic Activation
  ↓
Post-install Validation
  ↓
Update Completion
```

## 4.2 Cross-Platform

本仕様におけるCross-Platformとは、すべてのOSで同一バイナリまたは同一ファイル操作を使用することではない。

以下を共通化することを意味する。

* Update state machine
* Manifest schema
* Version policy
* Checksum policy
* File inventory policy
* Backup policy
* Rollback policy
* Preservation policy
* Diagnostics
* Exit codes
* JSON report
* CLI surface
* Acceptance criteria

OS固有の処理はPlatform Adapterで実装する。

## 4.3 Platform-independent Core

更新処理のうち、OS差異を持たない中核ロジックをUpdate Coreと呼ぶ。

## 4.4 Platform Adapter

Install root、PATH、実行権限、Launcher切替、実行中ファイルの置換等、OS固有処理を実装する層をPlatform Adapterと呼ぶ。

---

# 5. フェーズの位置づけ

Install Foundation v1.1は、Phase 1 Test再検証に先行して実施する。

```text
Phase 1R
VALIDATED
  ↓
Install Foundation v1.1
Cross-Platform Update Installation
  ↓
Installed Environment Update Validation
  ↓
Phase 1 Test
Integrated Computation Capability Revalidation
  ↓
Phase 2
Existing Machine Learning Model Reproduction
```

Install Foundation v1.1は、ReasonScriptの言語能力または推論能力を追加するフェーズではない。

本フェーズは、今後の継続的な実機検証を支える配布・更新基盤の改善である。

---

# 6. 設計原則

## 6.1 Update CoreはOS非依存とする

以下はOSごとに分岐させてはならない。

* Version comparison
* Manifest validation
* Checksum verification
* Package inventory
* File difference calculation
* Update planning
* Staging state
* Activation state
* Rollback decision
* Migration ordering
* Post-install validation policy
* Diagnostic mapping
* JSON report generation

## 6.2 OS依存処理をPlatform Adapterへ限定する

以下のみPlatform Adapterで処理する。

* Default install root resolution
* Executable path resolution
* Launcher creationおよび切替
* Executable permission
* File ownership
* PATH integration
* Process replacement
* Filesystem atomicity差異
* Privilege handling
* OS固有署名検証
* Windows executable lock処理

## 6.3 現行バージョンを直接上書きしない

更新パッケージを現在のversion directoryへ直接展開してはならない。

## 6.4 User-managed dataを変更しない

ユーザー設定、ReasonScript project、`.rsn` source、Artifact等を更新対象に含めてはならない。

## 6.5 更新失敗時も旧環境を使用可能にする

新バージョンの検証が完了する前に、旧バージョンを削除してはならない。

## 6.6 CLI契約を全OSで統一する

macOS、Linux、Windowsで同じ`reason update`コマンドを使用する。

## 6.7 PackageはRelease Unitとして扱う

CLI、Runtime、Schema、標準関数および関連metadataを個別更新せず、互換性確認済みの単一Release Unitとして更新する。

---

# 7. アーキテクチャ

## 7.1 全体構造

```text
reason update
  ↓
Update Command Layer
  ↓
Cross-Platform Update Core
  ├─ Installation Discovery
  ├─ Manifest Validation
  ├─ Version Resolution
  ├─ Package Verification
  ├─ Update Planning
  ├─ Inventory Comparison
  ├─ Staging
  ├─ Migration
  ├─ Activation
  ├─ Post-install Validation
  ├─ Rollback
  └─ Report Generation
        ↓
Platform Adapter
  ├─ macOS Adapter
  ├─ Linux Adapter
  └─ Windows Adapter
```

## 7.2 推奨モジュール構成

```text
install_foundation/
  update/
    core/
      discovery
      manifest
      version
      package
      inventory
      checksum
      planning
      staging
      activation
      rollback
      migration
      validation
      diagnostics
      report

    platform/
      common
      macos
      linux
      windows
```

## 7.3 実装言語

Update CoreはRustでの実装を推奨する。

理由:

* macOS、Linux、Windowsで共通化しやすい
* Python Runtimeの状態に依存せず更新できる
* Filesystem操作とエラー処理を厳密に管理できる
* 単一実行ファイルまたはLauncherに統合可能
* SHA-256、Manifest、rename、permission処理を安全に実装できる
* Windows用Updater subprocessを同一コードベースで構築できる

Pythonまたはshell scriptをUpdate Coreの唯一の実装としてはならない。

Shell scriptおよびPowerShell scriptはbootstrapまたは引数受け渡しに限定する。

---

# 8. Platform Adapter契約

## 8.1 共通Interface

Platform Adapterは、概念上以下の機能を提供する。

```rust
trait InstallPlatform {
    fn platform_id(&self) -> PlatformId;
    fn architecture_id(&self) -> ArchitectureId;

    fn detect_installation(&self) -> Result<InstallState>;
    fn default_install_root(&self) -> PathBuf;
    fn launcher_path(&self) -> PathBuf;

    fn prepare_install_root(&self, root: &Path) -> Result<()>;
    fn prepare_staging(&self, staging: &Path) -> Result<()>;

    fn ensure_executable(&self, path: &Path) -> Result<()>;
    fn validate_permissions(&self, path: &Path) -> Result<()>;

    fn activate_version(
        &self,
        install_root: &Path,
        version: &str
    ) -> Result<()>;

    fn restore_version(
        &self,
        install_root: &Path,
        version: &str
    ) -> Result<()>;

    fn update_launcher(&self, target: &Path) -> Result<()>;
    fn integrate_path(&self, launcher: &Path) -> Result<()>;

    fn detect_running_process_conflict(&self) -> Result<bool>;
}
```

具体的なAPI名は実装に合わせて変更してよいが、Update CoreからOS固有処理を排除する責務は維持する。

## 8.2 Adapter間の共通動作

各Adapterは以下について同一の論理結果を返す。

* installed / not installed
* compatible / incompatible
* writable / not writable
* activatable / not activatable
* rollback success / failure
* executable state
* launcher state

---

# 9. Install root構造

## 9.1 共通論理構造

OSごとに物理パスは異なるが、インストールroot内部は以下の論理構造に統一する。

```text
<install-root>/
  bin/
    reason
    reason-updater

  versions/
    0.5.0/
      bin/
      runtime/
      toolchain/
      schemas/
      standard_library/
      metadata/

    0.5.1/
      bin/
      runtime/
      toolchain/
      schemas/
      standard_library/
      metadata/

  staging/
  backup/
  config/
  metadata/
    install_state.json
    install_manifest.json
    installed_files.json
    update_history.json
    current.json
```

Windowsでは実行ファイルに`.exe`を付与してよい。

## 9.2 macOS / Linux推奨配置

User-local install:

```text
~/.local/share/reasonscript/
~/.local/bin/reason
```

System-wide installを将来許可する場合:

```text
/usr/local/lib/reasonscript/
/usr/local/bin/reason
```

Phase 1 Test再開前の実装では、User-local installを標準とする。

## 9.3 Windows推奨配置

```text
%LOCALAPPDATA%\ReasonScript\
%LOCALAPPDATA%\ReasonScript\bin\reason.exe
```

## 9.4 Config分離

ユーザー設定はversion directory内部に配置してはならない。

```text
<install-root>/config/
```

またはOS標準User Config Directoryを使用する。

更新時にはconfigを上書きしない。

---

# 10. Launcher方式

## 10.1 固定Launcher

`bin/reason`または`bin/reason.exe`は固定Launcherとして機能する。

Launcherは`current.json`を参照し、active versionの実体を起動する。

```text
bin/reason
  ↓
metadata/current.json
  ↓
versions/<active-version>/bin/reason-runtime
```

## 10.2 current.json

```json
{
  "schema_version": "reasonscript-current-installation/1.0",
  "active_version": "0.5.1",
  "previous_version": "0.5.0",
  "activation_status": "active"
}
```

## 10.3 更新処理

通常の更新では、固定Launcherを変更せず以下のみ実施する。

```text
versions/0.5.1 を追加
  ↓
0.5.1を検証
  ↓
current.jsonを0.5.1へ切替
```

## 10.4 Launcher自体の更新

Launcher更新が必要な場合は、専用Updaterを使用する。

```text
reason
  ↓
reason-updaterを起動
  ↓
reason process終了
  ↓
launcher置換
  ↓
新launcher検証
```

Windowsでは、実行中の`.exe`を直接置換できない可能性があるため、この方式を必須とする。

macOSおよびLinuxでも同じUpdater契約を使用してよい。

---

# 11. Package形式

## 11.1 Platform別Package

ネイティブバイナリを含むため、Package自体はOSおよびArchitecture別とする。

例:

```text
reasonscript-0.5.1-macos-arm64.tar.gz
reasonscript-0.5.1-macos-x86_64.tar.gz
reasonscript-0.5.1-linux-x86_64.tar.gz
reasonscript-0.5.1-linux-arm64.tar.gz
reasonscript-0.5.1-windows-x86_64.zip
reasonscript-0.5.1-windows-arm64.zip
```

## 11.2 共通内部構造

```text
package/
  manifest.json
  checksums.json
  payload/
    bin/
    runtime/
    toolchain/
    schemas/
    standard_library/
    metadata/
```

## 11.3 共通Manifest schema

すべてのOS Packageで同じManifest schemaを使用する。

```json
{
  "schema_version": "reasonscript-install-manifest/1.1",
  "package_version": "0.5.1",
  "runtime_version": "0.5.1",
  "install_foundation_version": "1.1",
  "platform": "macos",
  "architecture": "arm64",
  "minimum_previous_version": "0.5.0",
  "maximum_previous_version": null,
  "package_type": "update_and_install",
  "components": [
    {
      "name": "cli",
      "version": "0.5.1"
    },
    {
      "name": "runtime",
      "version": "0.5.1"
    },
    {
      "name": "tensor_standard_functions",
      "version": "0.1"
    }
  ],
  "files": []
}
```

## 11.4 checksums.json

```json
{
  "schema_version": "reasonscript-package-checksums/1.0",
  "algorithm": "sha256",
  "files": [
    {
      "path": "payload/bin/reason",
      "sha256": "..."
    }
  ]
}
```

---

# 12. Install state

## 12.1 install_state.json

現在のインストール状態を保持する。

```json
{
  "schema_version": "reasonscript-install-state/1.1",
  "installed_version": "0.5.1",
  "runtime_version": "0.5.1",
  "install_foundation_version": "1.1",
  "platform": "macos",
  "architecture": "arm64",
  "install_root": "/Users/example/.local/share/reasonscript",
  "installed_at": "2026-07-01T00:00:00Z",
  "updated_at": "2026-07-14T00:00:00Z",
  "update_count": 1,
  "status": "healthy"
}
```

## 12.2 installed_files.json

管理対象ファイルのinventoryおよびchecksumを保持する。

```json
{
  "schema_version": "reasonscript-installed-files/1.1",
  "version": "0.5.1",
  "files": [
    {
      "path": "versions/0.5.1/bin/reason-runtime",
      "sha256": "...",
      "managed": true,
      "component": "runtime"
    }
  ]
}
```

## 12.3 update_history.json

```json
{
  "schema_version": "reasonscript-update-history/1.0",
  "updates": [
    {
      "from_version": "0.5.0",
      "to_version": "0.5.1",
      "status": "success",
      "started_at": "2026-07-14T00:00:00Z",
      "completed_at": "2026-07-14T00:00:10Z",
      "rollback_performed": false
    }
  ]
}
```

---

# 13. Version policy

## 13.1 Version比較

通常更新は以下の場合のみ許可する。

```text
package version > installed version
```

## 13.2 同一Version

同一Version Packageを指定した場合は、更新不要として終了する。

```json
{
  "status": "already_up_to_date",
  "installed_version": "0.5.1",
  "package_version": "0.5.1"
}
```

同一Versionの強制再適用はPhase 1.1の対象外とする。

## 13.3 Downgrade

Package versionがinstalled versionより古い場合は拒否する。

```text
downgrade rejected
```

将来的には明示的な`--allow-downgrade`を追加してよいが、本仕様では対象外とする。

## 13.4 Version識別

更新内容が存在する場合、同じVersion番号のままPackage内容だけを変更してはならない。

推奨:

```text
0.5.0
  ↓
0.5.1
```

開発版の場合:

```text
0.5.1-dev
0.5.1-phase1r
```

## 13.5 Component version整合性

CLI、Runtime、Schema等のVersion組合せはManifestで定義する。

互換性のないComponent versionを混在させてはならない。

---

# 14. 標準CLI仕様

## 14.1 更新確認

```bash
reason update --check
```

ローカルPackageを指定する場合:

```bash
reason update --check --package <package-path>
```

出力例:

```json
{
  "schema_version": "reasonscript-update-report/1.0",
  "status": "update_available",
  "installed_version": "0.5.0",
  "package_version": "0.5.1",
  "platform": "macos",
  "architecture": "arm64",
  "compatible": true,
  "action": "update"
}
```

## 14.2 Local Package更新

```bash
reason update --package <package-path>
```

例:

```bash
reason update \
  --package ./dist/reasonscript-0.5.1-macos-arm64.tar.gz
```

## 14.3 更新後検証

```bash
reason update --validate
```

## 14.4 Rollback

```bash
reason update --rollback
```

明示Version指定を将来追加してよい。

```bash
reason update --rollback 0.5.0
```

## 14.5 JSON出力

```bash
reason update --package <package-path> --json
```

## 14.6 Force

管理対象ファイルのローカル変更を上書きする場合のみ使用する。

```bash
reason update --package <package-path> --force
```

`--force`を指定しても、ユーザー設定およびユーザーデータを削除してはならない。

## 14.7 Installer経由

macOS / Linux:

```bash
./install.sh --update --package <package-path>
```

Windows:

```powershell
.\install.ps1 -Update -Package <package-path>
```

Installerは内部的に共通Update Coreを呼び出す。

Installer script内に更新ロジックを重複実装してはならない。

---

# 15. Update state machine

## 15.1 状態一覧

```text
idle
detecting
validating_current
validating_package
planning
staging
validating_staging
migrating
activating
validating_active
completed
failed
rolling_back
rolled_back
rollback_failed
```

## 15.2 標準遷移

```text
idle
  ↓
detecting
  ↓
validating_current
  ↓
validating_package
  ↓
planning
  ↓
staging
  ↓
validating_staging
  ↓
migrating
  ↓
activating
  ↓
validating_active
  ↓
completed
```

## 15.3 失敗遷移

Activation前に失敗:

```text
failed
  ↓
staging cleanup
  ↓
旧versionを維持
```

Activation後に失敗:

```text
failed
  ↓
rolling_back
  ↓
rolled_back
```

Rollbackにも失敗:

```text
rollback_failed
```

---

# 16. 更新処理仕様

## 16.1 Existing installation detection

以下を確認する。

* Launcherの存在
* install root
* `install_state.json`
* `current.json`
* active version directory
* installed version
* Runtime version
* platform
* architecture
* file inventory
* current installation health

既存インストールがない場合、`reason update`を新規インストールへ自動変換してはならない。

Diagnosticを返す。

## 16.2 Current installation validation

更新前に以下を検証する。

* Manifest読取
* active version directory存在
* Launcher解決可能
* 必須ファイル存在
* checksum整合性
* CLIおよびRuntime version整合性
* install root書込権限
* metadata schema対応

## 16.3 Package validation

以下を検証する。

* Package形式
* Manifest schema
* checksums schema
* Package checksum
* 各payload file checksum
* platform一致
* architecture一致
* minimum previous version
* component version整合性
* 必須Component存在
* 重複path不存在
* path traversal不存在
* payload root外への展開不存在

## 16.4 Update planning

Update planには以下を含める。

* from version
* to version
* added files
* changed files
* removed managed files
* preserved files
* migration actions
* estimated disk usage
* rollback target
* activation method

## 16.5 Staging

新Packageは以下に展開する。

```text
<install-root>/staging/<version>/
```

現在のactive version directoryへ直接展開してはならない。

## 16.6 Staging validation

Staging後に以下を検証する。

* 全必須ファイル存在
* checksum一致
* executable integrity
* Schema読込
* CLI bootstrap
* Runtime bootstrap
* component version一致
* Package内参照解決

## 16.7 Version installation

検証済みstagingを以下へ配置する。

```text
<install-root>/versions/<new-version>/
```

同じFilesystem内でのatomic renameを優先する。

## 16.8 Activation

新Versionの配置完了後に`current.json`を切り替える。

Activation前にold versionを削除してはならない。

## 16.9 Post-install validation

Activation後に標準検証を実行する。

## 16.10 Completion

すべて成功した場合:

* install state更新
* installed files更新
* update history追記
* previous version記録
* staging削除
* backup整理
* statusをhealthyへ変更

---

# 17. Atomicity仕様

## 17.1 原則

更新は可能な限りatomicに行う。

以下の混在状態を作ってはならない。

```text
New CLI
Old Runtime
Old Schema
New Tensor Registry
```

## 17.2 Version directory方式

Version単位で完全なPackageを配置する。

```text
versions/0.5.0/
versions/0.5.1/
```

active pointerだけを切り替える。

## 17.3 Metadata切替

`current.json`更新は一時ファイルへ書き込み、flush後にrenameする。

```text
current.json.tmp
  ↓
validation
  ↓
atomic rename
  ↓
current.json
```

## 17.4 Filesystem制約

同一Filesystem内でのrenameを使用する。

Filesystemを跨ぐ場合は、Platform Adapterが安全な代替手段を提供する。

---

# 18. Rollback仕様

## 18.1 自動Rollback条件

以下の場合、旧Versionへ自動Rollbackする。

* Activation失敗
* `reason --version`失敗
* Runtime起動失敗
* `reason doctor`必須項目失敗
* `reason install-info`不整合
* `reason install-validate`失敗
* Schema load失敗
* Scalar smoke test失敗
* Tensor smoke test失敗
* Loop smoke test失敗
* Launcher解決失敗
* component version不一致

## 18.2 Rollback処理

```text
New active version invalid
  ↓
current.jsonをprevious versionへ戻す
  ↓
previous versionを起動
  ↓
previous version validation
  ↓
new versionをquarantineまたは削除
  ↓
rollback report生成
```

## 18.3 Rollback結果

```json
{
  "schema_version": "reasonscript-update-report/1.0",
  "status": "rolled_back",
  "attempted_version": "0.5.1",
  "restored_version": "0.5.0",
  "reason_code": "INS-UPD-010",
  "previous_installation_healthy": true
}
```

## 18.4 Rollback failure

旧Versionも復元できない場合は`rollback_failed`とし、明確な復旧手順をDiagnosticへ含める。

---

# 19. Preservation policy

## 19.1 更新対象

以下はReasonScript管理対象として更新する。

* CLI
* Launcher
* Compiler
* Runtime
* Toolchain
* Tensor function registry
* Standard library
* Schema
* Bundled diagnostics definition
* Built-in validation commands
* Bundled canonical fixtures
* Package metadata

## 19.2 保持対象

以下は更新時に削除または上書きしてはならない。

* User configuration
* User-created `.rsn` source
* Workspace
* ReasonScript project
* Project manifest
* User Artifact
* External Tensor Artifact
* Golden data created by user
* User package
* User log
* User cache
* Custom backend設定
* Local environment設定
* Credential
* Git repository data

## 19.3 ShellおよびPATH

更新時にPATH設定を毎回追加してはならない。

初回インストール時にLauncher pathを登録し、そのLauncher pathを固定する。

shell profileへの重複行追加を禁止する。

## 19.4 Config migration

Config schema変更が必要な場合、明示的Migrationを実行する。

Migration前にはbackupを作成する。

Migrationは以下を満たす。

* deterministic
* versioned
* idempotent
* rollback-aware
* user field preservation

---

# 20. Managed file modification policy

## 20.1 更新前検査

`installed_files.json`のchecksumと実ファイルを比較する。

## 20.2 Modified managed file

管理対象ファイルがローカルで変更されている場合、デフォルトでは更新を停止する。

```text
modified managed file detected
  ↓
INS-UPD-013
  ↓
update aborted
```

## 20.3 Force update

`--force`指定時は管理対象ファイルをPackage版へ戻してよい。

ただし、変更ファイル一覧をreportへ記録する。

## 20.4 User-managed file

User-managed fileはchecksum比較対象外とし、`--force`でも削除しない。

---

# 21. TensorおよびPhase 1R更新要件

Phase 1R実装済み環境をPackageへ反映する場合、少なくとも以下を同一Release Unitとして含める。

* Public `tensor.*` namespace
* Tensor registry 49 functions
* `tensor.relu`
* `tensor.softmax`
* `tensor.linear`
* Tensor semantic validation
* Tensor Reason IR
* Tensor ExecutionPlan integration
* Tensor runtime dispatch
* Empty Tensor diagnostics
* NaN diagnostics
* Infinity diagnostics
* Non-finite output diagnostics
* External Tensor Artifact validation
* `for`
* `while`
* `loop`
* `break`
* `continue`
* Loop limit
* Iteration trace
* `reason project-validate`
* `reason phase1r-validate`
* Related schemas
* Related canonical fixtures
* Version metadata

更新後に一部のみ古い状態を参照してはならない。

---

# 22. Post-install validation

## 22.1 必須コマンド

更新後に以下を実行する。

```bash
reason --version
reason doctor --json
reason install-info --json
reason install-validate --json
```

## 22.2 必須Smoke tests

### Scalar smoke test

* `.rsn` source check
* Scalar function execution
* Runtime result validation

### Tensor smoke test

* `tensor.create`
* `tensor.relu`
* Tensor Artifact生成
* Shape / dtype確認
* finite value確認

### Loop smoke test

* bounded loop
* iteration count
* final state
* loop trace

### Project validation smoke test

```bash
reason project-validate <fixture-project> --json
```

## 22.3 Optional deep validation

Packageにcanonical fixtureを含める場合:

```bash
reason phase1r-validate --json
```

## 22.4 Validation結果

必須Smoke testのいずれかが失敗した場合、更新成功として確定してはならない。

---

# 23. OS固有要件

## 23.1 macOS Adapter

最低限以下を扱う。

* User-local install root
* Unix executable bit
* Symlinkまたはfixed launcher
* Atomic rename
* shell PATH discovery
* Quarantine attributeの必要な処理
* 将来的なcode signing / notarization

更新時にshell profileを重複編集しない。

## 23.2 Linux Adapter

最低限以下を扱う。

* User-local install root
* Unix executable bit
* Symlinkまたはfixed launcher
* Atomic rename
* shell PATH discovery
* File ownership
* Distribution非依存の基本動作

特定Distribution package managerへの依存はPhase 1.1の対象外とする。

## 23.3 Windows Adapter

最低限以下を扱う。

* `%LOCALAPPDATA%` install root
* User PATH
* `.exe` launcher
* 実行中ファイルlock
* Updater subprocess
* Directory switch
* Windows path normalization
* ACLおよび書込権限
* PowerShell bootstrap

`reason.exe`実行中に同じ実行ファイルを直接置換してはならない。

---

# 24. 共通CLIおよびUX契約

macOS、Linux、Windowsで以下を共通にする。

* Command name
* Option name
* JSON schema
* Diagnostic code
* Exit code
* Update state
* Rollback result
* Version policy
* Package compatibility result
* Validation result

OSごとに異なる操作をユーザーへ要求するのは、初回bootstrapまたは権限処理に限定する。

通常更新は以下へ統一する。

```bash
reason update --package <package-path>
```

---

# 25. Diagnostics仕様

## 25.1 Stable Diagnostic codes

| Code          | Condition                                   |
| ------------- | ------------------------------------------- |
| `INS-UPD-001` | Existing installation not found             |
| `INS-UPD-002` | Package version is not newer                |
| `INS-UPD-003` | Platform mismatch                           |
| `INS-UPD-004` | Architecture mismatch                       |
| `INS-UPD-005` | Package checksum mismatch                   |
| `INS-UPD-006` | Insufficient permissions                    |
| `INS-UPD-007` | Insufficient disk space                     |
| `INS-UPD-008` | Staging validation failed                   |
| `INS-UPD-009` | Activation failed                           |
| `INS-UPD-010` | Post-install validation failed              |
| `INS-UPD-011` | Rollback completed                          |
| `INS-UPD-012` | Rollback failed                             |
| `INS-UPD-013` | Managed installed file was locally modified |
| `INS-UPD-014` | Unsupported update path                     |
| `INS-UPD-015` | Install state is invalid                    |
| `INS-UPD-016` | Component version mismatch                  |
| `INS-UPD-017` | Package manifest is invalid                 |
| `INS-UPD-018` | Running process prevents activation         |
| `INS-UPD-019` | Launcher update failed                      |
| `INS-UPD-020` | Configuration migration failed              |

既存Install Foundation Diagnosticsとの衝突確認後に最終確定する。

## 25.2 Diagnostic schema

```json
{
  "code": "INS-UPD-004",
  "severity": "fatal",
  "category": "installation_update",
  "message": "Package architecture does not match the installed architecture.",
  "installed_architecture": "arm64",
  "package_architecture": "x86_64",
  "phase": "validating_package",
  "recovery_hint": "Use a package built for arm64."
}
```

## 25.3 PythonまたはOS例外

Raw traceback、Rust panic、PowerShell stack trace、OS内部errorをそのままユーザー出力へ露出してはならない。

内部エラーはstable Diagnosticへ正規化する。

---

# 26. Exit code policy

推奨Exit code:

| Exit code | Meaning                               |
| --------: | ------------------------------------- |
|       `0` | Update completed / no update required |
|       `1` | General update failure                |
|       `2` | Invalid arguments                     |
|       `3` | Installation not found                |
|       `4` | Package incompatible                  |
|       `5` | Package integrity failure             |
|       `6` | Permission failure                    |
|       `7` | Activation failure                    |
|       `8` | Post-install validation failure       |
|       `9` | Rollback completed after failure      |
|      `10` | Rollback failure                      |

具体値は既存CLI契約との整合確認後に確定する。

---

# 27. JSON Report仕様

## 27.1 Update report

```json
{
  "schema_version": "reasonscript-update-report/1.0",
  "status": "completed",
  "platform": "macos",
  "architecture": "arm64",
  "install_root": "/Users/example/.local/share/reasonscript",
  "from_version": "0.5.0",
  "to_version": "0.5.1",
  "package": {
    "path": "./reasonscript-0.5.1-macos-arm64.tar.gz",
    "checksum_valid": true,
    "manifest_valid": true
  },
  "staging": {
    "status": "passed"
  },
  "activation": {
    "status": "passed",
    "atomic": true
  },
  "preservation": {
    "config_preserved": true,
    "projects_untouched": true,
    "artifacts_untouched": true
  },
  "post_install_validation": {
    "version": "passed",
    "doctor": "passed",
    "install_info": "passed",
    "install_validate": "passed",
    "scalar_smoke": "passed",
    "tensor_smoke": "passed",
    "loop_smoke": "passed"
  },
  "rollback": {
    "performed": false
  },
  "diagnostics": []
}
```

## 27.2 Deterministic fields

同一状態および同一Packageから生成される論理項目は決定的でなければならない。

Timestamp、temporary path等はcanonical comparisonから除外してよい。

---

# 28. セキュリティ要件

## 28.1 Path traversal防止

Package内pathがinstall root外へ展開されないこと。

以下を拒否する。

```text
../
absolute path
drive-qualified external path
symbolic link escape
```

## 28.2 Checksum

すべてのmanaged payload fileをSHA-256で検証する。

## 28.3 Package signature

Phase 1.1では必須としないが、Manifestに将来拡張可能な署名fieldを定義してよい。

## 28.4 Symlink

Package内symlinkを許可する場合、リンク先がPackageまたはinstall root外へ出ないことを確認する。

## 28.5 Privilege

不必要に管理者権限または`sudo`を要求してはならない。

User-local installを標準とする。

## 28.6 Arbitrary script execution

Package内の任意scriptを無条件で実行してはならない。

MigrationはVersion管理された組み込み処理または署名済み定義に限定する。

---

# 29. Resource要件

更新前に以下を確認する。

* Package size
* 展開後size
* Staging size
* Backup size
* 最小空き容量
* File count limit
* Path length
* Temporary directory write permission

ディスク容量不足はstaging開始前に検出する。

---

# 30. テスト構成

推奨ディレクトリ:

```text
tests/
  install_update/
    test_install_detection.py
    test_install_state_validation.py
    test_manifest_validation.py
    test_version_comparison.py
    test_platform_mismatch.py
    test_architecture_mismatch.py
    test_checksum_validation.py
    test_update_planning.py
    test_staging.py
    test_atomic_activation.py
    test_config_preservation.py
    test_managed_file_detection.py
    test_post_install_validation.py
    test_rollback.py
    test_update_report.py
    test_update_determinism.py

  platform_adapters/
    test_macos_adapter.py
    test_linux_adapter.py
    test_windows_adapter.py

  install_cli/
    test_update_check.py
    test_update_package.py
    test_update_validate.py
    test_update_rollback.py
```

Fixture構成:

```text
tests/
  fixtures/
    install_update/
      installed_0_5_0/
      package_0_5_1/
      invalid_checksum/
      invalid_manifest/
      platform_mismatch/
      architecture_mismatch/
      modified_managed_file/
      failed_post_validation/
      rollback_success/
      rollback_failure/
```

---

# 31. 検証マトリクス

| 項目                    |   macOS |   Linux | Windows |
| --------------------- | ------: | ------: | ------: |
| Update Core           |  Common |  Common |  Common |
| Manifest schema       |  Common |  Common |  Common |
| Version comparison    |  Common |  Common |  Common |
| Checksum verification |  Common |  Common |  Common |
| File inventory        |  Common |  Common |  Common |
| Staging state machine |  Common |  Common |  Common |
| Rollback policy       |  Common |  Common |  Common |
| Diagnostic codes      |  Common |  Common |  Common |
| JSON reports          |  Common |  Common |  Common |
| Install root          | Adapter | Adapter | Adapter |
| Executable permission | Adapter | Adapter | Adapter |
| Launcher switch       | Adapter | Adapter | Adapter |
| PATH integration      | Adapter | Adapter | Adapter |
| Process replacement   | Adapter | Adapter | Adapter |
| OS signing            | Adapter | Adapter | Adapter |

---

# 32. Valid test cases

最低限以下を検証する。

1. `0.5.0 → 0.5.1`更新
2. アンインストールなしで更新
3. User config保持
4. User project保持
5. User Artifact保持
6. PATH重複変更なし
7. 新CLI command追加
8. Tensor registry更新
9. Runtime更新
10. Schema更新
11. 古いmanaged fileの除去
12. 新Version directory作成
13. Atomic active version切替
14. 更新後scalar smoke test
15. 更新後Tensor smoke test
16. 更新後loop smoke test
17. `reason project-validate`成功
18. 同一Version Packageのno-op
19. 更新履歴記録
20. 旧Versionを保持したrollback準備

---

# 33. Invalid test cases

最低限以下を検証する。

1. 未インストール環境で`reason update`
2. 古いVersion Package
3. Platform不一致
4. Architecture不一致
5. Package checksum不一致
6. Payload checksum不一致
7. Manifest不正
8. Component version不一致
9. path traversal
10. 書込権限不足
11. ディスク容量不足
12. Staging validation失敗
13. Activation失敗
14. Post-install validation失敗
15. Rollback失敗
16. Managed fileローカル変更
17. active version directory欠落
18. current.json破損
19. Launcher更新失敗
20. Windows実行中process conflict

---

# 34. 実装工程

## IF-1.1-A — Common Install State

### 内容

* `install_state.json`
* `current.json`
* `installed_files.json`
* `update_history.json`
* Schema
* State migration

### 完了条件

既存インストール状態を共通形式で取得・検証できる。

---

## IF-1.1-B — Cross-Platform Update Core

### 内容

* Version comparison
* Manifest validation
* Checksum
* Package inventory
* Update plan
* Diagnostics
* JSON report

### 完了条件

OS固有処理なしで更新計画を生成できる。

---

## IF-1.1-C — Platform Adapter Interface

### 内容

* Common interface
* Platform ID
* Architecture ID
* Install root
* Permission
* Activation
* Launcher
* PATH
* Process conflict

### 完了条件

Update CoreがOS APIを直接呼び出さない。

---

## IF-1.1-D — Staging and Atomic Activation

### 内容

* Staging directory
* Package extraction
* Validation
* Version directory
* `current.json` switch
* Cleanup

### 完了条件

現行Versionを直接上書きせず更新できる。

---

## IF-1.1-E — Preservation and Migration

### 内容

* User config保持
* Project保護
* Artifact保護
* PATH idempotency
* Config migration
* Backup

### 完了条件

更新後もユーザー管理データが保持される。

---

## IF-1.1-F — Rollback

### 内容

* Previous version記録
* Automatic restore
* Restored environment validation
* Quarantine
* Rollback report

### 完了条件

新Version検証失敗時に旧Versionへ復旧できる。

---

## IF-1.1-G — CLI Integration

### 内容

* `reason update --check`
* `reason update --package`
* `reason update --validate`
* `reason update --rollback`
* `--json`
* `--force`

### 完了条件

全OSで共通CLI契約を使用できる。

---

## IF-1.1-H — macOS Adapter Validation

### 内容

* macOS arm64
* User-local install
* Executable bit
* Launcher
* Atomic rename
* PATH保持
* 実機更新

### 完了条件

既存macOSインストールをアンインストールせず更新できる。

---

## IF-1.1-I — Linux Adapter Validation

### 内容

* Linux x86_64またはarm64
* User-local install
* Executable bit
* Launcher
* PATH
* Rollback

### 完了条件

共通Update Coreを変更せずLinux更新が成立する。

---

## IF-1.1-J — Windows Adapter Validation

### 内容

* Windows x86_64
* `%LOCALAPPDATA%`
* Launcher
* Updater subprocess
* User PATH
* `.exe` lock処理
* Rollback

### 完了条件

共通Update Coreを変更せずWindows更新が成立する。

---

## IF-1.1-K — Final Regression

### 内容

* Clean install
* Update install
* Uninstall
* Rollback
* Install validation
* Full test suite
* Golden
* `reason ci --json`

### 完了条件

既存Install Foundation v1.0の能力を破壊しない。

---

# 35. Acceptance criteria

Install Foundation v1.1は、以下をすべて満たした場合に`VALIDATED`とする。

## 35.1 Update Gate

* 既存インストールを検出できる
* 新旧Versionを比較できる
* 新Versionへ更新できる
* アンインストールを要求しない
* 同一Versionを安全にno-opできる
* Downgradeを拒否できる

## 35.2 Cross-Platform Architecture Gate

* Update CoreがOS非依存
* Platform Adapter interfaceが存在
* OS固有処理がAdapterへ限定
* Manifest schemaが全OS共通
* Diagnostic codeが全OS共通
* JSON reportが全OS共通
* CLI surfaceが全OS共通

## 35.3 Integrity Gate

* Package Manifest検証
* SHA-256検証
* Platform検証
* Architecture検証
* Component version検証
* Path traversal防止
* Installed file inventory検証

## 35.4 Preservation Gate

* User config保持
* User project保持
* User Artifact保持
* User package保持
* PATH維持
* shell profile重複変更なし

## 35.5 Atomicity Gate

* Staging使用
* Version directory使用
* 現行Version直接上書きなし
* Active pointerのatomic切替
* CLIとRuntimeの混在状態なし

## 35.6 Rollback Gate

* 更新失敗を検出できる
* 旧Versionへ自動復旧できる
* 復旧後の環境を検証できる
* Rollback reportを生成できる
* Rollback失敗を診断できる

## 35.7 Post-install Gate

以下がすべてPASSする。

```bash
reason --version
reason doctor --json
reason install-info --json
reason install-validate --json
```

加えて:

* Scalar smoke test
* Tensor smoke test
* Loop smoke test
* Project validation smoke test

## 35.8 Compatibility Gate

* 新規インストールが引き続き可能
* Uninstallが引き続き可能
* Install Foundation v1.0互換性維持
* Existing CLI entry維持
* Existing Runtime維持
* Existing Artifact contract維持
* `reason ci --json` PASS

## 35.9 Determinism Gate

同一インストール状態と同一Packageから、以下が一致する。

* Update plan
* File inventory
* Diagnostic ordering
* Logical update result
* Canonical JSON report
* Checksum result

---

# 36. 初期VALIDATED範囲

Cross-platform architectureを最初から実装するが、実機認証は段階的に進めてよい。

## Stage 1

* Common Update Core: VALIDATED
* Platform Adapter contract: VALIDATED
* macOS Adapter実機: VALIDATED

## Stage 2

* Linux Adapter実機: VALIDATED

## Stage 3

* Windows Adapter実機: VALIDATED

Stage 1完了時点でmacOS上のPhase 1 Testを再開してよい。

ただし、仕様上のCross-platform契約をmacOS専用実装へ置き換えてはならない。

LinuxおよびWindows実機認証が未完了の場合、結果を以下のように明示する。

```text
Cross-platform architecture: VALIDATED
macOS implementation: VALIDATED
Linux implementation: IMPLEMENTED / NOT YET DEVICE-VALIDATED
Windows implementation: IMPLEMENTED / NOT YET DEVICE-VALIDATED
```

---

# 37. 成果物

## 37.1 仕様書

```text
docs/specifications/
  ReasonScript_Install_Foundation_v1_1_Cross_Platform_Update_Installation.md
```

## 37.2 実装レポート

```text
docs/implementation/
  ReasonScript_Install_Foundation_v1_1_Implementation_Report.md
```

## 37.3 検証レポート

```text
docs/validation/
  ReasonScript_Install_Foundation_v1_1_Validation_Report.md
```

## 37.4 Changelog

```text
docs/changelog/
  ReasonScript_Install_Foundation_v1_1_Update_Installation.md
```

## 37.5 Machine-readable summary

```text
artifacts/install_foundation_v1_1/
  install_foundation_validation_summary.json
```

推奨形式:

```json
{
  "schema_version": "reasonscript-install-foundation-validation/1.1",
  "status": "validated",
  "update_core": "passed",
  "manifest_gate": "passed",
  "integrity_gate": "passed",
  "preservation_gate": "passed",
  "atomicity_gate": "passed",
  "rollback_gate": "passed",
  "post_install_gate": "passed",
  "compatibility_gate": "passed",
  "determinism_gate": "passed",
  "platforms": {
    "macos": "validated",
    "linux": "not_yet_device_validated",
    "windows": "not_yet_device_validated"
  },
  "diagnostics": []
}
```

---

# 38. Phase 1 Test再開条件

以下を満たした後、Phase 1 Testへ戻る。

1. Install Foundation v1.1 Update Core実装完了
2. macOS Platform Adapter実装完了
3. 既存ReasonScriptインストール検出成功
4. 更新Package検証成功
5. アンインストールなしで更新成功
6. User config保持
7. PATH保持
8. 更新後`reason --version`成功
9. 更新後`reason doctor`成功
10. 更新後`reason install-validate`成功
11. Tensor smoke test成功
12. Loop smoke test成功
13. `reason project-validate`成功
14. Repositoryで`reason ci --json`成功

標準遷移:

```text
Installed ReasonScript 0.5.0
  ↓
reason update --package <new-package>
  ↓
Installed ReasonScript 0.5.1
  ↓
Post-install validation
  ↓
Phase 1 Test
```

---

# 39. 非対象範囲

Install Foundation v1.1では以下を対象外とする。

* 自動オンラインUpdate server
* Package repository service
* Background automatic update
* Delta binary patch
* Peer-to-peer distribution
* OS package manager統合
* Homebrew formula
* apt repository
* rpm repository
* winget package
* Microsoft Store
* macOS App Store
* Automatic signature infrastructure
* Enterprise fleet management
* Multi-user system install
* Silent administrator deployment
* Forced downgrade
* Multiple update channelsの完全実装
* Differential component update

ローカルPackageを指定する更新を最初の標準実装とする。

---

# 40. Compatibility要件

Install Foundation v1.1は以下を維持する。

* `reason --version`
* `reason doctor`
* `reason install-info`
* `reason install-validate`
* `reason init`
* Existing clean install
* Existing uninstall
* CLI-first architecture
* Artifact-first policy
* Coding Agent workflow
* `reason ci --json`
* `reason project-validate --json`
* Tensor Standard Functions
* Phase 1R runtime integration
* Existing user project structure

Install Foundation v1.0の既存metadataを読み取れない場合は、v1.1 metadataへの一度限りのMigrationを提供する。

---

# 41. 最終定義

ReasonScript Install Foundation v1.1は、ReasonScriptの既存インストール環境をアンインストールせず、新しいRelease Unitへ安全に更新するためのCross-platform更新基盤である。

本仕様における完成状態は、以下の経路が成立している状態と定義する。

```text
Existing ReasonScript Installation
  ↓
Cross-Platform Installation Detection
  ↓
Common Manifest and Version Validation
  ↓
Platform and Architecture Compatibility
  ↓
Checksum and Inventory Verification
  ↓
Staging
  ↓
Versioned Installation
  ↓
Platform Adapter Activation
  ↓
Post-install Runtime Validation
  ↓
Atomic Completion
```

失敗時:

```text
Update Failure
  ↓
Common Rollback Decision
  ↓
Platform Adapter Restore
  ↓
Previous Version Validation
  ↓
Operational Environment Recovery
```

本フェーズの完了は、ReasonScriptがmacOS、Linux、Windowsごとに異なる更新システムを持つのではなく、共通Update Coreと限定されたPlatform Adapterによって、安全かつ一貫した更新インストールを提供できる状態へ到達したことを示す。
