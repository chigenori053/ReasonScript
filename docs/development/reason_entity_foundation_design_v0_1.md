# ReasonScript Reason Entity Foundation / Surface Model 実装設計案 v0.1

- Document ID: RS-RE-DESIGN-001
- Version: 0.1
- Status: DRAFT（実装前設計）
- 対応仕様: RS-RE-FSM-001 v0.1 (ReasonScript Reason Entity Foundation and Surface Model)
- 調査対象ベースライン: 本ワークツリー `claude/reasonscript-entity-foundation-d37396`（`VERSION` = 0.5.4.6, HEAD = `181ba17`）
- Date: 2026-08-20
- Language: Japanese

---

## 0. 本書の位置づけ

RS-RE-FSM-001 は「何を満たすか」を定義する仕様書である。本書は、その仕様を
**現在のコードベースに対して具体的にどう実装するか**を定義する設計案であり、
以下を含む。

1. 現行実装の実測調査結果（仕様の前提が実際に成立しているかの検証）
2. 仕様と現状の差分、および前提の訂正
3. Reason Entity のデータモデル・Canonical ID・IR 表現の具体設計
4. Phase F0〜E2 の作業分解、変更対象ファイル、受け入れ条件
5. 診断・決定論・性能・互換性の実装方針
6. 本設計で新たに確定した設計判断（ADR-101〜）
7. 未決事項

本書は実装を伴わない。実装は本書の承認後、Phase 単位で着手する。

---

## 1. 現行実装の調査結果（実測）

### 1.1 コンパイルパイプライン構成

仕様が前提とする「Surface AST → Semantic AST → Reason IR → ExecutionPlan」は実在する。
実体は次のとおり。

| 段階 | 実装 | 備考 |
|---|---|---|
| Lexer | [frontend/language_surface/lexer.py](frontend/language_surface/lexer.py) | 位置付きトークナイザ。`tokenize()` は `parse()` 冒頭の検証にのみ使われる |
| Parser | [frontend/language_surface/parser.py](frontend/language_surface/parser.py) | **行ベース**。トークン列ではなく論理行の正規表現で解析する |
| Surface AST | [frontend/language_surface/nodes.py](frontend/language_surface/nodes.py) | 100 以上の frozen dataclass |
| 名前解決 | [frontend/language_surface/namespace.py:116](frontend/language_surface/namespace.py:116) `resolve_program` | |
| 検証／型検査 | [frontend/language_surface/validation.py](frontend/language_surface/validation.py) (3346行) | `_expression_type` が事実上の型検査器 |
| Semantic AST 射影 | [frontend/language_surface/integration.py:124](frontend/language_surface/integration.py:124) `project_module` | |
| Semantic AST | [frontend/ast/nodes.py](frontend/ast/nodes.py) | **Goal / State / Transition / Constraint / Context / Metadata の 6 種のみ** |
| Reason IR 生成 | [frontend/compiler/lowering.py:19](frontend/compiler/lowering.py:19) `lower` | JSON dict を生成 |
| Reason IR スキーマ | [schemas/reason_ir.schema.json](schemas/reason_ir.schema.json) | ルートは `additionalProperties: false`、`metadata` のみ開放 |
| ExecutionPlan | [frontend/language_surface/integration.py:2678](frontend/language_surface/integration.py:2678) `execution_plan_for` | |
| Runtime | [frontend/integrated_computation_runtime.py](frontend/integrated_computation_runtime.py) | AST 直接解釈のツリーウォーク型インタプリタ |
| 共通入口 | [toolchain/pipeline.py](toolchain/pipeline.py) `compile_source` / `validate_source` | `reason check` / `run` / `build` / `test` が共有 |

**設計上の最重要事実**: Semantic AST の宣言型は 6 種で固定されており、
Reason IR も同様に閉じたスキーマを持つ。仕様 §8.2 / §8.3 が要求する
Entity 関連ノード・命令は、この 2 層の**どちらかを拡張しなければ表現できない**。

### 1.2 実測で確認した基盤欠陥

以下はすべて本ワークツリーで実際に再現させた結果である。

| ID | 症状 | 再現入力 | 実際の出力 | 根本原因 |
|---|---|---|---|---|
| D-1 | 型注釈なし引数が Unknown のまま条件式へ到達 | `fn f(flag) { if flag { return 1 } return 0 }` | `CV-1 FCF-004 condition must be Bool` | [validation.py:839](frontend/language_surface/validation.py:839) `_function_parameter_type` が注釈なしで `None` を返し、[validation.py:1752](frontend/language_surface/validation.py:1752) `_expression_type` が `_UNKNOWN_TYPE` を返す。宣言位置ではなく**使用位置**で間接的に失敗する |
| D-2 | 戻り値型注釈なし関数の呼出結果が Unknown | `fn f(x: int) { return x > 1 }` → `let y = f(2)` → `if y` | `CV-1 ConditionMustBeBoolean` | [validation.py:2043](frontend/language_surface/validation.py:2043) `return function.return_type or _UNKNOWN_TYPE`。本体からの戻り値型推論を行っていない |
| D-3 | `tensor.to_array` の結果に添字アクセスできない | `let v = tensor.to_array(t)` → `v[0]` | `CV5-7 index access requires collection type` | [validation.py:2009](frontend/language_surface/validation.py:2009) の Tensor 戻り値表で `to_array` が未処理のため `NamedTypeNode("Tensor")` にフォールバックする。**一方 Tensor 契約レジストリ [tensor/runtime.py:2347](frontend/tensor/runtime.py:2347) は `to_array` の出力を `"Array"` と宣言済み**（型検査器がレジストリを参照していない） |
| D-4 | Int→Float の明示変換が存在しない | `float(count)` | 静的検査は**通過**し、実行時に `IntegratedRuntimeError: unknown runtime function: float` | 未知関数呼出が [validation.py:2044](frontend/language_surface/validation.py:2044) で `_UNKNOWN_TYPE` に落ちるため静的にも捕捉されない（二重欠陥） |
| D-5 | `/` の静的型と実行時型が不一致 | `let a = 7`, `let b = 2`, `a / b` | 静的型 `Int` / 実行時 `3.5` (float) | [validation.py:1877](frontend/language_surface/validation.py:1877) BinaryExpression が `left` をそのまま返す。実行時は Python の `/`（真の除算） |
| D-6 | 演算子継続による複数行式が不可 | 行末 `&&` での継続 | `D-001 binary operator is missing operand` | [parser.py:441](frontend/language_surface/parser.py:441) `_collect_simple_statement` は**括弧バランスのみ**で継続判定する |
| D-7 | モジュールレベル宣言が実行時環境に存在しない | `module M { const rate = 0.01  calculation C { let x = rate * 2.0 ... } }` | 静的検査は通過、実行時に `unknown runtime name: rate` | [integrated_computation_runtime.py:142](frontend/integrated_computation_runtime.py:142) `env = dict(calculations)` としており、モジュール本体の宣言を環境へ入れていない |

**D-7 は仕様 Appendix A に直撃する。** Appendix A は `ru:` をモジュール本体に宣言し、
`calculation Train` の内部から参照する。現行実装ではモジュールレベル束縛は
実行時に存在しないため、Surface 構文を追加しただけでは Appendix A は動作しない。

なお、仕様 §5.5 の例（丸括弧で囲む複数行式）は**現状すでに成立する**:

```
let comfort = (
  temperature > 18.0 &&
  temperature < 26.0
)
```

これは `_collect_simple_statement` の括弧バランス継続が働くためである。
必要な追加は D-6（演算子継続）と、後述する RUS/RUO ブロック本体の複数行解析のみ。

### 1.3 再利用できる既存資産

新規実装ではなく**既存資産への接続**で満たせる要件が多い。

| 仕様要求 | 既存資産 |
|---|---|
| Reason Entity の論理モデル（Identity / State / Relation / Evidence / Provenance / Lifecycle / Revision / Ownership / Projection） | [toolchain/reasonunit_object/model.py](toolchain/reasonunit_object/model.py) の RUO-U1 論理参照モデル。`CORE_PREFIXES`（`ruo:unit:` / `ruo:object:` / `ruo:state:` / `ruo:relation:` / `ruo:evidence:` / `ruo:revision:` / `ruo:projection:` …）、`LIFECYCLE`、`STATE_CLASSES`、`RELATION_CLASSES`、`canonicalize()` / `canonical_digest()` が既に存在する |
| Baseline Freeze（Phase F0） | [toolchain/reasonunit_baseline/baseline.py](toolchain/reasonunit_baseline/baseline.py)（RUO-C0）が identity / state / relation / ownership / evidence / lifecycle / execution / tensor の各 baseline artifact 生成と 3 回生成検証の実装先例を持つ |
| 決定論的正規化 | `canonicalize()`（NFC 正規化 + キーソート + レジストリ安定ソート + 非有限値拒否）、[toolchain/artifacts.py:13](toolchain/artifacts.py:13) `DETERMINISTIC_GENERATED_AT` |
| 診断 | [toolchain/diagnostics.py](toolchain/diagnostics.py) `reasonscript-diagnostics/1.0`。`DIAGNOSTIC_CODE_PATTERN` は `RE-DECL-001` 形式を既に受理する |
| Golden | [toolchain/golden.py](toolchain/golden.py) + [golden/](golden/) コーパス |
| 成果物 | [toolchain/artifacts.py:15](toolchain/artifacts.py:15) `CANONICAL_ARTIFACTS`（`language_surface_ast.json` / `semantic_ast.json` / `reason_ir.json` / `execution_plan.json` を含む） |
| Tensor 形状推論 | [frontend/tensor/integration.py:167](frontend/tensor/integration.py:167) `infer_tensor_shape`（部分的） |

### 1.4 実装上の制約（実測）

| # | 制約 | 影響 |
|---|---|---|
| C-1 | `reason_ir.schema.json` ルートは `additionalProperties: false`。`metadata` のみ `additionalProperties: true` | Entity IR は `metadata` 配下に置くか、スキーマを版上げするかの二択 |
| C-2 | `execution_plan.schema.json` は `additionalProperties: false` かつ必須 5 プロパティのみ。**しかし `execution_plan_for` は `reason_object_plan` / `vision_plan` を追加している**。実測で `vision_plan` 付き ExecutionPlan はスキーマ検証に失敗する（`$: unknown field vision_plan`）。RUO/Vision バインディングを含まないテストのみが通っているため潜在化している | ExecutionPlan への Entity 情報付加は、この既存の不整合ごと解消する必要がある |
| C-3 | Parser は論理行ベース。`_logical_lines` が行を strip して連結し、`_parse_simple` が正規表現でディスパッチする | 新構文は「行頭プレフィックス + 正規表現」で追加でき、トークンパーサへの全面移行は不要。ただし RUS/RUO ブロックは `_parse_body` 相当の明示的ブロック解析が必要 |
| C-4 | Lexer の複数文字演算子表は `-> => :: >= <= == != && \|\|` のみ。`<-` は未定義（`<` と `-` に分解される） | `tokenize()` は通過するが、`<-` を語彙的に一級化するなら追加が必要 |
| C-5 | `TensorRuntime.collect(env)` が**文単位**で呼ばれる（[integrated_computation_runtime.py:278](frontend/integrated_computation_runtime.py:278)）。`collect` は環境全体をグラフ走査する（[tensor/runtime.py:435](frontend/tensor/runtime.py:435)） | RU Slot は `collect` の可達性走査から見えなければ Tensor が誤解放される。かつ、ここは既知の性能ホットスポット |
| C-6 | `max_live_tensors = 1_000`（[tensor/runtime.py:82](frontend/tensor/runtime.py:82)） | 仕様 §1 の「Tensor 生存数」制約の実体 |
| C-7 | `toolchain/diagnostics.py` の `CATEGORIES` は閉じたタプルで、`diagnostics_summary.json` は全カテゴリのゼロ初期化辞書を出力する（[diagnostics.py:277](toolchain/diagnostics.py:277)） | 新カテゴリ追加は正規成果物のバイト差分を生む＝Golden 更新が必要 |
| C-8 | Surface AST スキーマ [frontend/schemas/language_surface_ast.schema.json](frontend/schemas/language_surface_ast.schema.json) は 100 個の `$defs` を持つ | 新 Surface ノードはここにも登録が必要 |

### 1.5 ベースラインの健全性

```
python3 -m pytest -q
2005 passed, 6 skipped, 100 subtests passed in 102.22s
```

Phase F0 の凍結対象として健全な状態にある。

---

## 2. 仕様との差分・前提の訂正

仕様どおりに進める前に、次の 3 点を確認・合意する必要がある。

### 2.1 ベースライン版の不一致

仕様は Target baseline を **v0.5.4.9** とするが、本リポジトリの `VERSION` は
**0.5.4.6** であり、`CHANGELOG.md` の最新項目も v0.5.4.5 である。v0.5.4.7〜
v0.5.4.9 に相当するコミットは本ワークツリーに存在しない。

**本設計の前提**: Phase F0 の Baseline Freeze は **v0.5.4.6（HEAD `181ba17`）**
に対して行う。仕様上の「v0.5.4.9」は、本ラインでは「Reason Entity 導入直前の
凍結済みベースライン」と読み替える。v0.5.4.7〜9 が別ラインに存在する場合、
F0 着手前にマージ順序の確定が必要（→ §10 未決事項 Q1）。

