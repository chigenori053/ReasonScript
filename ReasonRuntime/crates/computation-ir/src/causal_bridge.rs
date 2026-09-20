use crate::causal::CausalObservation;
use crate::reason_structure::{ExecutableMode, ReasonStructure, TerminalStatus};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::time::Instant;

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CausalObservationSource {
    #[default]
    External,
    Native,
    Merge,
}

impl CausalObservationSource {
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "external" => Some(Self::External),
            "native" => Some(Self::Native),
            "merge" => Some(Self::Merge),
            _ => None,
        }
    }
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct CausalBridgeMetrics {
    pub causal_bridge_ru_count: u64,
    pub causal_bridge_evidence_count: u64,
    pub causal_bridge_relation_count: u64,
    pub causal_bridge_observation_count: u64,
    pub causal_bridge_missing_evidence_count: u64,
    pub causal_bridge_invalid_relation_count: u64,
    pub causal_bridge_runtime_ns: u64,
    pub observation_coverage_ratio: f64,
    pub evidence_link_coverage: f64,
}

#[derive(Clone, Debug, Serialize)]
pub struct CausalBridgeProjection {
    pub source: CausalObservationSource,
    pub observations: Vec<CausalObservation>,
    pub observation_count: usize,
    pub observation_hash: String,
    pub diagnostics: Vec<String>,
    pub metrics: CausalBridgeMetrics,
}

pub fn project(
    structure: &ReasonStructure,
    source: CausalObservationSource,
) -> CausalBridgeProjection {
    let started = Instant::now();
    let (units, evidence, relations) = structure.executable_causal_parts();
    let mut diagnostics = Vec::new();
    if structure.executable_mode() == ExecutableMode::Off {
        diagnostics.push("CAUSAL-BRIDGE-007".to_owned());
    } else if structure.executable_mode() != ExecutableMode::Full {
        diagnostics.push("CAUSAL-BRIDGE-008".to_owned());
    }

    let mut observations: Vec<_> = units
        .iter()
        .map(|unit| CausalObservation {
            ru_id: unit.id.clone(),
            produces: Vec::new(),
            requires: Vec::new(),
            requires_any: Vec::new(),
            blocked_by: Vec::new(),
            success: unit.terminal_status != Some(TerminalStatus::Rejected),
        })
        .collect();
    let unit_indexes: BTreeMap<_, _> = observations
        .iter()
        .enumerate()
        .map(|(index, observation)| (observation.ru_id.clone(), index))
        .collect();
    let evidence_ids: BTreeSet<_> = evidence
        .iter()
        .filter_map(|item| item["id"].as_str().map(str::to_owned))
        .collect();
    let mut producers = BTreeMap::new();
    let mut linked_evidence = BTreeSet::new();
    let mut metrics = CausalBridgeMetrics {
        causal_bridge_ru_count: units.len() as u64,
        causal_bridge_evidence_count: evidence.len() as u64,
        causal_bridge_relation_count: relations.len() as u64,
        ..CausalBridgeMetrics::default()
    };

    for relation in relations {
        let kind = relation["kind"].as_str().unwrap_or_default();
        let source_ref = relation["source_ref"].as_str().unwrap_or_default();
        let target_ref = relation["target_ref"].as_str().unwrap_or_default();
        match kind {
            "PRODUCES" => {
                let Some(&unit_index) = unit_indexes.get(source_ref) else {
                    diagnostics.push("CAUSAL-BRIDGE-002".to_owned());
                    metrics.causal_bridge_invalid_relation_count += 1;
                    continue;
                };
                if !evidence_ids.contains(target_ref) {
                    diagnostics.push("CAUSAL-BRIDGE-001".to_owned());
                    metrics.causal_bridge_missing_evidence_count += 1;
                    continue;
                }
                if producers.insert(target_ref, source_ref).is_some() {
                    diagnostics.push("CAUSAL-BRIDGE-004".to_owned());
                    metrics.causal_bridge_invalid_relation_count += 1;
                    continue;
                }
                observations[unit_index]
                    .produces
                    .push(target_ref.to_owned());
                linked_evidence.insert(target_ref);
            }
            "REQUIRES" | "PREVENTS" => {
                let Some(&unit_index) = unit_indexes.get(source_ref) else {
                    diagnostics.push("CAUSAL-BRIDGE-002".to_owned());
                    metrics.causal_bridge_invalid_relation_count += 1;
                    continue;
                };
                if !evidence_ids.contains(target_ref) {
                    diagnostics.push("CAUSAL-BRIDGE-001".to_owned());
                    metrics.causal_bridge_missing_evidence_count += 1;
                    continue;
                }
                if kind == "REQUIRES" {
                    observations[unit_index]
                        .requires
                        .push(target_ref.to_owned());
                } else {
                    observations[unit_index]
                        .blocked_by
                        .push(target_ref.to_owned());
                }
                linked_evidence.insert(target_ref);
            }
            "ENABLES" | "DERIVES" | "VERIFIES" | "REJECTS" | "UPDATES" => {}
            _ => {
                diagnostics.push("CAUSAL-BRIDGE-005".to_owned());
                metrics.causal_bridge_invalid_relation_count += 1;
            }
        }
    }
    for observation in &mut observations {
        observation.produces.sort();
        observation.produces.dedup();
        observation.requires.sort();
        observation.requires.dedup();
        observation.blocked_by.sort();
        observation.blocked_by.dedup();
    }
    diagnostics.sort();
    diagnostics.dedup();
    metrics.causal_bridge_observation_count = observations.len() as u64;
    metrics.observation_coverage_ratio = ratio(observations.len(), units.len());
    metrics.evidence_link_coverage = ratio(linked_evidence.len(), evidence.len());
    metrics.causal_bridge_runtime_ns = started.elapsed().as_nanos() as u64;
    let observation_hash = observation_hash(&observations);
    CausalBridgeProjection {
        source,
        observation_count: observations.len(),
        observations,
        observation_hash,
        diagnostics,
        metrics,
    }
}

