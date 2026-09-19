//! Lazy / symbolic candidate space (spec
//! `docs/specifications/ReasonScript_Lazy_Symbolic_Candidate_Space_v0_1.md`).
//!
//! A `CandidateSpace` is a domain (`[lower, upper]`), a generation rule, and
//! an ordered conjunction of symbolic constraints over a single `i64`
//! candidate value. Candidates are produced one at a time by
//! `generate_next` and checked against the constraints at generation time;
//! nothing is materialized unless the program asks for it. Bound
//! constraints (`value < k`, ...) fold into the domain, equality and
//! modulo constraints are stored and evaluated per candidate, and
//! `&&`/`||`/`!` trees are stored as one symbolic constraint. Allocation is
//! O(number of constraints), never O(number of candidates).
//!
//! This module is pure data: the VM (`vm.rs`) owns the generation loop so
//! that execution budgets and runtime counters stay in one place.

use std::fmt;
use std::rc::Rc;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Generator {
    /// Every integer in the domain.
    Range,
    /// `6k - 1` and `6k + 1` (residues 1 and 5 modulo 6) in the domain.
    Wheel6,
}

impl Generator {
    pub fn name(self) -> &'static str {
        match self {
            Generator::Range => "range",
            Generator::Wheel6 => "wheel6",
        }
    }

    /// Number of generator values in `[first, last]` (0 when empty).
    pub fn count_in(self, first: i64, last: i64) -> u64 {
        if first > last {
            return 0;
        }
        match self {
            Generator::Range => (last as i128 - first as i128 + 1) as u64,
            Generator::Wheel6 => residue_count(first, last, 1, 6) + residue_count(first, last, 5, 6),
        }
    }

    fn base_fused(self) -> FusedConstraintSet {
        match self {
            Generator::Range => FusedConstraintSet { modulus: 1, residues: Rc::new(vec![0]) },
            Generator::Wheel6 => FusedConstraintSet { modulus: 6, residues: Rc::new(vec![1, 5]) },
        }
    }
}

/// Integers `v` in `[first, last]` with `v == residue (mod modulus)`, for any sign.
fn residue_count(first: i64, last: i64, residue: i64, modulus: i64) -> u64 {
    let last = last as i128 - residue as i128;
    let before = first as i128 - 1 - residue as i128;
    (last.div_euclid(modulus as i128) - before.div_euclid(modulus as i128)) as u64
}

/// `gcd`/`lcm` on `i64`, with `lcm` overflow-checked via an `i128`
/// intermediate (spec `ReasonScript_Constraint_Fusion_v0_1` section 66):
/// `None` on overflow, never a panic.
fn gcd(a: i64, b: i64) -> i64 {
    let (mut a, mut b) = (a.abs(), b.abs());
    while b != 0 {
        (a, b) = (b, a % b);
    }
    a
}

fn checked_lcm(a: i64, b: i64) -> Option<i64> {
    let g = gcd(a, b);
    if g == 0 {
        return None;
    }
    let value = (a as i128 / g as i128) * b as i128;
    i64::try_from(value).ok()
}

/// Trial division up to `isqrt(n)` -- cheap because a fusible modulus is
/// always small (bounded by `FusionBudget::max_modulus`, spec section 23).
fn is_small_prime(n: i64) -> bool {
    if n < 2 {
        return false;
    }
    if n % 2 == 0 {
        return n == 2;
    }
    let mut d = 3i64;
    while d.saturating_mul(d) <= n {
        if n % d == 0 {
            return false;
        }
        d += 2;
    }
    true
}

/// Budget guarding how far Constraint Fusion (`ReasonScript_Constraint_Fusion_v0_1`
/// section 22-24) may grow the fused modulus. `max_residue_count` guards
/// generator-rebuild cost independently of `max_modulus` (a modulus near the
/// cap with almost every residue still valid would otherwise still rebuild
/// a near-`max_modulus`-sized vector on every fusion).
#[derive(Clone, Copy, Debug)]
pub struct FusionBudget {
    pub max_modulus: i64,
    pub max_residue_count: usize,
}

impl Default for FusionBudget {
    fn default() -> Self {
        // 2 x 3 x 5 x 7 x 11 x 13 (spec section 23).
        FusionBudget { max_modulus: 30_030, max_residue_count: 30_030 }
    }
}

