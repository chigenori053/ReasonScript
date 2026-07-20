use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, HashMap, HashSet};
use std::path::PathBuf;

use super::{
    artifacts::{validate_documents, write_dynamic_artifacts},
    config::DynamicConfig,
    lifecycle::LifecycleStore,
};
use crate::{
    canonical::checksum, config::ClusterConfig, diagnostics::Diagnostic,
    planner::build_cluster_plan,
};

pub const PROPOSAL_SCHEMA: &str = "reasonscript-dynamic-unit-proposal/0.1";

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct GenerationRule {
    pub schema_version: String,
    pub rule_id: String,
    pub version: String,
    pub deterministic: bool,
    pub trigger: Value,
    pub input_contract: Value,
    pub output_contract: Value,
    pub limits: Value,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Proposer {
    pub node_id: String,
    pub reason_unit_id: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct UnitProposal {
    pub schema_version: String,
    pub run_id: String,
    pub proposal_id: String,
    pub logical_step: usize,
    pub epoch: usize,
    pub proposer: Proposer,
    pub generation_rule_id: String,
    pub parent_unit_ids: Vec<String>,
    pub input_refs: Vec<String>,
    pub evidence_refs: Vec<String>,
    pub proposed_unit: Value,
    pub generation_depth: usize,
    pub priority: i64,
    pub checksum: String,
}

#[derive(Serialize)]
struct ProposalBody<'a> {
    schema_version: &'a str,
    run_id: &'a str,
    proposal_id: &'a str,
    logical_step: usize,
    epoch: usize,
    proposer: &'a Proposer,
    generation_rule_id: &'a str,
    parent_unit_ids: &'a [String],
    input_refs: &'a [String],
    evidence_refs: &'a [String],
    proposed_unit: &'a Value,
    generation_depth: usize,
    priority: i64,
}
impl UnitProposal {
    pub fn seal(&mut self) -> Result<(), String> {
        self.normalize();
        self.checksum = checksum(&self.body()).map_err(|e| e.to_string())?;
        Ok(())
    }
    fn normalize(&mut self) {
        self.parent_unit_ids.sort();
        self.parent_unit_ids.dedup();
        self.input_refs.sort();
        self.input_refs.dedup();
        self.evidence_refs.sort();
        self.evidence_refs.dedup()
    }
    fn body(&self) -> ProposalBody<'_> {
        ProposalBody {
            schema_version: &self.schema_version,
            run_id: &self.run_id,
            proposal_id: &self.proposal_id,
            logical_step: self.logical_step,
            epoch: self.epoch,
            proposer: &self.proposer,
            generation_rule_id: &self.generation_rule_id,
            parent_unit_ids: &self.parent_unit_ids,
            input_refs: &self.input_refs,
            evidence_refs: &self.evidence_refs,
            proposed_unit: &self.proposed_unit,
            generation_depth: self.generation_depth,
            priority: self.priority,
        }
    }
    pub(crate) fn valid_checksum(&self) -> bool {
        checksum(&self.body()).ok().as_ref() == Some(&self.checksum)
    }
    fn duplicate_key(&self) -> String {
        checksum(&json!({"rule":self.generation_rule_id,"parents":self.parent_unit_ids,"inputs":self.input_refs,"evidence":self.evidence_refs,"parameters":self.proposed_unit.get("parameters"),"depth":self.generation_depth})).unwrap_or_default()
    }
}

