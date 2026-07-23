# ReasonScript コアコンセプト

対象読者: `docs/` 配下の規範仕様書を読む前に、ReasonScript の動作モデルを一通り
把握しておきたいエンジニア。本書はプロフェッショナルなソフトウェアエンジニアリ
ングの前提知識(AST、コンパイラ、グラフ理論など)を持つ読者を対象とし、それら
一般概念の再説明は行わない。

具体的な構文とツールチェインについては `docs/guide/basic-usage.ja.md` を参照
すること。本書が説明するのは「言語がなぜこの形をしているか」である。

## 1. ReasonScript とは何か

ReasonScript は **証明可能な AI ワークフロー** を構築するための、推論を第一級
の概念とする言語である。ここで言う「証明可能」とは、決定(ディシジョン)、
プランのステップ、計算といった状態遷移を決定論的に生成し、後からワールドを
再実行することなく記録された証拠(エビデンス)のみから監査できる、という性質
を指す。

ReasonScript は汎用プログラミング言語ではなく、ナレッジベースでもなく、自然
言語による推論システムでもない。これは **推論を決定論的な状態遷移として表現
し実行するための言語** であり、すべての遷移はそれを生み出した入力と証拠まで
遡って追跡可能である。

本プロジェクトは、混同されがちだが役割が異なる 2 つの層として提供される。

| 層 | 答える問い | 凍結済み仕様 |
|---|---|---|
| **Language Surface(言語表層)** | `.rsn` プログラムをどう書き、どうコンパイルするか | `docs/ReasonScript_Language_Surface_Core_v0.1_RC.md` |
| **Semantic Language(意味言語)** | 型付き意味状態(セマンティックステート)上で推論するとはどういうことか | `docs/ReasonScript_Semantic_Language_Core_v0.2.md` |

Language Surface は `module`、`fn`、`calculation`、`transition` などの具体
構文であり、`docs/guide/basic-usage.ja.md` で解説する。Semantic Language は
その下にある抽象モデル ── SemanticUnit、SemanticRelation、Reasoning Space、
Knowledge ── であり、本書で解説する対象である。`.rsn` プログラムは両方の層を
通ってコンパイルされる。ソースコードは Surface AST になり、Surface AST は
SemanticUnit と SemanticRelation をインスタンス化する Semantic AST になり、
その Semantic AST が下記のパイプラインへと降下していく。

## 2. コア原則

以下の 4 原則は、Language Surface から Runtime に至るシステムのあらゆる層を
支配する。これらは単なるスタイルの好みではなく、プラットフォーム全体が検証
される基準となる性質である。

1. **Knowledge はプリミティブではない。Knowledge は生成されるものである。**
   Knowledge を直接主張(アサート)することはできない。Knowledge は必ず、
   Reasoning Space 上で検証されたシミュレーションから、それを生成した証拠と
   共に出力される。
2. **推論(Reasoning)は Knowledge に先行する。** 生データから Knowledge
   オブジェクトへの近道は存在しない。必ず先に SemanticPlan がシミュレート
   される必要がある。
3. **すべての Knowledge オブジェクトは完全な証拠を含む。** Knowledge は
   自己監査可能である ── それを生成したプラン、トレース、確信度(コン
   フィデンス)が、値と一緒に保存されるため、検証のために何かを再導出する
   必要がない。
4. **意味推論(Semantic Reasoning)は決定論的である。** 同一のグラフ、同一の
   プラン、同一の制約が与えられれば、ランタイムは常に構造的に等しい結果と、
   バイト単位で同一な正規化 JSON を生成する。

決定性は「証明可能」という言葉を意味あるものにする性質である。もし実行結果
が実行のたびに変わり得るなら、Knowledge オブジェクトに付随する証拠は将来の
実行について何も証明しないことになる。

## 3. 推論パイプライン

Semantic Language Core は、あらゆる推論操作が流れる 1 本の方向性パイプライン
を定義する。