### 2.2 RS-DT-JP-GREET-001 が本リポジトリに存在しない

仕様 §1 / §13 Phase E2 / §18 が参照する Transformer 検証モデル
`RS-DT-JP-GREET-001` は、本リポジトリ内に文書・ソース・fixture のいずれも
存在しない（全文検索でヒット 0）。

**本設計の前提**: Phase E2 の受け入れ条件は、当該モデル一式（`.rsn` ソース、
固定 seed 構成、期待 loss curve、`.rstensor` チェックポイント）が
Phase F0 時点でリポジトリへ取り込まれていることを前提とする。
取り込まれない場合、E2 は「代替の Tensor 主体回帰モデル」で実施し、
仕様 §18 の該当条件は未達として明示報告する（→ §10 未決事項 Q2）。

なお、[examples/v0_5/tensor_training_foundation.rsn](examples/v0_5/tensor_training_foundation.rsn)
は単一ステップの学習例であり、`while` ループ・状態遷移・Relation Channel を
含まないため、E2 の代替としては不足する。

### 2.3 仕様 §5.5 の要求範囲

§5.5 は「括弧、配列、Object ブロックまたは継続可能な演算子文脈内では
複数行式を許可しなければならない」とする。実測では前 3 者は既に成立し、
**演算子継続のみ未実装**（D-6）である。Phase F2 の作業量は仕様から
受ける印象より小さい。

---

## 3. アーキテクチャ設計

### 3.1 モジュール配置

新規コードは既存レイヤ境界を壊さない位置に置く。

```
frontend/entity/                      # 新規: Reason Entity 内部モデル（言語非依存）
  __init__.py
  kinds.py          EntityKind, TransitionPolicy, PersistencePolicy, LifecycleState
  identity.py       Canonical Entity ID の決定論的生成と検証
  model.py          ReasonEntity / ReasonStructure / ReasonObjectEntity / DerivedEntity / EntityRelation
  slot.py           RU Slot（軽量 Runtime 表現）と Materialization
  registry.py       EntityTable: 宣言集合・所有グラフ・依存グラフ・循環検出
  diagnostics.py    RE-* 診断の生成（toolchain.diagnostics へ橋渡し）

frontend/language_surface/
  nodes.py          + Entity 系 Surface ノード（§3.4）
  lexer.py          + `<-` 演算子
  parser.py         + `ru:` / `rus:` / `ruo:` / `derive:` / `<-` の解析、演算子継続
  validation.py     + Entity 型検査、= と <- の分離検証、型基盤修正（D-1〜D-5）
  integration.py    + Entity → Semantic AST metadata / Reason IR / ExecutionPlan 射影

frontend/integrated_computation_runtime.py
                    + EntityEnvironment（RU Slot テーブル）、モジュールレベル束縛（D-7）

frontend/tensor/runtime.py
                    + collect() の可達性走査に RU Slot を追加（C-5）

schemas/
  reason_entity.schema.json           # 新規: Entity IR ペイロードのスキーマ
  execution_plan.schema.json          # 改訂: entity_plan / vision_plan / reason_object_plan を明示

toolchain/
  diagnostics.py                      # RE-* プレフィックス登録
  reason_entity_baseline/             # 新規: Phase F0 の凍結・3回生成検証
  reason_entity_cmd.py                # 新規: `reason reason-entity <subcommand>`

reason_entity_tests/                  # 新規: pytest スイート（既存 *_tests 命名規約に従う）
```

**方針**: `frontend/entity/` は Surface 構文にも Tensor にも依存しない。
Phase E0 の受け入れ条件「Parser 新構文に依存せず、内部 API または fixture から
全 Entity Kind を生成・検証できること」を構造的に保証するためである。

### 3.2 Reason Entity データモデル

RUO-U1（[toolchain/reasonunit_object/model.py](toolchain/reasonunit_object/model.py)）の
語彙を再利用し、コンパイラ内表現を新設する。**U1 を再発明しない。**

```python
class EntityKind(str, Enum):
    RU     = "AtomicReasonUnit"
    RUS    = "ReasonUnitStructure"
    RUO    = "ReasonUnitObject"
    DERIVE = "DerivedReasonUnit"

class TransitionPolicy(str, Enum):
    INITIALIZE_ONLY = "InitializeOnly"   # derive: / const 相当
    EXPLICIT        = "Explicit"         # `<-` のみ許可（RU/RUS/RUO の既定）

class PersistencePolicy(str, Enum):
    SESSION    = "Session"      # v0.1 既定
    PERSISTENT = "Persistent"   # RUO のみ、明示指定時（v0.1 は宣言のみ・実体化は Deferred）

@dataclass(frozen=True)
class ReasonEntityDecl:
    canonical_id: str              # §3.3
    kind: EntityKind
    identifier: str                # 宣言された素の名前
    owner_id: str | None           # 親 RUS/RUO の canonical_id、モジュール直下は None
    namespace: str                 # package.module
    value_type: Any                # 既存 TypeNode（PrimitiveTypeNode 等）
    declared_type: Any | None      # 注釈がある場合のみ
    transition_policy: TransitionPolicy
    persistence_policy: PersistencePolicy
    members: tuple[str, ...]       # RUS/RUO のメンバ canonical_id（宣言順）
    dependencies: tuple[str, ...]  # DERIVE の依存元 canonical_id（宣言順）
    initializer: Any               # ExpressionNode
    lifecycle: str                 # LIFECYCLE ⊂ RUO-U1 ("proposed" | "active" | ...)
    revision: int                  # 宣言時は 0
    source_span: SourceSpanNode
```

`Evidence` / `Provenance` は v0.1 では**参照フィールドのみ**を保持し、
実体は既存の `evidence_registry` / `data_provenance.schema.json` 側へ委譲する。
（仕様 §4.1 は「すべての項目を Runtime 上の完全な Object として常時実体化する
必要はない」と明示している。）

**RUS と RUO の区別**（仕様 §4.3 / §4.4 / §10）は以下で実装する。

| 側面 | RUS | RUO |
|---|---|---|
| Canonical ID 名前空間 | `ruo:unit:` | `ruo:object:` |
| 所有境界 | 局所名前空間 + メンバ所有 | 同左 + Object Identity |
| 永続化 | 不可（`PersistencePolicy.SESSION` 固定） | 宣言可能 |
| Projection | 構造単位の Projection のみ | Execution Projection を含む |
| 空間情報 | 保持しない | `Spatial Profile` を保持しうる（v0.1 は宣言のみ） |
| 実行 | 不可 | **不可**（明示 Projection 経由のみ。§10.4） |
| 自動昇格 | RUS→RUO は**禁止**（`RE-RUO-001`） | — |

### 3.3 Canonical Entity ID

仕様 §7.2 は Package ID / Module ID / Ownership Path / Declared Identifier /
Entity Kind から決定論的に生成することを要求する。RUO-U1 の `CORE_PREFIXES`
と互換な形式を採る。

```
canonical_entity_id := <u1-prefix> <kind-tag> ":" <path>

u1-prefix := "ruo:unit:"    (RU / RUS / DERIVE)
           | "ruo:object:"  (RUO)
kind-tag  := "ru" | "rus" | "ruo" | "derive"
path      := <namespace> ( "." <owner-identifier> )* "." <identifier>
namespace := <package> "." <module>   (package がある場合)
           | <module>                 (package がない場合)
```

例（仕様 Appendix A、パッケージなし）:

```
ruo:unit:ru:GreetingLearning.learning_rate
ruo:unit:ru:GreetingLearning.current_step
ruo:unit:rus:GreetingLearning.greeting_relation
ruo:unit:ru:GreetingLearning.greeting_relation.token_relation
ruo:unit:derive:GreetingLearning.training_active
```

設計根拠:

- `startswith("ruo:unit:")` / `startswith("ruo:object:")` を維持するため、
  RUO-U1 の `validate_object` を改変せずに Entity を U1 オブジェクトへ投影できる。
- `namespace` の算出は既存 [integration.py:125](frontend/language_surface/integration.py:125)
  （`f"{package}.{module}" if package else module`）と**完全に一致**させる。
  既存 `node_id` 規約と乖離させないため。
- 識別子は `[A-Za-z_]\w*` に限定されるため、`.` と `:` は区切り文字として安全。
- ホスト固有絶対パス・メモリアドレス・時刻は一切含まない（仕様 §7.2 MUST NOT）。

**衝突検出**: `EntityTable` が canonical_id をキーとする辞書を保持し、
重複挿入時に `RE-ID-001` を発する。同一所有スコープ内の重複宣言は
より具体的な `RE-DECL-001` を優先する。

### 3.4 Surface AST ノード

仕様 §8.1 の 7 ノードを、既存 `nodes.py` の frozen dataclass 規約に従って追加する。

```python
@dataclass(frozen=True)
class ReasonEntityDeclarationNode:      # ru: / rus: / ruo: / derive: の共通宣言
    kind: EntityKindNode                # "ru" | "rus" | "ruo" | "derive"
    identifier: str
    type_annotation: TypeNode | None
    initializer: ReasonEntityInitializerNode | None   # rus:/ruo: は構造リテラル
    visibility: Visibility
    source_span: SourceSpanNode

@dataclass(frozen=True)
class ReasonEntityInitializerNode:
    expression: ExpressionNode

@dataclass(frozen=True)
class ReasonStructureLiteralNode:       # rus: の { ... } 本体
    members: tuple[ReasonEntityDeclarationNode, ...]

@dataclass(frozen=True)
class ReasonObjectLiteralNode:          # ruo: の { ... } 本体
    members: tuple[ReasonEntityDeclarationNode, ...]

@dataclass(frozen=True)
class DerivedEntityDeclarationNode:     # derive: の専用ノード
    identifier: str
    type_annotation: TypeNode | None
    expression: ExpressionNode
    source_span: SourceSpanNode

@dataclass(frozen=True)
class ReasonStateTransitionNode:        # `target <- value`
    target: str
    expression: ExpressionNode
    source_span: SourceSpanNode

@dataclass(frozen=True)
class EntityReferenceNode:              # 解決済み Entity 参照（式内）
    identifier: str
    canonical_id: str
```

`EntityReferenceNode` は Parser では生成せず、**名前解決フェーズで
`IdentifierNode` から昇格させる**。これにより既存の式パーサに手を入れずに済む。

上記はすべて [frontend/schemas/language_surface_ast.schema.json](frontend/schemas/language_surface_ast.schema.json)
の `$defs` にも追加し、`statement` / `module_member` の union に加える。

### 3.5 Semantic AST への射影

Semantic AST の宣言型を**増やさない**（ADR-102）。理由:

- `frontend/ast/nodes.py` の 6 種は `from_json_value` / `to_json_value` /
  `frontend/compiler/lowering.py` / `frontend/compiler/validator.py` /
  `schemas/ast.schema.json` / DTO バインディング（Rust/Python/TS/Go/Java）に
  横断的に影響する。Entity 導入と DTO 破壊的変更を同時に行うのは
  仕様 §3.7 Staged Compatibility に反する。

代わりに次の射影を採る。

1. **Entity 宣言**は `StateNode.data` の隣に置かず、`MetadataNode` として射影する:
   `MetadataNode(f"{namespace}-reason-entities", "reason_entities", <payload>)`。
   これは既存の `const_declarations` / `function_declarations` /
   `reason_object_bindings` と同じパターンである。
2. **状態遷移 `<-`** は既存 `semantic.TransitionNode` として射影する。
   `_project_calculations`（[integration.py:420](frontend/language_surface/integration.py:420)）
   が既に `let` / 代入を `<calc>.state.<identifier>` 遷移へ落としているため、
   `<-` はこの機構の**自然な拡張**であり、`relation` に
   `EntityTransitionTransition`（→ 命名は `EntityStateTransition`）を用い、
   `effect.entity_transition` に Entity 情報を付す。
3. **Relation** は既存 `semantic.TransitionNode`（`RelationNode` 射影と同じ経路）
   および `metadata.reason_entity_relations` へ射影する。

### 3.6 Reason IR 表現

C-1 により、Reason IR ルートは拡張できない。**`metadata.reason_entities` を
正規の格納先とする**（ADR-103）。ペイロードは新規スキーマ
`schemas/reason_entity.schema.json`（`reasonscript-reason-entity/0.1`）で検証する。

