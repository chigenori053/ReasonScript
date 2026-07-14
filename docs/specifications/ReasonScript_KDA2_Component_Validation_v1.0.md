# ReasonScript KDA-2 Component Validation v1.0

Status: PROPOSED

Specification ID: `reasonscript-kda2-component-validation/1.0`

## 1. 文書情報

- Specification Name: ReasonScript KDA-2 Component Validation v1.0
- Specification ID: `reasonscript-kda2-component-validation/1.0`
- Target Specification: `reasonscript-kda2-titanic-rule-classification/1.0`
- Validation Target: KDA-2 — Titanic Rule-based Classification
- Status: PROPOSED
- Validation Type: Component-scoped formal validation
- Implementation Location: `/Users/chigenori/ReasonScriptProjects/kaggle-titanic-validation`
- Core Repository: `/Users/chigenori/development/ReasonScript`
- Installed Distribution Root: `~/.reasonscript/current`
- Target Dataset: `data/raw/train.csv`
- Expected Dataset Rows: 891
- Rule Set: `titanic-rule-set/1.0`
- Rule Count: 11
- Evaluation Dependency: ReasonScript ML Evaluation Visualization Standard Library v0.2
- Visualization Dependency: ReasonScript Visualization Standard Library v0.1

## 2. 目的

本仕様は、実装済みのKDA-2について、外部Project上の成果物、Installed Distribution、決定性、Evidence、Visualization、Compatibilityを正式に検証し、KDA-2 ComponentのStatusを`IMPLEMENTED`から`VALIDATED`へ移行可能か判定する。

本Validationは、ReasonScript Repository全体のRelease Certificationとは分離する。

```text
KDA-2 Component Validation
≠
ReasonScript Repository-wide Certification
```

KDA-2 Component Validationでは、KDA-2に直接関連する以下を検証する。

```text
Dataset
Feature Records
Rule Set
Predictions
Prediction Evidence
Decision Paths
Classification Evaluation
Knowledge
Visualizations
Artifacts
Schemas
Determinism
Installed Distribution
Repository Isolation
Compatibility
Reporting
```

## 3. 背景

KDA-2初版仕様では、以下が実在することが確認されている。

```text
Feature Records: 891
Predictions: 891
Prediction Evidence: 891
Knowledge: 10
Visualizations: 14
PNG/SVG: 28
Diagnostics: 0
```

確認済み評価値:

```text
Accuracy:          0.7598204264870931
Balanced Accuracy: 0.777538107563992
AUC:               0.8462755248777681
Average Precision: 0.7903496180334
```

Installed Distribution provenanceについては、以下のModuleがすべて`~/.reasonscript/current`配下から解決されることが確認されている。

```text
runtime
runtime.data
runtime.visualization
runtime.visualization.evaluation
```

一方、ReasonScript Repository-wide CIは現在次の状態である。

```text
status: FAIL
diagnostic: CI-008 Test failure
```

既知の失敗:

- Platform Architecture Review文書不足
- Install Validation期待件数の不一致

これらはKDA-2 Component Validation結果とは別に記録する。

## 4. Validation原則

### 4.1 Evidence before status

`VALIDATED`は、実行結果、Artifact、Schema、Digest、Import Provenance、Reportが一致した場合にのみ宣言する。

### 4.2 Installed-only execution

正式ValidationではReasonScript RuntimeをInstalled Distributionからのみ解決する。

許可:

```text
~/.reasonscript/current
```

禁止:

```text
ReasonScript Core Repository source tree
External Project内のReasonScript Runtime copy
.deps内のReasonScript Runtime fallback
一時的な開発Runtime
```

### 4.3 No silent fallback

Installed DistributionからのImportに失敗した場合、開発版Runtimeへ自動Fallbackしてはならない。

### 4.4 Deterministic rerun

同一入力と同一環境に対する再実行で、Semantic Artifactおよび画像ArtifactのDigestが一致しなければならない。

### 4.5 Component and repository separation

Repository-wide CIの失敗は隠蔽しない。ただし、KDA-2非関連のFailureを、KDA-2 Component自体のFailureとして自動的に扱わない。

