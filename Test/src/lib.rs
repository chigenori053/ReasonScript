pub mod semantic_space;
pub mod discovery_engine;
pub mod math_reason;

use std::fmt;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

static NEXT_ID: AtomicU64 = AtomicU64::new(1);

#[derive(Clone, Debug, Eq, PartialEq, Hash)]
pub struct UnitId(String);

impl UnitId {
    fn new() -> Self {
        let n = NEXT_ID.fetch_add(1, Ordering::SeqCst);
        Self(format!("00000000-0000-0000-0000-{n:012x}"))
    }
}

impl fmt::Display for UnitId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.0.fmt(f)
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum UnitKind {
    Token,
    Number,
    Symbol,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum UnitState {
    Created,
    Active,
    Derived,
    Converged,
    Failed,
    RolledBack,
    Invalidated,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Payload {
    Token(String),
    Number(i64),
    Symbol(String),
}

impl Payload {
    fn kind(&self) -> UnitKind {
        match self {
            Payload::Token(_) => UnitKind::Token,
            Payload::Number(_) => UnitKind::Number,
            Payload::Symbol(_) => UnitKind::Symbol,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum OperationKind {
    Create,
    Transform,
    Derive,
    Rollback,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct TraceInfo {
    pub parent_ids: Vec<UnitId>,
    pub operation: OperationKind,
    pub timestamp: u128,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ReasonUnit {
    pub id: UnitId,
    pub kind: UnitKind,
    pub state: UnitState,
    pub payload: Payload,
    pub links: Vec<UnitId>,
    pub trace: TraceInfo,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum RuntimeError {
    InvalidTransition { from: UnitState, to: UnitState },
    DeserializeError(String),
    ReplayMismatch(String),
    UnsupportedDeriveOperator(String),
    UnsupportedTransformRule(String),
    InvalidPayload(String),
}

pub type RuntimeResult<T> = Result<T, RuntimeError>;

pub struct Runtime;

impl Runtime {
    pub fn create_unit(payload: Payload) -> ReasonUnit {
        ReasonUnit {
            id: UnitId::new(),
            kind: payload.kind(),
            state: UnitState::Created,
            payload,
            links: Vec::new(),
            trace: TraceInfo {
                parent_ids: Vec::new(),
                operation: OperationKind::Create,
                timestamp: timestamp(),
            },
        }
    }

    pub fn transition(unit: &mut ReasonUnit, to: UnitState) -> RuntimeResult<()> {
        if allowed_transition(&unit.state, &to) {
            unit.state = to;
            Ok(())
        } else {
            Err(RuntimeError::InvalidTransition {
                from: unit.state.clone(),
                to,
            })
        }
    }

    pub fn transform_unit(unit: &ReasonUnit, rule: TransformRule) -> RuntimeResult<ReasonUnit> {
        let payload = match (&unit.payload, rule) {
            (Payload::Token(value), TransformRule::Synonym) if value == "apple" => {
                Payload::Token("fruit".to_string())
            }
            (Payload::Token(value), TransformRule::Synonym) => Payload::Token(value.clone()),
            (_, TransformRule::Synonym) => {
                return Err(RuntimeError::InvalidPayload(
                    "synonym transform requires token payload".to_string(),
                ));
            }
        };

        Ok(ReasonUnit {
            id: UnitId::new(),
            kind: payload.kind(),
            state: UnitState::Derived,
            payload,
            links: vec![unit.id.clone()],
            trace: TraceInfo {
                parent_ids: vec![unit.id.clone()],
                operation: OperationKind::Transform,
                timestamp: timestamp(),
            },
        })
    }

    pub fn derive_unit(
        inputs: &[ReasonUnit],
        operator: DeriveOperator,
    ) -> RuntimeResult<ReasonUnit> {
        match operator {
            DeriveOperator::Add => derive_add(inputs),
        }
    }

    pub fn rollback_unit(unit: &ReasonUnit) -> ReasonUnit {
        let mut rolled_back = unit.clone();
        rolled_back.state = UnitState::RolledBack;
        rolled_back.trace = TraceInfo {
            parent_ids: unit.trace.parent_ids.clone(),
            operation: OperationKind::Rollback,
            timestamp: timestamp(),
        };
        rolled_back
    }

    pub fn serialize_unit(unit: &ReasonUnit) -> Vec<u8> {
        let parent_ids = unit
            .trace
            .parent_ids
            .iter()
            .map(|id| escape(&id.0))
            .collect::<Vec<_>>()
            .join(",");
        let links = unit
            .links
            .iter()
            .map(|id| escape(&id.0))
            .collect::<Vec<_>>()
            .join(",");

        format!(
            "v1|{}|{}|{}|{}|{}|{}|{}|{}",
            escape(&unit.id.0),
            unit_kind_name(&unit.kind),
            unit_state_name(&unit.state),
            payload_record(&unit.payload),
            links,
            operation_name(&unit.trace.operation),
            unit.trace.timestamp,
            parent_ids
        )
        .into_bytes()
    }

    pub fn deserialize_unit(bytes: &[u8]) -> RuntimeResult<ReasonUnit> {
        let text = std::str::from_utf8(bytes)
            .map_err(|err| RuntimeError::DeserializeError(err.to_string()))?;
        let fields = split_escaped(text, '|');
        if fields.len() != 9 || fields[0] != "v1" {
            return Err(RuntimeError::DeserializeError(
                "invalid reasonunit serialization format".to_string(),
            ));
        }

        let id = UnitId(unescape(&fields[1])?);
        let kind = parse_unit_kind(&fields[2])?;
        let state = parse_unit_state(&fields[3])?;
        let payload = parse_payload(&fields[4])?;
        let links = parse_id_list(&fields[5])?;
        let operation = parse_operation(&fields[6])?;
        let timestamp = fields[7]
            .parse::<u128>()
            .map_err(|err| RuntimeError::DeserializeError(err.to_string()))?;
        let parent_ids = parse_id_list(&fields[8])?;

        if payload.kind() != kind {
            return Err(RuntimeError::DeserializeError(
                "payload kind does not match unit kind".to_string(),
            ));
        }

        Ok(ReasonUnit {
            id,
            kind,
            state,
            payload,
            links,
            trace: TraceInfo {
                parent_ids,
                operation,
                timestamp,
            },
        })
    }

    pub fn replay(trace: &ReplayTrace) -> RuntimeResult<ReasonUnit> {
        let replayed = Runtime::derive_unit(&trace.inputs, trace.operator)?;
        if replayed.payload != trace.expected_payload {
            return Err(RuntimeError::ReplayMismatch(
                "replayed payload does not match expected result".to_string(),
            ));
        }

        Ok(ReasonUnit {
            id: trace.expected_id.clone(),
            kind: trace.expected_payload.kind(),
            state: trace.expected_state.clone(),
            payload: trace.expected_payload.clone(),
            links: trace.expected_parent_ids.clone(),
            trace: TraceInfo {
                parent_ids: trace.expected_parent_ids.clone(),
                operation: OperationKind::Derive,
                timestamp: trace.expected_timestamp,
            },
        })
    }

    pub fn rollback_cascade(units: &[ReasonUnit], target_id: &UnitId) -> Vec<ReasonUnit> {
        let mut updated = units.to_vec();
        let mut invalidated_ids = vec![target_id.clone()];

        for unit in &mut updated {
            if &unit.id == target_id {
                *unit = Runtime::rollback_unit(unit);
                continue;
            }

            if unit
                .trace
                .parent_ids
                .iter()
                .any(|parent_id| invalidated_ids.contains(parent_id))
            {
                unit.state = UnitState::Invalidated;
                invalidated_ids.push(unit.id.clone());
            }
        }

        updated
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ReplayTrace {
    pub inputs: Vec<ReasonUnit>,
    pub operator: DeriveOperator,
    pub expected_id: UnitId,
    pub expected_state: UnitState,
    pub expected_payload: Payload,
    pub expected_parent_ids: Vec<UnitId>,
    pub expected_timestamp: u128,
}

impl ReplayTrace {
    pub fn from_derived(
        inputs: Vec<ReasonUnit>,
        operator: DeriveOperator,
        unit: &ReasonUnit,
    ) -> Self {
        Self {
            inputs,
            operator,
            expected_id: unit.id.clone(),
            expected_state: unit.state.clone(),
            expected_payload: unit.payload.clone(),
            expected_parent_ids: unit.trace.parent_ids.clone(),
            expected_timestamp: unit.trace.timestamp,
        }
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum TransformRule {
    Synonym,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DeriveOperator {
    Add,
}

fn derive_add(inputs: &[ReasonUnit]) -> RuntimeResult<ReasonUnit> {
    let mut sum = 0;
    let mut parent_ids = Vec::new();

    for input in inputs {
        match input.payload {
            Payload::Number(value) => sum += value,
            _ => {
                return Err(RuntimeError::InvalidPayload(
                    "add derive requires number payloads".to_string(),
                ));
            }
        }
        parent_ids.push(input.id.clone());
    }

    let payload = Payload::Number(sum);
    Ok(ReasonUnit {
        id: UnitId::new(),
        kind: UnitKind::Number,
        state: UnitState::Derived,
        payload,
        links: parent_ids.clone(),
        trace: TraceInfo {
            parent_ids,
            operation: OperationKind::Derive,
            timestamp: timestamp(),
        },
    })
}

fn allowed_transition(from: &UnitState, to: &UnitState) -> bool {
    matches!(
        (from, to),
        (UnitState::Created, UnitState::Active)
            | (UnitState::Active, UnitState::Derived)
            | (UnitState::Derived, UnitState::Converged)
            | (UnitState::Derived, UnitState::Failed)
            | (UnitState::Failed, UnitState::RolledBack)
            | (UnitState::RolledBack, UnitState::Active)
            | (UnitState::RolledBack, UnitState::Invalidated)
    )
}

fn timestamp() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock must be after unix epoch")
        .as_millis()
}

fn unit_kind_name(kind: &UnitKind) -> &'static str {
    match kind {
        UnitKind::Token => "Token",
        UnitKind::Number => "Number",
        UnitKind::Symbol => "Symbol",
    }
}

fn parse_unit_kind(value: &str) -> RuntimeResult<UnitKind> {
    match value {
        "Token" => Ok(UnitKind::Token),
        "Number" => Ok(UnitKind::Number),
        "Symbol" => Ok(UnitKind::Symbol),
        _ => Err(RuntimeError::DeserializeError(format!(
            "unknown unit kind: {value}"
        ))),
    }
}

fn unit_state_name(state: &UnitState) -> &'static str {
    match state {
        UnitState::Created => "Created",
        UnitState::Active => "Active",
        UnitState::Derived => "Derived",
        UnitState::Converged => "Converged",
        UnitState::Failed => "Failed",
        UnitState::RolledBack => "RolledBack",
        UnitState::Invalidated => "Invalidated",
    }
}

fn parse_unit_state(value: &str) -> RuntimeResult<UnitState> {
    match value {
        "Created" => Ok(UnitState::Created),
        "Active" => Ok(UnitState::Active),
        "Derived" => Ok(UnitState::Derived),
        "Converged" => Ok(UnitState::Converged),
        "Failed" => Ok(UnitState::Failed),
        "RolledBack" => Ok(UnitState::RolledBack),
        "Invalidated" => Ok(UnitState::Invalidated),
        _ => Err(RuntimeError::DeserializeError(format!(
            "unknown unit state: {value}"
        ))),
    }
}

fn operation_name(operation: &OperationKind) -> &'static str {
    match operation {
        OperationKind::Create => "Create",
        OperationKind::Transform => "Transform",
        OperationKind::Derive => "Derive",
        OperationKind::Rollback => "Rollback",
    }
}

fn parse_operation(value: &str) -> RuntimeResult<OperationKind> {
    match value {
        "Create" => Ok(OperationKind::Create),
        "Transform" => Ok(OperationKind::Transform),
        "Derive" => Ok(OperationKind::Derive),
        "Rollback" => Ok(OperationKind::Rollback),
        _ => Err(RuntimeError::DeserializeError(format!(
            "unknown operation: {value}"
        ))),
    }
}

fn payload_record(payload: &Payload) -> String {
    match payload {
        Payload::Token(value) => format!("Token:{}", escape(value)),
        Payload::Number(value) => format!("Number:{value}"),
        Payload::Symbol(value) => format!("Symbol:{}", escape(value)),
    }
}

fn parse_payload(value: &str) -> RuntimeResult<Payload> {
    let mut parts = value.splitn(2, ':');
    let kind = parts
        .next()
        .ok_or_else(|| RuntimeError::DeserializeError("missing payload kind".to_string()))?;
    let value = parts
        .next()
        .ok_or_else(|| RuntimeError::DeserializeError("missing payload value".to_string()))?;

    match kind {
        "Token" => Ok(Payload::Token(unescape(value)?)),
        "Number" => value
            .parse::<i64>()
            .map(Payload::Number)
            .map_err(|err| RuntimeError::DeserializeError(err.to_string())),
        "Symbol" => Ok(Payload::Symbol(unescape(value)?)),
        _ => Err(RuntimeError::DeserializeError(format!(
            "unknown payload kind: {kind}"
        ))),
    }
}

fn parse_id_list(value: &str) -> RuntimeResult<Vec<UnitId>> {
    if value.is_empty() {
        return Ok(Vec::new());
    }

    split_escaped(value, ',')
        .into_iter()
        .map(|id| unescape(&id).map(UnitId))
        .collect()
}

fn escape(value: &str) -> String {
    let mut escaped = String::new();
    for ch in value.chars() {
        match ch {
            '\\' => escaped.push_str("\\\\"),
            '|' => escaped.push_str("\\p"),
            ',' => escaped.push_str("\\c"),
            ':' => escaped.push_str("\\d"),
            _ => escaped.push(ch),
        }
    }
    escaped
}

fn unescape(value: &str) -> RuntimeResult<String> {
    let mut chars = value.chars();
    let mut unescaped = String::new();
    while let Some(ch) = chars.next() {
        if ch != '\\' {
            unescaped.push(ch);
            continue;
        }

        match chars.next() {
            Some('\\') => unescaped.push('\\'),
            Some('p') => unescaped.push('|'),
            Some('c') => unescaped.push(','),
            Some('d') => unescaped.push(':'),
            Some(other) => {
                return Err(RuntimeError::DeserializeError(format!(
                    "invalid escape sequence: \\{other}"
                )));
            }
            None => {
                return Err(RuntimeError::DeserializeError(
                    "trailing escape sequence".to_string(),
                ));
            }
        }
    }
    Ok(unescaped)
}

fn split_escaped(value: &str, delimiter: char) -> Vec<String> {
    let mut parts = Vec::new();
    let mut current = String::new();
    let mut escaped = false;

    for ch in value.chars() {
        if escaped {
            current.push('\\');
            current.push(ch);
            escaped = false;
            continue;
        }

        if ch == '\\' {
            escaped = true;
            continue;
        }

        if ch == delimiter {
            parts.push(std::mem::take(&mut current));
        } else {
            current.push(ch);
        }
    }

    if escaped {
        current.push('\\');
    }
    parts.push(current);
    parts
}
