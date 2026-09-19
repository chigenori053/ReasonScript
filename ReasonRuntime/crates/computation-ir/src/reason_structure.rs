use sha2::{Digest, Sha256};

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum ReasonUnitMode {
    #[default]
    Off,
    Ru,
    RuRus,
    RuRusRuo,
}

impl ReasonUnitMode {
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "off" => Some(Self::Off),
            "ru" => Some(Self::Ru),
            "ru_rus" => Some(Self::RuRus),
            "ru_rus_ruo" => Some(Self::RuRusRuo),
            _ => None,
        }
    }

    fn has_rus(self) -> bool {
        matches!(self, Self::RuRus | Self::RuRusRuo)
    }

    fn has_ruo(self) -> bool {
        self == Self::RuRusRuo
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::Off => "off",
            Self::Ru => "ru",
            Self::RuRus => "ru_rus",
            Self::RuRusRuo => "ru_rus_ruo",
        }
    }
}

#[derive(Default)]
pub struct ReasonStructure {
    mode: ReasonUnitMode,
    units: Vec<serde_json::Value>,
    states: Vec<serde_json::Value>,
    objects: Vec<serde_json::Value>,
    evidence: Vec<serde_json::Value>,
    relations: Vec<serde_json::Value>,
}

impl ReasonStructure {
    pub fn new(mode: ReasonUnitMode) -> Self {
        Self {
            mode,
            ..Self::default()
        }
    }

    pub fn record(
        &mut self,
        event_type: &str,
        subject: &serde_json::Value,
        evidence_value: &serde_json::Value,
    ) {
        if self.mode == ReasonUnitMode::Off {
            return;
        }
        let sequence = self.units.len() + 1;
        let ru_id = format!("ru:reasoning-event:{sequence:08}");
        let (kind, status) = classify(event_type);
        self.units.push(serde_json::json!({
            "id": ru_id,
            "kind": kind,
            "input_state_ref": if self.mode.has_rus() && sequence > 1 { serde_json::Value::String(format!("rus:reasoning@rev{}", sequence - 2)) } else { serde_json::Value::Null },
            "evidence_refs": [format!("evidence:reasoning:{sequence:08}")],
            "relation_refs": [format!("relation:reasoning:{sequence:08}")],
            "semantic_subject": subject,
            "source_event_type": event_type,
            "status": status,
        }));
        let evidence_id = format!("evidence:reasoning:{sequence:08}");
        self.evidence.push(serde_json::json!({
            "id": evidence_id,
            "kind": evidence_kind(event_type),
            "subject": subject,
            "value": evidence_value,
            "source_ru": ru_id,
        }));
        let relation_id = format!("relation:reasoning:{sequence:08}");
        self.relations.push(serde_json::json!({
            "id": relation_id,
            "kind": relation_kind(event_type),
            "source_ref": ru_id,
            "target_ref": evidence_id,
        }));

        if self.mode.has_rus() {
            let revision = self.states.len();
            self.states.push(serde_json::json!({
                "id": format!("rus:reasoning@rev{revision}"),
                "revision": revision,
                "changed_fields": changed_fields(event_type),
                "goal_status": goal_status(event_type),
                "semantic_subject": subject,
            }));
        }
        if self.mode.has_ruo() {
            self.objects.push(serde_json::json!({
                "id": format!("ruo:reasoning:{sequence:08}"),
                "reason_unit_ref": ru_id,
                "current_state_ref": format!("rus:reasoning@rev{}", sequence - 1),
                "evidence_refs": [evidence_id],
                "relation_refs": [relation_id],
                "lifecycle": ["CREATED", "ACTIVE", "COMPLETED"],
            }));
        }
    }

