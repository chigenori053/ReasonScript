# ReasonScript CLI reference

Run `reason help` for the installed command surface. Add `--json` when a
command is consumed by an agent, script, or CI job.

## Canonical CI

```sh
./reason ci --json
```

Runs the canonical v0.5 validation pipeline.

## Source and Project Validation

```sh
./reason check <source.rsn>
./reason check <source.rsn> --diagnostic-format json
./reason check
./reason check --diagnostic-format json
```

Validates a ReasonScript source file or the current package workspace without building runtime artifacts.

- `--diagnostic-format text` (default): Emits human-readable diagnostics.
- `--diagnostic-format json`: Emits deterministic JSON document adhering to `reasonscript-diagnostics/1.0`.

## Program and Project Execution (`reason run`)

### English
Executes a standalone source file or a package project.

```sh
# Standalone source file execution
./reason run <source.rsn>
./reason run <source.rsn> --json

# Project execution (from project directory)
./reason run
./reason run <entry>
./reason run --entry <entry>
./reason run --package <pkg> --json
```

- **On-Demand Build**: If runtime artifacts are not built yet, `reason run` automatically triggers `reason build` to lower the source into computation IR before execution.
- **Deterministic Entry Resolution**:
  - If no entry is specified:
    1. If the project contains exactly one calculation, it is selected automatically.
    2. If multiple calculations exist and one is named `Main` or `main`, it is prioritized.
    3. If multiple calculations exist without a `Main`, execution stops with `AmbiguousEntry` listing all available candidates.
  - If an explicit `<entry>` is specified and not found, execution halts with `UnknownEntry` displaying available calculation candidates.
- **Exit Codes**:
  - `0`: Successful execution.
  - `1`: User/CLI error, ambiguous entry, missing source, or unknown entry.
  - `2`: Build failure, IR compilation failure, or runtime panic/exception.

### 日本語 (Japanese)
単一ソースファイルまたはパッケージプロジェクトを実行します。

```sh
# 単一ソースファイルの直接実行
./reason run <source.rsn>
./reason run <source.rsn> --json

# プロジェクト実行（プロジェクト直下で実行）
./reason run
./reason run <entry>
./reason run --entry <entry>
./reason run --package <pkg> --json
```

- **オンデマンドビルド**: ビルド成果物が未生成の場合、`reason run` は自動的に `reason build` を実行して IR を生成した後に実行します。
- **決定論的エントリ解決**:
  - エントリが未指定の場合:
    1. プロジェクト内に calculation が 1 つのみの場合はそれを自動実行します。
    2. 複数の calculation が存在し `Main` または `main` がある場合はそれを優先実行します。
    3. それ以外の複数 calculation が存在し一意に定まらない場合は、暗黙選択を行わず候補一覧を表示して `AmbiguousEntry` エラーで停止します。
  - 明示的に `<entry>` を指定して見つからない場合は、候補一覧を表示して `UnknownEntry` エラーとなります。
- **プロセス終了コード (Exit Codes)**:
  - `0`: 正常終了。
  - `1`: ユーザー入力エラー、エントリの曖昧性、ソース不在、未知のエントリ。
  - `2`: ビルド失敗、IR コンパイル失敗、実行時エラー。



## Phase 8 Golden Validation

```sh
./reason phase8-golden validate --json
```

Validates Phase 8 golden fixtures and generated reasoning artifacts.

```sh
./reason phase8-golden update --json
```

Controlled maintenance command. Use only when intentionally updating approved golden artifacts after a specification, compatibility policy, or intentional behavior change.

## ReasoningModel

```sh
./reason reasoning-model validate <file> --json
```

Validates a `reasonscript-reasoning-model/1.0` artifact.

## ReasoningEvaluationReport

```sh
./reason reasoning-eval evaluate <reasoning-model.json> --json
./reason reasoning-eval validate <evaluation-report.json> --json
```