```jsonc
"metadata": {
  "reason_entities": {
    "schema_version": "reasonscript-reason-entity/0.1",
    "entities": [
      {
        "canonical_id": "ruo:unit:ru:GreetingLearning.learning_rate",
        "kind": "AtomicReasonUnit",
        "identifier": "learning_rate",
        "owner_id": null,
        "value_type": "Float",
        "declared_type": "Float",
        "transition_policy": "Explicit",
        "persistence_policy": "Session",
        "lifecycle": "active",
        "revision": 0,
        "members": [],
        "dependencies": [],
        "source_span": { "start_line": 2, "start_column": 3, "end_line": 2, "end_column": 34 }
      }
    ],
    "relations": [
      {
        "relation_id": "ruo:relation:GreetingLearning.greeting_relation.token_relation.member",
        "source": "ruo:unit:rus:GreetingLearning.greeting_relation",
        "target": "ruo:unit:ru:GreetingLearning.greeting_relation.token_relation",
        "relation_type": "PartOf",
        "relation_class": "internal",
        "validity": "declared",
        "evidence_refs": [],
        "provenance_ref": null,
        "revision": 0
      }
    ],
    "instructions": [
      { "op": "DeclareEntity",            "entity": "ruo:unit:ru:GreetingLearning.learning_rate", "kind": "AtomicReasonUnit", "type": "Float" },
      { "op": "InitializeEntityState",    "entity": "ruo:unit:ru:GreetingLearning.learning_rate", "value": { "node_type": "FloatLiteralNode", "value": 0.01 }, "revision": 0 },
      { "op": "DeclareDerivedEntity",     "entity": "ruo:unit:derive:GreetingLearning.training_active", "dependencies": ["ruo:unit:ru:GreetingLearning.current_step"], "strategy": "on_read" },
      { "op": "ProposeEntityTransition",  "entity": "ruo:unit:ru:GreetingLearning.current_step", "site": "Train#2", "proposed": { "...": "..." } },
      { "op": "ValidateEntityTransition", "entity": "ruo:unit:ru:GreetingLearning.current_step", "site": "Train#2", "expected_type": "Int" },
      { "op": "CommitEntityTransition",   "entity": "ruo:unit:ru:GreetingLearning.current_step", "site": "Train#2", "revision_delta": 1 }
    ]
  }
}
```

仕様 §8.3 が挙げる 10 命令の対応:

| 仕様の命令 | 本設計の `op` | 備考 |
|---|---|---|
| DeclareEntity | `DeclareEntity` | |
| InitializeEntityState | `InitializeEntityState` | |
| ReadEntityState | `ReadEntityState` | 依存解析結果として `derive` 評価点と `<-` の右辺に出力 |
| ProposeEntityTransition | `ProposeEntityTransition` | |
| CommitEntityTransition | `CommitEntityTransition` | 間に `ValidateEntityTransition` を挟む（Appendix B に準拠） |
| DeclareDerivedEntity | `DeclareDerivedEntity` | |
| EvaluateDerivedEntity | `EvaluateDerivedEntity` | |
| CreateStructure | `CreateStructure` | |
| CreateObject | `CreateObject` | |
| ProjectEntity | `ProjectEntity` | v0.1 は RUO→ExecutionPlan の明示 Projection のみ |

命令列は**宣言順・文順**で決定論的に生成する。ソート・辞書順再配置は行わない
（入力順序の情報が意味を持つため）。ただし `entities` / `relations` の配列は
canonical_id の昇順で正規化する（`canonicalize()` のレジストリ安定ソートと整合）。

### 3.7 ExecutionPlan

C-2 の既存不整合を、Entity 導入と同じ変更で解消する。
`execution_plan.schema.json` に**名前付きオプショナルプロパティ**を追加し、
`additionalProperties: false` は維持する。

```jsonc
"properties": {
  "selected_steps": {...}, "alternative_paths": {...}, "expected_cost": {...},
  "evidence_refs": {...}, "planner_version": {...},
  "reason_object_plan": { "type": "object" },   // 既存実装との整合（潜在不整合の解消）
  "vision_plan":        { "type": "object" },   // 同上
  "entity_plan":        { "$ref": "#/$defs/entity_plan" }
}
```

`entity_plan` の内容（仕様 §8.4）:

```jsonc
"entity_plan": {
  "schema_version": "reasonscript-reason-entity-plan/0.1",
  "declaration_order": ["<canonical_id>", "..."],
  "transition_sequence": [
    { "order": 1, "entity": "<canonical_id>", "site": "Train#2",
      "atomic_boundary": "Train#2", "revision_delta": 1 }
  ],
  "atomic_boundaries": [
    { "boundary_id": "Train#2", "entities": ["..."], "rollback_on_failure": true }
  ],
  "derived_evaluation": [
    { "entity": "<canonical_id>", "strategy": "on_read", "dependencies": ["..."] }
  ],
  "evidence_collection_points": [],
  "projection_boundaries": []
}
```

**互換性影響**: `entity_plan` は Entity を含むプログラムでのみ出力する。
Entity を含まない既存プログラムの ExecutionPlan は**バイト不変**である。
一方 `reason_object_plan` / `vision_plan` のスキーマ追加は、これらを含む
ExecutionPlan を「検証失敗」から「検証成功」へ変える。これは既存バグ修正であり、
`CHANGELOG.md` と Golden に記録する（AP-010）。

### 3.8 Runtime モデル（RU Slot）

```python
@dataclass
class RUSlot:
    slot_id: int                    # 実行内で単調増加、決定論的
    canonical_entity_id: str
    value_type: Any
    current_value: Any
    transition_policy: TransitionPolicy
    revision: int = 0
    provenance_ref: str | None = None
    materialized: bool = False
```

- `EntityEnvironment` が `identifier -> RUSlot` と `canonical_id -> RUSlot` の
  2 索引を持つ。所有スコープ（RUS/RUO）ごとに親リンクを持つチェーン構造とする。
- **`<-` の実行**は `propose → validate → commit` の 3 段で行い、
  validate 失敗時は `current_value` / `revision` を一切変更しない（仕様 §17 原子性）。
- **`derive` の評価**は §3.9 の戦略に従う。
- **Materialization**（仕様 §9.2）は `EntityEnvironment.materialize(canonical_id)`
  で RU Slot → 完全 `ReasonEntity` へ昇格させ、U1 互換ペイロードを生成する。
  トリガは仕様 §9.2 の 6 条件。

**C-5 への対応（重要）**: `TensorRuntime.collect` の可達性走査
（[tensor/runtime.py:440](frontend/tensor/runtime.py:440) `visit`）は
`dict` / `list` / `tuple` / `set` / `.fields` を持つオブジェクトのみを辿る。
RU Slot が Tensor を保持した場合、走査対象外だと **Tensor が誤って解放される**。
`visit` に `RUSlot` の明示分岐（`visit(value.current_value)`）を追加する。
`.fields` プロパティを生やす回避策は採らない（`RuntimeStruct` との意味的混同を避ける）。

### 3.9 Derived Entity の評価戦略

仕様 §5.4 は「依存元の更新によって再評価されるか、明示評価時に再計算されるかは
ExecutionPlan に記録する」とし、戦略の選択自体は実装に委ねている。

**v0.1 の決定: `on_read`（読み取り時評価 + 依存 revision メモ化）**（ADR-104）

```
evaluate(derived):
    key = tuple(revision of each dependency)
    if cache.key == key: return cache.value
    value = eval(expression)
    cache = (key, value)
    return value
```

根拠:

- 仕様 Appendix A の `while training_active { ... current_step <- current_step + 1 }`
  は、`training_active` がループごとに再評価されなければ**無限ループになる**。
  push 型（依存更新時に再計算）でも成立するが、on_read は評価順序が
  読み取り点で一意に定まるため決定論の証明が容易い。
- メモ化キーを依存 revision タプルにすることで、同一 revision 下の複数回読み取りが
  同一値を返すことを保証する（仕様 §9.3 意味保存）。
- ExecutionPlan の `derived_evaluation[].strategy = "on_read"` に必ず記録する。

**循環依存**は `EntityTable` の依存グラフで宣言時に検出し、
`RE-DERIVE-001`（新設、§5）を発する。

### 3.10 `=` と `<-` の分離

| 構文 | 対象 | 意味 | 違反時 |
|---|---|---|---|
| `ru: x = e` | 未宣言の Entity | 初期化 | 同名再宣言 → `RE-DECL-001` |
| `x <- e` | 宣言済み Entity | 状態遷移 | 未初期化 → `RE-STATE-001` / derive 対象 → `RE-STATE-002` |
| `x = e` | 宣言済み **Entity** | **禁止** | → `RE-STATE-003`（新設、§5）「Entity の更新には `<-` を使用」 |
| `x = e` | 通常の `let` 変数 | 従来どおり再代入 | 変更なし（仕様 §16.2 互換モード） |
| `let x = e` | 局所計算値 | 従来どおり | 変更なし |

これにより仕様 §3.2 Explicit Transition と §16.2 既存再代入の互換が両立する。
判定は名前解決の結果（Entity か通常束縛か）で行うため、静的に決定論的である。

---

## 3.11 実装状況（2026-08-20 時点）

本設計に基づく実装は Phase 単位で進行中である。現時点の状態を記録する。

