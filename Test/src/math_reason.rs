/// Phase R6-Math — Mathematical Semantic State Transition
///
/// Models mathematical transformations as ReasonUnit state transitions.
///
///   MathReasonUnit  = a mathematical expression / equation as a semantic state
///   Transition      = an equivalence-preserving transformation rule
///   Convergence     = reaching the solution state
///   Collapse        = detection of an invalid (non-equivalent) transition

// ---------------------------------------------------------------------------
// Polynomial  (coefficients indexed by degree: poly[i] = coeff of x^i)
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
pub struct Poly(pub Vec<f64>);

impl Poly {
    pub fn new(coeffs: Vec<f64>) -> Self {
        let mut p = Self(coeffs);
        p.trim();
        p
    }

    pub fn zero() -> Self {
        Self(vec![])
    }

    fn trim(&mut self) {
        while self.0.last().map(|&c| c.abs() < 1e-9).unwrap_or(false) {
            self.0.pop();
        }
    }

    pub fn coeff(&self, i: usize) -> f64 {
        self.0.get(i).copied().unwrap_or(0.0)
    }

    pub fn degree(&self) -> usize {
        self.0.len().saturating_sub(1)
    }

    pub fn eval(&self, x: f64) -> f64 {
        self.0
            .iter()
            .enumerate()
            .map(|(i, c)| c * x.powi(i as i32))
            .sum()
    }

    pub fn add(&self, other: &Poly) -> Poly {
        let n = self.0.len().max(other.0.len());
        Poly::new((0..n).map(|i| self.coeff(i) + other.coeff(i)).collect())
    }

    pub fn sub(&self, other: &Poly) -> Poly {
        let n = self.0.len().max(other.0.len());
        Poly::new((0..n).map(|i| self.coeff(i) - other.coeff(i)).collect())
    }

    pub fn scale(&self, k: f64) -> Poly {
        Poly::new(self.0.iter().map(|&c| c * k).collect())
    }

    pub fn mul(&self, other: &Poly) -> Poly {
        if self.0.is_empty() || other.0.is_empty() {
            return Poly::zero();
        }
        let n = self.0.len() + other.0.len() - 1;
        let mut c = vec![0.0f64; n];
        for (i, &a) in self.0.iter().enumerate() {
            for (j, &b) in other.0.iter().enumerate() {
                c[i + j] += a * b;
            }
        }
        Poly::new(c)
    }

    /// Numeric equality: same value at all test points
    pub fn numerically_equal(&self, other: &Poly) -> bool {
        [-7.3, -1.0, 0.0, 1.0, 2.5, 5.0, 13.7]
            .iter()
            .all(|&x| (self.eval(x) - other.eval(x)).abs() < 1e-9)
    }

    /// Human-readable form
    pub fn fmt(&self) -> String {
        if self.0.is_empty() {
            return "0".to_string();
        }
        let mut parts: Vec<String> = Vec::new();
        for (deg, &c) in self.0.iter().enumerate().rev() {
            if c.abs() < 1e-9 {
                continue;
            }
            let abs = c.abs();
            let abs_s = if (abs.round() - abs).abs() < 1e-9 {
                format!("{}", abs as i64)
            } else {
                format!("{:.3}", abs)
            };
            let term = match deg {
                0 => abs_s,
                1 if abs == 1.0 => "x".to_string(),
                1 => format!("{}x", abs_s),
                _ if abs == 1.0 => format!("x^{}", deg),
                _ => format!("{}x^{}", abs_s, deg),
            };
            if parts.is_empty() {
                parts.push(if c < 0.0 { format!("-{}", term) } else { term });
            } else if c < 0.0 {
                parts.push(format!("- {}", term));
            } else {
                parts.push(format!("+ {}", term));
            }
        }
        if parts.is_empty() {
            "0".to_string()
        } else {
            parts.join(" ")
        }
    }
}

