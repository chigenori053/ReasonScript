# ReasonScript KDA-2 Titanic Rule-based Classification v1.0

Status: VALIDATED (KDA-2 Component; see §24.1. Repository-wide certification is recorded separately and remains FAIL — CI-008, unrelated.)

Specification ID: `reasonscript-kda2-titanic-rule-classification/1.0`

## 1. 文書情報

- Specification Name: ReasonScript KDA-2 Titanic Rule-based Classification v1.0
- Specification ID: `reasonscript-kda2-titanic-rule-classification/1.0`
- Validation Series: ReasonScript Kaggle Data Analysis Validation
- Milestone: KDA-2
- Status: VALIDATED (KDA-2 Component; see §24.1)
- Specification Type: Initial specification
- Implementation Location: `/Users/chigenori/ReasonScriptProjects/kaggle-titanic-validation`
- Core Repository: `/Users/chigenori/development/ReasonScript`
- Target Dataset: Kaggle Titanic `train.csv`
- Dataset Rows: 891
- Classification Type: Binary classification
- Negative Label: `0`
- Positive Label: `1`
- Rule Evaluation Policy: `FIRST_MATCH_WINS`
- Rule Set Version: `titanic-rule-set/1.0`
- Primary Runtime: ReasonScript Python Reference Backend
- Installed Distribution Target: `~/.reasonscript/current`
- ML Evaluation Dependency: ReasonScript ML Evaluation Visualization Standard Library v0.2

## 2. 仕様の位置づけ

本仕様は、既存仕様に対する改訂ではなく、外部プロジェクトに実装済みのKDA-2を正式なReasonScript検証マイルストーンとして定義する初版仕様である。

本仕様作成時点で、KDA-2実装、成果物、実行スクリプト、完了レポートは外部プロジェクトに存在する。

```text
/Users/chigenori/ReasonScriptProjects/kaggle-titanic-validation
```

ReasonScriptコアリポジトリには、KDA-2本体の実装および正式仕様は存在しない。

したがって、本仕様の初期Statusは次とする。

```text
IMPLEMENTED
```

`VALIDATED`への移行は、本仕様に定義するValidation要件を正式に満たした後に行う。

## 3. 目的

KDA-2の目的は、ReasonScriptを用いてTitanic Datasetに対する決定的かつ説明可能なRule-based binary classificationを構築し、以下を一貫して生成できることを実証することである。

```text
Raw CSV
→ Typed Feature Records
→ Declarative Rule Evaluation
→ Row-level Prediction
→ Prediction Score
→ Confidence
→ Decision Path
→ Prediction Evidence
→ Classification Evaluation
→ Knowledge
→ Visualization
→ Deterministic Artifacts
```

本仕様は、高性能なTitanic予測モデルの構築だけを目的としない。

主要な検証対象は次である。

- 全行に対する決定的なPrediction
- Rule IDによる判断根拠
- Decision Pathによる推論経路
- Row-level Prediction Evidence
- 分類評価指標
- RuleおよびDecision Path評価
- ML Evaluation Visualization
- Knowledge生成
- JSON-safe Artifact
- Installed Distribution上での再現可能性

## 4. 実装実態

### 4.1 外部プロジェクト

実装は次の外部プロジェクトに存在する。

```text
/Users/chigenori/ReasonScriptProjects/kaggle-titanic-validation
```

主要ファイル:

```text
scripts/validate_kda2.py
reports/kda2_completion_report.md
artifacts/kda2/kda2_result.json
artifacts/kda2/feature_table.json
artifacts/kda2/predictions.json
artifacts/kda2/prediction_evidence.json
artifacts/kda2/classification_evaluation.json
artifacts/kda2/evaluation_artifact_manifest.json
```

### 4.2 コアリポジトリ

ReasonScriptコアリポジトリ:

```text
/Users/chigenori/development/ReasonScript
```

コアリポジトリは以下を提供する。

- Data Analysis Foundation
- Visualization Standard Library
- ML Evaluation Visualization v0.2
- Installed Distribution
- Install Manifest
- Install Validation
- Canonical CI

KDA-2のDomain-specific implementationは外部プロジェクト側に置く。

## 5. Dataset Contract

### 5.1 Dataset

入力Dataset:

```text
data/raw/train.csv
```

確認済みSHA-256:

```text
7d118fef8b6ccf7f81111877bc388536f7b1e498a655e3d649d19aaa010e9f6f
```

### 5.2 Expected Rows