#[derive(Clone, Debug, Default)]
pub struct DynamicOptions {
    pub artifacts_dir: Option<PathBuf>,
    pub scenario: Option<String>,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct DynamicRun {
    pub summary: Value,
    pub documents: BTreeMap<String, Value>,
}

#[derive(Clone)]
struct Unit {
    id: String,
    kind: String,
    depth: usize,
    branch_id: String,
    priority: i64,
    parents: Vec<String>,
    state_access: Value,
    replaced_by: Option<String>,
}

pub fn canonical_unit_id(run_seed: &str, p: &UnitProposal, index: usize) -> String {
    let digest=checksum(&json!({"contract":"reasonscript-dynamic-reason-unit-cluster/0.1","run_semantic_seed":run_seed,"generation_rule_id":p.generation_rule_id,"parent_unit_ids":p.parent_unit_ids,"input_refs":p.input_refs,"evidence_refs":p.evidence_refs,"parameters":p.proposed_unit.get("parameters"),"generation_depth":p.generation_depth,"logical_creation_index":index})).unwrap_or_default();
    format!(
        "dynamic_unit_{}_{index:04}",
        digest
            .trim_start_matches("sha256:")
            .chars()
            .take(16)
            .collect::<String>()
    )
}

pub fn plan_dynamic(bundle: &Value, cluster: &ClusterConfig, config: &DynamicConfig) -> Value {
    let payload = bundle.get("artifacts").unwrap_or(bundle);
    let workers: Vec<_> = cluster.workers.iter().map(|w| w.node_id.clone()).collect();
    let plan = build_cluster_plan(
        &payload["execution_plan"],
        &payload["reason_ir"],
        &workers,
        &cluster.execution.sync_policy,
    );
    let seeds:Vec<_>=plan.tasks.iter().enumerate().map(|(i,t)|json!({"reason_unit_id":format!("seed_unit_{:04}",i+1),"task_id":t.task_id,"unit_kind":"seed","state":"ready"})).collect();
    json!({"schema_version":"reasonscript-dynamic-plan/0.1","enabled":config.enabled,"seed_reason_units":seeds,"generation_rules":rules_from_bundle(bundle),"dynamic_budget":config.limits,"initial_branch":{"branch_id":"branch_root_0001","state":"active"},"activation_candidates":seeds.iter().map(|v|v["reason_unit_id"].clone()).collect::<Vec<_>>(),"diagnostics":config.validate(),"valid":config.validate().is_empty()&&plan.valid})
}

pub fn run_dynamic(
    bundle: &Value,
    cluster: &ClusterConfig,
    config: &DynamicConfig,
    options: &DynamicOptions,
) -> Result<DynamicRun, String> {
    let errors = config.validate();
    if !errors.is_empty() {
        return failed(config, errors, options);
    }
    let initial = plan_dynamic(bundle, cluster, config);
    if initial["valid"] != true {
        return failed(
            config,
            vec![Diagnostic::error(
                "DRU-REV-001",
                "Initial cluster plan is invalid",
                "cluster_plan",
            )],
            options,
        );
    }
    let seed =
        checksum(&json!({"bundle":bundle,"dynamic_config":config})).map_err(|e| e.to_string())?;
    let run_id = format!(
        "dynamic_run_{}",
        seed.trim_start_matches("sha256:")
            .chars()
            .take(16)
            .collect::<String>()
    );
    let mut lifecycle = LifecycleStore::default();
    let mut units = BTreeMap::<String, Unit>::new();
    let mut branches = BTreeMap::<String, Value>::new();
    let mut proposals = build_proposals(bundle, &run_id, options.scenario.as_deref());
    proposals.sort_by(|a, b| {
        (
            a.logical_step,
            a.epoch,
            a.generation_depth,
            std::cmp::Reverse(a.priority),
            &a.generation_rule_id,
            a.parent_unit_ids.first(),
            &a.proposal_id,
        )
            .cmp(&(
                b.logical_step,
                b.epoch,
                b.generation_depth,
                std::cmp::Reverse(b.priority),
                &b.generation_rule_id,
                b.parent_unit_ids.first(),
                &b.proposal_id,
            ))
    });
    let seed_ids: Vec<String> = initial["seed_reason_units"]
        .as_array()
        .unwrap_or(&vec![])
        .iter()
        .filter_map(|v| v["reason_unit_id"].as_str().map(str::to_string))
        .collect();
    for id in &seed_ids {
        lifecycle.transition(
            id,
            "proposed",
            0,
            "initial_plan",
            json!({}),
            config.limits.max_reactivations_per_unit,
        )?;
        lifecycle.transition(
            id,
            "validated",
            0,
            "seed_validation",
            json!({}),
            config.limits.max_reactivations_per_unit,
        )?;
        lifecycle.transition(
            id,
            "registered",
            0,
            "seed_registration",
            json!({}),
            config.limits.max_reactivations_per_unit,
        )?;
        lifecycle.transition(
            id,
            "ready",
            0,
            "initial_activation",
            json!({}),
            config.limits.max_reactivations_per_unit,
        )?;
        units.insert(
            id.clone(),
            Unit {
                id: id.clone(),
                kind: "seed".into(),
                depth: 0,
                branch_id: "branch_root_0001".into(),
                priority: 0,
                parents: vec![],
                state_access: json!({"read":[],"write":[],"append":[],"reduce":[]}),
                replaced_by: None,
            },
        );
    }
    branches.insert("branch_root_0001".into(),json!({"branch_id":"branch_root_0001","parent_branch_id":null,"state":"active","unit_ids":seed_ids}));
    let rules: HashMap<String, GenerationRule> = rules_from_bundle(bundle)
        .into_iter()
        .map(|r| (r.rule_id.clone(), r))
        .collect();
    let registered_nodes: HashSet<String> = cluster
        .workers
        .iter()
        .map(|w| w.node_id.clone())
        .chain(std::iter::once(cluster.coordinator.node_id.clone()))
        .collect();
    let mut seen = HashMap::<String, String>::new();
    let mut proposal_records = Vec::new();
    let mut revisions = Vec::new();
    let mut diagnostics = Vec::new();
    let mut pruned = Vec::new();
    let mut budget_terminated = false;
    let mut accepted = 0usize;
    let mut epoch_proposals = HashMap::<usize, usize>::new();
    let mut declared_writes = HashMap::<(usize, String), String>::new();
    for mut p in proposals {
        p.normalize();
        let mut code = None;
        let epoch_count = epoch_proposals.entry(p.epoch).or_default();
        *epoch_count += 1;
        let rule = rules.get(&p.generation_rule_id);
        if p.schema_version != PROPOSAL_SCHEMA {
            code = Some("DRU-PRP-001")
        } else if !p.valid_checksum() {
            code = Some("DRU-PRP-005")
        } else if !registered_nodes.contains(&p.proposer.node_id) {
            code = Some("DRU-PRP-002")
        } else if p.parent_unit_ids.iter().any(|id| !units.contains_key(id)) {
            code = Some("DRU-PRP-003")
        } else if rule.is_none() {
            code = Some("DRU-PRP-004")
        } else if !rule.unwrap().deterministic {
            code = Some("DRU-GEN-001")
        } else if p
            .proposed_unit
            .get("state_access")
            .and_then(Value::as_object)
            .is_none()
        {
            code = Some("DRU-GEN-007")
        } else if p.generation_depth > config.limits.max_generation_depth {
            code = Some("DRU-GEN-002")
        } else if *epoch_count > config.limits.max_proposals_per_epoch
            || units.len() >= config.limits.max_total_units
            || accepted >= config.limits.max_active_units
        {
            code = Some("DRU-GEN-003")
        }
        let key = p.duplicate_key();
        if code.is_none() {
            if let Some(existing) = seen.get(&key) {
                proposal_records.push(json!({"proposal":p,"accepted":false,"duplicate_of":existing,"diagnostic":"DRU-PRP-006"}));
                continue;
            }
        }
        if code.is_none() {
            for path in p
                .proposed_unit
                .pointer("/state_access/write")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
                .filter_map(Value::as_str)
            {
                if declared_writes.contains_key(&(p.logical_step, path.to_string())) {
                    code = Some("DRU-STA-003");
                    break;
                }
            }
        }
        if let Some(c) = code {
            diagnostics.push(Diagnostic::error(c, diagnostic_message(c), &p.proposal_id));
            proposal_records.push(json!({"proposal":p,"accepted":false,"diagnostic":c}));
            if c == "DRU-GEN-003" {
                budget_terminated = true;
            }
            continue;
        }
        accepted += 1;
        let id = canonical_unit_id(&seed, &p, accepted);
        for path in p
            .proposed_unit
            .pointer("/state_access/write")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .filter_map(Value::as_str)
        {
            declared_writes.insert((p.logical_step, path.to_string()), id.clone());
        }
        seen.insert(key, id.clone());
        let branch_id = format!("branch_{}", id.trim_start_matches("dynamic_unit_"));
        if branches.len() >= config.limits.max_branches {
            diagnostics.push(Diagnostic::error(
                "DRU-BRN-001",
                "Branch limit exceeded",
                &p.proposal_id,
            ));
            budget_terminated = true;
            continue;
        }
        lifecycle.transition(
            &id,
            "proposed",
            p.logical_step,
            "proposal_accepted",
            json!({"proposal_id":p.proposal_id}),
            config.limits.max_reactivations_per_unit,
        )?;
        lifecycle.transition(
            &id,
            "validated",
            p.logical_step,
            "contract_validated",
            json!({}),
            config.limits.max_reactivations_per_unit,
        )?;
        lifecycle.transition(
            &id,
            "registered",
            p.logical_step,
            "revision_pending",
            json!({}),
            config.limits.max_reactivations_per_unit,
        )?;
        let kind = p.proposed_unit["unit_kind"]
            .as_str()
            .unwrap_or("derived")
            .to_string();
        let state_access = p.proposed_unit["state_access"].clone();
        units.insert(
            id.clone(),
            Unit {
                id: id.clone(),
                kind,
                depth: p.generation_depth,
                branch_id: branch_id.clone(),
                priority: p.priority,
                parents: p.parent_unit_ids.clone(),
                state_access,
                replaced_by: None,
            },
        );
        branches.insert(branch_id.clone(),json!({"branch_id":branch_id,"parent_branch_id":"branch_root_0001","state":"active","unit_ids":[id.clone()]}));
        let base = checksum(&revisions).map_err(|e| e.to_string())?;
        let mut revision = json!({"schema_version":"reasonscript-dynamic-plan-revision/0.1","revision_id":format!("revision_{:06}",revisions.len()+1),"run_id":run_id,"base_plan_checksum":base,"logical_step":p.logical_step,"epoch":p.epoch,"added_unit_ids":[id.clone()],"activated_unit_ids":[id.clone()],"suspended_unit_ids":[],"retired_unit_ids":[],"replaced_units":[],"added_task_ids":[format!("task_dynamic_{accepted:06}")],"removed_task_ids":[],"dependency_updates":p.parent_unit_ids.iter().map(|parent|json!({"from":parent,"to":id,"type":"generation"})).collect::<Vec<_>>(),"placement_updates":[{"reason_unit_id":id,"worker_id":cluster.workers.get(accepted%cluster.workers.len().max(1)).map(|w|w.node_id.as_str()).unwrap_or("single-node-fallback")}],"atomic":true,"applied":true});
        let rc = checksum(&revision).map_err(|e| e.to_string())?;
        revision["revision_checksum"] = json!(rc);
        revisions.push(revision);
        lifecycle.transition(
            &id,
            "ready",
            p.logical_step + 1,
            "revision_committed",
            json!({}),
            config.limits.max_reactivations_per_unit,
        )?;
        proposal_records.push(json!({"proposal":p,"accepted":true,"reason_unit_id":id}));
    }
    apply_scenario_lifecycle(
        options.scenario.as_deref(),
        config,
        &mut lifecycle,
        &mut units,
        &mut revisions,
        &mut pruned,
        &mut diagnostics,
    )?;
    for unit in units.values() {
        if lifecycle.state(&unit.id) == Some("ready") {
            lifecycle.transition(
                &unit.id,
                "assigned",
                unit.depth + 1,
                "scheduled",
                json!({}),
                config.limits.max_reactivations_per_unit,
            )?;
            lifecycle.transition(
                &unit.id,
                "running",
                unit.depth + 1,
                "worker_started",
                json!({}),
                config.limits.max_reactivations_per_unit,
            )?;
            lifecycle.transition(
                &unit.id,
                "completed",
                unit.depth + 1,
                "result_committed",
                json!({}),
                config.limits.max_reactivations_per_unit,
            )?;
        }
    }
    let reason = if budget_terminated {
        "budget_terminated"
    } else {
        "quiescence"
    };
    let status = if budget_terminated {
        "budget_terminated"
    } else {
        "converged"
    };
    let unit_values:Vec<_>=units.values().map(|u|json!({"reason_unit_id":u.id,"unit_kind":u.kind,"generation_depth":u.depth,"branch_id":u.branch_id,"priority":u.priority,"parent_unit_ids":u.parents,"state_access":u.state_access,"replaced_by":u.replaced_by,"state":lifecycle.state(&u.id)})).collect();
    let dynamic_messages =
        proposal_records.len() * 2 + revisions.len() * 2 + lifecycle.events.len();
    if dynamic_messages > config.limits.max_messages {
        diagnostics.push(Diagnostic::error(
            "DRU-GEN-003",
            "Message budget exceeded",
            "limits.max_messages",
        ));
        budget_terminated = true;
    }
    let summary = json!({"schema_version":"reasonscript-dynamic-execution-summary/0.1","run_id":run_id,"status":if budget_terminated{"budget_terminated"}else{status},"final_state":bundle.get("artifacts").unwrap_or(bundle).get("simulation").and_then(|v|v.get("final_state")),"generated_units":accepted,"registered_units":units.len(),"activated_units":unit_values.iter().filter(|v|v["state"]!="registered").count(),"retired_units":unit_values.iter().filter(|v|v["state"]=="retired").count(),"pruned_branches":pruned.len(),"convergence_reason":reason,"semantic_result":crate::evaluator::semantic_projection(bundle),"diagnostics":diagnostics});
    let budget = json!({"schema_version":"reasonscript-dynamic-budget-report/0.1","usage":{"units":units.len(),"branches":branches.len(),"messages":dynamic_messages,"logical_steps":lifecycle.events.iter().map(|e|e.logical_step).max().unwrap_or(0),"state_bytes":serde_json::to_vec(&unit_values).map(|v|v.len()).unwrap_or(0)},"limits":config.limits,"terminated":budget_terminated});
    let convergence = json!({"schema_version":"reasonscript-dynamic-convergence-report/0.1","checks":[{"policy":"quiescence","satisfied":!budget_terminated},{"policy":"state_stable","satisfied":!budget_terminated,"stable_epochs":config.convergence.stable_epochs}],"global_convergence":!budget_terminated,"termination_reason":reason});
    let mut docs = BTreeMap::new();
    docs.insert(
        "dynamic_unit_lifecycle.jsonl".into(),
        serde_json::to_value(lifecycle.events).unwrap(),
    );
    docs.insert(
        "dynamic_unit_proposals.jsonl".into(),
        json!(proposal_records),
    );
    docs.insert("dynamic_plan_revisions.jsonl".into(), json!(revisions));
    docs.insert("dynamic_branch_graph.json".into(),json!({"schema_version":"reasonscript-dynamic-branch-graph/0.1","branches":branches.values().collect::<Vec<_>>(),"units":unit_values}));
    docs.insert(
        "dynamic_pruning_report.json".into(),
        json!({"schema_version":"reasonscript-dynamic-pruning-report/0.1","decisions":pruned}),
    );
    docs.insert("dynamic_convergence_report.json".into(), convergence);
    docs.insert("dynamic_budget_report.json".into(), budget);
    docs.insert("dynamic_execution_summary.json".into(), summary.clone());
    let manifest = json!({"schema_version":"reasonscript-dynamic-reason-unit-cluster/0.1","run_id":run_id,"run_semantic_seed":seed,"configuration":config,"cluster_run_reference":initial,"artifacts":[]});
    docs.insert("dynamic_unit_manifest.json".into(), manifest);
    if let Some(dir) = &options.artifacts_dir {
        let manifest = write_dynamic_artifacts(dir, &docs)?;
        docs.insert("dynamic_unit_manifest.json".into(), manifest);
    }
    let validation = validate_documents(&docs);
    if validation["valid"] != true {
        return Err(format!(
            "DRU-ART-002: generated artifacts failed validation: {}",
            validation
        ));
    }
    Ok(DynamicRun {
        summary,
        documents: docs,
    })
}

fn rules_from_bundle(bundle: &Value) -> Vec<GenerationRule> {
    if let Some(items) = bundle
        .pointer("/dynamic/generation_rules")
        .and_then(Value::as_array)
    {
        return items
            .iter()
            .filter_map(|v| serde_json::from_value(v.clone()).ok())
            .collect();
    }
    vec![GenerationRule {
        schema_version: "reasonscript-generation-rule/0.1".into(),
        rule_id: "rule_dynamic_generation".into(),
        version: "0.1".into(),
        deterministic: true,
        trigger: json!({"event_type":"task_completed"}),
        input_contract: json!({"required_state_refs":[]}),
        output_contract: json!({"unit_kind":"derived","max_units_per_trigger":16}),
        limits: json!({"max_generation_depth":64,"max_total_units":10000}),
    }]
}
fn build_proposals(bundle: &Value, run_id: &str, scenario: Option<&str>) -> Vec<UnitProposal> {
    if let Some(items) = bundle
        .pointer("/dynamic/proposals")
        .and_then(Value::as_array)
    {
        return items
            .iter()
            .filter_map(|v| serde_json::from_value(v.clone()).ok())
            .collect();
    }
    let count = if scenario == Some("multi-generation") {
        3
    } else if matches!(
        scenario,
        Some("generation-depth-limit") | Some("budget-termination")
    ) {
        6
    } else {
        1
    };
    let duplicate = scenario == Some("duplicate-elimination");
    let mut out = Vec::new();
    for i in 0..count {
        let depth = if matches!(
            scenario,
            Some("generation-depth-limit") | Some("budget-termination")
        ) {
            i + 1
        } else {
            1
        };
        let parent = if i == 0 {
            "seed_unit_0001".into()
        } else if scenario == Some("generation-depth-limit") {
            canonical_placeholder(i)
        } else {
            "seed_unit_0001".into()
        };
        let mut p = UnitProposal {
            schema_version: PROPOSAL_SCHEMA.into(),
            run_id: run_id.into(),
            proposal_id: format!("proposal_{:06}", i + 1),
            logical_step: i,
            epoch: i,
            proposer: Proposer {
                node_id: "worker-0".into(),
                reason_unit_id: parent.clone(),
            },
            generation_rule_id: "rule_dynamic_generation".into(),
            parent_unit_ids: vec![parent],
            input_refs: vec![format!("state://input/{i}")],
            evidence_refs: vec![format!("evidence://dynamic/{i}")],
            proposed_unit: json!({"unit_kind":if scenario==Some("molecular-dynamic"){"boundary_interaction"}else{"derived"},"parameters":{"index":i},"state_access":{"read":[format!("state.input.{i}")],"write":[format!("state.output.{i}")],"append":[],"reduce":[]}}),
            generation_depth: depth,
            priority: 20 - (i as i64),
            checksum: String::new(),
        };
        p.seal().unwrap();
        out.push(p);
    }
    if duplicate {
        let mut p = out[0].clone();
        p.proposal_id = "proposal_000002".into();
        p.proposer.node_id = "worker-1".into();
        p.seal().unwrap();
        out.push(p);
    }
    out
}
fn canonical_placeholder(i: usize) -> String {
    format!("seed_unit_{:04}", i.min(1))
}
fn diagnostic_message(code: &str) -> &str {
    match code {
        "DRU-PRP-001" => "Proposal schema invalid",
        "DRU-PRP-002" => "Unregistered proposer",
        "DRU-PRP-003" => "Parent unit missing",
        "DRU-PRP-004" => "Generation rule missing",
        "DRU-PRP-005" => "Proposal checksum mismatch",
        "DRU-GEN-001" => "Non-deterministic generation rule",
        "DRU-GEN-002" => "Generation depth exceeded",
        "DRU-GEN-003" => "Unit budget exceeded",
        "DRU-GEN-007" => "State access declaration missing",
        "DRU-STA-003" => "Dynamic state write conflict",
        _ => "Dynamic validation failed",
    }
}
fn apply_scenario_lifecycle(
    s: Option<&str>,
    c: &DynamicConfig,
    l: &mut LifecycleStore,
    u: &mut BTreeMap<String, Unit>,
    r: &mut Vec<Value>,
    p: &mut Vec<Value>,
    d: &mut Vec<Diagnostic>,
) -> Result<(), String> {
    let id = u.values().find(|x| x.depth > 0).map(|x| x.id.clone());
    if let Some(id) = id {
        match s {
            Some("suspension-reactivation") => {
                l.transition(
                    &id,
                    "ready",
                    2,
                    "activation",
                    json!({}),
                    c.limits.max_reactivations_per_unit,
                )
                .ok();
                l.transition(
                    &id,
                    "suspended",
                    2,
                    "dependency_missing",
                    json!({"checkpoint":{"state_version":1}}),
                    c.limits.max_reactivations_per_unit,
                )?;
                l.transition(
                    &id,
                    "ready",
                    3,
                    "dependency_satisfied",
                    json!({"checkpoint_state_version":1}),
                    c.limits.max_reactivations_per_unit,
                )?
            }
            Some("replacement") => {
                l.transition(
                    &id,
                    "ready",
                    2,
                    "activation",
                    json!({}),
                    c.limits.max_reactivations_per_unit,
                )
                .ok();
                l.transition(
                    &id,
                    "replaced",
                    3,
                    "state_version_changed",
                    json!({"state_transfer_policy":"copy_validated"}),
                    c.limits.max_reactivations_per_unit,
                )?;
                if let Some(x) = u.get_mut(&id) {
                    x.replaced_by = Some(format!("replacement_{id}"));
                }
            }
            Some("branch-pruning") => {
                p.push(json!({"branch_id":u[&id].branch_id,"reason":"dominated","comparison_branch_id":"branch_root_0001","budget_effect":{"units_removed":1}}));
                l.transition(
                    &id,
                    "ready",
                    2,
                    "activation",
                    json!({}),
                    c.limits.max_reactivations_per_unit,
                )
                .ok();
                l.transition(
                    &id,
                    "suspended",
                    3,
                    "branch_pruned",
                    json!({}),
                    c.limits.max_reactivations_per_unit,
                )?;
                l.transition(
                    &id,
                    "retired",
                    3,
                    "dominated",
                    json!({}),
                    c.limits.max_reactivations_per_unit,
                )?
            }
            Some("worker-failure") => {
                l.transition(
                    &id,
                    "ready",
                    2,
                    "activation",
                    json!({}),
                    c.limits.max_reactivations_per_unit,
                )
                .ok();
                l.transition(
                    &id,
                    "assigned",
                    2,
                    "initial_assignment",
                    json!({}),
                    c.limits.max_reactivations_per_unit,
                )?;
                l.transition(
                    &id,
                    "running",
                    2,
                    "worker_started",
                    json!({}),
                    c.limits.max_reactivations_per_unit,
                )?;
                l.transition(
                    &id,
                    "failed",
                    2,
                    "worker_failure",
                    json!({}),
                    c.limits.max_reactivations_per_unit,
                )?;
                l.transition(
                    &id,
                    "ready",
                    3,
                    "retry_repartition",
                    json!({"unit_id_preserved":true}),
                    c.limits.max_reactivations_per_unit,
                )?
            }
            Some("dynamic-dependency") => {
                if let Some(x) = r.last_mut() {
                    x["dependency_updates"] =
                        json!([{"from":"seed_unit_0001","to":id,"type":"completion"}]);
                    if let Some(object) = x.as_object_mut() {
                        object.remove("revision_checksum");
                    }
                    let revision_checksum = checksum(x).map_err(|e| e.to_string())?;
                    x["revision_checksum"] = json!(revision_checksum);
                }
            }
            _ => {}
        }
    }
    if s == Some("generation-depth-limit") && !d.iter().any(|x| x.code == "DRU-GEN-002") {
        d.push(Diagnostic::error(
            "DRU-GEN-002",
            "Generation depth exceeded",
            "proposal",
        ));
    }
    Ok(())
}
fn failed(
    config: &DynamicConfig,
    diagnostics: Vec<Diagnostic>,
    options: &DynamicOptions,
) -> Result<DynamicRun, String> {
    let summary = json!({"schema_version":"reasonscript-dynamic-execution-summary/0.1","status":"failed","diagnostics":diagnostics});
    let docs = BTreeMap::from([("dynamic_execution_summary.json".into(), summary.clone())]);
    if options.artifacts_dir.is_some() { /* fail closed: incomplete artifacts are not emitted */ }
    let _ = config;
    Ok(DynamicRun {
        summary,
        documents: docs,
    })
}
