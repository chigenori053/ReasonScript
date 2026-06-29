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
}