    pub fn trace(&self) -> serde_json::Value {
        serde_json::json!({
            "mode": self.mode.as_str(),
            "reason_units": self.units,
            "reason_unit_states": self.states,
            "reason_unit_objects": self.objects,
            "evidence": self.evidence,
            "relations": self.relations,
            "hashes": {
                "ru_sequence_hash": ru_hash(&self.units),
                "rus_transition_hash": rus_hash(&self.states),
                "ruo_graph_hash": hash(&self.objects),
                "hypothesis_sequence_hash": hypothesis_hash(&self.units, &self.evidence),
            }
        })
    }

    pub fn metrics(&self, vm_instruction_count: u64) -> serde_json::Value {
        let verified = self
            .units
            .iter()
            .filter(|unit| unit["status"] == "VERIFIED")
            .count();
        let rejected = self
            .units
            .iter()
            .filter(|unit| unit["status"] == "REJECTED")
            .count();
        let completed = self
            .units
            .iter()
            .filter(|unit| unit["status"] == "COMPLETED")
            .count();
        let executed = self.units.len();
        serde_json::json!({
            "ru_created_count": self.units.len(),
            "ru_executed_count": executed,
            "ru_verified_count": verified,
            "ru_rejected_count": rejected,
            "ru_completed_count": completed,
            "rus_created_count": self.states.len(),
            "rus_transition_count": self.states.len().saturating_sub(1),
            "rus_revision_count": self.states.len(),
            "rus_snapshot_bytes": serialized_len(&self.states),
            "ruo_created_count": self.objects.len(),
            "ruo_updated_count": self.objects.len(),
            "ruo_relation_count": self.relations.len(),
            "ruo_evidence_link_count": self.objects.len(),
            "reason_relation_created_count": self.relations.len(),
            "reason_relation_traversal_count": 0,
            "ru_allocated_bytes": serialized_len(&self.units),
            "rus_allocated_bytes": serialized_len(&self.states),
            "ruo_allocated_bytes": serialized_len(&self.objects),
            "relation_allocated_bytes": serialized_len(&self.relations),
            "ruvmr": if executed == 0 { serde_json::Value::Null } else { serde_json::json!(vm_instruction_count as f64 / executed as f64) },
            "ru_sequence_hash": ru_hash(&self.units),
            "rus_transition_hash": rus_hash(&self.states),
            "ruo_graph_hash": hash(&self.objects),
            "hypothesis_sequence_hash": hypothesis_hash(&self.units, &self.evidence),
        })
    }
}

fn classify(event_type: &str) -> (&'static str, &'static str) {
    match event_type {
        "HYPOTHESIS_VERIFIED" => ("VERIFICATION", "VERIFIED"),
        "HYPOTHESIS_REJECTED" | "CANDIDATE_PRUNED" => ("VERIFICATION", "REJECTED"),
        "STATE_TRANSITION" => ("STATE_TRANSITION", "COMPLETED"),
        "GOAL_UPDATED" => ("GOAL_EVALUATION", "COMPLETED"),
        "TERMINATION_INFERRED" => ("TERMINATION_CHECK", "COMPLETED"),
        "EVIDENCE_ADDED" => ("CONSTRAINT_DERIVATION", "COMPLETED"),
        _ => ("HYPOTHESIS", "CREATED"),
    }
}

fn evidence_kind(event_type: &str) -> &'static str {
    match event_type {
        "HYPOTHESIS_VERIFIED" => "FACTOR_CONFIRMED",
        "HYPOTHESIS_REJECTED" | "CANDIDATE_PRUNED" => "NOT_DIVISIBLE",
        "EVIDENCE_ADDED" => "CONSTRAINT_ADDED",
        "GOAL_UPDATED" | "TERMINATION_INFERRED" => "GOAL_REACHED",
        _ => "DIVISIBLE",
    }
}

