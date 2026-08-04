# ReasonScript Install Foundation v1.1.1

# Phase R1 — Rollback Failure Reproduction and Current Behavior Freeze Specification

## 1. 文書情報

* 文書名: ReasonScript Install Foundation v1.1.1 — Phase R1 Rollback Failure Reproduction and Current Behavior Freeze Specification
* 略称: Install Foundation v1.1.1 Phase R1
* Specification ID: `reasonscript-install-foundation-v1.1.1-phase-r1/1.0`
* 対象プロジェクト: ReasonScript
* 対象Release:

  * 更新元: ReasonScript 0.5.0
  * 更新先: ReasonScript 0.5.1
* 前提仕様:

  * ReasonScript Install Foundation v1.0
  * ReasonScript Install Foundation v1.1
  * Version-Aware Rollback Validation and Recovery State Correction Specification
* 対象範囲:

  * 障害再現
  * 再現fixture
  * 現行挙動の観測
  * pointer restorationとvalidation failureの分離記録
  * 回帰テスト基盤
* 対象外:

  * rollback実装修正
  * Validation Profile実装
  * Diagnostic code追加
  * Report schema変更
  * Metadata schema変更
  * Quarantine実装
* 対象OS:

  * 論理契約: macOS / Linux / Windows
  * 初期実行環境: macOS arm64
* ステータス: PROPOSED
* 完了状態:

  * NOT STARTED
  * IN PROGRESS
  * IMPLEMENTED
  * VALIDATED
  * BLOCKED
* Repository標準検証入口:

  * `./reason ci --json`

---

# 2. 背景

ReasonScript Install Foundation v1.1の実更新検証において、ReasonScript 0.5.0から0.5.1への更新を実行した際、更新後validationが失敗し、自動rollbackが開始された。

観測された最終report:

```json
{
  "status": "failed",
  "diagnostics": [
    {
      "code": "INS-UPD-012",
      "message": "Rollback failed: [Errno 2] No such file or directory: '/Users/chigenori/.reasonscript/versions/0.5.0/canonical_fixtures/phase1r'"
    }
  ]
}
```

一方、rollback後の実環境では以下が確認された。

```text
active_version: 0.5.0
reason --version: 0.5.0
reason doctor: healthy
reason install-info: pass
reason install-validate: pass
```

さらに、`current.json`は以下を示した。

```json
{
  "activation_status": "active",
  "active_version": "0.5.0",
  "previous_version": "0.5.1",
  "schema_version": "reasonscript-current-installation/1.0"
}
```

つまり、active pointer restorationおよび運用環境復旧は成功しているが、復旧後validationが0.5.0に存在しない0.5.1固有のPhase 1R fixtureを参照し、rollback全体を失敗と誤分類している。

Phase R1では、この障害を再現可能なテストとして固定する。

---

# 3. Phase R1の目的

Phase R1の目的は、今回発生したrollback障害を、将来の修正実装が検証可能な形で再現・固定することである。

本Phaseでは以下を実現する。

1. ReasonScript 0.5.0相当のlegacy installation fixtureを作成する
2. ReasonScript 0.5.1相当の更新package fixtureを作成する
3. 0.5.1 activation後にpost-install validationを意図的に失敗させる
4. rollback処理を起動させる
5. active pointerが0.5.0へ戻ることを記録する
6. 0.5.0に存在しない`canonical_fixtures/phase1r`参照を再現する
7. pointer restoration成功とrollback validation失敗を別々に観測する
8. 現行実装の誤分類をテストとして固定する
9. Phase R2以降の修正が同じシナリオで検証できるようにする

---

# 4. Phase R1の非目的

Phase R1では以下を行わない。

* rollback validationのVersion-aware化
* 0.5.0 legacy validation profile追加
* optional validationのskip処理
* `INS-UPD-012`適用条件修正
* `current.json` schema変更
* `update_report` schema変更
* failed version quarantine
* active pointer切替方式変更
* launcher実装変更
* post-install validation内容変更
* user data preservation実装変更
* Linux実機認証
* Windows実機認証