| Phase | 状態 | 内容 |
|---|---|---|
| F0 Baseline Freeze | **完了** | [toolchain/reason_entity_baseline/](toolchain/reason_entity_baseline/) 実装。`reason reason-entity-baseline generate/validate` で 3 回生成 byte-identical を確認済み（`performance_baseline.json` は §7 の方針どおり比較対象外）。テストは [tests/reason_entity_baseline/](tests/reason_entity_baseline/)。 |
| F1 Type Foundation Repair | **部分完了**（D-3・D-4・D-5 実装済み。D-1・D-2 は**再設計完了・実装待ち**） | 詳細は各 F1-N 節の「実装時の訂正」を参照。D-1/D-2 は全数計測により当初設計が反証されたため再設計済み → [F1-R](#f1-r-d-1--d-2-再設計2026-08-21)。テストは [type_foundation_repair_tests/](type_foundation_repair_tests/)。 |
| F2 Surface Prerequisite Foundation | **完了**（F2-3 のみ範囲縮小） | 演算子継続（D-6）、`<-` 語彙化、[frontend/entity/](frontend/entity/) の Canonical ID・`EntityTable` を実装。詳細は F2-3 節の「実装時の訂正」を参照。テストは [surface_prerequisite_foundation_tests/](surface_prerequisite_foundation_tests/)。 |
| E0 Internal Reason Entity Model | **完了** | [frontend/entity/](frontend/entity/) を完成（`model.py` / `slot.py` / `diagnostics.py` / `lowering.py` を追加）。[schemas/reason_entity.schema.json](schemas/reason_entity.schema.json) を新設。仕様 §13 Phase E0 の受け入れ条件（全 Entity Kind 生成、3 回生成 byte-identical、スキーマ通過、RUO-U1 `validate_object` 診断 0 件）をすべて満たすことを [reason_entity_tests/test_entity_model.py](reason_entity_tests/test_entity_model.py) で実証。Parser には一切触れていない。 |
| E1 Surface Model v0.1 | **完了**（一部診断は v0.1 の構文的制約により未到達） | `ru:`/`rus:`/`ruo:`/`derive:`/`<-` を Parser・名前解決・検証・Semantic AST/Reason IR/ExecutionPlan 射影・Runtime まで配線。D-7（モジュールレベル宣言が実行時環境に存在しない欠陥）を解消し、仕様 Appendix A を実際に実行して検証。テストは [surface_model_tests/](surface_model_tests/)。詳細は本節末尾の「実装時の訂正・確定事項」を参照。 |
| E2 Integration | **完了（代替モデルで実施）** | RS-DT-JP-GREET-001 は本リポジトリに存在しないため（§2.2 Q2）、代替の Tensor 学習ループ（`let` 版と `ru:`/`derive:`/`<-` 版）で移行等価性・決定論・性能を検証。テストは [entity_migration_regression_tests/](entity_migration_regression_tests/)、性能レポートは [artifacts/reason_entity/e2/performance_report.json](artifacts/reason_entity/e2/performance_report.json)。実装時に E1 の実バグ（後述）を発見・修正。 |

**D-1・D-2 を本セッションで保留した理由**: 当初計画どおり D-1（引数型推論）・D-2
（戻り値型推論）を実装しようとしたところ、その前段の F1-4（未知関数呼出の
静的検出）で、`notify(x)` / `publish(order)` のような**未宣言識別子への呼出**が
`statement_tests/` を含む 16 個の既存テストファイルにわたって「効果を表す文」の
慣用表現として確立されていることが判明した。同時に、リポジトリ全体で
型注釈なしパラメータを持つ関数宣言が 30 件以上見つかった
（`fn add(a, b)` 等）。D-1 の「呼出文脈からの単一化推論、失敗時はエラー」を
安全に実装するには、これらすべてを列挙し、影響を個別に判定・移行する必要があり、
本設計が F1-1/F1-2 について当初から警告していた「新たなエラーを生む可能性がある。
実装時に全数計測する」のとおりの状況である。D-3/D-4/D-5 は verified・低リスクで
完了させ、D-1/D-2 は独立した計測・移行作業として次のセッションへ持ち越す方が、
2000 件超の既存テストを持つこのリポジトリに対して安全である。

各修正は `python3 -m pytest -q`（2024 passed / 6 skipped、regression なし）と
`reason ci --json`（`status: PASS`）で検証済み。

---

## 4. Phase 別実装設計

仕様 §13 の Phase 構成に従う。各 Phase は独立に検証可能で、
`reason ci` を通過した時点でコミット可能とする。

### Phase F0 — Baseline Freeze

**目的**: v0.5.4.6 の観測可能挙動を回帰基準として凍結する。

**成果物**（`artifacts/reason_entity/f0/` 配下）:

| ファイル | 内容 |
|---|---|
| `environment_manifest.json` | Python 版・プラットフォーム・依存版・HEAD SHA |
| `surface_ast_baseline.json` | 正規 fixture 集合の Surface AST ダイジェスト |
| `semantic_ast_baseline.json` | 同 Semantic AST ダイジェスト |
| `reason_ir_baseline.json` | 同 Reason IR ダイジェスト |
| `execution_plan_baseline.json` | 同 ExecutionPlan ダイジェスト |
| `diagnostic_code_inventory.json` | 現行診断コードの全数一覧 |
| `tensor_numeric_baseline.json` | Tensor 主体 fixture の loss curve と `.rstensor` SHA-256 |
| `ruo_compatibility_baseline.json` | RUO-C0/C1/U1/F1/T1/N1/N2 成果物ダイジェスト |
| `performance_baseline.json` | §7 の各測定項目の基準値 |
| `validation_summary.json` / `run_manifest.json` | 総括 |

**実装**: `toolchain/reason_entity_baseline/` を
[toolchain/reasonunit_baseline/baseline.py](toolchain/reasonunit_baseline/baseline.py)
（RUO-C0）の構造を踏襲して新設する。`stable_json` / `sha256_bytes` /
`artifact()` の実装パターンをそのまま再利用する。

CLI: `reason reason-entity baseline --freeze` / `--verify`。

**受け入れ条件**:
- 3 回独立生成で全 canonical 成果物が byte-identical。
- `python3 -m pytest -q` が 2005 passed / 6 skipped を維持。
- `reason ci` が成功。

**この Phase ではプロダクションコードを一切変更しない。**

---

### Phase F1 — Type Foundation Repair

**目的**: D-1〜D-5 を修正する。Surface 構文は追加しない。

#### F1-1: 関数引数の型（D-1）

- `_function_parameter_type` が `None` を返す場合、**呼出文脈からの単一化推論**を試みる。
  - モジュール内の全呼出サイトを収集し、実引数型を集める。
  - 全て同一型 → その型を採用。
  - 呼出サイトが 0 個、または型が複数 → **宣言位置**で
    `TYPE-020 parameter type annotation required`（新設）を発する。
- 効果: `if flag` が `CV-1 FCF-004`（使用位置の間接エラー）ではなく、
  `fn f(flag)` の位置で「注釈が必要」と報告される。

**互換性**: 注釈なし引数を持ち、かつ推論不能な既存コードは**新たにエラーになる**。
リポジトリ内 `.rsn` コーパスへの影響は F1 実装時に全数計測し、影響 fixture は
注釈追加で移行する（Golden 更新対象）。

> **⚠ 本節は 2026-08-21 の全数計測により反証された。** 対象 15 個中 14 個が
> 呼出サイトを持たず、`reason init` が生成するテンプレートを含むため、
> 本設計を実装すると新規プロジェクトがコンパイル不能になる。
> 置換設計は **[F1-R.4 F1-1r](#f1-r4-f1-1r-d-1-の再設計二層方式)** を参照。

#### F1-2: 戻り値型（D-2）

- 注釈なし関数について、`_function_return_paths`（既存、
  [integration.py:837](frontend/language_surface/integration.py:837)）が既に
  全 return 経路を列挙している。各経路の式型を求めて単一化する。
  - 全一致 → 採用。
  - 不一致 → `TYPE-021 conflicting return types`（新設）。
  - 経路 0（`FN-010` で既に検出済み）→ 現行動作維持。
- 再帰呼出は既に `FN-007` で拒否されるため、不動点計算は不要。

> **補足（2026-08-21 の全数計測）**: 本節の方針自体は有効だが、単一化規則に
> `Null` / Unknown を除外する規則が欠けており、そのままでは実在する
> `fn find(...) { ... return value ... return null }` を破綻させる。
> また不一致時の `TYPE-021` 即時導入はリスクが高い。
> 補正後の設計は **[F1-R.5 F1-2r](#f1-r5-f1-2r-d-2-の再設計段階的厳格化)** を参照。

#### F1-3: `tensor.to_array` の要素型（D-3）

型検査器を Tensor 契約レジストリに接続する（現在は接続されていない）。

```
result_type(tensor.to_array(x)):
    shape = infer_tensor_shape(x, bindings)     # 既存 API
    dtype = infer_tensor_dtype(x, bindings)     # 新設（既存 DTYPES から）
    if shape is not None and dtype is not None:
        return nested ArrayTypeNode of rank len(shape) over primitive(dtype)
    if 宣言位置に型注釈がある:
        return その注釈型（実行時に整合検証）
    raise TYPE-022 "tensor.to_array result type requires an annotation"
```

- `f32`/`f64` → `Float`、`i32`/`i64` → `Int`、`bool` → `Bool`（`DTYPES` に従う）。
- rank 1 → `[Float]`、rank 2 → `[[Float]]`。
- 推論不能時に `Unknown` へ落とさない点が仕様 §6.2 の要求（Unknown を残さない）と整合する。
- 式への直接添字（`tensor.to_array(x)[0]`）も同一規則で処理される
  （`IndexAccessNode` の `collection` を通常どおり型付けするだけで成立する）。

**実装時の訂正（範囲の縮小）**: 「宣言位置に型注釈がある場合はそれを使う」の
分岐は実装しなかった。`_expression_type` は型注釈を持つ呼出元（`LetStatementNode`
等）の情報を受け取らずに再帰する設計であり、これを通すには module-level の
状態（`_CURRENT_FUNCTION` と同種のグローバル）を新設して 2 箇所の呼出順序を
組み替える必要があった。既存の「`_expression_type` を先に評価し、その後で
`type_annotation` と比較する」という呼出順序を崩さずに実装できる範囲として、
本実装は次の縮小版を採用する。

- shape 推論は `tensor.to_array` の**直接引数**に対してのみ行う。
  `let a = tensor.zeros(...)` のように一度 `let` を経由した識別子は、
  `infer_tensor_shape` に bindings（識別子→shape の対応表）を渡していないため
  解決できず、**rank は既定で 1 にフォールバックする**。
  仕様 Appendix A・本欠陥が実際に報告した `let values = tensor.to_array(x); values[0]`
  の形（rank 1 で足りる）はこれで解消するが、`let a = tensor.zeros([2,3], "f32")`
  を経由した 2 階以上の `tensor.to_array` 添字アクセスは、
  本 Phase では未解決のまま残る（既知の制約として記録する）。
- 上記に伴い `TYPE-022`（注釈要求診断）は実装しなかった。不明な dtype は
  `f32`（→ Float）にフォールバックし、常に添字アクセス可能な型を返す方針とした。
  Unknown を残さないという仕様 §6.2 の趣旨は、「型注釈へのフォールバック」ではなく
  「安全な既定値へのフォールバック」で満たしている。
- 副次的に、`infer_tensor_shape`（[frontend/tensor/integration.py](frontend/tensor/integration.py)）
  が `tensor.zeros` / `tensor.ones` / `tensor.full` の形状推論に未対応だったため、
  この 3 関数を `tensor.create` と同様に扱う分岐を追加した（既存関数の抜けの修正）。
- 識別子経由の shape 伝播（`_shape_bindings` 相当の仕組みを
  `_to_array_result_type` へ接続すること）は v0.2 以降の課題とする。

#### F1-4: Int→Float 明示変換（D-4）

- 組込変換関数 `float(x)` / `int(x)` を**予約組込**として追加する。
  - 静的型: `float(Int|Float) -> Float`、`int(Int|Float) -> Int`。
  - `int(Float)` は**ゼロ方向切り捨て**（`math.trunc`）と定義する。
    Python の `int()` と一致し、決定論的。
  - 実行時: [integrated_computation_runtime.py](frontend/integrated_computation_runtime.py)
    の呼出ディスパッチに追加。
- **実装時の訂正（未知関数呼出の一律拒否は撤回）**: 当初案は「`CallExpressionNode`
  の callee がモジュール内関数・Tensor・Vision・組込のいずれにも解決できない場合、
  `_UNKNOWN_TYPE` を返さず `FN-011 unknown function` を発する」としていたが、
  実装時の全数計測で、`notify(...)` / `publish(...)` のような**未宣言の識別子への
  呼出**が、文の効果を表す ExpressionStatementNode として既存テストコーパス全体
  （`statement_tests/` / `language_surface_core_conformance_tests/` など 16 テスト
  ファイル）で確立された慣用表現であることが判明した。これらは戻り値を消費しない
  文であり、D-4 が実際に問題としていた「型を消費する位置（`let` / `const` /
  `result =` / 引数）で Unknown が静かに伝播する」ケースには該当しない。
  一律拒否は仕様 §2.2 の後方互換要求に反する規模の破壊的変更になるため、
  **本設計は撤回し、`float(x)` / `int(x)` 組込の専用型付けのみを実装する**。
  未知関数呼出は従来どおり `_UNKNOWN_TYPE` にフォールバックする。
  一般の未知関数検出（`FN-011`）は、Entity 導入後に型を消費する位置に限定した
  形で再設計する候補として v0.2 以降へ持ち越す。

#### F1-5: 除算の型（D-5）

**採用案: 静的型を実行時挙動に合わせる。**
`Int / Int` の静的結果型を `Int` から `Float` に変更する。

| 案 | 内容 | 数値影響 | 判定 |
|---|---|---|---|
| (a) 静的型を Float に | 型検査器のみ変更 | **なし** | **採用** |
| (b) 実行時を整数除算に | Runtime 変更 | あり（既存の数値結果が変わる） | 却下（仕様 §2.2 に抵触） |

- 整数除算が必要な場合は `int(a / b)` を用いる（F1-4 で提供）。
- 実測: リポジトリ内 `.rsn` コーパスに `/` の使用は **0 件**。
  Python テスト内の埋め込みソースは
  [expression_lowering_tests/test_expression_lowering.py:23](expression_lowering_tests/test_expression_lowering.py:23)
  の `x / y` のみで、これは lowering 名（`DivideTransition`）の検査であり型に依存しない。
  **影響範囲は極めて小さい。**
- `CHANGELOG.md` に互換性変更として記録する（AP-010）。

#### F1-R: D-1 / D-2 再設計（2026-08-21）

Phase F1 で D-1（引数型推論）・D-2（戻り値型推論）を保留した際、
理由を「既存コーパスへの影響が大きく全数計測が必要」と記録した。
本節はその全数計測の結果と、それに基づく**当初設計の反証および再設計**を記録する。

##### F1-R.1 実測結果

計測対象: リポジトリ内の全 `.rsn`（192 ファイル）に加え、Python テスト内に
三重引用符で埋め込まれたモジュールソース（`module`/`model` 宣言を含むもの）を
全抽出したもの。合計 491 ソース、うち構文的に解析可能な 298 件を対象とした
（残りは invalid fixture や断片スニペットであり対象外）。

| 項目 | 実測値 |
|---|---|
| 型注釈なし引数を持つ関数 | **15 個**（`.rsn` 3 + 埋め込み 12） |
| うち**同一モジュール内に呼出サイトが存在しない**もの | **14 個** |
| うち呼出サイトがあり推論を試行できるもの | **1 個**（`fn add(a, b)`） |
| 戻り値型注釈なしの関数 | **22 個** |
| うち return 文が 0 個のもの | **0 個** |
| うち return 式の種別が複数混在するもの | **2 個** |

##### F1-R.2 当初設計（F1-1）の反証

当初の F1-1 は「呼出サイトが 0 個、または型が複数 → 宣言位置で
`TYPE-020` を発する」と定めていた。実測の結果、**型注釈なし引数を持つ
関数の 15 個中 14 個が「同一モジュール内に呼出サイトを持たない」**。
すなわち当初設計はこの 14 個すべてを新規エラーにする。

決定的なのは、その中に次の 2 つが含まれることである。

```
# hello_world/src/main.rsn — `reason init` が生成するスターターテンプレート
package hello_world
module main {
    fn run(goal) {
        return goal
    }
}
```

```
# standard_library/install_smoke_test.rsn — インストール検証用スモークテスト
```

`fn run(goal) { return goal }` は [toolchain/init_cmd.py:37](toolchain/init_cmd.py:37)
のテンプレート文字列そのものである。したがって当初設計を実装すると
**`reason init` で新規作成したプロジェクトが即座にコンパイル不能になる**。
これは移行コストの問題ではなく、設計の誤りである。

**当初設計が誤った原因**: 「関数は同一モジュール内から呼ばれる」という
暗黙の前提を置いていた。実際のこのコードベースの支配的パターンは
**エントリポイント・ライブラリ公開関数・パーサ検証用 fixture** であり、
いずれも「宣言されるが同一モジュールからは呼ばれない」。
呼出サイト単一化は、この前提が成り立つコードベースでしか機能しない。

##### F1-R.3 仕様 §6.2 の再解釈

仕様 §6.2 は次のとおり定める。

> 型注釈のない関数引数を無条件に Unknown のまま残してはならない。次のいずれかを実施する。
> - 呼び出し文脈から一意に推論する。
> - 推論不能な場合、宣言位置で型注釈を要求する診断を出す。
>
> **Unknown 値が if 条件や状態遷移に到達してから間接的なエラーを出す実装は不適合とする。**

最後の一文が**適合性の判定基準**である。すなわち仕様が禁じているのは
「Unknown の存在」そのものではなく、**Unknown に起因するエラーが原因から
離れた使用位置で間接的に報告されること**である。
「型注釈を要求する」は、その目的を達成する手段の一例として挙げられている。

この読み直しにより、`reason init` を壊さずに §6.2 の適合基準を満たす
設計余地が生まれる。実際、D-1 として当初記録した欠陥の症状も
「宣言位置ではなく**使用位置**で間接的に失敗する」ことであり、
診断の局所性こそが解決すべき問題であった。

##### F1-R.4 F1-1r: D-1 の再設計（二層方式）

**第 1 層 — 機会主義的な呼出サイト推論（決してエラーにしない）**

- 型注釈なし引数について、同一モジュール内の呼出サイトを収集する。
- 実引数型がすべて同一の具体型に単一化できる場合のみ、その型を採用する。
- 呼出サイトが 0 個、型が複数、いずれかが Unknown → **推論を諦め Unknown を維持する**
  （エラーにしない。ここが当初設計との決定的な差）。

**第 2 層 — 宣言位置に係留した診断（当初の「注釈必須」規則を置換）**

- Unknown を維持したまま、その値が**具体型を要求する位置**に到達した時点で
  `TYPE-020` を発する。ただしメッセージは**引数の宣言位置と引数名を明示**する。
- 具体型を要求する位置: `if`/`while` 条件、論理演算子の被演算子、
  算術演算子の被演算子、Entity 状態遷移（`<-`）の右辺。

効果の比較:

| 入力 | 現行 | F1-1r 適用後 |
|---|---|---|
| `fn f(flag) { if flag { ... } }` | `CV-1 FCF-004 condition must be Bool`（使用位置・原因不明） | `TYPE-020`: 「`fn f` の引数 `flag` に型注釈がなく推論もできません。`flag: bool` の注釈を追加してください」（宣言位置を明示） |
| `fn run(goal) { return goal }` | 通過 | **通過**（`goal` は具体型を要求する位置に到達しない） |

これにより §6.2 の適合基準（間接的エラーの禁止）を満たしつつ、
`reason init` テンプレートと 14 個の既存 fixture がすべて有効なまま維持される。

**実装方式の選択**: Unknown に来歴（provenance）を持たせる必要があるが、
`_UNKNOWN_TYPE` は現在 `object()` の素のセンチネルであり、
[validation.py](frontend/language_surface/validation.py) 内に
`is _UNKNOWN_TYPE` / `is not _UNKNOWN_TYPE` の同一性比較が **25 箇所**存在する。
センチネルをクラス化して来歴を載せる案は、この 25 箇所すべての監査を要し
リスクが高い。

採用案: **`_Binding` に来歴フィールドを追加する側テーブル方式**。
`_Binding` は現在 `type_node` / `mutable` の 2 フィールドのみであり、
`_validate_function` が引数束縛を生成する唯一の箇所（[validation.py:805](frontend/language_surface/validation.py:805) 付近）で
`provenance` を設定できる。条件検証関数
（`_require_bool_condition` / `_require_function_bool_condition` / `_require_iterable`）は
すでに `bindings` をスコープに持つため、被検査式が
「来歴付き Unknown の `IdentifierNode`」である場合に係留診断へ切り替えられる。
**`_UNKNOWN_TYPE` の同一性セマンティクスには一切触れない。**

##### F1-R.5 F1-2r: D-2 の再設計（段階的厳格化）

実測により D-2 は D-1 と**リスクプロファイルが根本的に異なる**ことが判明した。

- return 文 0 個の関数は 0 個（既存 `FN-010` が既に排除している）。
- 戻り値型推論は本質的に**受容範囲を広げる方向**の変更である。
  現在 `fn f(x: int) { return x > 1 }` の呼出結果は Unknown となり、
  `if y` が `CV-1 ConditionMustBeBoolean` で**誤って拒否**される（これが D-2 の症状）。
  推論を入れると Bool と判明し、**通るようになる**。

ただし厳格化方向の副作用が 1 つある: 推論後の戻り値型が呼出側の
期待型と衝突する場合、従来 Unknown により通過していたコードが新たにエラーになる。

**単一化規則**（実測で判明した必須要件）:

- `Null` は単一化から除外する。既存 `_require_compatible` が
  `if actual == PrimitiveTypeNode(PrimitiveKind.NULL): return` として
  Null を全型互換に扱っており、これに整合させる必要がある。
  実測した唯一の混在ケース
  `fn find(values, target) { ... return value ... return null }`
  （[test_core_language_phase3_iteration.py:23](language_spec_validation_tests/test_core_language_phase3_iteration.py:23)）は、
  この規則がなければ即座に破綻する。
- Unknown の経路も単一化から除外する（制約を与えないため）。
- 残りの具体型がすべて一致 → 採用。
- 残りの具体型が不一致 → **第 1 段では Unknown へフォールバック**（現行動作維持）。

**段階的厳格化**（仕様 §3.7 Staged Compatibility に従う）:

| 段 | 内容 | 検証ゲート |
|---|---|---|
| 第 1 段 | 単一化成功時のみ型を採用。不一致は Unknown 維持（エラーなし） | 全テスト緑・`reason ci` PASS・`tensor_numeric_baseline.json` 差分ゼロ |
| 第 2 段 | 不一致を `TYPE-021` として拒否 | 第 1 段の状態で不一致件数を計測し、**0 件または移行可能と確認できた場合のみ**実施 |

第 2 段を独立させる理由は、第 1 段が純粋に受容範囲を広げる低リスク変更であり、
万一の回帰が起きた場合に原因を第 1 段/第 2 段のどちらかへ即座に切り分けられるため。

##### F1-R.6 実装順序と検証ゲート

各段の完了時に `python3 -m pytest -q`（現行基準: 2088 passed / 6 skipped）と
`reason ci --json`（`status: PASS`）を必須ゲートとする。

1. **F1-2r 第 1 段**（戻り値型推論・エラー追加なし）— 最も低リスク。単独で着地させる。
2. **F1-2r 第 2 段の可否判定** — 不一致件数を計測。0 件なら `TYPE-021` を導入、
   非 0 件なら件数と内訳を報告して判断を仰ぐ。
3. **F1-1r 第 1 層**（呼出サイト推論・エラー追加なし）— 推論成功により
   新たな型エラーが顕在化しないか計測する。
4. **F1-1r 第 2 層**（`TYPE-020` の係留診断）— `_Binding.provenance` を追加し、
   条件検証 3 箇所を係留診断へ切り替える。

各段は独立コミットとし、回帰が出た場合はその段のみを切り戻せるようにする。

##### F1-R.7 診断コードの変更

| Code | 当初設計 | 再設計後 |
|---|---|---|
| `TYPE-020` | 「推論不能な引数は宣言位置で注釈必須」（**宣言時**にエラー） | 「型注釈なし引数が具体型を要求する位置に到達した」（**使用時**に検出するが、**メッセージは宣言位置と引数名を係留表示**） |
| `TYPE-021` | 戻り値型が経路間で不一致（無条件） | 同左。ただし **F1-2r 第 2 段**として分離し、実測で 0 件を確認してから導入 |

##### F1-R.8 残るリスクと未解決事項

- **F1-1r 第 1 層の副作用は未計測**。呼出サイト推論が成功した結果、
  関数本体内で新たな型エラーが顕在化する可能性がある（例:
  `fn f(x) { return x + 1 }` を `f("s")` で呼ぶと `x` が String と推論され
  `x + 1` がエラーになる）。これは**正しい新規エラー**だが、
  既存 fixture に該当がないかは実装時に計測する。実測上、推論を試行できる
  対象は `fn add(a, b)` の 1 個のみであり、影響は極小と見込まれる。
- **`TYPE-020` の到達位置の網羅性**。「具体型を要求する位置」として
  条件・論理演算・算術演算・Entity 遷移を挙げたが、
  網羅性は実装時に `_UNKNOWN_TYPE` を参照している 42 箇所を精査して確定する。
  網羅しきれない位置が残る場合、その位置では従来どおりの診断が出る
  （劣化はしないが §6.2 の目的を完全には満たさない）ため、
  残存箇所を limitations として明示記録する。
- **モジュール横断の呼出サイトは対象外**。F1-1r 第 1 層は同一モジュール内の
  呼出のみを見る。モジュール横断の推論は名前解決順序への依存を生み
  決定論（§3.3）を脅かすため、v0.1 では意図的に対象外とする。

#### F1 受け入れ条件

- 型検査変更の前後で、**型バグ修正の対象を除く**すべての Runtime 数値結果が一致すること。
  検証方法: F0 の `tensor_numeric_baseline.json` を再生成し diff が空であること。
- 新規診断 `TYPE-020` / `TYPE-021` / `FN-012` / `FN-013` の正常系・異常系 fixture を追加。（`TYPE-022` は実装せず、安全な既定値へのフォールバックを採用した。上記「実装時の訂正」参照。）
- `reason ci` 成功。

---

### Phase F2 — Surface Prerequisite Foundation

**目的**: 新構文を**有効化せず**、その前提となる Parser/AST 基盤を整備する。

#### F2-1: 演算子継続（D-6）

`_collect_simple_statement`（[parser.py:441](frontend/language_surface/parser.py:441)）の
継続条件を「括弧バランス > 0」から
「括弧バランス > 0 **または** 行末が継続可能演算子」へ拡張する。

継続可能演算子（行末に現れた場合のみ）:
```
+ - * / % && || == != < > <= >= = -> <- , .
```

- 文字列リテラル内は既存 `_strip_line_comment` と同じ引用符追跡で除外する。
- **曖昧性の排除**（仕様 §5.5 MUST NOT）: 行末が上記に該当しない限り従来どおり
  1 行で確定する。よって既存プログラムの解析結果は不変である。
  「新旧の解析結果が曖昧になってはならない」を、
  「継続は行末演算子の有無で一意に決まり、既存の行末は演算子で終わらない」
  という不変条件で満たす。
- 回帰検証: F0 の `surface_ast_baseline.json` が byte-identical であること。

#### F2-2: `<-` の語彙化（C-4）

[lexer.py:135](frontend/language_surface/lexer.py:135) の複数文字演算子表に
`"<-"` を追加する。`<=` より後、`<` より前に置く（最長一致順序に注意:
現行実装は tuple の記載順で最初にマッチしたものを採るため、`"<="` の直後に置く）。

**注意**: `a < -1` が `a <- 1` と誤解析される。現行の
`_parse_simple` は正規表現ベースであり `tokenize()` の結果を使わないため
即座の影響はないが、将来のトークンパーサ移行に備え、
比較の右辺に単項マイナスが来る場合は空白を必須とする規則を
`docs/grammar.md` 相当の文書へ明記する。v0.1 では
**`<-` は文頭パターン `^<identifier>\s*<-\s*` でのみ認識**し、
式中では `<-` を演算子として扱わない（→ 誤解析は構造的に発生しない）。

#### F2-3: Entity 名前解決の基盤

- `frontend/entity/identity.py` に Canonical ID 生成器を実装する（§3.3）。
- `frontend/entity/registry.py` に `EntityTable` を実装する
  （所有グラフ、依存グラフ、循環検出、衝突検出）。
- `namespace.py` の `resolve_program` に Entity スコープチェーンを追加する。
  **この時点では Entity 宣言が存在しないため、動作は完全に no-op である。**

**実装時の訂正（範囲の縮小）**: `namespace.py` の `resolve_program` への
フックは実装しなかった。この関数は Entity を含まない既存プログラムの
名前解決を毎回通る、極めて高頻度に実行される中核関数である。E1-1 で
`ReasonEntityDeclarationNode` が Surface AST に追加されるまでは、
このフックが実際にマッチしうる AST ノード型が存在しないため、
「完全な no-op」という設計上の前提そのものは正しいが、
**その no-op を実証するためだけにこの中核関数へ変更を加えることは、
得られる利益がゼロのままリスクだけを負う**と判断した。
`frontend/entity/identity.py` / `registry.py` は Surface 非依存で
完全に独立してテスト可能であるため（本節冒頭の 2 項目）、
`namespace.py` との接続は、実際に接続すべき Surface ノードが存在する
E1-2（§4 Phase E1）まで延期する。

#### F2-4: 診断基盤

- [toolchain/diagnostics.py:33](toolchain/diagnostics.py:33) `CODE_CATEGORY_PREFIXES`
  に `"RE": "Semantic"` を追加する。
- **`CATEGORIES` に新カテゴリを追加しない**（C-7）。理由: `diagnostics_summary.json`
  は全カテゴリのゼロ初期化辞書を出力するため、新カテゴリは Entity を含まない
  既存プロジェクトの正規成果物までバイト変化させる。仕様 §2.2 の後方互換要求と
  §3.7 Staged Compatibility に反する。専用カテゴリ `ReasonEntity` の新設は
  v0.2 の課題とする（ADR-105）。

#### F2 受け入れ条件

- 新構文をまだ有効化しない互換モードで、F0 の全 Golden がバイト一致。
- `python3 -m pytest -q` が F0 と同一の pass/skip 数。
- `reason ci` 成功。

---

### Phase E0 — Internal Reason Entity Model

**目的**: `frontend/entity/` を完成させる。**Parser には触れない。**

実装対象:

| ファイル | 内容 |
|---|---|
| `kinds.py` | `EntityKind` / `TransitionPolicy` / `PersistencePolicy` / `LifecycleState`（RUO-U1 `LIFECYCLE` から導出） |
| `identity.py` | Canonical ID 生成・パース・検証（§3.3） |
| `model.py` | `ReasonEntityDecl` / `EntityRelation` / U1 互換ペイロード生成 |
| `slot.py` | `RUSlot` / `EntityEnvironment` / propose-validate-commit / materialize |
| `registry.py` | `EntityTable`: 宣言登録、所有グラフ、依存グラフ、循環検出、衝突検出 |
| `diagnostics.py` | `RE-*` 診断ファクトリ |
| `lowering.py` | `EntityTable` → Reason IR `metadata.reason_entities` / ExecutionPlan `entity_plan` |

**受け入れ条件**（仕様 §13 Phase E0）:
- Parser 新構文に依存せず、内部 API または JSON fixture から
  RU / RUS / RUO / DerivedRU の全 Kind を生成・検証できること。
- `reason_entity_tests/test_entity_model.py` が、
  Appendix A 相当の Entity 構成を**構文なしで**組み立てて
  Reason IR ペイロードと ExecutionPlan `entity_plan` を生成し、
  3 回生成で byte-identical であることを検証する。
- 生成ペイロードが `schemas/reason_entity.schema.json` を通過すること。
- RUO-U1 `validate_object` に投影して診断 0 件であること
  （RUO-U1 との構造互換の実証）。

**実装時の訂正・確定事項**:

- **`ReasonEntityDecl` / `model.py` の扱い**: §3.2 の当初案は
  `ReasonEntityDecl` を `model.py` に置くとしていたが、F2 で先に
  `registry.py` の `EntityRecord` として実装・テスト済みであったため、
  同じ役割を果たす型を `model.py` へ移動（リネームのみ）することは
  何の振る舞いも変えずにリスクだけを負う。`EntityRecord` は
  `registry.py` に残し、`model.py` は F2 未実装だった 2 点
  （`EntityRelation` 型と RUO-U1 投影関数）に専念させた。
- **RUO のネスト投影は対象外**: `project_to_ruo_u1` は Entity Kind が
  `RUO` の宣言を含む `EntityTable` を拒否する（`RE-RUO-002`、新設）。
  RUO-U1 は 1 文書につき 1 つの `object_identity` のみを持つため、
  RUO を入れ子にした Reason Entity 構成をこの平坦な投影へ写すことは
  未定義になる。これは仕様 §10 Q4/Q5（RUO の永続化・RUS→RUO 明示変換の
  詳細仕様が Deferred）と整合する境界であり、v0.1 の非目標
  （§2.3「RUOの暗黙的実行」「完全な所有権推論」）を超えて先取りしない。
- **Derived Entity の依存循環検出の実効範囲**: `EntityTable.declare` は
  宣言順の単一パスであり、未宣言の Entity への依存は
  `RE-REL-001`（不明な依存）として先に拒否されるため、複数ノードを跨ぐ
  A↔B 循環は構造的に `_creates_dependency_cycle` の走査へ到達し得ない
  （到達できるのは自己参照のみ）。これは Surface 言語自体が前方参照を
  禁止していること（`let`/`const` と同様）と整合しており、Phase E1 で
  Surface の `derive:` を接続しても同じ制約が保たれる。走査ロジック自体は
  将来 2 パス方式の登録 API を導入した場合に備えて一般形のまま残した
  （`frontend/entity/registry.py` のコメント参照）。
- **Tensor 型の Entity 遷移は E0 では実 Tensor を使わない**: Appendix A
  の `loss: Tensor` は、E0 のフィクスチャでは Tensor Runtime を配線せず
  スカラー値で代用した。Entity の propose-validate-commit 機構自体は
  値の型に依存しないため、これで仕様が要求する遷移メカニクスの検証は
  成立する。実際の Tensor 値との接続は Phase E1（Runtime 配線）で行う。

---

### Phase E1 — Surface Model v0.1

**目的**: `ru:` / `rus:` / `ruo:` / `derive:` / `<-` を有効化する。

#### E1-1: Parser

`_parse_body`（[parser.py:297](frontend/language_surface/parser.py:297)）の
ディスパッチに分岐を追加する。既存の `line.startswith(...)` チェインと同じ形式。

```
elif re.match(r"^(ru|rus|ruo|derive)\s*:", line):
    nodes.append(_parse_entity_declaration(cursor, context=context))
elif re.match(r"^[A-Za-z_]\w*\s*<-\s*", line):
    nodes.append(_parse_state_transition(cursor, context=context))
```

- `rus:` / `ruo:` は `{` で終わる場合にブロック本体を再帰解析する
  （`_parse_body` と同型の `_parse_entity_members`）。
- `ru:` / `derive:` は `_collect_simple_statement` を用いる
  （F2-1 の演算子継続がここで効く）。
- **文脈依存キーワード**（ADR-106）: `ru` / `rus` / `ruo` / `derive` は
  `lexer.py` の `KEYWORDS` に**追加しない**。`^<word>\s*:` の位置でのみ
  キーワードとして扱う。これにより `let ru = 1` のような既存コードが壊れない。
  実測でリポジトリ内 `.rsn` に該当識別子の使用は 0 件だが、
  外部プロジェクトの互換性のため文脈依存とする。
- 既存の invalid fixture
  [frontend/parser_fixtures/invalid/unknown_keyword.rsn](frontend/parser_fixtures/invalid/unknown_keyword.rsn)
  の `derive Mammal`（コロンなし）は引き続き invalid のまま（影響なし）。

#### E1-2: 名前解決と検証

- `resolve_program` が Entity 宣言を `EntityTable` に登録し、
  式中の `IdentifierNode` を `EntityReferenceNode` に昇格させる。
- Shadowing 禁止（仕様 §7.3）: 同一所有スコープ内の同名 Entity は `RE-DECL-001`。
  異なる子 RUS/RUO 内の同名は完全修飾 Canonical ID で区別され、許可される。
- `<-` の検証:
  - 対象が Entity でない → `RE-STATE-001`
  - 対象が `derive` → `RE-STATE-002`
  - 右辺型が宣言型と不適合 → `RE-TYPE-002`
  - Entity Kind の変更を伴う → `RE-TYPE-002`（Kind 不一致として報告）
- Entity への `=` 再代入 → `RE-STATE-003`（新設）
- RUS 包含循環 → `RE-RUS-001`
- 暗黙の RUS→RUO 昇格の試み → `RE-RUO-001`
- 存在しない Entity への Relation → `RE-REL-001`

#### E1-3: 射影

- `project_module` に `metadata.reason_entities` を追加（§3.5 / §3.6）。
- `_project_calculations` に `ReasonStateTransitionNode` の分岐を追加し、
  `semantic.TransitionNode(relation="EntityStateTransition", effect={"entity_transition": {...}})`
  を出力する。
- `execution_plan_for` に `entity_plan` を追加（§3.7）。

#### E1-4: Runtime

- `execute_program` を改修し、**モジュール本体の Entity 宣言を
  `EntityEnvironment` へ登録してから calculation を実行する**（D-7 の解消）。
  併せてモジュールレベル `const` も同経路で解決可能にする
  （既存欠陥の修正。`CHANGELOG.md` 記載対象）。
- `_statements` に `ReasonStateTransitionNode` の分岐を追加し、
  propose → validate → commit を実行する。
- `_expression` の `IdentifierNode` 解決で、`EntityEnvironment` を先に引き、
  なければ従来の `env` を引く。
- `derive` は `EntityEnvironment.read()` 内で on_read 評価する（§3.9）。
- `TensorRuntime.collect` の `visit` に `RUSlot` 分岐を追加（§3.8 / C-5）。

#### E1 受け入れ条件

- 仕様 §15.1 の正常系 8 項目、§15.2 の異常系 8 項目の fixture が揃い、
  すべて期待どおりの結果／診断コードを返す。
- Surface 入力から Runtime 結果まで決定論的に実行できる。
- 仕様 Appendix A が**実行できる**（D-7 の解消の実証）。
- 仕様 Appendix B の Lowering が Reason IR 命令列として再現される。
- 3 回生成で Semantic AST / Reason IR / ExecutionPlan / Canonical Entity ID /
  Transition Log / Artifact Manifest / Runtime Result が byte-identical。
- Entity を含まない既存コードの canonical 成果物が F0 とバイト一致。

**実装時の訂正・確定事項**:

- **§15.1/§15.2 の 8+8 項目は「代表的カバレッジ」として実装した**。
  [surface_model_tests/](surface_model_tests/) は正常系 8・異常系 8
  （実装時に見つかった `RE-LANG-001`/`RE-LANG-002`〈Entity 宣言・`<-` の
  レキシカル文脈違反〉を含めると異常系は実質 8 種）を実装したが、以下は
  **v0.1 の構文的制約により到達不能**なため対象外とした（診断コード自体は
  `frontend/entity/diagnostics.py` に実装済みで、将来 v0.2 で到達可能な
  構文が追加された時点でそのまま機能する）。
  - `RE-RUS-001`（RUS 包含循環）: `rus:` の本体は字句的入れ子でのみ構成され、
    名前参照による包含を許さないため、循環そのものを Surface 構文で
    表現できない（F2/E0 で発見した「単一パス登録では多ノード循環に
    到達しない」という制約が、ここでは構文レベルでさらに強く効く）。
  - `RE-RUO-001`（暗黙の RUS→RUO 昇格）: 自動昇格を行うコードパスが
    どこにも存在しない（意図的に実装していない）ため、発生しようがない。
  - `RE-REL-001`（存在しない Entity への Relation）: v0.1 は §10 Q6 の
    決定どおり RUS/RUO メンバ包含からの暗黙 PartOf Relation のみを
    生成し、明示的な Relation 宣言構文（存在しない Entity を参照しうる
    唯一の経路）は v0.2 以降。
  - `RE-LOWER-001`（決定論的に Lowering できない構文）: v0.1 の Surface
    構文には非決定的な構成要素が存在しない。
- **Semantic AST の宣言型を増やさない（ADR-102）という決定は完全に守られた**。
  `ReasonEntityDeclarationNode`/`ReasonStateTransitionNode` は
  `frontend.ast`（Semantic AST）に一切追加していない。Entity 情報はすべて
  `semantic.MetadataNode(key="reason_entities")` 経由で運ばれる。
- **`EntityReferenceNode`（§3.4 の当初案）は実装しなかった**。Entity への
  参照は他の宣言型（Concept/Object/Goal 等）と同じく、`IdentifierNode` の
  ままシンボルテーブル（`symbols` dict）でルックアップする方式に統一した。
  これは既存コードの確立された慣用と一致しており、AST に新しいノード種別を
  増やさずに済む。
- **Runtime 配線は ContextVar を用いた**（§3.8 の設計どおり、`_CURRENT_SOURCE_LINE`
  と同じパターン）。`_statements`/`_expression`/`_loop`/`_while_loop` など
  46 箇所の相互再帰呼出しすべてに新しい引数を追加するのではなく、
  実行中の `EntityEnvironment` を `ContextVar` で保持する設計とした。
  1 モジュールの処理単位で `set`/`reset` する。
- **Runtime 側の `derive:` 依存関係計算に実装漏れがあった（発見・修正済み）**。
  当初、`integrated_computation_runtime.py` 側の Entity 宣言ビルダーが
  `EntityRecord.dependencies` を設定し忘れており、Derived Entity の
  on-read メモ化キー（依存 revision のタプル）が常に空タプルのままになる
  ため**キャッシュが一切無効化されず**、`while training_active { ... }`
  が終了しない実バグとして顕在化した（`LoopLimitError`）。
  `frontend/language_surface/integration.py` の
  `_expression_identifiers` を再利用して依存関係を計算するよう修正し、
  Appendix A が正しく 5 回で終了することを確認した。この経緯は
  「オンリード評価＋依存 revision メモ化」（ADR-104）という設計が
  正しくても、**2 箇所（コンパイル時射影とランタイム）に同じロジックを
  複製実装すると片方が漏れるリスクがある**という教訓として記録する。
- **`declared_type`/`value_type` のラベル語彙の不一致を発見・統一した**。
  `frontend/language_surface/integration.py` の既存 `_type_label()` は
  小文字ラベル（"float" 等）を返すが、`frontend/entity/slot.py` の
  `_LABEL_PYTHON_TYPES`（E0 で実装済み）は大文字始まりラベル
  （"Float" 等 = `PrimitiveKind` の enum 値そのもの）を期待していた。
  この不一致は当初のコンパイル時実装ではエラーにならず**型検査が
  静かに無効化される**形で潜在化しうる状態だった。
  `frontend/language_surface/nodes.py` に `entity_value_type_label()`
  （`PrimitiveKind` の enum 値をそのまま返す）を新設し、コンパイル時
  射影・Runtime の両方でこれに統一した。
- **`TensorRuntime.collect` の `RUSlot` 対応は設計どおり実装**（§3.8/C-5）。
  `frontend/entity/slot.py` に `EntityEnvironment.all_slots()` を追加し、
  `runtime.collect(calculations, scope.environment.all_slots())` として
  呼び出す形にした。`frontend/tensor/runtime.py` が
  `frontend.entity.slot.RUSlot` を import する一方向の依存になり、
  循環インポートは発生しない（実行時に確認済み）。
- **ExecutionPlan スキーマの改訂は ADR-109 どおり実施**。
  `schemas/execution_plan.schema.json` に `entity_plan`（新規 `$defs`）
  および `reason_object_plan`/`vision_plan`（型のみ、既存の潜在的不整合の
  解消）を追加した。

---

### Phase E2 — 回帰・性能検証モデル統合

**目的**: Tensor 主体の実モデルで実用性・決定論・性能を評価する。

**前提**: §2.2 のとおり RS-DT-JP-GREET-001 の取り込みが必要。

初期移行対象（仕様 §13）:

| 対象 | 移行前 | 移行後 |
|---|---|---|
| learning rate | `let learning_rate = 0.01` | `ru: learning_rate: float = 0.01` |
| current step | `let step = 0` / `step = step + 1` | `ru: current_step: int = 0` / `current_step <- current_step + 1` |
| loss | `let loss = ...` | `ru: loss: Tensor = ...` / `loss <- TrainStep(...)` |
| Relation Channel 構成 | 個別 `let` | `rus: greeting_relation { ru: ... }` |
| Reason Relation Matrix | Tensor のみ | RUS からの Projection として表現（仕様 §11） |

**受け入れ条件**:
- 移行前後で同一 seed の loss curve、予測結果、最終 `.rstensor` チェックポイントの
  SHA-256 が一致する。
- §7 の性能測定結果が保存される。

**実装時の訂正・確定事項（§2.2 Q2 の解決）**:

RS-DT-JP-GREET-001 は F0 の時点で確認したとおり本リポジトリに存在しない。
§2.2 Q2 の既定方針（「取り込まれない場合、代替の Tensor 主体回帰モデルで
実施し、仕様 §18 の該当条件を未達として明示報告する」）に従い、以下の
代替検証を実施した。

- **代替モデル**: `let`/再代入で書いた 8 ステップの Tensor 学習ループ
  （`tensor.matmul` → `tensor.relu` → `tensor.subtract` → `tensor.power` →
  `tensor.mean`(loss) → `tensor.grad` → パラメータ更新）と、仕様 §13 の
  移行表（learning rate / current step / loss）どおりに
  `ru:`/`derive:`/`<-` へ書き換えた同一計算の 2 版を用意し比較した。
  テストは [entity_migration_regression_tests/test_phase_e2_regression_performance.py](entity_migration_regression_tests/test_phase_e2_regression_performance.py)。
- **移行等価性**: 8 ステップ全ての `tensor.mean`（loss）トレース出力と
  最終チェックポイント（更新後の重み）が、`let` 版と `ru:` 版で
  **完全一致**することを確認した。RS-DT-JP-GREET-001 固有の基準
  （既存の外部チェックポイントとの一致）はモデル不在のため適用対象外。
- **性能測定**（§7、結果は
  [artifacts/reason_entity/e2/performance_report.json](artifacts/reason_entity/e2/performance_report.json)）:

  | 指標 | 測定値 | 目標 | 判定 |
  |---|---|---|---|
  | Entity 非使用コードのコンパイルオーバーヘッド | -3.2%（F0 ベースラインと同一 14 fixture を再計測） | 5% 以内 | **達成** |
  | RU Slot 使用コードの実行時オーバーヘッド | 9.7% | 20% 以内 | **達成** |
  | Entity 使用コードのコンパイルオーバーヘッド | 4.5% | （目標値なし、参考値） | — |

- **本 Phase で実際にバグを発見・修正した**:
  `frontend/integrated_computation_runtime.py` の `_statements` 内、
  文単位で呼ばれる `runtime.collect(env)`（ループ内の毎文で実行される、
  C-5 で最初に指摘したホットスポットそのもの）が、E1 実装時には
  **`execute_program` 内の 2 箇所にしか** `RUSlot` 対応
  （`scope.environment.all_slots()` を追加ルートとして渡す処理）を
  施していなかった。`_statements` 自身が持つ 3 箇所目の `collect` 呼出しは
  対応漏れのままで、Entity が保持する Tensor（学習ループ内で更新され続ける
  `ru: weight` 等）が **ループ実行中に誤って解放される**実バグとして
  顕在化した（`TSF-018 invalid Tensor value reference`）。
  `_statements` 内で `_CURRENT_ENTITY_SCOPE` を参照し、同様に
  `all_slots()` を追加ルートとして渡すよう修正した。
  **これはまさに本 Phase が検出を意図した種類の回帰**であり、
  「Tensor 主体の実モデルで実用性を評価する」という E2 の目的が
  代替モデルであっても実質的に機能したことの実証でもある。

---

## 5. 診断設計

仕様 §14 の 11 コードに加え、実装上必要な 6 コードを提案する。

| Code | 分類 | 内容 | 出典 |
|---|---|---|---|
| `RE-DECL-001` | Semantic | 同一スコープの Entity 再宣言 | 仕様 §14 |
| `RE-TYPE-001` | Semantic | 初期値型不一致 | 仕様 §14 |
| `RE-TYPE-002` | Semantic | 遷移値型不一致（Kind 不一致を含む） | 仕様 §14 |
| `RE-STATE-001` | Semantic | 未初期化 Entity への遷移 | 仕様 §14 |
| `RE-STATE-002` | Semantic | Derived Entity への直接遷移 | 仕様 §14 |
| **`RE-STATE-003`** | Semantic | **Entity への `=` 再代入（`<-` を使用すべき）** | **本設計で追加**（仕様 §16.2 の実装に必須） |
| `RE-ID-001` | Semantic | Canonical ID 競合 | 仕様 §14 |
| `RE-OWNER-001` | Semantic | 不正な所有境界参照 | 仕様 §14 |
| `RE-RUS-001` | Semantic | RUS 包含循環 | 仕様 §14 |
| `RE-RUO-001` | Semantic | 暗黙の RUS→RUO 昇格 | 仕様 §14 |
| `RE-REL-001` | Semantic | 存在しない Entity への Relation | 仕様 §14 |
| `RE-LOWER-001` | Semantic | 決定論的に Lowering できない構文 | 仕様 §14 |
| **`RE-DERIVE-001`** | Semantic | **Derived Entity の循環依存** | **本設計で追加**（§3.9） |
| **`RE-DERIVE-002`** | Semantic | **Derived Entity 宣言に評価器（evaluator）が無い** | **Phase E0 実装時に追加**（`frontend/entity/slot.py`。Surface 接続前の内部 API 制約） |
| **`RE-RUO-002`** | Semantic | **RUO-U1 投影が RUO のネストを含む Entity 構成を拒否** | **Phase E0 実装時に追加**（`frontend/entity/model.py`。§10 Q4/Q5 に伴う投影境界） |
| **`TYPE-020`** | Type | **関数引数の型注釈が必要（推論不能）** | **本設計で追加**（F1-1） |
| **`TYPE-021`** | Type | **戻り値型が経路間で不一致** | **本設計で追加**（F1-2） |
| ~~`TYPE-022`~~ | Type | ~~`tensor.to_array` の結果型に注釈が必要~~ | **未実装**（F1-3 実装時に、注釈要求ではなく既定値フォールバックへ縮小） |
| **`FN-012`** | Function | **`float()`/`int()` の引数個数不一致** | **本設計で追加**（F1-4、実装時に追加） |
| **`FN-013`** | Function | **`float()`/`int()` の引数型が数値でない** | **本設計で追加**（F1-4、実装時に追加） |

すべての `RE-*` 診断は、仕様 §14 の要求に従い次を含める:

- Source Span（`SourceSpanNode` を Surface ノードが保持する）
- Entity 名（素の識別子）と Canonical ID
- 推定型 / 期待型（型系診断の場合）
- 修正候補（`DiagnosticFix`、可能な範囲で）

`RE` プレフィックスは `CODE_CATEGORY_PREFIXES` で `"Semantic"` へ写像する（F2-4）。
`DIAGNOSTIC_CODE_PATTERN` は `RE-DECL-001` 形式を既に受理する（実測確認済み）。

---

## 6. 決定論設計

仕様 §3.3 / §8.5 / §15.4 に対応する。

| 不変条件 | 実装 |
|---|---|
| Canonical ID にホスト固有情報を含めない | `identity.py` は `package` / `module` / `owner path` / `identifier` / `kind` のみを入力に取る。ファイルパス・時刻・アドレスを引数に持たない（型で保証） |
| 配列の正規順序 | `entities` / `relations` は canonical_id 昇順。`instructions` は宣言順・文順（意味的順序のため再配置しない） |
| JSON 正規化 | `canonicalize()`（NFC + キーソート + 非有限値拒否）を再利用 |
| 浮動小数点 | 初期値・遷移値の JSON 出力は既存 `to_json_value` に従う。非有限値は `canonicalize()` が拒否する |
| Slot ID | 実行内の単調増加カウンタ。`id()` やアドレスを使わない |
| 生成時刻 | `DETERMINISTIC_GENERATED_AT` を継承 |

**検証**: 仕様 §15.4 のとおり、各正規 fixture を 3 回生成し
Semantic AST / Reason IR / ExecutionPlan / Canonical Entity ID /
Transition Log / Artifact Manifest / Runtime Result を比較する。
実装は `reason_entity_tests/test_determinism.py` に置く。

---

## 7. 性能設計

仕様 §9.4 の目標値と §15.5 の測定分離に対応する。

### 7.1 測定項目

| 指標 | 測定方法 |
|---|---|
| Parser / Semantic Analysis 時間 | `parse()` / `project_program()` の壁時計時間 |
| Lowering 時間 | `compile_program()` |
| RU Slot 読取・遷移時間 | マイクロベンチ（10^6 回の read / transition） |
| 完全 Entity Materialization 時間 | 同上（Materialize 1 回あたり） |
| ReasonRelation 追加時間 | 同上 |
| Tensor 主体ワークロードへの追加オーバーヘッド | Phase E2 モデルの総実行時間 |

### 7.2 目標値（仕様 §9.4）

| 対象 | 目標 |
|---|---|
| Entity を使用しない既存コード | 5% 以内 |
| 一時 RU Slot を使用するコード | 同等の `let`／代入処理比で 20% 以内 |
| 完全 Materialization | 別指標として明示（目標値なし） |

### 7.3 既知のホットスポットと方針

C-5 で確認したとおり、`runtime.collect(env)` は**文単位**で呼ばれ、
環境全体をグラフ走査する。Entity 導入で環境が大きくなると、
この走査コストが線形に増える。

**v0.1 の方針**:
1. まず**測定する**。F0 の `performance_baseline.json` と E1 後を比較する。
2. 目標未達の場合のみ、`collect` の呼出頻度削減を検討する
   （Tensor を生成しうる文の後だけ呼ぶ、など）。
3. **`collect` の意味論を変える最適化は v0.1 では行わない。**
   仕様 §12.3 のとおり、性能修正は Surface 構文の意味仕様と分離して追跡する。
4. 目標未達の場合、仕様 §9.4 の指示どおり**機能適合と性能適合を分けて報告する**。

Rust Tensor Runtime / GPU Runtime は仕様 ADR-007 に従い本 v0.1 の完了条件に含めない。

---

## 8. 互換性設計

### 8.1 互換性影響の一覧

| 変更 | 影響 | 緩和 |
|---|---|---|
| F1-1 引数型注釈要求 | 推論不能な注釈なし引数を持つ既存コードが新たにエラー | 実装時に全数計測。影響 fixture は注釈追加で移行。`CHANGELOG.md` 記載 |
| F1-2 戻り値型推論 | 型が厳格化される方向。経路間不一致が新たにエラー | 同上 |
| F1-3 `to_array` 型 | これまで通っていた誤用（Tensor として扱う）がエラー化。逆に添字アクセスが可能になる | Golden 更新 |
| F1-4 未知関数の静的検出 | 実行時エラーだったものが静的エラーになる（改善方向） | 影響なしと想定。実装時に計測 |
| F1-5 `/` の型 | `let n: int = a / b` が新たにエラー | **実測: `.rsn` コーパスに `/` 使用 0 件**。影響極小 |
| F2-1 演算子継続 | 行末が演算子で終わる既存プログラムのみ影響 | 既存 Surface AST Golden のバイト一致で検証 |
| E1 `entity_plan` 追加 | Entity を含むプログラムのみ ExecutionPlan が変化 | Entity 非使用時はバイト不変 |
| E1 ExecutionPlan スキーマ拡張 | `reason_object_plan` / `vision_plan` が検証を通るようになる（既存バグ修正） | `CHANGELOG.md` + Golden 更新（AP-010） |
| E1 モジュールレベル束縛 | 従来 `unknown runtime name` だったコードが動作する（既存バグ修正） | 同上 |

### 8.2 維持する既存仕様（仕様 §12.2）

以下は**変更しない**:

- `tensor.grad` の対象に `tensor.parameter(...)` を要求する規則
- `tensor.matmul` の rank-2 制約
- 現行 Tensor 成果物形式（`.rstensor`）
- 既存 ReasonUnit / RUO の Canonical Identity
- `reason_object` / RUO-N2 構文（削除しない。`ruo:` は**追加**であり置換ではない）
- `let` と通常再代入（仕様 §16.1 / §16.2）

### 8.3 移行支援（仕様 §16.4）

v0.1 では自動変換を提供しない。将来の診断支援候補として記録する:
`let` → `ru:` 候補提示、再代入 → `<-` 候補提示、複合 RU → `rus:` 候補提示、
`reason_object` → `ruo:` 候補提示。

---

## 9. 設計判断記録（ADR）

仕様の ADR-001〜007 は前提として受け入れる。本設計で新たに確定した判断を記す。

### ADR-101 — Reason Entity の論理モデルは RUO-U1 を再利用する

- **Decision**: 採用。
- **Reason**: [toolchain/reasonunit_object/model.py](toolchain/reasonunit_object/model.py)
  が Identity / State / Relation / Evidence / Constraint / Revision / Transaction /
  Projection / Lifecycle の語彙と正規化・ダイジェスト機構を既に持つ。
  第二のモデルを作ると RUO 互換性（仕様 §12.2）を維持できない。
- **Consequence**: Canonical ID は `ruo:unit:` / `ruo:object:` プレフィックスに従う。

### ADR-102 — Semantic AST の宣言型を増やさない

- **Decision**: 採用。Entity は `MetadataNode` として射影する。
- **Reason**: `frontend/ast/nodes.py` の 6 種は `from_json_value` /
  `lowering.py` / `validator.py` / `schemas/ast.schema.json` /
  5 言語の DTO バインディング（`docs/specifications/Common_DTO_Specification_v0.1.md`）に
  横断的に影響する。Entity 導入と DTO 破壊的変更の同時実施は
  仕様 §3.7 Staged Compatibility に反する。
- **Consequence**: Entity 情報は `metadata` 経由。専用ノード化は v0.2 以降の課題。
- **Alternative rejected**: `EntityNode` を Semantic AST に追加 →
  DTO 5 言語の同時改訂が必要で、Phase 分離が崩れる。

### ADR-103 — Reason IR は `metadata.reason_entities` に格納する

- **Decision**: 採用。`reason-ir/0.1` のルートスキーマは変更しない。
- **Reason**: `reason_ir.schema.json` ルートは `additionalProperties: false`。
  ルート追加は `reason-ir/0.2` への版上げを意味し、ABI 互換性
  （`docs/specifications/ReasonScript_ABI_Specification_v0.1.md`）に波及する。
  既存の `reason_object_bindings` / `vision_execution_plan` / `function_ir` も
  すべて `metadata` 経由であり、一貫している。
- **Consequence**: Entity IR は `schemas/reason_entity.schema.json` で個別に検証する。

### ADR-104 — Derived Entity は on_read + 依存 revision メモ化で評価する

- **Decision**: 採用。
- **Reason**: 仕様 Appendix A の `while training_active` が正しく終了するには
  ループごとの再評価が必要。on_read は評価点が読み取り位置で一意に定まり、
  決定論の証明が容易い。依存 revision をメモ化キーにすることで、
  同一 revision 下の複数回読み取りが同一値を返すことを保証する。
- **Consequence**: ExecutionPlan の `derived_evaluation[].strategy` に必ず記録する。
  循環依存は `RE-DERIVE-001` で宣言時に拒否する。

### ADR-105 — 診断カテゴリ `ReasonEntity` を新設せず `Semantic` へ写像する

- **Decision**: v0.1 では採用。専用カテゴリは v0.2 の課題とする。
- **Reason**: [toolchain/diagnostics.py:277](toolchain/diagnostics.py:277) は
  全カテゴリのゼロ初期化辞書を `diagnostics_summary.json` に出力する。
  新カテゴリは、Entity を一切使わない既存プロジェクトの正規成果物まで
  バイト変化させる。仕様 §2.2 の後方互換要求に反する。
- **Consequence**: `RE-*` は `Semantic` カテゴリで報告される。コード自体は
  一意なので識別性は失われない。

### ADR-106 — Entity キーワードは文脈依存キーワードとする

- **Decision**: 採用。`ru` / `rus` / `ruo` / `derive` を
  `lexer.py` の `KEYWORDS` に追加せず、`^<word>\s*:` の位置でのみ認識する。
- **Reason**: 予約語化は `let ru = 1` のような既存コードを破壊する。
  実測でリポジトリ内 `.rsn` に該当識別子の使用は 0 件だが、
  外部プロジェクトへの後方互換のため文脈依存とする。
- **Consequence**: `ru` を変数名として使い続けられる。

### ADR-107 — `<-` は文頭パターンでのみ認識し、式中の演算子にしない

- **Decision**: 採用。
- **Reason**: `a < -1` との語彙的曖昧性を構造的に排除する。
  仕様 §5.3 は `<-` を「状態遷移」として文レベルで定義しており、
  式中での使用は要求していない。
- **Consequence**: `x <- y <- z` のような連鎖は構文エラーとなる（意図的）。

### ADR-108 — `Int / Int` の静的型を Float に変更する（実行時は不変）

- **Decision**: 採用。
- **Reason**: 実行時は既に真の除算（`7/2 == 3.5`）である。静的型のみを
  実行時に合わせることで、**数値結果への影響がゼロ**のまま
  仕様 §6.3「`/` の結果型は実行時挙動と静的型で一致しなければならない」を満たす。
  逆方向（実行時を整数除算に）は仕様 §2.2 の数値不変要求に抵触する。
- **Consequence**: 整数除算は `int(a / b)` で表現する。
  実測で `.rsn` コーパスへの影響は 0 件。

### ADR-109 — ExecutionPlan スキーマの既存不整合を Entity 導入と同時に解消する

- **Decision**: 採用。`execution_plan.schema.json` に
  `reason_object_plan` / `vision_plan` / `entity_plan` を名前付き
  オプショナルプロパティとして追加し、`additionalProperties: false` は維持する。
- **Reason**: 実測で `vision_plan` 付き ExecutionPlan はスキーマ検証に失敗する
  （`$: unknown field vision_plan`）。Entity 導入で `entity_plan` を追加する際に
  同じ壁に当たるため、既存の潜在不整合ごと解消するのが最小コストである。
- **Consequence**: 互換性変更として `CHANGELOG.md` に記録する（AP-010）。

---

## 10. 未決事項

実装着手前に確認が必要な項目。

| # | 事項 | 影響 Phase | 既定の扱い |
|---|---|---|---|
| Q1 | v0.5.4.7〜v0.5.4.9 が別ラインに存在するか。存在する場合、F0 の前にマージするか | F0 | 存在しないものとして v0.5.4.6 を凍結する（§2.1） |
| Q2 | RS-DT-JP-GREET-001 一式（`.rsn`、固定 seed 構成、期待 loss curve、`.rstensor`）を F0 でリポジトリに取り込むか | E2 | 取り込まれない場合、代替 Tensor 回帰モデルで実施し、仕様 §18 の該当条件を未達として明示報告する（§2.2） |
| Q3 | F1-1 / F1-2 / F1-4 の型厳格化で新たにエラーになる既存コードが見つかった場合、注釈追加で移行するか、警告に留めるか | F1 | 既定はエラー（仕様 §6.2「Unknown のまま残してはならない」）。実装時に影響数を報告して判断を仰ぐ |
| Q4 | `ruo:` の Persistence を v0.1 で実際に永続化まで実装するか、宣言のみに留めるか | E1 | 仕様 §2.3 が「自動永続化」を非目標としているため、**宣言のみ**とする |
| Q5 | RUS→RUO の明示変換構文（仕様 §10.3）の具体形。仕様は要求項目のみ定義し構文を規定していない | E1 | v0.1 では**変換構文を提供せず**、`ruo:` による直接宣言のみとする。変換構文は「RUS→RUO Explicit Promotion Profile v0.1」（仕様 Appendix C）へ委ねる |
| Q6 | Relation 宣言構文（仕様 Appendix C が v0.2 とする）を v0.1 でどこまで扱うか | E1 | `rus:` のメンバ包含から**暗黙に生成される PartOf Relation のみ**を扱う。明示 Relation 宣言構文は v0.2 |

---

## 11. 推奨着手順序（仕様 §19 の具体化）

1. **Q1 / Q2 の確認**（§10）。特に Q2 は E2 の受け入れ条件を左右する。
2. **Phase F0**: `toolchain/reason_entity_baseline/` 実装 + 凍結 + 3 回生成検証。
   プロダクションコード変更なし。
3. **Phase F1**: F1-1 → F1-2 → F1-3 → F1-4 → F1-5 の順。
   各サブフェーズごとに `tensor_numeric_baseline.json` を再生成し diff 空を確認。
4. **Phase F2**: F2-1（演算子継続）→ F2-2（`<-` 語彙化）→ F2-3（Entity 名前解決基盤）
   → F2-4（診断基盤）。各段で Surface AST Golden のバイト一致を確認。
5. **Phase E0**: `frontend/entity/` 完成。Parser 非依存の fixture テストで検証。
6. **Phase E1**: Parser → 名前解決／検証 → 射影 → Runtime の順。
   Appendix A の実行と Appendix B の Lowering 再現を受け入れ条件とする。
7. **Phase E2**: 回帰・性能検証モデルの移行と測定。

各 Phase の完了時に `reason ci` を実行し、`agent_report.json` を更新する
（`AGENTS.md` の Agent Development Protocol に従う）。

---

## 12. 完了判定（仕様 §18 への対応）

| 仕様 §18 の条件 | 本設計での検証手段 |
|---|---|
| Phase F0〜E2 の受け入れ条件がすべて成功 | 各 Phase の受け入れ条件（§4） |
| 既存の必須回帰テストがすべて成功 | `reason ci` + `python3 -m pytest -q`（基準: 2005 passed / 6 skipped） |
| `ru:` / `rus:` / `ruo:` / `derive:` / `<-` の正常・異常 fixture が揃っている | `reason_entity_tests/`（仕様 §15.1 / §15.2 の全 16 項目） |
| Canonical 成果物の 3 回生成が byte-identical | `reason_entity_tests/test_determinism.py`（§6） |
| RS-DT-JP-GREET-001 の固定 seed 結果が移行前後で一致 | Phase E2（Q2 に依存） |
| 性能測定結果が保存され、目標未達項目も明示されている | `performance_baseline.json` + Phase E2 レポート（§7） |
| 既知制約が limitations 成果物へ記録されている | `artifacts/reason_entity/limitations.json` |
| RUS から RUO への暗黙昇格が存在しない | `RE-RUO-001` の異常系 fixture |
| Reason Entity の状態遷移が通常再代入へ意味消去されていない | `RE-STATE-003` の異常系 fixture + Reason IR に `ProposeEntityTransition` /
`ValidateEntityTransition` / `CommitEntityTransition` の 3 命令が出力されることの検証 |

---

## 付録 A — 調査で実行した再現コマンド

```bash
python3 -m pytest -q
```

型・構文欠陥の再現（D-1〜D-7）は
`toolchain.pipeline.validate_source` と
`frontend.integrated_computation_runtime.execute_program` を直接呼び出して確認した。
再現スクリプトは Phase F0 で `reason_entity_tests/test_baseline_defects.py` として
恒久化し、F1 完了時に「修正済み」を検証する回帰テストへ転用する。

## 付録 B — 仕様の各要求と本設計の対応表

| 仕様条項 | 本設計での対応 |
|---|---|
| §2.1 機能目標 7 項目 | §3.2 / §3.4 / §3.5 / §3.6 / §3.7 / §3.8 |
| §2.2 品質目標（byte-identical / 後方互換 / 数値不変 / 静的診断） | §6 / §8 / ADR-108 / §5 |
| §3.1〜3.7 設計原則 | §3.2（Entity First）/ §3.10（Explicit Transition）/ §6（Deterministic Lowering）/ ADR-105・§5 `RE-RUO-001`（Explicit Promotion）/ §3.8（Semantic Preservation）/ §3.8 RU Slot（Pay for Semantics Used）/ §4 Phase 構成（Staged Compatibility） |
| §4 用語と Entity 分類 | §3.2 |
| §5 Surface 構文 | §3.4 / §4 Phase E1-1 |
| §6 型システム要件 | §4 Phase F1 |
| §7 名前解決と Canonical ID | §3.3 / §4 Phase F2-3 / E1-2 |
| §8 Compiler Pipeline | §3.4 / §3.5 / §3.6 / §3.7 |
| §9 Runtime Model | §3.8 / §7 |
| §10 RU・RUS・RUO 間の規則 | §3.2 / Q5 |
| §11 ReasonRelation 統合 | §3.6 `relations` / Q6 |
| §12 基盤修正要件 | §4 Phase F1 / F2 |
| §13 実装 Phase | §4 |
| §14 診断要件 | §5 |
| §15 検証計画 | §4 各受け入れ条件 / §6 / §7 |
| §16 互換性と移行 | §8 |
| §17 セキュリティ・安全性・原子性 | §3.8（propose-validate-commit）/ §3.3（ID にホスト固有情報を含めない）/ Q4 |
| §18 完了判定 | §12 |
| §19 推奨着手順序 | §11 |
| §20 ADR-001〜007 | 前提として受け入れ。§9 で ADR-101〜109 を追加 |
