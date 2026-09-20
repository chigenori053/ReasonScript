use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::time::Instant;

pub const DEFAULT_MAX_CAUSAL_DEPTH: usize = 8;
pub const DEFAULT_MAX_COUNTERFACTUAL_RUNS: usize = 32;

#[derive(Clone, Copy, Debug, Default, Deserialize, Eq, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum CausalMode {
    #[default]
    Off,
    Dependency,
    Counterfactual,
    Full,
}

impl CausalMode {
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "off" => Some(Self::Off),
            "dependency" => Some(Self::Dependency),
            "counterfactual" => Some(Self::Counterfactual),
            "full" => Some(Self::Full),
            _ => None,
        }
    }

    fn counterfactual(self) -> bool {
        matches!(self, Self::Counterfactual | Self::Full)
    }
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct CausalObservation {
    pub ru_id: String,
    #[serde(default)]
    pub produces: Vec<String>,
    #[serde(default)]
    pub requires: Vec<String>,
    #[serde(default)]
    pub requires_any: Vec<Vec<String>>,
    #[serde(default)]
    pub blocked_by: Vec<String>,
    #[serde(default = "default_true")]
    pub success: bool,
}

fn default_true() -> bool {
    true
}

#[derive(Clone, Debug)]
pub struct CausalConfig {
    pub mode: CausalMode,
    pub max_causal_depth: usize,
    pub max_counterfactual_runs: usize,
}

