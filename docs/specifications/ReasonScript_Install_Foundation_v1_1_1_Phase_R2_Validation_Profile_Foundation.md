# ReasonScript Install Foundation v1.1.1

# Phase R2 — Validation Profile Foundation Specification

## 1. 文書情報

* 文書名: ReasonScript Install Foundation v1.1.1 — Phase R2 Validation Profile Foundation Specification
* 略称: Install Foundation v1.1.1 Phase R2
* Specification ID: `reasonscript-install-foundation-v1.1.1-phase-r2/1.0`
* 対象プロジェクト: ReasonScript
* 対象Release:

  * Legacy restored release: ReasonScript 0.5.0
  * Current update release: ReasonScript 0.5.1
* 前工程:

  * Phase R1 — Rollback Failure Reproduction and Current Behavior Freeze
* 後続工程:

  * Phase R3 — Restored-Version Validation Separation
  * Phase R4 — Rollback Result Model Separation
* 前提仕様:

  * ReasonScript Install Foundation v1.0
  * ReasonScript Install Foundation v1.1
  * Version-Aware Rollback Validation and Recovery State Correction Specification
  * Phase R1 Rollback Failure Reproduction Specification
* 対象範囲:

  * Validation Profileモデル
  * Validation capability表現
  * Release Unit別profile解決
  * Legacy release fallback
  * CLI command capability検出
  * Fixture capability検出
  * Component capability検出
  * Schema capability検出
  * Deterministic profile serialization
  * Profile validation
* 対象外:

  * Rollback validation経路の変更
  * Post-install validation経路の変更
  * `INS-UPD-012`適用条件変更
  * Update Report schema変更
  * Current Installation metadata schema変更
  * Failed version quarantine
  * Rollback state machine変更
  * Public CLI command追加
* 対象OS:

  * 論理契約: macOS / Linux / Windows
  * 初期検証環境: macOS arm64
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

Phase R1では、ReasonScript 0.5.0から0.5.1への更新失敗後に、active pointerが0.5.0へ正常に復元される一方、rollback validationが0.5.1固有のPhase 1R fixtureを0.5.0へ要求し、`INS-UPD-012`を発生させる現行挙動を決定的なcharacterization testとして固定した。

観測された不整合:

```text
Restored version: 0.5.0
Active pointer restoration: success
Restored launcher: operational
Baseline installation health: pass
Phase 1R fixture availability: absent
Rollback validation result: failed
Diagnostic: INS-UPD-012
```

根本原因は、更新処理が次の情報を明示的に区別していないことである。

```text
- Release Unitが宣言する検証能力
- Release Unitに実際に存在するcommand
- Release Unitに実際に存在するfixture
- Release Unitに実際に存在するschema
- Install Foundation世代ごとの互換検証契約
```

Phase R2では、各Release Unitが利用可能なvalidation capabilityを決定的に表現・解決する`ValidationProfile`基盤を追加する。

ただし、このPhaseでは解決したprofileをproduction rollbackへまだ接続しない。

---

# 3. Phase R2の目的

Phase R2の目的は、任意のinstalled Release Unitについて、「何を必須検証として実行でき、何をoptional検証として実行できないか」を、例外を発生させず決定的に判定できる基盤を構築することである。

本Phaseでは以下を実現する。

1. `ValidationProfile`のcanonical modelを定義する
2. Baseline validation capabilityを表現する
3. Optional feature validation capabilityを表現する
4. CLI commandの存在と利用可能性を検出する
5. Fixture directoryおよびfixture fileの存在を検出する
6. Required componentの存在を検出する
7. Required schemaの存在を検出する
8. Release metadataからprofile declarationを読み取る
9. Declarationがないlegacy releaseにfallback profileを適用する
10. ReasonScript 0.5.0向けlegacy profileを解決する
11. ReasonScript 0.5.1向けPhase 1R対応profileを解決する
12. Capability absenceを`FileNotFoundError`ではなく正規化された状態として返す
13. 同一Release Unitから常に同一profileを生成する
14. Phase R1のproduction behaviorおよびcharacterization testを変更しない

---

# 4. Phase R2の非目的

Phase R2では以下を行わない。

* `run_post_install_validation()`の変更
* `run_restored_version_validation()`のproduction接続
* rollback時のfixture root選択変更
* rollback後のPhase 1R validation skip
* `INS-UPD-012`の抑制
* `failed_rolled_back` status導入
* Rollback Result model導入
* metadata v1.1 migration
* `previous_version` semantics変更
* failed Release Unit quarantine
* rollback CLI変更
* update CLI出力変更
* public `validation-profile` CLI追加
* manifest signing
* online profile取得
* remote capability discovery

Phase R2完了時点でも、Phase R1で固定した現行rollback defectは再現される。

---

# 5. 設計原則

## 5.1 Release Unit owns its capabilities

Validation capabilityは、検証対象のRelease Unit自身に基づいて解決する。

```text
Target Release Unit
  ↓
Release-local metadata
  ↓
Release-local commands
  ↓
Release-local fixtures
  ↓
Release-local schemas
  ↓
ValidationProfile
```

更新packageや別Versionのfilesystemを暗黙に参照してはならない。

