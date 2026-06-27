import type * as Monaco from "monaco-editor";
import type { SourceSpan } from "../types";

/** SourceSpan uses 0-based lines internally (from DTO); Monaco uses 1-based. */
function toMonacoRange(span: SourceSpan): Monaco.IRange {
  return {
    startLineNumber: span.start_line + 1,
    startColumn: span.start_column + 1,
    endLineNumber: span.end_line + 1,
    endColumn: span.end_column + 1,
  };
}

let decorationIds: string[] = [];

export function revealSourceSpan(
  editor: Monaco.editor.IStandaloneCodeEditor,
  span: SourceSpan | null | undefined
): void {
  if (!span) return;

  const range = toMonacoRange(span);

  // Clear previous decoration
  decorationIds = editor.deltaDecorations(decorationIds, []);

  // Reveal and select
  editor.revealRangeInCenter(range, 0 /* Smooth */);
  editor.setSelection(range);

  // Apply highlight decoration
  decorationIds = editor.deltaDecorations([], [
    {
      range,
      options: {
        className: "ide-source-highlight",
        isWholeLine: false,
        overviewRuler: {
          color: "#3b82f6",
          position: 4 /* Right */,
        },
      },
    },
  ]);

  // Auto-clear after 3 seconds
  setTimeout(() => {
    decorationIds = editor.deltaDecorations(decorationIds, []);
  }, 3000);
}

/**
 * Symbol-based fallback: search for the first occurrence of `symbol` in the
 * editor text and reveal that line.
 */
export function revealSymbolFallback(
  editor: Monaco.editor.IStandaloneCodeEditor,
  symbol: string
): boolean {
  if (!symbol) return false;
  const model = editor.getModel();
  if (!model) return false;

  const text = model.getValue();
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].includes(symbol)) {
      const col = lines[i].indexOf(symbol);
      const span: SourceSpan = {
        uri: "",
        start_line: i,
        start_column: col,
        end_line: i,
        end_column: col + symbol.length,
      };
      revealSourceSpan(editor, span);
      return true;
    }
  }
  return false;
}

export function clearSourceHighlight(
  editor: Monaco.editor.IStandaloneCodeEditor
): void {
  decorationIds = editor.deltaDecorations(decorationIds, []);
}