```text
SemanticUnit
  -> SemanticRelation
  -> Reasoning Space
  -> SemanticPlan
  -> SemanticSimulation
  -> SimulationResult
  -> Knowledge
```

### SemanticUnit

推論における原子的・型付きの要素。凍結済みの型は `Concept`、`Object`、
`Event`、`Action`、`Attribute`、`Goal`、`Constraint` の 7 種類である。ランタ
イム上では SemanticUnit は `State` として表現される(`StateType` はランタイ
ムレベルの型タグ)。型なし・不明な SemanticUnit は存在せず、
`StateType::Unknown` は明示的に無効とされる。

### SemanticRelation

2 つの SemanticUnit 間の型付き有向接続: `IsA`、`PartOf`、`Cause`、
`Similar`、`Constraint`、`Temporal`、`Spatial`、`Dependency`。ランタイム上
では SemanticRelation は `Edge` として表現される。Relation は自由形式の文字
列ではない ── 凍結済みの集合のみが構造的に有効であり、両端点の互換性は
(後述の SCV-1 によって)検査される。

### Reasoning Space

```text
Reasoning Space = SemanticUnit群 + SemanticRelation群 + SemanticConstraint群 + SemanticTransition群
```

SemanticUnit と SemanticRelation が存在する、検証済みのプライベートグラフ
(`ReasonGraph`)。意図的に、ナレッジベースでもデータベースでも永続メモリ
ストアでも **ない** ── リポジトリのように問い合わせる対象ではなく、推論の
対象として存在する。読み取りは不変借用(immutable borrow)であり、所有権を
返す操作は Reasoning Space を消費(consume)する。そのため、進行中のシミュ
レーションの足元で Reasoning Space が誤って変更されることはあり得ない。

### SCV-1: 構造的制約検証(Structural Constraint Validation)

何かが Reasoning Space に入る前に、SCV-1 が Relation の互換性、ノード参照、
状態参照/型、グラフ構造、クロージャ生成 Relation を検証する。これは、無効な
意味トポロジー(例: 因果関係になり得ない 2 つの型間の `Cause` エッジ)が
パイプラインに入り込むことを完全に排除するゲートである ── 検証はシミュレー
ションの奥深くでのランタイムアサーションとしてではなく、構築時に行われる。

### SemanticPlan

「`start` から `goal` に向けて推論せよ」という外部リクエストであり、任意で
制約(回避するノード、最大距離)を伴う。SemanticPlan はリクエストオブジェク
トであり、Reasoning Space 自身の状態の一部ではない ── グラフに格納される
ことはない。

### SemanticSimulation

決定論的な評価器。凍結済みの操作は `simulate`、`simulate_goal`、
`simulate_goal_with_constraints`、`predict` である。保証事項: シミュレー
ション中も SCV-1 は強制され続ける、Reasoning Space は決して変更されない、
等しい入力は等しい出力を生成する、結果は完全にシリアライズ可能である。

### SimulationResult

検証済みの構造化された軌跡:

```text
SimulationResult
├─ source_plan
├─ success
├─ path
├─ distance
├─ cost        = すべてのエッジコストの合計
├─ confidence  = すべてのエッジ確信度の積
├─ trace       (各ステップの relation, transition, cost, confidence, 送信元/送信先の型)
└─ predicted_states
```

集計された `cost`/`confidence` は小数点以下 12 桁に正規化されるため、JSON
のラウンドトリップはバイト単位で再現可能である。

### Knowledge

```text
Knowledge = 検証済み構造化推論結果
          = relation + evidence + confidence
```

Knowledge が生の事実(raw fact)や生の Relation、データベースの行になること
は決してない ── 均質(homogeneous)でクロージャ互換な SimulationResult の
軌跡から導き出されるものである。KEV-1(Knowledge Emergence Validation)は
現時点でこれを `IsA`、`PartOf`、`Cause` のみから構成される軌跡に限定して
いる。すべての Knowledge オブジェクトは、元になった SemanticPlan、完全な
SimulationResult、完全なトレース、検証済みの確信度を保持する ── 可変なグラフ
状態や永続ストアに触れることなく監査可能である。

