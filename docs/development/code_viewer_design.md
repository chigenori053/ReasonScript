# ReasonScript CodeViewer 設計案 v0.1

対象コマンド: `reason view`
ステータス: **VALIDATED**（`AGENTS.md` のタスク状態に準拠。P1〜P4実装済み、`reason ci` 全通過）
15章の4論点は解決済み。決定内容を本文へ反映済み。

## 実装状況（§14 フェーズ表に対応）

| フェーズ | 状態 |
|---|---|
| P1（`model.py`/`projection.py`/`anchors.py`、`--json`） | ✅ 完了 |
| P2（`stages.py`/`render.py`、`--plain`） | ✅ 完了 |
| P3（`tui.py`/`theme.py`、対話TUI基本操作） | ✅ 完了 |
| P4（検索`/`・`y`コピー・診断ペイン`d`・最小サイズ縮退CV-004） | ✅ 完了 |
| P5（ドキュメント） | ✅ 完了（本ファイル・CLIリファレンス・CHANGELOG・roadmap） |

実装は `toolchain/code_viewer/`（`model.py` / `anchors.py` / `stages.py` /
`projection.py` / `render.py` / `theme.py` / `tui.py` / `serialize.py`）と
`toolchain/code_viewer_cmd.py`。テストは `code_viewer_phase1_tests/`
（65件）、ゴールデンは `golden/code_viewer/`、スキーマは
`schemas/code_viewer_document.schema.json`。

未着手・別タスク:
- §16 の AST スパン導入（S1〜S4）— S1（`ReasonObjectBindingNode.source_span`
  の物理行修正）は別セッションで着手済み。CodeViewer 自体は字句索引
  （`anchors.py`）で完結しており、この作業の完了を待たない。

---

## 1. 目的とスコープ

`.rsn` ソースと、それがコンパイルされていく4段階の中間表現を **1画面で並べて閲覧する**
ターミナル TUI ツール。ReasonScript の中核価値である「推論過程が追跡可能」を、
JSON を手で開かずに体感できるようにするのが狙い。

閲覧対象（決定済み）:

| ペイン | 内容 | 生成元 |
|---|---|---|
| Source | `.rsn` ソース（シンタックスハイライト + 行番号） | ファイル |
| Surface AST | `ProgramNode` ツリー | `frontend.language_surface.parser.parse` |
| Semantic AST | `semantic.ModuleNode` ツリー | `integration.project_program` |
| Reason IR | `reason-ir/0.1` JSON | `integration.compile_program` |
| ExecutionPlan | `selected_steps` / `alternative_paths` | `integration.execution_plan_for` |

**スコープ外（v0.1 では作らない）**: 編集機能、実行機能、`.ruo` / vision / visualization
アーティファクトの閲覧、LSP サーバとの通信。すべて後続フェーズで検討。

---

## 2. 調査で判明した前提（設計を規定する制約）

実装前に確認した、設計を左右する4点。

### 2.1 ✅ 4段階すべてがライブラリとして到達可能

追加のコンパイラ改修なしに、既存 API だけで全ステージを取得できる:

```python
from toolchain.pipeline import compile_source              # Source → Surface AST → Reason IR
from frontend.language_surface.integration import (
    project_program,      # Surface AST → Semantic AST
    execution_plan_for,   # Reason IR → ExecutionPlan     (integration.py:2664)
)
```

CodeViewer は**新しいコンパイル経路を一切作らない**。既存パイプラインの読み取り専用
コンシューマに徹する。これは「生成物は公式コマンド経由でのみ生成する」という
`AGENTS.md` のアーティファクト方針とも整合する。

### 2.2 ❌ Surface AST にソース位置情報が無い ← 最重要の制約

`frontend/language_surface/nodes.py` の109個のノードクラスのうち、
`line` / `column` / `span` を持つのは `SourceSpanNode`（[nodes.py:736](frontend/language_surface/nodes.py:736)）
だけで、これは ReasonObject 節の記録専用。**通常の宣言・式ノードは位置情報を持たない。**

したがって「ソースの15行目の式 ↔ IR のこのノード」という**式レベルの厳密な対応付けは
現状不可能**。設計はこの制約を正面から受け止める必要がある（→ 6章の Anchor 設計）。

> スパン導入は**採用決定済み**（→ 16章）。ただし調査の結果、これは想定より
> 大きな作業（パーサの再構成を伴う）であることが判明したため、
> **CodeViewer v0.1 はスパンに依存させず**、宣言レベル相関で先行させる。
> スパン完成後に Anchor を v2 へ拡張する移行経路を6章に用意する。

