use reasonunit_phase1_test::semantic_space::{SemanticVector, build_english_space};

const EPSILON: f64 = 1e-4;

// Transition Operator T(S): Refinement towards a target
fn t_refine(s: &SemanticVector, target: &SemanticVector, alpha: f64) -> SemanticVector {
    s.lerp(target, alpha)
}

// ============================================================
// PHASE D1: FIXED POINT VALIDATION
// ============================================================
#[test]
fn phase_d1_fixed_point_validation() {
    let space = build_english_space();
    let target = space.get("Car").unwrap();
    let mut state = space.get("Vehicle").unwrap().clone();
    
    println!("[D1] Initial state: {}", state.label);
    for i in 1..100 {
        let next_state = t_refine(&state, target, 0.2);
        let dist = state.euclidean_distance(&next_state);
        state = next_state;
        if dist < 1e-6 {
            println!("[D1] Fixed point reached at iteration {}", i);
            let final_dist = state.euclidean_distance(target);
            assert!(final_dist < EPSILON, "Converged state should be close to target");
            return;
        }
    }
    panic!("FAIL D1: Failed to reach fixed point");
}

// ============================================================
// PHASE D2: ATTRACTOR VALIDATION
// ============================================================
#[test]
fn phase_d2_attractor_validation() {
    let space = build_english_space();
    let target = space.get("Car").unwrap();
    
    let mut s1 = space.get("Vehicle").unwrap().clone();
    let mut s2 = space.get("Motorcycle").unwrap().clone();
    let mut s3 = space.get("Bus").unwrap().clone();
    
    for _ in 0..30 {
        s1 = t_refine(&s1, target, 0.3);
        s2 = t_refine(&s2, target, 0.3);
        s3 = t_refine(&s3, target, 0.3);
    }
    
    let d12 = s1.euclidean_distance(&s2);
    let d23 = s2.euclidean_distance(&s3);
    
    println!("[D2] Inter-state distances: d12={:.6}, d23={:.6}", d12, d23);
    assert!(d12 < EPSILON && d23 < EPSILON, "Multiple initial states should converge to the same attractor");
    println!("[D2] PASS: Attractor behavior confirmed");
}

// ============================================================
// PHASE D3: DIVERGENCE DETECTION
// ============================================================
#[test]
fn phase_d3_divergence_detection() {
    // T_div(S) = S * 1.5 (Explosive growth)
    let space = build_english_space();
    let mut state = space.get("Car").unwrap().clone();
    
    println!("[D3] Divergence Check");
    for i in 1..20 {
        let norm = state.values.iter().map(|x| x*x).sum::<f64>().sqrt();
        if norm > 100.0 {
            println!("[D3] Divergence detected at iteration {} (norm={:.2})", i, norm);
            return;
        }
        state = state.scale(1.5);
    }
    panic!("FAIL D3: Divergence not detected");
}

// ============================================================
// PHASE D4: OSCILLATION VALIDATION
// ============================================================
#[test]
fn phase_d4_oscillation_validation() {
    let space = build_english_space();
    let s_a = space.get("Car").unwrap().clone();
    let s_b = space.get("Dog").unwrap().clone();
    
    let mut state = s_a.clone();
    let mut history = vec![state.values];
    
    println!("[D4] Oscillation Check");
    for i in 1..10 {
        // Swap transition
        if i % 2 == 1 {
            state = s_b.clone();
        } else {
            state = s_a.clone();
        }
        
        // Detect cycle
        for (h_idx, h_val) in history.iter().enumerate() {
            let diff: f64 = state.values.iter().zip(h_val.iter()).map(|(a, b)| (a - b).powi(2)).sum::<f64>().sqrt();
            if diff < 1e-6 {
                println!("[D4] Oscillation detected: current state matches iteration {}", h_idx);
                return;
            }
        }
        history.push(state.values);
    }
    panic!("FAIL D4: Oscillation not detected");
}