## 4. コンパイルパイプライン

上記の推論パイプラインとは直交する、もう 1 つのパイプラインが存在する。これ
は ReasonScript の **ソースコード** を、Runtime が実行可能な形へと降下させる
ものである。

```text
ソースコード
  -> Surface AST         (Language Surface パーサ)
  -> Semantic AST        (宣言解決、型検査済み)
  -> Reason IR           (バージョン管理・スキーマ検証済みの中間表現)
  -> ExecutionPlan       (不変、Runtime 実行可能)
  -> Runtime             (RuntimeReal / HybridRuntime)
  -> InferenceResult
```

Surface AST は `module`、`fn`、`calculation`、`transition`、式/パターン構文
が存在する層である(`docs/guide/basic-usage.ja.md` 参照)。`calculation` や
`transition` をコンパイルすると、その文(ステートメント)群は第 3 節の
Semantic Language 語彙へと投影(プロジェクション)される ── 例えば
`calculation` 内の `if`/`match` は `DecisionTransition` になり、`result`
文は計算の意味的 Goal に向かう `ResultTransition` になる。ここが「書かれた
構文」と「推論対象となる SemanticUnit/SemanticRelation グラフ」との継ぎ目
である。

Reason IR は安定的でバージョン管理されたスキーマ
(`schemas/reason_ir.schema.json`)であり、独立した Runtime、コンパイラ、
適合性(コンフォーマンス)ツールが実装コードを共有せずに意味論について合意
するためのワイヤ契約である。`Common_DTO_Specification_v0.1.md` は Rust、
Python、TypeScript、Go、Java 向けの対応するデータ転送オブジェクトを定義して
おり、ある実装が生成した Reason IR ドキュメントを別言語のツールが消費できる
ようになっている。

現時点でこの契約を実装しているランタイムは 2 つある: `RuntimeReal`
(Semantic Language v0.2 Core を支えるリファレンス実装の Rust ランタイム)と
`HybridRuntime`(曖昧性ハンドリング、プランニング、後続の推論機能で使われる
クロージャ/シミュレーション拡張を追加したもの)である。両者は同一の
ExecutionPlan に対して同一の InferenceResult を再現しなければならない ──
これがこのコードベースにおいて「Runtime」という用語が、単一の固定バイナリ
ではなく交換可能な用語として使われる理由である。

## 5. State、Goal、Transition、Rollback

Operational Semantics v0.1 は、コンパイル済みモジュールの実行意味論を定義
する。実行の構成(configuration)は以下の通りである。

```text
C = <M, IR, P, EP, S, D, T>
  M  ソース Module      IR  Reason IR              P  プランナーポリシー
  EP ExecutionPlan       S  コミット済み State       D  StateDelta の並び
  T  実行トレース
```

実行は単一の **commit** 関係によってのみ進行する:
`<EP, S_i, D, T> --commit(step_i)--> <EP, S_i+1, D+delta_i, T+event_i>`。
プランニングと検証はコミット済み State を決して変更しない ── 変更するのは
commit のみであり、すべての commit はアトミックであり、ちょうど 1 つの
`StateDelta`(`before_state` -> `after_state`)を生成する。

**Goal** は不変な終端達成条件であり、プランのステップでも状態変更でもない。
`reach_state` の充足は純粋に構造的である: `S.state_id == target`。すべての
実行はちょうど 1 つの Goal を持つ。初期 State が既に Goal を満たしている
場合、ゼロステップの実行も有効である。

**Transition** はプランナーが選択可能な状態変化の宣言である ── ソース上で
書く `transition { ... }` 構文のランタイム側の対応物であり、すべての
`calculation` の文が投影される先でもある(`StateUpdateTransition`、
`CallTransition`、`DecisionTransition`、`ResultTransition` など)。