### 2.3 ✅ 字句レベルの位置情報はある

`frontend/language_surface/lexer.py` の `SurfaceToken` は `line` / `column` を持つ。
→ **シンタックスハイライトと「宣言名 → 宣言行」の索引作成はこれだけで実現できる。**

### 2.4 ✅ ゴールデン基準線が既に4ステージ揃っている

```
golden/sample001/sample001.ast.json
golden/sample001/sample001.semantic.json
golden/sample001/sample001.reason_ir.json
golden/sample001/sample001.execution.json
```

CodeViewer の4ペインと 1:1 で対応する。検証戦略をここに乗せられる（→ 13章）。

---

## 3. CLI 表面設計

```sh
reason view <source.rsn> [options]
```

| オプション | 既定 | 説明 |
|---|---|---|
| `--stage <name>` | `source` | 起動時に右ペインへ表示する段。`surface` / `semantic` / `ir` / `plan` |
| `--module <name>` | 先頭 | 複数モジュールを含むファイルで対象を限定 |
| `--json` | off | TUI を起動せず、ビューアの内部モデルを JSON で標準出力（CI・エージェント用） |
| `--plain` | 自動 | 非対話のプレーンテキスト出力。非 TTY 時は自動的にこれ |
| `--no-color` | 自動 | `NO_COLOR` 環境変数でも有効化 |
| `--width <n>` | 端末幅 | プレーン出力時の折り返し幅（ゴールデンテストで固定するため） |

`reason` のヘルプ（`toolchain/__main__.py` の `_usage()`）へ1行追加:

```
  view          Browse .rsn source alongside its compiled representations
```

ディスパッチは既存の全コマンドと同じ形にそろえる:

```python
if command == "view":
    from toolchain.code_viewer_cmd import run
    return run(args[1:], project_root)
```

---

## 4. アーキテクチャ（4層）

CodeViewer の設計上いちばん重要な判断は、**curses を最外殻の1ファイルに封じ込める**こと。
これにより本体が端末なしで完全にテスト可能になり、`AGENTS.md` の検証要件を満たせる。

```
┌──────────────────────────────────────────────────────────┐
│ toolchain/code_viewer_cmd.py    ← 薄い CLI アダプタ       │
│   引数解析・TTY 判定・終了コード。既存 *_cmd.py と同形   │
└───────────────┬──────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────┐
│ toolchain/code_viewer/tui.py    ← curses I/O のみ         │
│   Frame を画面へ blit / キー入力を Action へ変換          │
│   ★ ここ以外に curses import を一切置かない               │
└───────────────┬──────────────────────────────────────────┘
                │  ViewerState ──▶ Frame
┌───────────────▼──────────────────────────────────────────┐
│ toolchain/code_viewer/render.py ← 純粋関数                │
│   render(state, width, height) -> Frame                   │
│   Frame = tuple[Line, ...], Line = tuple[Span, ...]       │
│   Span = (text: str, style: StyleRole)                    │
│   ★ 端末不要。80x24 のフレームを文字列比較でテストできる  │
└───────────────┬──────────────────────────────────────────┘
                │  ViewerDocument + カーソル位置
┌───────────────▼──────────────────────────────────────────┐
│ toolchain/code_viewer/projection.py ← 純粋関数            │
│   project(source, path) -> ViewerDocument                 │
│   既存パイプラインを呼び、5段すべてと Anchor 索引を構築   │
│   ★ 決定論的・JSON シリアライズ可能 → ゴールデン対象      │
└───────────────┬──────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────┐
│ toolchain/code_viewer/model.py  ← dataclass のみ、I/O なし │
└──────────────────────────────────────────────────────────┘
```

この分割の見返り:

- `projection` は**入力ファイル → JSON** の純関数なので、`golden/sample001/*.json` と
  直接突き合わせられる。
- `render` は**状態 → 文字列**の純関数なので、レイアウト崩れをゴールデンテストで検出できる。
- `tui` に残るのは curses 呼び出しだけで、ロジックが無いので手動確認で足りる。

---

## 5. データモデル（`model.py`）

