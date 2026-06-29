/**
 * Monarch tokenizer for ReasonScript.
 *
 * Specification: reasonscript-ide-compatibility/0.6-D §10
 * Language Surface: v0.5 + v0.6-B/C/D
 */
import type * as monaco from "monaco-editor";

export const REASONSCRIPT_LANGUAGE_ID = "reasonscript";

/** Keywords that are active in the current language version. */
const ACTIVE_KEYWORDS = [
  // Top-level constructs — model preferred (v0.6-C), module compatible (v0.6-B)
  "model", "module",
  // Declarations
  "pub", "fn", "struct", "enum", "calculation",
  "goal", "state", "constraint", "transition", "relation",
  // Module system
  "package", "import", "export", "const", "let",
  "reason_graph", "execution_plan",
  // Control flow
  "if", "elif", "else", "match", "when",
  "for", "while", "loop", "break", "continue", "return",
  // Runtime operations
  "input", "print", "search", "simulate", "predict", "plan",
  // Legacy
  "requires", "reach",
];

/** Keywords reserved for future language versions — not active in v0.6-D. */
const RESERVED_KEYWORDS = ["world", "system", "component"];

/** Literal keyword values. */
const LITERAL_KEYWORDS = ["true", "false", "some", "none"];

/** Built-in type identifiers. */
const TYPE_IDENTIFIERS = [
  "Goal", "State", "Constraint", "ReasonGraph", "ExecutionPlan",
  "World", "Scene", "Entity", "Object", "Geometry", "Relation",
  "Event", "Snapshot", "SceneTemplate", "SimulationTrace",
  "Planner", "Plan", "PlanStep", "PlanResult",
  "Agent", "Task", "Decision", "Action", "Tool", "AgentResult",
];

export const monarchTokenizer: monaco.languages.IMonarchLanguage = {
  keywords: ACTIVE_KEYWORDS,
  reservedKeywords: RESERVED_KEYWORDS,
  literals: LITERAL_KEYWORDS,
  typeIdentifiers: TYPE_IDENTIFIERS,

  symbols: /[=><!~?:&|+\-*\/\^%]+/,

  tokenizer: {
    root: [
      // Line comments
      [/\/\/.*$/, "comment"],
      // Block comments
      [/\/\*/, "comment", "@blockComment"],
      // Strings
      [/"/, "string", "@string"],
      // Range operators (before numbers to avoid ambiguity)
      [/\.\.\.?<?\b/, "operator"],
      // Float literals
      [/\b\d+\.\d+\b/, "number.float"],
      // Integer literals
      [/\b\d+\b/, "number"],
      // Identifiers, keywords, literals, types
      [
        /[A-Za-z_][A-Za-z0-9_]*/,
        {
          cases: {
            "@reservedKeywords": "keyword.other.reserved",
            "@literals": "constant.language",
            "@keywords": "keyword",
            "@typeIdentifiers": "type.identifier",
            "@default": "identifier",
          },
        },
      ],
      // Operators and symbols
      [/@symbols/, "operator"],
      // Brackets
      [/[{}()\[\]]/, "@brackets"],
      // Whitespace
      [/\s+/, "white"],
    ],
    blockComment: [
      [/[^/*]+/, "comment"],
      [/\*\//, "comment", "@pop"],
      [/[/*]/, "comment"],
    ],
    string: [
      [/[^\\"]+/, "string"],
      [/\\./, "string.escape.invalid"],
      [/"/, "string", "@pop"],
    ],
  },
};