/// A generator specialized by folding `NotDivisibleBy(p)` constraints
/// directly into its stepping rule: "every integer `v` in the domain with
/// `v mod modulus` in `residues`". Wraps the base `Generator` (`Range` /
/// `Wheel6`) as its own fused set (`modulus=1,residues=[0]` /
/// `modulus=6,residues=[1,5]`) so stepping is driven by one mechanism
/// whether or not any extra constraint has been fused in -- fusion-disabled
/// behavior is byte-identical to the pre-fusion `Generator::next_after`
/// (verified in `fused_set_matches_generator_stepping_exactly`).
#[derive(Clone, Debug)]
pub struct FusedConstraintSet {
    pub modulus: i64,
    /// Sorted ascending, each in `[0, modulus)`. `Rc`-shared so cloning a
    /// `CandidateSpace` (on every constraint addition -- a persistent,
    /// not in-place, data structure) is O(1) regardless of how large the
    /// fused modulus has grown, instead of O(residue count) -- discovered
    /// as a real regression while benchmarking Constraint Fusion: without
    /// this, a `relation.filter` call made AFTER the modulus neared
    /// `FusionBudget::max_modulus` (up to 30,030/5,760 residues) paid a
    /// full residue-vector clone even when it only fell back to a
    /// residual constraint and changed nothing about the fused set.
    pub residues: Rc<Vec<i64>>,
}

pub enum FuseOutcome {
    /// `p` already excluded (a duplicate `exclude_multiples_of` or a prime
    /// the base generator already excludes, e.g. wheel-6 and `p=3`).
    AlreadyExcluded,
    Fused { modulus: i64, residue_count: usize },
    /// The resulting modulus or residue count would exceed the budget, or
    /// the LCM would overflow `i64`; the caller falls back to a residual
    /// constraint (spec section 26 -- fallback is not an error).
    BudgetExceeded,
}

impl FusedConstraintSet {
    /// Smallest fused-valid value strictly greater than `after`, via one
    /// binary search (O(log R): spec section 27/28) -- never O(modulus).
    #[inline]
    fn next_after(&self, after: i64) -> i64 {
        let start = after.saturating_add(1);
        let r = start.rem_euclid(self.modulus);
        match self.residues.binary_search(&r) {
            Ok(index) => start - r + self.residues[index],
            Err(index) if index < self.residues.len() => start - r + self.residues[index],
            Err(_) => start - r + self.modulus + self.residues[0],
        }
    }

    fn count_in(&self, first: i64, last: i64) -> u64 {
        self.residues
            .iter()
            .map(|residue| residue_count(first, last, *residue, self.modulus))
            .sum()
    }

    /// O(1) pre-check: would `try_fuse(p, budget)` change the fused set at
    /// all (`true`), or is it certain to hit `BudgetExceeded` (`false`)?
    /// Never touches `residues`, so the caller can skip the O(residue
    /// count) `unvisited_count` bookkeeping entirely for a call that is
    /// going to fall back regardless -- the common case once a program has
    /// fused as many primes as the budget admits and moves on to more
    /// (each new one is coprime to the capped modulus, so this is O(1) per
    /// such call, not O(residue count)). A `true` result does not
    /// guarantee `try_fuse` succeeds (the rare `p` divides `modulus`
    /// dedup-vs-new-exclusion case still needs the real O(R) check), only
    /// that it is not a guaranteed no-op fallback.
    fn would_fuse(&self, p: i64, budget: &FusionBudget) -> bool {
        if self.modulus % p == 0 {
            return true;
        }
        let Some(new_modulus) = checked_lcm(self.modulus, p) else {
            return false;
        };
        if new_modulus > budget.max_modulus {
            return false;
        }
        let scale = (new_modulus / self.modulus) as usize;
        self.residues.len().saturating_mul(scale) <= budget.max_residue_count
    }