```python
SCHEMA = "reasonscript-code-viewer/0.1"

class Stage(str, Enum):
    SOURCE   = "source"
    SURFACE  = "surface"
    SEMANTIC = "semantic"
    IR       = "ir"
    PLAN     = "plan"

@dataclass(frozen=True)
class Anchor:
    """段をまたいで同一の宣言を指す識別子。相関の唯一の単位。"""
    symbol: str            # 例: "Base" （calculation 名 / function 名 / module 名）
    kind: str              # "module" | "calculation" | "function" | "enum" | "struct"
    source_line: int       # 1-origin。字句索引から解決
    source_end_line: int   # ブロック終端（波括弧の対応から算出）

@dataclass(frozen=True)
class StageNode:
    """右ペインに表示される1行分の論理ノード。"""
    node_id: str           # 段内で一意
    depth: int             # ツリー描画のインデント段数
    label: str             # 表示テキスト
    anchor: str | None     # Anchor.symbol。相関に使う。無ければ None
    json_pointer: str      # 例: "/transitions/0/effect" — `y` でコピーする値

@dataclass(frozen=True)
class StageView:
    stage: Stage
    nodes: tuple[StageNode, ...]
    available: bool                    # そのステージまで到達できたか
    diagnostics: tuple[Diagnostic, ...]  # frontend.lsp.Diagnostic を再利用

@dataclass(frozen=True)
class ViewerDocument:
    """projection の出力。これ自体が --json の出力対象。"""
    schema: str
    source_path: str
    source_lines: tuple[str, ...]
    tokens: tuple[TokenSpan, ...]      # ハイライト用（行・列・種別）
    anchors: tuple[Anchor, ...]
    stages: Mapping[Stage, StageView]
    module_names: tuple[str, ...]
    ok: bool

@dataclass(frozen=True)
class ViewerState:
    """render への入力。ユーザ操作で変わるのはここだけ。"""
    document: ViewerDocument
    active_stage: Stage
    cursor_line: int        # 左ペインのカーソル行
    source_scroll: int
    stage_scroll: int
    search_query: str | None
    show_help: bool
```

`Diagnostic` は `frontend/lsp/model.py` の既存 dataclass をそのまま再利用する
（新しい診断型を作らない）。

---

## 6. 段をまたぐ相関 — Anchor 設計 ★設計の核心

2.2 で述べたとおり式レベルの対応付けは不可能。代わりに **「宣言名」を共通キーにした
名前ベース相関**を採る。実データで検証済みの連鎖は次のとおり:

```
ソース             lexer トークン走査で宣言行を索引
  calculation Base            → Anchor(symbol="Base", source_line=2)
       │
       │ 名前一致
       ▼
Semantic AST   TransitionNode(node_id="CalculationDependency-calculation-1",
                              transition_id="Base-1-result")
       │
       ▼
Reason IR      transitions[0].effect.calculation == "Base"
               transitions[0].transition_id      == "Base-1-result"
       │
       │ transition_id 一致
       ▼
ExecutionPlan  selected_steps[0].transition_id == "Base-1-result"
```

つまり **`effect.calculation` と `transition_id` が既に名前を埋め込んでいる**ため、
コンパイラを一切変更せずに4段の相関が成立する。これが本設計が成立する根拠。

### 索引の作り方（`projection.py` 内）

1. `lexer.tokenize(source)` でトークン列を取得。
2. `module` / `calculation` / `function` / `enum` / `struct` キーワードの**直後の
   IDENTIFIER** を宣言名とし、そのトークンの `line` を `source_line` とする。
3. 続く `{` から対応する `}` までを波括弧の深さ計数で追い、`source_end_line` を決める。
4. 各段のノード生成時に、上表の規則で `anchor` フィールドへ宣言名を埋める。

`frontend/lsp/core.py` の `_scan_symbols`（[core.py:190](frontend/lsp/core.py:190)）が
似た走査をしているので、**まず共通化を検討する**（重複実装を避ける）。ただし LSP 側は
LSP の `Symbol` 型を返すため、そのまま流用できるかは実装時に判断する。

### 相関の粒度と、その正直な限界

- **できること**: カーソルが `calculation Base` のブロック内にあるとき、右ペインの
  `Base` 由来ノードを強調表示し、そこへ自動スクロールする（逆方向も同様）。
- **できないこと**: `result = Base * 2` の `Base` という**参照**にカーソルを合わせても、
  それが `Base` 宣言への参照だとは（スパンが無いので）分からない。宣言行単位でしか
  引けない。
- この制限は起動時に警告を出すのではなく、**ヘルプ（`?`）に明記**する。

