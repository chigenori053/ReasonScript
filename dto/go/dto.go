package dto

import "encoding/json"

type StateSnapshot struct {
	StateID   string          `json:"state_id"`
	StateType string          `json:"state_type"`
	Data      json.RawMessage `json:"data"`
}

type GoalSpec struct {
	Kind   string `json:"kind"`
	Target string `json:"target"`
}

type ContextRef struct {
	ContextID   string  `json:"context_id"`
	ContextType string  `json:"context_type"`
	URI         *string `json:"uri,omitempty"`
}

type ConstraintSpec struct {
	ConstraintID string `json:"constraint_id"`
	Kind         string `json:"kind"`
	Expression   string `json:"expression"`
}

type TransitionSpec struct {
	TransitionID string          `json:"transition_id"`
	Source       string          `json:"source"`
	Relation     string          `json:"relation"`
	Target       string          `json:"target"`
	ExpectedCost float64         `json:"expected_cost"`
	Guard        *string         `json:"guard,omitempty"`
	Effect       json.RawMessage `json:"effect,omitempty"`
}

type PlannerPolicy struct {
	Strategy        string  `json:"strategy"`
	MaxDepth        *uint64 `json:"max_depth,omitempty"`
	MaxAlternatives *uint64 `json:"max_alternatives,omitempty"`
}

type ExecutionPolicy struct {
	MaxSteps          uint64 `json:"max_steps"`
	RollbackOnFailure bool   `json:"rollback_on_failure"`
	ConstraintMode    string `json:"constraint_mode"`
}

type TracePolicy struct {
	Level               string `json:"level"`
	IncludeAlternatives bool   `json:"include_alternatives"`
	IncludeStateData    bool   `json:"include_state_data"`
}

type ReasonIR struct {
	SchemaVersion   string                     `json:"schema_version"`
	InitialState    StateSnapshot              `json:"initial_state"`
	Goal            GoalSpec                   `json:"goal"`
	ContextRefs     []ContextRef               `json:"context_refs,omitempty"`
	Constraints     []ConstraintSpec           `json:"constraints,omitempty"`
	Transitions     []TransitionSpec           `json:"transitions"`
	PlannerPolicy   *PlannerPolicy             `json:"planner_policy,omitempty"`
	ExecutionPolicy ExecutionPolicy            `json:"execution_policy"`
	TracePolicy     TracePolicy                `json:"trace_policy"`
	Metadata        map[string]json.RawMessage `json:"metadata,omitempty"`
}

type PlanStep struct {
	StepID       string `json:"step_id"`
	TransitionID string `json:"transition_id"`
	Source       string `json:"source"`
	Target       string `json:"target"`
}

type PlanPath struct {
	StepIDs      []string `json:"step_ids"`
	ExpectedCost float64  `json:"expected_cost"`
}

type ExecutionPlan struct {
	SelectedSteps    []PlanStep `json:"selected_steps"`
	AlternativePaths []PlanPath `json:"alternative_paths"`
	ExpectedCost     float64    `json:"expected_cost"`
	EvidenceRefs     []string   `json:"evidence_refs"`
	PlannerVersion   string     `json:"planner_version"`
}

type StateDelta struct {
	DeltaID           string        `json:"delta_id"`
	BeforeState       StateSnapshot `json:"before_state"`
	AfterState        StateSnapshot `json:"after_state"`
	AppliedTransition string        `json:"applied_transition"`
	Timestamp         uint64        `json:"timestamp"`
}

type Proof struct {
	SelectedStepIDs []string `json:"selected_step_ids"`
	EvidenceRefs    []string `json:"evidence_refs"`
}

type Violation struct {
	ConstraintID string `json:"constraint_id"`
	Message      string `json:"message"`
}

type InferenceResult struct {
	Status       string        `json:"status"`
	FinalState   StateSnapshot `json:"final_state"`
	StateDeltas  []StateDelta  `json:"state_deltas"`
	Proof        *Proof        `json:"proof"`
	Violations   []Violation   `json:"violations"`
	Alternatives []PlanPath   `json:"alternatives"`
	TraceID      string        `json:"trace_id"`
}

type Trace struct {
	RequestID       string            `json:"request_id"`
	ReasonIRVersion string            `json:"reason_ir_version"`
	PlannerVersion *string           `json:"planner_version"`
	PolicyVersion  string            `json:"policy_version"`
	Events         []json.RawMessage `json:"events"`
}

type TransactionRecord struct {
	TransactionID      string   `json:"transaction_id"`
	ExecutionPlanID    string   `json:"execution_plan_id"`
	CandidateID        string   `json:"candidate_id"`
	DeltaID            *string  `json:"delta_id"`
	Status             string   `json:"status"`
	CommitTimestamp    *uint64  `json:"commit_timestamp"`
	ValidationFailures []string `json:"validation_failures"`
	SourceDeltaID      *string  `json:"source_delta_id"`
}
