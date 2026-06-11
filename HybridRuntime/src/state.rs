use crate::error::RuntimeError;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Candidate {
    pub identity: String,
    pub probability: f64,
    pub semantic_vector: Vec<f64>,
}

impl Candidate {
    pub fn new(identity: impl Into<String>, probability: f64, semantic_vector: Vec<f64>) -> Self {
        Self {
            identity: identity.into(),
            probability,
            semantic_vector,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Evidence {
    pub label: String,
    pub candidate_support: Vec<f64>,
    pub supported: bool,
}

impl Evidence {
    pub fn supported(label: impl Into<String>, candidate_support: Vec<f64>) -> Self {
        Self {
            label: label.into(),
            candidate_support,
            supported: true,
        }
    }

    pub fn unsupported(label: impl Into<String>) -> Self {
        Self {
            label: label.into(),
            candidate_support: Vec::new(),
            supported: false,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct StableState {
    pub identity: String,
}

impl StableState {
    pub fn new(identity: impl Into<String>) -> Self {
        Self {
            identity: identity.into(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct AmbiguousState {
    pub candidates: Vec<Candidate>,
    pub evidence: Vec<Evidence>,
}

impl AmbiguousState {
    pub fn new(candidates: Vec<Candidate>, evidence: Vec<Evidence>) -> Self {
        Self {
            candidates,
            evidence,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum StateKind {
    Stable,
    Ambiguous,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum StatePayload {
    Stable(StableState),
    Ambiguous(AmbiguousState),
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct State {
    pub kind: StateKind,
    pub payload: StatePayload,
}

impl State {
    pub fn stable(identity: impl Into<String>) -> Self {
        Self {
            kind: StateKind::Stable,
            payload: StatePayload::Stable(StableState::new(identity)),
        }
    }

    pub fn ambiguous(candidates: Vec<Candidate>, evidence: Vec<Evidence>) -> Self {
        Self {
            kind: StateKind::Ambiguous,
            payload: StatePayload::Ambiguous(AmbiguousState::new(candidates, evidence)),
        }
    }

    pub fn as_stable(&self) -> Result<&StableState, RuntimeError> {
        match &self.payload {
            StatePayload::Stable(state) => Ok(state),
            StatePayload::Ambiguous(_) => Err(RuntimeError::ExpectedStableState),
        }
    }

    pub fn as_ambiguous(&self) -> Result<&AmbiguousState, RuntimeError> {
        match &self.payload {
            StatePayload::Ambiguous(state) => Ok(state),
            StatePayload::Stable(_) => Err(RuntimeError::ExpectedAmbiguousState),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct HybridReasonUnit {
    state: State,
}

impl HybridReasonUnit {
    pub fn new(state: State) -> Self {
        Self { state }
    }

    pub fn state(&self) -> &State {
        &self.state
    }

    pub(crate) fn replace_state(&mut self, state: State) {
        self.state = state;
    }
}

#[derive(Clone, Debug)]
pub struct StateManager {
    unit: HybridReasonUnit,
    units: BTreeMap<String, HybridReasonUnit>,
}

impl StateManager {
    pub fn new(unit: HybridReasonUnit) -> Self {
        Self {
            unit,
            units: BTreeMap::new(),
        }
    }

    pub fn unit(&self) -> &HybridReasonUnit {
        &self.unit
    }

    pub fn current(&self) -> &State {
        self.unit.state()
    }

    pub fn replace(&mut self, state: State) {
        self.unit.replace_state(state);
    }

    pub fn register_unit(&mut self, name: impl Into<String>, unit: HybridReasonUnit) {
        self.units.insert(name.into(), unit);
    }

    pub fn unit_named(&self, name: &str) -> Option<&HybridReasonUnit> {
        self.units.get(name)
    }

    pub fn unit_count(&self) -> usize {
        1 + self.units.len()
    }
}
