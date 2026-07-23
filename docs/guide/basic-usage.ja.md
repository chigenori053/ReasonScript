# ReasonScript 基本的な使い方

対象読者: `docs/guide/concepts.ja.md` を読み終え、ReasonScript のソースコード
を実際に書き、コンパイルし、実行する必要があるエンジニア。本書は、この
リポジトリに含まれる Language Surface v0.1 の構文と、それに対する v1.0 の
増分拡張(関数、enum、struct、optional)、そして `reason` ツールチェインの
実践的なウォークスルーである。意図的にサンプル駆動の構成としている。各構文
の背後にある規範的な規則については、`docs/` への相互参照をたどること。

以下のコード例はすべて、このリポジトリに既に存在し検証済みのファイル
(`examples/`、`hello_world/`、`tests/`)から逐語的に採ったもの、または
その最小変形である。

## 1. ツールチェインとプロジェクト構成

ReasonScript のパッケージは、`reason.toml` マニフェストを持つディレクトリ
である。

```toml
[package]
name = "hello_world"
version = "0.1.7"

[compiler]
language_core = "0.7"
platform = "0.2"

[runtime]
backend = "RuntimeReal"
```

慣例的なレイアウト(`hello_world/`):

```text
hello_world/
├── reason.toml
├── src/
│   └── main.rsn
└── tests/
    └── sample_test.rsn
```

パッケージに属するすべての `.rsn` ファイルは、そのパッケージ名を宣言する
`package` 文で始まる。

```reasonscript
package hello_world
module main {
    fn run(goal) {
        return goal
    }
}
```

### CLI コマンド

`reason` CLI(リポジトリルートから `./reason <command>`、または
`python3 -m toolchain <command>`)は、`docs/guide/concepts.ja.md` 第 4 節で
説明したパイプラインを駆動する。

| コマンド | 効果 |
|---|---|
| `reason init <name>` | 新しいパッケージディレクトリを生成する |
| `reason build [--package <name>]` | ソースを解析し Reason IR / ExecutionPlan にコンパイルする |
| `reason check [--package <name>]` | ビルド成果物を生成せずにソースを検証する |
| `reason run [--package <name>]` | ビルド後、設定済みの Runtime に対して実行し InferenceResult を生成する |
| `reason test [--package <name>]` | パッケージのテストソースを実行する |

複数パッケージからなるワークスペースは、ワークスペースルートの
`reason.workspace.toml` で宣言する。`--package` でメンバーパッケージを 1 つ
選択でき、ワークスペース全体の依存順序はトポロジカルに解決される
(`docs/ReasonScript_Toolchain_Phase_2_Report.md` 参照)。

## 2. モジュールとインポート

`module` は名前空間の単位である。1 つのファイルは 1 つ以上の module を宣言
でき、`pub` はその module の公開シンボルが他所からインポート可能かどうかを
制御する。

```reasonscript
module finance {
}

pub module finance {
}
```

インポートは module 全体または単一のシンボルのいずれかを解決し、任意で
エイリアスを付けられる。

```reasonscript
import finance.loan
import finance.loan as loan
import finance.RiskScore
import finance as loan
import finance.RiskScore as risk
```

非修飾名の解決順序は次の通り(優先順)。

1. 現在の `calculation` 内のローカルバインディング
2. 現在の module 自身の名前空間
3. `import` によって取り込まれた公開シンボル

同じ非修飾名を公開する 2 つのインポートはコンパイルエラーとなり
(`NS-040`)、プライベートシンボルのインポート(`NS-050`)や存在しない名前の
参照(`NS-020`/`NS-030`)も同様である。曖昧さを解消したい場合や module を
横断して参照したい場合は、`::` で明示的に修飾する。

```reasonscript
finance::RiskScore
loan::RiskScore
```

参照: `docs/ReasonScript_Language_Surface_Namespace_Import_Resolution_v0.1.md`。

## 3. 宣言と Relation

Semantic Language Core(`docs/guide/concepts.ja.md` 第 3 節参照)の各
SemanticUnit 型には、対応する宣言キーワードが存在する: `Concept`、
`Object`、`Event`、`Action`、`Attribute`、`Goal`、`Constraint`。これらは
`module` 本体内で宣言し、名前を付ける。