    /// Attempts to fold `NotDivisibleBy(p)` into this set (spec sections
    /// 12-13, 22, 66-67). `p` must already be verified `is_small_prime` by
    /// the caller -- composite moduli are Class C (residual) by design
    /// (section 21) and never reach here.
    fn try_fuse(&mut self, p: i64, budget: &FusionBudget) -> FuseOutcome {
        if self.modulus % p == 0 {
            let filtered: Vec<i64> = self.residues.iter().copied().filter(|r| r % p != 0).collect();
            if filtered.len() == self.residues.len() {
                return FuseOutcome::AlreadyExcluded;
            }
            self.residues = Rc::new(filtered);
            return FuseOutcome::Fused { modulus: self.modulus, residue_count: self.residues.len() };
        }
        let Some(new_modulus) = checked_lcm(self.modulus, p) else {
            return FuseOutcome::BudgetExceeded;
        };
        if new_modulus > budget.max_modulus {
            return FuseOutcome::BudgetExceeded;
        }
        let scale = (new_modulus / self.modulus) as usize;
        if self.residues.len().saturating_mul(scale) > budget.max_residue_count {
            return FuseOutcome::BudgetExceeded;
        }
        let mut expanded = Vec::with_capacity(self.residues.len() * scale);
        for &base in self.residues.iter() {
            let mut offset = 0i64;
            while offset < new_modulus {
                let candidate = base + offset;
                if candidate % p != 0 {
                    expanded.push(candidate);
                }
                offset += self.modulus;
            }
        }
        expanded.sort_unstable();
        self.modulus = new_modulus;
        self.residues = Rc::new(expanded);
        FuseOutcome::Fused { modulus: self.modulus, residue_count: self.residues.len() }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CmpOp {
    Eq,
    Ne,
    Lt,
    Le,
    Gt,
    Ge,
}

impl CmpOp {
    /// IR comparison operator names (`Expr::Comparison { operator }`).
    pub fn parse(operator: &str) -> Option<Self> {
        Some(match operator {
            "Equal" => CmpOp::Eq,
            "NotEqual" => CmpOp::Ne,
            "LessThan" => CmpOp::Lt,
            "LessThanOrEqual" => CmpOp::Le,
            "GreaterThan" => CmpOp::Gt,
            "GreaterThanOrEqual" => CmpOp::Ge,
            _ => return None,
        })
    }

    /// `a <op> b` written as `b <flipped> a`.
    pub fn flip(self) -> Self {
        match self {
            CmpOp::Lt => CmpOp::Gt,
            CmpOp::Le => CmpOp::Ge,
            CmpOp::Gt => CmpOp::Lt,
            CmpOp::Ge => CmpOp::Le,
            same => same,
        }
    }

    fn negate(self) -> Self {
        match self {
            CmpOp::Eq => CmpOp::Ne,
            CmpOp::Ne => CmpOp::Eq,
            CmpOp::Lt => CmpOp::Ge,
            CmpOp::Le => CmpOp::Gt,
            CmpOp::Gt => CmpOp::Le,
            CmpOp::Ge => CmpOp::Lt,
        }
    }

    #[inline]
    fn holds(self, left: i64, right: i64) -> bool {
        match self {
            CmpOp::Eq => left == right,
            CmpOp::Ne => left != right,
            CmpOp::Lt => left < right,
            CmpOp::Le => left <= right,
            CmpOp::Gt => left > right,
            CmpOp::Ge => left >= right,
        }
    }

    fn symbol(self) -> &'static str {
        match self {
            CmpOp::Eq => "==",
            CmpOp::Ne => "!=",
            CmpOp::Lt => "<",
            CmpOp::Le => "<=",
            CmpOp::Gt => ">",
            CmpOp::Ge => ">=",
        }
    }
}

/// Python floor modulo (`python_mod_i64` in `vm.rs`), duplicated here so
/// this module stays free of VM dependencies.
#[inline]
fn floor_mod(a: i64, b: i64) -> i64 {
    let r = a % b;
    if r != 0 && ((r < 0) != (b < 0)) {
        r + b
    } else {
        r
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Constraint {
    /// `value <op> k`. Only `==`/`!=` are ever stored; the ordering forms
    /// fold into the domain bounds in `CandidateSpace::add`.
    Compare { op: CmpOp, k: i64 },
    /// `(value % m) <op> r` with `m != 0`.
    Modulo { m: i64, op: CmpOp, r: i64 },
    And(Box<Constraint>, Box<Constraint>),
    Or(Box<Constraint>, Box<Constraint>),
    Not(Box<Constraint>),
}

impl Constraint {
    /// Canonical order rank (spec section 31): bounds are folded (rank 0),
    /// then equality, then modulo, then logical trees.
    fn rank(&self) -> u8 {
        match self {
            Constraint::Compare { .. } => 1,
            Constraint::Modulo { .. } => 2,
            _ => 3,
        }
    }

    /// `!c` with leaf comparisons negated in place so `!(v % f == 0)` and
    /// `v % f != 0` canonicalize to the same constraint.
    pub fn negated(self) -> Constraint {
        match self {
            Constraint::Compare { op, k } => Constraint::Compare { op: op.negate(), k },
            Constraint::Modulo { m, op, r } => Constraint::Modulo {
                m,
                op: op.negate(),
                r,
            },
            Constraint::Not(inner) => *inner,
            tree => Constraint::Not(Box::new(tree)),
        }
    }

    /// Top-level conjuncts, so `a && b` is added as two constraints.
    pub fn conjuncts(self) -> Vec<Constraint> {
        match self {
            Constraint::And(left, right) => {
                let mut items = left.conjuncts();
                items.extend(right.conjuncts());
                items
            }
            leaf => vec![leaf],
        }
    }

    /// Evaluates against `value`; `evals` counts leaf evaluations.
    #[inline]
    pub fn accepts(&self, value: i64, evals: &mut u64) -> bool {
        match self {
            Constraint::Compare { op, k } => {
                *evals += 1;
                op.holds(value, *k)
            }
            Constraint::Modulo { m, op, r } => {
                *evals += 1;
                op.holds(floor_mod(value, *m), *r)
            }
            Constraint::And(left, right) => {
                left.accepts(value, evals) && right.accepts(value, evals)
            }
            Constraint::Or(left, right) => {
                left.accepts(value, evals) || right.accepts(value, evals)
            }
            Constraint::Not(inner) => !inner.accepts(value, evals),
        }
    }
}

impl fmt::Display for Constraint {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Constraint::Compare { op, k } => write!(f, "value {} {k}", op.symbol()),
            Constraint::Modulo { m, op, r } => write!(f, "value % {m} {} {r}", op.symbol()),
            Constraint::And(left, right) => write!(f, "({left} && {right})"),
            Constraint::Or(left, right) => write!(f, "({left} || {right})"),
            Constraint::Not(inner) => write!(f, "!({inner})"),
        }
    }
}

/// Outcome of `CandidateSpace::add`.
#[derive(Debug, PartialEq, Eq)]
pub enum Added {
    /// A bound folded into the domain; `excluded` is the exact number of
    /// generator values it removed from the unvisited range (exact only
    /// while no residual constraint exists -- the caller decides).
    Folded { excluded: u64 },
    /// `NotDivisibleBy(p)` folded directly into the generator's stepping
    /// rule (Constraint Fusion v0.1); no residual constraint was added.
    /// `excluded` is exact, like `Folded` (spec section 29).
    Fused { modulus: i64, residue_count: usize, excluded: u64 },
    /// Went to `residual_constraints` as before. `fusion_fallback` is true
    /// only when fusion was attempted (a prime `NotDivisibleBy`, fusion
    /// enabled) and rejected by the budget -- not merely ineligible (a
    /// non-prime modulus, or fusion disabled), which is ordinary Class C
    /// classification, not a fallback.
    Stored { fusion_fallback: bool },
    Duplicate,
}

#[derive(Clone, Debug)]
pub struct CandidateSpace {
    pub lower: i64,
    pub upper: i64,
    pub generator: Generator,
    /// Constraints folded into the generator's stepping rule (Constraint
    /// Fusion v0.1): `NotDivisibleBy(p)` for each `p` in `fused_primes`.
    /// Generation (`generate_next`/`unvisited_count`) is always driven by
    /// this set -- when nothing has been fused it exactly mirrors the base
    /// `generator`, so fusion-disabled behavior is unchanged (spec
    /// `ReasonScript_Constraint_Fusion_v0_1` section 55).
    pub fused: FusedConstraintSet,
    pub fused_primes: Vec<i64>,
    /// Everything not fused: equality, ordering-already-folded markers
    /// never appear here, composite-modulus and logical-tree constraints
    /// do. Evaluated per generated candidate, in canonical order.
    pub residual_constraints: Vec<Constraint>,
    /// Last generator value examined; `lower - 1` before the first
    /// `generate_next`. Never moves backwards except through `reset`.
    pub cursor: i64,
    /// A generated-and-accepted candidate not yet handed out (the
    /// `is_exhausted` lookahead). Always equal to `cursor` when present.
    pub peeked: Option<i64>,
    pub exhausted_reported: bool,
}

impl CandidateSpace {
    pub fn new(generator: Generator, lower: i64, upper: i64) -> Self {
        CandidateSpace {
            lower,
            upper,
            generator,
            fused: generator.base_fused(),
            fused_primes: Vec::new(),
            residual_constraints: Vec::new(),
            cursor: lower.saturating_sub(1),
            peeked: None,
            exhausted_reported: false,
        }
    }