Phase R1は、現行障害を正確に固定するための観測フェーズである。

---

# 5. 対象障害

## 5.1 障害ID

```text
IF-RB-LEGACY-001
```

## 5.2 障害名

```text
Legacy Restored Version Incorrectly Validated with Newer Phase 1R Fixtures
```

## 5.3 発生条件

以下の条件がすべて成立した場合に発生する。

1. 既存active versionがReasonScript 0.5.0
2. 更新packageがReasonScript 0.5.1
3. 0.5.1 packageにPhase 1R fixtureが含まれる
4. 0.5.1 activation後validationが失敗する
5. 自動rollbackが0.5.0へactive pointerを戻す
6. rollback validationが0.5.1向けPhase 1R validation pathを再利用する
7. 0.5.0 directoryに`canonical_fixtures/phase1r`が存在しない

## 5.4 観測結果

```text
Pointer restoration: success
Restored launcher execution: success
Restored version: 0.5.0
Baseline health: pass
Phase 1R fixture lookup: fail
Top-level rollback classification: failed
Diagnostic: INS-UPD-012
```

---

# 6. 再現シナリオ

## 6.1 標準シナリオ

```text
Installed ReasonScript 0.5.0
  ↓
Validate current installation
  ↓
Apply ReasonScript 0.5.1 test package
  ↓
Install 0.5.1 into version directory
  ↓
Activate 0.5.1
  ↓
Force post-install validation failure
  ↓
Start automatic rollback
  ↓
Restore active pointer to 0.5.0
  ↓
Resolve restored launcher
  ↓
Run rollback validation
  ↓
Attempt to access:
versions/0.5.0/canonical_fixtures/phase1r
  ↓
FileNotFoundError
  ↓
INS-UPD-012
```

## 6.2 期待されるPhase R1結果

Phase R1時点では、現行実装の誤動作を意図的に再現する。

```text
Test reproduction: PASS
Current implementation behavior: DEFECT REPRODUCED
```

ここでいうPASSは、更新成功を意味しない。

意味:

```text
障害が期待どおり再現され、
観測項目が固定された
```

---

# 7. Fixture仕様

## 7.1 Fixture構成

推奨配置:

```text
tests/fixtures/install_update/rollback_legacy_reproduction/
  installed_0_5_0/
  package_0_5_1/
  expected/
```

詳細:

```text
installed_0_5_0/
  bin/
    reason
  versions/
    0.5.0/
      reason
      VERSION
      runtime/
      toolchain/
      schemas/
      standard_library/
      metadata/
  metadata/
    current.json
    install_state.json
    install_manifest.json
    installed_files.json
```

重要条件:

```text
versions/0.5.0/canonical_fixtures/phase1r
```

は存在してはならない。

## 7.2 0.5.0 fixtureの必須条件

* `VERSION`は`0.5.0`
* Install Foundation versionは`1.0`
* Runtime versionは`0.5.0`
* fixed launcherまたはtest launcherが0.5.0を解決可能
* `doctor`相当baseline checkがPASS可能
* `install-info`相当情報が取得可能
* `install-validate`相当validationがPASS可能
* Phase 1R fixtureを含まない
* `phase1r-validate`を提供しない、または利用不能である
* user data directoryを含めてもよいが、managed payloadから分離する

## 7.3 0.5.1 package fixtureの必須条件

```text
package_0_5_1/
  manifest.json
  checksums.json
  payload/
    VERSION
    reason
    bin/
      reason-runtime
      reason-updater
    canonical_fixtures/
      phase1r/
        tensor_namespace_probe.rsn
        tensor_integration_probe.rsn
        iterative_state_probe.rsn
```

必須条件:

* package versionは`0.5.1`
* minimum previous versionは`0.5.0`
* platformはtest環境と一致
* architectureはtest環境と一致
* checksumは正常
* staging validationはPASS
* activationまでは成功
* post-install validationだけを意図的に失敗させる

## 7.4 意図的失敗方式