## 5.2 Declaration and availability are distinct

機能がmetadataで宣言されていることと、実際に利用可能であることは分離する。

例:

```text
declared = true
command_available = true
fixture_available = false
effective_status = unavailable
```

## 5.3 Capability absence is data, not an exception

Optional command、fixture、schema、componentの不存在は、原則として例外ではなくprofile状態として表現する。

禁止:

```python
fixture_path.iterdir()
# path不存在によりFileNotFoundError
```

必須:

```python
if not fixture_path.is_dir():
    return CapabilityStatus.UNAVAILABLE
```

## 5.4 Legacy releases remain immutable

ReasonScript 0.5.0 directoryへprofile file、fixture、schema、markerを追加してはならない。

Legacy compatibilityはresolver側で提供する。

## 5.5 Resolution is deterministic

同一filesystem、同一metadata、同一platformから生成されるprofileは、field orderを含め決定的でなければならない。

## 5.6 Resolution does not execute validation

Phase R2のresolverはvalidation commandを実行しない。

実施するのは以下に限定する。

* declaration読取
* path確認
* file type確認
* executable確認
* command registration確認
* schema存在確認
* component存在確認

---

# 6. 用語定義

## 6.1 Validation Profile

Release Unitが提供するbaselineおよびoptional validation capabilityを正規化したmodel。

## 6.2 Baseline Validation

Release Unitの基本的な運用可能性を検証するための必須能力。

例:

```text
version
doctor
install_info
install_validate
basic_runtime
basic_parser
```

## 6.3 Optional Feature Validation

特定Releaseまたは追加Componentに依存する検証。

例:

```text
phase1r_validate
tensor_smoke
loop_smoke
project_validate
visualization_smoke
```

## 6.4 Declared Capability

Release metadataまたは互換fallbackで、その機能を提供すると宣言された状態。

## 6.5 Available Capability

必要command、fixture、schema、componentが実際に存在し、利用条件を満たす状態。

## 6.6 Effective Capability

Declarationとavailabilityを統合した、後続validation plannerが使用する最終状態。

## 6.7 Legacy Fallback Profile

Validation Profile declarationを持たない旧Releaseに対して、Install Foundation互換表から生成するprofile。

---

# 7. Validation Profile model

## 7.1 Canonical schema

推奨model:

```json
{
  "schema_version": "reasonscript-validation-profile/1.0",
  "reason_version": "0.5.1",
  "install_foundation_version": "1.1",
  "runtime_version": "0.5.1",
  "profile_source": "release_metadata",
  "release_root": "<release-root>",
  "baseline": {},
  "features": {},
  "fixtures": {},
  "components": {},
  "schemas": {},
  "summary": {},
  "diagnostics": []
}
```

## 7.2 Python model候補

```python
@dataclass(frozen=True)
class ValidationProfile:
    schema_version: str
    reason_version: str
    install_foundation_version: str
    runtime_version: str
    profile_source: ProfileSource
    release_root: str
    baseline: Mapping[str, ValidationCapability]
    features: Mapping[str, ValidationCapability]
    fixtures: Mapping[str, FixtureCapability]
    components: Mapping[str, ComponentCapability]
    schemas: Mapping[str, SchemaCapability]
    summary: ValidationProfileSummary
    diagnostics: tuple[ValidationProfileDiagnostic, ...]
```

Immutable modelを推奨する。

## 7.3 Profile source

許容値:

```text
release_metadata
release_manifest
legacy_fallback
minimum_baseline
test_fixture
```

優先順位:

```text
release_metadata
  ↓
release_manifest
  ↓
legacy_fallback
  ↓
minimum_baseline
```

---

# 8. Capability status model

## 8.1 Status値

```text
available
unavailable
not_declared
invalid
unsupported
```

### available

宣言済みであり、必要resourceがすべて利用可能。

### unavailable

宣言済みだが、必要resourceの一部が不足。

### not_declared

Releaseが機能を宣言していない。

### invalid

Declarationまたはresource構造が不正。

### unsupported

Resolverまたはplatformがそのcapabilityを扱えない。

## 8.2 Required level

```text
required
optional
informational
```

## 8.3 Capability model

```json
{
  "id": "phase1r_validate",
  "category": "feature",
  "required_level": "optional",
  "declared": true,
  "status": "available",
  "command": "phase1r-validate",
  "command_available": true,
  "required_fixtures": [
    "canonical_fixtures/phase1r"
  ],
  "fixtures_available": true,
  "required_components": [],
  "components_available": true,
  "required_schemas": [],
  "schemas_available": true,
  "reasons": []
}
```

## 8.4 Unavailable例

```json
{
  "id": "phase1r_validate",
  "category": "feature",
  "required_level": "optional",
  "declared": true,
  "status": "unavailable",
  "command": "phase1r-validate",
  "command_available": true,
  "required_fixtures": [
    "canonical_fixtures/phase1r"
  ],
  "fixtures_available": false,
  "reasons": [
    "required_fixture_missing"
  ]
}
```

## 8.5 Not declared例