pub fn merge(
    native: CausalBridgeProjection,
    external: &[CausalObservation],
) -> CausalBridgeProjection {
    let mut projection = native;
    projection.source = CausalObservationSource::Merge;
    let mut indexes: BTreeMap<_, _> = projection
        .observations
        .iter()
        .enumerate()
        .map(|(index, observation)| (observation.ru_id.clone(), index))
        .collect();
    for observation in external {
        if let Some(&index) = indexes.get(&observation.ru_id) {
            if projection.observations[index] != *observation {
                projection.diagnostics.push("CAUSAL-BRIDGE-006".to_owned());
            }
        } else {
            indexes.insert(observation.ru_id.clone(), projection.observations.len());
            projection.observations.push(observation.clone());
        }
    }
    projection.diagnostics.sort();
    projection.diagnostics.dedup();
    projection.observation_count = projection.observations.len();
    projection.metrics.causal_bridge_observation_count = projection.observation_count as u64;
    projection.observation_hash = observation_hash(&projection.observations);
    projection
}

pub fn external(observations: Vec<CausalObservation>) -> CausalBridgeProjection {
    let observation_hash = observation_hash(&observations);
    CausalBridgeProjection {
        source: CausalObservationSource::External,
        observation_count: observations.len(),
        metrics: CausalBridgeMetrics {
            causal_bridge_observation_count: observations.len() as u64,
            ..CausalBridgeMetrics::default()
        },
        observations,
        observation_hash,
        diagnostics: Vec::new(),
    }
}

fn observation_hash(observations: &[CausalObservation]) -> String {
    format!(
        "sha256:{:x}",
        Sha256::digest(serde_json::to_vec(observations).unwrap())
    )
}

fn ratio(numerator: usize, denominator: usize) -> f64 {
    if denominator == 0 {
        1.0
    } else {
        numerator as f64 / denominator as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::reason_structure::{ExecutableKind, ReasonUnitSource};

    #[test]
    fn typed_projection_extracts_producer_consumer_outcome_and_hash() {
        let mut structure = ReasonStructure::default();
        structure.set_executable_mode(ExecutableMode::Full);
        let producer = structure.begin_executable(
            ExecutableKind::Hypothesis,
            ReasonUnitSource::Runtime,
            "candidate",
            serde_json::json!(7),
            serde_json::Value::Null,
        );
        let producer_ref = structure.executable_ref(&producer).unwrap();
        structure
            .finish_executable(
                producer,
                TerminalStatus::Completed,
                serde_json::Value::Null,
                Some("CANDIDATE_ADOPTED"),
                serde_json::json!(7),
            )
            .unwrap();
        let evidence_ref = structure.evidence_ref_for_ru(&producer_ref).unwrap();
        let consumer = structure.begin_executable(
            ExecutableKind::Verification,
            ReasonUnitSource::Runtime,
            "verify",
            serde_json::json!(7),
            serde_json::Value::Null,
        );
        let consumer_ref = structure.executable_ref(&consumer).unwrap();
        structure
            .record_reason_relation("REQUIRES", &consumer_ref, &evidence_ref)
            .unwrap();
        structure
            .finish_executable(
                consumer,
                TerminalStatus::Verified,
                serde_json::Value::Null,
                None,
                serde_json::Value::Null,
            )
            .unwrap();
        let first = project(&structure, CausalObservationSource::Native);
        let second = project(&structure, CausalObservationSource::Native);
        assert!(first.diagnostics.is_empty());
        assert_eq!(first.observations[0].produces, [evidence_ref.clone()]);
        assert_eq!(first.observations[1].requires, [evidence_ref]);
        assert!(first.observations[1].success);
        assert_eq!(first.observation_hash, second.observation_hash);
    }

    #[test]
    fn strict_projection_reports_missing_and_duplicate_evidence_links() {
        let mut structure = ReasonStructure::default();
        structure.set_executable_mode(ExecutableMode::Full);
        let producer = structure.begin_executable(
            ExecutableKind::Hypothesis,
            ReasonUnitSource::Runtime,
            "candidate",
            serde_json::json!(7),
            serde_json::Value::Null,
        );
        let producer_ref = structure.executable_ref(&producer).unwrap();
        structure
            .finish_executable(
                producer,
                TerminalStatus::Completed,
                serde_json::Value::Null,
                Some("CANDIDATE_ADOPTED"),
                serde_json::json!(7),
            )
            .unwrap();
        let evidence_ref = structure.evidence_ref_for_ru(&producer_ref).unwrap();
        structure
            .record_reason_relation("PRODUCES", &producer_ref, &evidence_ref)
            .unwrap();
        structure
            .record_reason_relation("REQUIRES", &producer_ref, "evidence:missing")
            .unwrap();
        let projection = project(&structure, CausalObservationSource::Native);
        assert!(projection
            .diagnostics
            .contains(&"CAUSAL-BRIDGE-001".to_owned()));
        assert!(projection
            .diagnostics
            .contains(&"CAUSAL-BRIDGE-004".to_owned()));
    }
}