    /// Generator values in the initial domain (before any constraint).
    pub fn estimated_size(&self) -> u64 {
        self.generator.count_in(self.lower, self.upper)
    }

    /// Last generator value considered visited, honouring a raised lower
    /// bound and an unreturned lookahead value.
    fn visited_through(&self) -> i64 {
        let cursor = if self.peeked.is_some() {
            self.cursor - 1
        } else {
            self.cursor
        };
        cursor.max(self.lower.saturating_sub(1))
    }

    /// Generator values the space can still produce, honouring whatever
    /// has been fused in so far but ignoring `residual_constraints` (exact
    /// when `residual_constraints` is empty).
    pub fn unvisited_count(&self) -> u64 {
        let from = self.visited_through();
        if from >= self.upper {
            0
        } else {
            self.fused.count_in(from + 1, self.upper)
        }
    }

    /// Next fused-valid value in the domain, advancing the cursor. `None`
    /// once the domain is used up (the cursor then stays at `upper`).
    #[inline]
    pub fn generate_next(&mut self) -> Option<i64> {
        let after = self.cursor.max(self.lower.saturating_sub(1));
        if after >= self.upper {
            self.cursor = self.upper.max(self.cursor);
            return None;
        }
        let value = self.fused.next_after(after);
        if value > self.upper {
            self.cursor = self.upper;
            return None;
        }
        self.cursor = value;
        Some(value)
    }