```json
{
  "id": "phase1r_validate",
  "category": "feature",
  "required_level": "optional",
  "declared": false,
  "status": "not_declared",
  "command": null,
  "command_available": false,
  "required_fixtures": [],
  "fixtures_available": false,
  "reasons": [
    "capability_not_declared"
  ]
}
```

---

# 9. Baseline capability定義

## 9.1 必須baseline IDs

Phase R2では以下を標準baseline capabilityとする。

| ID                 | 内容                       | 標準Required Level |
| ------------------ | ------------------------ | ---------------- |
| `version`          | Release version取得        | required         |
| `doctor`           | Environment health検証     | required         |
| `install_info`     | Installation inventory取得 | required         |
| `install_validate` | Installation contract検証  | required         |
| `cli_entry_point`  | Release CLI存在・実行可能性      | required         |
| `runtime_import`   | Runtime module存在         | required         |
| `parser_import`    | Parser module存在          | optional         |
| `schema_inventory` | 必須schema存在               | required         |
| `standard_library` | 標準ライブラリ存在                | required         |

## 9.2 Baseline command mapping

```text
version           → reason --version
doctor            → reason doctor --json
install_info      → reason install-info --json
install_validate  → reason install-validate --json
```

Phase R2ではcommandを実行せず、CLI registrationまたはparser definitionからcommand availabilityを判定する。

## 9.3 Minimum baseline

Release metadataもlegacy mappingも利用できない場合、次だけをminimum baselineとする。

```text
version
cli_entry_point
runtime_import
schema_inventory
standard_library
```

この場合:

```text
profile_source = minimum_baseline
```

diagnosticを記録するが、resolver自体をfatal failureにしない。

---

# 10. Optional feature capability定義

Phase R2で認識する標準feature IDs:

| ID                    | Command                  | 主なResource                   |
| --------------------- | ------------------------ | ---------------------------- |
| `phase1r_validate`    | `phase1r-validate`       | `canonical_fixtures/phase1r` |
| `tensor_smoke`        | internal / fixture-based | Tensor runtime、probe         |
| `loop_smoke`          | internal / fixture-based | iterative state probe        |
| `project_validate`    | `project validate`系      | Project validation modules   |
| `phase8_golden`       | `phase8-golden validate` | Phase 8 golden corpus        |
| `reasoning_runtime`   | `reasoning-runtime`      | reasoning schemas/runtime    |
| `visualization_smoke` | internal                 | visualization runtime        |
| `data_analysis_smoke` | internal                 | data runtime                 |
| `update_validate`     | `update --validate`      | update schemas/core          |

全featureを各Releaseへ必須とはしない。

---

# 11. Fixture capability model

## 11.1 Fixture定義

```json
{
  "id": "phase1r",
  "relative_path": "canonical_fixtures/phase1r",
  "declared": true,
  "status": "available",
  "path_type": "directory",
  "required_files": [
    "iterative_state_probe.rsn",
    "tensor_integration_probe.rsn",
    "tensor_namespace_probe.rsn"
  ],
  "missing_files": []
}
```

## 11.2 Fixture status

```text
available
missing
incomplete
invalid_type
not_declared
```

## 11.3 Directory存在だけでは不十分

Phase 1R fixtureはdirectoryの存在に加え、標準probe fileを確認する。

```text
canonical_fixtures/phase1r/
  iterative_state_probe.rsn
  tensor_integration_probe.rsn
  tensor_namespace_probe.rsn
```

一部だけ存在する場合:

```text
status = incomplete
```

## 11.4 Path safety

Fixture pathは必ずrelease root配下へ解決されなければならない。

禁止:

```text
../
absolute path
symlink escape
```

Resolverはpath traversalおよびrelease root外参照を拒否する。

---

# 12. Command capability detection

## 12.1 検出方法

Command availabilityは次の順で判定する。

1. Release metadataのcommand declaration
2. CLI command registry
3. CLI parser registration
4. Version別legacy mapping
5. 不明の場合はunavailable

## 12.2 実行禁止

Phase R2 resolverは以下を実行してはならない。

```bash
reason doctor --json
reason install-validate --json
reason phase1r-validate --json
```

Command availability検出によってsubprocessを起動してはならない。

## 12.3 Command alias

Aliasがある場合、canonical command IDへ正規化する。

例:

```text
phase1r validate
phase1r-validate
```

canonical:

```text
phase1r-validate
```

## 12.4 False positive防止

単なるsource file内文字列検索だけでcommand availableと判定してはならない。

少なくとも以下のいずれかを要求する。

* command registry entry
* argparse/subparser registration
* formal manifest declaration
* legacy compatibility mapping

---

# 13. Component capability detection

## 13.1 Component model

```json
{
  "id": "runtime-core",
  "relative_path": "runtime",
  "required": true,
  "status": "available"
}
```

## 13.2 標準Component

```text
cli
runtime-core
toolchain
scripts
frontend-core
schemas
standard-library
metadata
playground-backend
conformance-core
```

Releaseごとにrequired/optionalは異なり得る。

## 13.3 Component status

```text
available
missing
invalid_type
not_declared
```

## 13.4 Legacy manifest利用

0.5.0では`install_manifest.json`または`release_manifest.json`から既存Component inventoryを読み取り、Validation Profileへ投影してよい。