### Anchor v2 への移行経路（スパン導入後）

16章のスパン導入が完了したら、CodeViewer 側は**加算的な変更だけ**で式レベル相関へ
移行できる。この移行しやすさを保つのが v1 の `Anchor` を「名前 + 行」に絞った理由。

```python
@dataclass(frozen=True)
class Anchor:
    symbol: str
    kind: str
    source_line: int
    source_end_line: int
    # --- v2 で追加（すべて Optional。無ければ v1 と同じ挙動） ---
    source_column: int | None = None
    end_column: int | None = None
    parent: str | None = None      # 参照 → 宣言の解決結果
```

- `render.py` は `source_column` が `None` なら行全体を、値があれば列範囲を強調する
  分岐を入れるだけ。
- `projection.py` は「字句走査による索引」と「AST スパンによる索引」の2実装を持ち、
  スパンが利用可能なノードではそちらを優先する（フォールバック構造）。
- したがって **v1 実装がv2で捨てられることはない**。

---

## 7. 画面設計

### レイアウト（80x24 の例）

```
┌─ examples/v0_5/003_calculation_dependency.rsn ────── module: CalculationDependency ─┐
│                                     │                                              │
│  1  module CalculationDependency {  │  Reason IR            reason-ir/0.1          │
│▸ 2    calculation Base {            │  ─────────────────────────────────────       │
│▸ 3      result = 21                 │   initial_state                              │
│▸ 4    }                             │     state_id: CalculationDependencyStart     │
│  5                                  │   goal                                       │
│  6    calculation Answer {          │     reach_state → Answer.state.result        │
│  7      result = Base * 2           │ ▸ transitions[0]          Base-1-result      │
│  8    }                             │ ▸   relation: ResultTransition               │
│  9  }                               │ ▸   target:   Base.state.result              │
│                                     │ ▸   effect.calculation: Base                 │
│                                     │     transitions[1]        Answer-1-result    │
│                                     │       relation: ResultTransition             │
│                                     │                                              │
├─────────────────────────────────────┴──────────────────────────────────────────────┤
│ [1]Source [2]Surface [3]Semantic [4]IR* [5]Plan   Base → Base-1-result    ?:help q:quit│
└────────────────────────────────────────────────────────────────────────────────────┘
```

- `▸` が相関ハイライト。左の `calculation Base` ブロックと右の対応ノードが**同時に**光る。
- 最下行のステータスバーに、現在の Anchor と対応する `transition_id` を表示する。
- 幅が 60 桁未満の場合は左右分割をやめ、**単一ペイン + `Tab` で段切替**に自動縮退する。

### キーバインド

| キー | 動作 |
|---|---|
| `1`–`5` / `Tab` / `Shift-Tab` | 表示する段を切り替え |
| `j` / `k` / `↓` / `↑` | 左ペインのカーソル移動（右ペインは追従） |
| `Ctrl-d` / `Ctrl-u` | 半画面スクロール |
| `n` / `p` | 次 / 前の**宣言**へジャンプ（Anchor 単位） |
| `Enter` | フォーカスを右ペインへ移す（右ペイン内を独立に移動） |
| `Esc` | フォーカスを左ペインへ戻す |
| `/` → 文字列 → `Enter` | 検索。`n` で次候補（検索モード中のみ意味が変わる） |
| `y` | カーソル位置ノードの JSON ポインタをクリップボードへ（不可なら標準エラーへ出力） |
| `d` | 診断ペインの表示切替 |
| `?` | ヘルプ表示 |
| `q` / `Ctrl-c` | 終了 |

vi 系（`j`/`k`/`/`）を基本にしつつ矢印キーも受ける。既存の `reason` CLI に対話 UI の
前例が無いため、**新しい慣習を作らず一般的な TUI 慣習に寄せる**方針。

---

## 8. シンタックスハイライト

`lexer.SurfaceTokenType` の5種をそのまま色役割に写す。独自トークナイザは作らない。

| SurfaceTokenType | StyleRole | 既定色（8色端末） |
|---|---|---|
| `KEYWORD` | `keyword` | magenta |
| `IDENTIFIER` | `identifier` | 既定色 |
| `NUMBER` | `literal` | cyan |
| `STRING` | `literal` | green |
| `OPERATOR` / `DELIMITER` | `punctuation` | 暗色 |
| （宣言名の IDENTIFIER） | `declaration` | yellow + bold |