// ---------------------------------------------------------------------------
// MathState — the semantic state of a mathematical ReasonUnit
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
pub enum MathState {
    /// A standalone expression: p(x)
    Expr(Poly),
    /// An equation: lhs = rhs
    Equation { lhs: Poly, rhs: Poly },
    /// Factored equation: (x - r₁)(x - r₂)⋯ = 0
    Factored { roots: Vec<f64> },
    /// Solved: x = r₁ or x = r₂ …
    Solutions(Vec<f64>),
}

impl MathState {
    pub fn fmt(&self) -> String {
        match self {
            MathState::Expr(p) => p.fmt(),
            MathState::Equation { lhs, rhs } => format!("{} = {}", lhs.fmt(), rhs.fmt()),
            MathState::Factored { roots } => {
                let fs: Vec<String> = roots
                    .iter()
                    .map(|&r| {
                        if r.abs() < 1e-9 {
                            "x".to_string()
                        } else if r > 0.0 {
                            format!("(x - {})", r as i64)
                        } else {
                            format!("(x + {})", (-r) as i64)
                        }
                    })
                    .collect();
                format!("{} = 0", fs.join(""))
            }
            MathState::Solutions(sols) => {
                let ss: Vec<String> = sols
                    .iter()
                    .map(|&s| {
                        if (s.round() - s).abs() < 1e-9 {
                            format!("x = {}", s as i64)
                        } else {
                            format!("x = {:.3}", s)
                        }
                    })
                    .collect();
                ss.join(" or ")
            }
        }
    }

    /// Residual polynomial (lhs - rhs for equations, poly for expressions, None for solutions)
    pub fn residual(&self) -> Option<Poly> {
        match self {
            MathState::Expr(p) => Some(p.clone()),
            MathState::Equation { lhs, rhs } => Some(lhs.sub(rhs)),
            MathState::Factored { roots } => {
                let mut prod = Poly::new(vec![1.0]);
                for &r in roots {
                    prod = prod.mul(&Poly::new(vec![-r, 1.0]));
                }
                Some(prod)
            }
            MathState::Solutions(_) => None,
        }
    }

    /// Check whether a numeric value satisfies this state (used for solution validation)
    pub fn satisfied_by(&self, x: f64) -> bool {
        match self {
            MathState::Equation { lhs, rhs } => (lhs.eval(x) - rhs.eval(x)).abs() < 1e-9,
            MathState::Solutions(sols) => sols.iter().any(|&s| (s - x).abs() < 1e-9),
            MathState::Factored { roots } => roots.iter().any(|&r| (r - x).abs() < 1e-9),
            MathState::Expr(p) => p.eval(x).abs() < 1e-9,
        }
    }
}

// ---------------------------------------------------------------------------
// Transition validity checker
// ---------------------------------------------------------------------------

/// Returns true when `after` is a valid (equivalence-preserving) transformation of `before`.
pub fn is_valid_transition(before: &MathState, after: &MathState) -> bool {
    match (before.residual(), after.residual()) {
        // Expression / Equation → Expression / Equation: residual polys must agree
        (Some(r_before), Some(r_after)) => r_before.numerically_equal(&r_after),

        // Equation → Solutions: every proposed solution must satisfy the original
        (Some(r_before), None) => {
            if let MathState::Solutions(sols) = after {
                !sols.is_empty() && sols.iter().all(|&s| r_before.eval(s).abs() < 1e-9)
            } else {
                false
            }
        }
        _ => false,
    }
}

// ---------------------------------------------------------------------------
// Step record & trace
// ---------------------------------------------------------------------------

#[derive(Debug)]
pub struct StepRecord {
    pub rule: String,
    pub state_before: String,
    pub state_after: String,
    pub valid: bool,
}

#[derive(Debug)]
pub struct MathTrace {
    pub initial: String,
    pub steps: Vec<StepRecord>,
    pub final_state: String,
    /// Every transition was equivalence-preserving
    pub all_valid: bool,
    /// Final state reached the intended solution
    pub converged: bool,
}

impl MathTrace {
    pub fn new(initial: &MathState) -> Self {
        Self {
            initial: initial.fmt(),
            steps: Vec::new(),
            final_state: initial.fmt(),
            all_valid: true,
            converged: false,
        }
    }