```text
891
```

### 5.3 Required Columns

```text
PassengerId
Survived
Pclass
Name
Sex
Age
SibSp
Parch
Ticket
Fare
Cabin
Embarked
```

### 5.4 Target

```text
target_column = Survived
negative_label = 0
positive_label = 1
```

### 5.5 Input Mode

```text
CSV_DIRECT
```

事前集計されたPrediction入力を使用してはならない。

## 6. Feature Contract

KDA-2は、各乗客についてFeature Recordを生成する。

確認済みFeature Record数:

```text
891
```

### 6.1 Base Features

```text
PassengerId
Pclass
Sex
Age
SibSp
Parch
Fare
Cabin
Embarked
```

`Survived`はPrediction生成には使用せず、評価時のみ参照する。

### 6.2 Derived Features

最低限、以下を生成する。

```text
FamilySize
IsAlone
AgeGroup
FareBand
FamilyBand
HasCabin
EmbarkedNormalized
```

### 6.3 FamilySize

```text
FamilySize = SibSp + Parch + 1
```

### 6.4 IsAlone

```text
IsAlone = FamilySize == 1
```

### 6.5 AgeGroup

```text
child       Age < 14
adolescent  14 <= Age < 18
adult       18 <= Age < 60
senior      Age >= 60
missing     Age is missing
```

### 6.6 FareBand

```text
missing  Fare is missing
low      Fare < 10
medium   10 <= Fare < 30
high     30 <= Fare < 100
premium  Fare >= 100
```

### 6.7 FamilyBand

```text
alone   FamilySize == 1
small   2 <= FamilySize <= 4
large   FamilySize >= 5
```

### 6.8 HasCabin

```text
HasCabin = Cabin is present
```

## 7. Missing-value Policy

**Age** — Missing Ageは自動補完せず、次として扱う。

```text
AgeGroup = missing
```

**Fare** — Missing Fare:

```text
FareBand = missing
```

**Embarked** — Missing Embarked:

```text
EmbarkedNormalized = missing
```

**Cabin** — Missing Cabin:

```text
HasCabin = false
```

**Sex / Pclass / Survived** — Missingまたは不正な値は分類または評価を継続できないため、ErrorまたはFatal Diagnosticとする。

## 8. Rule Model Contract

### 8.1 Rule Set

Rule Set version:

```text
titanic-rule-set/1.0
```

確認済みRule数:

```text
11
```

### 8.2 Evaluation Policy

```text
FIRST_MATCH_WINS
```

RuleはPriority順に評価し、最初に成立したRuleを採用する。

### 8.3 Required Rule Fields

```text
rule_id
priority
description
conditions
prediction
prediction_score
confidence
```

### 8.4 Default Rule

全Predictionを保証するため、Default Ruleを必須とする。

```text
R-DEFAULT
```

### 8.5 Rule Identity

Rule IDは安定していなければならない。

```text
R-001
R-002
...
R-DEFAULT
```

## 9. Prediction Contract

確認済みPrediction数:

```text
891
```

各Predictionは最低限、以下を持つ。

```json
{
  "prediction_id": "pred_...",
  "passenger_id": 1,
  "actual": 0,
  "predicted": 0,
  "prediction_score": 0.12,
  "confidence": 0.88,
  "rule_id": "R-009",
  "decision_path_id": "path_...",
  "decision_path": [],
  "evidence_refs": []
}
```

### 9.1 Prediction Score

範囲:

```text
0.0 <= prediction_score <= 1.0
```

Prediction Scoreは、positive classに対するRule-based tendencyである。校正済み確率とはみなさない。

### 9.2 Confidence

範囲:

```text
0.0 <= confidence <= 1.0
```

Confidenceは、採用Ruleの判断強度を表す。Prediction Scoreとは別の値として扱う。

### 9.3 Prediction Label

Default threshold:

```text
predicted = 1 if prediction_score >= 0.5 else 0
```

RuleのPredictionとScore thresholdは一致しなければならない。

## 10. Decision Path Contract

全PredictionにDecision Pathを付与する。

例:

```json
[
  "sex=male",
  "pclass=3",
  "age_group=adult",
  "matched_rule=R-009",
  "prediction=0"
]
```

Decision Pathは以下を含む。

- 判断に使用した主要Feature
- 採用Rule
- Prediction

Decision Path IDはCanonical representationから生成する。

```text
decision_path_id = SHA-256(canonical decision path)
```

