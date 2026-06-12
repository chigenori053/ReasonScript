import type { ReasonIR } from "../../dto/typescript/index";

declare const require: (name: string) => {
  readFileSync(path: string, encoding: string): string;
};
declare const process: {
  argv: string[];
  stdout: { write(value: string): void };
};

const { readFileSync } = require("node:fs");
const input = JSON.parse(readFileSync(process.argv[2], "utf8")) as ReasonIR;
if (input.schema_version !== "reason-ir/0.1") {
  throw new Error(`unsupported ABI version: ${input.schema_version}`);
}
if (!input.initial_state || !input.goal || !Array.isArray(input.transitions)) {
  throw new Error("missing required ReasonIR field");
}
const ids = new Set<string>();
for (const transition of input.transitions) {
  if (ids.has(transition.transition_id)) {
    throw new Error(`duplicate transition_id: ${transition.transition_id}`);
  }
  if (!Number.isFinite(transition.expected_cost) || transition.expected_cost < 0) {
    throw new Error("expected_cost must be finite and non-negative");
  }
  ids.add(transition.transition_id);
}
process.stdout.write(JSON.stringify(input));
