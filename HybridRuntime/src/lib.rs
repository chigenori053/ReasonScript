pub mod ambiguity;
pub mod closure;
pub mod decision;
pub mod error;
pub mod graph;
pub mod graph_ir;
pub mod reason_ir;
pub mod resolver;
pub mod runtime;
pub mod semantic_closure;
pub mod semantic_constraint;
pub mod semantic_contradiction;
pub mod semantic_planning;
pub mod semantic_search;
pub mod semantic_similarity;
pub mod semantic_simulation;
pub mod semantic_transformation;
pub mod semantic_type;
pub mod state;
pub mod strategy;
pub mod trace;
pub mod transaction;
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
pub use reason_ir::{
    ConstraintSpec, ContextRef, ExecutionPlan, ExecutionPolicy, GoalSpec, InferenceResult,
    InferenceStatus, MinimalReasonIR, PlanPath, PlanStep, PlannerPolicy, Proof, ReasonIR,
    ReasonIrError, ReasonIrValidator, StateDelta, StateKernel, StateSnapshot, Trace, TraceEvent,
    TracePolicy, TransitionSpec, Violation, REASON_IR_SCHEMA_ID, REASON_IR_VERSION,
};
pub use resolver::IdentityResolver;
pub use runtime::HybridRuntime;
pub use semantic_closure::{
    ClosureMetadata, SemanticClosure, SemanticClosureConstraintIr, SemanticClosureEngine,
    SemanticClosureError, SemanticClosureIrNode, SEMANTIC_CLOSURE_NODE, SEMANTIC_CLOSURE_VERSION,
};
pub use semantic_constraint::{
    ConstraintKind, ConstraintPolarity, SemanticConstraint, SemanticConstraintDeclaration,
    SemanticConstraintError, SemanticConstraintId, SemanticConstraintIrNode,
    SemanticConstraintRegistry, SEMANTIC_CONSTRAINT_NODE,
};
pub use semantic_contradiction::{
    ConsistencyStatus, ContradictionKind, SemanticContradiction, SemanticContradictionEngine,
    SemanticContradictionError, SemanticContradictionIrNode, SemanticValidationReport,
    SemanticValidationReportIrNode, SEMANTIC_CONTRADICTION_NODE, SEMANTIC_CONTRADICTION_VERSION,
    SEMANTIC_VALIDATION_REPORT_NODE,
};
pub use semantic_planning::{
    PlanStep as SemanticPlanStep, PlanningGoal, PlanningResult, PlanningResultIrNode,
    PlanningState, SemanticPlan, SemanticPlanIrNode, SemanticPlanningEngine, SemanticPlanningError,
    PLANNING_RESULT_NODE, SEMANTIC_PLANNING_VERSION, SEMANTIC_PLAN_NODE,
};
pub use semantic_search::{
    PathSearchResult, PathSearchResultIrNode, SearchKind, SearchQuery, SearchResult,
    SearchResultIrNode, SearchResultItem, SearchResultItemIrNode, SemanticSearchEngine,
    SemanticSearchError, PATH_SEARCH_RESULT_NODE, SEARCH_RESULT_ITEM_NODE, SEARCH_RESULT_NODE,
    SEMANTIC_SEARCH_VERSION,
};
pub use semantic_similarity::{
    SemanticSimilarityEngine, SemanticSimilarityError, SimilarityReport, SimilarityReportIrNode,
    SimilarityResult, SimilarityResultIrNode, SEMANTIC_SIMILARITY_VERSION, SIMILARITY_REPORT_NODE,
    SIMILARITY_RESULT_NODE,
};
pub use semantic_simulation::{
    SemanticSimulationEngine, SemanticSimulationError, SimulationResult, SimulationResultIrNode,
    SimulationState, SimulationStep, SimulationTrace, SimulationTraceIrNode,
    SEMANTIC_SIMULATION_VERSION, SIMULATION_RESULT_NODE, SIMULATION_TRACE_NODE,
};
pub use semantic_transformation::{
    SemanticTransformationEngine, SemanticTransformationError, TransformationKind,
    TransformationPath, TransformationPathIrNode, TransformationResult, TransformationResultIrNode,
    SEMANTIC_TRANSFORMATION_VERSION, TRANSFORMATION_PATH_NODE, TRANSFORMATION_RESULT_NODE,
};
pub use semantic_type::{
    SemanticRelation, SemanticType, SemanticTypeDeclaration, SemanticTypeError, SemanticTypeId,
    SemanticTypeIrNode, SemanticTypeMetadata, SemanticTypeRegistry, IS_A_RELATION,
    SEMANTIC_RELATION_NODE, SEMANTIC_TYPE_DECLARATION_NODE, SEMANTIC_TYPE_NODE,
};
pub use state::{
    AmbiguousState, Candidate, Evidence, HybridReasonUnit, StableState, State, StateKind,
    StateManager, StatePayload,
};
pub use strategy::{
    ClarifyStrategy, ComplexStrategy, RealStrategy, ResolutionOutcome, ResolutionStrategy,
};
pub use trace::{TraceEventKind, TraceLogger, TraceRecord};
pub use transaction::{
    PreparedDelta, TransactionKernel, TransactionRecord, TransactionStatus, ValidationChecks,
    ValidationStatus,
};
pub use transition::{Transition, TransitionCandidate, TransitionEngine};
