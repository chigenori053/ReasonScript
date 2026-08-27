use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::canonical::checksum;

#[derive(Clone, Debug, Deserialize, PartialEq, Eq, Serialize)]
pub struct UeraPartition {
    pub partition_index: usize,
    pub operation_id: String,
    pub partition_id: String,
    pub preferred_worker: String,
    pub assigned_worker: String,
    pub fallback_used: bool,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Eq, Serialize)]
pub struct UeraPlan {
    pub schema_version: String,
    pub policy_version: String,
    pub source_plan_hash: String,
    pub partitions: Vec<UeraPartition>,
    pub reduction_order: Vec<String>,
}

/// Build only orchestration metadata. Execution remains the responsibility of
/// the worker's existing UEO backend adapter.
pub fn build_uera_plan(
    execution_plan: &Value,
    operation_ids: &[String],
    worker_ids: &[String],
    available_worker_ids: &[String],
    policy_version: &str,
) -> Result<UeraPlan, String> {
    let workers: Vec<_> = worker_ids
        .iter()
        .cloned()
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    if workers.is_empty() {
        return Err("CRR-UER-001: no cluster workers configured".into());
    }
    let available: BTreeSet<_> = available_worker_ids.iter().cloned().collect();
    if available.is_empty() {
        return Err("CRR-UER-002: no cluster workers available".into());
    }
    if !available.iter().all(|worker| workers.contains(worker)) {
        return Err("CRR-UER-003: available worker is not configured".into());
    }

    let source_plan_hash = checksum(execution_plan).map_err(|error| error.to_string())?;
    let mut partitions = Vec::with_capacity(operation_ids.len());
    for (partition_index, operation_id) in operation_ids.iter().enumerate() {
        let preferred_index = partition_index % workers.len();
        let preferred_worker = workers[preferred_index].clone();
        let assigned_worker = (0..workers.len())
            .map(|offset| &workers[(preferred_index + offset) % workers.len()])
            .find(|worker| available.contains(*worker))
            .cloned()
            .ok_or("CRR-UER-002: no cluster workers available")?;
        let partition_id = checksum(&json!({
            "execution_plan": execution_plan,
            "operation_id": operation_id,
            "partition_index": partition_index,
            "policy_version": policy_version,
        }))
        .map_err(|error| error.to_string())?;
        partitions.push(UeraPartition {
            partition_index,
            operation_id: operation_id.clone(),
            partition_id,
            fallback_used: assigned_worker != preferred_worker,
            preferred_worker,
            assigned_worker,
        });
    }
    let reduction_order = partitions
        .iter()
        .map(|partition| partition.partition_id.clone())
        .collect();
    Ok(UeraPlan {
        schema_version: "reasonscript-cluster-uera-plan/0.1".into(),
        policy_version: policy_version.into(),
        source_plan_hash,
        partitions,
        reduction_order,
    })
}
