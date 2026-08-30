# ReasonScript String & Collection Standard Library Specification v0.1
# ReasonScript 文字列・コレクション標準ライブラリ仕様書 v0.1

- **Spec ID / 仕様ID:** `reasonscript-spec-string-collection/v0.1`
- **Status / 状態:** APPROVED / 確定
- **Target / 対象:** Language Surface, Computation IR (0.2), Rust VM, Python AST Runtime

---

## 1. Overview / 概要

### English
This specification defines the standard library functions for `string` manipulation and `array` operations in ReasonScript. Operator overloading of `+` for string concatenation is explicitly avoided to keep type rules unambiguous and sound. Instead, explicit namespace functions under `string.*` and `array.*` are provided with deterministic evaluation semantics across both Python AST/IR and native Rust VM execution.

### 日本語
本文書は、ReasonScriptにおける文字列操作（`string`）および配列操作（`array`）の標準組み込み関数仕様を定義します。型推論規則の曖昧性を排除し健全性を維持するため、`+` 演算子の文字列連結へのオーバーロードは行わず、明示的な名前空間 `string.*` および `array.*` の組み込み関数を提供します。Python AST/IR および Rust ネイティブ VM の双方で決定的な挙動パリティを保証します。

---

## 2. String Standard Library API / 文字列標準ライブラリ API

| Function Signature / 関数シグネチャ | Description (EN) | 説明 (JA) | Diagnostic Code on Type Error / 型エラー時診断 |
| :--- | :--- | :--- | :--- |
| `string.concat(a: string, b: string) -> string` | Concatenates two strings into a new string. | 2つの文字列を連結した新文字列を返却。 | `STR-002` |
| `string.join(sep: string, items: [string]) -> string` | Joins an array of strings with a separator. | 文字列配列の各要素を区切り文字で結合した文字列を返却。 | `STR-002` |
| `string.length(s: string) -> int` | Returns Unicode character count of string. | 文字列のUnicode文字数を返却。 | `STR-002` |
| `string.from_int(n: int) -> string` | Converts integer to decimal string representation. | 整数値を10進表記の文字列に変換。 | `STR-002` |
| `string.from_float(f: float) -> string` | Converts float to string representation. | 浮動小数点数を文字列に変換。 | `STR-002` |
| `string.slice(s: string, start: int, end: int) -> string` | Extracts substring from start to end index (0-indexed). | 指定インデックス範囲の部分文字列を返却（0始まり）。 | `STR-002` |

---

## 3. Array Standard Library API / 配列標準ライブラリ API

| Function Signature / 関数シグネチャ | Description (EN) | 説明 (JA) | Diagnostic Code on Type Error / 型エラー時診断 |
| :--- | :--- | :--- | :--- |
| `array.concat(a: [T], b: [T]) -> [T]` | Concatenates two arrays of homogeneous type into a new array. | 同一要素型の2つの配列を連結した新配列を返却。 | `COLL-002`, `COLL-003` |
| `array.append(arr: [T], item: T) -> [T]` | Returns a new array with item appended (pure/immutable). | 要素を追加した新しい配列を返却（イミュータブル）。 | `COLL-002`, `COLL-003` |
