//! Model A for the Relation / State Runtime Experiment D (Rust stdlib only).
fn main() {
    let mut remaining: u64 = std::env::args().nth(1).unwrap().parse().unwrap();
    let mut factors = Vec::new();
    let mut tests = 0;
    let mut candidate = 2;
    while candidate * candidate <= remaining {
        tests += 1;
        while remaining % candidate == 0 {
            factors.push(candidate);
            remaining /= candidate;
        }
        candidate += 1;
    }
    if remaining > 1 { factors.push(remaining); }
    println!("{{\"factors\":{factors:?},\"candidate_tests\":{tests},\"termination\":\"factorization_complete\"}}");
}
