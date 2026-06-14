use crate::graph::{ReasonGraph, Edge};
use crate::core::dynamics::{DynamicsContext, ActivationState};
use crate::core::SemanticContext;
use crate::core::StructuralConstraintValidator;
use crate::core::types::RelationType;
use crate::executor::ExecutionContext;
use crate::executor::execution_context::TraceEvent;
use uuid::Uuid;
use std::collections::{HashSet, HashMap};

pub struct Dynamics;

impl Dynamics {
    /// Activate a state
    pub fn activate(context: &mut ExecutionContext, state_id: Uuid) {
        match context.dynamics.get_state(&state_id) {
            ActivationState::Inactive => {
                context.dynamics.set_state(state_id, ActivationState::Active);
                if !context.dynamics.active_states.contains(&state_id) {
                    context.dynamics.active_states.push(state_id);
                }
                context.dynamics.activation_history.push(state_id);
                context.record_trace(TraceEvent::Activation(state_id));
            }
            ActivationState::Visited => {
                // Loop detected or re-activation
            }
            ActivationState::Active => {}
        }
    }

    /// Propagate activation to reachable states
    pub fn propagate(graph: &mut ReasonGraph, context: &mut ExecutionContext) {
        if context.dynamics.active_states.is_empty() {
            return;
        }

        let current_active = std::mem::take(&mut context.dynamics.active_states);

        if context.dynamics.propagation_depth >= context.dynamics.max_depth {
            return;
        }

        // Build adjacency map for efficient lookup
        let mut outgoing: HashMap<Uuid, Vec<Uuid>> = HashMap::with_capacity(graph.edges.len());
        for edge in &graph.edges {
            outgoing.entry(edge.source).or_default().push(edge.id);
        }

        for state_id in current_active {
            context.dynamics.set_state(state_id, ActivationState::Visited);
            
            // Find the node to update metrics
            if let Some(node) = graph.nodes.get(&state_id) {
                if let Some(state) = graph.states.get_mut(&node.state_id) {
                    state.value.increment_propagation();
                }
            }

            if let Some(reachable_edge_ids) = outgoing.get(&state_id).cloned() {
                for edge_id in reachable_edge_ids {
                    // Find the edge again to get target
                    if let Some(edge) = graph.edges.iter().find(|e| e.id == edge_id) {
                        let target = edge.target;
                        Self::activate(context, target);
                        
                        if !context.dynamics.edge_history.contains(&edge_id) {
                            context.dynamics.edge_history.push(edge_id);
                        }
                        
                        context.record_trace(TraceEvent::Propagation { 
                            source: state_id, 
                            target, 
                            edge_id 
                        });
                    }
                }
            }
        }
        context.dynamics.propagation_depth += 1;
    }

    /// Perform transitive closure on relations
    pub fn closure(graph: &mut ReasonGraph, context: &mut ExecutionContext, _semantic_context: &SemanticContext) -> usize {
        let mut new_edges = Vec::new();
        let mut existing_set: HashSet<(Uuid, Uuid, RelationType)> = graph.edges.iter()
            .map(|e| (e.source, e.target, e.relation))
            .collect();

        let mut outgoing: HashMap<(Uuid, RelationType), Vec<usize>> = HashMap::new();
        let mut incoming: HashMap<(Uuid, RelationType), Vec<usize>> = HashMap::new();

        for (idx, edge) in graph.edges.iter().enumerate() {
            match edge.relation {
                RelationType::IsA | RelationType::PartOf | RelationType::Cause => {
                    outgoing.entry((edge.source, edge.relation)).or_default().push(idx);
                    incoming.entry((edge.target, edge.relation)).or_default().push(idx);
                }
                _ => {}
            }
        }

        for (&(bridge_node, relation), in_indices) in &incoming {
            if let Some(out_indices) = outgoing.get(&(bridge_node, relation)) {
                for &idx1 in in_indices {
                    for &idx2 in out_indices {
                        let e1 = &graph.edges[idx1];
                        let e2 = &graph.edges[idx2];
                        let key = (e1.source, e2.target, relation);
                        let structurally_valid = graph
                            .get_node_state(&e1.source)
                            .zip(graph.get_node_state(&e2.target))
                            .is_some_and(|(source, target)| {
                                StructuralConstraintValidator::is_compatible(
                                    source.state_type,
                                    relation,
                                    target.state_type,
                                )
                            });
                        
                        if e1.source != e2.target
                            && !existing_set.contains(&key)
                            && structurally_valid
                        {
                            let mut new_edge = Edge::new(
                                e1.source, 
                                e2.target, 
                                relation, 
                                e1.transition.clone()
                            );
                            new_edge.cost = e1.cost + e2.cost;
                            new_edge.confidence = e1.confidence * e2.confidence;
                            
                            // Update metrics on the source ReasonUnit
                            if let Some(node) = graph.nodes.get(&e1.source) {
                                if let Some(state) = graph.states.get_mut(&node.state_id) {
                                    state.value.increment_closure();
                                }
                            }

                            context.record_trace(TraceEvent::Closure { 
                                source: e1.source, 
                                target: e2.target, 
                                relation_id: Uuid::nil() // Placeholder for relation edge
                            });

                            existing_set.insert(key);
                            new_edges.push(new_edge);
                        }
                    }
                }
            }
        }

        let count = new_edges.len();
        for edge in new_edges {
            graph.add_edge(edge);
        }
        count
    }

    /// Run a single dynamics cycle
    pub fn run_cycle(
        graph: &mut ReasonGraph,
        context: &mut ExecutionContext,
        semantic_context: &SemanticContext,
    ) -> bool {
        // 1. Propagate
        Self::propagate(graph, context);

        // 2. Closure
        let new_edges = Self::closure(graph, context, semantic_context);

        // 3. Convergence check
        if context.dynamics.active_states.is_empty() && new_edges == 0 {
            true // Converged
        } else {
            false // Continue
        }
    }
}
