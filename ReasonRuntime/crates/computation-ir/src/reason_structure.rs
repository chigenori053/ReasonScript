use sha2::{Digest, Sha256};
use std::borrow::Cow;
use std::io::{self, Write};

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum ExecutableMode {
    #[default]
    Off,
    Count,
    Full,
}

impl ExecutableMode {
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "off" => Some(Self::Off),
            "count" => Some(Self::Count),
            "full" => Some(Self::Full),
            _ => None,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ReasonUnitSource {
    Runtime,
    LegacyReasoningEvent,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ExecutableKind {
    Hypothesis,
    Verification,
    ConstraintDerivation,
    GoalEvaluation,
    TerminationCheck,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TerminalStatus {
    Verified,
    Rejected,
    Completed,
}

#[derive(Clone, Debug)]
pub enum ExecutableHandle {
    Count {
        sequence: u64,
        kind: ExecutableKind,
        operation: Cow<'static, str>,
        subject: serde_json::Value,
        input: serde_json::Value,
    },
    Full(usize),
}

#[derive(Clone)]
struct RollingJsonArrayHash {
    hasher: Sha256,
    items: u64,
    updates: u64,
    bytes: u64,
}

impl Default for RollingJsonArrayHash {
    fn default() -> Self {
        let mut hasher = Sha256::new();
        hasher.update(b"[");
        Self {
            hasher,
            items: 0,
            updates: 1,
            bytes: 1,
        }
    }
}

impl RollingJsonArrayHash {
    fn write(&mut self, bytes: &[u8]) {
        self.hasher.update(bytes);
        self.updates += 1;
        self.bytes += bytes.len() as u64;
    }

    fn begin_item(&mut self) {
        if self.items > 0 {
            self.write(b",");
        }
        self.items += 1;
    }

    fn lifecycle(&mut self, kind: ExecutableKind, sequence: u64, transition: &str, revision: u64) {
        self.begin_item();
        self.write(b"[\"ru:");
        self.write(executable_kind_id(kind).as_bytes());
        self.write(b":");
        write_zero_padded_u64(self, sequence, 8);
        self.write(b"\",\"");
        write_json_string_content(self, transition);
        self.write(b"\",");
        write_u64(self, revision);
        self.write(b"]");
    }

    fn sequence(
        &mut self,
        kind: ExecutableKind,
        operation: &str,
        subject: &serde_json::Value,
        input: &serde_json::Value,
        terminal: TerminalStatus,
    ) {
        self.begin_item();
        self.write(b"[\"");
        write_json_string_content(self, executable_kind(kind));
        self.write(b"|");
        write_json_string_content(self, operation);
        self.write(b"|");
        write_canonical_escaped(self, subject);
        self.write(b"|");
        write_canonical_escaped(self, input);
        self.write(b"\",\"");
        self.write(executable_kind(kind).as_bytes());
        self.write(b"\",\"");
        self.write(terminal_status(terminal).as_bytes());
        self.write(b"\",");
        write_canonical(self, subject);
        self.write(b"]");
    }

    fn finish(&self) -> String {
        let mut hasher = self.hasher.clone();
        hasher.update(b"]");
        format!("sha256:{:x}", hasher.finalize())
    }
}

struct HashWriter<'a>(&'a mut RollingJsonArrayHash);

impl Write for HashWriter<'_> {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.0.write(bytes);
        Ok(bytes.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

struct EscapedHashWriter<'a>(&'a mut RollingJsonArrayHash);

impl Write for EscapedHashWriter<'_> {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        write_json_string_bytes(self.0, bytes);
        Ok(bytes.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

fn write_u64(hash: &mut RollingJsonArrayHash, value: u64) {
    let mut buffer = [0_u8; 20];
    let start = decimal_u64(value, &mut buffer);
    hash.write(&buffer[start..]);
}

fn write_zero_padded_u64(hash: &mut RollingJsonArrayHash, value: u64, width: usize) {
    let mut buffer = [0_u8; 20];
    let start = decimal_u64(value, &mut buffer);
    for _ in 0..width.saturating_sub(buffer.len() - start) {
        hash.write(b"0");
    }
    hash.write(&buffer[start..]);
}

fn decimal_u64(mut value: u64, buffer: &mut [u8; 20]) -> usize {
    let mut cursor = buffer.len();
    loop {
        cursor -= 1;
        buffer[cursor] = b'0' + (value % 10) as u8;
        value /= 10;
        if value == 0 {
            return cursor;
        }
    }
}

fn write_json_string_content(hash: &mut RollingJsonArrayHash, value: &str) {
    write_json_string_bytes(hash, value.as_bytes());
}

fn write_json_string_bytes(hash: &mut RollingJsonArrayHash, bytes: &[u8]) {
    let mut start = 0;
    for (index, byte) in bytes.iter().copied().enumerate() {
        let escape = match byte {
            b'"' => Some(b"\\\"".as_slice()),
            b'\\' => Some(b"\\\\".as_slice()),
            b'\x08' => Some(b"\\b".as_slice()),
            b'\t' => Some(b"\\t".as_slice()),
            b'\n' => Some(b"\\n".as_slice()),
            b'\x0c' => Some(b"\\f".as_slice()),
            b'\r' => Some(b"\\r".as_slice()),
            0x00..=0x1f => None,
            _ => continue,
        };
        if start < index {
            hash.write(&bytes[start..index]);
        }
        if let Some(escape) = escape {
            hash.write(escape);
        } else {
            const HEX: &[u8; 16] = b"0123456789abcdef";
            hash.write(&[
                b'\\',
                b'u',
                b'0',
                b'0',
                HEX[(byte >> 4) as usize],
                HEX[(byte & 15) as usize],
            ]);
        }
        start = index + 1;
    }
    if start < bytes.len() {
        hash.write(&bytes[start..]);
    }
}

fn write_canonical(hash: &mut RollingJsonArrayHash, value: &serde_json::Value) {
    write_canonical_to(&mut HashWriter(hash), value);
}

fn write_canonical_escaped(hash: &mut RollingJsonArrayHash, value: &serde_json::Value) {
    write_canonical_to(&mut EscapedHashWriter(hash), value);
}

fn write_canonical_to<W: Write>(writer: &mut W, value: &serde_json::Value) {
    match value {
        serde_json::Value::Null => writer.write_all(b"null").unwrap(),
        serde_json::Value::Bool(value) => writer
            .write_all(if *value { b"true" } else { b"false" })
            .unwrap(),
        serde_json::Value::Number(value) => serde_json::to_writer(writer, value).unwrap(),
        serde_json::Value::String(value) => serde_json::to_writer(writer, value).unwrap(),
        serde_json::Value::Array(values) => {
            writer.write_all(b"[").unwrap();
            for (index, value) in values.iter().enumerate() {
                if index > 0 {
                    writer.write_all(b",").unwrap();
                }
                write_canonical_to(writer, value);
            }
            writer.write_all(b"]").unwrap();
        }
        serde_json::Value::Object(values) => {
            writer.write_all(b"{").unwrap();
            for (index, (key, value)) in values.iter().enumerate() {
                if index > 0 {
                    writer.write_all(b",").unwrap();
                }
                serde_json::to_writer(&mut *writer, key).unwrap();
                writer.write_all(b":").unwrap();
                write_canonical_to(writer, value);
            }
            writer.write_all(b"}").unwrap();
        }
    }
}

#[derive(Debug)]
struct ExecutableReasonUnit {
    id: String,
    semantic_signature: String,
    kind: ExecutableKind,
    source: ReasonUnitSource,
    subject: serde_json::Value,
    input: serde_json::Value,
    output: serde_json::Value,
    evidence_refs: Vec<String>,
    status: &'static str,
    terminal_status: Option<TerminalStatus>,
    lifecycle_revision: u64,
    lifecycle: Vec<&'static str>,
}

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
    executable_mode: ExecutableMode,
    executable_units: Vec<ExecutableReasonUnit>,
    executable_evidence: Vec<serde_json::Value>,
    executable_relations: Vec<serde_json::Value>,
    executable_sequence: Vec<serde_json::Value>,
    executable_lifecycle: Vec<serde_json::Value>,
    executable_metrics: [u64; 18],
    executable_active: Vec<u64>,
    executable_sequence_hash: RollingJsonArrayHash,
    executable_lifecycle_hash: RollingJsonArrayHash,
}

impl ReasonStructure {
    pub fn new(mode: ReasonUnitMode) -> Self {
        Self {
            mode,
            ..Self::default()
        }
    }

    pub fn set_executable_mode(&mut self, mode: ExecutableMode) {
        self.executable_mode = mode;
    }

    pub fn begin_executable(
        &mut self,
        kind: ExecutableKind,
        source: ReasonUnitSource,
        operation: &str,
        subject: serde_json::Value,
        input: serde_json::Value,
    ) -> Option<ExecutableHandle> {
        if self.executable_mode == ExecutableMode::Off {
            return None;
        }
        let sequence = self.executable_metrics[0] + 1;
        self.executable_metrics[0] += 1; // created
        self.executable_metrics[1] += 1; // activated
        self.executable_metrics[6] += 2; // lifecycle transitions
        self.executable_metrics[8 + executable_kind_index(kind)] += 1;
        match source {
            ReasonUnitSource::Runtime => self.executable_metrics[13] += 1,
            ReasonUnitSource::LegacyReasoningEvent => self.executable_metrics[14] += 1,
        }
        if self.executable_mode == ExecutableMode::Count {
            self.executable_lifecycle_hash
                .lifecycle(kind, sequence, "CREATED", 0);
            self.executable_lifecycle_hash
                .lifecycle(kind, sequence, "ACTIVE", 1);
            self.executable_active.push(sequence);
            return Some(ExecutableHandle::Count {
                sequence,
                kind,
                operation: executable_operation(operation),
                subject,
                input,
            });
        }
        let semantic_signature = format!(
            "{}|{}|{}|{}",
            executable_kind(kind),
            operation,
            canonical(&subject),
            canonical(&input)
        );
        let id = format!("ru:{}:{sequence:08}", executable_kind_id(kind));
        let unit = ExecutableReasonUnit {
            id: id.clone(),
            semantic_signature,
            kind,
            source,
            subject,
            input,
            output: serde_json::Value::Null,
            evidence_refs: Vec::new(),
            status: "ACTIVE",
            terminal_status: None,
            lifecycle_revision: 1,
            lifecycle: vec!["CREATED", "ACTIVE"],
        };
        self.executable_lifecycle
            .push(serde_json::json!([id, "CREATED", 0]));
        self.executable_lifecycle
            .push(serde_json::json!([id, "ACTIVE", 1]));
        self.executable_units.push(unit);
        Some(ExecutableHandle::Full(self.executable_units.len() - 1))
    }

    pub fn finish_executable(
        &mut self,
        handle: Option<ExecutableHandle>,
        terminal: TerminalStatus,
        output: serde_json::Value,
        evidence_kind: Option<&str>,
        evidence_value: serde_json::Value,
    ) -> Result<(), &'static str> {
        let Some(handle) = handle else { return Ok(()) };
        if let ExecutableHandle::Count {
            sequence,
            kind,
            operation,
            subject,
            input,
        } = handle
        {
            let Some(position) = self
                .executable_active
                .iter()
                .rposition(|active| *active == sequence)
            else {
                self.executable_metrics[7] += 1;
                return Err("RU-LIFECYCLE-001");
            };
            self.executable_active.swap_remove(position);
            let mut revision = 2;
            self.executable_lifecycle_hash.lifecycle(
                kind,
                sequence,
                terminal_status(terminal),
                revision,
            );
            self.executable_metrics[6] += 1;
            if terminal != TerminalStatus::Completed {
                revision += 1;
                self.executable_lifecycle_hash
                    .lifecycle(kind, sequence, "COMPLETED", revision);
                self.executable_metrics[6] += 1;
            }
            self.executable_sequence_hash
                .sequence(kind, &operation, &subject, &input, terminal);
            self.finish_counters(terminal, evidence_kind.is_some());
            return Ok(());
        }
        let ExecutableHandle::Full(index) = handle else {
            unreachable!()
        };
        let Some(unit) = self.executable_units.get_mut(index) else {
            self.executable_metrics[7] += 1;
            return Err("RU-LIFECYCLE-001");
        };
        if unit.status != "ACTIVE" {
            self.executable_metrics[7] += 1;
            return Err("RU-LIFECYCLE-001");
        }
        unit.output = output;
        unit.terminal_status = Some(terminal);
        unit.status = "COMPLETED";
        unit.lifecycle_revision += 1;
        unit.lifecycle.push(terminal_status(terminal));
        self.executable_metrics[6] += 1;
        self.executable_lifecycle.push(serde_json::json!([
            unit.id,
            terminal_status(terminal),
            unit.lifecycle_revision
        ]));
        if terminal != TerminalStatus::Completed {
            unit.lifecycle_revision += 1;
            unit.lifecycle.push("COMPLETED");
            self.executable_metrics[6] += 1;
            self.executable_lifecycle.push(serde_json::json!([
                unit.id,
                "COMPLETED",
                unit.lifecycle_revision
            ]));
        }
        if let Some(kind) = evidence_kind {
            let evidence_id = format!("evidence:ru:{:08}", self.executable_evidence.len() + 1);
            unit.evidence_refs.push(evidence_id.clone());
            self.executable_evidence.push(serde_json::json!({
                "id": evidence_id,
                "kind": kind,
                "subject": unit.subject,
                "value": evidence_value,
                "source_ru": unit.id,
            }));
            self.executable_relations.push(serde_json::json!({
                "id": format!("relation:ru:{:08}", self.executable_relations.len() + 1),
                "kind": "PRODUCES",
                "source_ref": unit.id,
                "target_ref": evidence_id,
            }));
        }
        self.executable_sequence.push(serde_json::json!([
            unit.semantic_signature,
            executable_kind(unit.kind),
            terminal_status(terminal),
            unit.subject
        ]));
        self.finish_counters(terminal, evidence_kind.is_some());
        Ok(())
    }

    fn finish_counters(&mut self, terminal: TerminalStatus, evidence: bool) {
        self.executable_metrics[2] += 1; // executed
        self.executable_metrics[5] += 1; // completed
        match terminal {
            TerminalStatus::Verified => self.executable_metrics[3] += 1,
            TerminalStatus::Rejected => self.executable_metrics[4] += 1,
            TerminalStatus::Completed => {}
        }
        if evidence {
            self.executable_metrics[15] += 1; // evidence created
            self.executable_metrics[16] += 1; // evidence attached
            self.executable_metrics[17] += 1; // relation created
        }
    }

    pub fn record_legacy_executable(
        &mut self,
        event_type: &str,
        subject: serde_json::Value,
        evidence: serde_json::Value,
    ) -> Result<(), &'static str> {
        let (kind, terminal, evidence_kind) = executable_event(event_type);
        let handle = self.begin_executable(
            kind,
            ReasonUnitSource::LegacyReasoningEvent,
            event_type,
            subject,
            serde_json::Value::Null,
        );
        self.finish_executable(handle, terminal, evidence.clone(), evidence_kind, evidence)
    }