Evaluates a ReasoningModel or validates an existing `reasonscript-reasoning-evaluation-report/1.0` artifact.

## ReasoningRuntimeResult

```sh
./reason reasoning-runtime run <source.rsn> --json
./reason reasoning-runtime build-model <source.rsn> --json
./reason reasoning-runtime evaluate <source.rsn> --json
./reason reasoning-runtime validate <runtime-result.json> --json
```

Generates, evaluates, or validates Phase 8 runtime reasoning artifacts.

## Tensor data files

```sh
./reason tensor import --from json --input data.json --output data.rstensor
./reason tensor import --from csv --input data.csv --output data.rstensor --dtype f32
./reason tensor import --from npy --input data.npy --output data.rstensor
./reason tensor inspect data.rstensor --json
./reason tensor verify data.rstensor --json
```

`reason tensor import` converts rectangular JSON arrays, CSV rows, or NumPy
arrays into the canonical checksum-bearing `.rstensor` profile. NumPy import
requires the optional `numpy` package; JSON and CSV import are dependency-free.
Existing output files are rejected unless `--overwrite` is supplied.

ReasonScript source reads and writes these files with `tensor.load` and
`tensor.save`. Runtime file access remains opt-in:

```sh
./reason run train.rsn --allow-read --allow-write --json
```

Paths are resolved relative to the source file directory and cannot be absolute
or escape that resource root.

## CodeViewer

```sh
./reason view <source.rsn>
./reason view <source.rsn> --stage ir
./reason view <source.rsn> --plain --stage plan --width 100
./reason view <source.rsn> --json
./reason view <project-directory>       # browse a project's file tree instead
./reason view                            # same, rooted at the current directory
```

Browses a `.rsn` source file alongside its compiled Surface AST, Semantic
AST, Reason IR, and ExecutionPlan, correlating whichever declaration
contains the cursor with the stage nodes that came from it.

Passing a directory (or nothing at all) instead of a file opens the
interactive UI straight into the file-tree overlay, scoped to that
directory, with a shallow `.rsn` file auto-opened underneath so there's
always something to look at while picking a different one.

Options:

- `--stage <source|surface|semantic|ir|plan>` — stage shown first (default
  `source`).
- `--module <name>` — select a module when the source declares more than
  one (default: the first module).
- `--root <dir>` — scope the file-tree overlay to `<dir>` regardless of
  which file was opened (default: the file's own directory isn't used —
  the tree is rooted at the current directory, or at the directory
  argument itself when one was given).
- `--json` — print the full compiled-stage document as JSON and exit; the
  shape is validated by `schemas/code_viewer_document.schema.json`. Requires
  a specific file — a directory or omitted path exits with `CV-007`.
- `--plain` — print one static, non-interactive rendering and exit; useful
  for CI logs and coding agents. `--width <n>` bounds its line length
  (default: the terminal width, or 80). Same file requirement as `--json`.

With no `--json`/`--plain` flag, `reason view` opens an interactive
terminal UI when attached to a real terminal:

| Key | Action |
| --- | --- |
| `1`–`5`, `Tab` / `Shift-Tab` | Switch stage |
| `j`/`k`, `↓`/`↑` | Move the cursor (source pane) or the selection (stage/tree pane) |
| `Ctrl-d` / `Ctrl-u` | Half-page scroll |

## Language Server (`reason lsp`)

### English
Starts the ReasonScript Language Server over stdio (JSON-RPC). Used by editor integrations such as the official VS Code extension (`.rsn` client).

```sh
./reason lsp
./reason lsp --stdio
```