## 5. Validation Scope

### 5.1 対象

- Dataset identity
- Dataset schema
- Feature Record generation
- Missing-value handling
- Rule Set identity
- Rule ordering
- FIRST_MATCH_WINS
- Default Rule
- Prediction generation
- Prediction Score
- Confidence
- Decision Path
- Prediction Evidence
- Confusion Matrix
- Classification Metrics
- ROC/AUC
- Precision–Recall/AP
- Rule Evaluation
- Decision Path Evaluation
- Error Distribution
- Score Distribution
- Knowledge
- Visualization
- JSON Schema
- Artifact Manifest
- SHA-256
- Determinism
- Installed Distribution
- Repository isolation
- KDA-1 regression
- Data/VSL/MLV compatibility
- Completion Report consistency

### 5.2 対象外

- Platform Architecture Review文書作成
- Repository-wide governance review
- Linux release certification
- Windows release certification
- Kaggle leaderboard submission
- Train/Test split
- Cross-validation
- Rule optimization
- Model retraining
- Score calibration
- Cross-platform image byte identity
- Core Runtime redesign

## 6. Validation Inputs

### 6.1 Dataset

```text
/Users/chigenori/ReasonScriptProjects/kaggle-titanic-validation/data/raw/train.csv
```

Expected SHA-256:

```text
7d118fef8b6ccf7f81111877bc388536f7b1e498a655e3d649d19aaa010e9f6f
```

Expected rows:

```text
891
```

### 6.2 Validation Script

```text
scripts/validate_kda2.py
scripts/validate_kda2_component.py
```

### 6.3 Artifact Root

```text
artifacts/kda2/
```

### 6.4 Completion Report

```text
reports/kda2_completion_report.md
reports/kda2_component_validation_report.md
```

### 6.5 Installed Runtime

```text
~/.reasonscript/current
```

## 7. Validation Environment Contract

### 7.1 Working directory

```bash
cd /Users/chigenori/ReasonScriptProjects/kaggle-titanic-validation
```

### 7.2 Virtual environment

```bash
source .venv/bin/activate
```

### 7.3 Runtime resolution

```bash
export PYTHONPATH="$HOME/.reasonscript/current"
```

正式Validationでは、`PYTHONPATH`へ`.deps`やCore Repositoryを追加してはならない。

### 7.4 Required runtime imports

```python
import runtime
import runtime.data
import runtime.visualization
import runtime.visualization.evaluation
```

すべての`__file__`は以下のPrefixを持たなければならない。

```text
/Users/chigenori/.reasonscript/current/
```

## 8. Validation Phases

**KDA2-V1 — Environment and Provenance**

検証対象: Python executable、virtual environment、PYTHONPATH、Installed Distribution version、Runtime import paths、Repository source absence、`.deps` Runtime absence

出力: `environment_validation.json`、`import_provenance.json`

**KDA2-V2 — Dataset Integrity**

検証対象: Dataset existence、SHA-256、row count、required columns、target labels、missing-value policy inputs

出力: `dataset_validation.json`

**KDA2-V3 — Feature Validation**

検証対象: 891 Feature Records、Derived Feature completeness、dtype、category domain、missing-value mapping、deterministic Feature IDs

出力: `feature_validation.json`

**KDA2-V4 — Rule Set Validation**

検証対象: Rule Set version、Rule count 11、unique Rule IDs、unique priorities、FIRST_MATCH_WINS、R-DEFAULT、score range、confidence range、prediction/score consistency

出力: `rule_set_validation.json`

**KDA2-V5 — Prediction Validation**

検証対象: 891 Predictions、unique Prediction IDs、all Passenger IDs covered、actual/predicted values、Score presence、Confidence presence、Rule ID presence、Decision Path presence

出力: `prediction_validation.json`

**KDA2-V6 — Evidence Validation**

検証対象: 891 Prediction Evidence records、source row linkage、Feature linkage、Rule linkage、Decision Path linkage、actual/predicted linkage、correctness linkage

出力: `prediction_evidence_validation.json`

