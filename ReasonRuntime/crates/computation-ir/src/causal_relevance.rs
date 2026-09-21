//! Causal Relevance Filtering v0.1: which reasoning objects the result needed.
//!
//! This is *observational* filtering. After the program has run, the causal
//! graph is walked backwards from the relevance roots (Termination and
//! GoalEvaluation RUs, the final RUS, the `goal_status` transition, and optional
//! user roots) and every RU is classified as `ESSENTIAL`, `SUPPORTING`,
//! `EXCLUSION`, `UNRESOLVED`, or `NOISE`. Only `NOISE` may leave the relevant
//! view. Nothing that ran, and nothing the causal evaluation decided, changes.
//!
//! Policy: when in doubt keep (a missing root, a dangling reference, an
//! exceeded depth, a conflict, or a budget-exhausted judgement all resolve to
//! `UNRESOLVED`, never to a removal).

use crate::causal::{CausalObservation, CausalRelation, CausalTrace};
use crate::reason_objects::{
    project, unit_bindings, Keep, ObjectSources, ReasonObjectsMode, ReasonObjectsTrace, RuoTrace,
    RusTrace,
};
use crate::reason_structure::{ExecutableKind, TerminalStatus};
use crate::reasoning_state::{ReasonStateField, RefResolver, RuRef, RuntimeStateTransition};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashMap, HashSet, VecDeque};
use std::time::Instant;

pub const RELEVANCE_SCHEMA: &str = "reasonscript-causal-relevance/0.1";

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum RelevanceMode {
    #[default]
    Off,
    Annotate,
    Filter,
}

impl RelevanceMode {
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "off" => Some(Self::Off),
            "annotate" => Some(Self::Annotate),
            "filter" => Some(Self::Filter),
            _ => None,
        }
    }

    pub fn enabled(self) -> bool {
        self != Self::Off
    }

    pub fn name(self) -> &'static str {
        match self {
            Self::Off => "off",
            Self::Annotate => "annotate",
            Self::Filter => "filter",
        }
    }
}

/// Ordered by precedence: a later variant never overrides an earlier one.
#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum RelevanceClass {
    Essential,
    Unresolved,
    Supporting,
    Exclusion,
    Noise,
}

impl RelevanceClass {
    pub fn name(self) -> &'static str {
        match self {
            Self::Essential => "ESSENTIAL",
            Self::Unresolved => "UNRESOLVED",
            Self::Supporting => "SUPPORTING",
            Self::Exclusion => "EXCLUSION",
            Self::Noise => "NOISE",
        }
    }
}

/// Machine-readable reasons (bit positions in a `u32` set; variant order is the
/// canonical output and hash order).
#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ReasonCode {
    GoalTermination,
    UserRoot,
    DirectCause,
    CounterfactualNecessary,
    StateCause,
    Prevents,
    TransitiveCause,
    Enables,
    SupportedDependency,
    AlternativeDependency,
    InitialState,
    SearchExclusion,
    Prevented,
    Conflict,
    Insufficient,
    DepthExceeded,
    UnknownRelation,
    DanglingReference,
    SearchUnresolved,
    StateGraphUnavailable,
    NoRoot,
    TemporalOnly,
    NoPathToRoot,
}

impl ReasonCode {
    const ALL: [Self; 23] = [
        Self::GoalTermination,
        Self::UserRoot,
        Self::DirectCause,
        Self::CounterfactualNecessary,
        Self::StateCause,
        Self::Prevents,
        Self::TransitiveCause,
        Self::Enables,
        Self::SupportedDependency,
        Self::AlternativeDependency,
        Self::InitialState,
        Self::SearchExclusion,
        Self::Prevented,
        Self::Conflict,
        Self::Insufficient,
        Self::DepthExceeded,
        Self::UnknownRelation,
        Self::DanglingReference,
        Self::SearchUnresolved,
        Self::StateGraphUnavailable,
        Self::NoRoot,
        Self::TemporalOnly,
        Self::NoPathToRoot,
    ];

    pub fn name(self) -> &'static str {
        match self {
            Self::GoalTermination => "GOAL_TERMINATION",
            Self::UserRoot => "USER_ROOT",
            Self::DirectCause => "DIRECT_CAUSE",
            Self::CounterfactualNecessary => "COUNTERFACTUAL_NECESSARY",
            Self::StateCause => "STATE_CAUSE",
            Self::Prevents => "PREVENTS",
            Self::TransitiveCause => "TRANSITIVE_CAUSE",
            Self::Enables => "ENABLES",
            Self::SupportedDependency => "SUPPORTED_DEPENDENCY",
            Self::AlternativeDependency => "ALTERNATIVE_DEPENDENCY",
            Self::InitialState => "INITIAL_STATE",
            Self::SearchExclusion => "SEARCH_EXCLUSION",
            Self::Prevented => "PREVENTED",
            Self::Conflict => "CONFLICT",
            Self::Insufficient => "INSUFFICIENT",
            Self::DepthExceeded => "DEPTH_EXCEEDED",
            Self::UnknownRelation => "UNKNOWN_RELATION",
            Self::DanglingReference => "DANGLING_REFERENCE",
            Self::SearchUnresolved => "SEARCH_UNRESOLVED",
            Self::StateGraphUnavailable => "STATE_GRAPH_UNAVAILABLE",
            Self::NoRoot => "NO_ROOT",
            Self::TemporalOnly => "TEMPORAL_ONLY",
            Self::NoPathToRoot => "NO_PATH_TO_ROOT",
        }
    }

    fn bit(self) -> u32 {
        1 << self as u32
    }
}

/// What the runtime knows about an Executable RU.
#[derive(Clone, Copy, Debug)]
pub struct NativeUnit {
    pub kind: ExecutableKind,
    pub status: Option<TerminalStatus>,
    /// Reasoning-state revision when the RU began.
    pub state_before: u64,
    /// Revision its own transition produced, when it changed the state.
    pub state_after: Option<u64>,
}

#[derive(Clone, Debug)]
pub struct UnitFacts {
    pub id: String,
    pub native: Option<NativeUnit>,
}

#[derive(Clone, Debug, Default)]
pub struct StateFacts {
    pub final_revision: u64,
    /// Index of the RU that initialized the state (RUS 0).
    pub initial_source: Option<usize>,
    /// Revisions whose transition changed `goal_status`.
    pub goal_revisions: Vec<u64>,
}

