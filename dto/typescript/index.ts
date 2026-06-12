export type JsonValue =
  | null
  | boolean
  | number
  | string
  | readonly JsonValue[]
  | { readonly [key: string]: JsonValue };

export interface StateSnapshot {
  readonly state_id: string;
  readonly state_type: string;
  readonly data: JsonValue;
}

export interface GoalSpec {
  readonly kind: string;
  readonly target: string;
}

export interface ContextRef {
  readonly context_id: string;
  readonly context_type: string;
  readonly uri?: string | null;
}

export interface ConstraintSpec {
  readonly constraint_id: string;
  readonly kind: string;
  readonly expression: string;
}

export interface TransitionSpec {
  readonly transition_id: string;
  readonly source: string;
  readonly relation: string;
  readonly target: string;
  readonly expected_cost: number;
  readonly guard?: string | null;
  readonly effect?: JsonValue;
}

export interface PlannerPolicy {
  readonly strategy: string;
  readonly max_depth?: number | null;
  readonly max_alternatives?: number | null;
}

export interface ExecutionPolicy {
  readonly max_steps: number;
  readonly rollback_on_failure: boolean;
  readonly constraint_mode: string;
}

export interface TracePolicy {
  readonly level: string;
  readonly include_alternatives: boolean;
  readonly include_state_data: boolean;
}

export interface ReasonIR {
  readonly schema_version: "reason-ir/0.1";
  readonly initial_state: StateSnapshot;
  readonly goal: GoalSpec;
  readonly context_refs?: readonly ContextRef[];
  readonly constraints?: readonly ConstraintSpec[];
  readonly transitions: readonly TransitionSpec[];
  readonly planner_policy?: PlannerPolicy | null;
  readonly execution_policy: ExecutionPolicy;
  readonly trace_policy: TracePolicy;
  readonly metadata?: Readonly<Record<string, JsonValue>>;
}

export interface PlanStep {
  readonly step_id: string;
  readonly transition_id: string;
  readonly source: string;
  readonly target: string;
}

export interface PlanPath {
  readonly step_ids: readonly string[];
  readonly expected_cost: number;
}

export interface ExecutionPlan {
  readonly selected_steps: readonly PlanStep[];
  readonly alternative_paths: readonly PlanPath[];
  readonly expected_cost: number;
  readonly evidence_refs: readonly string[];
  readonly planner_version: string;
}

// A bigint codec must emit this as an unquoted JSON integer token.
export interface StateDelta {
  readonly delta_id: string;
  readonly before_state: StateSnapshot;
  readonly after_state: StateSnapshot;
  readonly applied_transition: string;
  readonly timestamp: bigint;
}

export type InferenceStatus =
  | "completed"
  | "rejected"
  | "decision_required"
  | "failed";

export interface Proof {
  readonly selected_step_ids: readonly string[];
  readonly evidence_refs: readonly string[];
}

export interface Violation {
  readonly constraint_id: string;
  readonly message: string;
}

export interface InferenceResult {
  readonly status: InferenceStatus;
  readonly final_state: StateSnapshot;
  readonly state_deltas: readonly StateDelta[];
  readonly proof: Proof | null;
  readonly violations: readonly Violation[];
  readonly alternatives: readonly PlanPath[];
  readonly trace_id: string;
}

export type TraceEvent =
  | {
      readonly event_type: "plan_selected";
      readonly step_ids: readonly string[];
      readonly expected_cost: number;
    }
  | {
      readonly event_type: "state_delta_applied";
      readonly delta_id: string;
      readonly transition_id: string;
      readonly transaction_id?: string | null;
    }
  | {
      readonly event_type: "constraint_violation";
      readonly constraint_id: string;
      readonly message: string;
    }
  | {
      readonly event_type: "evidence_observed";
      readonly evidence_ref: string;
    }
  | {
      readonly event_type: "tool_invoked";
      readonly tool_ref: string;
      readonly result_ref: string;
    };

export interface Trace {
  readonly request_id: string;
  readonly reason_ir_version: "reason-ir/0.1";
  readonly planner_version: string | null;
  readonly policy_version: string;
  readonly events: readonly TraceEvent[];
}

export type TransactionStatus =
  | "prepared"
  | "accepted"
  | "rejected"
  | "committed"
  | "rolled_back";

export interface TransactionRecord {
  readonly transaction_id: string;
  readonly execution_plan_id: string;
  readonly candidate_id: string;
  readonly delta_id: string | null;
  readonly status: TransactionStatus;
  readonly commit_timestamp: bigint | null;
  readonly validation_failures: readonly string[];
  readonly source_delta_id: string | null;
}