impl Default for CausalConfig {
    fn default() -> Self {
        Self {
            mode: CausalMode::Off,
            max_causal_depth: DEFAULT_MAX_CAUSAL_DEPTH,
            max_counterfactual_runs: DEFAULT_MAX_COUNTERFACTUAL_RUNS,
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct CausalRelation {
    pub id: String,
    pub source_ref: String,
    pub target_ref: String,
    pub relation_kind: &'static str,
    pub evidence_refs: Vec<String>,
    pub dependency: Option<bool>,
    pub necessity: Option<bool>,
    pub sufficiency: Option<bool>,
    pub polarity: &'static str,
    pub modality: &'static str,
    pub status: &'static str,
    pub provenance: serde_json::Value,
}

#[derive(Clone, Debug, Serialize)]
pub struct CounterfactualResult {
    pub id: String,
    pub source_ref: String,
    pub target_ref: String,
    pub suppressed_evidence_refs: Vec<String>,
    pub observed_success: bool,
    pub counterfactual_success: bool,
    pub runtime_ns: u64,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct CausalMetrics {
    pub causal_candidate_count: u64,
    pub causal_dependency_count: u64,
    pub causal_confirmed_count: u64,
    pub causal_rejected_count: u64,
    pub causal_conflict_count: u64,
    pub counterfactual_run_count: u64,
    pub counterfactual_success_count: u64,
    pub counterfactual_failure_count: u64,
    pub causal_traversal_count: u64,
    pub causal_max_depth: u64,
    pub causal_evaluation_ns: u64,
    pub normal_runtime_ns: u64,
    pub counterfactual_runtime_ns: u64,
    pub cost_per_intervention_ns: u64,
    pub counterfactual_cost_ratio: Option<f64>,
}

#[derive(Clone, Debug, Serialize)]
pub struct CausalTrace {
    pub schema: &'static str,
    pub relations: Vec<CausalRelation>,
    pub counterfactuals: Vec<CounterfactualResult>,
    pub metrics: CausalMetrics,
    pub hashes: BTreeMap<&'static str, String>,
    pub diagnostics: Vec<&'static str>,
}

impl CausalTrace {
    pub fn extend_relations(&mut self, relations: impl IntoIterator<Item = CausalRelation>) {
        self.relations.extend(relations);
        self.relations.sort_by(|left, right| {
            (&left.source_ref, &left.target_ref, left.relation_kind).cmp(&(
                &right.source_ref,
                &right.target_ref,
                right.relation_kind,
            ))
        });
        for (index, relation) in self.relations.iter_mut().enumerate() {
            relation.id = format!("causal-relation:{:08}", index + 1);
        }
        self.hashes
            .insert("causal_relation_hash", stable_hash(&self.relations));
    }
}

pub fn evaluate(observations: &[CausalObservation], config: &CausalConfig) -> CausalTrace {
    let started = Instant::now();
    if config.mode == CausalMode::Off {
        return empty_trace(started);
    }

    let mut producers: BTreeMap<&str, Vec<&str>> = BTreeMap::new();
    let by_id: BTreeMap<&str, &CausalObservation> = observations
        .iter()
        .map(|observation| (observation.ru_id.as_str(), observation))
        .collect();
    for observation in observations {
        for evidence in &observation.produces {
            producers
                .entry(evidence)
                .or_default()
                .push(&observation.ru_id);
        }
    }

    let mut diagnostics = Vec::new();
    if by_id.len() != observations.len() {
        diagnostics.push("CAUSAL-001");
    }
    let mut candidates: BTreeMap<(String, String), Candidate> = BTreeMap::new();
    for target in observations {
        for evidence in target
            .requires
            .iter()
            .chain(target.requires_any.iter().flatten())
        {
            if evidence.is_empty() {
                if !diagnostics.contains(&"CAUSAL-002") {
                    diagnostics.push("CAUSAL-002");
                }
            } else if !producers.contains_key(evidence.as_str())
                && !diagnostics.contains(&"CAUSAL-003")
            {
                diagnostics.push("CAUSAL-003");
            }
            for source in producers.get(evidence.as_str()).into_iter().flatten() {
                if *source != target.ru_id {
                    candidates
                        .entry(((*source).to_owned(), target.ru_id.clone()))
                        .or_default()
                        .required
                        .insert(evidence.clone());
                }
            }
        }
        for evidence in &target.blocked_by {
            for source in producers.get(evidence.as_str()).into_iter().flatten() {
                if *source != target.ru_id {
                    candidates
                        .entry(((*source).to_owned(), target.ru_id.clone()))
                        .or_default()
                        .blocked
                        .insert(evidence.clone());
                }
            }
        }
    }

    let mut metrics = CausalMetrics {
        causal_candidate_count: candidates.len() as u64,
        ..CausalMetrics::default()
    };
    let mut relations = Vec::new();
    let mut counterfactuals = Vec::new();
    let mut relation_number = 0_u64;

    for ((source_id, target_id), candidate) in &candidates {
        relation_number += 1;
        let source = by_id[source_id.as_str()];
        let target = by_id[target_id.as_str()];
        let conflict = !candidate.required.is_empty() && !candidate.blocked.is_empty();
        let dependency = !candidate.required.is_empty();
        metrics.causal_dependency_count += u64::from(dependency);
        let mut necessity = None;
        let mut counterfactual_ref = serde_json::Value::Null;
        let mut counterfactual_success = target.success;
        let mut budget_exhausted = false;

        if config.mode.counterfactual() {
            if metrics.counterfactual_run_count >= config.max_counterfactual_runs as u64 {
                budget_exhausted = true;
                if !diagnostics.contains(&"CAUSAL-BUDGET-001") {
                    diagnostics.push("CAUSAL-BUDGET-001");
                }
            } else {
                let counterfactual_started = Instant::now();
                let suppressed: BTreeSet<&str> =
                    source.produces.iter().map(String::as_str).collect();
                counterfactual_success = succeeds_without(target, &suppressed, &producers);
                let runtime_ns = counterfactual_started.elapsed().as_nanos() as u64;
                metrics.counterfactual_run_count += 1;
                metrics.counterfactual_runtime_ns += runtime_ns;
                if counterfactual_success {
                    metrics.counterfactual_success_count += 1;
                } else {
                    metrics.counterfactual_failure_count += 1;
                }
                necessity = dependency.then_some(target.success && !counterfactual_success);
                let id = format!("counterfactual:{:08}", counterfactuals.len() + 1);
                counterfactual_ref = serde_json::Value::String(id.clone());
                counterfactuals.push(CounterfactualResult {
                    id,
                    source_ref: source_id.clone(),
                    target_ref: target_id.clone(),
                    suppressed_evidence_refs: source.produces.clone(),
                    observed_success: target.success,
                    counterfactual_success,
                    runtime_ns,
                });
            }
        }

        let (kind, polarity, status) = if budget_exhausted {
            ("DEPENDENCY", "POSITIVE", "INSUFFICIENT")
        } else if conflict {
            metrics.causal_conflict_count += 1;
            ("DEPENDENCY", "POSITIVE", "CONFLICT")
        } else if !candidate.blocked.is_empty() && !target.success && counterfactual_success {
            metrics.causal_confirmed_count += 1;
            ("PREVENTS", "NEGATIVE", "CONFIRMED")
        } else if necessity == Some(true) {
            metrics.causal_confirmed_count += 1;
            ("CAUSES", "POSITIVE", "CONFIRMED")
        } else if dependency && necessity == Some(false) {
            metrics.causal_rejected_count += 1;
            ("DEPENDENCY", "POSITIVE", "REJECTED")
        } else if dependency {
            ("DEPENDENCY", "POSITIVE", "SUPPORTED")
        } else {
            metrics.causal_rejected_count += 1;
            ("TEMPORAL", "POSITIVE", "REJECTED")
        };
        let mut evidence_refs: Vec<_> = candidate
            .required
            .union(&candidate.blocked)
            .cloned()
            .collect();
        evidence_refs.sort();
        relations.push(CausalRelation {
            id: format!("causal-relation:{relation_number:08}"),
            source_ref: source_id.clone(),
            target_ref: target_id.clone(),
            relation_kind: kind,
            evidence_refs: evidence_refs.clone(),
            dependency: Some(dependency),
            necessity,
            sufficiency: None,
            polarity,
            modality: "ACTUAL",
            status,
            provenance: serde_json::json!({
                "evidence_refs": evidence_refs,
                "counterfactual_result_ref": counterfactual_ref,
                "explanation_trace": explanation(source_id, target_id, kind, necessity),
            }),
        });
    }

    add_temporal_only(observations, &mut relations, &mut relation_number);
    add_transitive_relations(
        &mut relations,
        &mut relation_number,
        config.max_causal_depth,
        &mut metrics,
        &mut diagnostics,
    );
    relations.sort_by(|left, right| {
        (&left.source_ref, &left.target_ref, left.relation_kind).cmp(&(
            &right.source_ref,
            &right.target_ref,
            right.relation_kind,
        ))
    });
    for (index, relation) in relations.iter_mut().enumerate() {
        relation.id = format!("causal-relation:{:08}", index + 1);
    }
    metrics.cost_per_intervention_ns = if metrics.counterfactual_run_count == 0 {
        0
    } else {
        metrics.counterfactual_runtime_ns / metrics.counterfactual_run_count
    };
    metrics.causal_evaluation_ns = started.elapsed().as_nanos() as u64;
    let relation_hash = stable_hash(&relations);
    CausalTrace {
        schema: "reasonscript-causal-trace/0.1",
        relations,
        counterfactuals,
        metrics,
        hashes: BTreeMap::from([("causal_relation_hash", relation_hash)]),
        diagnostics,
    }
}

#[derive(Default)]
struct Candidate {
    required: BTreeSet<String>,
    blocked: BTreeSet<String>,
}

fn succeeds_without(
    target: &CausalObservation,
    suppressed: &BTreeSet<&str>,
    producers: &BTreeMap<&str, Vec<&str>>,
) -> bool {
    let available =
        |evidence: &str| producers.contains_key(evidence) && !suppressed.contains(evidence);
    target.requires.iter().all(|evidence| available(evidence))
        && target
            .requires_any
            .iter()
            .all(|group| group.iter().any(|evidence| available(evidence)))
        && target
            .blocked_by
            .iter()
            .all(|evidence| !available(evidence))
}

fn add_temporal_only(
    observations: &[CausalObservation],
    relations: &mut Vec<CausalRelation>,
    relation_number: &mut u64,
) {
    for pair in observations.windows(2) {
        if relations.iter().any(|relation| {
            relation.source_ref == pair[0].ru_id && relation.target_ref == pair[1].ru_id
        }) {
            continue;
        }
        *relation_number += 1;
        relations.push(CausalRelation {
            id: format!("causal-relation:{relation_number:08}"),
            source_ref: pair[0].ru_id.clone(),
            target_ref: pair[1].ru_id.clone(),
            relation_kind: "TEMPORAL",
            evidence_refs: Vec::new(),
            dependency: Some(false),
            necessity: None,
            sufficiency: None,
            polarity: "POSITIVE",
            modality: "ACTUAL",
            status: "CANDIDATE",
            provenance: serde_json::json!({"evidence_refs": [], "counterfactual_result_ref": null, "explanation_trace": ["source executed before target; no evidence dependency"]}),
        });
    }
}

fn add_transitive_relations(
    relations: &mut Vec<CausalRelation>,
    relation_number: &mut u64,
    max_depth: usize,
    metrics: &mut CausalMetrics,
    diagnostics: &mut Vec<&'static str>,
) {
    let direct: BTreeMap<String, Vec<String>> = relations
        .iter()
        .filter(|relation| relation.relation_kind == "CAUSES" && relation.status == "CONFIRMED")
        .fold(BTreeMap::new(), |mut graph, relation| {
            graph
                .entry(relation.source_ref.clone())
                .or_default()
                .push(relation.target_ref.clone());
            graph
        });
    let mut additions = BTreeSet::new();
    for source in direct.keys() {
        let mut stack = vec![(source.clone(), 0_usize, BTreeSet::from([source.clone()]))];
        while let Some((current, depth, visited)) = stack.pop() {
            if depth >= max_depth {
                continue;
            }
            for target in direct.get(&current).into_iter().flatten() {
                metrics.causal_traversal_count += 1;
                metrics.causal_max_depth = metrics.causal_max_depth.max((depth + 1) as u64);
                if visited.contains(target) {
                    if !diagnostics.contains(&"CAUSAL-CYCLE-001") {
                        diagnostics.push("CAUSAL-CYCLE-001");
                    }
                    continue;
                }
                if depth >= 1 {
                    additions.insert((source.clone(), target.clone(), depth + 1));
                }
                let mut next_visited = visited.clone();
                next_visited.insert(target.clone());
                stack.push((target.clone(), depth + 1, next_visited));
            }
        }
    }
    for (source, target, depth) in additions {
        if source == target
            || relations
                .iter()
                .any(|relation| relation.source_ref == source && relation.target_ref == target)
        {
            continue;
        }
        *relation_number += 1;
        relations.push(CausalRelation {
            id: format!("causal-relation:{relation_number:08}"),
            source_ref: source,
            target_ref: target,
            relation_kind: "CAUSES",
            evidence_refs: Vec::new(),
            dependency: Some(true),
            necessity: Some(true),
            sufficiency: None,
            polarity: "POSITIVE",
            modality: "ACTUAL",
            status: "CONFIRMED",
            provenance: serde_json::json!({"evidence_refs": [], "counterfactual_result_ref": null, "indirect": true, "depth": depth}),
        });
        metrics.causal_confirmed_count += 1;
    }
}

fn explanation(source: &str, target: &str, kind: &str, necessity: Option<bool>) -> Vec<String> {
    let mut trace = vec![format!("{source} produced evidence referenced by {target}")];
    if necessity == Some(true) {
        trace.push(format!(
            "suppressing {source} evidence caused {target} to fail"
        ));
    } else if kind == "PREVENTS" {
        trace.push(format!(
            "suppressing {source} evidence allowed {target} to succeed"
        ));
    }
    trace
}

fn stable_hash(relations: &[CausalRelation]) -> String {
    let values: Vec<_> = relations
        .iter()
        .map(|relation| {
            serde_json::json!([
                relation.source_ref,
                relation.target_ref,
                relation.relation_kind,
                relation.dependency,
                relation.necessity,
                relation.sufficiency,
                relation.status,
            ])
        })
        .collect();
    format!(
        "sha256:{:x}",
        Sha256::digest(serde_json::to_vec(&values).unwrap())
    )
}

fn empty_trace(started: Instant) -> CausalTrace {
    CausalTrace {
        schema: "reasonscript-causal-trace/0.1",
        relations: Vec::new(),
        counterfactuals: Vec::new(),
        metrics: CausalMetrics {
            causal_evaluation_ns: started.elapsed().as_nanos() as u64,
            ..CausalMetrics::default()
        },
        hashes: BTreeMap::from([("causal_relation_hash", stable_hash(&[]))]),
        diagnostics: Vec::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn observation(
        id: &str,
        produces: &[&str],
        requires: &[&str],
        success: bool,
    ) -> CausalObservation {
        CausalObservation {
            ru_id: id.into(),
            produces: produces.iter().map(|value| (*value).into()).collect(),
            requires: requires.iter().map(|value| (*value).into()).collect(),
            requires_any: Vec::new(),
            blocked_by: Vec::new(),
            success,
        }
    }

    #[test]
    fn direct_counterfactual_cause_and_temporal_only_are_distinct() {
        let input = vec![
            observation("A", &["E"], &[], true),
            observation("B", &[], &["E"], true),
            observation("C", &[], &[], true),
        ];
        let trace = evaluate(
            &input,
            &CausalConfig {
                mode: CausalMode::Counterfactual,
                ..CausalConfig::default()
            },
        );
        assert!(trace
            .relations
            .iter()
            .any(|relation| relation.source_ref == "A"
                && relation.target_ref == "B"
                && relation.relation_kind == "CAUSES"
                && relation.necessity == Some(true)));
        assert!(trace
            .relations
            .iter()
            .any(|relation| relation.source_ref == "B"
                && relation.target_ref == "C"
                && relation.relation_kind == "TEMPORAL"
                && relation.dependency == Some(false)));
    }

    #[test]
    fn alternative_evidence_makes_a_dependency_non_necessary() {
        let mut target = observation("B", &[], &[], true);
        target.requires_any = vec![vec!["E".into(), "E2".into()]];
        let trace = evaluate(
            &[
                observation("A", &["E"], &[], true),
                observation("C", &["E2"], &[], true),
                target,
            ],
            &CausalConfig {
                mode: CausalMode::Counterfactual,
                ..CausalConfig::default()
            },
        );
        assert!(trace
            .relations
            .iter()
            .any(|relation| relation.source_ref == "A"
                && relation.target_ref == "B"
                && relation.necessity == Some(false)));
    }

    #[test]
    fn preventive_cause_is_confirmed() {
        let mut target = observation("B", &[], &[], false);
        target.blocked_by = vec!["REJECTION".into()];
        let trace = evaluate(
            &[observation("A", &["REJECTION"], &[], true), target],
            &CausalConfig {
                mode: CausalMode::Counterfactual,
                ..CausalConfig::default()
            },
        );
        assert_eq!(trace.relations[0].relation_kind, "PREVENTS");
        assert_eq!(trace.relations[0].status, "CONFIRMED");
    }

    #[test]
    fn chain_cycle_budget_and_hash_are_deterministic() {
        let chain = vec![
            observation("A", &["E1"], &["E3"], true),
            observation("B", &["E2"], &["E1"], true),
            observation("C", &["E3"], &["E2"], true),
        ];
        let config = CausalConfig {
            mode: CausalMode::Counterfactual,
            max_causal_depth: 8,
            max_counterfactual_runs: 32,
        };
        let hashes: BTreeSet<_> = (0..3)
            .map(|_| evaluate(&chain, &config).hashes["causal_relation_hash"].clone())
            .collect();
        let trace = evaluate(&chain, &config);
        assert_eq!(hashes.len(), 1);
        assert!(trace.diagnostics.contains(&"CAUSAL-CYCLE-001"));
        let budget_trace = evaluate(
            &chain,
            &CausalConfig {
                max_counterfactual_runs: 2,
                ..config
            },
        );
        assert!(budget_trace.diagnostics.contains(&"CAUSAL-BUDGET-001"));
    }
}
