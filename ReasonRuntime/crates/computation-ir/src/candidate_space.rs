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

    /// Smallest generator value strictly greater than `after`.
    fn next_after(self, after: i64) -> i64 {
        let value = after.saturating_add(1);
        match self {
            Generator::Range => value,
            Generator::Wheel6 => match value.rem_euclid(6) {
                1 | 5 => value,
                0 => value.saturating_add(1),
                residue => value.saturating_add(5 - residue),
            },
        }
    }

    /// Number of generator values in `[first, last]` (0 when empty).
    pub fn count_in(self, first: i64, last: i64) -> u64 {
        if first > last {
            return 0;
        }
        match self {
            Generator::Range => (last as i128 - first as i128 + 1) as u64,
            Generator::Wheel6 => residue_count(first, last, 1) + residue_count(first, last, 5),
        }
    }
}

/// Integers `v` in `[first, last]` with `v == residue (mod 6)`, for any sign.
fn residue_count(first: i64, last: i64, residue: i64) -> u64 {
    let last = last as i128 - residue as i128;
    let before = first as i128 - 1 - residue as i128;
    (last.div_euclid(6) - before.div_euclid(6)) as u64
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
    /// while no stored constraint exists -- the caller decides).
    Folded { excluded: u64 },
    Stored,
    Duplicate,
}

#[derive(Clone, Debug)]
pub struct CandidateSpace {
    pub lower: i64,
    pub upper: i64,
    pub generator: Generator,
    pub constraints: Vec<Constraint>,
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
            constraints: Vec::new(),
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

    /// Generator values the space can still produce, ignoring stored
    /// constraints (exact when `constraints` is empty).
    pub fn unvisited_count(&self) -> u64 {
        let from = self.visited_through();
        if from >= self.upper {
            0
        } else {
            self.generator.count_in(from + 1, self.upper)
        }
    }

    /// Next generator value in the domain, advancing the cursor. `None`
    /// once the domain is used up (the cursor then stays at `upper`).
    #[inline]
    pub fn generate_next(&mut self) -> Option<i64> {
        let after = self.cursor.max(self.lower.saturating_sub(1));
        if after >= self.upper {
            self.cursor = self.upper.max(self.cursor);
            return None;
        }
        let value = self.generator.next_after(after);
        if value > self.upper {
            self.cursor = self.upper;
            return None;
        }
        self.cursor = value;
        Some(value)
    }

    #[inline]
    pub fn accepts(&self, value: i64, evals: &mut u64) -> bool {
        self.constraints
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

    /// Adds one constraint: bounds fold into the domain, everything else is
    /// deduplicated and inserted in canonical order. Never moves the
    /// cursor backwards.
    pub fn add(&mut self, constraint: Constraint) -> Added {
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
        if self.constraints.contains(&constraint) {
            return Added::Duplicate;
        }
        let rank = constraint.rank();
        let position = self
            .constraints
            .iter()
            .rposition(|existing| existing.rank() <= rank)
            .map_or(0, |index| index + 1);
        self.constraints.insert(position, constraint);
        Added::Stored
    }

    pub fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "candidate_space": {
                "generator": self.generator.name(),
                "lower": self.lower,
                "upper": self.upper,
                "cursor": self.cursor,
                "constraints": self.constraints.iter().map(ToString::to_string).collect::<Vec<_>>(),
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
    fn modulo_constraints_dedupe_order_and_never_reset_the_cursor() {
        let mut space = CandidateSpace::new(Generator::Wheel6, 5, 60);
        assert_eq!(space.generate_next(), Some(5));
        assert_eq!(
            space.add(Constraint::Modulo { m: 5, op: CmpOp::Ne, r: 0 }),
            Added::Stored
        );
        assert_eq!(
            space.add(Constraint::Modulo { m: 5, op: CmpOp::Ne, r: 0 }),
            Added::Duplicate
        );
        assert_eq!(
            space.add(Constraint::Compare { op: CmpOp::Ne, k: 13 }),
            Added::Stored
        );
        // equality sorts before modulo regardless of insertion order
        assert!(matches!(space.constraints[0], Constraint::Compare { .. }));
        assert_eq!(space.cursor, 5);
        assert_eq!(drain(&mut space), vec![7, 11, 17, 19, 23, 29, 31, 37, 41, 43, 47, 49, 53, 59]);
    }

    #[test]
    fn bounds_fold_and_report_exact_exclusions() {
        let mut space = CandidateSpace::new(Generator::Range, 1, 100);
        assert_eq!(space.generate_next(), Some(1));
        assert_eq!(
            space.add(Constraint::Compare { op: CmpOp::Gt, k: 90 }),
            Added::Folded { excluded: 89 }
        );
        assert_eq!(
            space.add(Constraint::Compare { op: CmpOp::Lt, k: 10 }),
            Added::Folded { excluded: 10 }
        );
        assert_eq!(space.unvisited_count(), 0);
        assert_eq!(space.generate_next(), None);
    }

    #[test]
    fn unpeek_puts_the_lookahead_back_without_revisiting_skips() {
        let mut space = CandidateSpace::new(Generator::Range, 1, 10);
        space.add(Constraint::Modulo { m: 2, op: CmpOp::Eq, r: 0 });
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

    #[test]
    fn isqrt_is_exact_around_perfect_squares() {
        for n in [0i64, 1, 2, 3, 4, 24, 25, 26, 1_000_003 * 1_000_033, i64::MAX] {
            let r = isqrt(n);
            assert!((r as i128) * (r as i128) <= n as i128);
            assert!(((r + 1) as i128) * ((r + 1) as i128) > n as i128, "{n}");
        }
    }
}
