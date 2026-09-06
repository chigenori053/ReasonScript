# Common Diagnostic Model and JSON Contract / 共通 Diagnostic モデルと JSON 契約

[English](#english) | [日本語](#japanese)

---

<a name="english"></a>
## English

### 1. Overview
ReasonScript provides a unified diagnostic model across the compiler, CLI, language server protocol (LSP), and editor extensions. Every diagnostic carries a stable error/warning code, categorized prefix, precise source span, severity, human-readable message, optional title and help text, and fix candidates.

### 2. Classification and Diagnostic Codes
Diagnostics are organized into canonical categories identified by standard prefixes:

| Prefix | Category | Description |
|---|---|---|
| `CLI` | CLI | Command-line interface argument, option, or I/O errors |
| `SRC` | Source | Source file extension, encoding, or deprecation warnings |
| `PRJ` | Project | Project manifest (`reason.toml`) and workspace errors |
| `LEX` | Lexer | Lexical errors, tokenization errors, and illegal Unicode |
| `PAR` | Parser | Syntactic errors and malformed constructs |
| `NAM` | Namespace | Name resolution, undefined identifiers, and visibility violations |
| `TYP` | Type | Type checking mismatches and invalid operations |
| `BLD` | Build | Compilation lowering, IR generation, and artifact errors |
| `RUN` | Runtime | Runtime execution errors, assertions, and limits |
| `ICE` | ICE | Internal Compiler Error (unreachable states, compiler panics) |

### 3. Source Span and Coordinate Conventions
- **Line numbers (`line`)**: 1-indexed. Incremented on each line break.
- **Column numbers (`column`)**: 1-indexed. Measured in Unicode code points (1 character = 1 column).
- **Newlines**: Both LF (`\n`) and CRLF (`\r\n`) are recognized as valid line delimiters.
- **Offsets (`offset`)**: 0-indexed byte offset in UTF-8.
- **Spans (`span`)**: Half-open interval `[start, end)` representing the precise token or node range.
- **Paths (`file`)**: Normalized POSIX-style relative paths from workspace or project root.

### 4. JSON Schema and `reason check --diagnostic-format json`
Diagnostics can be emitted in standard JSON format conforming to schema `reasonscript-diagnostics/1.0`:

```sh
reason check src/main.rsn --diagnostic-format json
```

Example JSON response:
```json
{
  "version": "1.0",
  "schema": "reasonscript-diagnostics/1.0",
  "compiler_version": "0.5.5.11",
  "runtime_version": "0.5.5.11",
  "diagnostics": [
    {
      "id": "diag-00000001",
      "code": "PAR-0001",
      "severity": "ERROR",
      "category": "Parser",
      "title": "Syntax error",
      "message": "Expected identifier after 'let'",
      "help": "Provide a valid variable name",
      "location": {
        "file": "src/main.rsn",
        "line": 10,
        "column": 5,
        "length": 3,
        "uri": "file://src/main.rsn",
        "span": {
          "start": { "line": 10, "column": 5, "offset": 120 },
          "end": { "line": 10, "column": 8, "offset": 123 }
        }
      },
      "related_locations": [],
      "fix": {},
      "fix_candidates": [],
      "metadata": {}
    }
  ]
}
```

### 5. Compiler Frontend API (CLI & LSP Shared Pipeline)
ReasonScript provides a unified in-process frontend pipeline (`CompilerFrontend.analyze`) shared by both the CLI and the Language Server Protocol (LSP).

- **In-Memory & Pre-Save Analysis**: Accepts `FrontendRequest(source, filename, uri, compiler_mode)` to analyze editor buffer content before saving to disk.
- **Deterministic Pipeline Boundaries**:
  1. `lexer`: Tokenization and unsupported character validation (`LEX-0001`).
  2. `parser`: Structural parsing via `parse_unresolved` (`PAR-0001`, `LL-002-RESERVED-TOP-LEVEL-CONSTRUCT`).
  3. `name_resolution`: Module import resolution, symbol binding, visibility checks (`NAM-0001` - `NAM-0004`).
  4. `type_check`: Type consistency and semantic validation (`TYP-0001`).
  5. `completed`: Full analysis succeeded.
- **Panic & Exception Isolation**: Unhandled exceptions are isolated and converted into structured `ICE-0001` (Internal Compiler Error) diagnostics, preventing LSP or CLI host process crashes.
- **CLI / LSP Parity**: CLI checking tools and the LSP core produce identical diagnostic codes, source ranges, severities, and error messages.

### 6. Diagnostic Registry & Canonical Code Catalog
ReasonScript maintains a centralized `DiagnosticRegistry` (`toolchain/diagnostics.py`) registering all standard diagnostics, default severities, titles, descriptions, remediation guidance, and legacy compatibility aliases.

#### Standard Code Catalog

| Code | Category | Severity | Title | Description / Guidance |
|---|---|---|---|---|
| `CLI-0001` | CLI | ERROR | Command-line argument error | Unknown option or invalid arguments provided. |
| `CLI-0002` | CLI | ERROR | Missing required CLI argument | A required positional argument or flag was omitted. |
| `CLI-0003` | CLI | ERROR | I/O or file system error | Unable to read or write file specified in command line. |
| `SRC-0001` | Source | WARNING | Source file naming warning | Source files should use the `.rsn` extension. |
| `SRC-0002` | Source | ERROR | No source files found | No `.rsn` files found in `src/` or target directory. |
| `SRC-0003` | Source | ERROR | Source entry missing | Target source file is not found in package. |
| `SRC-0004` | Source | ERROR | Source file migration conflict | Target `.rsn` file already exists or multiple sources map to the same destination. |
| `SRC-0005` | Source | ERROR | Unsupported migration target | File cannot be migrated due to unsupported format, symlink, or permission issue. |
| `PRJ-0001` | Project | ERROR | Project manifest error | Failed to parse or validate `reason.toml`. |
| `PRJ-0002` | Project | ERROR | Workspace dependency cycle | Circular dependency detected between workspace packages. |
| `PRJ-0003` | Project | ERROR | Unknown workspace package | Requested package is not defined in workspace. |
| `LEX-0001` | Lexer | ERROR | Lexical error | Unsupported character or illegal byte sequence. |
| `LEX-0002` | Lexer | ERROR | Unterminated string literal | String literal opened but not closed before newline/EOF. |
| `LEX-0003` | Lexer | ERROR | Malformed number literal | Numeric literal contains invalid formatting. |
| `PAR-0001` | Parser | ERROR | Syntax error | Failed to parse token sequence into valid AST. |
| `PAR-0002` | Parser | ERROR | Reserved construct | Construct reserved for future features (alias: `LL-002`). |
| `PAR-0003` | Parser | ERROR | Unexpected delimiter or block | Unmatched delimiter or unexpected token encountered. |
| `PAR-0004` | Parser | ERROR | Invalid package declaration | Package declaration misplaced or malformed (alias: `PV-1`). |
| `NAM-0001` | Namespace | ERROR | Namespace resolution error | Duplicate symbol or ambiguous declaration (alias: `NS-001`). |
| `NAM-0002` | Namespace | ERROR | Module not found | Imported module not found (alias: `PV-4`). |
| `NAM-0003` | Namespace | ERROR | Unknown symbol | Referenced symbol does not exist in target scope (alias: `NS-020`). |
| `NAM-0004` | Namespace | ERROR | Visibility violation | Cannot access private symbol from another module. |
| `NAM-0005` | Namespace | ERROR | Ambiguous symbol reference | Symbol is ambiguous due to conflicting imports. |
| `TYP-0001` | Type | ERROR | Type validation error | Type mismatch or unsupported operation on type. |
| `TYP-0002` | Type | ERROR | Function return type mismatch | Return expression does not match annotation (alias: `FN-005`). |
| `TYP-0003` | Type | ERROR | Struct field type mismatch | Field value does not match struct definition. |
| `TYP-0004` | Type | ERROR | Pattern matching mismatch | Pattern type does not match inspected expression. |
| `BLD-0001` | Build | ERROR | Build compilation error | Failed to lower surface AST to ReasonIR. |
| `BLD-0002` | Build | ERROR | Artifact emission error | Failed to generate or serialize build artifacts. |
| `RUN-0001` | Runtime | ERROR | Runtime execution error | Unhandled runtime panic during execution. |
| `RUN-0002` | Runtime | ERROR | Assertion failure | Runtime assertion or reach goal was not met. |
| `RUN-0003` | Runtime | ERROR | Resource limit exceeded | Execution exceeded step or memory limit. |
| `ICE-0001` | ICE | ERROR | Internal compiler error | Unexpected compiler panic or unhandled internal exception. |

### 7. Remediation Guidance and Fix Candidates (`help` & `fix_candidates`)
ReasonScript diagnostics can carry structured remediation guidance and actionable code fixes:

- **`help` text**: A human-friendly hint explaining how to fix the issue or why the error occurred.
- **`fix_candidates`**: An array of `DiagnosticFix` objects containing:
  - `title`: Short title of the fix (e.g., `Replace with 'model'`).
  - `description`: Detailed explanation of the proposed edit.
  - `edits`: List of precise text replacements (`file`, `span`, `new_text`).
  - `priority`: Ordering rank for IDE QuickFix presentation.

#### CLI Rendering
When rendered in terminal output (`--diagnostic-format text`), remediation information is displayed clearly below the source excerpt:
```text
sample.rsn:1:1: error[PAR-0002]: Reserved Construct: Reserved top-level construct 'world' is not supported in this version.
  1 | world MyWorld {}
    | ^^^^^
    = help: Reserved top-level construct. Consider using 'model' or 'module' instead.
    = suggested fix: Replace with 'model'
      model
    = suggested fix: Replace with 'module'
      module
```

#### LSP / QuickFix Integration
In Language Server Protocol responses, `help` and `fix_candidates` are included in the diagnostic payload (`data` field).
- **Real-time Push Diagnostics**: On document open (`didOpen`) or edit (`didChange`), diagnostics are immediately broadcast to the client via `textDocument/publishDiagnostics`.
- **CodeAction (QuickFix)**: The server exposes `codeActionProvider` supporting `quickfix`. Requesting `textDocument/codeAction` for a diagnostic range generates standard `WorkspaceEdit` objects containing the text replacements, enabling instant one-click fixes in VS Code.
- **Context-Aware Completion**: Includes documentation and details for keywords and constructs, and provides dedicated member completions (e.g. `runtime.search`, `vision.infer`) upon trailing dots.
- **Rich Markdown Hover**: Displays syntax-highlighted code blocks, full signatures, and module metadata for keywords, APIs, and user-defined declarations.
- **Precise Definition Jump**: Resolves local declarations, functions, models, and cross-module symbols.

---

<a name="japanese"></a>
## 日本語

### 1. 概要
ReasonScript は、コンパイラ、CLI、LSP（言語サーバー）、およびエディタ統合全体で共有される統一 Diagnostic モデルを提供します。すべての診断は、安定したコード、プレフィックス分類、正確な Source Span、重大度（Severity）、説明メッセージ、任意のタイトルおよび修正ヒント（help）、修正候補（fix candidates）を保持します。

### 2. 分類と診断コード
診断は、以下の標準プレフィックスによって体系化されています:

| プレフィックス | カテゴリ | 説明 |
|---|---|---|
| `CLI` | CLI | コマンドライン引数・フラグ・I/O エラー |
| `SRC` | Source | ソースファイル拡張子・エンコーディング・非推奨警告 |
| `PRJ` | Project | プロジェクト設定 (`reason.toml`)・ワークスペースエラー |
| `LEX` | Lexer | 字句解析エラー・不正な Unicode・トークン化失敗 |
| `PAR` | Parser | 構文解析エラー・文法違反 |
| `NAM` | Namespace | 名前解決・未定義識別子・可視性違反 |
| `TYP` | Type | 型検査エラー・型不一致 |
| `BLD` | Build | コンパイル・IR生成・成果物生成エラー |
| `RUN` | Runtime | ランタイム実行時エラー・アサーション失敗・リソース制限 |
| `ICE` | ICE | 内部コンパイラエラー (Internal Compiler Error) |

### 3. Source Span と座標系の基準
- **行番号 (`line`)**: 1-indexed（1始まり）。改行ごとにインクリメント。
- **列番号 (`column`)**: 1-indexed（1始まり）。Unicode コードポイント単位（1文字＝1列）。
- **改行**: LF (`\n`) および CRLF (`\r\n`) の両方を正規の改行文字として認識。
- **オフセット (`offset`)**: UTF-8 バイト単位の 0-indexed オフセット。
- **範囲 (`span`)**: 半開区間 `[start, end)`。開始位置と終了位置を正確に保持。
- **ファイルパス (`file`)**: プロジェクト/ワークスペースルートからの正規化された POSIX 形式相対パス。

### 4. JSON スキーマと `reason check --diagnostic-format json`
`reason check` コマンドで `--diagnostic-format json` を指定することで、同一の Diagnostic オブジェクトから生成された決定的な JSON 出力を取得できます:

```sh
reason check src/main.rsn --diagnostic-format json
```
人間向け表示（`--diagnostic-format text`）と JSON 出力（`--diagnostic-format json`）は同一の Diagnostic モデルに基づいて生成されるため、コード、重大度、位置、メッセージの完全な一致が保証されます。

### 5. コンパイラフロントエンド API (CLI と LSP 共有パイプライン)
ReasonScript は、CLI と Language Server Protocol (LSP) の双方が共有するインプロセス解析パイプライン (`CompilerFrontend.analyze`) を提供します。

- **メモリ内・保存前解析**: `FrontendRequest(source, filename, uri, compiler_mode)` を受け取り、エディタの保存前バッファを直接解析可能。
- **決定的なパイプライン境界**:
  1. `lexer`: トークン化および非対応文字の検出 (`LEX-0001`)。
  2. `parser`: `parse_unresolved` による AST 構文解析および予約語検証 (`PAR-0001`, `LL-002-RESERVED-TOP-LEVEL-CONSTRUCT`)。
  3. `name_resolution`: モジュールインポート解決、シンボルバインド、可視性検証 (`NAM-0001` - `NAM-0004`)。
  4. `type_check`: 型整合性および意味検証 (`TYP-0001`)。
  5. `completed`: 全フェーズ完了。
- **パニック／例外分離 (Panic / Exception Isolation)**: コンパイラ内部の予期せぬ例外を安全に捕捉し、構造化された `ICE-0001` (Internal Compiler Error) 診断として返却することで、エディタやプロセス全体のクラッシュを防止。
- **CLI / LSP パリティ**: CLI の検査ツールと LSP コアが同一の Diagnostic モデルを消費し、コード、範囲、重大度、メッセージの完全な一致を保証。

### 6. Diagnostic Registry と標準エラーコードカタログ
ReasonScript は、全標準診断コード、デフォルトの重大度、タイトル、詳細説明、修正案内、および旧コードとの互換性エイリアスを一元管理する `DiagnosticRegistry` (`toolchain/diagnostics.py`) を保持します。

#### 標準エラーコードカタログ

| コード | カテゴリ | 重大度 | タイトル | 説明・修正案内 |
|---|---|---|---|---|
| `CLI-0001` | CLI | ERROR | コマンドライン引数エラー | 不明なオプションまたは無効な引数が指定されました。 |
| `CLI-0002` | CLI | ERROR | 必須引数の欠落 | 必要な位置引数またはフラグが指定されていません。 |
| `CLI-0003` | CLI | ERROR | I/O・ファイルシステムエラー | コマンドで指定されたファイルの読み書きに失敗しました。 |
| `SRC-0001` | Source | WARNING | ソースファイル命名警告 | ReasonScript ソースファイルは `.rsn` 拡張子を使用してください。 |
| `SRC-0002` | Source | ERROR | ソースファイル不在 | `src/` または対象ディレクトリ内に `.rsn` ファイルが見つかりません。 |
| `SRC-0003` | Source | ERROR | ソースエントリ欠落 | 対象のソースファイルがパッケージ内に見つかりません。 |
| `SRC-0004` | Source | ERROR | ソースファイル移行衝突 | 移行先の `.rsn` が既に存在するか、複数の旧ファイルが同一ファイルに変換されます。 |
| `SRC-0005` | Source | ERROR | 非対応の移行対象 | シンボリックリンクや権限不足、または非対応形式のため移行できません。 |
| `PRJ-0001` | Project | ERROR | プロジェクトマニフェストエラー | `reason.toml` の構文またはスキーマの検証に失敗しました。 |
| `PRJ-0002` | Project | ERROR | ワークスペース循環依存 | ワークスペースパッケージ間で循環依存が検出されました。 |
| `PRJ-0003` | Project | ERROR | 未知のワークスペースパッケージ | 指定されたパッケージがワークスペース内に定義されていません。 |
| `LEX-0001` | Lexer | ERROR | 字句解析エラー | 非対応文字または不正なバイトシーケンスが検出されました。 |
| `LEX-0002` | Lexer | ERROR | 未終端の文字列リテラル | 改行または EOF の前に文字列クォートが閉じられていません。 |
| `LEX-0003` | Lexer | ERROR | 不正な数値リテラル | 数値リテラルの書式が不正です。 |
| `PAR-0001` | Parser | ERROR | 構文エラー | トークン列を有効な AST に解析できませんでした。 |
| `PAR-0002` | Parser | ERROR | 予約構文 | 将来の機能向けに予約された構文です（旧コード: `LL-002`）。 |
| `PAR-0003` | Parser | ERROR | 予期しない区切り文字またはブロック | 括弧の不一致または予期しないトークンに遭遇しました。 |
| `PAR-0004` | Parser | ERROR | 不正なパッケージ宣言 | パッケージ宣言の位置または書式が不正です（旧コード: `PV-1`）。 |
| `NAM-0001` | Namespace | ERROR | 名前解決エラー | 重複シンボルまたは曖昧な宣言が検出されました（旧コード: `NS-001`）。 |
| `NAM-0002` | Namespace | ERROR | モジュール未検出 | インポート対象モジュールが見つかりません（旧コード: `PV-4`）。 |
| `NAM-0003` | Namespace | ERROR | 未知のシンボル | 参照されたシンボルが対象スコープに存在しません（旧コード: `NS-020`）。 |
| `NAM-0004` | Namespace | ERROR | 可視性違反 | 別モジュールの非公開（private）シンボルにはアクセスできません。 |
| `NAM-0005` | Namespace | ERROR | 曖昧なシンボル参照 | 衝突する複数のインポートによりシンボルが曖昧です。 |
| `TYP-0001` | Type | ERROR | 型検査エラー | 型の不一致またはサポートされていない型演算です。 |
| `TYP-0002` | Type | ERROR | 関数戻り値型不一致 | 返却された式の型が関数の戻り値型アノテーションと一致しません（旧コード: `FN-005`）。 |
| `TYP-0003` | Type | ERROR | 構造体フィールド型不一致 | フィールド値の型が構造体定義と一致しません。 |
| `TYP-0004` | Type | ERROR | パターンマッチング型不一致 | パターンの型が検査対象の式と一致しません。 |
| `BLD-0001` | Build | ERROR | ビルドコンパイルエラー | 構文 AST から ReasonIR への変換に失敗しました。 |
| `BLD-0002` | Build | ERROR | 成果物出力エラー | ビルド成果物の生成またはシリアライズに失敗しました。 |
| `RUN-0001` | Runtime | ERROR | ランタイム実行エラー | 実行中に未捕捉のランタイムエラーまたはパニックが発生しました。 |
| `RUN-0002` | Runtime | ERROR | アサーション失敗 | ランタイムアサーションまたは reach ゴールが満たされませんでした。 |
| `RUN-0003` | Runtime | ERROR | リソース制限超過 | 最大ステップ数またはメモリ制限を超過しました。 |
| `ICE-0001` | ICE | ERROR | 内部コンパイラエラー | 予期しないコンパイラパニックまたは内部例外が発生しました。 |

### 7. 修正ガイダンスと修正候補 (`help` & `fix_candidates`)
ReasonScript の診断は、構造化された修正案内と機械可読なコード修正（Fixes）を保持できます:

- **`help` テキスト**: 問題の解決策やエラー理由を説明する人間向けのヒント。
- **`fix_candidates`**: `DiagnosticFix` オブジェクトの配列（タイトル、詳細説明、置換テキスト、適用範囲、優先度）。
  - `title`: 修正候補の簡潔な表示名（例: `Replace with 'model'`）。
  - `description`: 提案される変更内容の具体的説明。
  - `edits`: 正確なテキスト置換リスト (`file`, `span`, `new_text`)。
  - `priority`: IDE の QuickFix 一覧での表示優先度。

#### CLI 出力表示
ターミナル出力（`--diagnostic-format text`）では、ソースコードの抜粋の下に修正案内と提案が整形表示されます:
```text
sample.rsn:1:1: error[PAR-0002]: Reserved Construct: Reserved top-level construct 'world' is not supported in this version.
  1 | world MyWorld {}
    | ^^^^^
    = help: Reserved top-level construct. Consider using 'model' or 'module' instead.
    = suggested fix: Replace with 'model'
      model
    = suggested fix: Replace with 'module'
      module
```

#### LSP / QuickFix 連携
Language Server Protocol (LSP) の診断レスポンスでは、`help` および `fix_candidates` が `data` ペイロード内に保持されます。
- **リアルタイム診断配信**: ドキュメントを開いた際（`didOpen`）や変更時（`didChange`）に、`textDocument/publishDiagnostics` 通知を通じて即座にエディタへ波線警告をプッシュ配信。
- **CodeAction (QuickFix)**: サーバーが `quickfix` を提供する `codeActionProvider` を宣言。診断位置で `textDocument/codeAction` を呼び出すと、置換テキストを含む標準 `WorkspaceEdit` が返却され、VS Code 上で電球アイコンから1クリックでコード修正を適用可能。
- **コンテキスト対応補完**: キーワードや組み込み型に詳細なドキュメントとシグネチャを付与。末尾ドット（`runtime.`, `vision.` 等）に応じた専用メンバー補完を提供。
- **リッチな Markdown ホバー**: シンタックスハイライト付きコードブロック、完全なシグネチャ、可視性、モジュール情報を Markdown ツールチップとして表示。
- **高精度な定義ジャンプ**: ローカル宣言、関数、モデル、モジュール間シンボル定義への正確なジャンプをサポート。