- **Features**:
  - Real-time diagnostics on `textDocument/didOpen`, `textDocument/didChange`, `textDocument/didSave`.
  - Hierarchical Document Symbols (`textDocument/documentSymbol`) for models, modules, functions, calculations, structs, enums, consts, states, transitions, relations, and goals.
  - Workspace Symbols (`workspace/symbol`) supporting case-insensitive query filtering and integer `SymbolKind` codes across all open documents and builtins.
  - Find References (`textDocument/references`) excluding comments, accurately mapping references across workspace documents.
  - Signature Help (`textDocument/signatureHelp`) for user-defined functions and built-in runtime/vision APIs with parameter hints and active parameter tracking.
  - Semantic Tokens (`textDocument/semanticTokens/full`) delivering standard 5-element relative delta encoding for rich syntax highlighting (keywords, types, functions, variables, strings, numbers, comments).
  - Rename Symbol (`textDocument/prepareRename` & `textDocument/rename`) validating identifier tokens, preventing keyword/built-in clashes and symbol collisions, and producing atomic workspace-wide edits.
  - Document Formatting (`textDocument/formatting`) providing 4-space indentation, normalized operator/brace spacing, and idempotent text edits.
  - Hover (`textDocument/hover`) with markdown signatures, visibility, type info, doc comments (`///`), and local variable/parameter inspection.
  - Go to Definition (`textDocument/definition`) resolving local variables/parameters, same-module declarations, qualified names (`Model.Member`), and cross-file exports.
  - Cancellation (`$/cancelRequest`) and QuickFix code actions.
- **Document Targeting**: Only ReasonScript files (`.rsn`) are served. Legacy or foreign extensions (`.re`, `.res`, etc.) are ignored.

### 日本語 (Japanese)
stdio 経由 (JSON-RPC) で ReasonScript Language Server を起動します。公式 VS Code 拡張（`.rsn` 専用クライアント）などのエディタ統合から利用されます。

```sh
./reason lsp
./reason lsp --stdio
```

- **機能**:
  - `didOpen` / `didChange` / `didSave` 時のリアルタイム診断配信。
  - 階層型ドキュメントシンボル (`textDocument/documentSymbol`): model, module, fn, calculation, struct, enum, const, state, transition, relation, goal などの構造ツリー。
  - ワークスペースシンボル (`workspace/symbol`): 大文字小文字不問のクエリフィルタリング、整数値 `SymbolKind` コードの返却、開いている全ファイルおよびビルトインシンボルの網羅。
  - 参照検索 (`textDocument/references`): コメント（行コメント・ブロックコメント）を除外したワークスペース全域の正確な参照箇所収集。
  - シグネチャヘルプ (`textDocument/signatureHelp`): ユーザー定義関数およびランタイム・ビジョン組み込み API の引数案内と `activeParameter` 追跡。
  - セマンティックトークン (`textDocument/semanticTokens/full`): 標準 5 要素相対デルタエンコードによる高精度シンタックスハイライト（キーワード、型、関数、変数、文字列、数値、コメント）。
  - シンボルリネーム (`textDocument/prepareRename` & `textDocument/rename`): 識別子範囲の事前検査、予約キーワード・ビルトイン・既存シンボル衝突の防止、ワークスペース一括置換 `WorkspaceEdit` 生成。
  - ドキュメントフォーマット (`textDocument/formatting`): 4スペースインデント、演算子・波括弧周辺の空白正規化、冪等性を保証した一括整形。
  - ホバー表示 (`textDocument/hover`): Markdown 形式のシグネチャ、可視性、型情報、ドキュメントコメント (`///`)、ローカル変数/引数のインスペクション。
  - 定義へ移動 (`textDocument/definition`): ローカルスコープ（引数・変数）、モジュール内シンボル、修飾名 (`Model.Member`)、別ファイル公開シンボルの解決。
  - キャンセル処理 (`$/cancelRequest`) および QuickFix アクション。
- **対象ドキュメント**: ReasonScript ソースファイル (`.rsn`) のみを対象とし、旧拡張子や他言語 (`.re`, `.res` 等) は対象外となります。

