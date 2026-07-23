# HybridRuntime Research Phase A
## Decision Logic Report

**実行日:** 2026-06-11  
**対象:** Phase B / Phase C  
**実行コマンド:** `cd Test && cargo test --test hybrid_runtime_phase_a -- --nocapture`  
**結果:** PASS (3 passed, 0 failed)

## 1. 結論

DL-01からDL-03では、帯域ルールと期待コストモデルが同じ戦略を選択した。

- DL-01: `Real`
- DL-02: `Clarify`
- DL-03: `Complex`

DL-04では選択が分岐した。

- 帯域ルール: `Complex`
- 期待コストモデル: `Clarify`

したがって意思決定は、曖昧度の閾値だけでは一意に決まらない。
誤決定損失、追加質問コスト、Complex実行コストを含む目的関数が必要である。

## 2. 比較した意思決定仮説

### Model 1: Ambiguity Band

研究用の帯域ルールとして次を使用した。

```text
Real:
  P1 >= 0.85 and Margin >= 0.50

Complex:
  Hn >= 0.85
  or Margin <= 0.10
  or Conflict >= 0.60

Clarify:
  otherwise
```

閾値は正式仕様ではなく、低・中・高領域を観測するための仮置きである。

### Model 2: Expected Cost

三戦略の期待コストを比較した。

```text
Real    = 4.00 * error_probability + 1.50 * conflict
Clarify = 0.45 + 1.20 * error_probability + 0.40 * conflict
Complex = 0.90 + 0.35 * error_probability + 0.15 * conflict
```

定数は戦略選択原理の差を観測するための研究値であり、運用コストの実測値ではない。

## 3. 実験結果

| ID | P1 | Margin | Hn | Conflict | Band | Expected Cost |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| DL-01 | 0.950 | 0.920 | 0.211 | 0.000 | Real | Real |
| DL-02 | 0.600 | 0.250 | 0.750 | 0.000 | Clarify | Clarify |
| DL-03 | 0.450 | 0.050 | 0.920 | 0.000 | Complex | Complex |
| DL-04 | 0.718 | 0.527 | 0.703 | 0.662 | Complex | Clarify |

## 4. ケース別評価

### DL-01 Low Ambiguity

候補分布は `Dog=0.95, Wolf=0.03, Fox=0.02`。

- 高い最上位確率
- 大きいmargin
- 低い正規化entropy
- 期待コスト: Real `0.200`、Clarify `0.510`、Complex `0.918`

両モデルで `Real` が選択された。即時確定条件として安定している。

### DL-02 Medium Ambiguity

候補分布は `Dog=0.60, Wolf=0.35, Fox=0.05`。

- 上位二候補が競合
- ただしDL-03ほど均衡していない
- 期待コスト: Clarify `0.930`、Complex `1.040`、Real `1.600`

両モデルで `Clarify` が選択された。中間領域には、
即時確定とComplex実行の間に追加証拠取得戦略が必要である。

### DL-03 High Ambiguity

候補分布は `Dog=0.45, Wolf=0.40, Fox=0.15`。

- margin `0.05`
- 正規化entropy `0.920`
- 期待コスト: Complex `1.093`、Clarify `1.110`、Real `2.200`

両モデルで `Complex` が選択された。ただし期待コスト差は `0.0175` と小さく、
コスト仮定の微小変化でClarifyへ反転し得る境界ケースでもある。

### DL-04 Conflict Resolution

入力 `Pet, Wild, Canine` から得た分布は
`Dog=0.718, Wolf=0.191, Fox=0.091`。

- 最上位候補は存在する
- marginは `0.527` と比較的大きい
- しかしConflictは `0.662`

帯域ルールは高Conflictを理由に `Complex` を選択した。
期待コストモデルは Clarify `1.053`、Complex `1.098` のため `Clarify` を選択した。

この分岐は、意思決定原理を仕様化しない限り「正しい戦略」は決まらないことを示す。

## 5. Decision Explainability

各判断は次の形式でtrace可能である。

```text
Test:
DL-04

Observed:
top_probability = 0.718
top_margin = 0.527
normalized_entropy = 0.703
evidence_conflict = 0.662

Band Strategy:
Complex

Band Reason:
evidence_conflict >= 0.60

Expected Cost Strategy:
Clarify

Expected Costs:
Real = 2.121
Clarify = 1.053
Complex = 1.098

Decision Status:
model-dependent
```

監査可能性のため、最終戦略名だけでなく次を保存する必要がある。

1. 入力候補分布
2. 使用した曖昧度成分
3. 適用したルールまたは目的関数
4. 各戦略の評価値
5. 選択理由
6. 次点戦略との差
7. 使用したモデル・閾値・コスト設定のversion

## 6. 意思決定原理の評価

| 原理 | 評価 | 観測 |
| --- | --- | --- |
| 単一閾値 | 不十分 | DL-04の矛盾とDL-02/03境界を表現しにくい |
| 複数閾値・帯域 | 有効だが硬い | 説明しやすいが境界で不連続 |
| 確率分布 | 必須入力 | P1だけでなくentropyとmarginが必要 |
| 期待値 | 有望 | 戦略コストを比較できる |
| コスト最小化 | 有望だが未較正 | DL-03/04でコスト設定に敏感 |

現段階では、確率分布を観測基盤とし、帯域ルールを安全制約、
期待コストを選択原理として組み合わせる構成が最も検証価値が高い。

## 7. DecisionEngine v1への要件候補

```text
DecisionInput:
  ambiguity_observation
  available_strategies
  strategy_cost_profile
  risk_policy

DecisionOutput:
  selected_strategy
  alternative_strategies
  score_or_cost_per_strategy
  decision_reason
  confidence
  policy_version
  evaluator_version
```

候補となる二段階判定:

1. 安全制約で `Real` を許可できるか判定する。
2. 残りの戦略を期待コストまたは期待効用で比較する。

これにより、低曖昧時の高速確定と、高矛盾時の保守的処理を分離できる。

## 8. 次フェーズで必要な検証

- 閾値近傍を細かく走査する境界テスト
- 誤決定損失を変えた感度分析
- Clarifyで得られる情報価値の測定
- ComplexStrategyの実時間・計算資源コスト測定
- 候補生成失敗と未知候補を含むopen-set評価
- 同じ曖昧度でConflictだけが異なる対照実験
- traceのJSON schemaとversioning検証

## 9. 制約

- Expected Costの係数は実測値ではない。
- `Clarify` は研究上追加した中間戦略であり、正式名称ではない。
- ComplexRuntimeは現時点で最小構造のみのため、実処理コストは測定していない。
- 戦略実行後の正答率・回復率・遅延は未測定。

本レポートはDecisionEngineの選択原理を絞り込むための結果であり、
正式な閾値またはコスト係数を確定するものではない。
