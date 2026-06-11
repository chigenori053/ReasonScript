use std::fmt;

#[derive(Clone, Debug, PartialEq)]
pub enum RuntimeError {
    EmptyCandidates,
    InvalidProbability(String),
    InvalidSemanticVector(String),
    InvalidEvidence(String),
    NoAvailableStrategy,
    StrategyUnavailable(String),
    ExpectedAmbiguousState,
    ExpectedStableState,
    TransitionNotFound {
        source: String,
        relation: String,
    },
    TransitionDecisionRequired {
        source: String,
        candidate_count: usize,
    },
    GraphNodeNotFound(String),
    GraphNodeAlreadyExists(String),
    GraphPathNotFound {
        start: String,
        target: String,
    },
    GraphDecisionRequired {
        source: String,
        candidate_count: usize,
    },
    GraphCycleDetected {
        nodes: Vec<String>,
    },
    InvalidMathematicalExpression(String),
    UnitMismatch {
        left: String,
        right: String,
    },
    TraceSerialization(String),
}

impl fmt::Display for RuntimeError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::EmptyCandidates => write!(formatter, "ambiguous state has no candidates"),
            Self::InvalidProbability(candidate) => {
                write!(formatter, "invalid probability for candidate {candidate}")
            }
            Self::InvalidSemanticVector(candidate) => {
                write!(
                    formatter,
                    "invalid semantic vector for candidate {candidate}"
                )
            }
            Self::InvalidEvidence(label) => write!(formatter, "invalid evidence {label}"),
            Self::NoAvailableStrategy => write!(formatter, "no resolution strategy is available"),
            Self::StrategyUnavailable(strategy) => {
                write!(formatter, "resolution strategy {strategy} is unavailable")
            }
            Self::ExpectedAmbiguousState => write!(formatter, "expected an ambiguous state"),
            Self::ExpectedStableState => write!(formatter, "expected a stable state"),
            Self::TransitionNotFound { source, relation } => {
                write!(formatter, "no transition from {source} via {relation}")
            }
            Self::TransitionDecisionRequired {
                source,
                candidate_count,
            } => write!(
                formatter,
                "transition decision required for {source}: {candidate_count} candidates"
            ),
            Self::GraphNodeNotFound(node) => write!(formatter, "graph node not found: {node}"),
            Self::GraphNodeAlreadyExists(node) => {
                write!(formatter, "graph node already exists: {node}")
            }
            Self::GraphPathNotFound { start, target } => {
                write!(formatter, "no graph path from {start} to {target}")
            }
            Self::GraphDecisionRequired {
                source,
                candidate_count,
            } => write!(
                formatter,
                "graph decision required for {source}: {candidate_count} candidates"
            ),
            Self::GraphCycleDetected { nodes } => {
                write!(formatter, "graph cycle detected: {}", nodes.join(" -> "))
            }
            Self::InvalidMathematicalExpression(message) => {
                write!(formatter, "invalid mathematical expression: {message}")
            }
            Self::UnitMismatch { left, right } => {
                write!(formatter, "unit mismatch: {left} != {right}")
            }
            Self::TraceSerialization(message) => {
                write!(formatter, "trace serialization failed: {message}")
            }
        }
    }
}

impl std::error::Error for RuntimeError {}
