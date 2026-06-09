use reasonunit_phase1_test::semantic_space::{SemanticVector, build_english_space};

const EPSILON: f64 = 1e-10;

// ============================================================
// PHASE A: CLOSURE TEST
// =============================================&===============

#[test]
fn phase_a_closure_test() {
    let space = build_english_space();
    let ru_a = space.get("Car").expect("Car should exist");
    let ru_b = space.get("Truck").expect("Truck should exist");
    
    let ru_c = ru_a.add(ru_b);
    
    println!("[Phase A] Closure: {} + {} = {}", ru_a.label, ru_b.label, ru_c.label);
    
    // Check if result is a valid SemanticVector (all values are finite)
    for (i, val) in ru_c.values.iter().enumerate() {
        assert!(val.is_finite(), "Value at index {} is not finite: {}", i, val);
    }
}

// ============================================================
// PHASE B: ASSOCIATIVITY TEST
// ============================================================

#[test]
fn phase_b_associativity_test() {
    let space = build_english_space();
    let a = space.get("Car").unwrap();
    let b = space.get("Truck").unwrap();
    let c = space.get("Bus").unwrap();
    
    let lhs = a.add(b).add(c);
    let rhs = a.add(&b.add(c));
    
    println!("[Phase B] Associativity Check");
    for i in 0..16 {
        let diff = (lhs.values[i] - rhs.values[i]).abs();
        assert!(diff < EPSILON, "Associativity failed at index {}: lhs={}, rhs={}, diff={}", i, lhs.values[i], rhs.values[i], diff);
    }
    println!("[Phase B] Associativity PASS (diff < EPSILON)");
}

// ============================================================
// PHASE C: IDENTITY TEST
// ============================================================

#[test]
fn phase_c_identity_test() {
    let space = build_english_space();
    let ru = space.get("Dog").unwrap();
    let identity = SemanticVector::zero();
    
    let result = ru.add(&identity);
    
    println!("[Phase C] Identity Check: {} + Identity", ru.label);
    for i in 0..16 {
        let diff = (result.values[i] - ru.values[i]).abs();
        assert!(diff < EPSILON, "Identity failed at index {}: result={}, original={}, diff={}", i, result.values[i], ru.values[i], diff);
    }
    println!("[Phase C] Identity PASS");
}

// ============================================================
// PHASE D: INVERSE TEST
// ============================================================

#[test]
fn phase_d_inverse_test() {
    let space = build_english_space();
    let ru = space.get("Tiger").unwrap();
    let inverse = ru.neg();
    
    let result = ru.add(&inverse);
    
    println!("[Phase D] Inverse Check: {} + (-{})", ru.label, ru.label);
    for i in 0..16 {
        let diff = result.values[i].abs();
        assert!(diff < EPSILON, "Inverse failed at index {}: result={}, expected=0, diff={}", i, result.values[i], diff);
    }
    println!("[Phase D] Inverse PASS (result converges to Zero)");
}

// ============================================================
// PHASE E: METRIC CONSISTENCY TEST (P1)
// ============================================================

#[test]
fn phase_e_metric_consistency_test() {
    let space = build_english_space();
    
    // d(Car, Vehicle) < d(Car, Banana)
    // In our space, Banana is used instead of Apple
    let d_car_vehicle = space.dist("Car", "Vehicle");
    let d_car_banana  = space.dist("Car", "Banana");
    
    println!("[Phase E] Metric Consistency: dist(Car, Vehicle) = {:.4}, dist(Car, Banana) = {:.4}", d_car_vehicle, d_car_banana);
    
    assert!(
        d_car_vehicle < d_car_banana,
        "FAIL Phase E: Semantic proximity should reflect geometric distance. dist(Car, Vehicle)={:.4} should be < dist(Car, Banana)={:.4}",
        d_car_vehicle, d_car_banana
    );
    println!("[Phase E] Metric Consistency PASS");
}

// ============================================================
// PHASE F: COMPOSITIONAL REASONING TEST (P2)
// ============================================================

#[test]
fn phase_f_compositional_reasoning_test() {
    // Goal(Car) ⊕ Constraint(Cost) -> CompactCar
    
    let space = build_english_space();
    let car = space.get("Car").unwrap().clone();
    
    // Define Constraint(Cost): High abstractness, low size
    // dim layout: [animal, vehicle, tech, nature, size, speed, domestic, complexity,
    //              abstract, living, mobility, digital, fluid, atmospheric, mechanical, biological]
    let cost_constraint = SemanticVector::new("Constraint(Cost)", [
        0.0, 0.0, 0.0, 0.0, -0.3, 0.0, 0.0, 0.2, 0.8, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    ]);
    
    // Result of composition
    let reasoning_result = car.add(&cost_constraint);
    
    // Define CompactCar: Car but with reduced size, increased complexity, and increased abstractness
    let mut compact_car_values = car.values.clone();
    compact_car_values[4] -= 0.3; // Reduce size
    compact_car_values[7] += 0.2; // Increase complexity
    compact_car_values[8] += 0.8; // Increase abstractness (cost factor)
    let compact_car = SemanticVector::new("CompactCar", compact_car_values);
    
    let dist_to_compact = reasoning_result.euclidean_distance(&compact_car);
    println!("[Phase F] Compositional Reasoning: Car + CostConstraint = {}", reasoning_result.label);
    println!("[Phase F] Distance to target (CompactCar): {:.4}", dist_to_compact);
    
    assert!(dist_to_compact < 0.1, "Reasoning result should be close to the intended CompactCar state");
    println!("[Phase F] Compositional Reasoning PASS");
}

// ============================================================
// PHASE G: GRAPH INTEGRATION TEST (P3)
// ============================================================

#[test]
fn phase_g_graph_integration_test() {
    // Verify that ReasonUnits can be integrated into a graph-like sequence
    // State_0 -> State_1 -> State_2
    
    let space = build_english_space();
    let goal = space.get("Vehicle").unwrap().clone();
    
    // Need Engine
    let engine_req = SemanticVector::new("NeedEngine", [
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.8, 0.0
    ]);
    
    // Need Wheel
    let wheel_req = SemanticVector::new("NeedWheel", [
        0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.3, 0.0
    ]);
    
    let state_1 = goal.add(&engine_req);
    let state_2 = state_1.add(&wheel_req);
    
    println!("[Phase G] Graph Integration Sequence:");
    println!("  S0: {}", goal.label);
    println!("  S1: {}", state_1.label);
    println!("  S2: {}", state_2.label);
    
    assert!(state_2.values[14] > goal.values[14], "Mechanical complexity should increase");
    assert!(state_2.values[10] > goal.values[10], "Mobility factor should increase");
    
    println!("[Phase G] Graph Integration PASS");
}