---

# 14. Schema capability detection

## 14.1 Schema model

```json
{
  "id": "install_validation",
  "relative_path": "schemas/install_validation.schema.json",
  "declared": true,
  "status": "available"
}
```

## 14.2 Baseline required schemas

最低限候補:

```text
install_manifest.schema.json
install_report.schema.json
install_validation.schema.json
release_manifest.schema.json
version_validation.schema.json
doctor.schema.json
```

ただし、Release世代に存在しない新schemaをlegacy Releaseへ要求してはならない。

## 14.3 Schema declaration source

優先順位:

1. validation profile declaration
2. release manifest component inventory
3. install manifest file inventory
4. legacy mapping
5. minimum baseline mapping

---

# 15. Release-local profile declaration

## 15.1 推奨配置

```text
metadata/validation_profile.json
```

または:

```text
metadata/release_manifest.json
  └─ validation_profile
```

Phase R2ではどちらか一方を正式採用し、二重sourceを避ける。

推奨:

```text
metadata/validation_profile.json
```

理由:

* validation contractを独立管理できる
* release manifest肥大化を防げる
* schema versionを独立進化できる
* test fixtureを構築しやすい

## 15.2 Declaration schema例

```json
{
  "schema_version": "reasonscript-validation-profile-declaration/1.0",
  "reason_version": "0.5.1",
  "install_foundation_version": "1.1",
  "baseline": {
    "version": {
      "required_level": "required",
      "command": "--version"
    },
    "doctor": {
      "required_level": "required",
      "command": "doctor"
    },
    "install_info": {
      "required_level": "required",
      "command": "install-info"
    },
    "install_validate": {
      "required_level": "required",
      "command": "install-validate"
    }
  },
  "features": {
    "phase1r_validate": {
      "required_level": "optional",
      "command": "phase1r-validate",
      "fixtures": [
        "phase1r"
      ]
    }
  },
  "fixtures": {
    "phase1r": {
      "path": "canonical_fixtures/phase1r",
      "path_type": "directory",
      "required_files": [
        "iterative_state_probe.rsn",
        "tensor_integration_probe.rsn",
        "tensor_namespace_probe.rsn"
      ]
    }
  }
}
```

---

# 16. Legacy 0.5.0 fallback profile

## 16.1 適用条件

以下を満たす場合に0.5.0 legacy fallbackを使用する。

```text
reason_version == 0.5.0
AND
validation profile declaration does not exist
AND
Install Foundation version == 1.0
```

## 16.2 Profile内容

```json
{
  "reason_version": "0.5.0",
  "install_foundation_version": "1.0",
  "profile_source": "legacy_fallback",
  "baseline": {
    "version": "available",
    "doctor": "available",
    "install_info": "available",
    "install_validate": "available",
    "cli_entry_point": "available",
    "runtime_import": "available",
    "schema_inventory": "available",
    "standard_library": "available"
  },
  "features": {
    "phase1r_validate": "not_declared",
    "tensor_smoke": "not_declared",
    "loop_smoke": "not_declared",
    "project_validate": "not_declared"
  },
  "fixtures": {
    "phase1r": "not_declared"
  }
}
```

## 16.3 重要制約

0.5.0 profile解決時に以下を参照してはならない。

```text
canonical_fixtures/phase1r
phase1r-validate
tensor namespace probe
iterative state probe
0.5.1 package metadata
0.5.1 staging directory
```

## 16.4 Legacy fallback diagnostic

```json
{
  "code": "VP-LEGACY-001",
  "severity": "info",
  "category": "validation_profile",
  "message": "A legacy validation profile was resolved for ReasonScript 0.5.0.",
  "reason_version": "0.5.0"
}
```

Phase R2ではInstall Updateの`INS-UPD-*` diagnostic codeを使用しない。

---

# 17. ReasonScript 0.5.1 profile

## 17.1 必須条件

ReasonScript 0.5.1 profileは少なくとも以下を表現する。

```text
baseline:
  version
  doctor
  install_info
  install_validate
  cli_entry_point
  runtime_import
  schema_inventory
  standard_library

features:
  phase1r_validate
  tensor_smoke
  loop_smoke
  project_validate

fixtures:
  phase1r
```

## 17.2 Phase 1R availability

次のすべてが成立する場合に`available`とする。

```text
phase1r declared
AND
phase1r command registered
AND
canonical_fixtures/phase1r exists
AND
three required probes exist
AND
required Phase 1R modules exist
```

## 17.3 Incomplete fixture例

1ファイル不足の場合:

```json
{
  "id": "phase1r",
  "status": "incomplete",
  "missing_files": [
    "tensor_namespace_probe.rsn"
  ]
}
```

連動するfeature:

```json
{
  "id": "phase1r_validate",
  "status": "unavailable",
  "reasons": [
    "required_fixture_incomplete"
  ]
}
```

Resolver自体は正常終了する。

---

# 18. Profile resolution algorithm

## 18.1 入力

```python
resolve_validation_profile(
    release_root: Path,
    expected_version: str | None = None,
    platform: PlatformInfo | None = None,
) -> ValidationProfile
```

## 18.2 処理順序