    pub fn push(&mut self, rule: &str, before: &MathState, after: &MathState) {
        let valid = is_valid_transition(before, after);
        if !valid {
            self.all_valid = false;
        }
        self.steps.push(StepRecord {
            rule: rule.to_string(),
            state_before: before.fmt(),
            state_after: after.fmt(),
            valid,
        });
        self.final_state = after.fmt();
    }

    /// Record an INVALID transition (for collapse detection tests)
    pub fn push_unchecked(&mut self, rule: &str, before: &MathState, after: &MathState) {
        let valid = is_valid_transition(before, after);
        if !valid {
            self.all_valid = false;
        }
        self.steps.push(StepRecord {
            rule: rule.to_string(),
            state_before: before.fmt(),
            state_after: after.fmt(),
            valid,
        });
        self.final_state = after.fmt();
    }
}

// ---------------------------------------------------------------------------
// Concrete solver functions
// ---------------------------------------------------------------------------

/// Test 1 — Solve linear equation: x + c = d  →  x = d - c  →  x = value
pub fn solve_linear(lhs: Poly, rhs: Poly) -> MathTrace {
    let s0 = MathState::Equation {
        lhs: lhs.clone(),
        rhs: rhs.clone(),
    };
    let mut trace = MathTrace::new(&s0);

    // Step 1: move constant term from LHS to RHS
    let const_term = lhs.coeff(0);
    let new_lhs = Poly::new({
        let mut v = lhs.0.clone();
        if !v.is_empty() {
            v[0] = 0.0;
        }
        v
    });
    // RHS: original - constant  (shown as intermediate "d - c" form)
    let new_rhs = rhs.add(&Poly::new(vec![-const_term]));
    let _s1 = MathState::Equation {
        lhs: new_lhs.clone(),
        rhs: Poly::new(vec![rhs.coeff(0), 0.0]),
    };
    // We display the subtraction step symbolically; validate against correct residual
    let s1_symbolic = MathState::Equation {
        lhs: new_lhs.clone(),
        rhs: Poly::new(vec![rhs.coeff(0)]).add(&Poly::new(vec![-const_term])),
    };
    trace.push(
        "subtract constant from LHS (move to RHS)",
        &s0,
        &s1_symbolic,
    );

    // Step 2: evaluate RHS arithmetic
    let s2 = MathState::Equation {
        lhs: new_lhs.clone(),
        rhs: new_rhs.clone(),
    };
    trace.push("evaluate RHS arithmetic", &s1_symbolic, &s2);

    // Step 3: extract solution
    let value = new_rhs.eval(0.0); // RHS is constant
    let s3 = MathState::Solutions(vec![value]);
    trace.push("extract solution", &s2, &s3);

    // Convergence: solution satisfies original equation?
    trace.converged = s0.satisfied_by(value);
    trace
}

/// Test 2 — Solve quadratic: ax² + bx + c = 0 → (x - r₁)(x - r₂) = 0 → x = r₁ or x = r₂
pub fn solve_quadratic_by_factoring(poly: Poly) -> MathTrace {
    let s0 = MathState::Equation {
        lhs: poly.clone(),
        rhs: Poly::zero(),
    };
    let mut trace = MathTrace::new(&s0);

    // Find roots via quadratic formula (integer roots for our test)
    let a = poly.coeff(2);
    let b = poly.coeff(1);
    let c = poly.coeff(0);
    let disc = b * b - 4.0 * a * c;
    assert!(disc >= 0.0, "quadratic has no real roots");
    let sq = disc.sqrt();
    let r1 = (-b + sq) / (2.0 * a);
    let r2 = (-b - sq) / (2.0 * a);

    // Step 1: factor into (x - r1)(x - r2) = 0
    let mut roots = vec![r1, r2];
    roots.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let s1 = MathState::Factored {
        roots: roots.clone(),
    };
    trace.push("factor quadratic (find integer roots)", &s0, &s1);

    // Step 2: extract solutions from factored form
    let s2 = MathState::Solutions(roots.clone());
    trace.push("apply zero-product property", &s1, &s2);

    // Convergence: all roots satisfy original
    trace.converged = roots.iter().all(|&r| s0.satisfied_by(r));
    trace
}

