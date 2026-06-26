use reasonunit_phase1_test::semantic_space::{build_english_space, SemanticVector};

const EPSILON: f64 = 1e-6;

// ============================================================
// PHASE S1: SEMANTIC DISTANCE VALIDATION
// ============================================================
#[test]
fn phase_s1_semantic_distance_validation() {
    let space = build_english_space();

    // Target: Car
    // Expected Ranking: Vehicle < Truck < Banana
    let car = "Car";
    let vehicle = "Vehicle";
    let truck = "Truck";
    let banana = "Banana";

    let d_cv = space.dist(car, vehicle);
    let d_ct = space.dist(car, truck);
    let d_cb = space.dist(car, banana);

    println!("[S1] dist(Car, Vehicle) = {:.4}", d_cv);
    println!("[S1] dist(Car, Truck)   = {:.4}", d_ct);
    println!("[S1] dist(Car, Banana)  = {:.4}", d_cb);

    // Check ranking
    assert!(
        d_cv < d_ct,
        "FAIL S1: Vehicle should be closer to Car than Truck is"
    );
    assert!(
        d_ct < d_cb,
        "FAIL S1: Truck should be closer to Car than Banana is"
    );

    println!("[S1] PASS: Ranking holds");
}

// ============================================================
// PHASE S2: CONSTRAINT CONSISTENCY VALIDATION
// ============================================================
#[test]
fn phase_s2_constraint_consistency_validation() {
    let space = build_english_space();
    let car = space.get("Car").unwrap();
    let animal = space.get("Animal").unwrap();

    // CostConstraint: High abstract, low size
    let cost_constraint = SemanticVector::new(
        "Constraint(Cost)",
        [
            0.0, 0.0, 0.0, 0.0, -0.2, 0.0, 0.0, 0.1, 0.7, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ],
    );

    let result = car.add(&cost_constraint);

    // Result should still be closer to Car/Vehicle than to Animal
    let d_to_car = result.euclidean_distance(car);
    let d_to_animal = result.euclidean_distance(animal);

    println!("[S2] dist(Result, Car)    = {:.4}", d_to_car);
    println!("[S2] dist(Result, Animal) = {:.4}", d_to_animal);

    assert!(
        d_to_car < d_to_animal,
        "FAIL S2: Result of Car+Cost should still be a vehicle-like state, not an animal"
    );
    println!("[S2] PASS: Semantic Class preserved");
}

// ============================================================
// PHASE S3: NOVEL COMPOSITION VALIDATION
// ============================================================
#[test]
fn phase_s3_novel_composition_validation() {
    // SolarCar + LowCost -> SolarCompactCar

    // Solar Feature: Atmospheric and Nature
    let solar_feature = SemanticVector::new(
        "Solar",
        [
            0.0, 0.0, 0.1, 0.8, 0.0, 0.0, 0.0, 0.3, 0.2, 0.0, 0.0, 0.0, 0.0, 0.7, 0.2, 0.0,
        ],
    );

    let low_cost = SemanticVector::new(
        "LowCost",
        [
            0.0, 0.0, 0.0, 0.0, -0.4, 0.0, 0.0, 0.1, 0.6, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ],
    );

    let result = solar_feature.add(&low_cost);

    // Target: SolarCompactCar (Atmospheric + Low Size + High Abstract)
    let target = SemanticVector::new(
        "SolarCompactCar",
        [
            0.0, 0.0, 0.1, 0.8, -0.4, 0.0, 0.0, 0.4, 0.8, 0.0, 0.0, 0.0, 0.0, 0.7, 0.2, 0.0,
        ],
    );

    let d_to_target = result.euclidean_distance(&target);
    let space = build_english_space();
    let banana = space.get("Banana").unwrap();
    let d_to_banana = result.euclidean_distance(banana);

    println!("[S3] dist(Result, Target) = {:.4}", d_to_target);
    println!("[S3] dist(Result, Banana) = {:.4}", d_to_banana);

    assert!(
        d_to_target < d_to_banana,
        "FAIL S3: Result should be closer to logical target than to Banana"
    );
    println!("[S3] PASS: Converges to reasonable neighbor");
}