## 11. Prediction Evidence Contract

確認済みPrediction Evidence数:

```text
891
```

各Evidenceは最低限、以下を保持する。

```text
evidence_id
prediction_id
dataset_ref
source_row_id
passenger_id
feature_values
derived_feature_values
matched_rule_id
rule_set_version
decision_path_id
prediction
prediction_score
confidence
actual
correct
```

Evidenceは次の追跡を可能にする。

```text
Source row
→ Feature Record
→ Rule
→ Decision Path
→ Prediction
→ Evaluation
```

## 12. Classification Evaluation Contract

ML Evaluation Visualization Standard Library v0.2を使用する。

必須評価:

```text
Confusion Matrix
Normalized Confusion Matrix
Accuracy
Precision
Recall
Specificity
F1
Balanced Accuracy
ROC Curve
AUC
Precision–Recall Curve
Average Precision
Rule Coverage
Rule Accuracy
Decision Path Frequency
Decision Path Accuracy
Error Distribution
Confidence Distribution
Prediction Score Distribution
```

## 13. Verified Classification Results

以下は実際のArtifactから確認された結果である。

Confusion Matrix:

```text
True Negative: 385
False Positive: 164
False Negative: 50
True Positive: 292
```

Total:

```text
891
```

Metrics:

```text
Accuracy:           0.7598204264870931
Balanced Accuracy:  0.777538107563992
Precision:          0.6403508772
Recall:             0.8538011696
Specificity:        0.7012750455
F1:                 0.7318295739
AUC:                0.8462755248777681
Average Precision:  0.7903496180334
```

数値は`kda2_result.json`および関連Artifactから確認された値である。

## 14. Knowledge Contract

確認済みKnowledge数:

```text
10
```

Knowledgeは最低限、以下の領域を扱う。

```text
Overall performance
Strongest rule
Highest-risk error group
False positive pattern
False negative pattern
Decision path concentration
Score separation
Model limitation
Missing-data impact
Validation conclusion
```

各KnowledgeはEvaluation EvidenceまたはPrediction Evidenceを参照する。

## 15. Visualization Contract

確認済みVisualization数:

```text
14
```

必須Visualization:

```text
1. Confusion Matrix
2. Normalized Confusion Matrix
3. Classification Metrics
4. ROC Curve
5. Precision–Recall Curve
6. Error Distribution by Sex
7. Error Distribution by Pclass
8. Error Distribution by AgeGroup
9. Rule Coverage
10. Rule Accuracy
11. Decision Path Frequency
12. Confidence Distribution
13. Prediction Score Distribution
14. Prediction Score by Actual Class
```

各Visualizationについて以下を生成する。

```text
PNG
SVG
Visualization Spec
Visualization IR
Render Plan
Evidence
Validation
Manifest record
```

確認済み画像数:

```text
PNG/SVG total = 28
```

## 16. Artifact Contract

Artifact root:

```text
artifacts/kda2/
```

必須Artifact:

```text
kda2_result.json
feature_table.json
rule_set.json
predictions.json
prediction_evidence.json
decision_paths.json
classification_evaluation.json
confusion_matrix.json
classification_metrics.json
roc_curve.json
precision_recall_curve.json
rule_coverage.json
rule_accuracy.json
decision_path_evaluation.json
error_distribution.json
score_distribution.json
classification_knowledge.json
validation.json
diagnostics.json
evaluation_artifact_manifest.json
```

Artifact Manifestは各Artifactについて以下を保持する。

```text
relative path
SHA-256
byte size
artifact type
schema version
```

## 17. Determinism Contract

同一Dataset、同一Rule Set、同一Runtime、同一描画環境では以下が一致しなければならない。

```text
Feature Records
Predictions
Prediction Scores
Confidence
Rule IDs
Decision Paths
Prediction Evidence
Confusion Matrix
Metrics
ROC points
Precision–Recall points
Rule Evaluation
Decision Path Evaluation
Knowledge
Visualization Specs
Visualization IR
Render Plans
JSON Artifact digests
PNG/SVG digests
```

確認済み結果:

```text
Repeated-run Artifact digest equality: PASS
```

## 18. Installed Distribution Contract

KDA-2はReasonScript Installed Distributionを使用して実行できなければならない。

Expected Runtime root:

```text
~/.reasonscript/current
```

必須確認対象:

```text
runtime
runtime.data
runtime.visualization
runtime.visualization.evaluation
```