```text
1. Validate release_root
2. Resolve VERSION
3. Resolve Install Foundation version
4. Resolve Runtime version
5. Locate profile declaration
6. Parse declaration if present
7. Otherwise select legacy fallback
8. Otherwise use minimum baseline
9. Detect commands
10. Detect fixtures
11. Detect components
12. Detect schemas
13. Compute effective capability statuses
14. Generate summary
15. Sort diagnostics deterministically
16. Return immutable profile
```

## 18.3 Version mismatch

`expected_version`が指定され、実際のVersionと異なる場合:

```text
status: invalid
diagnostic: VP-RES-003
```

Fatal exceptionを外部へ出さず、typed errorまたはinvalid profileとして返す。

## 18.4 Missing release root

Release root不存在はresolver input errorである。

推奨:

```python
raise ValidationProfileResolutionError(
    code="VP-RES-001",
    message="Release root does not exist."
)
```

Optional resource不足とは区別する。

---

# 19. Validation Profile diagnostics

## 19.1 Diagnostic namespace

Phase R2では以下を使用する。

```text
VP-RES-xxx
VP-DECL-xxx
VP-CAP-xxx
VP-LEGACY-xxx
VP-PATH-xxx
```

## 19.2 推奨Diagnostic IDs

| Code            | 意味                                |
| --------------- | --------------------------------- |
| `VP-RES-001`    | Release root不存在                   |
| `VP-RES-002`    | VERSION読取不能                       |
| `VP-RES-003`    | Expected version mismatch         |
| `VP-RES-004`    | Install Foundation version不明      |
| `VP-DECL-001`   | Profile declaration parse failure |
| `VP-DECL-002`   | Unsupported declaration schema    |
| `VP-DECL-003`   | Duplicate capability ID           |
| `VP-CAP-001`    | Declared command unavailable      |
| `VP-CAP-002`    | Required fixture missing          |
| `VP-CAP-003`    | Required fixture incomplete       |
| `VP-CAP-004`    | Required component missing        |
| `VP-CAP-005`    | Required schema missing           |
| `VP-LEGACY-001` | Legacy fallback selected          |
| `VP-LEGACY-002` | Minimum baseline selected         |
| `VP-PATH-001`   | Path escapes release root         |
| `VP-PATH-002`   | Invalid path type                 |
| `VP-PATH-003`   | Symlink escapes release root      |

## 19.3 Severity policy

```text
info:
  legacy fallback selected
  optional capability not declared

warning:
  optional capability unavailable
  optional fixture incomplete
  minimum baseline selected

error:
  required baseline resource missing
  declaration invalid
  expected version mismatch

fatal:
  release root invalid
  required path escapes release root
```

Phase R2ではこれらをInstall Update reportへまだ投影しない。

---

# 20. Profile summary

## 20.1 Summary model

```json
{
  "baseline_total": 9,
  "baseline_available": 9,
  "baseline_unavailable": 0,
  "features_total": 8,
  "features_available": 4,
  "features_unavailable": 0,
  "features_not_declared": 4,
  "fixtures_total": 1,
  "fixtures_available": 1,
  "required_capabilities_ready": true,
  "optional_capabilities_ready": true
}
```

## 20.2 Required readiness

```text
required_capabilities_ready = true
```

となる条件:

* required baseline capabilityがすべてavailable
* required componentがすべてavailable
* required schemaがすべてavailable
* required fixtureがすべてavailable

Optional capabilityはこの値へ影響しない。

---

# 21. Canonical serialization

## 21.1 Ordering

以下をlexicographic orderで出力する。

* baseline keys
* feature keys
* fixture keys
* component keys
* schema keys
* diagnostics

## 21.2 Path canonicalization

実環境依存のabsolute pathはcanonical artifactでは以下へ置換する。

```text
<release-root>
```

例:

```text
<release-root>/canonical_fixtures/phase1r
```

## 21.3 Excluded nondeterministic values

* timestamp
* PID
* temporary directory prefix
* inode
* filesystem creation time
* process-specific environment values

## 21.4 Canonical JSON

```text
sort_keys = true
indent = 2
ensure_ascii = false
trailing newline = true
```

---

# 22. 推奨実装構成

## 22.1 Production files

```text
toolchain/install_update/
  validation_profile.py
  validation_profile_resolver.py
```

小規模に保つ場合は、初期実装を単一fileとしてよい。

```text
toolchain/install_update/validation_profile.py
```

## 22.2 Schema

```text
schemas/
  validation_profile.schema.json
  validation_profile_declaration.schema.json
```

Schema追加がPhase R2 scope内であることを明記する。

これはUpdate ReportやCurrent Installation metadata schema変更ではない。

## 22.3 Release declaration

```text
metadata/
  validation_profile.json
```

0.5.1にのみ追加する。

0.5.0 test fixtureへ追加してはならない。

## 22.4 Tests

```text
tests/install_update/
  test_validation_profile_model.py
  test_validation_profile_resolution.py
  test_legacy_validation_profile.py
  test_validation_capability_detection.py
  test_validation_profile_paths.py
  test_validation_profile_determinism.py
```

---

# 23. 必須テストケース