失敗は決定的でなければならない。

推奨方式:

```text
test-only validation hook
```

または:

```text
fixture manifest flag:
force_post_install_validation_failure = true
```

禁止:

* ランダム失敗
* timing依存
* 実ファイル破損による不安定な失敗
* platform依存のpermission failure
* 実環境のPATH汚染
* network依存
* Python version依存
* repository外部状態依存

---

# 8. テスト構成

## 8.1 推奨テストファイル

```text
tests/install_update/
  test_rollback_legacy_failure_reproduction.py
```

必要に応じて分割:

```text
tests/install_update/
  test_rollback_legacy_fixture_contract.py
  test_rollback_legacy_failure_reproduction.py
  test_rollback_current_behavior_observation.py
```

## 8.2 テストクラスまたはテスト群

推奨構成:

```python
class TestLegacyRollbackFailureReproduction:
    def test_fixture_has_no_phase1r_directory(self):
        ...

    def test_update_reaches_activation(self):
        ...

    def test_post_install_validation_is_forced_to_fail(self):
        ...

    def test_active_pointer_is_restored_to_0_5_0(self):
        ...

    def test_restored_launcher_reports_0_5_0(self):
        ...

    def test_phase1r_fixture_lookup_fails(self):
        ...

    def test_current_implementation_reports_ins_upd_012(self):
        ...
```

---

# 9. 観測項目

Phase R1では、最低限以下を個別に記録する。

## 9.1 更新前状態

* active version
* previous version
* install foundation version
* runtime version
* installation health
* current metadata
* existing version directories

## 9.2 更新処理

* package validation
* staging result
* version installation result
* activation result
* post-install validation result
* failure phase
* failure reason

## 9.3 Rollback処理

* rollback start
* pointer restoration result
* restored active version
* launcher resolution result
* restored launcher execution result
* restored reported version
* fixture lookup path
* fixture lookup result
* final diagnostic
* final top-level status

## 9.4 復旧後状態

* active version
* fixed launcher version
* doctor status
* install-info status
* install-validate status
* required components
* current metadata
* failed version directory existence

---

# 10. Phase R1用観測モデル

修正前のschema変更を避けるため、Phase R1専用test observation modelを使用してよい。

推奨形式:

```json
{
  "schema_version": "reasonscript-rollback-reproduction-observation/1.0",
  "scenario_id": "rollback_legacy_0_5_0_from_0_5_1_failure",
  "update": {
    "from_version": "0.5.0",
    "to_version": "0.5.1",
    "activation_reached": true,
    "post_install_validation_failed": true
  },
  "rollback": {
    "started": true,
    "pointer_restored": true,
    "restored_version": "0.5.0",
    "launcher_resolved": true,
    "launcher_reported_version": "0.5.0",
    "phase1r_fixture_lookup_attempted": true,
    "phase1r_fixture_exists": false,
    "validation_failed": true
  },
  "current_behavior": {
    "top_level_status": "failed",
    "diagnostic_code": "INS-UPD-012"
  },
  "environment": {
    "operational_recovery_confirmed": true
  }
}
```

このmodelは正式Update Report schemaの代替ではない。

用途:

* テスト観測
* 障害固定
* Phase R2以降の比較
* before/after検証

---

# 11. 必須テストケース

## R1-TC-001 — Legacy fixture contract

### 条件

0.5.0 fixtureを読み込む。

### 検証

* versionが0.5.0
* install foundationが1.0
* baseline validation resourcesが存在
* `canonical_fixtures/phase1r`が存在しない

### 期待結果

```text
PASS
```

---

## R1-TC-002 — Update package contract

### 条件

0.5.1 test packageを読み込む。

### 検証

* package versionが0.5.1
* minimum previous versionが0.5.0
* checksum valid
* Phase 1R fixture存在
* forced validation failure設定存在

### 期待結果

```text
PASS
```

---

## R1-TC-003 — Update activation reached

### 条件

0.5.0 fixtureへ0.5.1 packageを適用する。

### 検証