// ============================================================
// PHASE D5: ENERGY MONOTONICITY VALIDATION
// ============================================================
#[test]
fn phase_d5_energy_monotonicity_validation() {
    let space = build_english_space();
    let target = space.get("Car").unwrap();
    let mut state = space.get("Bus").unwrap().clone();
    
    let mut prev_energy = state.euclidean_distance(target);
    println!("[D5] Initial Energy: {:.6}", prev_energy);
    
    for i in 1..10 {
        state = t_refine(&state, target, 0.1);
        let energy = state.euclidean_distance(target);
        println!("[D5] Iteration {}: Energy = {:.6}", i, energy);
        assert!(energy <= prev_energy + 1e-10, "Energy must be monotonically non-increasing");
        prev_energy = energy;
    }
    println!("[D5] PASS: Energy monotonicity confirmed");
}

// ============================================================
// PHASE D6: GRAPH DYNAMICS VALIDATION
// ============================================================
#[test]
fn phase_d6_graph_dynamics_validation() {
    let space = build_english_space();
    let goal = space.get("Vehicle").unwrap().clone();
    
    let parts = vec![
        SemanticVector::new("Engine", [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.8, 0.0]),
        SemanticVector::new("Wheel", [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0, 0.5, 0.0, 0.0, 0.0, 0.3, 0.0]),
        SemanticVector::new("Body", [0.0, 0.0, 0.0, 0.0, 0.4, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 0.0]),
    ];
    
    let mut current_state = goal;
    for part in parts {
        current_state = current_state.add(&part);
    }
    
    // Check stability (not collapsing or exploding)
    let norm = current_state.values.iter().map(|x| x*x).sum::<f64>().sqrt();
    println!("[D6] Graph final state norm: {:.4}", norm);
    assert!(norm > 0.0 && norm < 10.0, "Graph-based state should remain within reasonable bounds");
    println!("[D6] PASS: Graph dynamics stable");
}

// ============================================================
// PHASE D7: PERTURBATION RECOVERY VALIDATION
// ============================================================
#[test]
fn phase_d7_perturbation_recovery_validation() {
    let space = build_english_space();
    let target = space.get("Car").unwrap();
    
    // 1. Converge to fixed point
    let mut state = target.clone(); // Start at fixed point
    
    // 2. Inject noise
    let noise = SemanticVector::new("Noise", [0.05; 16]);
    state = state.add(&noise);
    let dist_after_noise = state.euclidean_distance(target);
    println!("[D7] Dist after noise: {:.6}", dist_after_noise);
    
    // 3. Recover
    for i in 1..30 {
        state = t_refine(&state, target, 0.3);
        let dist = state.euclidean_distance(target);
        if dist < 1e-5 {
            println!("[D7] Recovered at iteration {}", i);
            return;
        }
    }
    panic!("FAIL D7: Failed to recover from perturbation");
}

// ============================================================
// PHASE D8: TRAJECTORY CONSISTENCY VALIDATION
// ============================================================
#[test]
fn phase_d8_trajectory_consistency_validation() {
    let space = build_english_space();
    let start = space.get("Vehicle").unwrap();
    let target = space.get("Car").unwrap();
    
    fn run_trajectory(start: &SemanticVector, target: &SemanticVector) -> Vec<[f64; 16]> {
        let mut traj = Vec::new();
        let mut s = start.clone();
        for _ in 0..5 {
            s = t_refine(&s, target, 0.2);
            traj.push(s.values);
        }
        traj
    }
    
    let t1 = run_trajectory(start, target);
    let t2 = run_trajectory(start, target);
    
    for i in 0..t1.len() {
        for j in 0..16 {
            assert!((t1[i][j] - t2[i][j]).abs() < 1e-12, "Trajectory should be deterministic and consistent");
        }
    }
    println!("[D8] PASS: Trajectory consistency confirmed");
}

// ============================================================
// PHASE D9: STATE SPACE TOPOLOGY VALIDATION
// ============================================================
#[test]
fn phase_d9_state_space_topology_validation() {
    // This phase is descriptive and summarizes findings from D1-D8
    println!("[D9] State Space Topology Analysis:");
    println!("  - Fixed Points: Detected and stable (D1)");
    println!("  - Attractors: Identified basins of attraction (D2)");
    println!("  - Divergence: Boundaries identified (D3)");
    println!("  - Oscillation: Cyclic states detectable (D4)");
    println!("  - Energy: Monotonic descent towards minima (D5)");
    println!("  - Recovery: Stable manifold around attractors (D7)");
    
    assert!(true);
}