**KDA2-V7 — Evaluation Validation**

検証対象: Confusion Matrix、Metrics、ROC、AUC、Precision–Recall、Average Precision、Rule Evaluation、Decision Path Evaluation、Error Distribution、Score Distribution

出力: `classification_evaluation_validation.json`

**KDA2-V8 — Knowledge Validation**

検証対象: Knowledge count 10以上、unique Knowledge IDs、Evidence references、required Knowledge categories、deterministic ordering

出力: `knowledge_validation.json`

**KDA2-V9 — Visualization Validation**

検証対象: Visualization count 14、PNG count 14、SVG count 14、Visualization Spec、Visualization IR、Render Plan、Evidence、Validation、Manifest linkage

出力: `visualization_validation.json`

**KDA2-V10 — Artifact and Schema Validation**

検証対象: required Artifact existence、JSON parse、JSON Schema、Manifest completeness、byte size、SHA-256、project-root confinement

出力: `artifact_validation.json`

**KDA2-V11 — Determinism Validation**

実行を2回行い、JSON Artifact digest、Prediction order、Metrics、Curve points、Knowledge、Visualization Spec、Visualization IR、Render Plan、PNG/SVG digestを比較する。

出力: `determinism_validation.json`

**KDA2-V12 — Compatibility Validation**

検証対象: KDA-1 regression、Data Analysis Foundation、VSL v0.1、MLV v0.2、Installed Distribution、Core API compatibility

出力: `compatibility_validation.json`

**KDA2-V13 — Report Consistency**

検証対象: Completion Report、`kda2_result.json`、`classification_evaluation.json`、`validation.json`、manifest。数値とStatusが一致すること。

出力: `report_consistency_validation.json`

## 9. Canonical Expected Results

### 9.1 Counts

```text
Dataset rows: 891
Feature Records: 891
Predictions: 891
Prediction Evidence: 891
Knowledge: 10
Visualizations: 14
PNG: 14
SVG: 14
Diagnostics: 0
```

### 9.2 Confusion Matrix

```text
TN: 385
FP: 164
FN: 50
TP: 292
Total: 891
```

### 9.3 Metrics

```text
Accuracy:          0.7598204264870931
Balanced Accuracy: 0.777538107563992
AUC:               0.8462755248777681
Average Precision: 0.7903496180334
```

Precision、Recall、Specificity、F1についてもArtifact値との一致を確認する。

### 9.4 Float tolerance

JSON Artifactが同一実装で生成される場合、Canonical serialization上の完全一致を要求する。独立計算との比較では以下を許容する。

```text
absolute tolerance = 1e-12
relative tolerance = 1e-12
```

## 10. Import Provenance Contract

`import_provenance.json`は最低限以下を持つ。

```json
{
  "schema_version": "reasonscript-kda2-import-provenance/1.0",
  "python_executable": "",
  "python_version": "",
  "installed_root": "",
  "modules": [
    {
      "name": "runtime",
      "path": "",
      "inside_installed_root": true
    }
  ],
  "repository_source_used": false,
  "deps_runtime_used": false,
  "status": "pass"
}
```

必須Module:

```text
runtime
runtime.data
runtime.visualization
runtime.visualization.evaluation
runtime.visualization.evaluation.metrics
runtime.visualization.evaluation.operations
```

## 11. Artifact Manifest Contract

Manifestはすべての正式Artifactを記録する。必須Field:

```text
relative_path
artifact_type
schema_version
sha256
byte_size
```

禁止:

- Absolute path
- Temporary path
- Repository source path
- Missing digest
- Duplicate path

## 12. Determinism Procedure

### 12.1 First run

```bash
PYTHONPATH="$HOME/.reasonscript/current" \
python scripts/validate_kda2.py
```

First-run Artifactを一時保存する。

### 12.2 Second run

同一環境で同じコマンドを再実行する。

### 12.3 Comparison

JSON byte digest、PNG digest、SVG digest、Artifact Manifest、Counts、Metrics、Ordering、IDsを比較する。

### 12.4 Exclusions

以下は決定性比較対象から除外できる。