全Moduleの`__file__`がInstalled Distribution配下に存在しなければならない。

### 18.1 Strict Installed-only Mode

Strict validationでは、ReasonScript Runtimeの探索元をInstalled Distributionへ限定する。

```bash
PYTHONPATH="$HOME/.reasonscript/current" \
python scripts/validate_kda2.py
```

`.deps`にReasonScript本体のRuntime copyが存在する場合、それを利用してはならない。

### 18.2 Import Provenance

実行結果またはReportに以下を保存する。

```text
runtime module path
runtime.data module path
runtime.visualization module path
runtime.visualization.evaluation module path
```

本仕様作成時点で確認された値(strict installed-only実行、`.deps`未使用):

```text
runtime:                      /Users/chigenori/.reasonscript/current/runtime/__init__.py
runtime.data:                 /Users/chigenori/.reasonscript/current/runtime/data/__init__.py
runtime.visualization:        /Users/chigenori/.reasonscript/current/runtime/visualization/__init__.py
runtime.visualization.evaluation: /Users/chigenori/.reasonscript/current/runtime/visualization/evaluation/__init__.py
```

全ModuleがInstalled Distribution(`~/.reasonscript/current` → `0.5.0`)配下から解決されることを確認した。

## 19. Compatibility Contract

以下への回帰を禁止する。

```text
KDA-1 descriptive analysis
Data Analysis Foundation
Visualization Standard Library v0.1
ML Evaluation Visualization v0.2
Tensor Standard Functions
Reason IR
ExecutionPlan
Simulation
Knowledge
Core CLI
```

確認済み:

```text
KDA-1 regression: PASS
```

## 20. Diagnostics Contract

KDA-2 valid executionでは次を要求する。

```text
diagnostics count = 0
```

確認済み:

```text
diagnostics = []
```

主なDiagnostic領域:

```text
KDA2-IN-*      Input
KDA2-FEAT-*    Feature
KDA2-RULE-*    Rule
KDA2-PRED-*    Prediction
KDA2-EVAL-*    Evaluation
KDA2-KNOW-*    Knowledge
KDA2-ART-*     Artifact
KDA2-DET-*     Determinism
```

## 21. Validation Scope

### 21.1 KDA-2 Component Validation

KDA-2 Component validationには以下を含む。

```text
Dataset integrity
Feature generation
Rule execution
Prediction generation
Prediction Evidence
Classification Evaluation
Knowledge
Visualization
Artifact schema
Artifact manifest
Determinism
Installed Distribution
Repository isolation
KDA-1 regression
Data/VSL/MLV compatibility
```

### 21.2 Repository-wide CI

ReasonScriptコアリポジトリのCanonical CIは別途記録する。

実行コマンド:

```bash
cd /Users/chigenori/development/ReasonScript
./reason ci --json
```

本仕様作成時点で確認されたRepository-wide CI結果:

```text
status: FAIL
diagnostic: CI-008 Test failure
```

確認された失敗:

```text
Platform Architecture Review report absence
  (platform_architecture_review_tests/test_platform_architecture_review.py::
   test_par_001_through_par_011_review_reports_exist_and_are_classified ほか7件)
Install validation expected-check-count mismatch
  (tests/installation/test_install_foundation.py::test_install_validation_contract,
   expected 26, actual 36)
```

Repository-wide CIの失敗は隠蔽してはならない。KDA-2 Component validationとRepository-wide release certificationは別のStatusとして記録する。

## 22. Acceptance Criteria

**Input and Feature**

- KDA2-AC-001: Dataset SHA-256が仕様値と一致する
- KDA2-AC-002: 891行を`CSV_DIRECT`で読み込める
- KDA2-AC-003: 891件のFeature Recordを生成できる
- KDA2-AC-004: 必須Derived Featureを生成できる
- KDA2-AC-005: Missing-value policyが決定的である

**Rule and Prediction**

- KDA2-AC-006: `titanic-rule-set/1.0`を読み込める
- KDA2-AC-007: Rule数が11件である
- KDA2-AC-008: `FIRST_MATCH_WINS`を保証する
- KDA2-AC-009: Default Ruleが存在する
- KDA2-AC-010: 891件のPredictionを生成できる
- KDA2-AC-011: 全PredictionにRule IDがある
- KDA2-AC-012: 全PredictionにScoreがある
- KDA2-AC-013: 全PredictionにConfidenceがある
- KDA2-AC-014: 全PredictionにDecision Pathがある
- KDA2-AC-015: 891件のPrediction Evidenceを生成できる