色は 8 色 ANSI に限定する。256 色や truecolor は使わない（端末互換性を優先）。
`NO_COLOR` 環境変数または `--no-color` で `StyleRole` をすべて無視し、
ハイライトは反転表示のみで表現する。

---

## 9. 壊れたコードでの挙動 ★重要

**構文エラーのあるファイルでも必ず起動する。** ここを妥協すると「エラーを調べたいのに
ビューアが開かない」という最悪の体験になる。

`projection.project()` は各段を**独立に try で囲み**、失敗した段以降を
`StageView(available=False, diagnostics=(...))` として返す:

| 失敗段 | Source | Surface | Semantic | IR | Plan |
|---|---|---|---|---|---|
| `SurfaceSyntaxError` | ✅ 字句のみで表示 | ⚠️ 診断 | ⚠️ | ⚠️ | ⚠️ |
| `SurfaceValidationError` | ✅ | ✅ | ⚠️ 診断 | ⚠️ | ⚠️ |
| `NamespaceResolutionError` | ✅ | ✅ | ⚠️ 診断 | ⚠️ | ⚠️ |

- Source ペインは**パーサを通さず字句だけ**で描くので、構文エラーでもハイライトが出る。
  （`tokenize` が失敗する未対応文字のケースのみ、無色のプレーンテキストへ縮退）
- 利用不可の段を選ぶと、ノードの代わりに診断メッセージを中央に表示する。
- 既存の `PipelineError.code`（`SyntaxError` / `ValidationError` / `CompilerError`）を
  そのまま診断コードに使い、新しいエラー分類を導入しない。

---

## 10. 非 TTY / `--json` フォールバック

TUI が主用途でも、非対話経路は**必須**。`reason ci` や coding agent がこのコマンドを
呼ぶ可能性があり、そこで curses を起動すると壊れる。

```python
if not sys.stdout.isatty() or "--plain" in args or "--json" in args:
    # curses を import すらしない
```

- `--json`: `ViewerDocument` を JSON で出力。`schema` フィールドは
  `reasonscript-code-viewer/0.1`。**これがゴールデンテストの入力になる。**
- `--plain`: 相関ハイライトを `▸` などの ASCII マーカーで表現した静的テキストを出力。
  `--width` で幅を固定できるので、これもゴールデン対象にできる。

終了コード: `0` = 正常終了、`1` = ファイル不在・引数不正、`2` = パイプライン失敗
（`--json` / `--plain` 時のみ。TUI では診断を表示して 0 で終わる）。

---

## 11. 依存とプラットフォーム

**必須依存はゼロ。** `curses` は macOS / Linux では Python 標準ライブラリ。

`pyproject.toml` は本体に `dependencies` の指定が無く、`matplotlib` すら optional
extra に留めている。この方針を踏襲し、`textual` / `rich` / `prompt_toolkit` は
**採用しない**。

| プラットフォーム | 扱い |
|---|---|
| macOS / Linux | stdlib `curses` で TUI。追加インストール不要 |
| Windows | **Windows 限定 extra `windows-curses` で TUI**（決定事項）。未導入なら `--plain` へ自動縮退 |

### pyproject.toml への追加

環境マーカーを使い、**Windows 以外には一切影響を与えない**形で追加する:

```toml
[project.optional-dependencies]
viewer = ["windows-curses>=2.3; sys_platform == 'win32'"]
full = ["matplotlib>=3.8,<4", "windows-curses>=2.3; sys_platform == 'win32'"]
```

- `sys_platform == 'win32'` マーカーにより、macOS / Linux で `pip install
  'reasonscript[viewer]'` しても **何もインストールされない**（no-op）。
  したがって「実行時依存ゼロ」の実質は維持される。
- `full` にも含め、既存の `[full]` 利用者が Windows で TUI を得られるようにする。

### 縮退時の挙動

Windows で `windows-curses` 未導入のまま `reason view` を叩いた場合:

1. `import curses` を `try` で囲み、`ImportError` を捕捉する。
2. `--plain` 相当の静的出力へ自動縮退し、**終了コードは 0**（失敗にしない）。
3. 標準エラーへ一度だけ案内を出す:

   ```
   note: interactive viewer requires windows-curses on this platform.
         install with: pip install 'reasonscript[viewer]'
         falling back to --plain output.
   ```

この案内は `CV-006`（TUI 利用不可のため縮退）として診断コードに登録し、
`--json` 出力時は `diagnostics` に含める。`docs/installation/windows.md` にも
1節追加する。

