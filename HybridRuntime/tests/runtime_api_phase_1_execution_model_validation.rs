use std::collections::{BTreeSet, VecDeque};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ModelKind {
    Graph,
    StateSpace,
    Hybrid,
}

#[derive(Clone, Debug)]
enum Guard {
    Always,
    ConstraintClear(&'static str),
    ConstraintViolated(&'static str),
}

#[derive(Clone, Debug)]
struct IrTransition {
    source: &'static str,
    relation: &'static str,
    target: &'static str,
    cost: u32,
    evidence: &'static str,
    guard: Guard,
}

impl IrTransition {
    fn new(source: &'static str, relation: &'static str, target: &'static str) -> Self {
        Self {
            source,
            relation,
            target,
            cost: 1,
            evidence: relation,
            guard: Guard::Always,
        }
    }

    fn guarded(mut self, guard: Guard) -> Self {
        self.guard = guard;
        self
    }

    fn enabled(&self, constraints: &[&str]) -> bool {
        match self.guard {
            Guard::Always => true,
            Guard::ConstraintClear(value) => !constraints.contains(&value),
            Guard::ConstraintViolated(value) => constraints.contains(&value),
        }
    }
}

#[derive(Clone, Debug)]
struct ExecutionRequest {
    reason_unit: &'static str,
    context: Vec<&'static str>,
    constraints: Vec<&'static str>,
    goal: &'static str,
    transitions: Vec<IrTransition>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct ExecutionTrace {
    model: ModelKind,
    path: Vec<String>,
    evidence: Vec<String>,
    violations: Vec<String>,
    explored_transitions: usize,
    state_updates: usize,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct InferenceResult {
    final_state: String,
    accepted: bool,
    trace: ExecutionTrace,
}

trait ExecutionModel {
    fn kind(&self) -> ModelKind;
    fn execute(&self, request: &ExecutionRequest) -> InferenceResult;
}

struct GraphExecutionModel;
struct StateSpaceExecutionModel;
struct HybridExecutionModel;

impl ExecutionModel for GraphExecutionModel {
    fn kind(&self) -> ModelKind {
        ModelKind::Graph
    }

    fn execute(&self, request: &ExecutionRequest) -> InferenceResult {
        let search = search_paths(request);
        result_from_path(self.kind(), request, search, 0)
    }
}

impl ExecutionModel for StateSpaceExecutionModel {
    fn kind(&self) -> ModelKind {
        ModelKind::StateSpace
    }

    fn execute(&self, request: &ExecutionRequest) -> InferenceResult {
        let mut current = request.reason_unit;
        let mut path = vec![current.to_string()];
        let mut evidence = Vec::new();
        let mut explored = 0;
        let mut updates = 0;
        let mut seen = BTreeSet::from([current]);

        while current != request.goal {
            let candidates = request
                .transitions
                .iter()
                .filter(|transition| {
                    transition.source == current && transition.enabled(&request.constraints)
                })
                .collect::<Vec<_>>();
            explored += request
                .transitions
                .iter()
                .filter(|transition| transition.source == current)
                .count();
            let Some(selected) = candidates
                .into_iter()
                .min_by_key(|transition| (transition.cost, transition.target))
            else {
                break;
            };
            if !seen.insert(selected.target) {
                break;
            }
            current = selected.target;
            path.push(current.to_string());
            evidence.push(format!("{}: {}", selected.relation, selected.evidence));
            updates += 1;
        }

        result_from_parts(self.kind(), request, path, evidence, explored, updates)
    }
}

impl ExecutionModel for HybridExecutionModel {
    fn kind(&self) -> ModelKind {
        ModelKind::Hybrid
    }

    fn execute(&self, request: &ExecutionRequest) -> InferenceResult {
        let search = search_paths(request);
        let updates = search.path.len().saturating_sub(1);
        result_from_path(self.kind(), request, search, updates)
    }
}

#[derive(Clone, Debug)]
struct SearchResult {
    path: Vec<String>,
    evidence: Vec<String>,
    explored: usize,
}

fn search_paths(request: &ExecutionRequest) -> SearchResult {
    let mut queue = VecDeque::from([(
        vec![request.reason_unit.to_string()],
        Vec::<String>::new(),
        0_u32,
    )]);
    let mut explored = 0;
    let mut completed = Vec::new();

    while let Some((path, evidence, cost)) = queue.pop_front() {
        let current = path.last().expect("path always contains the initial state");
        if current == request.goal {
            completed.push((path, evidence, cost));
            continue;
        }

        for transition in request
            .transitions
            .iter()
            .filter(|transition| transition.source == current)
        {
            explored += 1;
            if !transition.enabled(&request.constraints)
                || path.iter().any(|state| state == transition.target)
            {
                continue;
            }
            let mut next_path = path.clone();
            next_path.push(transition.target.to_string());
            let mut next_evidence = evidence.clone();
            next_evidence.push(format!("{}: {}", transition.relation, transition.evidence));
            queue.push_back((next_path, next_evidence, cost + transition.cost));
        }
    }

    completed.sort_by(|left, right| {
        left.2
            .cmp(&right.2)
            .then_with(|| left.0.len().cmp(&right.0.len()))
            .then_with(|| left.0.cmp(&right.0))
    });
    let (path, evidence, _) = completed
        .into_iter()
        .next()
        .unwrap_or_else(|| (vec![request.reason_unit.to_string()], Vec::new(), 0));
    SearchResult {
        path,
        evidence,
        explored,
    }
}

fn result_from_path(
    model: ModelKind,
    request: &ExecutionRequest,
    search: SearchResult,
    state_updates: usize,
) -> InferenceResult {
    result_from_parts(
        model,
        request,
        search.path,
        search.evidence,
        search.explored,
        state_updates,
    )
}

fn result_from_parts(
    model: ModelKind,
    request: &ExecutionRequest,
    path: Vec<String>,
    evidence: Vec<String>,
    explored_transitions: usize,
    state_updates: usize,
) -> InferenceResult {
    let final_state = path
        .last()
        .cloned()
        .unwrap_or_else(|| request.reason_unit.to_string());
    let violations = request
        .constraints
        .iter()
        .filter(|constraint| request.context.contains(constraint))
        .map(|constraint| format!("constraint violated: {constraint}"))
        .collect::<Vec<_>>();
    InferenceResult {
        accepted: final_state == request.goal && violations.is_empty(),
        final_state,
        trace: ExecutionTrace {
            model,
            path,
            evidence,
            violations,
            explored_transitions,
            state_updates,
        },
    }
}

fn models() -> Vec<Box<dyn ExecutionModel>> {
    vec![
        Box::new(GraphExecutionModel),
        Box::new(StateSpaceExecutionModel),
        Box::new(HybridExecutionModel),
    ]
}

fn assert_common_contract(request: &ExecutionRequest, expected: &str) {
    for model in models() {
        let result = model.execute(request);
        assert_eq!(result.final_state, expected, "{:?}", model.kind());
        assert_eq!(result.trace.path.first().unwrap(), request.reason_unit);
        assert_eq!(result.trace.path.last().unwrap(), expected);
        assert_eq!(
            result.trace.evidence.len() + 1,
            result.trace.path.len(),
            "{:?}",
            model.kind()
        );
    }
}

fn taxonomy_request() -> ExecutionRequest {
    ExecutionRequest {
        reason_unit: "Dog",
        context: Vec::new(),
        constraints: Vec::new(),
        goal: "Animal",
        transitions: vec![
            IrTransition::new("Dog", "IsA", "Mammal"),
            IrTransition::new("Mammal", "IsA", "Animal"),
        ],
    }
}

fn constraint_request() -> ExecutionRequest {
    ExecutionRequest {
        reason_unit: "Hypothesis",
        context: vec!["DogCanFly"],
        constraints: vec!["DogCanFly"],
        goal: "Reject",
        transitions: vec![
            IrTransition::new("Hypothesis", "Validate", "ConstraintCheck"),
            IrTransition::new("ConstraintCheck", "Accept", "Accept")
                .guarded(Guard::ConstraintClear("DogCanFly")),
            IrTransition::new("ConstraintCheck", "Reject", "Reject")
                .guarded(Guard::ConstraintViolated("DogCanFly")),
        ],
    }
}

fn memory_request() -> ExecutionRequest {
    ExecutionRequest {
        reason_unit: "Query",
        context: vec!["SHM", "CHM", "DHM"],
        constraints: Vec::new(),
        goal: "Output",
        transitions: vec![
            IrTransition::new("Query", "Retrieve", "MemoryRetrieval"),
            IrTransition::new("MemoryRetrieval", "Integrate", "Integration"),
            IrTransition::new("Integration", "Emit", "Output"),
        ],
    }
}

fn dbm_request() -> ExecutionRequest {
    ExecutionRequest {
        reason_unit: "Goal",
        context: vec!["Task", "Planning", "Validation"],
        constraints: Vec::new(),
        goal: "Output",
        transitions: vec![
            IrTransition::new("Goal", "Generate", "HypothesisGeneration"),
            IrTransition::new("HypothesisGeneration", "Validate", "Validation"),
            IrTransition::new("Validation", "Select", "Selection"),
            IrTransition::new("Selection", "Emit", "Output"),
        ],
    }
}

fn world_model_request() -> ExecutionRequest {
    ExecutionRequest {
        reason_unit: "StateA",
        context: vec!["Environment"],
        constraints: Vec::new(),
        goal: "StateB",
        transitions: vec![IrTransition::new("StateA", "Transition", "StateB")],
    }
}

fn long_chain_request(length: usize) -> ExecutionRequest {
    let names = (0..=length)
        .map(|index| Box::leak(format!("State{index}").into_boxed_str()) as &'static str)
        .collect::<Vec<_>>();
    let transitions = (0..length)
        .map(|index| IrTransition::new(names[index], "Reason", names[index + 1]))
        .collect();
    ExecutionRequest {
        reason_unit: names[0],
        context: Vec::new(),
        constraints: Vec::new(),
        goal: names[length],
        transitions,
    }
}

#[test]
fn rem_01_graph_inference_common_contract() {
    assert_common_contract(&taxonomy_request(), "Animal");
}

#[test]
fn rem_02_constraint_validation_common_contract() {
    let request = constraint_request();
    assert_common_contract(&request, "Reject");
    for model in models() {
        let result = model.execute(&request);
        assert!(!result.accepted);
        assert_eq!(
            result.trace.violations,
            vec!["constraint violated: DogCanFly"]
        );
    }
}

#[test]
fn rem_03_memory_space_query_common_contract() {
    let request = memory_request();
    assert_common_contract(&request, "Output");
    for model in models() {
        assert!(model.execute(&request).accepted);
    }
}

#[test]
fn rem_04_dbm_planning_common_contract() {
    let request = dbm_request();
    assert_common_contract(&request, "Output");
    for model in models() {
        let result = model.execute(&request);
        assert_eq!(result.trace.path.len(), 5);
    }
}

#[test]
fn rem_05_world_model_transition_common_contract() {
    let request = world_model_request();
    assert_common_contract(&request, "StateB");
    for model in models() {
        let result = model.execute(&request);
        assert_eq!(result.trace.path, vec!["StateA", "StateB"]);
    }
}

#[test]
fn rem_06_long_reasoning_chain_common_contract() {
    let request = long_chain_request(128);
    assert_common_contract(&request, "State128");
    for model in models() {
        let result = model.execute(&request);
        assert_eq!(result.trace.path.len(), 129);
        assert_eq!(result.trace.evidence.len(), 128);
    }
}

#[test]
fn rem_07_execution_model_semantics_are_distinct() {
    let request = taxonomy_request();
    let graph = GraphExecutionModel.execute(&request);
    let state = StateSpaceExecutionModel.execute(&request);
    let hybrid = HybridExecutionModel.execute(&request);

    assert_eq!(graph.trace.state_updates, 0);
    assert_eq!(state.trace.state_updates, 2);
    assert_eq!(hybrid.trace.state_updates, 2);
    assert_eq!(graph.trace.path, state.trace.path);
    assert_eq!(state.trace.path, hybrid.trace.path);
}

#[test]
fn rem_08_common_contract_is_serializable_in_shape() {
    let request = dbm_request();
    for model in models() {
        let result = model.execute(&request);
        assert!(!result.final_state.is_empty());
        assert!(!result.trace.path.is_empty());
        assert_eq!(result.trace.model, model.kind());
        assert!(result.trace.violations.is_empty());
    }
}

#[test]
fn rem_09_state_space_requires_a_planner_for_nonlocal_branches() {
    let request = ExecutionRequest {
        reason_unit: "Goal",
        context: vec!["Planning"],
        constraints: Vec::new(),
        goal: "Output",
        transitions: vec![
            IrTransition {
                source: "Goal",
                relation: "LocallyCheap",
                target: "DeadEnd",
                cost: 0,
                evidence: "local minimum",
                guard: Guard::Always,
            },
            IrTransition::new("Goal", "Generate", "Hypothesis"),
            IrTransition::new("Hypothesis", "Validate", "Output"),
        ],
    };

    let graph = GraphExecutionModel.execute(&request);
    let state = StateSpaceExecutionModel.execute(&request);
    let hybrid = HybridExecutionModel.execute(&request);

    assert_eq!(graph.final_state, "Output");
    assert_eq!(hybrid.final_state, "Output");
    assert_eq!(state.final_state, "DeadEnd");
    assert!(!state.accepted);
}