    pub fn executable_trace(&self) -> serde_json::Value {
        let full = self.executable_mode == ExecutableMode::Full;
        let sequence_hash = if full {
            hash(&self.executable_sequence)
        } else {
            self.executable_sequence_hash.finish()
        };
        let lifecycle_hash = if full {
            hash(&self.executable_lifecycle)
        } else {
            self.executable_lifecycle_hash.finish()
        };
        serde_json::json!({
            "mode": match self.executable_mode { ExecutableMode::Off => "off", ExecutableMode::Count => "count", ExecutableMode::Full => "full" },
            "reason_units": if full { self.executable_units.iter().map(executable_json).collect::<Vec<_>>() } else { Vec::new() },
            "evidence": if full { self.executable_evidence.clone() } else { Vec::new() },
            "relations": if full { self.executable_relations.clone() } else { Vec::new() },
            "ru_sequence_hash": sequence_hash,
            "ru_lifecycle_hash": lifecycle_hash,
        })
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
        // Deterministic managed-allocation proxy: VM value slots plus retained
        // ReasonStructure payload. This is intentionally allocator-independent
        // so Model G/H runs remain comparable across platforms and allocators.
        let executable_bytes = serialized_len(
            &self
                .executable_units
                .iter()
                .map(executable_json)
                .collect::<Vec<_>>(),
        ) + serialized_len(&self.executable_evidence)
            + serialized_len(&self.executable_relations)
            + serialized_len(&self.executable_sequence)
            + serialized_len(&self.executable_lifecycle);
        let managed_base_bytes = vm_instruction_count.saturating_mul(16);
        let managed_allocation_count = vm_instruction_count
            + self.executable_units.len() as u64
            + self.executable_evidence.len() as u64
            + self.executable_relations.len() as u64
            + self.executable_sequence.len() as u64
            + self.executable_lifecycle.len() as u64;
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
        let mut metrics = serde_json::json!({
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
            "allocation_count": managed_allocation_count,
            "allocated_bytes": managed_base_bytes + executable_bytes as u64,
            "peak_live_bytes": managed_base_bytes + executable_bytes as u64,
            "allocation_metric_kind": "deterministic_managed_proxy",
        });
        if self.executable_mode != ExecutableMode::Off {
            let sequence_hash = if self.executable_mode == ExecutableMode::Full {
                hash(&self.executable_sequence)
            } else {
                self.executable_sequence_hash.finish()
            };
            let lifecycle_hash = if self.executable_mode == ExecutableMode::Full {
                hash(&self.executable_lifecycle)
            } else {
                self.executable_lifecycle_hash.finish()
            };
            let extra = serde_json::json!({
                "ru_created_count": self.executable_metrics[0],
                "ru_activated_count": self.executable_metrics[1],
                "ru_executed_count": self.executable_metrics[2],
                "ru_verified_count": self.executable_metrics[3],
                "ru_rejected_count": self.executable_metrics[4],
                "ru_completed_count": self.executable_metrics[5],
                "ru_lifecycle_transition_count": self.executable_metrics[6],
                "ru_invalid_transition_count": self.executable_metrics[7],
                "ru_hypothesis_count": self.executable_metrics[8],
                "ru_verification_count": self.executable_metrics[9],
                "ru_constraint_derivation_count": self.executable_metrics[10],
                "ru_goal_evaluation_count": self.executable_metrics[11],
                "ru_termination_check_count": self.executable_metrics[12],
                "ru_evidence_created_count": self.executable_metrics[15],
                "ru_evidence_attached_count": self.executable_metrics[16],
                "ru_relation_created_count": self.executable_metrics[17],
                "ru_native_count": self.executable_metrics[13],
                "ru_legacy_adapter_count": self.executable_metrics[14],
                "ru_active_count": self.executable_active.len(),
                "ru_hash_update_count": self.executable_sequence_hash.updates + self.executable_lifecycle_hash.updates,
                "ru_hash_bytes": self.executable_sequence_hash.bytes + self.executable_lifecycle_hash.bytes + 2,
                "ru_canonicalization_count": self.executable_metrics[2].saturating_mul(3),
                "ru_serialized_bytes": if self.executable_mode == ExecutableMode::Full { serialized_len(&self.executable_units.iter().map(executable_json).collect::<Vec<_>>()) } else { 0 },
                "ruvmr": if self.executable_metrics[2] == 0 { serde_json::Value::Null } else { serde_json::json!(vm_instruction_count as f64 / self.executable_metrics[2] as f64) },
                "ru_sequence_hash": sequence_hash,
                "ru_lifecycle_hash": lifecycle_hash,
            });
            metrics
                .as_object_mut()
                .unwrap()
                .extend(extra.as_object().unwrap().clone());
        }
        metrics
    }
}