* staging成功
* version installation成功
* 0.5.1 activation成功
* failureがactivation前ではない

### 期待結果

```text
activation_reached = true
```

---

## R1-TC-004 — Forced post-install failure

### 条件

0.5.1 activation後validationを実行する。

### 検証

* 意図したvalidation phaseで失敗
* failure reasonが決定的
* raw exceptionに依存しない
* rollbackが開始される

### 期待結果

```text
post_install_validation_failed = true
rollback_started = true
```

---

## R1-TC-005 — Pointer restoration succeeds

### 条件

自動rollbackを実行する。

### 検証

* active pointerが0.5.0へ戻る
* current metadataが0.5.0をactiveとして示す
* 0.5.0 directoryが存在する

### 期待結果

```text
pointer_restored = true
active_version = 0.5.0
```

---

## R1-TC-006 — Restored launcher remains operational

### 条件

rollback後のfixed launcherまたはrestored version launcherを起動する。

### 検証

* 実行可能
* reported versionが0.5.0
* launcher pathが0.5.0を解決

### 期待結果

```text
launcher_resolved = true
reported_version = 0.5.0
```

---

## R1-TC-007 — Phase 1R fixture mismatch reproduced

### 条件

現行rollback validationを継続する。

### 検証

以下のpath参照が発生する。

```text
versions/0.5.0/canonical_fixtures/phase1r
```

さらに、対象pathが存在しない。

### 期待結果

```text
phase1r_fixture_lookup_attempted = true
phase1r_fixture_exists = false
```

---

## R1-TC-008 — Current diagnostic misclassification reproduced

### 条件

fixture lookup failure後のreportを取得する。

### 検証

* top-level statusが`failed`
* diagnostic codeが`INS-UPD-012`
* messageがrollback failureとして分類される

### 期待結果

```text
diagnostic_code = INS-UPD-012
```

本テストは現行欠陥の固定であり、Phase R3以降で期待値を変更する。

---

## R1-TC-009 — Operational recovery independently confirmed

### 条件

`INS-UPD-012`発生後に0.5.0 baseline状態を検証する。

### 検証

* active versionが0.5.0
* launcherが0.5.0を返す
* doctor相当checkがhealthy
* install-info相当checkがpass
* install-validate相当checkがpass

### 期待結果

```text
operational_recovery_confirmed = true
```

これにより、rollback failure reportと実環境復旧の矛盾を固定する。

---

## R1-TC-010 — Deterministic reproduction

### 条件

同じfixtureで再現テストを複数回実行する。

### 検証

以下が一致する。

* failure phase
* restored version
* fixture lookup path
* diagnostic code
* observation ordering
* canonical observation JSON

### 期待結果

```text
determinism = pass
```

---

# 12. テストの期待状態

Phase R1完了時点では、テストを2種類に分ける。

## 12.1 Fixture contract tests

通常のPASSテストとする。

対象:

* R1-TC-001
* R1-TC-002
* R1-TC-003
* R1-TC-004
* R1-TC-005
* R1-TC-006
* R1-TC-009
* R1-TC-010

## 12.2 Known-defect characterization tests

現行欠陥を期待値として固定する。

対象:

* R1-TC-007
* R1-TC-008

これらはテストスイート上でPASSさせる。

例:

```python
assert observation.phase1r_fixture_lookup_attempted is True
assert observation.current_diagnostic_code == "INS-UPD-012"
```

`xfail`の使用は原則避ける。

理由:

* 障害が再現されなかった場合に明確に検出したい
* Phase R2以降で期待値を意図的に変更したい
* 現行動作のcharacterization testとして固定したい

---

# 13. 実装制約

## 13.1 Production code変更制約

Phase R1ではproduction rollback behaviorを変更してはならない。

許可:

* test hook
* fixture loader
* observation recorder
* test-only failure injection
* test helper
* test report生成

禁止:

* rollback validation条件変更
* fixture lookup skip
* diagnostic変更
* metadata更新方式変更
* report status変更

## 13.2 Test-only hook