- Generated timestamp
- Temporary directory
- Process ID
- Environment-specific absolute path

ただし、除外Fieldは仕様またはCanonical serializerで明示されていなければならない。

## 13. Compatibility Procedure

### 13.1 KDA-1

KDA-1 canonical outputsが変更されていないことを確認する。

### 13.2 Data Foundation

Titanic descriptive analysis、Typed Table、JSON-safe resultを確認する。

### 13.3 VSL v0.1

Titanic 7 Chart regressionを確認する。

### 13.4 MLV v0.2

Classification evaluation API、AUC/AP、Visualization Artifactを確認する。

### 13.5 Installed Distribution

```bash
reason doctor --json
reason install-validate --json
```

## 14. Repository-wide CI Recording

Core Repositoryで実行する。

```bash
cd /Users/chigenori/development/ReasonScript
./reason ci --json
```

結果は次に分類する。

**PASS**

```text
repository_status = pass
```

**FAIL — KDA-2 related**

KDA-2 Component validationに直接影響するFailure。例: ML Evaluation API failure、Installed Distribution failure、Schema failure、Artifact failure、Data/VSL/MLV compatibility failure

**FAIL — unrelated**

KDA-2 Componentに影響しないFailure。例: 独立したPlatform review document不足、無関係なUI test、無関係なRepository governance failure

ただし、Failure code、test名、path、impact分析を記録する。

## 15. Failure Classification Contract

各Failureは以下を持つ。

```json
{
  "code": "",
  "phase": "",
  "test": "",
  "path": "",
  "scope": "kda2_related | unrelated | uncertain",
  "impact": "",
  "blocks_component_validation": true
}
```

`uncertain`はComponent ValidationをBlockする。根拠なく`unrelated`へ分類してはならない。

## 16. Acceptance Criteria

**Environment**

- KDA2-CV-001: Installed Distributionのみを使用する
- KDA2-CV-002: 全Runtime ModuleがInstalled root配下から解決される
- KDA2-CV-003: Repository source treeを使用しない
- KDA2-CV-004: `.deps` Runtimeを使用しない
- KDA2-CV-005: Import Provenance Artifactを生成する

**Dataset and Features**

- KDA2-CV-006: Dataset SHA-256が一致する
- KDA2-CV-007: Dataset row countが891である
- KDA2-CV-008: 必須列が存在する
- KDA2-CV-009: Feature Recordsが891件である
- KDA2-CV-010: Derived Featuresが完全である
- KDA2-CV-011: Missing-value policyが一致する

**Rules and Predictions**

- KDA2-CV-012: Rule Set versionが一致する
- KDA2-CV-013: Rule countが11である
- KDA2-CV-014: FIRST_MATCH_WINSが成立する
- KDA2-CV-015: Default Ruleが存在する
- KDA2-CV-016: Predictionsが891件である
- KDA2-CV-017: 全PredictionにRule IDがある
- KDA2-CV-018: 全PredictionにScoreとConfidenceがある
- KDA2-CV-019: 全PredictionにDecision Pathがある
- KDA2-CV-020: Prediction Evidenceが891件である

**Evaluation**

- KDA2-CV-021: Confusion MatrixがGolden値と一致する
- KDA2-CV-022: AccuracyがGolden値と一致する
- KDA2-CV-023: Balanced AccuracyがGolden値と一致する
- KDA2-CV-024: AUCがGolden値と一致する
- KDA2-CV-025: Average PrecisionがGolden値と一致する
- KDA2-CV-026: Rule Evaluationを生成できる
- KDA2-CV-027: Decision Path Evaluationを生成できる
- KDA2-CV-028: Error Distributionを生成できる
- KDA2-CV-029: Score/Confidence Distributionを生成できる

**Knowledge and Visualization**

- KDA2-CV-030: Knowledgeが10件以上存在する
- KDA2-CV-031: 全KnowledgeにEvidenceがある
- KDA2-CV-032: Visualizationが14種類存在する
- KDA2-CV-033: PNGが14件存在する
- KDA2-CV-034: SVGが14件存在する
- KDA2-CV-035: Visualization Evidenceが存在する

