package astdto

import "encoding/json"

type GoalNode struct {
	NodeType string `json:"node_type"`
	NodeID   string `json:"node_id"`
	Kind     string `json:"kind"`
	Target   string `json:"target"`
}

type StateNode struct {
	NodeType  string          `json:"node_type"`
	NodeID    string          `json:"node_id"`
	StateID   string          `json:"state_id"`
	StateType string          `json:"state_type"`
	Data      json.RawMessage `json:"data"`
}

type TransitionNode struct {
	NodeType      string          `json:"node_type"`
	NodeID        string          `json:"node_id"`
	TransitionID  string          `json:"transition_id"`
	Source        string          `json:"source"`
	Relation      string          `json:"relation"`
	Target        string          `json:"target"`
	ExpectedCost  *float64        `json:"expected_cost,omitempty"`
	Guard         *string         `json:"guard,omitempty"`
	Effect        json.RawMessage `json:"effect,omitempty"`
}

type ConstraintNode struct {
	NodeType     string `json:"node_type"`
	NodeID       string `json:"node_id"`
	ConstraintID string `json:"constraint_id"`
	Kind         string `json:"kind"`
	Expression   string `json:"expression"`
}

type ContextNode struct {
	NodeType    string `json:"node_type"`
	NodeID      string `json:"node_id"`
	ContextID   string `json:"context_id"`
	ContextType string `json:"context_type"`
	URI         string `json:"uri"`
}

type MetadataNode struct {
	NodeType string          `json:"node_type"`
	NodeID   string          `json:"node_id"`
	Key      string          `json:"key"`
	Value    json.RawMessage `json:"value"`
}

type ModuleNode struct {
	NodeType     string            `json:"node_type"`
	Version      string            `json:"version"`
	NodeID       string            `json:"node_id"`
	Imports      []string          `json:"imports,omitempty"`
	Declarations []json.RawMessage `json:"declarations"`
	Metadata     []MetadataNode    `json:"metadata,omitempty"`
}