Post-install failure injectionが必要な場合、以下を満たす。

* production defaultでは無効
* test codeから明示的に有効化
* environment variableだけに依存しない
* public CLI契約へ露出しない
* release packageへ含めない
* deterministic

推奨例:

```python
UpdateTestHooks(
    force_post_install_validation_failure=True
)
```

## 13.3 実インストール保護

テストは実ユーザー環境を使用してはならない。

禁止対象:

```text
~/.reasonscript
/Users/chigenori/.reasonscript
```

必ずtemporary install rootを使用する。

例:

```text
/tmp/reasonscript-r1-<test-id>/
```

---

# 14. User data preservation確認

Phase R1の主目的ではないが、再現中にuser-managed dataを破壊しないことを確認する。

Fixtureへ以下を含めてよい。

```text
config/user.json
projects/sample-project/
artifacts/sample-artifact.json
cache/sample-cache
```

再現後:

* config保持
* project保持
* artifact保持
* cache保持

これらは現行v1.1 preservation contractの非回帰確認として扱う。

---

# 15. Diagnostic観測要件

Phase R1では、以下をそのまま記録する。

* code
* severity
* category
* phase
* message
* recovery hint
* attempted version
* restored version
* missing path

ただし、テストassertionではabsolute temporary root全体に依存しない。

推奨canonicalization:

```text
<install-root>/versions/0.5.0/canonical_fixtures/phase1r
```

Timestamp、PID、temporary prefixはcomparisonから除外する。

---

# 16. 成果物

## 16.1 Phase R1仕様書

```text
docs/specifications/
  ReasonScript_Install_Foundation_v1_1_1_Phase_R1_Rollback_Failure_Reproduction.md
```

## 16.2 Fixture

```text
tests/fixtures/install_update/
  rollback_legacy_reproduction/
```

## 16.3 Tests

```text
tests/install_update/
  test_rollback_legacy_fixture_contract.py
  test_rollback_legacy_failure_reproduction.py
  test_rollback_current_behavior_observation.py
```

## 16.4 Machine-readable observation

```text
artifacts/install_foundation_v1_1_1/phase_r1/
  rollback_failure_reproduction_observation.json
```

## 16.5 実装記録

```text
docs/implementation/
  ReasonScript_Install_Foundation_v1_1_1_Phase_R1_Implementation_Report.md
```

## 16.6 検証記録

```text
docs/validation/
  ReasonScript_Install_Foundation_v1_1_1_Phase_R1_Validation_Report.md
```

---

# 17. 実行コマンド

推奨focused test:

```bash
python3 -m pytest \
  tests/install_update/test_rollback_legacy_fixture_contract.py \
  tests/install_update/test_rollback_legacy_failure_reproduction.py \
  tests/install_update/test_rollback_current_behavior_observation.py \
  -v --tb=short
```

Install/update regression:

```bash
python3 -m pytest tests/install_update -v --tb=short
```

Repository regression:

```bash
./reason ci --json
```

Formattingおよび差分確認:

```bash
git diff --check
git status --short
```

---

# 18. Acceptance criteria

Phase R1は以下をすべて満たした場合に`VALIDATED`とする。

## 18.1 Fixture Gate

* 0.5.0 legacy installation fixtureが存在
* 0.5.1 update package fixtureが存在
* 0.5.0 fixtureにPhase 1R directoryが存在しない
* 0.5.1 fixtureにPhase 1R directoryが存在する
* fixtureがrepository外部状態へ依存しない

## 18.2 Reproduction Gate

* updateがactivationまで到達
* post-install validationが意図的に失敗
* automatic rollbackが開始
* active pointerが0.5.0へ復元
* restored launcherが0.5.0を報告
* Phase 1R fixture mismatchが再現
* `INS-UPD-012`が現行挙動として観測

## 18.3 State Separation Gate

以下が個別に記録される。

* update failure
* pointer restoration success
* launcher recovery success
* fixture lookup failure
* current diagnostic classification
* operational recovery success