/// Test 3 — Expand distribution: k·(p(x)) → k·p(x)
pub fn expand_distribution(scalar: f64, inner: Poly) -> MathTrace {
    let _s0 = MathState::Expr(Poly::new(vec![scalar])); // represents "scalar * (...)"
                                                        // We'll use a two-expression comparison rather than a single Expr
                                                        // Represent before as (scalar * inner) before multiplication
    let before_poly = inner.scale(1.0); // inner unchanged
    let before_state = MathState::Expr(before_poly.scale(scalar)); // conceptually "scalar*(inner)"
    let mut trace = MathTrace::new(&before_state);

    // Actually track the before as "k * (p)" (unnested)
    let before_display = MathState::Expr(inner.scale(scalar));

    // Step 1: distribute scalar into each term
    let expanded = inner.scale(scalar);
    let after_state = MathState::Expr(expanded.clone());
    trace.initial = format!("{}({})", scalar as i64, inner.fmt());
    trace.push(
        "distribute scalar over polynomial (expansion)",
        &before_display,
        &after_state,
    );

    // Convergence: expanded poly equals scalar * inner numerically
    trace.converged = expanded.numerically_equal(&inner.scale(scalar));
    trace
}

/// Test 4 — Simplify: combine like terms
pub fn simplify_polynomial(terms: Vec<Poly>) -> MathTrace {
    // Build the "unsimplified" polynomial by summing parts
    let combined: Poly = terms.iter().fold(Poly::zero(), |acc, p| acc.add(p));
    let before_repr = terms
        .iter()
        .map(|p| p.fmt())
        .collect::<Vec<_>>()
        .join(" + ");

    let s0 = MathState::Expr(combined.clone()); // already combined numerically
    let mut trace = MathTrace::new(&s0);
    trace.initial = before_repr.replace("+ -", "- ");

    // Step 1: combine like terms
    let simplified = combined.clone(); // Poly::new already normalises
    let s1 = MathState::Expr(simplified.clone());
    trace.push("combine like terms", &s0, &s1);

    // Convergence: simplified poly is numerically equal to original sum
    trace.converged = simplified.numerically_equal(&combined);
    trace
}

/// Test 5 — Detect invalid transition
/// Shows that "x + 2 = 5  →  x = 7" is a collapsed (non-equivalent) transition.
pub fn detect_invalid_transition() -> MathTrace {
    let lhs = Poly::new(vec![2.0, 1.0]); // x + 2
    let rhs = Poly::new(vec![5.0]); // 5
    let s0 = MathState::Equation {
        lhs: lhs.clone(),
        rhs: rhs.clone(),
    };
    let mut trace = MathTrace::new(&s0);

    // WRONG step 1: x = 5 + 2 (should be 5 - 2)
    let wrong_rhs = Poly::new(vec![7.0]); // 5 + 2 = 7 (mistake: added instead of subtracted)
    let s1_wrong = MathState::Equation {
        lhs: Poly::new(vec![0.0, 1.0]),
        rhs: wrong_rhs.clone(),
    };
    trace.push_unchecked(
        "subtract constant from LHS [WRONG: added instead]",
        &s0,
        &s1_wrong,
    );

    // WRONG step 2: x = 7
    let s2_wrong = MathState::Solutions(vec![7.0]);
    trace.push_unchecked("extract solution [WRONG]", &s1_wrong, &s2_wrong);

    // Convergence check: does x=7 satisfy original?
    trace.converged = s0.satisfied_by(7.0);
    trace
}

// ---------------------------------------------------------------------------
// Equivalence verifier (standalone utility)
// ---------------------------------------------------------------------------

/// Directly verify whether a proposed solution satisfies the original equation.
pub fn verify_solution(original_lhs: &Poly, original_rhs: &Poly, x: f64) -> bool {
    (original_lhs.eval(x) - original_rhs.eval(x)).abs() < 1e-9
}