## R2-TC-001 — Canonical model construction

### 条件

完全なprofile dataから`ValidationProfile`を構築する。

### 検証

* immutable
* schema version一致
* required fields存在
* canonical serialization可能

### 期待結果

```text
PASS
```

---

## R2-TC-002 — Legacy 0.5.0 profile resolution

### 条件

Phase R1の0.5.0 legacy fixtureを使用する。

### 検証

* `profile_source = legacy_fallback`
* baseline required capabilityがavailable
* Phase 1Rはnot_declared
* Phase 1R fixtureを探索対象にしない
* exceptionなし

### 期待結果

```text
reason_version = 0.5.0
phase1r_validate = not_declared
```

---

## R2-TC-003 — 0.5.1 declared profile resolution

### 条件

0.5.1 fixtureを使用する。

### 検証

* declaration読取成功
* `profile_source = release_metadata`
* Phase 1R declared
* command available
* fixture available
* required probe files存在

### 期待結果

```text
phase1r_validate = available
```

---

## R2-TC-004 — Missing optional fixture

### 条件

0.5.1 profileでPhase 1Rを宣言し、fixture directoryを削除する。

### 検証

* resolver正常終了
* Phase 1R featureがunavailable
* fixtureがmissing
* `VP-CAP-002`
* raw `FileNotFoundError`なし

### 期待結果

```text
PASS
```

---

## R2-TC-005 — Incomplete fixture

### 条件

Phase 1R probeを1件削除する。

### 検証

* fixture statusがincomplete
* missing fileが記録
* feature statusがunavailable
* diagnosticが決定的

### 期待結果

```text
PASS
```

---

## R2-TC-006 — Command not registered

### 条件

Feature declarationは存在するがcommand registrationがない。

### 検証

* command_available = false
* capability status = unavailable
* `VP-CAP-001`

### 期待結果

```text
PASS
```

---

## R2-TC-007 — Required component missing

### 条件

Required baseline componentを削除する。

### 検証

* component status = missing
* required readiness = false
* `VP-CAP-004`

### 期待結果

```text
PASS
```

---

## R2-TC-008 — Required schema missing

### 条件

Profileでrequiredとされたschemaを削除する。

### 検証

* schema status = missing
* required readiness = false
* `VP-CAP-005`

### 期待結果

```text
PASS
```

---

## R2-TC-009 — Path traversal rejection

### 条件

Fixture declarationへ次を設定する。

```text
../../external
```

### 検証

* release root外参照を拒否
* `VP-PATH-001`
* external pathを読み取らない

### 期待結果

```text
PASS
```

---

## R2-TC-010 — Symlink escape rejection

### 条件

Release root内symlinkが外部directoryを指す。

### 検証

* escapeを拒否
* `VP-PATH-003`

### 期待結果

```text
PASS
```

Platformがsymlinkを扱えない場合は明示skipとする。

---

## R2-TC-011 — Unknown release fallback

### 条件

Profile declarationなし、legacy mappingなし。

### 検証

* minimum baselineを選択
* `VP-LEGACY-002`
* resolverは正常終了
* optional featuresはnot_declared

### 期待結果

```text
PASS
```

---

## R2-TC-012 — Version mismatch

### 条件

Expected versionが0.5.1、実Releaseが0.5.0。

### 検証

* mismatchを検出
* `VP-RES-003`
* 誤ったprofileを返さない

### 期待結果

```text
PASS
```

---

## R2-TC-013 — Deterministic profile

### 条件

同一fixtureからprofileを複数回解決する。

### 検証

* canonical JSON一致
* diagnostic order一致
* capability order一致
* path canonicalization一致

### 期待結果

```text
PASS
```

---

## R2-TC-014 — Phase R1 compatibility

### 条件

Phase R1 test suiteを実行する。

### 検証

* characterization testが引き続きPASS
* 現行`INS-UPD-012`再現が維持
* rollback production behavior変更なし

### 期待結果

```text
PASS
```

---

# 24. Phase R1との互換性契約

Phase R2は、Phase R1 artifactおよびtest fixtureを再利用してよい。

ただし、Phase R1 canonical observationを変更してはならない。

維持する期待値:

```text
phase1r_fixture_lookup_attempted = true
rollback.validation_failed = true
current_behavior.diagnostic_code = INS-UPD-012
operational_recovery_confirmed = true
```

Phase R2で追加したresolverをproduction rollbackへ接続しないため、この期待値は変化しない。

Phase R3で初めて次へ変更する。

```text
phase1r_fixture_lookup_attempted:
  true → false
```

---

# 25. Production behavior freeze

Phase R2では、次のproduction functionsのbehaviorを変更してはならない。

```text
update package validation
staging
activation
post-install validation
automatic rollback
pointer restoration
rollback validation
rollback diagnostics
current metadata writing
update report generation
```

許可されるproduction変更:

* 独立したValidation Profile model追加
* 独立したresolver追加
* profile schema追加
* 0.5.1 release profile declaration追加
* 内部unit test向けAPI export

禁止される接続:

```text
rollback core
  ↓
new validation profile resolver
```

これはPhase R3で実施する。

---

# 26. Safety要件

## 26.1 Read-only resolution

