pub mod ambiguity;
pub mod closure;
pub mod decision;
pub mod error;
pub mod graph;
pub mod graph_ir;
pub mod resolver;
pub mod runtime;
pub mod state;
pub mod strategy;
pub mod trace;
pub mod transition;

pub use ambiguity::{AmbiguityEvaluator, AmbiguityObservation};
pub use closure::{
    ClosureResult, ClosureTraceEventKind, ClosureTraceLogger, ClosureTraceRecord,
    GraphClosureEngine, MathClosureEngine, MathValue,
};
pub use decision::{
    DecisionEngine, DecisionInput, DecisionResult, GraphDecisionInput, GraphDecisionResult,
    GraphPathCandidate, RiskPolicy, StrategyKind, TransitionDecisionInput,
    TransitionDecisionResult,
};
pub use error::RuntimeError;
pub use graph::{
    GraphRelation, GraphTraceEventKind, GraphTraceLogger, GraphTraceRecord, ReasonGraph,
    ReasonGraphRuntime,
};
pub use graph_ir::{
    GraphIR, GraphIRClosure, GraphIRConversionType, GraphIRConverter, GraphIRNode,
    GraphIRProvenance, GraphIRReconstruction, GraphIRRelation, GraphIRTraceEventKind,
    GraphIRTraceLogger, GraphIRTraceRecord,
};
pub use resolver::IdentityResolver;
pub use runtime::HybridRuntime;
pub use state::{
    AmbiguousState, Candidate, Evidence, HybridReasonUnit, StableState, State, StateKind,
    StateManager, StatePayload,
};
pub use strategy::{
    ClarifyStrategy, ComplexStrategy, RealStrategy, ResolutionOutcome, ResolutionStrategy,
};
pub use trace::{TraceEventKind, TraceLogger, TraceRecord};
pub use transition::{Transition, TransitionCandidate, TransitionEngine};