**Rollback** はコミット済み State を、以前に記録された安全なチェックポイント
へと巻き戻す。オリジナルのコアプリミティブモデル(`docs/semantics.md`)では
`rollback` は第一級の文であり、リテラルマーカー `invalid` を含む `prove` の
失敗は自動的にこれを引き起こす ── これが本プラットフォームを
「rollback-safe」たらしめている性質である。失敗した証明がシステムを半端に
適用された状態のまま放置することはない。

## 6. ReasonScript が意図的に「ではない」もの

v0.2 Core の凍結宣言はスコープについて明示的であり、隣接システムとの類推で
つい仮定してしまいがちな境界であるからこそ、内面化しておく価値がある。

- ナレッジリポジトリ、永続化レイヤ、検索システムではない ──
  Knowledge はシミュレーションごとに生成されるものであり、後で保存して
  クエリするものではない。
- Knowledge の再推論は存在しない ── 同じパイプラインを通して Knowledge
  オブジェクトについて推論することはできない。SemanticPlan を再実行するの
  みである。
- Core レベルでは MemorySpace や WorldModel の意味論は存在しない
  (WorldModel は別の、より上位の SDK レイヤとして存在する ──
  `docs/World_SDK_Phase_1_Specification.md` を参照)。
- 自然言語解析は存在しない ── SemanticUnit はプログラム的に、または
  Language Surface を通じて構築されるものであり、文章から推論されることは
  ない。
- 外部実行は存在せず、現実世界の真理性も主張しない ── 検証済みの
  SimulationResult は内部的に一貫しており再現可能であるが、それが現実と
  一致するという主張ではない。
- SCV-2 から SCV-5(SCV-1 の構造的検査を超える、時間的・因果的・空間的・
  依存関係の制約検証)は将来の仕様のために予約されており、v0.2 Core では
  実装されていない。

## 7. エンジニアリング上の制約としての決定性

各層のテストスイートとリリースゲートは、すべて同じ保証 ── 同一の入力は
同一の出力を生成する ── を守るために存在する。具体的には以下として現れる。

- 固定小数正規化(シミュレーション指標は 12 桁)を伴う正規化 JSON シリアラ
  イズにより、`deserialize(serialize(x)) == x` が成立し、繰り返し実行した
  結果をバイト単位で比較できる。
- AST、IR、ExecutionPlan の値はすべて不変(immutable)である ── 構築後は
  すべてのノードが不変であり、コンテナは集合ではなく順序付きタプルである
  ため、ソースの記述順序が最初から最後まで保持される。
- State のスナップショット比較の基盤は同一性等価(identity equality)では
  なく構造的等価(structural equality)である ── そのため独立に計算された
  2 つのスナップショットが、同じ内容を持つ限り等しいと認識される。
- リリースゲート(`release/*/run_release_validation.py`)は、ソースから
  InferenceResult までの全経路を再実行し、いかなる逸脱に対してもビルドを
  失敗させる。

言語やランタイムを拡張する際に問うべきは「この機能は動くか」ではなく
「この機能は決定性と証拠を最初から最後まで保持するか」である ──
`docs/` に収録されているすべての採択済み仕様は、この基準で検証されている。

## 8. 次に読むべきもの

- 具体的な構文、ツールチェイン、`.rsn` プログラムの書き方・実行方法:
  `docs/guide/basic-usage.ja.md`。
- 正確な文法: `docs/grammar.md`(オリジナルの行ベースコア)と
  `docs/ReasonScript_Language_Surface_Core_v0.1_RC.md`(現行のブロック構造化
  された表層構文)。
- Semantic Language Core の完全な契約:
  `docs/ReasonScript_Semantic_Language_Core_v0.2.md`。
- 実行意味論: `docs/ReasonScript_Operational_Semantics_v0.1.md`。
- プラットフォーム全体の成熟度と Beta までに残る作業:
  `docs/platform_architecture_review/platform_architecture_v1.md`。