ResolverはRelease Unitを変更してはならない。

禁止:

* profile file自動生成
* missing fixture生成
* missing schema生成
* permission変更
* metadata migration
* checksum更新

## 26.2 User installation protection

Unit testは実ユーザーの以下を参照しない。

```text
~/.reasonscript
/Users/chigenori/.reasonscript
```

Temporary fixture rootを使用する。

## 26.3 Network independence

Profile resolutionはnetworkへ接続しない。

## 26.4 Repository independence

Installed Release Unit profileの解決時に、checkout repository内の同名resourceへfallbackしてはならない。

---

# 27. Machine-readable artifacts

## 27.1 0.5.0 canonical profile

```text
artifacts/install_foundation_v1_1_1/phase_r2/
  validation_profile_0_5_0.json
```

期待:

```text
profile_source = legacy_fallback
phase1r_validate = not_declared
```

## 27.2 0.5.1 canonical profile

```text
artifacts/install_foundation_v1_1_1/phase_r2/
  validation_profile_0_5_1.json
```

期待:

```text
profile_source = release_metadata
phase1r_validate = available
```

## 27.3 Summary

```text
artifacts/install_foundation_v1_1_1/phase_r2/
  validation_profile_foundation_summary.json
```

推奨形式:

```json
{
  "schema_version": "reasonscript-validation-profile-foundation-summary/1.0",
  "status": "validated",
  "legacy_0_5_0_profile": "passed",
  "release_0_5_1_profile": "passed",
  "command_detection": "passed",
  "fixture_detection": "passed",
  "component_detection": "passed",
  "schema_detection": "passed",
  "path_safety": "passed",
  "determinism": "passed",
  "phase_r1_compatibility": "passed",
  "repository_ci": "passed",
  "diagnostics": []
}
```

---

# 28. 成果物

## 28.1 仕様書

```text
docs/specifications/
  ReasonScript_Install_Foundation_v1_1_1_Phase_R2_Validation_Profile_Foundation.md
```

## 28.2 Production implementation

```text
toolchain/install_update/
  validation_profile.py
```

必要に応じて:

```text
toolchain/install_update/
  validation_profile_resolver.py
```

## 28.3 Schemas

```text
schemas/
  validation_profile.schema.json
  validation_profile_declaration.schema.json
```

## 28.4 Release declaration

```text
metadata/
  validation_profile.json
```

## 28.5 Tests

```text
tests/install_update/
  test_validation_profile_model.py
  test_validation_profile_resolution.py
  test_legacy_validation_profile.py
  test_validation_capability_detection.py
  test_validation_profile_paths.py
  test_validation_profile_determinism.py
```

## 28.6 Canonical artifacts

```text
artifacts/install_foundation_v1_1_1/phase_r2/
  validation_profile_0_5_0.json
  validation_profile_0_5_1.json
  validation_profile_foundation_summary.json
```

## 28.7 Implementation report

```text
docs/implementation/
  ReasonScript_Install_Foundation_v1_1_1_Phase_R2_Implementation_Report.md
```

## 28.8 Validation report

```text
docs/validation/
  ReasonScript_Install_Foundation_v1_1_1_Phase_R2_Validation_Report.md
```

---

# 29. 実行コマンド

## 29.1 Focused tests

```bash
python3 -m pytest \
  tests/install_update/test_validation_profile_model.py \
  tests/install_update/test_validation_profile_resolution.py \
  tests/install_update/test_legacy_validation_profile.py \
  tests/install_update/test_validation_capability_detection.py \
  tests/install_update/test_validation_profile_paths.py \
  tests/install_update/test_validation_profile_determinism.py \
  -v --tb=short
```

## 29.2 Phase R1 compatibility

```bash
python3 -m pytest \
  tests/install_update/test_rollback_legacy_failure_reproduction.py \
  -v --tb=short
```

## 29.3 Install/update regression

```bash
python3 -m pytest tests/install_update -v --tb=short
```

## 29.4 Schema validation

既存schema validation commandまたはtest suiteを使用する。

```bash
python3 -m pytest tests/schemas -v --tb=short
```

対象test pathが異なる場合はRepository既存構成に合わせる。

## 29.5 Repository CI

```bash
./reason ci --json
```

## 29.6 Diff validation

```bash
git diff --check
git status --short
```

---

# 30. Acceptance criteria

Phase R2は以下をすべて満たした場合に`VALIDATED`とする。

## 30.1 Model Gate

* Validation Profile modelが存在
* immutableまたは実質immutable
* schema versionが固定
* canonical serialization可能
* baselineとfeatureが分離
* declarationとavailabilityが分離

## 30.2 Legacy Profile Gate

* 0.5.0へlegacy fallback profileを解決
* baseline capabilityが正しくavailable
* Phase 1Rがnot_declared
* Phase 1R fixtureを要求しない
* 0.5.0 Release Unitを変更しない

## 30.3 Current Release Gate

* 0.5.1 profile declarationを解決
* Phase 1Rがdeclared
* command capabilityを検出
* fixture capabilityを検出
* required probeを検出
* profile sourceがrelease metadata

## 30.4 Capability Detection Gate

