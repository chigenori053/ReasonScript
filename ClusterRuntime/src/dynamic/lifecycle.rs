use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct LifecycleEvent {
    pub schema_version: String,
    pub sequence: usize,
    pub logical_step: usize,
    pub epoch: usize,
    pub reason_unit_id: String,
    pub from: Option<String>,
    pub to: String,
    pub reason: String,
    pub details: Value,
}

#[derive(Default)]
pub struct LifecycleStore {
    states: BTreeMap<String, String>,
    pub events: Vec<LifecycleEvent>,
    reactivations: BTreeMap<String, usize>,
}
impl LifecycleStore {
    pub fn state(&self, id: &str) -> Option<&str> {
        self.states.get(id).map(String::as_str)
    }
    pub fn transition(
        &mut self,
        id: &str,
        to: &str,
        step: usize,
        reason: &str,
        details: Value,
        max_reactivations: usize,
    ) -> Result<(), String> {
        let from = self.states.get(id).map(String::as_str);
        if !allowed(from, to) {
            return Err(format!(
                "DRU-LFC-001: invalid lifecycle transition {:?} -> {to} for {id}",
                from
            ));
        }
        if from == Some("suspended") && to == "ready" {
            let n = self.reactivations.entry(id.into()).or_default();
            *n += 1;
            if *n > max_reactivations {
                return Err(format!("DRU-LFC-003: reactivation limit exceeded for {id}"));
            }
        }
        self.events.push(LifecycleEvent {
            schema_version: "reasonscript-dynamic-unit-lifecycle/0.1".into(),
            sequence: self.events.len() + 1,
            logical_step: step,
            epoch: step,
            reason_unit_id: id.into(),
            from: from.map(str::to_string),
            to: to.into(),
            reason: reason.into(),
            details,
        });
        self.states.insert(id.into(), to.into());
        Ok(())
    }
}
pub fn allowed(from: Option<&str>, to: &str) -> bool {
    matches!(
        (from, to),
        (None, "proposed")
            | (Some("proposed"), "validated" | "rejected")
            | (Some("validated"), "registered" | "rejected")
            | (Some("registered"), "inactive" | "ready" | "replaced")
            | (Some("inactive"), "ready" | "retired" | "replaced")
            | (
                Some("ready"),
                "assigned" | "suspended" | "cancelled" | "replaced"
            )
            | (Some("assigned"), "running" | "cancelled")
            | (
                Some("running"),
                "waiting" | "completed" | "failed" | "suspended"
            )
            | (Some("waiting"), "running" | "suspended" | "failed")
            | (
                Some("suspended"),
                "ready" | "retired" | "replaced" | "cancelled"
            )
            | (Some("failed"), "ready" | "retired" | "replaced")
            | (Some("completed"), "retired")
    )
}
