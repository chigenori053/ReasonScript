/**
 * Monaco language registration for ReasonScript.
 *
 * Specification: reasonscript-ide-compatibility/0.6-D §10
 * Call this function in the Monaco `beforeMount` callback before the editor renders.
 */
import type * as Monaco from "monaco-editor";
import { REASONSCRIPT_LANGUAGE_ID, monarchTokenizer } from "./reasonscriptMonarch";

export { REASONSCRIPT_LANGUAGE_ID };

export function registerReasonScriptLanguage(monaco: typeof Monaco): void {
  monaco.languages.register({
    id: REASONSCRIPT_LANGUAGE_ID,
    extensions: [".rsn", ".reason"],
    aliases: ["ReasonScript", "reasonscript"],
  });

  monaco.languages.setMonarchTokensProvider(
    REASONSCRIPT_LANGUAGE_ID,
    monarchTokenizer,
  );

  monaco.languages.setLanguageConfiguration(REASONSCRIPT_LANGUAGE_ID, {
    comments: {
      lineComment: "//",
      blockComment: ["/*", "*/"],
    },
    brackets: [
      ["{", "}"],
      ["[", "]"],
      ["(", ")"],
    ],
    autoClosingPairs: [
      { open: "{", close: "}" },
      { open: "[", close: "]" },
      { open: "(", close: ")" },
      { open: '"', close: '"', notIn: ["string"] },
    ],
    surroundingPairs: [
      { open: "{", close: "}" },
      { open: "[", close: "]" },
      { open: "(", close: ")" },
      { open: '"', close: '"' },
    ],
    indentationRules: {
      increaseIndentPattern: /^.*\{[^}"']*$/,
      decreaseIndentPattern: /^\s*\}/,
    },
  });

  monaco.languages.registerCompletionItemProvider(REASONSCRIPT_LANGUAGE_ID, {
    provideCompletionItems: (model, position) => {
      const word = model.getWordUntilPosition(position);
      const range = new monaco.Range(
        position.lineNumber,
        word.startColumn,
        position.lineNumber,
        word.endColumn,
      );
      return {
      suggestions: [
        {
          label: "vision.infer",
          kind: monaco.languages.CompletionItemKind.Function,
          insertText: 'vision.infer("${1:model.json}", "${2:image.png}")',
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: "Run the configured Rust Vision backend and return VisionObservation.",
          range,
        },
        {
          label: "vision.build_ruo",
          kind: monaco.languages.CompletionItemKind.Function,
          insertText: 'vision.build_ruo(${1:observation}, "${2:output.ruo}")',
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: "Build and atomically publish a canonical ReasonUnitObject.",
          range,
        },
      ],
    };
    },
  });
}