---

## 12. ファイル配置

```
toolchain/
  code_viewer_cmd.py              # CLI アダプタ（既存 *_cmd.py と同形）
  code_viewer/
    __init__.py                   # 公開 API: project, render, run_tui
    model.py                      # dataclass 群（I/O なし）
    projection.py                 # .rsn → ViewerDocument（純関数）
    anchors.py                    # 字句走査による Anchor 索引
    stages.py                     # 各段 → StageNode 列への変換
    render.py                     # ViewerState → Frame（純関数）
    theme.py                      # StyleRole → ANSI/curses 属性
    tui.py                        # curses 本体（この1ファイルにのみ curses）

code_viewer_phase1_tests/         # 既存の *_tests/ 命名規約に合わせる
  __init__.py
  test_projection.py
  test_anchors.py
  test_render.py
  test_cli.py

golden/code_viewer/               # ゴールデン基準線
  sample001.viewer.json
  sample001.plain.txt

schemas/
  code_viewer_document.schema.json
```

`schemas/` へ JSON Schema を置くのは、既存の79個のスキーマと同じ扱いにするため
（`--json` 出力を `validate-artifacts` の検証対象にできる）。

---

## 13. 検証戦略（`AGENTS.md` 準拠）

`AGENTS.md` は4段階の検証を必須としている。CodeViewer での具体化:

| 必須検証 | CodeViewer での実施内容 |
|---|---|
| 1. Workspace 検証 | 変更なし（`reason workspace` がそのまま通ること） |
| 2. 診断検証 | 壊れたソース（`examples/v0_5/invalid/*.rsn` の5本）で 9章の縮退表を検証 |
| 3. アーティファクト検証 | `--json` 出力を `code_viewer_document.schema.json` で検証 |
| 4. ゴールデンテスト | 下記 |

### ゴールデンテストの設計

2.4 で確認した既存基準線を活用する:

1. **相関の正当性**: `golden/sample001/sample001.reason_ir.json` と
   `sample001.execution.json` を読み、CodeViewer が算出した Anchor 対応表が
   これらの `transition_id` と完全一致することを検証する。
   → **ビューアの相関ロジックが、公式アーティファクトと同じ結論に達することの証明**になる。
2. **描画の安定性**: `render(state, width=80, height=24)` の Frame を
   `golden/code_viewer/sample001.plain.txt` と文字列比較。レイアウト崩れを検出。
3. **決定論性**: 同一入力で `--json` を2回実行し、バイト単位で一致すること。

### 診断コード

既存の接頭辞（`CI-` / `AP-` / `CE-` / `SVR-`）にならい `CV-` を新設:

- `CV-001`: ソースファイルが存在しない
- `CV-002`: 未知のステージ名
- `CV-003`: 指定モジュールがファイル内に存在しない
- `CV-004`: 端末サイズが最小要件（40x10）未満
- `CV-005`: `--json` 出力がスキーマ検証に失敗
- `CV-006`: TUI が利用できないため `--plain` へ縮退（Windows で `windows-curses` 未導入 等）

---

## 14. 実装フェーズ分割

各フェーズ末尾で `reason ci` が通る状態を保つ。

| フェーズ | 内容 | 完了判定 |
|---|---|---|
| **P1** | `model.py` + `projection.py` + `anchors.py`、`reason view --json` | `--json` がスキーマ検証を通り、相関がゴールデン IR と一致 |
| **P2** | `stages.py` + `render.py`、`reason view --plain` | 80桁プレーン出力がゴールデン一致。**まだ curses 不要** |
| **P3** | `tui.py` + `theme.py`、対話 TUI とキーバインド | 手動確認 + キー入力 → `ViewerState` 遷移の単体テスト |
| **P4** | 検索 / `y` コピー / 診断ペイン / 最小サイズ縮退 | 上記の単体テスト |
| **P5** | ドキュメント（CLI リファレンス、CHANGELOG、`_usage()`） | `reason ci` 全通過 |

P1・P2 の時点で**端末を一切使わずに価値が出る**（エージェントや CI から
`reason view --json` でパイプラインを一括取得できる）のがこの分割の利点。
TUI が P3 まで遅れても、成果物は途中で捨てられない。

### スパン導入（16章）との順序関係

CodeViewer と AST スパンは**並行して進められる**。依存は一方向だけ:

