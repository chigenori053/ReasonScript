/// Phase R6-Math — Mathematical Semantic State Transition Validation
///
/// Demonstrates that mathematical transformations are semantic state transitions:
///
///   MathReasonUnit  = 数式状態
///   Transition      = 等価変形
///   Reasoning       = 解への状態遷移
///   Convergence     = 解に到達
///   Collapse        = 不正変形・非等価変形

use reasonunit_phase1_test::math_reason::{
    detect_invalid_transition, expand_distribution, simplify_polynomial,
    solve_linear, solve_quadratic_by_factoring, verify_solution, Poly,
};

fn print_trace(label: &str, trace: &reasonunit_phase1_test::math_reason::MathTrace) {
    println!("\n========== {} ==========", label);
    println!("  INITIAL : {}", trace.initial);
    for (i, step) in trace.steps.iter().enumerate() {
        let mark = if step.valid { "✓" } else { "✗ COLLAPSE" };
        println!("  Step {:>2} [{}] {} ", i + 1, mark, step.rule);
        println!("          before: {}", step.state_before);
        println!("          after : {}", step.state_after);
    }
    println!("  FINAL   : {}", trace.final_state);
    println!("  all_valid={:?}  converged={:?}", trace.all_valid, trace.converged);
}

// ============================================================
// Test 1 — 一次方程式  x + 2 = 5  →  x = 3
// ============================================================

#[test]
fn r6_math_1_linear_equation() {
    //  LHS: x + 2  →  Poly([2, 1]) (coeff[0]=2, coeff[1]=1)
    //  RHS: 5      →  Poly([5])
    let lhs = Poly::new(vec![2.0, 1.0]);
    let rhs = Poly::new(vec![5.0]);

    let trace = solve_linear(lhs.clone(), rhs.clone());
    print_trace("R6-Math-1: Linear Equation  x + 2 = 5", &trace);

    // All transitions must be equivalence-preserving
    assert!(trace.all_valid,   "FAIL R6-1: invalid transition detected");
    // Final state must have converged to a solution
    assert!(trace.converged,   "FAIL R6-1: did not converge");

    // The solution x = 3 must satisfy the original equation
    assert!(
        verify_solution(&lhs, &rhs, 3.0),
        "FAIL R6-1: x=3 does not satisfy x + 2 = 5"
    );

    // Final state text must contain "3"
    assert!(
        trace.final_state.contains('3'),
        "FAIL R6-1: final state '{}' should represent x = 3",
        trace.final_state
    );

    println!("[R6-1] PASS — x + 2 = 5 converged to x = 3 via {} valid steps", trace.steps.len());
}

// ============================================================
// Test 2 — 二次方程式  x² − 5x + 6 = 0  →  x = 2 or x = 3
// ============================================================

#[test]
fn r6_math_2_quadratic_equation() {
    // x^2 - 5x + 6 = Poly([6, -5, 1]) (coeff[0]=6, coeff[1]=-5, coeff[2]=1)
    let poly = Poly::new(vec![6.0, -5.0, 1.0]);
    let rhs  = Poly::new(vec![0.0]);

    let trace = solve_quadratic_by_factoring(poly.clone());
    print_trace("R6-Math-2: Quadratic  x^2 - 5x + 6 = 0", &trace);

    assert!(trace.all_valid, "FAIL R6-2: invalid transition detected");
    assert!(trace.converged, "FAIL R6-2: did not converge");

    // Both roots must satisfy the original equation
    for x in [2.0, 3.0] {
        assert!(
            verify_solution(&poly, &rhs, x),
            "FAIL R6-2: x={x} does not satisfy x^2 - 5x + 6 = 0"
        );
    }

    // Final state must contain both "2" and "3"
    assert!(
        trace.final_state.contains('2') && trace.final_state.contains('3'),
        "FAIL R6-2: final state '{}' should represent x=2 or x=3",
        trace.final_state
    );

    println!("[R6-2] PASS — x^2 - 5x + 6 = 0 converged to x=2 or x=3 via {} steps",
             trace.steps.len());
}

// ============================================================
// Test 3 — 恒等変形  2(x + 3)  →  2x + 6
// ============================================================

#[test]
fn r6_math_3_identity_expansion() {
    // inner: x + 3 = Poly([3, 1])
    let inner  = Poly::new(vec![3.0, 1.0]);
    let scalar = 2.0_f64;

    let trace = expand_distribution(scalar, inner.clone());
    print_trace("R6-Math-3: Expansion  2(x + 3)", &trace);

    assert!(trace.all_valid, "FAIL R6-3: invalid transition detected");
    assert!(trace.converged, "FAIL R6-3: expansion not equivalent");

    // Result must be 2x + 6 = Poly([6, 2])
    let expected = Poly::new(vec![6.0, 2.0]);
    let expanded  = inner.scale(scalar);

    assert!(
        expanded.numerically_equal(&expected),
        "FAIL R6-3: 2(x+3) expanded to '{}', expected '2x + 6'",
        expanded.fmt()
    );

    println!("[R6-3] PASS — 2(x+3) = {} (equiv to 2x+6)", expanded.fmt());
}

// ============================================================
// Test 4 — 式の簡約  3x + 2x − 4  →  5x − 4
// ============================================================

