/**
 * Builds a SourceModelViewModel from the surface AST.
 * Specification: reasonscript-ide-runtime-visualization/0.1 §7
 */
import type {
  SourceModelViewModel,
  SourceModelEntryViewModel,
  SourceDeclarationViewModel,
  ConstructStatus,
} from "./viewModels";

const NODE_TYPE_TO_KIND: Record<string, SourceDeclarationViewModel["kind"]> = {
  FunctionDeclarationNode: "function",
  CalculationNode: "calculation",
  StateNode: "state",
  GoalNode: "goal",
  ConstraintNode: "constraint",
  TransitionNode: "transition",
  StructNode: "struct",
  EnumNode: "enum",
  ConstNode: "const",
};

function classifyConstruct(sourceKind: string, nodeType: string): ConstructStatus {
  const keyword = sourceKind || (nodeType === "ModuleNode" ? "module" : "model");
  if (keyword === "model") return "preferred";
  if (keyword === "module") return "compatible";
  if (["world", "system", "component"].includes(keyword)) return "reserved";
  return "compatible";
}

function buildDeclarationSignature(node: Record<string, unknown>): string | undefined {
  const nodeType = node.node_type as string;
  if (nodeType === "FunctionDeclarationNode") {
    const params = Array.isArray(node.parameters)
      ? (node.parameters as Array<Record<string, unknown>>)
          .map((p) => `${p.name}: ${p.type}`)
          .join(", ")
      : "";
    const ret = node.return_type ? ` -> ${node.return_type}` : "";
    return `(${params})${ret}`;
  }
  return undefined;
}

function buildDeclarations(body: unknown[]): SourceDeclarationViewModel[] {
  const result: SourceDeclarationViewModel[] = [];
  for (const node of body) {
    if (!node || typeof node !== "object") continue;
    const n = node as Record<string, unknown>;
    const nodeType = n.node_type as string;
    const kind = NODE_TYPE_TO_KIND[nodeType] ?? "other";
    const name = (n.name as string) ?? nodeType;
    result.push({
      kind,
      name,
      signature: buildDeclarationSignature(n),
    });
  }
  return result;
}

export function buildSourceModel(surfaceAst: unknown): SourceModelViewModel {
  if (!surfaceAst || typeof surfaceAst !== "object") {
    return { entries: [] };
  }

  const ast = surfaceAst as Record<string, unknown>;
  const modules = Array.isArray(ast.modules) ? ast.modules : [];

  const entries: SourceModelEntryViewModel[] = modules.map((mod) => {
    const m = mod as Record<string, unknown>;
    const nodeType = (m.node_type as string) ?? "ModuleNode";
    const sourceKind = (m.source_kind as string) ?? "";
    const name = (m.name as string) ?? "(unnamed)";
    const body = Array.isArray(m.body) ? m.body : [];

    return {
      construct: sourceKind || (nodeType === "ModelNode" ? "model" : "module"),
      name,
      status: classifyConstruct(sourceKind, nodeType),
      declarations: buildDeclarations(body),
    };
  });

  return { entries };
}