Relation は **同一 module 内** で解決される 2 つの宣言を接続する:
`IsA`、`PartOf`、`Cause`、`Dependency`、`Constraint`、`Temporal`、
`Spatial`、`Similar`。

参照: `docs/ReasonScript_Language_Surface_Core_v0.1_RC.md` 第 3 節。

## 4. Transition

`transition` ブロックは、プランナーが選択し得る状態変化を宣言する。ある
宣言から別の宣言への遷移をマッピングし、任意で `require` によりガードを
かけ、`Goal` への注釈または到達先の指定を行う。

```reasonscript
transition Approve {
    Draft -> Approved
    require Adult
    goal LoanApproval
    reach LoanApproval
}
```

`transition` 本体内で許可される文: `Require`、`Goal`、`Reach`、`If`、
`Match`、および式(呼び出し)文。`require` は `Constraint` に解決され、
`goal` と `reach` は `Goal` に解決される。本体内の最後のトップレベル
`reach` が、意味的な Transition のターゲットを決定する ── これはあくまで
コンパイル時のマッピングであり、Goal の「充足」自体は実行時に Operational
Semantics(`docs/guide/concepts.ja.md` 第 5 節)によって決定される。

## 5. Calculation

`calculation` は `transition` の実行可能・式指向な対応物である ── 不変な
ローカルバインディングを持ち、必ずちょうど 1 つの `result` で終端する、名前
付きの文の集合である。

```reasonscript
calculation RiskScore {
    result = income * factor
}

pub calculation RiskScore goal: RiskEvaluation {
    let score = income * factor
    result = score
}
```

`pub` はその calculation をインポート可能にする。任意の `goal: <Goal>`
注釈は、それを宣言済みの `Goal` に結び付ける。本体内の各文は、それぞれ 1 つ
の順序付き意味的 Transition にコンパイルされる。

| 文 | 意味的投影(プロジェクション) |
|---|---|
| `let` | 式固有の Transition(状態変数ステップ) |
| 代入(`x = ...`) | `StateUpdateTransition` |
| 裸の式(呼び出しである必要がある) | `CallTransition` |
| `if` / `match` | `DecisionTransition` |
| `result = ...` | `ResultTransition`(calculation の意味的 Goal へ) |

参照: `docs/ReasonScript_Language_Surface_Calculation_Integration_v0.1.md`、
`docs/ReasonScript_Language_Surface_Statement_v0.1.md`。

## 6. 文(Statement)

完全な文の階層と、それぞれがどこで有効かを示す。

```text
StatementNode
├─ LetStatementNode          let score = 100
├─ AssignmentStatementNode   score = score + 1     (Calculation 本体のみ)
├─ ResultStatementNode       result = score         (Calculation 本体、ちょうど1回、最終文)
├─ RequireStatementNode      require Adult          (Transition 本体)
├─ GoalStatementNode         goal LoanApproval       (Transition 本体)
├─ ReachStatementNode        reach LoanApproval      (Transition 本体)
├─ ExpressionStatementNode   publish(order)          (ルートは呼び出しである必要がある)
├─ IfStatementNode           if / elif / else
└─ MatchStatementNode        match { pattern => ... }
```

配置規則:

| コンテナ | 許可される文 |
|---|---|
| Module 本体 | 宣言、インポート、Relation、`transition`、`calculation` |
| Transition 本体 | Require、Goal、Reach、If、Match、式文 |
| Calculation 本体 | Let、代入、If、Match、式文、Result |

`if` / `elif` / `else`:

```reasonscript
if score > 80 {
    reach Approved
} elif score > 50 {
    reach Review
} else {
    reach Rejected
}
```

`result` は `calculation` 本体の最後のトップレベル文でなければならず、
ちょうど 1 回だけ現れなければならない。ネストした `if`/`match` の分岐内や
`transition` 本体内では決して有効にならない。文の順序は最初から最後まで
(パース、シリアライズ、意味的投影を通して)保持される。これは生成される
Transition の並びを決定するためである。

参照: `docs/ReasonScript_Language_Surface_Statement_v0.1.md`。

## 7. 型

