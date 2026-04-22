use std::cmp::Ordering;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SearchConfig {
    pub beam_width: usize,
    pub quantization_unit: i64,
    pub global_window: usize,
    pub fallback_stagnation_steps: usize,
    pub fallback_extra_width: usize,
    pub exploration_injection_stride: usize,
    pub enable_depth_diversification: bool,
    pub dominance_top_k: usize,
    pub max_visited_records: usize,
}

impl Default for SearchConfig {
    fn default() -> Self {
        Self {
            beam_width: 4,
            quantization_unit: 1,
            global_window: 32,
            fallback_stagnation_steps: 2,
            fallback_extra_width: 2,
            exploration_injection_stride: 4,
            enable_depth_diversification: true,
            dominance_top_k: 3,
            max_visited_records: 1024,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct TransitionSignature(String);

impl TransitionSignature {
    pub fn from_raw(raw: impl Into<String>) -> Self {
        Self(raw.into())
    }

    pub fn from_fields<K, V, I>(fields: I) -> Self
    where
        K: Into<String>,
        V: Into<String>,
        I: IntoIterator<Item = (K, V)>,
    {
        let mut normalized: Vec<(String, String)> = fields
            .into_iter()
            .map(|(key, value)| (normalize_signature_component(key.into()), normalize_signature_component(value.into())))
            .collect();
        normalized.sort();
        Self(
            normalized
                .into_iter()
                .map(|(key, value)| format!("{key}={value}"))
                .collect::<Vec<_>>()
                .join("|"),
        )
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct StepIndex {
    pub depth: usize,
    pub local_order: u64,
    pub global_seq: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BranchNode<S> {
    pub branch_id: String,
    pub parent_branch_id: Option<String>,
    pub transition_signature: TransitionSignature,
    pub state: S,
    pub state_hash: String,
    pub depth: usize,
    pub step_index: StepIndex,
    pub score_raw: i64,
    pub score_quantized: i64,
    pub is_goal: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Expansion<S> {
    pub transition_signature: TransitionSignature,
    pub state: S,
    pub state_hash: String,
    pub score_raw: i64,
    pub is_goal: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExpandedParent<S> {
    pub parent: BranchNode<S>,
    pub children: Vec<Expansion<S>>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SearchSnapshot<S> {
    pub beam: Vec<BranchNode<S>>,
    pub global_visited: BTreeMap<String, Vec<VisitedRecord>>,
    pub next_local_order: u64,
    pub next_global_seq: u64,
    pub best_goal: Option<BranchNode<S>>,
    pub best_frontier_score: Option<i64>,
    pub stagnation_steps: usize,
    pub current_depth: usize,
    pub history: BTreeMap<String, BranchNode<S>>,
    pub branch_id_mapping: BTreeMap<String, Option<String>>,
    pub active_lineage_set: BTreeSet<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StepOutcome<S> {
    pub beam: Vec<BranchNode<S>>,
    pub best_goal: Option<BranchNode<S>>,
    pub expanded_children: usize,
    pub retained_children: usize,
    pub pruned_children: usize,
    pub effective_beam_width: usize,
    pub active_lineage_set: BTreeSet<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VisitedRecord {
    pub score_raw: i64,
    pub depth: usize,
    pub branch_id: String,
    pub last_seen_depth: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BeamSearch<S> {
    config: SearchConfig,
    beam: Vec<BranchNode<S>>,
    global_visited: BTreeMap<String, Vec<VisitedRecord>>,
    next_local_order: u64,
    next_global_seq: u64,
    best_goal: Option<BranchNode<S>>,
    best_frontier_score: Option<i64>,
    stagnation_steps: usize,
    current_depth: usize,
    history: BTreeMap<String, BranchNode<S>>,
    branch_id_mapping: BTreeMap<String, Option<String>>,
    active_lineage_set: BTreeSet<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct CandidateDraft<S> {
    parent_branch_id: String,
    transition_signature: TransitionSignature,
    state: S,
    state_hash: String,
    depth: usize,
    score_raw: i64,
    score_quantized: i64,
    is_goal: bool,
}

impl<S: Clone + Ord> BeamSearch<S> {
    pub fn new(config: SearchConfig, roots: Vec<Expansion<S>>) -> Self {
        assert!(!roots.is_empty(), "BeamSearch requires at least one root");

        let mut search = Self {
            config,
            beam: Vec::new(),
            global_visited: BTreeMap::new(),
            next_local_order: 0,
            next_global_seq: 0,
            best_goal: None,
            best_frontier_score: None,
            stagnation_steps: 0,
            current_depth: 0,
            history: BTreeMap::new(),
            branch_id_mapping: BTreeMap::new(),
            active_lineage_set: BTreeSet::new(),
        };

        let root_parent = BranchNode {
            branch_id: "root".to_string(),
            parent_branch_id: None,
            transition_signature: TransitionSignature::from_raw("root"),
            state: roots[0].state.clone(),
            state_hash: "root".to_string(),
            depth: 0,
            step_index: StepIndex {
                depth: 0,
                local_order: 0,
                global_seq: 0,
            },
            score_raw: i64::MIN,
            score_quantized: i64::MIN,
            is_goal: false,
        };

        let outcome = search.step_from_expanded(vec![ExpandedParent {
            parent: root_parent,
            children: roots,
        }]);
        search.beam = outcome.beam;
        search.best_goal = outcome.best_goal;
        search
    }

    pub fn from_snapshot(config: SearchConfig, snapshot: SearchSnapshot<S>) -> Self {
        Self {
            config,
            beam: snapshot.beam,
            global_visited: snapshot.global_visited,
            next_local_order: snapshot.next_local_order,
            next_global_seq: snapshot.next_global_seq,
            best_goal: snapshot.best_goal,
            best_frontier_score: snapshot.best_frontier_score,
            stagnation_steps: snapshot.stagnation_steps,
            current_depth: snapshot.current_depth,
            history: snapshot.history,
            branch_id_mapping: snapshot.branch_id_mapping,
            active_lineage_set: snapshot.active_lineage_set,
        }
    }

    pub fn snapshot(&self) -> SearchSnapshot<S> {
        SearchSnapshot {
            beam: self.beam.clone(),
            global_visited: self.global_visited.clone(),
            next_local_order: self.next_local_order,
            next_global_seq: self.next_global_seq,
            best_goal: self.best_goal.clone(),
            best_frontier_score: self.best_frontier_score,
            stagnation_steps: self.stagnation_steps,
            current_depth: self.current_depth,
            history: self.history.clone(),
            branch_id_mapping: self.branch_id_mapping.clone(),
            active_lineage_set: self.active_lineage_set.clone(),
        }
    }

    pub fn beam(&self) -> &[BranchNode<S>] {
        &self.beam
    }

    pub fn best_goal(&self) -> Option<&BranchNode<S>> {
        self.best_goal.as_ref()
    }

    pub fn history(&self) -> &BTreeMap<String, BranchNode<S>> {
        &self.history
    }

    pub fn active_lineage_set(&self) -> &BTreeSet<String> {
        &self.active_lineage_set
    }

    pub fn step<F>(&mut self, mut expand: F) -> StepOutcome<S>
    where
        F: FnMut(&BranchNode<S>) -> Vec<Expansion<S>>,
    {
        let expanded = self
            .beam
            .iter()
            .cloned()
            .map(|parent| ExpandedParent {
                children: expand(&parent),
                parent,
            })
            .collect();

        self.step_from_expanded(expanded)
    }

    pub fn step_from_expanded(&mut self, mut expanded: Vec<ExpandedParent<S>>) -> StepOutcome<S> {
        expanded.sort_by(|left, right| compare_nodes(&left.parent, &right.parent));

        let mut drafts = Vec::new();
        let mut expanded_children = 0usize;
        let mut pruned_children = 0usize;

        for expanded_parent in expanded {
            let child_depth = if expanded_parent.parent.branch_id == "root" {
                0
            } else {
                expanded_parent.parent.depth + 1
            };

            for child in expanded_parent.children {
                expanded_children += 1;
                drafts.push(CandidateDraft {
                    parent_branch_id: expanded_parent.parent.branch_id.clone(),
                    transition_signature: child.transition_signature,
                    state: child.state,
                    state_hash: child.state_hash,
                    depth: child_depth,
                    score_raw: child.score_raw,
                    score_quantized: quantize_score(child.score_raw, self.config.quantization_unit),
                    is_goal: child.is_goal,
                });
            }
        }

        drafts.sort_by(compare_drafts);

        let mut candidates = Vec::new();

        for draft in drafts {
            let branch_id = branch_id(Some(draft.parent_branch_id.as_str()), draft.transition_signature.as_str());
            let node = BranchNode {
                branch_id: branch_id.clone(),
                parent_branch_id: Some(draft.parent_branch_id.clone()),
                transition_signature: draft.transition_signature,
                state: draft.state,
                state_hash: draft.state_hash,
                depth: draft.depth,
                step_index: StepIndex {
                    depth: draft.depth,
                    local_order: self.next_local_order,
                    global_seq: self.next_global_seq,
                },
                score_raw: draft.score_raw,
                score_quantized: draft.score_quantized,
                is_goal: draft.is_goal,
            };

            self.next_local_order += 1;
            self.next_global_seq += 1;
            self.current_depth = self.current_depth.max(node.depth);

            if self.is_dominated(&node) {
                pruned_children += 1;
                continue;
            }

            self.update_visited(&node);
            self.branch_id_mapping
                .insert(branch_id.clone(), node.parent_branch_id.clone());
            self.history.insert(branch_id, node.clone());

            if node.is_goal {
                self.update_best_goal(&node);
            }

            candidates.push(node);
        }

        let effective_beam_width =
            self.effective_beam_width(candidates.iter().map(|candidate| candidate.score_raw).max());
        let beam = select_beam(
            candidates,
            effective_beam_width,
            self.config.enable_depth_diversification,
            self.config.exploration_injection_stride,
        );

        self.best_frontier_score = beam.iter().map(|node| node.score_raw).max();
        self.beam = beam.clone();
        self.refresh_active_lineage_set();
        self.evict_visited();

        StepOutcome {
            retained_children: beam.len(),
            best_goal: self.best_goal.clone(),
            beam,
            expanded_children,
            pruned_children,
            effective_beam_width,
            active_lineage_set: self.active_lineage_set.clone(),
        }
    }

    fn effective_beam_width(&mut self, candidate_best_score: Option<i64>) -> usize {
        match (self.best_frontier_score, candidate_best_score) {
            (Some(previous), Some(current)) if current > previous => self.stagnation_steps = 0,
            (Some(_), Some(_)) => self.stagnation_steps += 1,
            _ => self.stagnation_steps = 0,
        }

        if self.stagnation_steps >= self.config.fallback_stagnation_steps {
            self.config.beam_width + self.config.fallback_extra_width
        } else {
            self.config.beam_width
        }
    }

    fn is_dominated(&self, node: &BranchNode<S>) -> bool {
        let epsilon = self.config.quantization_unit / 2;
        let Some(records) = self.global_visited.get(&node.state_hash) else {
            return false;
        };

        if records.is_empty() {
            return false;
        }

        records.iter().all(|record| {
            node.score_raw + epsilon < record.score_raw && node.depth >= record.depth
        })
    }

    fn update_visited(&mut self, node: &BranchNode<S>) {
        let records = self.global_visited.entry(node.state_hash.clone()).or_default();
        records.push(VisitedRecord {
            score_raw: node.score_raw,
            depth: node.depth,
            branch_id: node.branch_id.clone(),
            last_seen_depth: node.depth,
        });
        records.sort_by(compare_visited_records);
        records.dedup_by(|left, right| left.branch_id == right.branch_id);
        records.truncate(self.config.dominance_top_k.max(1));
    }

    fn update_best_goal(&mut self, node: &BranchNode<S>) {
        let should_update = self
            .best_goal
            .as_ref()
            .is_none_or(|best| compare_nodes(node, best) == Ordering::Less);

        if should_update {
            self.best_goal = Some(node.clone());
        }
    }

    fn refresh_active_lineage_set(&mut self) {
        let mut lineage = BTreeSet::new();
        for node in &self.beam {
            let mut current = Some(node.branch_id.clone());
            while let Some(branch_id) = current {
                if !lineage.insert(branch_id.clone()) {
                    break;
                }
                current = self
                    .branch_id_mapping
                    .get(&branch_id)
                    .and_then(|parent| parent.clone());
            }
        }
        self.active_lineage_set = lineage;
    }

    fn evict_visited(&mut self) {
        let min_depth = self.current_depth.saturating_sub(self.config.global_window);

        self.global_visited.retain(|_, records| {
            records.retain(|record| {
                self.active_lineage_set.contains(&record.branch_id) || record.depth >= min_depth
            });
            !records.is_empty()
        });

        let protected_count: usize = self
            .global_visited
            .values()
            .map(|records| {
                records
                    .iter()
                    .filter(|record| self.active_lineage_set.contains(&record.branch_id))
                    .count()
            })
            .sum();

        if protected_count >= self.config.max_visited_records {
            return;
        }

        let mut total_records: usize = self.global_visited.values().map(Vec::len).sum();
        if total_records <= self.config.max_visited_records {
            return;
        }

        let mut eviction_candidates = Vec::new();
        for (state_hash, records) in &self.global_visited {
            for (index, record) in records.iter().enumerate() {
                if self.active_lineage_set.contains(&record.branch_id) {
                    continue;
                }
                eviction_candidates.push((
                    state_hash.clone(),
                    index,
                    record.score_raw,
                    record.depth,
                    record.last_seen_depth,
                    record.branch_id.clone(),
                ));
            }
        }

        eviction_candidates.sort_by(|left, right| {
            left.2
                .cmp(&right.2)
                .then_with(|| left.3.cmp(&right.3))
                .then_with(|| left.4.cmp(&right.4))
                .then_with(|| left.5.cmp(&right.5))
        });

        for (state_hash, index, _, _, _, _) in eviction_candidates {
            if total_records <= self.config.max_visited_records {
                break;
            }
            let mut remove_key = false;
            if let Some(records) = self.global_visited.get_mut(&state_hash) {
                if index < records.len() && !self.active_lineage_set.contains(&records[index].branch_id) {
                    records.remove(index);
                    total_records -= 1;
                }
                remove_key = records.is_empty();
            }
            if remove_key {
                self.global_visited.remove(&state_hash);
            }
        }
    }
}

fn select_beam<S: Clone + Ord>(
    candidates: Vec<BranchNode<S>>,
    beam_width: usize,
    enable_depth_diversification: bool,
    exploration_injection_stride: usize,
) -> Vec<BranchNode<S>> {
    if beam_width == 0 || candidates.is_empty() {
        return Vec::new();
    }

    let mut deduped_by_state = BTreeMap::new();
    for candidate in candidates {
        deduped_by_state
            .entry(candidate.state_hash.clone())
            .and_modify(|current: &mut BranchNode<S>| {
                if compare_nodes(&candidate, current) == Ordering::Less {
                    *current = candidate.clone();
                }
            })
            .or_insert(candidate);
    }

    let mut ordered: Vec<_> = deduped_by_state.into_values().collect();
    ordered.sort_by(compare_nodes);

    let reserve_injection = usize::from(beam_width > 1 && exploration_injection_stride > 0);
    let normal_slots = beam_width.saturating_sub(reserve_injection);
    let mut selected = Vec::new();
    let mut selected_ids = BTreeSet::new();

    if enable_depth_diversification {
        let mut seen_depths = BTreeSet::new();
        for candidate in &ordered {
            if selected.len() >= normal_slots {
                break;
            }
            if seen_depths.insert(candidate.depth) && selected_ids.insert(candidate.branch_id.clone()) {
                selected.push(candidate.clone());
            }
        }
    }

    for candidate in &ordered {
        if selected.len() >= normal_slots {
            break;
        }
        if selected_ids.insert(candidate.branch_id.clone()) {
            selected.push(candidate.clone());
        }
    }

    if reserve_injection == 1 {
        let injected = ordered
            .iter()
            .rev()
            .find(|candidate| {
                !selected_ids.contains(&candidate.branch_id)
                    && hash_u64(&candidate.branch_id) % exploration_injection_stride as u64 == 0
            })
            .cloned()
            .or_else(|| {
                ordered
                    .iter()
                    .find(|candidate| !selected_ids.contains(&candidate.branch_id))
                    .cloned()
            });

        if let Some(candidate) = injected {
            selected.push(candidate);
        }
    }

    selected.sort_by(compare_nodes);
    selected.truncate(beam_width);
    selected
}

fn compare_drafts<S: Ord>(left: &CandidateDraft<S>, right: &CandidateDraft<S>) -> Ordering {
    right
        .score_quantized
        .cmp(&left.score_quantized)
        .then_with(|| right.score_raw.cmp(&left.score_raw))
        .then_with(|| left.depth.cmp(&right.depth))
        .then_with(|| left.parent_branch_id.cmp(&right.parent_branch_id))
        .then_with(|| left.transition_signature.cmp(&right.transition_signature))
        .then_with(|| left.state_hash.cmp(&right.state_hash))
        .then_with(|| left.state.cmp(&right.state))
}

fn compare_nodes<S: Ord>(left: &BranchNode<S>, right: &BranchNode<S>) -> Ordering {
    right
        .score_quantized
        .cmp(&left.score_quantized)
        .then_with(|| right.score_raw.cmp(&left.score_raw))
        .then_with(|| left.depth.cmp(&right.depth))
        .then_with(|| left.step_index.cmp(&right.step_index))
        .then_with(|| left.branch_id.cmp(&right.branch_id))
        .then_with(|| left.state_hash.cmp(&right.state_hash))
        .then_with(|| left.state.cmp(&right.state))
}

fn compare_visited_records(left: &VisitedRecord, right: &VisitedRecord) -> Ordering {
    right
        .score_raw
        .cmp(&left.score_raw)
        .then_with(|| left.depth.cmp(&right.depth))
        .then_with(|| left.branch_id.cmp(&right.branch_id))
}

fn quantize_score(score_raw: i64, quantization_unit: i64) -> i64 {
    if quantization_unit <= 1 {
        score_raw
    } else {
        let epsilon = quantization_unit / 2;
        (score_raw + epsilon).div_euclid(quantization_unit)
    }
}

fn branch_id(parent_branch_id: Option<&str>, transition_signature: &str) -> String {
    let mut input = String::new();
    if let Some(parent_branch_id) = parent_branch_id {
        input.push_str(parent_branch_id);
    }
    input.push('|');
    input.push_str(transition_signature);
    format!("{:016x}", hash_u64(&input))
}

fn normalize_signature_component(input: String) -> String {
    input
        .chars()
        .flat_map(|ch| match ch {
            '\\' => "\\\\".chars().collect::<Vec<_>>(),
            '|' => "\\|".chars().collect(),
            '=' => "\\=".chars().collect(),
            _ => vec![ch],
        })
        .collect()
}

fn hash_u64(input: &str) -> u64 {
    const FNV_OFFSET: u64 = 0xcbf29ce484222325;
    const FNV_PRIME: u64 = 0x100000001b3;

    let mut hash = FNV_OFFSET;
    for byte in input.as_bytes() {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(FNV_PRIME);
    }
    hash
}