**Evaluation**

- KDA2-AC-016: Confusion Matrixを生成できる
- KDA2-AC-017: Classification Metricsを生成できる
- KDA2-AC-018: ROC CurveとAUCを生成できる
- KDA2-AC-019: Precision–Recall CurveとAverage Precisionを生成できる
- KDA2-AC-020: Rule CoverageとRule Accuracyを生成できる
- KDA2-AC-021: Decision Path Evaluationを生成できる
- KDA2-AC-022: Error Distributionを生成できる
- KDA2-AC-023: ScoreおよびConfidence Distributionを生成できる

**Knowledge and Visualization**

- KDA2-AC-024: 10件以上のKnowledgeを生成できる
- KDA2-AC-025: 全KnowledgeにEvidenceがある
- KDA2-AC-026: 14種類のVisualizationを生成できる
- KDA2-AC-027: 14件のPNGを生成できる
- KDA2-AC-028: 14件のSVGを生成できる
- KDA2-AC-029: Visualization Evidenceを生成できる

**Artifact and Determinism**

- KDA2-AC-030: Public ResultがJSON-safeである
- KDA2-AC-031: 必須Artifactを生成できる
- KDA2-AC-032: Artifact Manifestを生成できる
- KDA2-AC-033: Manifest内にSHA-256を保持する
- KDA2-AC-034: Diagnosticsが0件である
- KDA2-AC-035: Repeated-run JSON Artifact digestが一致する
- KDA2-AC-036: 同一描画環境でPNG/SVG digestが一致する

**Installed Distribution and Compatibility**

- KDA2-AC-037: Installed Distributionから実行できる
- KDA2-AC-038: ReasonScript ModuleのImport元を記録できる
- KDA2-AC-039: 全ReasonScript ModuleがInstalled root配下から解決される
- KDA2-AC-040: `.deps`内のReasonScript Runtimeに依存しない
- KDA2-AC-041: Repository source treeに依存しない
- KDA2-AC-042: KDA-1 regressionがPASSする
- KDA2-AC-043: Data/VSL/MLV compatibilityがPASSする

**Reporting and CI Scope**

- KDA2-AC-044: Completion Reportを生成する
- KDA2-AC-045: 実行結果とArtifact値がReportと一致する
- KDA2-AC-046: KDA-2 Component validation結果とRepository-wide CI結果を分離して記録する
- KDA2-AC-047: Repository-wide CIの実際の診断CodeとFailureを記録する
- KDA2-AC-048: KDA-2関連Failureが存在する場合は`VALIDATED`を宣言しない
- KDA2-AC-049: Repository-wide unrelated failureを隠蔽しない
- KDA2-AC-050: Status変更の根拠をCompletion Reportへ記録する

## 23. Status Policy

**IMPLEMENTED** — 次の場合:

```text
Implementation exists
Artifacts exist
Functional execution completed
Formal validation not yet completed
```

**VALIDATED** — 次をすべて満たす場合:

```text
KDA-2 Component acceptance criteria: PASS
Installed-only execution: PASS
Import provenance: PASS
Artifact determinism: PASS
Diagnostics: 0
KDA-2-related failures: 0
Completion Report updated
```

Repository-wide CIが失敗している場合、そのStatusは別途記録する。

**BLOCKED** — KDA-2に直接関連するValidation failureがある場合。

## 24. Current Status

本仕様作成時点:

```text
Implementation:            IMPLEMENTED
Artifact existence:        CONFIRMED
Artifact values:           VERIFIED
Functional execution:      PASS
Determinism:               PASS
KDA-1 regression:          PASS
Installed Distribution:    CONFIRMED (import provenance verified; see §18.2)
Repository-wide CI:        FAIL — CI-008
Formal KDA-2 Status:       IMPLEMENTED
```

### 24.1 更新: Component Validation実行後の状態

`reasonscript-kda2-component-validation/1.0`(`docs/specifications/ReasonScript_KDA2_Component_Validation_v1.0.md`)に定義された`scripts/validate_kda2_component.py`を実行した結果、KDA2-CV-001〜050の全50件がPASSし、KDA-2 Diagnosticsは0件であった。

```text
Formal Component Validation:  EXECUTED
Acceptance Criteria:          50 passed / 0 failed
KDA-2 Diagnostics:            0
Repository-wide CI:           FAIL — CI-008 (classified `unrelated`; does not block KDA-2 component status)
Formal KDA-2 Component Status: VALIDATED
```