    #[inline]
    pub fn accepts(&self, value: i64, evals: &mut u64) -> bool {
        self.residual_constraints
            .iter()
            .all(|constraint| constraint.accepts(value, evals))
    }

    /// Returns the lookahead value to the unvisited range (used before a
    /// constraint changes what is acceptable).
    pub fn unpeek(&mut self) {
        if self.peeked.take().is_some() {
            self.cursor -= 1;
        }
    }

    pub fn reset_cursor(&mut self) {
        self.cursor = self.lower.saturating_sub(1);
        self.peeked = None;
        self.exhausted_reported = false;
    }

    /// Adds one constraint: bounds fold into the domain; a prime
    /// `NotDivisibleBy(p)` folds into the generator when `fusion_enabled`
    /// and the budget allows it (Constraint Fusion v0.1); everything else
    /// is deduplicated and inserted into `residual_constraints` in
    /// canonical order. Never moves the cursor backwards (fusion never
    /// touches `cursor`/`peeked`; the caller `unpeek`s first as before).
    pub fn add(&mut self, constraint: Constraint, fusion_enabled: bool) -> Added {
        if let Constraint::Compare { op, k } = constraint {
            if !matches!(op, CmpOp::Eq | CmpOp::Ne) {
                let before = self.unvisited_count();
                match op {
                    CmpOp::Gt => self.lower = self.lower.max(k.saturating_add(1)),
                    CmpOp::Ge => self.lower = self.lower.max(k),
                    CmpOp::Lt => self.upper = self.upper.min(k.saturating_sub(1)),
                    CmpOp::Le => self.upper = self.upper.min(k),
                    CmpOp::Eq | CmpOp::Ne => unreachable!(),
                }
                let after = self.unvisited_count();
                return Added::Folded {
                    excluded: before - after,
                };
            }
        }
        let mut fallback = false;
        if fusion_enabled {
            if let Constraint::Modulo { m: p, op: CmpOp::Ne, r: 0 } = constraint {
                if is_small_prime(p) {
                    let budget = FusionBudget::default();
                    if self.fused.would_fuse(p, &budget) {
                        // `unvisited_count` is O(residue count) -- paid
                        // only when `try_fuse` might actually change the
                        // fused set, never for a call `would_fuse` already
                        // knows is a guaranteed fallback. Discovered as a
                        // real regression while benchmarking: computing it
                        // unconditionally for every prime-modulo call, even
                        // ones a full modulus had already made no-ops, made
                        // Fusion slower than no fusion at all once a
                        // program kept excluding more primes past the
                        // budget cap (each such call used to cost O(final
                        // residue count) for nothing).
                        let before = self.unvisited_count();
                        match self.fused.try_fuse(p, &budget) {
                            FuseOutcome::AlreadyExcluded => return Added::Duplicate,
                            FuseOutcome::Fused { modulus, residue_count } => {
                                self.fused_primes.push(p);
                                let excluded = before - self.unvisited_count();
                                return Added::Fused { modulus, residue_count, excluded };
                            }
                            FuseOutcome::BudgetExceeded => fallback = true,
                        }
                    } else {
                        fallback = true;
                    }
                }
            }
        }
        if self.residual_constraints.contains(&constraint) {
            return Added::Duplicate;
        }
        let rank = constraint.rank();
        let position = self
            .residual_constraints
            .iter()
            .rposition(|existing| existing.rank() <= rank)
            .map_or(0, |index| index + 1);
        self.residual_constraints.insert(position, constraint);
        Added::Stored { fusion_fallback: fallback }
    }