* command absenceを正規化
* fixture absenceを正規化
* incomplete fixtureを正規化
* component absenceを正規化
* schema absenceを正規化
* optional absenceでraw exceptionなし

## 30.5 Path Safety Gate

* relative pathのみ許可
* traversal拒否
* absolute path拒否
* symlink escape拒否
* release root外を読み取らない

## 30.6 Determinism Gate

* canonical JSON一致
* diagnostic order一致
* capability order一致
* path表現一致
* timestamp等を含まない

## 30.7 Production Freeze Gate

* rollback behavior変更なし
* post-install validation変更なし
* diagnostic契約変更なし
* update report schema変更なし
* current metadata schema変更なし
* Phase R1 characterization維持

## 30.8 Regression Gate

* R2 focused tests PASS
* R1 tests PASS
* install/update regression PASS
* schema tests PASS
* `./reason ci --json` PASS
* `git diff --check` PASS

---

# 31. Phase R2完了時の正式判定

```text
ReasonScript Install Foundation v1.1.1
Phase R2 — Validation Profile Foundation

Status: VALIDATED

Validation Profile model: PASS
Legacy 0.5.0 fallback resolution: PASS
ReasonScript 0.5.1 profile resolution: PASS
Command capability detection: PASS
Fixture capability detection: PASS
Component capability detection: PASS
Schema capability detection: PASS
Path safety: PASS
Deterministic serialization: PASS
Phase R1 compatibility: PASS
Production behavior freeze: PASS
Repository regression: PASS
```

`VALIDATED`は、rollback defectが修正されたことを意味しない。

意味:

```text
各Release Unitが提供するvalidation能力を、
Release-localかつ決定的に解決できる基盤が完成した
```

---

# 32. Phase R3への移行条件

以下をすべて満たした後、Phase R3 — Rollback Validation Separationへ移行する。

1. 0.5.0 legacy profileが解決可能
2. 0.5.1 declared profileが解決可能
3. Baseline capabilityを列挙可能
4. Optional feature capabilityを列挙可能
5. Phase 1R not_declaredとavailableを区別可能
6. Missing fixtureを例外なしで処理可能
7. Required readinessを計算可能
8. Canonical profile artifactが生成済み
9. Phase R1 testsがPASS
10. Repository CIがPASS
11. Production rollback behaviorが未変更

Phase R3では、初めて次を実施する。

```text
rollback core
  ↓
resolve_validation_profile(restored_release)
  ↓
run restored-version baseline validation
  ↓
skip not_declared optional features
```

Phase R3の主要期待値:

```text
0.5.0 restored profile:
  phase1r_validate = not_declared

rollback validation:
  phase1r fixture lookup = not executed
```

---

# 33. Changelog案

## ReasonScript Install Foundation v1.1.1 Phase R2 — Validation Profile Foundation

### Added

* Added an immutable Validation Profile model for Release Unit validation capabilities.
* Added baseline and optional feature capability contracts.
* Added Release-local command, fixture, component, and schema capability detection.
* Added a legacy ReasonScript 0.5.0 fallback validation profile.
* Added a declared ReasonScript 0.5.1 validation profile with Phase 1R capabilities.
* Added deterministic canonical Validation Profile serialization.
* Added path traversal and symlink escape protection for declared validation resources.
* Added machine-readable canonical profiles and validation summary artifacts.

### Validation

* Legacy 0.5.0 profile resolution: PASS
* ReasonScript 0.5.1 profile resolution: PASS
* Phase 1R declaration detection: PASS
* Missing optional fixture normalization: PASS
* Incomplete fixture normalization: PASS
* Command capability detection: PASS
* Component and schema capability detection: PASS
* Path safety: PASS
* Deterministic resolution: PASS
* Phase R1 characterization compatibility: PASS
* Repository regression: PASS

### Compatibility

* Production rollback behavior is unchanged.
* Post-install validation behavior is unchanged.
* Existing Install Foundation diagnostics are unchanged.
* Current Installation metadata schema is unchanged.
* Update Report schema is unchanged.
* Phase R1 canonical observation remains unchanged.
* Runtime, Tensor, Phase 1R, Artifact, Golden, and CI semantics remain unchanged.

---

# 34. 最終定義

Phase R2は、ReasonScript Release Unitごとのvalidation能力を、明示的・安全・決定的に表現する基盤を構築するPhaseである。

完成状態:

```text
ReasonScript Release Unit
  ↓
Read Release-local Declaration
  ↓
Fallback to Legacy Contract if Required
  ↓
Detect Commands
  ↓
Detect Fixtures
  ↓
Detect Components
  ↓
Detect Schemas
  ↓
Normalize Capability Status
  ↓
Generate Deterministic Validation Profile
```

0.5.0に対する期待:

```text
baseline validations: available
Phase 1R validation: not_declared
Phase 1R fixture requirement: none
```

0.5.1に対する期待:

```text
baseline validations: available
Phase 1R validation: available
Phase 1R fixtures: available
```

Phase R2では、このprofileをrollbackへまだ適用しない。

本Phaseの成果は、Phase R3でrestored Release Unitに適合するvalidation planを選択するための正式な判断基盤となる。