pub struct RelevanceInput<'a> {
    pub units: &'a [UnitFacts],
    /// `None` when the reasoning state is unavailable.
    pub state: Option<&'a StateFacts>,
    pub relations: &'a [CausalRelation],
    pub user_roots: &'a [String],
    pub max_depth: usize,
    /// The causal evaluation ran out of counterfactual budget (`CAUSAL-BUDGET-001`).
    pub budget_exhausted: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub struct RootRef {
    #[serde(rename = "ref")]
    pub reference: String,
    pub kind: &'static str,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct ClassificationMetrics {
    pub total_ru_count: u64,
    pub essential_ru_count: u64,
    pub supporting_ru_count: u64,
    pub exclusion_ru_count: u64,
    pub unresolved_ru_count: u64,
    pub noise_ru_count: u64,
    pub causal_traversal_count: u64,
    pub causal_relevance_max_depth: u64,
}

#[derive(Clone, Debug)]
pub struct Classification {
    pub classes: Vec<RelevanceClass>,
    reasons: Vec<u32>,
    pub roots: Vec<RootRef>,
    pub metrics: ClassificationMetrics,
    pub diagnostics: Vec<&'static str>,
    /// No relevance root: everything is kept (fail-open).
    pub missing_root: bool,
    dropped: HashSet<String>,
}

impl Classification {
    pub fn reasons(&self, index: usize) -> Vec<ReasonCode> {
        ReasonCode::ALL
            .into_iter()
            .filter(|code| self.reasons[index] & code.bit() != 0)
            .collect()
    }

    pub fn keeps_unit(&self, index: usize) -> bool {
        self.classes[index] != RelevanceClass::Noise
    }

    pub fn kept_count(&self) -> usize {
        self.classes
            .iter()
            .filter(|c| **c != RelevanceClass::Noise)
            .count()
    }

    /// A causal relation belongs to the relevant view when both endpoints do and
    /// it is more than a bare temporal adjacency.
    pub fn keeps_relation(&self, relation: &CausalRelation) -> bool {
        relation.relation_kind != "TEMPORAL"
            && !self.dropped.contains(&relation.source_ref)
            && !self.dropped.contains(&relation.target_ref)
    }

    pub fn is_dropped(&self, id: &str) -> bool {
        self.dropped.contains(id)
    }