fn executable_kind(kind: ExecutableKind) -> &'static str {
    match kind {
        ExecutableKind::Hypothesis => "HYPOTHESIS",
        ExecutableKind::Verification => "VERIFICATION",
        ExecutableKind::ConstraintDerivation => "CONSTRAINT_DERIVATION",
        ExecutableKind::GoalEvaluation => "GOAL_EVALUATION",
        ExecutableKind::TerminationCheck => "TERMINATION_CHECK",
    }
}

fn executable_kind_id(kind: ExecutableKind) -> &'static str {
    match kind {
        ExecutableKind::Hypothesis => "hypothesis",
        ExecutableKind::Verification => "verification",
        ExecutableKind::ConstraintDerivation => "constraint-derivation",
        ExecutableKind::GoalEvaluation => "goal-evaluation",
        ExecutableKind::TerminationCheck => "termination-check",
    }
}

fn executable_kind_index(kind: ExecutableKind) -> usize {
    match kind {
        ExecutableKind::Hypothesis => 0,
        ExecutableKind::Verification => 1,
        ExecutableKind::ConstraintDerivation => 2,
        ExecutableKind::GoalEvaluation => 3,
        ExecutableKind::TerminationCheck => 4,
    }
}

fn executable_operation(operation: &str) -> Cow<'static, str> {
    match operation {
        "CANDIDATE_ADOPTED" => Cow::Borrowed("CANDIDATE_ADOPTED"),
        "CANDIDATE_PREDICATE" => Cow::Borrowed("CANDIDATE_PREDICATE"),
        "HYPOTHESIS_CREATED" => Cow::Borrowed("HYPOTHESIS_CREATED"),
        "HYPOTHESIS_VERIFIED" => Cow::Borrowed("HYPOTHESIS_VERIFIED"),
        "HYPOTHESIS_REJECTED" => Cow::Borrowed("HYPOTHESIS_REJECTED"),
        "CANDIDATE_PRUNED" => Cow::Borrowed("CANDIDATE_PRUNED"),
        "STATE_TRANSITION" => Cow::Borrowed("STATE_TRANSITION"),
        "GOAL_UPDATED" => Cow::Borrowed("GOAL_UPDATED"),
        "TERMINATION_INFERRED" => Cow::Borrowed("TERMINATION_INFERRED"),
        "EVIDENCE_ADDED" => Cow::Borrowed("EVIDENCE_ADDED"),
        other => Cow::Owned(other.to_owned()),
    }
}

