use crate::graph::{ReasonGraph, Edge};
use crate::core::dynamics::{DynamicsContext, ActivationState};
use crate::core::SemanticContext;
use crate::core::types::RelationType;
use uuid::Uuid;

pub struct Dynamics;

impl Dynamics {
    /// Activate a state
    pub fn activate(context: &mut DynamicsContext, state_id: Uuid) {
        match context.get_state(&state_id) {
            ActivationState::Inactive => {
                context.set_state(state_id, ActivationState::Active);
                if !context.active_states.contains(&state_id) {
                    context.active_states.push(state_id);
                }
                context.activation_history.push(state_id);
            }
            ActivationState::Visited => {
                // Loop detected or re-activation
                // In v0.1 we just re-activate if needed, or handle loop
            }
            ActivationState::Active => {}
        }
    }

    /// Propagate activation to reachable states
    pub fn propagate(graph: &ReasonGraph, context: &mut DynamicsContext) {
        let current_active = context.active_states.clone();
        context.active_states.clear();

        if context.propagation_depth >= context.max_depth {
            return;
        }

        for state_id in current_active {
            context.set_state(state_id, ActivationState::Visited);
            
            // Find all outgoing edges from the active state
            let reachable_edges: Vec<_> = graph.edges.iter()
                .filter(|e| e.source == state_id)
                .collect();

            for edge in reachable_edges {
                // Propagation Rule: Active(A) && Edge(A,B) => Activate(B)
                Self::activate(context, edge.target);
                if !context.edge_history.contains(&edge.id) {
                    context.edge_history.push(edge.id);
                }
            }
        }
        context.propagation_depth += 1;
    }

    /// Perform transitive closure on relations
    pub fn closure(graph: &mut ReasonGraph, _semantic_context: &SemanticContext) -> usize {
        let mut new_edges = Vec::new();

        // v0.1 Implementation of Taxonomic, Part-Whole, and Causal closures
        // We use a snapshot of edges to avoid concurrent modification issues
        let edges = graph.edges.clone();

        for e1 in &edges {
            for e2 in &edges {
                // A -> B, B -> C => A -> C (if same relation)
                if e1.target == e2.source && e1.relation == e2.relation {
                    match e1.relation {
                        RelationType::IsA | RelationType::PartOf | RelationType::Cause => {
                            // Check if the edge already exists in the original graph
                            let already_exists = graph.edges.iter().any(|e| 
                                e.source == e1.source && 
                                e.target == e2.target && 
                                e.relation == e1.relation
                            );

                            if !already_exists {
                                let mut new_edge = Edge::new(
                                    e1.source, 
                                    e2.target, 
                                    e1.relation, 
                                    e1.transition.clone()
                                );
                                new_edge.cost = e1.cost + e2.cost;
                                new_edges.push(new_edge);
                            }
                        }
                        _ => {}
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
        context: &mut DynamicsContext,
        semantic_context: &SemanticContext,
    ) -> bool {
        // 1. Propagate
        Self::propagate(graph, context);

        // 2. Closure
        let new_edges = Self::closure(graph, semantic_context);

        // 3. Convergence check
        // If no new states are active and no new edges were generated, we converged
        if context.active_states.is_empty() && new_edges == 0 {
            true // Converged
        } else {
            false // Continue
        }
    }
}