## 18.4 Determinism Gate

同じfixtureによる再実行で以下が一致する。

* scenario result
* restored version
* failure phase
* missing logical path
* diagnostic code
* canonical observation JSON

## 18.5 Safety Gate

* 実ユーザーinstall rootを使用しない
* user data fixtureが保持される
* repository sourceを変更しない
* networkを使用しない
* platform外部状態へ依存しない

## 18.6 Regression Gate

* focused tests PASS
* existing install/update tests PASS
* `reason ci --json` PASS
* Phase R1以外のruntime semanticsに変更なし

---

# 19. Phase R1完了時の正式判定

Phase R1の正式結果は次の形式で記録する。

```text
Phase R1 Status: VALIDATED

Rollback defect reproduction: PASS
Active pointer restoration observation: PASS
Restored launcher observation: PASS
Legacy Phase 1R fixture mismatch reproduction: PASS
INS-UPD-012 misclassification reproduction: PASS
Operational recovery contradiction observation: PASS
Determinism: PASS
Repository regression: PASS
```

ここでの`VALIDATED`は、rollback defectが修正されたことを意味しない。

意味:

```text
障害が再現可能かつ決定的なテストとして固定され、
Phase R2以降の修正を評価できる状態になった
```

---

# 20. Phase R2への移行条件

以下を満たした後、Phase R2 — Validation Profile基盤へ移行する。

1. Legacy 0.5.0 fixtureが固定済み
2. 0.5.1 failure package fixtureが固定済み
3. pointer restoration successが観測可能
4. Phase 1R fixture mismatchが観測可能
5. `INS-UPD-012`誤分類が観測可能
6. operational recovery successが別項目として観測可能
7. observation JSONが決定的
8. focused testがPASS
9. Repository CIがPASS

Phase R2では、Phase R1で固定した期待値のうち以下を変更対象とする。

```text
phase1r_fixture_lookup_attempted:
  true → false

rollback validation:
  failed → passed

diagnostic:
  INS-UPD-012 → no fatal rollback diagnostic

top-level status:
  failed → failed_rolled_back
```

---

# 21. Changelog案

## ReasonScript Install Foundation v1.1.1 Phase R1 — Rollback Failure Reproduction

### Added

* Added a deterministic legacy 0.5.0 installation fixture without Phase 1R validation resources.
* Added a deterministic 0.5.1 update package fixture with forced post-install validation failure.
* Added rollback lifecycle characterization tests.
* Added independent observations for update failure, pointer restoration, launcher recovery, rollback validation failure, and operational recovery.
* Added a machine-readable rollback reproduction observation artifact.

### Validation

* 0.5.0 to failed 0.5.1 update reproduction: PASS
* Active pointer restoration to 0.5.0: PASS
* Restored launcher execution: PASS
* Missing legacy Phase 1R fixture condition: REPRODUCED
* Current `INS-UPD-012` classification: REPRODUCED
* Restored 0.5.0 operational health: CONFIRMED
* Deterministic rerun: PASS
* Repository regression: PASS

### Compatibility

* No production rollback behavior was changed.
* No diagnostic contract was changed.
* No metadata schema was changed.
* No update report schema was changed.
* Runtime, Tensor, Phase 1R, Artifact, Golden, and CI semantics remain unchanged.

---

# 22. 最終定義

Phase R1は、Install Foundation v1.1のrollback障害を、再現可能かつ決定的なcharacterization testとして固定するフェーズである。

完成状態は以下で定義する。

```text
Legacy 0.5.0 Installation Fixture
  ↓
0.5.1 Update Activation
  ↓
Deterministic Post-install Failure
  ↓
Pointer Restoration to 0.5.0
  ↓
Restored Launcher Recovery
  ↓
Incorrect Phase 1R Fixture Lookup
  ↓
INS-UPD-012 Reproduction
  ↓
Operational Recovery Independently Confirmed
```

Phase R1では欠陥を修正しない。

欠陥を正確に観測し、Phase R2以降の修正が正しく評価できる基準を構築する。