    pub fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "candidate_space": {
                "generator": self.generator.name(),
                "lower": self.lower,
                "upper": self.upper,
                "cursor": self.cursor,
                "fused_modulus": self.fused.modulus,
                "fused_residue_count": self.fused.residues.len(),
                "fused_primes": self.fused_primes,
                "residual_constraints": self.residual_constraints.iter().map(ToString::to_string).collect::<Vec<_>>(),
            }
        })
    }
}

/// Exact `floor(sqrt(n))` for `n >= 0`.
pub fn isqrt(n: i64) -> i64 {
    let mut root = (n as f64).sqrt() as i64;
    let square = |r: i64| (r as i128) * (r as i128);
    while square(root) > n as i128 {
        root -= 1;
    }
    while square(root + 1) <= n as i128 {
        root += 1;
    }
    root
}

#[cfg(test)]
mod tests {
    use super::*;

    fn drain(space: &mut CandidateSpace) -> Vec<i64> {
        let mut out = Vec::new();
        let mut evals = 0;
        while let Some(value) = space.generate_next() {
            if space.accepts(value, &mut evals) {
                out.push(value);
            }
        }
        out
    }

    fn not_divisible_by(p: i64) -> Constraint {
        Constraint::Modulo { m: p, op: CmpOp::Ne, r: 0 }
    }

    #[test]
    fn wheel6_generates_6k_plus_minus_1_and_counts_exactly() {
        let mut space = CandidateSpace::new(Generator::Wheel6, 5, 40);
        assert_eq!(space.estimated_size(), 12);
        assert_eq!(drain(&mut space), vec![5, 7, 11, 13, 17, 19, 23, 25, 29, 31, 35, 37]);
        assert_eq!(space.unvisited_count(), 0);
        assert_eq!(Generator::Wheel6.count_in(1, 1), 1);
        assert_eq!(Generator::Wheel6.count_in(2, 4), 0);
        assert_eq!(Generator::Wheel6.count_in(-7, 7), 6); // -7, -5, -1, 1, 5, 7
    }

    #[test]
    fn modulo_constraints_dedupe_order_and_never_reset_the_cursor_fusion_disabled() {
        let mut space = CandidateSpace::new(Generator::Wheel6, 5, 60);
        assert_eq!(space.generate_next(), Some(5));
        assert_eq!(
            space.add(not_divisible_by(5), false),
            Added::Stored { fusion_fallback: false }
        );
        assert_eq!(space.add(not_divisible_by(5), false), Added::Duplicate);
        assert_eq!(
            space.add(Constraint::Compare { op: CmpOp::Ne, k: 13 }, false),
            Added::Stored { fusion_fallback: false }
        );
        // equality sorts before modulo regardless of insertion order
        assert!(matches!(space.residual_constraints[0], Constraint::Compare { .. }));
        assert_eq!(space.cursor, 5);
        assert_eq!(drain(&mut space), vec![7, 11, 17, 19, 23, 29, 31, 37, 41, 43, 47, 49, 53, 59]);
    }