Language Surface v0.1 における型注釈は検証専用である ── ランタイムの
オブジェクトレイアウトを定義するものではなく、ジェネリクス・トレイト・
継承の仕組みも存在しない。

```reasonscript
let age: Int = 20
let score: Float = 0.8

calculation RiskScore -> Float {
    result = score
}
```

プリミティブ型: `Int`、`Float`、`Bool`、`String`、`Null`。State 型注釈は
SemanticUnit の種類のいずれかを名指しし、参照先の宣言がその種類であること
を要求する。

```reasonscript
let target: Goal = LoanApproval
let rule: Constraint = Adult
```

覚えておくべき互換性規則: 算術演算は **同一** の数値型のオペランド 2 つを
要求する(`Int + Float` は無効 ── 混合算術が必要な場合は呼び出し側で明示
的にキャストすること)。比較演算は既知の等しい型を要求し、論理演算子は
`Bool` オペランドを要求する。

参照: `docs/ReasonScript_Language_Surface_Type_Specification_v0.1.md`。

## 8. 式(Expression)

リテラル: 整数(`42`)、浮動小数点数(`3.14`)、真偽値(`true`/`false`)、
文字列(`"hello"`)、`null`。負の数は単項否定としてパースされる
(`-score` は `Negate(score)` であり、負のリテラルトークンではない)。

演算子(優先度が高い順):

| レベル | 構文 |
|---:|---|
| 80 | メンバーアクセス(`a.b`)、呼び出し(`f(x)`) |
| 70 | 単項 `-`、単項 `!` |
| 60 | `*` `/` `%` |
| 50 | `+` `-` |
| 40 | `==` `!=` `>` `>=` `<` `<=` |
| 30 | `&&` |
| 20 | `\|\|` |

すべての二項演算子は左結合であり、括弧は単に解析時に取り除かれるのではなく
シリアライズを通して保持される。

```reasonscript
1 + 2 * 3        // Binary(Add, 1, Binary(Multiply, 2, 3))
(a + b)          // Parenthesized(Binary(Add, a, b))
user.profile.age // ネストした MemberAccess
risk(score, age) // Call(risk, [score, age])
```

参照: `docs/ReasonScript_Language_Surface_Expression_Pattern_v0.1.md`。

## 9. 関数(Function)

`fn` は通常の module レベル関数を宣言する。パラメータと戻り値の型は必須で
あり(`FN-002`、`FN-003`)、v1.0 では直接再帰は拒否される(`FN-007`)。

```reasonscript
module Basic {
    fn Value() -> int {
        return 42
    }

    calculation Result {
        result = Value()
    }
}
```

構造化関数制御フロー拡張(FSI-2)により、関数本体は単一の終端 `return` に
限定されなくなった ── **到達可能なすべてのパス** が `return` で終わる限り、
分岐を含んでよい。

```reasonscript
fn Score(color: Color, shape: Shape) -> int {
    match color {
        Color.Red => {
            match shape {
                Shape.Circle => return 10
                Shape.Square => return 20
            }
        }
        Color.Blue => return 0
    }
}
```

参照: `docs/specs/function_semantic_integration_v1.md`、
`docs/specs/function_control_flow_v1.md`。

## 10. Match、パターン、構造化データ

`match` は `transition`、`calculation`、`fn` の本体内で有効である。v0.1 で
サポートされるパターンは、識別子、`_`(ワイルドカード)、リテラルである。

```reasonscript
match state {
    Draft => approve()
    Approved => publish()
    _ => reject()
}
```

v1.0 の拡張は、`tests/` 全体で使われている以下のパターン形式を追加する。

**Enum** ── バリアントを宣言し、修飾形式(`型.バリアント`)でマッチする。

```reasonscript
module Basic {
    enum Color {
        Red
        Blue
    }

    fn Get() -> Color {
        return Red
    }
}
```

**Struct** ── フィールドを宣言し、リテラルフィールド、束縛フィールド、
ネストした struct フィールドでマッチする。

```reasonscript
module Test {
    struct Position { x: int, y: int }
    struct Person { position: Position }

    fn Score(person: Person) -> int {
        match person {
            Person { position: Position { } } => return 1
        }
    }

    calculation Result {
        result = Score(Person { position: Position { x: 1, y: 2 } })
    }
}
```

