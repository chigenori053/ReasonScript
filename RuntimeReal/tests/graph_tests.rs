use ndarray::array;
use reasonscript_runtime_real::core::types::{RelationType, StateType, TransitionType, UnitType};
use reasonscript_runtime_real::core::{transition::TransitionOp, ReasonUnit, State, Transition};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph};

#[test]
fn test_graph_creation_and_topology() {
    let mut graph = ReasonGraph::default();

    // Create states
    let ru_dog = ReasonUnit::new("Dog", UnitType::Symbolic, array![1.0]);
    let state_dog = State::new(StateType::Concept, ru_dog.clone());
    let id_state_dog = graph.add_state(state_dog);

    let ru_mammal = ReasonUnit::new("Mammal", UnitType::Symbolic, array![2.0]);
    let state_mammal = State::new(StateType::Concept, ru_mammal);
    let id_state_mammal = graph.add_state(state_mammal);

    // Create nodes mapped to states
    let node_dog = Node::new(id_state_dog);
    let id_node_dog = graph.add_node(node_dog);

    let node_mammal = Node::new(id_state_mammal);
    let id_node_mammal = graph.add_node(node_mammal);

    // Create transition edge
    let trans_op = TransitionOp::Addition(ru_dog);
    let transition = Transition::new(TransitionType::Deduction, trans_op);
    let edge = Edge::new(id_node_dog, id_node_mammal, RelationType::IsA, transition);

    graph.add_edge(edge);

    assert_eq!(graph.nodes.len(), 2);
    assert_eq!(graph.states.len(), 2);
    assert_eq!(graph.edges.len(), 1);

    let fetched_state = graph.get_node_state(&id_node_dog).unwrap();
    assert_eq!(fetched_state.value.label, "Dog");
}