```
S1（物理行の是正）─┐
S2（宣言スパン）  ─┴─▶ 任意のタイミングで P1 の anchors.py を切替（Anchor v1 のまま）
S3（式スパン）    ────▶ P4 以降に Anchor v2 へ拡張
```

CodeViewer 側はどの段階でも**スパンが無ければ字句索引にフォールバック**するため、
S1〜S3 の完了を待たずに P1〜P5 を完走できる。

---

## 15. 決定事項

| # | 論点 | 決定 | 反映先 |
|---|---|---|---|
| 1 | Windows の TUI | **`windows-curses` を Windows 限定 extra として追加**。未導入時は `--plain` へ縮退 | 11章 |
| 2 | `_scan_symbols` の共通化 | **P1 で実コードを読んだうえで判断**。LSP の挙動を壊すリスクは取らない | 6章 / 14章 |
| 3 | AST スパン導入 | **導入する**。ただし CodeViewer v0.1 の前提条件にはしない | 16章 |
| 4 | コマンド名 | **`view`** | 3章 |

決定2について補足しておくと、判断基準は次のとおり:

- **共通化する条件**: `_scan_symbols` が宣言の**開始行と終了行の両方**を返せること。
- **しない条件**: 開始行しか持たない場合。CodeViewer はブロック範囲の強調表示に
  終了行が必須なので、無理に合わせると LSP 側の `Symbol` 型を変更することになる。
  その場合は `anchors.py` に独立実装を置き、**将来 LSP 側から `anchors.py` を
  使う方向**（逆向きの共通化）を検討する。

---

## 16. AST スパン導入タスク設計（決定3）

スパン導入は採用決定。ただし着手前に実装を調査した結果、**「`nodes.py` に
フィールドを足す」だけでは済まない**ことが判明した。ここに実態と段階計画を記す。

### 16.1 調査結果 — なぜ機械的な追加で済まないか

**(a) サーフェスパーサはトークン駆動ではなく、行 / 正規表現ベース**

`parse()` は `tokenize(source)` を呼ぶが、これは**字句エラーの検出用で結果を捨てている**
（[parser.py:151](frontend/language_surface/parser.py:151)）。実際の構文解析は
`_Cursor(_logical_lines(source))` に対して正規表現で行われる
（例: [parser.py:175](frontend/language_surface/parser.py:175) の `re.fullmatch`）。
**位置情報を持つトークン列がパーサに届いていない。**

**(b) `_logical_lines` が物理行との対応を破壊している**

[parser.py:192](frontend/language_surface/parser.py:192):

```python
for raw in source.splitlines():
    line = _strip_line_comment(raw).strip()
    if not line:
        continue                              # ← 空行を捨てる
    line = re.sub(r"}\s*(elif\b)", r"}\n\1", line)   # ← 1物理行を2論理行に分割
    line = re.sub(r"}\s*(else\b)", r"}\n\1", line)
```

空行とコメント行が脱落し、`} else` は分割される。つまり `_Cursor.index` は
**論理行番号であり、物理行番号ではない**。

**(c) 既存の `SourceSpanNode` は現時点で誤った行番号を出している**

`ReasonObjectBindingNode` のスパンは `start_index + 1` を行番号として使っている
（[parser.py:340](frontend/language_surface/parser.py:340)）が、これは論理行番号。
実測で確認した:

| ソース | `span.start_line` | 実際の物理行 | |
|---|---|---|---|
| 空行・コメントなし | 2 | 2 | ✅ |
| 直前に空行1行 + コメント1行 | 2 | **4** | ❌ 2行ずれ |

この値は `toolchain/reasonunit_language/` を経由して
`source_provenance_report.json` の `source_span` に記録される
（[language.py:69](toolchain/reasonunit_language/language.py:69)、
[phase.py:149](toolchain/reasonunit_language/phase.py:149)）。
**「ソース来歴」を名乗るアーティファクトが、実在しない行を指しうる状態にある。**
これは CodeViewer とは独立に修正すべき欠陥。

**(d) 式パーサは独立したトークナイザを持ち、オフセットが式ローカル**

`expressions.py` は独自の `_tokenize` / `_Token` を持つ
（[expressions.py:650](frontend/language_surface/expressions.py:650)）。
`_Token.offset` は**その式文字列内の文字オフセット**で、ファイル先頭からの
絶対位置ではない。さらに生成される式ノード（`BinaryExpressionNode` など）は
`offset` を保持せず捨てている。