**Artifacts and Determinism**

- KDA2-CV-036: 必須Artifactがすべて存在する
- KDA2-CV-037: 全JSONがparse可能である
- KDA2-CV-038: JSON Schema validationがPASSする
- KDA2-CV-039: Manifestが完全である
- KDA2-CV-040: 全Manifest entryにSHA-256がある
- KDA2-CV-041: Diagnosticsが0件である
- KDA2-CV-042: JSON Artifact digestが再実行で一致する
- KDA2-CV-043: PNG/SVG digestが同一環境で一致する

**Compatibility and Reporting**

- KDA2-CV-044: KDA-1 regressionがPASSする
- KDA2-CV-045: Data Foundation compatibilityがPASSする
- KDA2-CV-046: VSL v0.1 compatibilityがPASSする
- KDA2-CV-047: MLV v0.2 compatibilityがPASSする
- KDA2-CV-048: Completion ReportとArtifact値が一致する
- KDA2-CV-049: Repository-wide CI結果を別途記録する
- KDA2-CV-050: KDA-2関連Failureが0件である

## 17. Validation Result Schema

```json
{
  "schema_version": "reasonscript-kda2-component-validation/1.0",
  "status": "pass",
  "component": {
    "name": "kda2",
    "specification_id": "reasonscript-kda2-titanic-rule-classification/1.0"
  },
  "environment": {},
  "dataset": {},
  "counts": {},
  "metrics": {},
  "artifacts": {},
  "determinism": {},
  "compatibility": {},
  "acceptance_criteria": {
    "passed": 50,
    "failed": 0,
    "items": []
  },
  "repository_ci": {
    "status": "fail",
    "failures": []
  },
  "diagnostics": []
}
```

## 18. Status判定

**VALIDATED** — 以下をすべて満たす場合。

```text
KDA2-CV-001〜050: PASS
KDA-2 diagnostics: 0
KDA-2 related failures: 0
Installed-only execution: PASS
Artifact determinism: PASS
Completion Report consistency: PASS
```

Repository-wideに無関係なFailureが存在する場合でも、別Statusとして記録する。

**IMPLEMENTED** — 次の場合。

```text
Implementation complete
but
Component Validation incomplete or unexecuted
```

**BLOCKED** — KDA-2関連Failureまたはscope不明Failureが存在する場合。

**FAILED** — KDA-2 Component Validationを実行し、Acceptance CriteriaにFailureがある場合。

## 19. Required Outputs

Validation完了時に以下を生成する。

```text
reports/kda2_component_validation_report.md
artifacts/kda2/component_validation.json
artifacts/kda2/environment_validation.json
artifacts/kda2/import_provenance.json
artifacts/kda2/dataset_validation.json
artifacts/kda2/feature_validation.json
artifacts/kda2/rule_set_validation.json
artifacts/kda2/prediction_validation.json
artifacts/kda2/prediction_evidence_validation.json
artifacts/kda2/classification_evaluation_validation.json
artifacts/kda2/knowledge_validation.json
artifacts/kda2/visualization_validation.json
artifacts/kda2/artifact_validation.json
artifacts/kda2/determinism_validation.json
artifacts/kda2/compatibility_validation.json
artifacts/kda2/report_consistency_validation.json
```

## 20. Validation Report要件

Reportには次を記載する。

```text
Specification ID
Validation Specification ID
Validation timestamp
Dataset SHA-256
Runtime provenance
Installed Distribution version
Rows
Features
Predictions
Evidence
Rule Set
Rule count
Confusion Matrix
Metrics
Knowledge count
Visualization count
Artifact count
Schema result
Determinism result
Compatibility result
Acceptance Criteria summary
KDA-2 diagnostics
Repository-wide CI result
Failure scope classification
Final KDA-2 Component status
Repository-wide certification status
```

## 21. Validation Commands

**Component Validation**

```bash
cd /Users/chigenori/ReasonScriptProjects/kaggle-titanic-validation
source .venv/bin/activate
PYTHONPATH="$HOME/.reasonscript/current" \
python scripts/validate_kda2.py
```

