use std::collections::{HashMap, HashSet};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{
    canonical::checksum,
    diagnostics::{sort, Diagnostic},
};

pub const MESSAGE_SCHEMA: &str = "reasonscript-cluster-message/0.1";

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct ClusterMessage {
    pub schema_version: String,
    pub message_id: String,
    pub run_id: String,
    pub logical_step: usize,
    pub sequence: usize,
    pub sender: String,
    pub receiver: String,
    pub message_type: String,
    pub payload: Value,
    pub checksum: String,
}

#[derive(Serialize)]
struct MessageBody<'a> {
    schema_version: &'a str,
    message_id: &'a str,
    run_id: &'a str,
    logical_step: usize,
    sequence: usize,
    sender: &'a str,
    receiver: &'a str,
    message_type: &'a str,
    payload: &'a Value,
}

impl ClusterMessage {
    pub fn new(
        message_id: String,
        run_id: &str,
        logical_step: usize,
        sequence: usize,
        sender: &str,
        receiver: &str,
        message_type: &str,
        payload: Value,
    ) -> Result<Self, serde_json::Error> {
        let body = MessageBody {
            schema_version: MESSAGE_SCHEMA,
            message_id: &message_id,
            run_id,
            logical_step,
            sequence,
            sender,
            receiver,
            message_type,
            payload: &payload,
        };
        let checksum = checksum(&body)?;
        Ok(Self {
            schema_version: MESSAGE_SCHEMA.into(),
            message_id,
            run_id: run_id.into(),
            logical_step,
            sequence,
            sender: sender.into(),
            receiver: receiver.into(),
            message_type: message_type.into(),
            payload,
            checksum,
        })
    }

    fn expected_checksum(&self) -> Result<String, serde_json::Error> {
        checksum(&MessageBody {
            schema_version: &self.schema_version,
            message_id: &self.message_id,
            run_id: &self.run_id,
            logical_step: self.logical_step,
            sequence: self.sequence,
            sender: &self.sender,
            receiver: &self.receiver,
            message_type: &self.message_type,
            payload: &self.payload,
        })
    }
}

pub fn validate_stream(
    messages: &[ClusterMessage],
    nodes: &HashSet<String>,
    max_bytes: usize,
) -> Vec<Diagnostic> {
    let allowed: HashSet<_> = [
        "worker_register",
        "worker_ready",
        "task_assign",
        "task_start",
        "task_result",
        "task_failure",
        "state_request",
        "state_response",
        "barrier_wait",
        "barrier_release",
        "heartbeat",
        "cancel",
        "shutdown",
        "diagnostic",
    ]
    .into_iter()
    .collect();
    let mut diagnostics = Vec::new();
    let mut ids = HashSet::new();
    let mut sequences: HashMap<(&str, &str, &str), usize> = HashMap::new();
    for message in messages {
        if message.expected_checksum().ok().as_ref() != Some(&message.checksum) {
            diagnostics.push(Diagnostic::error(
                "CRR-MSG-001",
                "Message checksum mismatch",
                &message.message_id,
            ));
        }
        if !allowed.contains(message.message_type.as_str()) {
            diagnostics.push(Diagnostic::error(
                "CRR-MSG-003",
                "Unknown message type",
                &message.message_id,
            ));
        }
        if !nodes.contains(&message.sender) {
            diagnostics.push(Diagnostic::error(
                "CRR-MSG-004",
                "Unregistered sender",
                &message.sender,
            ));
        }
        if !nodes.contains(&message.receiver) {
            diagnostics.push(Diagnostic::error(
                "CRR-MSG-005",
                "Invalid receiver",
                &message.receiver,
            ));
        }
        if !ids.insert(&message.message_id) {
            diagnostics.push(Diagnostic::error(
                "CRR-MSG-006",
                "Duplicate message",
                &message.message_id,
            ));
        }
        let route = (
            message.run_id.as_str(),
            message.sender.as_str(),
            message.receiver.as_str(),
        );
        if message.sequence <= *sequences.get(&route).unwrap_or(&0) {
            diagnostics.push(Diagnostic::error(
                "CRR-MSG-002",
                "Message sequence violation",
                &message.message_id,
            ));
        }
        sequences.insert(route, message.sequence);
        if serde_json::to_vec(message).map_or(true, |v| v.len() > max_bytes) {
            diagnostics.push(Diagnostic::error(
                "CRR-RUN-002",
                "Message exceeds max_message_bytes",
                &message.message_id,
            ));
        }
    }
    sort(&mut diagnostics);
    diagnostics
}
