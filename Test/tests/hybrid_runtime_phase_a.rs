use std::collections::BTreeMap;

#[derive(Clone, Copy)]
struct Candidate {
    name: &'static str,
    features: [f64; 7],
}

#[derive(Clone, Debug)]
struct Observation {
    probabilities: Vec<(&'static str, f64)>,
    entropy_bits: f64,
    normalized_entropy: f64,
    effective_candidates: f64,
    top_probability: f64,
    top_margin: f64,
    semantic_density: f64,
    evidence_conflict: f64,
    unsupported_evidence: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Strategy {
    Real,
    Clarify,
    Complex,
}

const ANIMAL: usize = 0;
const CANINE: usize = 1;
const DOMESTIC: usize = 2;
const WILD: usize = 3;
const PET: usize = 4;
const VEHICLE: usize = 5;
const PLANET: usize = 6;

const DOG: Candidate = Candidate {
    name: "Dog",
    features: [0.99, 0.99, 0.96, 0.18, 0.97, 0.01, 0.01],
};
const WOLF: Candidate = Candidate {
    name: "Wolf",
    features: [0.99, 0.96, 0.08, 0.96, 0.05, 0.01, 0.01],
};
const FOX: Candidate = Candidate {
    name: "Fox",
    features: [0.99, 0.58, 0.06, 0.94, 0.04, 0.01, 0.01],
};
const CAR: Candidate = Candidate {
    name: "Car",
    features: [0.01, 0.01, 0.01, 0.01, 0.01, 0.99, 0.01],
};
const TRUCK: Candidate = Candidate {
    name: "Truck",
    features: [0.01, 0.01, 0.01, 0.01, 0.01, 0.99, 0.01],
};
const BUS: Candidate = Candidate {
    name: "Bus",
    features: [0.01, 0.01, 0.01, 0.01, 0.01, 0.99, 0.01],
};
const MOTORCYCLE: Candidate = Candidate {
    name: "Motorcycle",
    features: [0.01, 0.01, 0.01, 0.01, 0.01, 0.99, 0.01],
};
const BICYCLE: Candidate = Candidate {
    name: "Bicycle",
    features: [0.01, 0.01, 0.01, 0.01, 0.01, 0.99, 0.01],
};
const EARTH: Candidate = Candidate {
    name: "Planet",
    features: [0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.99],
};

fn evidence_index(label: &str) -> Option<usize> {
    match label {
        "Animal" => Some(ANIMAL),
        "Canine" => Some(CANINE),
        "Domestic" => Some(DOMESTIC),
        "Wild" => Some(WILD),
        "Pet" => Some(PET),
        "Vehicle" => Some(VEHICLE),
        "Planet" => Some(PLANET),
        _ => None,
    }
}

fn observe(evidence: &[&str], candidates: &[Candidate]) -> Observation {
    let supported: Vec<usize> = evidence
        .iter()
        .filter_map(|label| evidence_index(label))
        .collect();
    let recognized_count = evidence
        .iter()
        .filter(|label| {
            evidence_index(label).is_some()
                || candidates.iter().any(|candidate| candidate.name == **label)
        })
        .count();
    let unsupported_evidence =
        (evidence.len() - recognized_count) as f64 / evidence.len().max(1) as f64;

    let log_scores: Vec<f64> = candidates
        .iter()
        .map(|candidate| {
            supported
                .iter()
                .map(|&index| candidate.features[index].max(1e-9).ln())
                .sum()
        })
        .collect();
    let max_score = log_scores.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    let weights: Vec<f64> = log_scores
        .iter()
        .map(|score| (score - max_score).exp())
        .collect();
    let weight_sum: f64 = weights.iter().sum();
    let mut probabilities: Vec<(&'static str, f64)> = candidates
        .iter()
        .zip(weights.iter())
        .map(|(candidate, weight)| (candidate.name, weight / weight_sum))
        .collect();
    probabilities.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());

    let entropy_bits = probabilities
        .iter()
        .filter(|(_, p)| *p > 0.0)
        .map(|(_, p)| -p * p.log2())
        .sum::<f64>();
    let normalized_entropy = if candidates.len() <= 1 {
        0.0
    } else {
        entropy_bits / (candidates.len() as f64).log2()
    };
    let effective_candidates = 2.0_f64.powf(entropy_bits);
    let top_probability = probabilities.first().map(|(_, p)| *p).unwrap_or(0.0);
    let second_probability = probabilities.get(1).map(|(_, p)| *p).unwrap_or(0.0);

    let mut similarity_sum = 0.0;
    let mut pair_count = 0;
    for left in 0..candidates.len() {
        for right in (left + 1)..candidates.len() {
            similarity_sum +=
                cosine_similarity(&candidates[left].features, &candidates[right].features);
            pair_count += 1;
        }
    }
    let semantic_density = if pair_count == 0 {
        0.0
    } else {
        similarity_sum / pair_count as f64
    };

    let evidence_conflict = if supported.len() <= 1 {
        0.0
    } else {
        let evidence_vectors: Vec<Vec<f64>> = supported
            .iter()
            .map(|&index| {
                candidates
                    .iter()
                    .map(|candidate| candidate.features[index])
                    .collect()
            })
            .collect();
        let mut disagreement = 0.0;
        let mut comparisons = 0;
        for left in 0..evidence_vectors.len() {
            for right in (left + 1)..evidence_vectors.len() {
                disagreement +=
                    1.0 - pearson_similarity(&evidence_vectors[left], &evidence_vectors[right]);
                comparisons += 1;
            }
        }
        (disagreement / comparisons as f64).clamp(0.0, 1.0)
    };

    Observation {
        probabilities,
        entropy_bits,
        normalized_entropy,
        effective_candidates,
        top_probability,
        top_margin: top_probability - second_probability,
        semantic_density,
        evidence_conflict,
        unsupported_evidence,
    }
}

fn observe_probabilities(values: &[(&'static str, f64)]) -> Observation {
    let entropy_bits = values
        .iter()
        .map(|(_, p)| if *p > 0.0 { -p * p.log2() } else { 0.0 })
        .sum::<f64>();
    let mut probabilities = values.to_vec();
    probabilities.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    let top_probability = probabilities[0].1;
    let second_probability = probabilities.get(1).map(|(_, p)| *p).unwrap_or(0.0);
    Observation {
        probabilities,
        entropy_bits,
        normalized_entropy: entropy_bits / (values.len() as f64).log2(),
        effective_candidates: 2.0_f64.powf(entropy_bits),
        top_probability,
        top_margin: top_probability - second_probability,
        semantic_density: 0.0,
        evidence_conflict: 0.0,
        unsupported_evidence: 0.0,
    }
}

fn cosine_similarity(left: &[f64], right: &[f64]) -> f64 {
    let dot: f64 = left.iter().zip(right).map(|(a, b)| a * b).sum();
    let left_norm = left.iter().map(|value| value * value).sum::<f64>().sqrt();
    let right_norm = right.iter().map(|value| value * value).sum::<f64>().sqrt();
    if left_norm == 0.0 || right_norm == 0.0 {
        0.0
    } else {
        dot / (left_norm * right_norm)
    }
}

fn pearson_similarity(left: &[f64], right: &[f64]) -> f64 {
    let left_mean = left.iter().sum::<f64>() / left.len() as f64;
    let right_mean = right.iter().sum::<f64>() / right.len() as f64;
    let numerator: f64 = left
        .iter()
        .zip(right)
        .map(|(a, b)| (a - left_mean) * (b - right_mean))
        .sum();
    let left_scale = left
        .iter()
        .map(|value| (value - left_mean).powi(2))
        .sum::<f64>()
        .sqrt();
    let right_scale = right
        .iter()
        .map(|value| (value - right_mean).powi(2))
        .sum::<f64>()
        .sqrt();
    if left_scale == 0.0 || right_scale == 0.0 {
        // A non-discriminating evidence item does not oppose another ranking.
        1.0
    } else {
        ((numerator / (left_scale * right_scale)) + 1.0) / 2.0
    }
}

fn band_strategy(observation: &Observation) -> Strategy {
    if observation.top_probability >= 0.85 && observation.top_margin >= 0.50 {
        Strategy::Real
    } else if observation.normalized_entropy >= 0.85
        || observation.top_margin <= 0.10
        || observation.evidence_conflict >= 0.60
    {
        Strategy::Complex
    } else {
        Strategy::Clarify
    }
}

fn expected_cost_strategy(observation: &Observation) -> (Strategy, BTreeMap<&'static str, f64>) {
    let error_probability = 1.0 - observation.top_probability;
    let conflict = observation.evidence_conflict;
    let costs = BTreeMap::from([
        ("Real", 4.0 * error_probability + 1.5 * conflict),
        ("Clarify", 0.45 + 1.2 * error_probability + 0.4 * conflict),
        ("Complex", 0.90 + 0.35 * error_probability + 0.15 * conflict),
    ]);
    let selected = costs
        .iter()
        .min_by(|left, right| left.1.partial_cmp(right.1).unwrap())
        .map(|(name, _)| match *name {
            "Real" => Strategy::Real,
            "Clarify" => Strategy::Clarify,
            _ => Strategy::Complex,
        })
        .unwrap();
    (selected, costs)
}

fn print_observation(test_id: &str, observation: &Observation) {
    let probabilities = observation
        .probabilities
        .iter()
        .map(|(name, p)| format!("{name}={p:.4}"))
        .collect::<Vec<_>>()
        .join(",");
    println!(
        "OBS|{test_id}|H={:.6}|Hn={:.6}|Neff={:.6}|P1={:.6}|Margin={:.6}|Density={:.6}|Conflict={:.6}|Unsupported={:.6}|{}",
        observation.entropy_bits,
        observation.normalized_entropy,
        observation.effective_candidates,
        observation.top_probability,
        observation.top_margin,
        observation.semantic_density,
        observation.evidence_conflict,
        observation.unsupported_evidence,
        probabilities
    );
}

#[test]
fn phase_a_1_ambiguity_evaluation_validation() {
    let ae01 = observe(&["Dog"], &[DOG]);
    let ae02 = observe(&["Animal", "Canine"], &[DOG, WOLF]);
    let ae03 = observe(&["Vehicle"], &[CAR, TRUCK, BUS, MOTORCYCLE, BICYCLE]);
    let ae04 = observe(&["Animal", "Canine", "Domestic"], &[DOG, WOLF, FOX]);
    let ae05 = observe(&["Animal"], &[DOG, CAR, EARTH]);

    for (id, observation) in [
        ("AE-01", &ae01),
        ("AE-02", &ae02),
        ("AE-03", &ae03),
        ("AE-04", &ae04),
        ("AE-05", &ae05),
    ] {
        print_observation(id, observation);
    }

    assert!(ae01.entropy_bits < ae02.entropy_bits);
    assert!(ae02.entropy_bits < ae03.entropy_bits);
    assert!(ae04.semantic_density > ae05.semantic_density);
    assert!(ae04.entropy_bits > ae05.entropy_bits);
}

#[test]
fn phase_a_2_ambiguity_dynamics_validation() {
    let ad01_base = observe(&["Animal"], &[DOG, WOLF, FOX]);
    let ad01_canine = observe(&["Animal", "Canine"], &[DOG, WOLF, FOX]);
    let ad01_domestic = observe(&["Animal", "Canine", "Domestic"], &[DOG, WOLF, FOX]);
    let ad01_pet = observe(&["Animal", "Canine", "Domestic", "Pet"], &[DOG, WOLF, FOX]);
    let ad02_consistent = ad01_domestic.clone();
    let ad02_conflict = observe(&["Animal", "Canine", "Domestic", "Wild"], &[DOG, WOLF, FOX]);
    let ad03_clean = observe(&["Animal", "Canine", "Domestic"], &[DOG, WOLF, FOX]);
    let ad03_noise = observe(
        &["Animal", "Canine", "Domestic", "RandomNoise"],
        &[DOG, WOLF, FOX],
    );

    for (id, observation) in [
        ("AD-01/base", &ad01_base),
        ("AD-01/+Canine", &ad01_canine),
        ("AD-01/+Domestic", &ad01_domestic),
        ("AD-01/+Pet", &ad01_pet),
        ("AD-02/consistent", &ad02_consistent),
        ("AD-02/conflict", &ad02_conflict),
        ("AD-03/clean", &ad03_clean),
        ("AD-03/noise", &ad03_noise),
    ] {
        print_observation(id, observation);
    }

    assert!(ad01_base.entropy_bits > ad01_canine.entropy_bits);
    assert!(ad01_canine.entropy_bits > ad01_domestic.entropy_bits);
    assert!(ad01_domestic.entropy_bits > ad01_pet.entropy_bits);
    assert!(ad02_conflict.entropy_bits > ad02_consistent.entropy_bits);
    assert!(ad02_conflict.evidence_conflict > ad02_consistent.evidence_conflict);
    assert!((ad03_clean.entropy_bits - ad03_noise.entropy_bits).abs() < 1e-12);
    assert!(ad03_noise.unsupported_evidence > ad03_clean.unsupported_evidence);
}

#[test]
fn phase_b_and_c_decision_logic_and_trace_validation() {
    let dl01 = observe_probabilities(&[("Dog", 0.95), ("Wolf", 0.03), ("Fox", 0.02)]);
    let dl02 = observe_probabilities(&[("Dog", 0.60), ("Wolf", 0.35), ("Fox", 0.05)]);
    let dl03 = observe_probabilities(&[("Dog", 0.45), ("Wolf", 0.40), ("Fox", 0.15)]);
    let dl04 = observe(&["Pet", "Wild", "Canine"], &[DOG, WOLF, FOX]);

    for (id, observation) in [
        ("DL-01", &dl01),
        ("DL-02", &dl02),
        ("DL-03", &dl03),
        ("DL-04", &dl04),
    ] {
        print_observation(id, observation);
        let band = band_strategy(observation);
        let (cost, costs) = expected_cost_strategy(observation);
        println!(
            "TRACE|{id}|Band={band:?}|ExpectedCost={cost:?}|Costs={costs:?}|Reason=top:{:.4},margin:{:.4},entropy:{:.4},conflict:{:.4}",
            observation.top_probability,
            observation.top_margin,
            observation.normalized_entropy,
            observation.evidence_conflict
        );
    }

    assert_eq!(band_strategy(&dl01), Strategy::Real);
    assert_eq!(band_strategy(&dl02), Strategy::Clarify);
    assert_eq!(band_strategy(&dl03), Strategy::Complex);
    assert_eq!(band_strategy(&dl04), Strategy::Complex);
    assert_eq!(expected_cost_strategy(&dl01).0, Strategy::Real);
    assert_eq!(expected_cost_strategy(&dl02).0, Strategy::Clarify);
    assert_eq!(expected_cost_strategy(&dl03).0, Strategy::Complex);
    assert_eq!(expected_cost_strategy(&dl04).0, Strategy::Clarify);
    assert_ne!(
        band_strategy(&dl04),
        expected_cost_strategy(&dl04).0,
        "DL-04 is expected to expose model-dependent strategy selection"
    );
}