fn relation_kind(event_type: &str) -> &'static str {
    match event_type {
        "HYPOTHESIS_VERIFIED" => "VERIFIES",
        "HYPOTHESIS_REJECTED" | "CANDIDATE_PRUNED" => "REJECTS",
        "STATE_TRANSITION" | "GOAL_UPDATED" => "UPDATES",
        "EVIDENCE_ADDED" => "DERIVES",
        "TERMINATION_INFERRED" => "CAUSES",
        _ => "REQUIRES",
    }
}

fn changed_fields(event_type: &str) -> Vec<&'static str> {
    match event_type {
        "CANDIDATE_GENERATED" | "CANDIDATE_PRUNED" => vec!["current_candidate"],
        "EVIDENCE_ADDED" => vec!["active_constraint_count"],
        "STATE_TRANSITION" => vec!["remaining", "current_candidate", "search_bound"],
        "GOAL_UPDATED" | "TERMINATION_INFERRED" => vec!["goal_status"],
        _ => Vec::new(),
    }
}

fn goal_status(event_type: &str) -> &'static str {
    if matches!(event_type, "GOAL_UPDATED" | "TERMINATION_INFERRED") {
        "REACHED"
    } else {
        "ACTIVE"
    }
}

fn hash(values: &[serde_json::Value]) -> String {
    let bytes = serde_json::to_vec(values).expect("JSON values are serializable");
    format!("sha256:{:x}", Sha256::digest(bytes))
}

fn serialized_len(values: &[serde_json::Value]) -> usize {
    serde_json::to_vec(values).map_or(0, |value| value.len())
}

fn ru_hash(units: &[serde_json::Value]) -> String {
    let tuples: Vec<_> = units
        .iter()
        .map(|unit| serde_json::json!([unit["kind"], unit["status"], unit["semantic_subject"]]))
        .collect();
    hash(&tuples)
}

fn rus_hash(states: &[serde_json::Value]) -> String {
    let tuples: Vec<_> = states
        .iter()
        .map(|state| {
            serde_json::json!([
                state["revision"],
                state["changed_fields"],
                state["goal_status"]
            ])
        })
        .collect();
    hash(&tuples)
}

fn hypothesis_hash(units: &[serde_json::Value], evidence: &[serde_json::Value]) -> String {
    let tuples: Vec<_> = units
        .iter()
        .zip(evidence)
        .filter(|(unit, _)| matches!(unit["kind"].as_str(), Some("HYPOTHESIS" | "VERIFICATION")))
        .map(|(unit, evidence)| {
            serde_json::json!([
                unit["source_event_type"],
                unit["semantic_subject"],
                evidence["value"]
            ])
        })
        .collect();
    hash(&tuples)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn explicit_layers_are_incremental_and_deterministic() {
        let event = |structure: &mut ReasonStructure| {
            structure.record(
                "HYPOTHESIS_VERIFIED",
                &serde_json::json!(11),
                &serde_json::json!({"divisible": true}),
            );
        };
        let mut ru = ReasonStructure::new(ReasonUnitMode::Ru);
        let mut rus = ReasonStructure::new(ReasonUnitMode::RuRus);
        let mut ruo = ReasonStructure::new(ReasonUnitMode::RuRusRuo);
        event(&mut ru);
        event(&mut rus);
        event(&mut ruo);
        assert_eq!(ru.trace()["reason_unit_states"], serde_json::json!([]));
        assert_eq!(
            rus.trace()["reason_unit_states"].as_array().unwrap().len(),
            1
        );
        assert_eq!(
            ruo.trace()["reason_unit_objects"].as_array().unwrap().len(),
            1
        );
        assert_eq!(
            rus.trace()["hashes"]["ru_sequence_hash"],
            ruo.trace()["hashes"]["ru_sequence_hash"]
        );
    }

    #[test]
    fn off_mode_materializes_nothing() {
        let mut structure = ReasonStructure::default();
        structure.record(
            "HYPOTHESIS_CREATED",
            &serde_json::json!(3),
            &serde_json::json!({}),
        );
        assert_eq!(structure.metrics(4)["ru_created_count"], 0);
    }
}
