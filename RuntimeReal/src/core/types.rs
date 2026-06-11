use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum UnitType {
    Symbolic,
    Real,
    Vector,
    Tensor,
    Composite,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum StateType {
    Concept,
    Event,
    Object,
    Action,
    Attribute,
    Goal,
    Constraint,
    Unknown,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum RelationType {
    IsA,
    PartOf,
    Cause,
    Similar,
    Temporal,
    Spatial,
    Dependency,
    Constraint,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum TransitionType {
    Deduction,
    Induction,
    Abduction,
    Search,
    Optimization,
    Simulation,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum GraphType {
    KnowledgeGraph,
    MemoryGraph,
    WorldGraph,
    ReasonGraph,
    PlanningGraph,
}

// Re-exporting legacy Type as StateType for transition period if needed
pub type Type = StateType;