    #[test]
    fn bounds_fold_and_report_exact_exclusions() {
        let mut space = CandidateSpace::new(Generator::Range, 1, 100);
        assert_eq!(space.generate_next(), Some(1));
        assert_eq!(
            space.add(Constraint::Compare { op: CmpOp::Gt, k: 90 }, false),
            Added::Folded { excluded: 89 }
        );
        assert_eq!(
            space.add(Constraint::Compare { op: CmpOp::Lt, k: 10 }, false),
            Added::Folded { excluded: 10 }
        );
        assert_eq!(space.unvisited_count(), 0);
        assert_eq!(space.generate_next(), None);
    }

    #[test]
    fn unpeek_puts_the_lookahead_back_without_revisiting_skips() {
        let mut space = CandidateSpace::new(Generator::Range, 1, 10);
        space.add(Constraint::Modulo { m: 2, op: CmpOp::Eq, r: 0 }, false);
        let mut evals = 0;
        // peek: 1 skipped, 2 accepted
        let mut found = None;
        while let Some(v) = space.generate_next() {
            if space.accepts(v, &mut evals) {
                found = Some(v);
                break;
            }
        }
        space.peeked = found;
        assert_eq!((space.cursor, space.peeked), (2, Some(2)));
        assert_eq!(space.unvisited_count(), 9);
        space.unpeek();
        assert_eq!((space.cursor, space.peeked), (1, None));
        assert_eq!(space.generate_next(), Some(2));
    }

    #[test]
    fn negation_and_conjunction_canonicalize() {
        let not_eq = Constraint::Modulo { m: 3, op: CmpOp::Eq, r: 0 }.negated();
        assert_eq!(not_eq, Constraint::Modulo { m: 3, op: CmpOp::Ne, r: 0 });
        let both = Constraint::And(
            Box::new(Constraint::Compare { op: CmpOp::Gt, k: 1 }),
            Box::new(Constraint::And(
                Box::new(not_eq.clone()),
                Box::new(Constraint::Compare { op: CmpOp::Ne, k: 7 }),
            )),
        );
        assert_eq!(both.conjuncts().len(), 3);
        assert_eq!(not_eq.to_string(), "value % 3 != 0");
    }

    // Constraint Fusion v0.1 tests (spec `ReasonScript_Constraint_Fusion_v0_1.md`
    // section 68).

    #[test]
    fn wheel6_plus_5_fuses_to_mod_30() {
        let mut space = CandidateSpace::new(Generator::Wheel6, 5, 100);
        assert_eq!(
            space.add(not_divisible_by(5), true),
            Added::Fused { modulus: 30, residue_count: 8, excluded: 7 }
        );
        assert_eq!(space.fused.modulus, 30);
        assert_eq!(*space.fused.residues, vec![1, 7, 11, 13, 17, 19, 23, 29]); // spec section 12
        assert!(space.residual_constraints.is_empty());
        assert_eq!(space.fused_primes, vec![5]);
    }

    #[test]
    fn wheel30_plus_7_fuses_to_mod_210() {
        let mut space = CandidateSpace::new(Generator::Wheel6, 5, 250);
        space.add(not_divisible_by(5), true);
        assert_eq!(
            space.add(not_divisible_by(7), true),
            Added::Fused { modulus: 210, residue_count: 48, excluded: 9 }
        );
        assert_eq!(space.fused.modulus, 210); // spec section 13
        for &r in space.fused.residues.iter() {
            assert_ne!(r % 5, 0);
            assert_ne!(r % 7, 0);
        }
    }

    #[test]
    fn fusion_is_order_invariant() {
        let mut a = CandidateSpace::new(Generator::Wheel6, 5, 250);
        a.add(not_divisible_by(5), true);
        a.add(not_divisible_by(7), true);
        let mut b = CandidateSpace::new(Generator::Wheel6, 5, 250);
        b.add(not_divisible_by(7), true);
        b.add(not_divisible_by(5), true);
        assert_eq!(a.fused.modulus, b.fused.modulus); // spec section 19
        assert_eq!(a.fused.residues, b.fused.residues);
        assert_eq!(drain(&mut a.clone()), drain(&mut b.clone()));
    }