**(e) リポジトリ内にトークナイザが3系統ある**

- `frontend/language_surface/lexer.py` — 行・列を持つが、出力が使われていない
- `frontend/language_surface/expressions.py::_tokenize` — 式専用、式ローカルオフセット
- `frontend/parser/lexer.py` — 別系統のパーサスタックが正しくトークン駆動

スパン設計はどれを正とするかを先に決める必要がある。

### 16.2 段階計画

上記を踏まえ、**独立して価値が出る4段階**に分割する。S1 だけでも既存欠陥が直る。

| 段 | 内容 | AST 変更 | ゴールデン影響 | CodeViewer への効果 |
|---|---|---|---|---|
| **S1** | 論理行 → 物理行の対応表を `_logical_lines` に持たせ、既存スパンを物理行に是正 | なし | `source_provenance_report.json` の値が変わる | なし（v1 は字句索引を使うため） |
| **S2** | 宣言ノード（module / calculation / function / enum / struct）に `span` を追加 | 5〜8クラス | `*.ast.json` に新フィールド | Anchor の索引をスパン由来へ切替（精度向上） |
| **S3** | 式ノードにファイル絶対オフセットを付与。`_tokenize` にファイル基準オフセットを渡す | 式ノード群 | `*.ast.json` 拡大 | **式レベル相関が可能に（Anchor v2）** |
| **S4** | サーフェスパーサをトークン駆動へ再構成し、`lexer.py` の出力を実際に消費 | 大 | 広範 | 位置精度が完全化 |

**推奨: S1 → S2 まで先に実施し、S3 は CodeViewer v0.1 完成後に着手。S4 は別途判断。**

理由: S1 は欠陥修正で単独の価値があり、S2 は CodeViewer の相関精度を上げる。
S3 / S4 はパーサの再構成に踏み込むため、CodeViewer を人質に取らせない。

### 16.3 S1 の具体案（最小・低リスク）

`_logical_lines` の戻り値を `list[str]` から `list[_LogicalLine]` に変える:

```python
@dataclass(frozen=True)
class _LogicalLine:
    text: str
    physical_line: int    # 1-origin の物理行番号

    def __str__(self) -> str:      # 既存の文字列操作を壊さないための互換
        return self.text
```

- `_Cursor.current()` / `take()` は `.text` を返し続けるので、
  **1236行のパーサ本体はほぼ無変更**で済む。
- スパン生成箇所（現状 `parser.py` の3箇所のみ）で `start_index + 1` を
  `cursor.lines[start_index].physical_line` に置き換える。
- `} else` 分割で生まれた2つ目の論理行は、元の物理行番号を共有する。

### 16.4 互換性の扱い（`AGENTS.md` ゴールデン方針）

`AGENTS.md` は「ゴールデン基準線の更新は仕様変更・意図的な挙動変更・互換性方針が
許す場合のみ」と定めている。S1 は `source_provenance_report.json` の値を変えるため、
**仕様変更として扱い、CHANGELOG と基準線更新をセットで行う**。

「バリデーション失敗後に自動でゴールデンを更新してはならない」という規定があるので、
S1 は次の順序で進める:

1. 現行の誤った行番号を**テストで固定**し、欠陥として明示する
2. 修正を入れる
3. 仕様変更として CHANGELOG に記載し、そのうえで基準線を更新する

---

## 付録: 検証に使った実データ

`examples/v0_5/003_calculation_dependency.rsn` を実際にパイプラインへ通した結果、
6章の相関連鎖が成立することを確認済み:

```
Reason IR       transitions[0].transition_id      = "Base-1-result"
                transitions[0].effect.calculation = "Base"
ExecutionPlan   selected_steps[0].transition_id   = "Base-1-result"
                selected_steps[0].target          = "Base.state.result"
Semantic AST    TransitionNode(node_id="CalculationDependency-calculation-1",
                               transition_id="Base-1-result")
```

### 既存スパンのずれ（16.1-c）の再現手順

```python
from frontend.language_surface.parser import parse

src = '''module M {

  // comment line
  reason_object Cat from "a.ruo"
}'''
binding = next(d for d in parse(src).modules[0].body
               if type(d).__name__ == "ReasonObjectBindingNode")
print(binding.source_span.start_line)   # => 2  （物理行は 4）
```

空行とコメント行を削ると `2` が正しくなる。すなわち脱落した行数だけずれる。