**Optional** ── `optional<T>` を、`some(x)` / `none` でマッチする。

```reasonscript
fn Score(value: optional<int>) -> int {
    match value {
        some(x) => return x
        none => return 0
    }
}
```

**Or パターンと `default`** ── 複数の候補を組み合わせるか、フォールスルー
する。

```reasonscript
fn Score(value: int) -> int {
    match value {
        1 | 2 | 3 => return 10
        default => return 0
    }
}
```

**ガード** ── `when` を使い、束縛フィールドのマッチを真偽条件で絞り込む。

```reasonscript
match point {
    Point { x } when x > 0 => return 1
    Point { } => return 0
}
```

参照: `docs/specs/enum_symbol_resolution_v1.md`、
`docs/specs/struct_pattern_matching_v1.md`、
`docs/specs/optional_pattern_matching_v1.md`、
`docs/specs/or_pattern_v1.md`、`docs/specs/pattern_guard_v1.md`。

## 11. 完全な作例

関数と、それを呼び出す calculation を組み合わせた例
(`examples/function_call_from_calculation.rsn` より):

```reasonscript
module Basic {

    fn Value() -> int {
        return 42
    }

    calculation Result {
        result = Value()
    }

}
```

実行方法:

```sh
reason check    # パースと検証のみ
reason build    # Reason IR / ExecutionPlan へコンパイル
reason run      # 設定済み Runtime バックエンドに対して実行し、InferenceResult を出力
```

## 12. オリジナルのコアプリミティブ

ブロック構造化された Language Surface が導入される以前、ReasonScript は
6 つのプリミティブからなる最小限の行ベースコア(現在も有効でパース可能 ──
`docs/grammar.md`)を定義していた。これは言語の証明/ロールバックモデルを
単独で理解するのに有用である。

```reasonscript
goal preserve_session_consistency
derive identify_transition_gap
prove deterministic_state_transition
apply patch_session_machine
converge verify_repl_stability
rollback previous_safe_state
```

| プリミティブ | ペイロード型 | 意味 |
|---|---|---|
| `goal` | Symbol | 望ましい状態を宣言する |
| `derive` | Symbol | 候補となる推論戦略を生成する |
| `prove` | Proof | 導出を検証する。テキストに `invalid` を含む `Proof` は決定論的な失敗であり、自動的に `rollback` を引き起こす |
| `apply` | State | 検証済みの変更をコミットする |
| `converge` | Symbol | 指定ラベルに収束・安定化する |
| `rollback` | State | 指定された安全なチェックポイントに巻き戻す |

`apply` のペイロードは、有理数(`1/2`)、符号付き整数(`-3`)、自然数
(`42`)、シンボル(`x`)の順で分類される。各文は 1 行であり、未知の
キーワードは現行パーサによって無視される。ブロック、コメント、文字列は
このコア形式のスコープ外である。

参照: `docs/semantics.md`、`docs/grammar.md`。

## 13. 検証とコンフォーマンス

新しい構文に依存する前に、レイヤ固有の回帰テストスイート(各仕様書に個別の
コマンドが記載されている)、またはフルスイートを実行すること。

```sh
python3 -m pytest --import-mode=importlib
```

リリースゲートによる保証(Language Surface v0.1、Semantic Language v0.2、
Platform v0.1 Alpha)については、`release/` 配下の対応するゲートを実行する。

```sh
python3 release/language-surface-v0.1/run_release_validation.py
python3 release/semantic-language-v0.2/run_release_validation.py
python3 release/v0.1-alpha/run_release_validation.py
```

## 14. 次に読むべきもの

- 概念モデル(Reasoning Space、Knowledge、決定性の保証):
  `docs/guide/concepts.ja.md`。
- 完全な文法: `docs/grammar.md`、
  `docs/ReasonScript_Language_Surface_Core_v0.1_RC.md`。
- 文・式・型の契約: `docs/ReasonScript_Language_Surface_*` 配下の
  LS-1/1.2/1.3 各文書。
- v1.0 の増分機能(関数、enum、struct、optional、ガード、タイムゾーン対応
  タイムスタンプ): `docs/specs/`。
- 実行意味論と Runtime 契約: `docs/ReasonScript_Operational_Semantics_v0.1.md`。