    #[test]
    fn duplicate_fusion_is_a_noop() {
        let mut space = CandidateSpace::new(Generator::Wheel6, 5, 100);
        assert!(matches!(space.add(not_divisible_by(5), true), Added::Fused { .. }));
        assert_eq!(space.add(not_divisible_by(5), true), Added::Duplicate); // spec section 20
        // A prime the base generator already excludes is also a no-op.
        assert_eq!(space.add(not_divisible_by(3), true), Added::Duplicate);
    }

    #[test]
    fn cursor_never_moves_backwards_across_a_fusion() {
        let mut space = CandidateSpace::new(Generator::Wheel6, 5, 200);
        for _ in 0..3 {
            space.generate_next();
        } // cursor now at the 3rd wheel-6 value (11)
        let before = space.cursor;
        space.add(not_divisible_by(5), true); // spec section 17
        assert_eq!(space.cursor, before);
        assert!(space.generate_next().unwrap() > before);
    }

    #[test]
    fn overflow_and_budget_exceeded_fall_back_to_residual() {
        let mut budget_hit = CandidateSpace::new(Generator::Range, 1, 1_000_000);
        // 2*3*5*7*11*13 = 30030 (the default max_modulus); *17 would exceed it.
        for p in [2, 3, 5, 7, 11, 13] {
            assert!(matches!(budget_hit.add(not_divisible_by(p), true), Added::Fused { .. } | Added::Duplicate));
        }
        assert_eq!(budget_hit.fused.modulus, 30_030);
        assert_eq!(
            budget_hit.add(not_divisible_by(17), true),
            Added::Stored { fusion_fallback: true }
        ); // spec section 22-23, 26

        // A prime whose LCM with the current modulus would overflow i64
        // also falls back, never panics (spec section 66).
        let mut overflow = CandidateSpace::new(Generator::Range, 1, 100);
        overflow.fused.modulus = i64::MAX / 2; // simulate an already-huge modulus
        let huge_prime = 4_611_686_018_427_387_847i64; // prime, coprime to the modulus above
        assert_eq!(
            overflow.add(not_divisible_by(huge_prime), true),
            Added::Stored { fusion_fallback: true }
        );
    }

    #[test]
    fn composite_modulus_and_non_ne_zero_modulo_stay_residual_even_with_fusion_on() {
        let mut space = CandidateSpace::new(Generator::Range, 1, 100);
        assert_eq!(
            space.add(not_divisible_by(15), true), // composite: spec section 21
            Added::Stored { fusion_fallback: false }
        );
        assert_eq!(
            space.add(Constraint::Modulo { m: 5, op: CmpOp::Eq, r: 0 }, true), // not `!= 0`
            Added::Stored { fusion_fallback: false }
        );
        assert_eq!(space.fused.modulus, 1); // untouched
    }

    #[test]
    fn fusion_disabled_matches_pre_fusion_behavior_exactly() {
        let mut space = CandidateSpace::new(Generator::Wheel6, 5, 100);
        assert_eq!(
            space.add(not_divisible_by(5), false),
            Added::Stored { fusion_fallback: false }
        );
        assert_eq!(space.fused.modulus, 6); // spec section 55: never touched
        assert_eq!(space.residual_constraints.len(), 1);
    }

    #[test]
    fn fused_set_matches_generator_stepping_exactly() {
        // The generic FusedConstraintSet-driven stepping must reproduce
        // Generator::Wheel6's original hand-written stepping value for
        // value: every `after` in a wide range.
        let wheel = CandidateSpace::new(Generator::Wheel6, i64::MIN / 2, i64::MIN / 2).fused;
        let hand_written = |after: i64| -> i64 {
            let value = after.saturating_add(1);
            match value.rem_euclid(6) {
                1 | 5 => value,
                0 => value.saturating_add(1),
                residue => value.saturating_add(5 - residue),
            }
        };
        for after in -50..500i64 {
            assert_eq!(wheel.next_after(after), hand_written(after), "after={after}");
        }
    }

    #[test]
    fn isqrt_is_exact_around_perfect_squares() {
        for n in [0i64, 1, 2, 3, 4, 24, 25, 26, 1_000_003 * 1_000_033, i64::MAX] {
            let r = isqrt(n);
            assert!((r as i128) * (r as i128) <= n as i128);
            assert!(((r + 1) as i128) * ((r + 1) as i128) > n as i128, "{n}");
        }
    }
}
