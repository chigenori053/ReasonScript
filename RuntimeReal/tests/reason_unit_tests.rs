use reasonscript_runtime_real::core::types::{UnitType, StateType};
use reasonscript_runtime_real::core::{ReasonUnit, State};
use ndarray::array;

#[test]
fn test_reason_unit_creation() {
    let ru = ReasonUnit::new("Test Unit", UnitType::Vector, array![1.0, 2.0, 3.0]);
    assert_eq!(ru.label, "Test Unit");
    assert_eq!(ru.unit_type, UnitType::Vector);
    assert_eq!(ru.vector, array![1.0, 2.0, 3.0]);
}

#[test]
fn test_reason_unit_algebra() {
    let ru_a = ReasonUnit::new("A", UnitType::Vector, array![1.0, 2.0]);
    let ru_b = ReasonUnit::new("B", UnitType::Vector, array![3.0, 4.0]);
    
    let sum = ru_a.add(&ru_b);
    assert_eq!(sum.vector, array![4.0, 6.0]);
    assert_eq!(sum.unit_type, UnitType::Vector);
    
    let diff = ru_b.sub(&ru_a);
    assert_eq!(diff.vector, array![2.0, 2.0]);
    
    let neg = ru_a.neg();
    assert_eq!(neg.vector, array![-1.0, -2.0]);
}

#[test]
fn test_state_creation() {
    let ru = ReasonUnit::new("Dog", UnitType::Symbolic, array![1.0]);
    let state = State::new(StateType::Concept, ru);
    
    assert_eq!(state.state_type, StateType::Concept);
    assert_eq!(state.value.label, "Dog");
}