fn terminal_status(status: TerminalStatus) -> &'static str {
    match status {
        TerminalStatus::Verified => "VERIFIED",
        TerminalStatus::Rejected => "REJECTED",
        TerminalStatus::Completed => "COMPLETED",
    }
}

fn executable_source(source: ReasonUnitSource) -> &'static str {
    match source {
        ReasonUnitSource::Runtime => "runtime",
        ReasonUnitSource::LegacyReasoningEvent => "legacy_reasoning_event",
    }
}

fn executable_event(event_type: &str) -> (ExecutableKind, TerminalStatus, Option<&'static str>) {
    match event_type {
        "HYPOTHESIS_VERIFIED" => (
            ExecutableKind::Verification,
            TerminalStatus::Verified,
            Some("FACTOR_CONFIRMED"),
        ),
        "HYPOTHESIS_REJECTED" | "CANDIDATE_PRUNED" => (
            ExecutableKind::Verification,
            TerminalStatus::Rejected,
            Some("NOT_DIVISIBLE"),
        ),
        "EVIDENCE_ADDED" => (
            ExecutableKind::ConstraintDerivation,
            TerminalStatus::Completed,
            Some("CONSTRAINT_DERIVED"),
        ),
        "GOAL_UPDATED" => (
            ExecutableKind::GoalEvaluation,
            TerminalStatus::Verified,
            Some("GOAL_CONFIRMED"),
        ),
        "TERMINATION_INFERRED" => (
            ExecutableKind::TerminationCheck,
            TerminalStatus::Verified,
            Some("GOAL_CONFIRMED"),
        ),
        _ => (ExecutableKind::Hypothesis, TerminalStatus::Completed, None),
    }
}