    /// `[ru_ref, class, reason_codes]` per RU in execution order.
    pub fn hash(&self, units: &[UnitFacts]) -> String {
        let mut hasher = Sha256::new();
        let mut buf = Vec::with_capacity(256);
        hasher.update(b"[");
        for (index, unit) in units.iter().enumerate() {
            buf.clear();
            if index > 0 {
                buf.push(b',');
            }
            buf.push(b'[');
            crate::reason_objects::push_str(&mut buf, &unit.id);
            buf.push(b',');
            crate::reason_objects::push_str(&mut buf, self.classes[index].name());
            buf.push(b',');
            let codes: Vec<&str> = self
                .reasons(index)
                .into_iter()
                .map(ReasonCode::name)
                .collect();
            crate::reason_objects::push_list(&mut buf, &codes);
            buf.push(b']');
            hasher.update(&buf);
        }
        hasher.update(b"]");
        format!("sha256:{:x}", hasher.finalize())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Edge {
    CauseDirect { counterfactual: bool },
    CauseIndirect,
    StateCause,
    Terminates,
    Updates,
    Initializes,
    Prevents,
    Enables,
    DependencySupported,
    DependencyAlternative,
    Reads,
    Derives,
    Temporal,
    Unresolved(ReasonCode),
}

impl Edge {
    /// The RU-level class an outgoing edge into a reached node gives its source.
    /// Direct contact with the goal (a root RU) or with the state is essential;
    /// a cause of a cause is only supporting.
    fn contribution(self, target_is_root: bool) -> Option<(RelevanceClass, ReasonCode)> {
        use RelevanceClass::{Essential, Supporting};
        Some(match self {
            Self::CauseDirect { .. } if target_is_root => (Essential, ReasonCode::DirectCause),
            Self::Prevents if target_is_root => (Essential, ReasonCode::Prevents),
            Self::CauseDirect { .. } | Self::CauseIndirect => {
                (Supporting, ReasonCode::TransitiveCause)
            }
            Self::Prevents => (Supporting, ReasonCode::Prevents),
            Self::StateCause | Self::Updates => (Essential, ReasonCode::StateCause),
            Self::Terminates => (Essential, ReasonCode::GoalTermination),
            Self::Enables => (Supporting, ReasonCode::Enables),
            Self::DependencySupported => (Supporting, ReasonCode::SupportedDependency),
            Self::DependencyAlternative => (Supporting, ReasonCode::AlternativeDependency),
            Self::Initializes => (Supporting, ReasonCode::InitialState),
            Self::Reads | Self::Derives | Self::Temporal | Self::Unresolved(_) => return None,
        })
    }

    /// Causal-depth cost: only causal relations count toward `max_causal_depth`;
    /// the state lineage (RUS chain, updates, reads) is structural.
    fn cost(self) -> u32 {
        match self {
            Self::Updates | Self::Initializes | Self::Reads | Self::Derives => 0,
            _ => 1,
        }
    }

    /// Backward relevance propagates along everything except bare temporal
    /// adjacency and judgements that did not resolve.
    fn traversable(self) -> bool {
        !matches!(self, Self::Temporal | Self::Unresolved(_))
    }
}

fn relation_edge(relation: &CausalRelation) -> Edge {
    match (relation.relation_kind, relation.status) {
        (_, "CONFLICT") => Edge::Unresolved(ReasonCode::Conflict),
        (_, "INSUFFICIENT") => Edge::Unresolved(ReasonCode::Insufficient),
        ("TEMPORAL", "CANDIDATE" | "REJECTED") => Edge::Temporal,
        ("CAUSES", "CONFIRMED") => {
            if relation.provenance["indirect"] == true {
                Edge::CauseIndirect
            } else {
                Edge::CauseDirect {
                    counterfactual: !relation.provenance["counterfactual_result_ref"].is_null(),
                }
            }
        }
        ("CAUSES_STATE_CHANGE", "CONFIRMED") => Edge::StateCause,
        ("TERMINATES", "CONFIRMED") => Edge::Terminates,
        ("ENABLES", "CONFIRMED") => Edge::Enables,
        ("PREVENTS", "CONFIRMED") => Edge::Prevents,
        ("DEPENDENCY", "SUPPORTED") => Edge::DependencySupported,
        // The dependency exists but is not necessary: an alternative supplies it.
        ("DEPENDENCY", "REJECTED") if relation.dependency == Some(true) => {
            Edge::DependencyAlternative
        }
        ("DEPENDENCY", "REJECTED") => Edge::Temporal,
        _ => Edge::Unresolved(ReasonCode::UnknownRelation),
    }
}

fn known_relation(kind: &str) -> bool {
    matches!(
        kind,
        "CAUSES"
            | "CAUSES_STATE_CHANGE"
            | "TERMINATES"
            | "ENABLES"
            | "PREVENTS"
            | "DEPENDENCY"
            | "TEMPORAL"
    )
}

fn transition_revision(id: &str) -> Option<u64> {
    let digits = id.strip_prefix("state-transition:")?;
    (digits.len() == 8 && digits.bytes().all(|b| b.is_ascii_digit()))
        .then(|| digits.parse().ok())
        .flatten()
}

/// Classifies every RU in `input.units` (in that order).
pub fn classify(input: &RelevanceInput) -> Classification {
    let units = input.units;
    let unit_count = units.len();
    let (revisions, transitions) = input.state.map_or((0, 0), |state| {
        (
            state.final_revision as usize + 1,
            state.final_revision as usize,
        )
    });
    let revision_node = |revision: u64| (unit_count + revision as usize) as u32;
    let transition_node = |revision: u64| (unit_count + revisions + revision as usize - 1) as u32;
    let node_count = unit_count + revisions + transitions;

    let unit_index: HashMap<&str, u32> = units
        .iter()
        .enumerate()
        .map(|(index, unit)| (unit.id.as_str(), index as u32))
        .collect();
    let resolve = |id: &str| -> Option<u32> {
        unit_index.get(id).copied().or_else(|| {
            let revision = transition_revision(id)?;
            (revision >= 1 && revision as usize <= transitions).then(|| transition_node(revision))
        })
    };

    let mut diagnostics: Vec<&'static str> = Vec::new();
    fn note(code: &'static str, diagnostics: &mut Vec<&'static str>) {
        if !diagnostics.contains(&code) {
            diagnostics.push(code);
        }
    }
    let mut reasons = vec![0_u32; unit_count];
    let mut edges: Vec<(u32, u32, Edge)> =
        Vec::with_capacity(input.relations.len() + unit_count * 2);

    // Causal relations.
    for relation in input.relations {
        if !known_relation(relation.relation_kind) {
            note("REL-003", &mut diagnostics);
        }
        let edge = relation_edge(relation);
        match (resolve(&relation.source_ref), resolve(&relation.target_ref)) {
            (Some(source), Some(target)) => edges.push((source, target, edge)),
            (source, target) => {
                // A dangling endpoint: keep the resolvable side undecided.
                note("REL-002", &mut diagnostics);
                for node in [source, target].into_iter().flatten() {
                    if (node as usize) < unit_count {
                        reasons[node as usize] |= ReasonCode::DanglingReference.bit();
                    }
                }
            }
        }
    }

    // State lineage: RU --UPDATES--> RUS, RUS --DERIVES_STATE--> RUS, RUS --READS_STATE--> RU.
    if let Some(state) = input.state {
        for (index, unit) in units.iter().enumerate() {
            let Some(native) = unit.native else { continue };
            if let Some(after) = native.state_after {
                edges.push((index as u32, revision_node(after), Edge::Updates));
            }
            edges.push((
                revision_node(native.state_before),
                index as u32,
                Edge::Reads,
            ));
        }
        for revision in 1..=state.final_revision {
            edges.push((
                revision_node(revision - 1),
                revision_node(revision),
                Edge::Derives,
            ));
        }
        if let Some(source) = state.initial_source {
            edges.push((source as u32, revision_node(0), Edge::Initializes));
        }
    }

    let mut incoming: Vec<Vec<u32>> = vec![Vec::new(); node_count];
    let mut outgoing: Vec<Vec<u32>> = vec![Vec::new(); node_count];
    for (index, (source, target, _)) in edges.iter().enumerate() {
        outgoing[*source as usize].push(index as u32);
        incoming[*target as usize].push(index as u32);
    }

    // Roots, in canonical (ID) order.
    let mut roots: Vec<(String, u32, &'static str)> = Vec::new();
    for (index, unit) in units.iter().enumerate() {
        match unit.native.map(|native| native.kind) {
            Some(ExecutableKind::TerminationCheck) => {
                roots.push((unit.id.clone(), index as u32, "TERMINATION_CHECK"));
            }
            Some(ExecutableKind::GoalEvaluation) => {
                roots.push((unit.id.clone(), index as u32, "GOAL_EVALUATION"));
            }
            _ => {}
        }
    }
    if let Some(state) = input.state {
        roots.push((
            format!("rus:runtime:{:08}", state.final_revision),
            revision_node(state.final_revision),
            "FINAL_RUS",
        ));
        for revision in &state.goal_revisions {
            roots.push((
                format!("state-transition:{revision:08}"),
                transition_node(*revision),
                "GOAL_STATUS_TRANSITION",
            ));
        }
    }
    let mut user_root_units: HashSet<u32> = HashSet::new();
    for root in input.user_roots {
        match resolve(root) {
            Some(node) => {
                if (node as usize) < unit_count {
                    user_root_units.insert(node);
                }
                if !roots.iter().any(|(id, _, _)| id == root) {
                    roots.push((root.clone(), node, "USER"));
                }
            }
            None => note("REL-002", &mut diagnostics),
        }
    }
    roots.sort_by(|left, right| left.0.cmp(&right.0));
    roots.dedup_by(|left, right| left.0 == right.0);
    let root_refs: Vec<RootRef> = roots
        .iter()
        .map(|(reference, _, kind)| RootRef {
            reference: reference.clone(),
            kind,
        })
        .collect();

    let mut metrics = ClassificationMetrics {
        total_ru_count: unit_count as u64,
        ..Default::default()
    };
    let root_nodes: HashSet<u32> = roots.iter().map(|(_, node, _)| *node).collect();

    if roots.is_empty() {
        // Fail-open: no root means no relevance judgement; keep everything.
        note("REL-001", &mut diagnostics);
        return finish(
            units,
            vec![RelevanceClass::Unresolved; unit_count],
            vec![ReasonCode::NoRoot.bit(); unit_count],
            root_refs,
            metrics,
            diagnostics,
            true,
        );
    }

    // Goal-seeded backward traversal (0-1 BFS: causal relations cost one level,
    // the state lineage none).
    let limit = input.max_depth as u32;
    let mut depth: Vec<Option<u32>> = vec![None; node_count];
    let mut queue: VecDeque<u32> = VecDeque::new();
    for (_, node, _) in &roots {
        if depth[*node as usize].is_none() {
            depth[*node as usize] = Some(0);
            queue.push_back(*node);
        }
    }
    let mut blocked: Vec<u32> = Vec::new();
    while let Some(node) = queue.pop_front() {
        let level = depth[node as usize].expect("queued nodes have a depth");
        for edge_index in &incoming[node as usize] {
            let (source, _, edge) = edges[*edge_index as usize];
            if !edge.traversable() {
                continue;
            }
            let next = level + edge.cost();
            if next > limit {
                blocked.push(source);
                continue;
            }
            metrics.causal_traversal_count += 1;
            if depth[source as usize].is_none_or(|known| next < known) {
                depth[source as usize] = Some(next);
                metrics.causal_relevance_max_depth =
                    metrics.causal_relevance_max_depth.max(u64::from(next));
                if edge.cost() == 0 {
                    queue.push_front(source);
                } else {
                    queue.push_back(source);
                }
            }
        }
    }
    // An edge into a visited node counts when it could have been traversed.
    let expanded =
        |node: u32, edge: Edge| depth[node as usize].is_some_and(|d| d + edge.cost() <= limit);
    // Everything upstream of a node the depth limit cut off is undecided, however
    // far behind it lies: the cut, not the graph, kept it out of the traversal.
    let mut cut = vec![false; node_count];
    let mut pending: Vec<u32> = Vec::new();
    for source in blocked {
        if depth[source as usize].is_none() && !cut[source as usize] {
            cut[source as usize] = true;
            pending.push(source);
        }
    }
    while let Some(node) = pending.pop() {
        for edge_index in &incoming[node as usize] {
            let (source, _, edge) = edges[*edge_index as usize];
            if edge.traversable() && depth[source as usize].is_none() && !cut[source as usize] {
                cut[source as usize] = true;
                pending.push(source);
            }
        }
    }
    let depth_exceeded: Vec<bool> = cut[..unit_count].to_vec();

    // Search exclusion: a rejected candidate check followed, in the same
    // reasoning-state lineage, by a verified candidate or a reached goal.
    let mut resolved_after = vec![false; unit_count];
    let mut resolved = false;
    for (index, unit) in units.iter().enumerate().rev() {
        resolved_after[index] = resolved;
        resolved |= unit.native.is_some_and(|native| {
            matches!(
                (native.kind, native.status),
                (
                    ExecutableKind::Verification | ExecutableKind::GoalEvaluation,
                    Some(TerminalStatus::Verified)
                )
            )
        });
    }
    let state_available = input.state.is_some();

    let mut classes = vec![RelevanceClass::Noise; unit_count];
    let mut prevented = vec![false; unit_count];
    for (source, target, edge) in &edges {
        if *edge == Edge::Prevents
            && !expanded(*target, *edge)
            && (*source as usize) < unit_count
            && (*target as usize) < unit_count
        {
            prevented[*source as usize] = true;
            prevented[*target as usize] = true;
        }
    }
    for index in 0..unit_count {
        let node = index as u32;
        let mut bits = reasons[index];
        let mut class = RelevanceClass::Noise;
        let raise = |candidate: RelevanceClass, class: &mut RelevanceClass| {
            *class = (*class).min(candidate);
        };
        if let Some(native) = units[index].native {
            if matches!(
                native.kind,
                ExecutableKind::TerminationCheck | ExecutableKind::GoalEvaluation
            ) {
                bits |= ReasonCode::GoalTermination.bit();
                raise(RelevanceClass::Essential, &mut class);
            }
        }
        if user_root_units.contains(&node) {
            bits |= ReasonCode::UserRoot.bit();
            raise(RelevanceClass::Essential, &mut class);
        }
        let mut temporal_only = false;
        let mut unresolved = bits & ReasonCode::DanglingReference.bit() != 0;
        for edge_index in outgoing[index].iter().chain(incoming[index].iter()) {
            let (source, target, edge) = edges[*edge_index as usize];
            if let Edge::Unresolved(code) = edge {
                bits |= code.bit();
                unresolved = true;
                if code == ReasonCode::UnknownRelation {
                    note("REL-003", &mut diagnostics);
                }
                continue;
            }
            if edge == Edge::Temporal {
                temporal_only = true;
                continue;
            }
            if source == node && expanded(target, edge) {
                if let Some((contribution, code)) = edge.contribution(root_nodes.contains(&target))
                {
                    bits |= code.bit();
                    if code == ReasonCode::DirectCause
                        && edge
                            == (Edge::CauseDirect {
                                counterfactual: true,
                            })
                    {
                        bits |= ReasonCode::CounterfactualNecessary.bit();
                    }
                    raise(contribution, &mut class);
                }
            }
        }
        if depth_exceeded[index] {
            bits |= ReasonCode::DepthExceeded.bit();
            unresolved = true;
            note("REL-004", &mut diagnostics);
        }
        if prevented[index] && class > RelevanceClass::Supporting {
            bits |= ReasonCode::Prevented.bit();
            raise(RelevanceClass::Exclusion, &mut class);
        }
        if class > RelevanceClass::Exclusion {
            if let Some(native) = units[index].native {
                if native.kind == ExecutableKind::Verification
                    && native.status == Some(TerminalStatus::Rejected)
                {
                    if resolved_after[index] {
                        bits |= ReasonCode::SearchExclusion.bit();
                        raise(RelevanceClass::Exclusion, &mut class);
                    } else {
                        bits |= ReasonCode::SearchUnresolved.bit();
                        unresolved = true;
                    }
                }
            }
        }
        if class > RelevanceClass::Unresolved && unresolved {
            raise(RelevanceClass::Unresolved, &mut class);
        }
        if class == RelevanceClass::Noise {
            if !state_available && units[index].native.is_some() {
                // Without the state graph nothing can show this RU was irrelevant.
                bits |= ReasonCode::StateGraphUnavailable.bit();
                note("REL-008", &mut diagnostics);
                class = RelevanceClass::Unresolved;
            } else {
                bits |= if temporal_only {
                    ReasonCode::TemporalOnly
                } else {
                    ReasonCode::NoPathToRoot
                }
                .bit();
            }
        }
        classes[index] = class;
        reasons[index] = bits;
    }

    // Consistency: roots stay ESSENTIAL and nothing touching an unresolved
    // relation or a reached node may be NOISE; a violation fails open.
    for index in 0..unit_count {
        let touches_unresolved = outgoing[index]
            .iter()
            .chain(&incoming[index])
            .any(|edge_index| matches!(edges[*edge_index as usize].2, Edge::Unresolved(_)));
        let inconsistent = classes[index] == RelevanceClass::Noise
            && (touches_unresolved || depth[index].is_some());
        if inconsistent {
            note("REL-006", &mut diagnostics);
            classes[index] = RelevanceClass::Unresolved;
        }
    }
    if input.budget_exhausted {
        note("REL-005", &mut diagnostics);
    }
    finish(
        units,
        classes,
        reasons,
        root_refs,
        metrics,
        diagnostics,
        false,
    )
}

fn finish(
    units: &[UnitFacts],
    classes: Vec<RelevanceClass>,
    reasons: Vec<u32>,
    roots: Vec<RootRef>,
    mut metrics: ClassificationMetrics,
    diagnostics: Vec<&'static str>,
    missing_root: bool,
) -> Classification {
    let mut dropped = HashSet::new();
    for (unit, class) in units.iter().zip(&classes) {
        match class {
            RelevanceClass::Essential => metrics.essential_ru_count += 1,
            RelevanceClass::Supporting => metrics.supporting_ru_count += 1,
            RelevanceClass::Exclusion => metrics.exclusion_ru_count += 1,
            RelevanceClass::Unresolved => metrics.unresolved_ru_count += 1,
            RelevanceClass::Noise => {
                metrics.noise_ru_count += 1;
                dropped.insert(unit.id.clone());
            }
        }
    }
    Classification {
        classes,
        reasons,
        roots,
        metrics,
        diagnostics,
        missing_root,
        dropped,
    }
}

/// The `causal_relevance` artifact.
#[derive(Clone, Debug, Serialize)]
pub struct RuRelevance {
    pub ru_ref: String,
    pub class: RelevanceClass,
    pub reasons: Vec<ReasonCode>,
}

pub fn classifications(units: &[UnitFacts], classification: &Classification) -> Vec<RuRelevance> {
    units
        .iter()
        .enumerate()
        .map(|(index, unit)| RuRelevance {
            ru_ref: unit.id.clone(),
            class: classification.classes[index],
            reasons: classification.reasons(index),
        })
        .collect()
}

#[derive(Clone, Debug)]
pub struct RelevanceConfig {
    pub max_depth: usize,
    pub user_roots: Vec<String>,
}

/// The relevant RUS / RUO view (`filter` mode). It refers to the IDs of the
/// full artifacts and never copies their content.
#[derive(Clone, Debug, Serialize)]
pub struct RelevantView {
    pub rus: RusTrace,
    pub ruo: Option<RuoTrace>,
    pub causal_relation_refs: Vec<String>,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct RelevanceMetrics {
    #[serde(flatten)]
    pub classification: ClassificationMetrics,
    pub reasoning_noise_reduction_ratio: f64,
    pub essential_preservation_rate: Option<f64>,
    pub ru_reduction_ratio: f64,
    pub ruo_reduction_ratio: Option<f64>,
    pub rus_reduction_ratio: Option<f64>,
    pub relation_reduction_ratio: Option<f64>,
    pub full_relation_count: Option<u64>,
    pub relevant_relation_count: Option<u64>,
    pub full_json_bytes: Option<u64>,
    pub relevant_json_bytes: Option<u64>,
    pub response_reduction_ratio: Option<f64>,
    pub causal_relevance_ns: u64,
    pub relevant_projection_ns: u64,
    pub size_accounting_ns: u64,
}

#[derive(Clone, Debug, Serialize)]
pub struct CausalRelevanceTrace {
    pub schema: &'static str,
    pub mode: &'static str,
    pub roots: Vec<RootRef>,
    pub classifications: Vec<RuRelevance>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub relevant: Option<RelevantView>,
    pub metrics: RelevanceMetrics,
    pub hashes: BTreeMap<&'static str, String>,
    pub diagnostics: Vec<&'static str>,
}

fn ratio(part: u64, whole: u64) -> f64 {
    if whole == 0 {
        0.0
    } else {
        part as f64 / whole as f64
    }
}

/// Runs the analysis after execution: facts from the runtime tables and the
/// causal trace, classification, and (in `filter` mode) the relevant projection.
pub(crate) fn build(
    sources: &ObjectSources,
    resolver: &dyn RefResolver,
    mode: RelevanceMode,
    causal: &CausalTrace,
    observations: &[CausalObservation],
    config: &RelevanceConfig,
    full: Option<&ReasonObjectsTrace>,
) -> CausalRelevanceTrace {
    let started = Instant::now();
    let units = sources.units;
    let transitions = sources.transitions;
    let state_available = sources.state.enabled();
    let (updated_at, _) = unit_bindings(units, transitions);

    // Native RUs first (execution order), then observations that are not RUs.
    let mut facts: Vec<UnitFacts> = units
        .iter()
        .enumerate()
        .map(|(index, unit)| UnitFacts {
            id: unit.id.clone(),
            native: Some(NativeUnit {
                kind: unit.kind,
                status: unit.terminal_status,
                state_before: u64::from(unit.state_before),
                state_after: updated_at[index],
            }),
        })
        .collect();
    let native_ids: HashSet<&str> = units.iter().map(|unit| unit.id.as_str()).collect();
    for observation in observations {
        if !native_ids.contains(observation.ru_id.as_str())
            && !facts.iter().any(|fact| fact.id == observation.ru_id)
        {
            facts.push(UnitFacts {
                id: observation.ru_id.clone(),
                native: None,
            });
        }
    }
    let state = state_available.then(|| StateFacts {
        final_revision: sources.state.revision(),
        initial_source: sources
            .state
            .initial_source_ru()
            .map(|RuRef(index)| index as usize),
        goal_revisions: transitions
            .iter()
            .filter(|transition| transition.changed.contains(ReasonStateField::GoalStatus))
            .map(RuntimeStateTransition::revision_after)
            .collect(),
    });
    let classification = classify(&RelevanceInput {
        units: &facts,
        state: state.as_ref(),
        relations: &causal.relations,
        user_roots: &config.user_roots,
        max_depth: config.max_depth,
        budget_exhausted: causal.diagnostics.contains(&"CAUSAL-BUDGET-001"),
    });
    let mut hashes = BTreeMap::new();
    hashes.insert("causal_relevance_hash", classification.hash(&facts));
    let mut diagnostics = classification.diagnostics.clone();
    let mut metrics = RelevanceMetrics {
        classification: classification.metrics.clone(),
        ..RelevanceMetrics::default()
    };
    metrics.reasoning_noise_reduction_ratio = ratio(
        classification.metrics.noise_ru_count,
        classification.metrics.total_ru_count,
    );
    metrics.ru_reduction_ratio = metrics.reasoning_noise_reduction_ratio;
    metrics.causal_relevance_ns = elapsed(started);

    let mut relevant = None;
    let projectable = mode == RelevanceMode::Filter && state_available && !units.is_empty();
    if projectable {
        let started = Instant::now();
        let fail_open = classification.missing_root;
        let keep_unit: Vec<bool> = (0..units.len())
            .map(|index| fail_open || classification.keeps_unit(index))
            .collect();
        let keep_causal: Vec<bool> = causal
            .relations
            .iter()
            .map(|relation| fail_open || classification.keeps_relation(relation))
            .collect();
        let trace = project(
            sources,
            resolver,
            ReasonObjectsMode::RusRuo,
            &causal.relations,
            Some(&Keep {
                unit: &keep_unit,
                causal: &keep_causal,
            }),
        );
        let causal_relation_refs: Vec<String> = causal
            .relations
            .iter()
            .zip(&keep_causal)
            .filter(|(_, kept)| **kept)
            .map(|(relation, _)| relation.id.clone())
            .collect();
        metrics.relevant_projection_ns = elapsed(started);

        let ruo = trace.ruo.as_ref().expect("filter projects RUOs");
        hashes.insert(
            "relevant_ruo_graph_hash",
            ruo.hashes["ruo_graph_hash"].clone(),
        );
        hashes.insert(
            "relevant_rus_sequence_hash",
            trace.rus.hashes["rus_sequence_hash"].clone(),
        );
        hashes.insert(
            "relevant_rus_relation_hash",
            trace.rus.hashes["rus_relation_hash"].clone(),
        );

        // Reduction and preservation, counted against the full projection.
        let updating = updated_at.iter().flatten().count() as u64;
        let full_rus_relations = units.len() as u64 + 2 * updating;
        let full_relations =
            causal.relations.len() as u64 + full_rus_relations + sources.relations.len() as u64;
        let relevant_relations = keep_causal.iter().filter(|kept| **kept).count() as u64
            + trace.rus.relations.len() as u64
            + trace.reason_relation_count;
        metrics.full_relation_count = Some(full_relations);
        metrics.relevant_relation_count = Some(relevant_relations);
        metrics.relation_reduction_ratio =
            Some(ratio(full_relations - relevant_relations, full_relations));
        metrics.ruo_reduction_ratio = Some(ratio(
            (units.len() - ruo.objects.len()) as u64,
            units.len() as u64,
        ));
        metrics.rus_reduction_ratio = Some(0.0);
        let retained: HashSet<&str> = ruo
            .objects
            .iter()
            .map(|object| object.ru_ref.as_str())
            .collect();
        let essential: Vec<&str> = facts
            .iter()
            .zip(&classification.classes)
            .filter(|(_, class)| **class == RelevanceClass::Essential)
            .map(|(fact, _)| fact.id.as_str())
            .collect();
        let preserved = essential
            .iter()
            .filter(|id| retained.contains(**id) || !native_ids.contains(**id))
            .count();
        metrics.essential_preservation_rate = Some(if essential.is_empty() {
            1.0
        } else {
            preserved as f64 / essential.len() as f64
        });
        // A relevant view that does not resolve is an inconsistent classification.
        if (!trace.rus.diagnostics.is_empty() || ruo.metrics.dangling_reference_count > 0)
            && !diagnostics.contains(&"REL-006")
        {
            diagnostics.push("REL-006");
        }

        let view = RelevantView {
            rus: trace.rus,
            ruo: trace.ruo,
            causal_relation_refs,
        };
        let started = Instant::now();
        metrics.relevant_json_bytes =
            Some(serde_json::to_vec(&view).map_or(0, |bytes| bytes.len() as u64));
        if let Some(full) = full {
            let bytes = serde_json::to_vec(&full.rus).map_or(0, |b| b.len() as u64)
                + full.ruo.as_ref().map_or(0, |ruo| {
                    serde_json::to_vec(ruo).map_or(0, |b| b.len() as u64)
                });
            metrics.full_json_bytes = Some(bytes);
            metrics.response_reduction_ratio =
                Some(1.0 - metrics.relevant_json_bytes.unwrap_or(0) as f64 / bytes.max(1) as f64);
        }
        metrics.size_accounting_ns = elapsed(started);
        relevant = Some(view);
    }

    CausalRelevanceTrace {
        schema: RELEVANCE_SCHEMA,
        mode: mode.name(),
        roots: classification.roots.clone(),
        classifications: classifications(&facts, &classification),
        relevant,
        metrics,
        hashes,
        diagnostics,
    }
}

fn elapsed(started: Instant) -> u64 {
    started.elapsed().as_nanos() as u64
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn relation(
        source: &str,
        target: &str,
        kind: &'static str,
        status: &'static str,
    ) -> CausalRelation {
        CausalRelation {
            id: String::new(),
            source_ref: source.into(),
            target_ref: target.into(),
            relation_kind: kind,
            evidence_refs: Vec::new(),
            dependency: Some(kind == "DEPENDENCY" || kind == "CAUSES"),
            necessity: (kind == "CAUSES").then_some(true),
            sufficiency: None,
            polarity: "POSITIVE",
            modality: "ACTUAL",
            status,
            provenance: json!({"counterfactual_result_ref": "counterfactual:00000001"}),
        }
    }

    fn external(ids: &[&str]) -> Vec<UnitFacts> {
        ids.iter()
            .map(|id| UnitFacts {
                id: (*id).into(),
                native: None,
            })
            .collect()
    }

    fn run(units: &[UnitFacts], relations: &[CausalRelation], roots: &[&str]) -> Classification {
        let roots: Vec<String> = roots.iter().map(|root| (*root).into()).collect();
        classify(&RelevanceInput {
            units,
            state: None,
            relations,
            user_roots: &roots,
            max_depth: 8,
            budget_exhausted: false,
        })
    }

    fn class_of(
        classification: &Classification,
        index: usize,
    ) -> (RelevanceClass, Vec<&'static str>) {
        (
            classification.classes[index],
            classification
                .reasons(index)
                .into_iter()
                .map(ReasonCode::name)
                .collect(),
        )
    }

    #[test]
    fn a_direct_counterfactual_cause_of_the_root_is_essential() {
        let units = external(&["A", "B"]);
        let result = run(&units, &[relation("A", "B", "CAUSES", "CONFIRMED")], &["B"]);
        let (class, reasons) = class_of(&result, 0);
        assert_eq!(class, RelevanceClass::Essential);
        assert_eq!(reasons, ["DIRECT_CAUSE", "COUNTERFACTUAL_NECESSARY"]);
    }

    #[test]
    fn transitive_cause_is_only_supporting() {
        let units = external(&["A", "B", "C"]);
        let mut indirect = relation("A", "C", "CAUSES", "CONFIRMED");
        indirect.provenance = json!({"indirect": true, "depth": 2});
        let result = run(&units, &[indirect], &["C"]);
        assert_eq!(
            class_of(&result, 0),
            (RelevanceClass::Supporting, vec!["TRANSITIVE_CAUSE"])
        );
        assert_eq!(result.classes[1], RelevanceClass::Noise);
    }

    #[test]
    fn a_cause_of_a_cause_is_supporting_while_contact_with_the_root_is_essential() {
        let units = external(&["A", "B", "C"]);
        let result = run(
            &units,
            &[
                relation("A", "B", "CAUSES", "CONFIRMED"),
                relation("B", "C", "CAUSES", "CONFIRMED"),
            ],
            &["C"],
        );
        assert_eq!(class_of(&result, 1).0, RelevanceClass::Essential);
        assert_eq!(
            class_of(&result, 0),
            (RelevanceClass::Supporting, vec!["TRANSITIVE_CAUSE"])
        );
    }

    #[test]
    fn c_enables_and_supported_dependency_are_supporting() {
        let units = external(&["A", "B", "C"]);
        let result = run(
            &units,
            &[
                relation("A", "C", "ENABLES", "CONFIRMED"),
                relation("B", "C", "DEPENDENCY", "SUPPORTED"),
            ],
            &["C"],
        );
        assert_eq!(
            class_of(&result, 0),
            (RelevanceClass::Supporting, vec!["ENABLES"])
        );
        assert_eq!(
            class_of(&result, 1),
            (RelevanceClass::Supporting, vec!["SUPPORTED_DEPENDENCY"])
        );
    }

    #[test]
    fn d_temporal_only_is_noise_and_does_not_propagate() {
        let units = external(&["A", "B", "C"]);
        let result = run(
            &units,
            &[
                relation("A", "B", "TEMPORAL", "CANDIDATE"),
                relation("B", "C", "TEMPORAL", "CANDIDATE"),
            ],
            &["C"],
        );
        assert_eq!(
            class_of(&result, 0),
            (RelevanceClass::Noise, vec!["TEMPORAL_ONLY"])
        );
        assert_eq!(
            class_of(&result, 1),
            (RelevanceClass::Noise, vec!["TEMPORAL_ONLY"])
        );
        assert_eq!(result.classes[2], RelevanceClass::Essential);
        assert!(result.is_dropped("A") && result.is_dropped("B") && !result.is_dropped("C"));
    }

    #[test]
    fn e_and_f_conflict_and_insufficient_are_unresolved_never_noise() {
        for (status, code) in [("CONFLICT", "CONFLICT"), ("INSUFFICIENT", "INSUFFICIENT")] {
            let units = external(&["A", "B", "C"]);
            let result = run(&units, &[relation("A", "B", "DEPENDENCY", status)], &["C"]);
            // Not connected to the root, yet neither endpoint may be dropped.
            assert_eq!(
                class_of(&result, 0),
                (RelevanceClass::Unresolved, vec![code])
            );
            assert_eq!(
                class_of(&result, 1),
                (RelevanceClass::Unresolved, vec![code])
            );
            assert!(!result.is_dropped("A") && !result.is_dropped("B"));
        }
    }

    #[test]
    fn o_alternative_evidence_keeps_the_dependency_as_supporting() {
        let units = external(&["A", "B", "C"]);
        let mut alternative = relation("A", "C", "DEPENDENCY", "REJECTED");
        alternative.dependency = Some(true);
        alternative.necessity = Some(false);
        let result = run(&units, &[alternative], &["C"]);
        assert_eq!(
            class_of(&result, 0),
            (RelevanceClass::Supporting, vec!["ALTERNATIVE_DEPENDENCY"])
        );
        // A rejected dependency with no evidence link is a noise candidate.
        let mut none = relation("B", "C", "DEPENDENCY", "REJECTED");
        none.dependency = Some(false);
        let result = run(&units, &[none], &["C"]);
        assert_eq!(result.classes[1], RelevanceClass::Noise);
    }

    #[test]
    fn prevention_is_essential_toward_the_goal_and_an_exclusion_elsewhere() {
        let units = external(&["A", "B", "C", "D"]);
        let result = run(
            &units,
            &[
                relation("A", "B", "PREVENTS", "CONFIRMED"),
                relation("C", "D", "PREVENTS", "CONFIRMED"),
            ],
            &["B"],
        );
        assert_eq!(
            class_of(&result, 0),
            (RelevanceClass::Essential, vec!["PREVENTS"])
        );
        assert_eq!(result.classes[2], RelevanceClass::Exclusion);
        assert_eq!(result.classes[3], RelevanceClass::Exclusion);
    }

    #[test]
    fn missing_root_dangling_references_and_unknown_relations_fail_open() {
        let units = external(&["A", "B"]);
        let no_root = run(&units, &[relation("A", "B", "CAUSES", "CONFIRMED")], &[]);
        assert!(no_root.missing_root && no_root.diagnostics.contains(&"REL-001"));
        assert!(no_root
            .classes
            .iter()
            .all(|class| *class == RelevanceClass::Unresolved));

        let dangling = run(
            &units,
            &[relation("A", "ghost", "CAUSES", "CONFIRMED")],
            &["B"],
        );
        assert!(dangling.diagnostics.contains(&"REL-002"));
        assert_eq!(class_of(&dangling, 0).0, RelevanceClass::Unresolved);

        let unknown = run(
            &units,
            &[relation("A", "B", "MYSTERY", "CONFIRMED")],
            &["B"],
        );
        assert!(unknown.diagnostics.contains(&"REL-003"));
        assert_eq!(class_of(&unknown, 0).0, RelevanceClass::Unresolved);
        let unknown_root = run(&units, &[], &["ghost"]);
        assert!(unknown_root.diagnostics.contains(&"REL-002"));
    }

    #[test]
    fn traversal_deeper_than_max_depth_is_unresolved() {
        let ids = ["A", "B", "C", "D", "E"];
        let units = external(&ids);
        let chain: Vec<_> = ids
            .windows(2)
            .map(|pair| relation(pair[0], pair[1], "ENABLES", "CONFIRMED"))
            .collect();
        let result = classify(&RelevanceInput {
            units: &units,
            state: None,
            relations: &chain,
            user_roots: &["E".to_owned()],
            max_depth: 2,
            budget_exhausted: true,
        });
        let classes: Vec<_> = result.classes.iter().map(|class| class.name()).collect();
        assert_eq!(
            classes,
            [
                "UNRESOLVED",
                "UNRESOLVED",
                "SUPPORTING",
                "SUPPORTING",
                "ESSENTIAL"
            ]
        );
        assert!(result.diagnostics.contains(&"REL-004") && result.diagnostics.contains(&"REL-005"));
        // The unresolved ones are kept.
        assert!(!result.is_dropped("A") && !result.is_dropped("B"));
    }

    #[test]
    fn precedence_keeps_essential_over_unresolved_and_is_deterministic() {
        let units = external(&["A", "B", "C"]);
        let relations = [
            relation("A", "C", "CAUSES", "CONFIRMED"),
            relation("A", "B", "DEPENDENCY", "CONFLICT"),
        ];
        let result = run(&units, &relations, &["C"]);
        assert_eq!(class_of(&result, 0).0, RelevanceClass::Essential);
        assert!(result.reasons(0).contains(&ReasonCode::Conflict));
        assert_eq!(class_of(&result, 1).0, RelevanceClass::Unresolved);
        let hashes: HashSet<_> = (0..3)
            .map(|_| run(&units, &relations, &["C"]).hash(&units))
            .collect();
        assert_eq!(hashes.len(), 1);
        let other = run(&units, &relations[..1], &["C"]).hash(&units);
        assert!(!hashes.contains(&other));
    }

    fn native(
        kind: ExecutableKind,
        status: TerminalStatus,
        before: u64,
        after: Option<u64>,
    ) -> NativeUnit {
        NativeUnit {
            kind,
            status: Some(status),
            state_before: before,
            state_after: after,
        }
    }

    #[test]
    fn state_lineage_makes_every_state_changing_ru_essential_and_search_checks_exclusions() {
        // hypothesis(2) -> verification rejected -> hypothesis(3) -> verification verified -> goal
        let units = vec![
            UnitFacts {
                id: "init".into(),
                native: Some(native(
                    ExecutableKind::Hypothesis,
                    TerminalStatus::Completed,
                    0,
                    None,
                )),
            },
            UnitFacts {
                id: "h2".into(),
                native: Some(native(
                    ExecutableKind::Hypothesis,
                    TerminalStatus::Completed,
                    0,
                    Some(1),
                )),
            },
            UnitFacts {
                id: "v2".into(),
                native: Some(native(
                    ExecutableKind::Verification,
                    TerminalStatus::Rejected,
                    1,
                    None,
                )),
            },
            UnitFacts {
                id: "noise".into(),
                native: Some(native(
                    ExecutableKind::Hypothesis,
                    TerminalStatus::Completed,
                    1,
                    None,
                )),
            },
            UnitFacts {
                id: "h3".into(),
                native: Some(native(
                    ExecutableKind::Hypothesis,
                    TerminalStatus::Completed,
                    1,
                    Some(2),
                )),
            },
            UnitFacts {
                id: "v3".into(),
                native: Some(native(
                    ExecutableKind::Verification,
                    TerminalStatus::Verified,
                    2,
                    Some(3),
                )),
            },
            UnitFacts {
                id: "goal".into(),
                native: Some(native(
                    ExecutableKind::GoalEvaluation,
                    TerminalStatus::Verified,
                    3,
                    Some(4),
                )),
            },
            UnitFacts {
                id: "end".into(),
                native: Some(native(
                    ExecutableKind::TerminationCheck,
                    TerminalStatus::Verified,
                    4,
                    None,
                )),
            },
        ];
        let state = StateFacts {
            final_revision: 4,
            initial_source: Some(0),
            goal_revisions: vec![4],
        };
        let relations = [relation("noise", "h3", "TEMPORAL", "CANDIDATE")];
        let result = classify(&RelevanceInput {
            units: &units,
            state: Some(&state),
            relations: &relations,
            user_roots: &[],
            max_depth: 8,
            budget_exhausted: false,
        });
        let classes: Vec<_> = result.classes.iter().map(|class| class.name()).collect();
        assert_eq!(
            classes,
            [
                "SUPPORTING",
                "ESSENTIAL",
                "EXCLUSION",
                "NOISE",
                "ESSENTIAL",
                "ESSENTIAL",
                "ESSENTIAL",
                "ESSENTIAL"
            ]
        );
        assert_eq!(class_of(&result, 3).1, ["TEMPORAL_ONLY"]);
        let root_refs: Vec<_> = result
            .roots
            .iter()
            .map(|root| root.reference.as_str())
            .collect();
        assert_eq!(
            root_refs,
            [
                "end",
                "goal",
                "rus:runtime:00000004",
                "state-transition:00000004"
            ]
        );
    }

    #[test]
    fn a_rejected_check_without_a_later_resolution_is_unresolved_not_an_exclusion() {
        let units = vec![
            UnitFacts {
                id: "h".into(),
                native: Some(native(
                    ExecutableKind::Hypothesis,
                    TerminalStatus::Completed,
                    0,
                    Some(1),
                )),
            },
            UnitFacts {
                id: "v".into(),
                native: Some(native(
                    ExecutableKind::Verification,
                    TerminalStatus::Rejected,
                    1,
                    None,
                )),
            },
        ];
        let state = StateFacts {
            final_revision: 1,
            initial_source: None,
            goal_revisions: vec![],
        };
        let result = classify(&RelevanceInput {
            units: &units,
            state: Some(&state),
            relations: &[],
            user_roots: &[],
            max_depth: 8,
            budget_exhausted: false,
        });
        assert_eq!(
            class_of(&result, 1),
            (RelevanceClass::Unresolved, vec!["SEARCH_UNRESOLVED"])
        );
    }

    #[test]
    fn native_rus_without_a_state_graph_are_never_dropped() {
        let units = vec![
            UnitFacts {
                id: "v".into(),
                native: Some(native(
                    ExecutableKind::Verification,
                    TerminalStatus::Completed,
                    0,
                    None,
                )),
            },
            UnitFacts {
                id: "end".into(),
                native: Some(native(
                    ExecutableKind::TerminationCheck,
                    TerminalStatus::Verified,
                    0,
                    None,
                )),
            },
        ];
        let result = classify(&RelevanceInput {
            units: &units,
            state: None,
            relations: &[],
            user_roots: &[],
            max_depth: 8,
            budget_exhausted: false,
        });
        assert_eq!(
            class_of(&result, 0),
            (RelevanceClass::Unresolved, vec!["STATE_GRAPH_UNAVAILABLE"])
        );
        assert!(result.diagnostics.contains(&"REL-008"));
    }
}