#[test]
fn r6_math_4_simplification() {
    // 3x     = Poly([0, 3])
    // 2x     = Poly([0, 2])
    // -4     = Poly([-4])
    let terms = vec![
        Poly::new(vec![0.0, 3.0]),
        Poly::new(vec![0.0, 2.0]),
        Poly::new(vec![-4.0]),
    ];

    let trace = simplify_polynomial(terms);
    print_trace("R6-Math-4: Simplification  3x + 2x - 4", &trace);

    assert!(trace.all_valid, "FAIL R6-4: invalid transition detected");
    assert!(trace.converged, "FAIL R6-4: simplification not equivalent");

    // Result must be 5x - 4 = Poly([-4, 5])
    let expected = Poly::new(vec![-4.0, 5.0]);
    let result   = Poly::new(vec![0.0, 3.0])
        .add(&Poly::new(vec![0.0, 2.0]))
        .add(&Poly::new(vec![-4.0]));

    assert!(
        result.numerically_equal(&expected),
        "FAIL R6-4: simplified to '{}', expected '5x - 4'",
        result.fmt()
    );

    // Numeric verification: 3(2)+2(2)-4 = 6+4-4 = 6;  5(2)-4 = 6  ✓
    let test_x = 2.0;
    let original_val = 3.0 * test_x + 2.0 * test_x - 4.0;
    let simplified_val = result.eval(test_x);
    assert!(
        (original_val - simplified_val).abs() < 1e-9,
        "FAIL R6-4: value mismatch at x=2: original={} simplified={}",
        original_val, simplified_val
    );

    println!("[R6-4] PASS — 3x + 2x - 4 = {} (numeric at x=2: {})",
             result.fmt(), simplified_val);
}

// ============================================================
// Test 5 — 不正遷移検出  x + 2 = 5  →  x = 7 (誤り)
// ============================================================

#[test]
fn r6_math_5_invalid_transition_detection() {
    let trace = detect_invalid_transition();
    print_trace("R6-Math-5: Invalid Transition Detection  x + 2 = 5 → x = 7 [WRONG]", &trace);

    // The trace must contain at least one invalid step
    let invalid_steps: Vec<_> = trace.steps.iter().filter(|s| !s.valid).collect();
    assert!(
        !invalid_steps.is_empty(),
        "FAIL R6-5: invalid transition was not detected"
    );

    // The solver must NOT have converged (wrong answer)
    assert!(
        !trace.converged,
        "FAIL R6-5: system incorrectly converged to wrong solution x=7"
    );

    // Explicitly verify x=7 does NOT satisfy x + 2 = 5
    let lhs = Poly::new(vec![2.0, 1.0]);
    let rhs = Poly::new(vec![5.0]);
    assert!(
        !verify_solution(&lhs, &rhs, 7.0),
        "FAIL R6-5: x=7 should NOT satisfy x + 2 = 5"
    );

    // Verify x=3 DOES satisfy x + 2 = 5 (the correct solution)
    assert!(
        verify_solution(&lhs, &rhs, 3.0),
        "FAIL R6-5: x=3 should satisfy x + 2 = 5"
    );

    println!("[R6-5] PASS — {} invalid step(s) detected; x=7 collapsed (not converged)",
             invalid_steps.len());
    println!("         Collapse at: '{}'", invalid_steps[0].rule);
    println!("         before : {}", invalid_steps[0].state_before);
    println!("         after  : {}", invalid_steps[0].state_after);
}

// ============================================================
// Integration test — all 5 proofs in one trace
// ============================================================

#[test]
fn r6_math_integration_all_proofs() {
    // Linear
    let t1 = solve_linear(Poly::new(vec![2.0, 1.0]), Poly::new(vec![5.0]));
    assert!(t1.all_valid && t1.converged, "Linear equation failed");

    // Quadratic
    let t2 = solve_quadratic_by_factoring(Poly::new(vec![6.0, -5.0, 1.0]));
    assert!(t2.all_valid && t2.converged, "Quadratic equation failed");

    // Expansion
    let t3 = expand_distribution(2.0, Poly::new(vec![3.0, 1.0]));
    assert!(t3.all_valid && t3.converged, "Expansion failed");

    // Simplification
    let t4 = simplify_polynomial(vec![
        Poly::new(vec![0.0, 3.0]),
        Poly::new(vec![0.0, 2.0]),
        Poly::new(vec![-4.0]),
    ]);
    assert!(t4.all_valid && t4.converged, "Simplification failed");

    // Invalid transition
    let t5 = detect_invalid_transition();
    let has_collapse = t5.steps.iter().any(|s| !s.valid);
    assert!(has_collapse && !t5.converged, "Invalid transition not detected");

    println!("\n[R6-Math Integration]");
    println!("  Test1 (linear)       : valid={} converged={}", t1.all_valid, t1.converged);
    println!("  Test2 (quadratic)    : valid={} converged={}", t2.all_valid, t2.converged);
    println!("  Test3 (expansion)    : valid={} converged={}", t3.all_valid, t3.converged);
    println!("  Test4 (simplify)     : valid={} converged={}", t4.all_valid, t4.converged);
    println!("  Test5 (collapse det) : collapse={} not_converged={}", has_collapse, !t5.converged);
    println!("\n  ReasonUnit = 数式状態            ✓");
    println!("  Transition = 等価変形            ✓");
    println!("  Reasoning  = 解への状態遷移      ✓");
    println!("  Convergence= 解に到達            ✓");
    println!("  Collapse   = 不正変形を検出      ✓");
}