fn executable_json(unit: &ExecutableReasonUnit) -> serde_json::Value {
    serde_json::json!({
        "id": unit.id,
        "semantic_signature": unit.semantic_signature,
        "kind": executable_kind(unit.kind),
        "source": executable_source(unit.source),
        "subject": unit.subject,
        "input": unit.input,
        "output": unit.output,
        "evidence_refs": unit.evidence_refs,
        "status": unit.status,
        "terminal_status": unit.terminal_status.map(terminal_status),
        "lifecycle_revision": unit.lifecycle_revision,
        "lifecycle": unit.lifecycle,
    })
}

fn canonical(value: &serde_json::Value) -> String {
    serde_json::to_string(value).expect("JSON values are serializable")
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

    #[test]
    fn executable_lifecycle_is_validated_and_deterministic() {
        let run = || {
            let mut structure = ReasonStructure::default();
            structure.set_executable_mode(ExecutableMode::Full);
            let handle = structure.begin_executable(
                ExecutableKind::Verification,
                ReasonUnitSource::Runtime,
                "DIVISIBLE",
                serde_json::json!(11),
                serde_json::json!({"remaining": 77}),
            );
            structure
                .finish_executable(
                    handle.clone(),
                    TerminalStatus::Verified,
                    serde_json::json!({"divisible": true}),
                    Some("FACTOR_CONFIRMED"),
                    serde_json::json!(11),
                )
                .unwrap();
            assert!(structure
                .finish_executable(
                    handle,
                    TerminalStatus::Completed,
                    serde_json::Value::Null,
                    None,
                    serde_json::Value::Null
                )
                .is_err());
            structure
        };
        let first = run();
        let second = run();
        assert_eq!(
            first.executable_trace()["ru_sequence_hash"],
            second.executable_trace()["ru_sequence_hash"]
        );
        assert_eq!(
            first.executable_trace()["ru_lifecycle_hash"],
            second.executable_trace()["ru_lifecycle_hash"]
        );
        assert_eq!(
            first.executable_trace()["reason_units"][0]["lifecycle"],
            serde_json::json!(["CREATED", "ACTIVE", "VERIFIED", "COMPLETED"])
        );
        assert_eq!(first.executable_trace()["relations"][0]["kind"], "PRODUCES");
        assert_eq!(first.metrics(4)["ru_invalid_transition_count"], 1);
    }

    #[test]
    fn executable_count_mode_omits_payloads() {
        let mut structure = ReasonStructure::default();
        structure.set_executable_mode(ExecutableMode::Count);
        structure
            .record_legacy_executable(
                "HYPOTHESIS_CREATED",
                serde_json::json!(5),
                serde_json::Value::Null,
            )
            .unwrap();
        assert_eq!(
            structure.executable_trace()["reason_units"],
            serde_json::json!([])
        );
        assert_eq!(structure.metrics(1)["ru_legacy_adapter_count"], 1);
    }

    #[test]
    fn executable_count_fast_path_matches_full_hashes_and_metrics() {
        let run = |mode| {
            let mut structure = ReasonStructure::default();
            structure.set_executable_mode(mode);
            for (event, subject, evidence) in [
                (
                    "HYPOTHESIS_VERIFIED",
                    serde_json::json!(11),
                    serde_json::json!(true),
                ),
                (
                    "HYPOTHESIS_REJECTED",
                    serde_json::json!(13),
                    serde_json::json!(false),
                ),
                (
                    "TERMINATION_INFERRED",
                    serde_json::json!(77),
                    serde_json::json!(true),
                ),
            ] {
                structure
                    .record_legacy_executable(event, subject, evidence)
                    .unwrap();
            }
            structure
        };
        let count = run(ExecutableMode::Count);
        let full = run(ExecutableMode::Full);
        let count_trace = count.executable_trace();
        let full_trace = full.executable_trace();
        assert_eq!(
            count_trace["ru_sequence_hash"],
            full_trace["ru_sequence_hash"]
        );
        assert_eq!(
            count_trace["ru_lifecycle_hash"],
            full_trace["ru_lifecycle_hash"]
        );
        assert_eq!(count_trace["reason_units"], serde_json::json!([]));
        assert!(count.executable_units.is_empty());
        assert!(count.executable_evidence.is_empty());
        assert!(count.executable_relations.is_empty());
        assert!(count.executable_sequence.is_empty());
        assert!(count.executable_lifecycle.is_empty());
        let count_metrics = count.metrics(10);
        let full_metrics = full.metrics(10);
        for name in [
            "ru_created_count",
            "ru_activated_count",
            "ru_executed_count",
            "ru_verified_count",
            "ru_rejected_count",
            "ru_completed_count",
            "ru_lifecycle_transition_count",
            "ru_invalid_transition_count",
            "ru_hypothesis_count",
            "ru_verification_count",
            "ru_constraint_derivation_count",
            "ru_goal_evaluation_count",
            "ru_termination_check_count",
            "ru_native_count",
            "ru_legacy_adapter_count",
            "ru_evidence_created_count",
            "ru_evidence_attached_count",
        ] {
            assert_eq!(count_metrics[name], full_metrics[name], "{name}");
        }
        assert_eq!(count_metrics["ru_active_count"], 0);
    }

    #[test]
    fn executable_streaming_hash_matches_full_for_json_edge_values() {
        let subjects = [
            serde_json::Value::Null,
            serde_json::json!(true),
            serde_json::json!(i64::MIN),
            serde_json::json!(u64::MAX),
            serde_json::json!(-12.5),
            serde_json::json!("quote \" slash \\ line\n雪"),
            serde_json::json!([]),
            serde_json::json!({}),
            serde_json::json!([null, false, 7, "é"]),
            serde_json::json!({"nested": {"items": [1, 2]}, "empty": []}),
        ];
        for subject in subjects {
            let run = |mode| {
                let mut structure = ReasonStructure::default();
                structure.set_executable_mode(mode);
                let handle = structure.begin_executable(
                    ExecutableKind::Verification,
                    ReasonUnitSource::Runtime,
                    "CANDIDATE_PREDICATE",
                    subject.clone(),
                    serde_json::json!({"index": 0, "label": "a\tb"}),
                );
                structure
                    .finish_executable(
                        handle,
                        TerminalStatus::Verified,
                        serde_json::Value::Null,
                        Some("FACTOR_CONFIRMED"),
                        serde_json::Value::Null,
                    )
                    .unwrap();
                structure.executable_trace()
            };
            let count = run(ExecutableMode::Count);
            let full = run(ExecutableMode::Full);
            assert_eq!(count["ru_sequence_hash"], full["ru_sequence_hash"]);
            assert_eq!(count["ru_lifecycle_hash"], full["ru_lifecycle_hash"]);
        }
    }

    #[test]
    fn executable_hash_v1_golden_is_stable() {
        let mut structure = ReasonStructure::default();
        structure.set_executable_mode(ExecutableMode::Count);
        structure
            .record_legacy_executable(
                "HYPOTHESIS_VERIFIED",
                serde_json::json!(11),
                serde_json::json!(true),
            )
            .unwrap();
        let trace = structure.executable_trace();
        assert_eq!(
            trace["ru_sequence_hash"],
            "sha256:eb90b531efe93b19c86007c1a4d2a78be05b2fb202450f076ba0b96c4686ee95"
        );
        assert_eq!(
            trace["ru_lifecycle_hash"],
            "sha256:8fc292f6f4d053b76e6777bd473c9e24db4b883ab8a2d8e480737ca2e6275b55"
        );
    }
}
