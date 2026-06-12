export type JsonValue =
  | null
  | boolean
  | number
  | string
  | readonly JsonValue[]
  | { readonly [key: string]: JsonValue };

export interface GoalNode {
  readonly node_type: "GoalNode";
  readonly node_id: string;
  readonly kind: string;
  readonly target: string;
}

export interface StateNode {
  readonly node_type: "StateNode";
  readonly node_id: string;
  readonly state_id: string;
  readonly state_type: string;
  readonly data: JsonValue;
}

export interface TransitionNode {
  readonly node_type: "TransitionNode";
  readonly node_id: string;
  readonly transition_id: string;
  readonly source: string;
  readonly relation: string;
  readonly target: string;
  readonly expected_cost?: number;
  readonly guard?: string | null;
  readonly effect?: JsonValue;
}

export interface ConstraintNode {
  readonly node_type: "ConstraintNode";
  readonly node_id: string;
  readonly constraint_id: string;
  readonly kind: string;
  readonly expression: string;
}

export interface ContextNode {
  readonly node_type: "ContextNode";
  readonly node_id: string;
  readonly context_id: string;
  readonly context_type: string;
  readonly uri: string;
}

export interface MetadataNode {
  readonly node_type: "MetadataNode";
  readonly node_id: string;
  readonly key: string;
  readonly value: JsonValue;
}

export type DeclarationNode =
  | GoalNode
  | StateNode
  | TransitionNode
  | ConstraintNode
  | ContextNode;

export interface ModuleNode {
  readonly node_type: "ModuleNode";
  readonly version: "reasonscript-ast/0.1";
  readonly node_id: string;
  readonly imports?: readonly string[];
  readonly declarations: readonly DeclarationNode[];
  readonly metadata?: readonly MetadataNode[];
}

export function roundTrip(value: ModuleNode): ModuleNode {
  return JSON.parse(JSON.stringify(value)) as ModuleNode;
}