| `n` / `p` | Jump to the next/previous declaration — or the next/previous search match once `/` has been used |
| `/` | Search the source text; `Enter` confirms, `Esc` cancels |
| `Enter` | Focus the stage pane |
| `Esc` | Clear an active search, otherwise return focus to the source pane |
| `y` | Copy the selected stage node's JSON pointer to the clipboard |
| `d` | Toggle a summary of every stage's diagnostics |
| `e` | Toggle the file-tree overlay for the current project |
| `?` | Toggle this key list |
| `q`, `Ctrl-c` | Quit |

While the file tree is open (`e`): `j`/`k` move, `l`/`Enter` opens a file
or expands a directory, `h` collapses a directory (or jumps to its
parent), and `Esc` closes the tree without changing the open file. The
file currently open is always highlighted, and reopening the tree
re-reveals wherever that file is, even after browsing elsewhere.

Non-interactive environments (a pipe, a CI job, an agent) automatically get
the `--plain` rendering instead of the terminal UI, even without passing
`--plain` explicitly — this only applies when a specific file was given;
with a directory or no path, non-interactive environments get the usage
message instead (there's nothing to render non-interactively without a
file).

**Windows**: the interactive UI needs the `windows-curses` package, pulled
in by installing the `viewer` or `full` extra (`pip install
'reasonscript[viewer]'`). Without it, `reason view` still works — it falls
back to the `--plain` rendering and prints a note to stderr instead of
failing.

## Project Management and Manifest Contract

### Project Initialization (`reason init`)

```sh
reason init <project-name>
```

Initializes a standard ReasonScript project structure:

- `.gitignore` (excludes `target/` and artifacts except `.gitkeep`)
- `artifacts/.gitkeep`
- `README.md`
- `reason.toml` (canonical project manifest)
- `src/main.rsn` (standard entry point)
- `tests/sample_test.rsn` (standard unit test)

### Project Manifest (`reason.toml`)

Standard sections and keys in `reason.toml`:

```toml
[package]
name = "my_project"
version = "0.1.0"
identifier = "my_project"      # normalized package identifier

[project]
name = "my_project"            # defaults to package.name
version = "0.1.0"              # defaults to package.version
reason_version = ">=0.5.0"     # compatible toolchain constraint

[source]
entry = "src/main.rsn"         # entry file (relative, within project root)

[artifacts]
directory = "artifacts"        # artifact output directory (relative, within project root)

[compiler]
language_core = "0.7"          # language core version
platform = "0.2"               # platform version

[runtime]
backend = "RuntimeReal"        # "RuntimeReal" or "HybridRuntime"
max_call_depth = 100           # optional positive integer recursion limit
max_loop_iterations = 100000   # optional positive integer; default 10000 block visits per call

[dependencies]
# package dependencies

[capabilities]
# capability declarations
```

`[source]` is optional for legacy manifests. When it is absent, `build`,
`check`, `run`, and project validation recursively discover `src/**/*.rsn`
without requiring `src/main.rsn`. When `[source]` is present, `entry` is
required, must remain inside the project root, is compiled first, and does
not exclude sibling modules under `src/`.

#### Diagnostic Policy:
- Truly unknown sections outside known tables (`package`, `project`, `source`, `artifacts`, `compiler`, `runtime`, `dependencies`, `capabilities`) emit `UserWarning: Unknown sections in reason.toml: <sections>`.
- Unknown keys within known sections emit `UserWarning: Unknown keys in reason.toml [<section>]: <keys>`.
- Missing required fields, type errors, or root-escaping paths in `source.entry` / `artifacts.directory` raise `ManifestError`.
- A declared but missing `source.entry` produces `SourceEntryMissing` consistently across `build`, `check`, `run`, and project validation.

---

## Migration of Legacy Source Extensions (`reason migrate extensions`)

### English

The `reason migrate extensions` command safely and deterministically renames legacy ReasonScript source files to the canonical `.rsn` format and updates references in `reason.toml`.

