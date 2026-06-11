use crate::ambiguity::AmbiguityObservation;
use crate::decision::{DecisionResult, StrategyKind};
use crate::error::RuntimeError;
use crate::state::AmbiguousState;
use crate::strategy::{
    ClarifyStrategy, ComplexStrategy, RealStrategy, ResolutionOutcome, ResolutionStrategy,
};
use std::collections::BTreeMap;

pub struct IdentityResolver {
    strategies: BTreeMap<StrategyKind, Box<dyn ResolutionStrategy>>,
}

impl Default for IdentityResolver {
    fn default() -> Self {
        let mut resolver = Self {
            strategies: BTreeMap::new(),
        };
        resolver.register(Box::new(RealStrategy));
        resolver.register(Box::new(ClarifyStrategy));
        resolver.register(Box::new(ComplexStrategy));
        resolver
    }
}

impl IdentityResolver {
    pub fn register(&mut self, strategy: Box<dyn ResolutionStrategy>) {
        self.strategies.insert(strategy.kind(), strategy);
    }

    pub fn available_strategies(&self) -> Vec<StrategyKind> {
        self.strategies.keys().copied().collect()
    }

    pub fn resolve(
        &self,
        state: &AmbiguousState,
        observation: &AmbiguityObservation,
        decision: &DecisionResult,
    ) -> Result<ResolutionOutcome, RuntimeError> {
        self.strategies
            .get(&decision.selected_strategy)
            .ok_or_else(|| {
                RuntimeError::StrategyUnavailable(format!("{:?}", decision.selected_strategy))
            })?
            .resolve(state, observation)
    }
}
