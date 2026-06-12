import type { ModuleNode } from "../../dto/typescript/index";
import { roundTrip } from "../../dto/typescript/index";

declare const require: (name: string) => {
  readFileSync(path: string, encoding: string): string;
};
declare const process: {
  argv: string[];
  stdout: { write(value: string): void };
};

const { readFileSync } = require("node:fs");
const source = JSON.parse(readFileSync(process.argv[2], "utf8")) as ModuleNode;
process.stdout.write(JSON.stringify(roundTrip(source)));
