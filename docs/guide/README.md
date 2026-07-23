# ReasonScript Guide / ガイド

Entry point for engineers new to ReasonScript. `docs/` contains the full set
of normative specifications and validation reports; start here for an
organized on-ramp before diving into them.

新しく ReasonScript に触れるエンジニア向けの入り口です。`docs/` には規範的
な仕様書と検証レポートが多数含まれていますが、まずはここから読み始めること
を推奨します。

| Document | 文書 | Contents / 内容 |
|---|---|---|
| [`concepts.en.md`](concepts.en.md) | [`concepts.ja.md`](concepts.ja.md) | Core concepts: the Semantic Language pipeline, determinism guarantees, State/Goal/Transition/Rollback, what is out of scope. / コアコンセプト: 意味言語パイプライン、決定性の保証、State/Goal/Transition/Rollback、スコープ外事項。 |
| [`basic-usage.en.md`](basic-usage.en.md) | [`basic-usage.ja.md`](basic-usage.ja.md) | Basic usage and specification: toolchain, project layout, modules, declarations, transitions, calculations, statements, expressions, functions, pattern matching. / 基本的な使い方と仕様: ツールチェイン、プロジェクト構成、モジュール、宣言、transition、calculation、文、式、関数、パターンマッチ。 |

Read `concepts` first, then `basic-usage`. Both assume senior-engineer-level
familiarity with compilers, ASTs, and type systems, and link out to the
normative specification files in `docs/` for exact rule numbers and edge
cases.

まず `concepts` を読み、その後 `basic-usage` を読んでください。両文書とも
コンパイラ・AST・型システムに関するシニアエンジニア相当の知識を前提とし、
正確な規則番号やエッジケースについては `docs/` 内の規範仕様書へのリンクを
参照します。