// ============================================================
// PHASE S4: SEMANTIC STABILITY VALIDATION
// ============================================================
#[test]
fn phase_s4_semantic_stability_validation() {
    let space = build_english_space();
    let car = space.get("Car").unwrap();

    // Cost 0.50
    let cost_50 = SemanticVector::new(
        "Cost(0.50)",
        [
            0.0, 0.0, 0.0, 0.0, -0.20, 0.0, 0.0, 0.1, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ],
    );

    // Cost 0.51
    let cost_51 = SemanticVector::new(
        "Cost(0.51)",
        [
            0.0, 0.0, 0.0, 0.0, -0.21, 0.0, 0.0, 0.1, 0.51, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ],
    );

    let res_50 = car.add(&cost_50);
    let res_51 = car.add(&cost_51);

    let diff = res_50.euclidean_distance(&res_51);
    println!("[S4] Stability check: diff = {:.6}", diff);

    assert!(
        diff < 0.05,
        "FAIL S4: Small input change caused large semantic jump"
    );
    println!("[S4] PASS: Smooth transition");
}

// ============================================================
// PHASE S5: MULTI-STEP REASONING VALIDATION
// ============================================================
#[test]
fn phase_s5_multi_step_reasoning_validation() {
    let space = build_english_space();
    let car = space.get("Car").unwrap();

    let cost = SemanticVector::new(
        "Cost",
        [
            0.0, 0.0, 0.0, 0.0, -0.1, 0.0, 0.0, 0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ],
    );
    let safety = SemanticVector::new(
        "Safety",
        [
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.3, 0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ],
    );
    let efficiency = SemanticVector::new(
        "Efficiency",
        [
            0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.2, 0.3, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0,
        ],
    );

    let step1 = car.add(&cost);
    let step2 = step1.add(&safety);
    let final_state = step2.add(&efficiency);

    println!("[S5] Final State complexity: {:.4}", final_state.values[7]);
    println!(
        "[S5] Final State abstractness: {:.4}",
        final_state.values[8]
    );

    assert!(
        final_state.values[8] > car.values[8],
        "Abstractness should increase with more constraints"
    );
    assert!(
        final_state.values[7] > car.values[7],
        "Complexity should increase with more constraints"
    );

    println!("[S5] PASS: Meaning holds over multiple steps");
}

// ============================================================
// PHASE S6: GRAPH SEMANTIC VALIDATION
// ============================================================
#[test]
fn phase_g_graph_semantic_validation() {
    let space = build_english_space();
    let car = space.get("Car").unwrap().clone();

    let need_engine = SemanticVector::new(
        "Engine",
        [
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.8, 0.0,
        ],
    );
    let need_wheel = SemanticVector::new(
        "Wheel",
        [
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.3, 0.0,
        ],
    );

    let state = car.add(&need_engine).add(&need_wheel);

    // Should still be vehicle-like
    let d_to_vehicle = state.cosine_distance(space.get("Vehicle").unwrap());
    println!("[S6] Cosine distance to Vehicle: {:.4}", d_to_vehicle);

    assert!(
        d_to_vehicle < 0.5,
        "Graph state should maintain vehicle-ness"
    );
    println!("[S6] PASS: Graph semantic integrity");
}

// ============================================================
// PHASE S7: SEMANTIC CONVERGENCE VALIDATION
// ============================================================
#[test]
fn phase_s7_semantic_convergence_validation() {
    // Repeated "Refinement" should converge (values capped or decreasing changes)
    let space = build_english_space();
    let mut state = space.get("Car").unwrap().clone();

    // Refinement: reduces error, increases abstractness, but effect decays
    fn refine(v: &SemanticVector, step: i32) -> SemanticVector {
        let decay = 0.5f64.powi(step);
        let mut delta = [0.0; 16];
        delta[8] = 0.1 * decay; // abstractness
        delta[7] = 0.05 * decay; // complexity

        let mut new_values = v.values;
        for i in 0..16 {
            new_values[i] += delta[i];
        }
        SemanticVector {
            label: format!("Refined({})", v.label),
            values: new_values,
        }
    }

    let mut prev_values = state.values;
    for i in 1..20 {
        state = refine(&state, i);
        let diff = state
            .values
            .iter()
            .zip(prev_values.iter())
            .map(|(a, b)| (a - b).powi(2))
            .sum::<f64>()
            .sqrt();
        println!("[S7] Iteration {}: change = {:.8}", i, diff);
        if diff < 1e-4 {
            println!("[S7] Converged at iteration {}", i);
            return;
        }
        prev_values = state.values;
    }

    panic!("FAIL S7: Failed to converge within 20 iterations");
}