Repository-wide CI(`CI-008`)は本仕様の§21.2で記録した通り引き続きFAILであり、これはRepository-wide release certificationとは別のStatusとして記録される。KDA-2 ComponentのStatusは、`reasonscript-kda2-component-validation/1.0`の全Acceptance Criteriaを満たしたことにより`IMPLEMENTED`から`VALIDATED`へ移行した。

## 25. Completion Report更新要件

既存Completion Reportは、最新ArtifactおよびInstalled Distribution状態と一致するよう更新する。特に、次の古い記述を再検証する。

```text
Installed Distribution is blocked because evaluate_classification is missing
```

現在のInstalled DistributionにAPIが存在するため、この記述は削除し履歴注記へ変更する。

Completion Reportには次を記載する。

```text
Dataset SHA-256
Rows
Feature count
Prediction count
Evidence count
Rule Set version
Rule count
Confusion Matrix
Metrics
AUC
Average Precision
Knowledge count
Visualization count
PNG/SVG count
Diagnostics count
Artifact digest result
Import provenance
Installed-only result
KDA-1 regression
KDA-2 Component status
Repository-wide CI status
Known limitations
```

## 26. Known Limitations

- Rule Setは人手設計である
- Scoreは校正済み確率ではない
- Dataset全体を評価しており、Train/Test分割ではない
- Cross-validationを行っていない
- NameとTicketをPrediction Featureとして使用しない
- Kaggle test.csv Submissionを生成しない
- Rule SetはTitanic domain専用である
- Cross-platform画像byte identityを保証しない
- Repository-wide CIは本仕様作成時点でPASSしていない

## 27. Validation Commands

**KDA-2 External Project**

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

print(runtime.__file__)
print(runtime.data.__file__)
print(runtime.visualization.__file__)
print(runtime.visualization.evaluation.__file__)
PY
```

**Core Canonical CI**

```bash
cd /Users/chigenori/development/ReasonScript
./reason ci --json
```

## 28. Changelog Entry

```text
## KDA-2 — Titanic Rule-based Classification v1.0

### Status

IMPLEMENTED

### Added

- Added the initial formal KDA-2 specification.
- Added direct 891-row Titanic rule-based classification.
- Added deterministic Feature Records, Predictions, Decision Paths, and Prediction Evidence.
- Added classification metrics, ROC/AUC, Precision–Recall/AP, Rule evaluation, and error analysis.
- Added 10 evidence-linked Knowledge records.
- Added 14 evaluation visualizations and 28 PNG/SVG files.
- Added deterministic Artifact Manifest and SHA-256 records.
- Added explicit separation between KDA-2 component validation and repository-wide CI status.

### Verified Results

- Dataset rows: 891
- Feature records: 891
- Predictions: 891
- Prediction Evidence: 891
- Accuracy: 0.7598204264870931
- Balanced accuracy: 0.777538107563992
- AUC: 0.8462755248777681
- Average precision: 0.7903496180334
- Knowledge: 10
- Visualizations: 14
- Diagnostics: 0
- Artifact determinism: PASS
- KDA-1 regression: PASS

### Validation Status

- KDA-2 implementation and artifacts: CONFIRMED
- Formal component validation: PENDING
- Repository-wide canonical CI: FAIL, CI-008
```

## 29. 完了時の正式宣言

全Component Acceptance Criteriaを満たした場合:

```text
ReasonScript KDA-2 Titanic Rule-based Classification v1.0

Specification ID: reasonscript-kda2-titanic-rule-classification/1.0

KDA-2 Component Status: VALIDATED

Dataset: 891 rows
Predictions: 891
Prediction Evidence: 891
Knowledge: 10
Visualizations: 14

Installed Distribution: VALIDATED
Artifact Determinism: VALIDATED
Repository-wide CI: RECORDED SEPARATELY
```

## 30. 最終定義

```text
KDA-2
=
Direct Titanic CSV Input
+ Deterministic Feature Records
+ Versioned Rule Set
+ Row-level Predictions
+ Prediction Score
+ Confidence
+ Decision Path
+ Prediction Evidence
+ Classification Evaluation
+ Rule and Error Analysis
+ Knowledge
+ ML Visualization
+ Deterministic Artifacts
+ Installed Distribution Reproducibility
```

本仕様は、KDA-2実装と実在するArtifactを正式なReasonScript検証契約へ移行する初版仕様である。