```sh
# Dry-run inspection: report planned migrations and detect conflicts without modifying files
reason migrate extensions --check
reason migrate extensions --check --json

# Execute migration in project or specified directory
reason migrate extensions
reason migrate extensions path/to/project
```

#### Supported Legacy Extensions
- `.re` -> `.rsn`
- `.rei` -> `.rsn`
- `.res` -> `.rsn`
- `.resi` -> `.rsn`
- `.reason` -> `.rsn`
- `.rscript` -> `.rsn`

Non-source artifacts (`.ruo`, `.ruot`, `.vwm`, `reason.toml`) and already canonical `.rsn` files are preserved and never migrated.

#### Safety and Atomicity Guarantees
1. **Never Overwrites Existing `.rsn` Files:** If the target `.rsn` file already exists, migration aborts with `SRC-0004` (Conflict).
2. **Many-to-One and Case-Insensitive Collisions:** If multiple legacy sources map to the same target `.rsn` (or differ only by casing on case-insensitive filesystems), migration aborts with `SRC-0004`.
3. **Symlink Safety:** Symbolic links are rejected with `SRC-0005` to prevent accidental modification of external files.
4. **Atomic Execution with Rollback:** If an unexpected file system error occurs during batch rename, already renamed files are rolled back in reverse order, preserving project integrity.
5. **Manifest Updating:** Legacy source paths referenced in `reason.toml` (e.g. `entry = "src/main.re"`) are updated to `.rsn`.

#### Exit Codes
- `0`: Success (all files migrated, or check mode passed with 0 conflicts, or no legacy files found)
- `1`: Conflicts detected, unsupported source format, or invalid CLI arguments
- `2`: File system or I/O failure (with automatic rollback)

---

### 日本語 (Japanese)

`reason migrate extensions` コマンドは、旧形式の ReasonScript ソースファイルを正規の `.rsn` 形式へ安全かつ決定論的にリネームし、`reason.toml` 内のパス参照を同期します。

```sh
# Dry-run（検査モード）: ファイルを変更せずに対象・衝突を診断・報告
reason migrate extensions --check
reason migrate extensions --check --json

# プロジェクトまたは指定ディレクトリの移行を実行
reason migrate extensions
reason migrate extensions path/to/project
```

#### 対象となる旧拡張子
- `.re` -> `.rsn`
- `.rei` -> `.rsn`
- `.res` -> `.rsn`
- `.resi` -> `.rsn`
- `.reason` -> `.rsn`
- `.rscript` -> `.rsn`

非ソース成果物 (`.ruo`, `.ruot`, `.vwm`, `reason.toml`) や既存の `.rsn` ファイルは移行対象に含まれません。

#### 安全性と原子性 (Atomicity) 保証
1. **既存 `.rsn` ファイルの上書き防止:** 移行先に同名の `.rsn` が既に存在する場合、上書きせず `SRC-0004` (Conflict) として拒否します。
2. **跨ぎ衝突・大文字小文字衝突の検知:** 複数の旧ソースが同一の `.rsn` にマッピングされる場合や、大文字小文字を区別しないファイルシステムでの衝突を `SRC-0004` として拒否します。
3. **シンボリックリンクの安全保護:** シンボリックリンクは `SRC-0005` として拒否し、外部ファイルへの意図しない変更を防ぎます。
4. **自動ロールバックによる原子性:** リネーム処理中に I/O 障害等が発生した場合、変更済みファイルを逆順で元の名前に安全にロールバックします。
5. **マニフェスト参照の同期:** `reason.toml` の `entry = "src/main.re"` などの旧拡張子指定を `.rsn` へ安全に更新します。

#### 終了コード
- `0`: 成功（移行完了、または `--check` で衝突なし、または移行対象なし）
- `1`: 衝突（Conflict）検出、非対応形式、または引数エラー
- `2`: ファイルシステム・I/O 障害（自動ロールバック実行）