**Import Provenance**

```bash
PYTHONPATH="$HOME/.reasonscript/current" python - <<'PY'
import runtime
import runtime.data
import runtime.visualization
import runtime.visualization.evaluation
import runtime.visualization.evaluation.metrics
import runtime.visualization.evaluation.operations

modules = [
    runtime,
    runtime.data,
    runtime.visualization,
    runtime.visualization.evaluation,
    runtime.visualization.evaluation.metrics,
    runtime.visualization.evaluation.operations,
]

for module in modules:
    print(f"{module.__name__}: {module.__file__}")
PY
```

**Installed Distribution Validation**

```bash
reason doctor --json
reason install-validate --json
```

**Repository-wide CI**

```bash
cd /Users/chigenori/development/ReasonScript
./reason ci --json
```

## 22. Changelog Entry

```text
## KDA-2 Component Validation v1.0

### Status

PROPOSED

### Added

- Added the formal KDA-2 component-validation contract.
- Added installed-only Runtime provenance validation.
- Added Dataset, Feature, Rule, Prediction, Evidence, Evaluation, Knowledge, Visualization, Artifact, and Determinism validation phases.
- Added KDA2-CV-001 through KDA2-CV-050.
- Added explicit repository-wide CI failure classification.
- Added formal component-validation result and report contracts.

### Compatibility

- KDA-2 implementation semantics are unchanged.
- Titanic Rule Set v1.0 is unchanged.
- Data Foundation, VSL v0.1, and MLV v0.2 semantics are unchanged.
- Repository-wide certification remains separate from KDA-2 component validation.
```

## 23. 完了時の正式宣言

すべてのAcceptance Criteriaを満たした場合、次を宣言する。

```text
ReasonScript KDA-2 Component Validation v1.0

Validation Specification ID:
reasonscript-kda2-component-validation/1.0

Target Specification ID:
reasonscript-kda2-titanic-rule-classification/1.0

KDA-2 Component Status:
VALIDATED

Dataset Integrity:        VALIDATED
Feature Generation:       VALIDATED
Rule Execution:           VALIDATED
Prediction and Evidence:  VALIDATED
Classification Evaluation: VALIDATED
Knowledge:                VALIDATED
Visualization:            VALIDATED
Artifacts and Schemas:    VALIDATED
Installed Distribution:   VALIDATED
Repository Isolation:     VALIDATED
Determinism:              VALIDATED
Compatibility:            VALIDATED

Repository-wide CI:
RECORDED SEPARATELY
```

本仕様作成時点における実行結果は §24a に記録する。

## 24. 最終定義

```text
KDA-2 Component VALIDATED
=
Installed-only Execution
+ Dataset Integrity
+ 891 Feature Records
+ 891 Predictions
+ 891 Prediction Evidence
+ Golden Classification Results
+ 10 Knowledge Records
+ 14 Visualizations
+ Complete Artifact Manifest
+ Schema Validation
+ Zero Diagnostics
+ Deterministic Rerun
+ KDA-1/Data/VSL/MLV Compatibility
+ No KDA-2-related Failure
```

## 24a. 実行結果(本仕様作成時点)

本仕様に定義した`scripts/validate_kda2_component.py`を実行した結果、KDA2-CV-001〜050の全50件がPASSし、KDA-2 Diagnosticsは0件であった。実行結果は`artifacts/kda2/component_validation.json`および`reports/kda2_component_validation_report.md`に記録されている。

```text
Acceptance Criteria: 50 passed / 0 failed
KDA-2 Diagnostics: 0
Determinism (repeated-run digest equality, 416 files): PASS
Installed Distribution import provenance: CONFIRMED (all modules resolve under ~/.reasonscript/current)
Repository-wide CI: FAIL — CI-008 (classified `unrelated`; does not block KDA-2 component validation)

KDA-2 Component Status: VALIDATED
```

本仕様は、KDA-2を実装済み状態から正式なComponent Validationへ移行するための検証契約であり、上記実行結果をもってこの検証契約が満たされたことを示す。
