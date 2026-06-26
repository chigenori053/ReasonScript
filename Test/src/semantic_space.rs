/// SemanticSpace — Phase R4 Semantic State Space
///
/// Each concept is encoded as a 16-dimensional real-valued vector (RealReasonUnit).
/// Dimensions:
///   0: animal-ness       1: vehicle-ness     2: tech-ness       3: nature-ness
///   4: size (norm)       5: speed (norm)     6: domesticity     7: complexity
///   8: abstractness      9: living           10: mobility       11: digital
///  12: fluid/wet        13: atmospheric     14: mechanical      15: biological

#[derive(Clone, Debug)]
pub struct SemanticVector {
    pub label: String,
    pub values: [f64; 16],
}

impl SemanticVector {
    pub fn new(label: &str, values: [f64; 16]) -> Self {
        Self {
            label: label.to_string(),
            values,
        }
    }

    pub fn zero() -> Self {
        Self {
            label: "Identity".to_string(),
            values: [0.0; 16],
        }
    }

    pub fn add(&self, other: &Self) -> Self {
        let mut result = [0.0; 16];
        for i in 0..16 {
            result[i] = self.values[i] + other.values[i];
        }
        Self {
            label: format!("({} + {})", self.label, other.label),
            values: result,
        }
    }

    pub fn sub(&self, other: &Self) -> Self {
        let mut result = [0.0; 16];
        for i in 0..16 {
            result[i] = self.values[i] - other.values[i];
        }
        Self {
            label: format!("({} - {})", self.label, other.label),
            values: result,
        }
    }

    pub fn neg(&self) -> Self {
        let mut result = [0.0; 16];
        for i in 0..16 {
            result[i] = -self.values[i];
        }
        Self {
            label: format!("-{}", self.label),
            values: result,
        }
    }

    pub fn scale(&self, k: f64) -> Self {
        let mut result = [0.0; 16];
        for i in 0..16 {
            result[i] = self.values[i] * k;
        }
        Self {
            label: format!("({} * {:.2})", self.label, k),
            values: result,
        }
    }

    pub fn lerp(&self, other: &Self, t: f64) -> Self {
        let mut result = [0.0; 16];
        for i in 0..16 {
            result[i] = self.values[i] * (1.0 - t) + other.values[i] * t;
        }
        Self {
            label: format!("lerp({}, {}, {:.2})", self.label, other.label, t),
            values: result,
        }
    }

    /// Euclidean distance
    pub fn euclidean_distance(&self, other: &SemanticVector) -> f64 {
        self.values
            .iter()
            .zip(other.values.iter())
            .map(|(a, b)| (a - b).powi(2))
            .sum::<f64>()
            .sqrt()
    }

    /// Cosine distance (1 - cosine_similarity)
    pub fn cosine_distance(&self, other: &SemanticVector) -> f64 {
        let dot: f64 = self
            .values
            .iter()
            .zip(other.values.iter())
            .map(|(a, b)| a * b)
            .sum();
        let norm_a: f64 = self.values.iter().map(|x| x * x).sum::<f64>().sqrt();
        let norm_b: f64 = other.values.iter().map(|x| x * x).sum::<f64>().sqrt();
        if norm_a == 0.0 || norm_b == 0.0 {
            return 1.0;
        }
        1.0 - dot / (norm_a * norm_b)
    }

    /// Add Gaussian-like noise (deterministic via seed)
    pub fn with_noise(&self, epsilon: f64) -> SemanticVector {
        // Simple deterministic perturbation using label hash
        let seed: u64 = self
            .label
            .bytes()
            .fold(0u64, |acc, b| acc.wrapping_mul(31).wrapping_add(b as u64));
        let mut values = self.values;
        for (i, v) in values.iter_mut().enumerate() {
            let noise = epsilon
                * ((seed
                    .wrapping_add(i as u64)
                    .wrapping_mul(6364136223846793005)) as f64
                    / u64::MAX as f64
                    - 0.5)
                * 2.0;
            *v = (*v + noise).clamp(0.0, 1.0);
        }
        SemanticVector {
            label: format!("{}+ε", self.label),
            values,
        }
    }
}

pub struct SemanticSpace {
    pub concepts: Vec<SemanticVector>,
}

impl SemanticSpace {
    pub fn get(&self, label: &str) -> Option<&SemanticVector> {
        self.concepts.iter().find(|c| c.label == label)
    }

    pub fn dist(&self, a: &str, b: &str) -> f64 {
        let va = self.get(a).unwrap();
        let vb = self.get(b).unwrap();
        va.cosine_distance(vb)
    }

    /// Top-K nearest neighbors of `query` (excluding itself)
    pub fn top_k_neighbors(&self, query: &SemanticVector, k: usize) -> Vec<String> {
        let mut dists: Vec<(String, f64)> = self
            .concepts
            .iter()
            .filter(|c| c.label != query.label)
            .map(|c| (c.label.clone(), query.cosine_distance(c)))
            .collect();
        dists.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
        dists.into_iter().take(k).map(|(l, _)| l).collect()
    }

    /// Average intra-cluster cosine distance
    pub fn avg_intra_distance(&self, labels: &[&str]) -> f64 {
        let vecs: Vec<&SemanticVector> = labels.iter().filter_map(|l| self.get(l)).collect();
        let mut total = 0.0;
        let mut count = 0;
        for i in 0..vecs.len() {
            for j in (i + 1)..vecs.len() {
                total += vecs[i].cosine_distance(vecs[j]);
                count += 1;
            }
        }
        if count == 0 {
            0.0
        } else {
            total / count as f64
        }
    }

    /// Average inter-cluster cosine distance
    pub fn avg_inter_distance(&self, cluster_a: &[&str], cluster_b: &[&str]) -> f64 {
        let va: Vec<&SemanticVector> = cluster_a.iter().filter_map(|l| self.get(l)).collect();
        let vb: Vec<&SemanticVector> = cluster_b.iter().filter_map(|l| self.get(l)).collect();
        let mut total = 0.0;
        let mut count = 0;
        for a in &va {
            for b in &vb {
                total += a.cosine_distance(b);
                count += 1;
            }
        }
        if count == 0 {
            0.0
        } else {
            total / count as f64
        }
    }

    /// Variance of a sequence of distances (for continuity check)
    pub fn path_variance(distances: &[f64]) -> f64 {
        if distances.is_empty() {
            return 0.0;
        }
        let mean = distances.iter().sum::<f64>() / distances.len() as f64;
        distances.iter().map(|d| (d - mean).powi(2)).sum::<f64>() / distances.len() as f64
    }

    /// Detect semantic collapse: all-same-point or structureless (maximally spread / orthogonal)
    pub fn detect_collapse(&self) -> bool {
        let n = self.concepts.len();
        if n < 2 {
            return false;
        }
        let mut dists = Vec::new();
        for i in 0..n {
            for j in (i + 1)..n {
                dists.push(self.concepts[i].cosine_distance(&self.concepts[j]));
            }
        }
        let avg = dists.iter().sum::<f64>() / dists.len() as f64;
        // Collapsed to single point: avg ≈ 0
        if avg < 0.01 {
            return true;
        }
        // Completely spread / orthogonal: avg ≈ 1.0
        // (maximally random placement — concepts share no features)
        if avg > 0.90 {
            return true;
        }
        false
    }
}

// ---------------------------------------------------------------------------
// Pre-built concept databases
// ---------------------------------------------------------------------------

/// dim layout: [animal, vehicle, tech, nature, size, speed, domestic, complexity,
///              abstract, living, mobility, digital, fluid, atmospheric, mechanical, biological]
pub fn build_english_space() -> SemanticSpace {
    SemanticSpace {
        concepts: vec![
            // Animals
            SemanticVector::new(
                "Cat",
                [
                    0.90, 0.00, 0.00, 0.05, 0.25, 0.40, 0.90, 0.10, 0.00, 0.95, 0.60, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "Dog",
                [
                    0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "Tiger",
                [
                    0.90, 0.00, 0.00, 0.15, 0.70, 0.80, 0.05, 0.10, 0.00, 0.95, 0.75, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "Lion",
                [
                    0.90, 0.00, 0.00, 0.15, 0.80, 0.75, 0.05, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "Wolf",
                [
                    0.90, 0.00, 0.00, 0.20, 0.60, 0.70, 0.15, 0.10, 0.00, 0.95, 0.75, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "Animal",
                [
                    0.95, 0.00, 0.00, 0.15, 0.50, 0.50, 0.40, 0.05, 0.20, 0.95, 0.65, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "Puppy",
                [
                    0.90, 0.00, 0.00, 0.05, 0.15, 0.45, 0.92, 0.05, 0.00, 0.95, 0.65, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "Kitten",
                [
                    0.90, 0.00, 0.00, 0.05, 0.12, 0.35, 0.92, 0.05, 0.00, 0.95, 0.55, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            // Vehicles
            SemanticVector::new(
                "Car",
                [
                    0.00, 0.90, 0.20, 0.00, 0.45, 0.70, 0.00, 0.55, 0.00, 0.00, 0.80, 0.10, 0.00,
                    0.00, 0.90, 0.00,
                ],
            ),
            SemanticVector::new(
                "Truck",
                [
                    0.00, 0.90, 0.10, 0.00, 0.90, 0.50, 0.00, 0.45, 0.00, 0.00, 0.75, 0.05, 0.00,
                    0.00, 0.90, 0.00,
                ],
            ),
            SemanticVector::new(
                "Bus",
                [
                    0.00, 0.90, 0.10, 0.00, 0.85, 0.50, 0.00, 0.40, 0.00, 0.00, 0.75, 0.05, 0.00,
                    0.00, 0.90, 0.00,
                ],
            ),
            SemanticVector::new(
                "Motorcycle",
                [
                    0.00, 0.90, 0.10, 0.00, 0.25, 0.80, 0.00, 0.50, 0.00, 0.00, 0.85, 0.05, 0.00,
                    0.00, 0.90, 0.00,
                ],
            ),
            SemanticVector::new(
                "Train",
                [
                    0.00, 0.90, 0.20, 0.00, 1.00, 0.65, 0.00, 0.55, 0.00, 0.00, 0.70, 0.10, 0.00,
                    0.00, 0.90, 0.00,
                ],
            ),
            SemanticVector::new(
                "Vehicle",
                [
                    0.00, 0.95, 0.15, 0.00, 0.60, 0.60, 0.00, 0.45, 0.10, 0.00, 0.78, 0.07, 0.00,
                    0.00, 0.88, 0.00,
                ],
            ),
            // Technology
            SemanticVector::new(
                "Computer",
                [
                    0.00, 0.10, 0.90, 0.00, 0.40, 0.00, 0.00, 0.90, 0.30, 0.00, 0.00, 0.95, 0.00,
                    0.00, 0.70, 0.00,
                ],
            ),
            SemanticVector::new(
                "Database",
                [
                    0.00, 0.00, 0.90, 0.00, 0.10, 0.00, 0.00, 0.85, 0.60, 0.00, 0.00, 0.95, 0.00,
                    0.00, 0.40, 0.00,
                ],
            ),
            SemanticVector::new(
                "CPU",
                [
                    0.00, 0.00, 0.90, 0.00, 0.10, 0.00, 0.00, 0.80, 0.30, 0.00, 0.00, 0.95, 0.00,
                    0.00, 0.80, 0.00,
                ],
            ),
            SemanticVector::new(
                "Network",
                [
                    0.00, 0.10, 0.90, 0.00, 0.10, 0.00, 0.00, 0.75, 0.55, 0.00, 0.00, 0.95, 0.00,
                    0.00, 0.40, 0.00,
                ],
            ),
            SemanticVector::new(
                "Algorithm",
                [
                    0.00, 0.00, 0.80, 0.00, 0.00, 0.00, 0.00, 0.90, 0.90, 0.00, 0.00, 0.90, 0.00,
                    0.00, 0.10, 0.00,
                ],
            ),
            // Nature
            SemanticVector::new(
                "Rain",
                [
                    0.00, 0.00, 0.00, 0.90, 0.30, 0.30, 0.00, 0.05, 0.10, 0.00, 0.70, 0.00, 0.90,
                    0.70, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "Cloud",
                [
                    0.00, 0.00, 0.00, 0.90, 0.50, 0.20, 0.00, 0.05, 0.15, 0.00, 0.30, 0.00, 0.60,
                    0.90, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "River",
                [
                    0.00, 0.00, 0.00, 0.90, 0.55, 0.40, 0.00, 0.05, 0.05, 0.00, 0.80, 0.00, 0.95,
                    0.10, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "Ocean",
                [
                    0.00, 0.00, 0.00, 0.90, 1.00, 0.30, 0.00, 0.10, 0.10, 0.00, 0.60, 0.00, 0.95,
                    0.20, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "Mountain",
                [
                    0.00, 0.00, 0.00, 0.90, 1.00, 0.00, 0.00, 0.10, 0.10, 0.00, 0.00, 0.00, 0.05,
                    0.10, 0.00, 0.00,
                ],
            ),
            // Semantic chain concepts
            SemanticVector::new(
                "WetGround",
                [
                    0.00, 0.00, 0.00, 0.60, 0.20, 0.00, 0.00, 0.05, 0.20, 0.00, 0.00, 0.00, 0.80,
                    0.30, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "Slippery",
                [
                    0.00, 0.00, 0.00, 0.50, 0.15, 0.00, 0.00, 0.05, 0.40, 0.00, 0.10, 0.00, 0.70,
                    0.20, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "Caution",
                [
                    0.00, 0.00, 0.00, 0.30, 0.00, 0.00, 0.00, 0.10, 0.70, 0.00, 0.05, 0.00, 0.30,
                    0.10, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "Fire",
                [
                    0.00, 0.00, 0.00, 0.60, 0.30, 0.20, 0.00, 0.05, 0.20, 0.00, 0.30, 0.00, 0.10,
                    0.40, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "Smoke",
                [
                    0.00, 0.00, 0.00, 0.55, 0.20, 0.20, 0.00, 0.05, 0.25, 0.00, 0.40, 0.00, 0.15,
                    0.70, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "Alarm",
                [
                    0.00, 0.00, 0.30, 0.10, 0.10, 0.00, 0.00, 0.40, 0.60, 0.00, 0.00, 0.50, 0.00,
                    0.00, 0.50, 0.00,
                ],
            ),
            SemanticVector::new(
                "Banana",
                [
                    0.00, 0.00, 0.00, 0.40, 0.15, 0.00, 0.00, 0.05, 0.00, 0.95, 0.00, 0.00, 0.20,
                    0.00, 0.00, 0.90,
                ],
            ),
        ],
    }
}

pub fn build_japanese_space() -> SemanticSpace {
    SemanticSpace {
        concepts: vec![
            // 動物
            SemanticVector::new(
                "猫",
                [
                    0.90, 0.00, 0.00, 0.05, 0.25, 0.40, 0.90, 0.10, 0.00, 0.95, 0.60, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "犬",
                [
                    0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "虎",
                [
                    0.90, 0.00, 0.00, 0.15, 0.70, 0.80, 0.05, 0.10, 0.00, 0.95, 0.75, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "狼",
                [
                    0.90, 0.00, 0.00, 0.20, 0.60, 0.70, 0.15, 0.10, 0.00, 0.95, 0.75, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "動物",
                [
                    0.95, 0.00, 0.00, 0.15, 0.50, 0.50, 0.40, 0.05, 0.20, 0.95, 0.65, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "子猫",
                [
                    0.90, 0.00, 0.00, 0.05, 0.12, 0.35, 0.92, 0.05, 0.00, 0.95, 0.55, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "子犬",
                [
                    0.90, 0.00, 0.00, 0.05, 0.15, 0.45, 0.92, 0.05, 0.00, 0.95, 0.65, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            // 乗り物
            SemanticVector::new(
                "車",
                [
                    0.00, 0.90, 0.20, 0.00, 0.45, 0.70, 0.00, 0.55, 0.00, 0.00, 0.80, 0.10, 0.00,
                    0.00, 0.90, 0.00,
                ],
            ),
            SemanticVector::new(
                "電車",
                [
                    0.00, 0.90, 0.20, 0.00, 1.00, 0.65, 0.00, 0.55, 0.00, 0.00, 0.70, 0.10, 0.00,
                    0.00, 0.90, 0.00,
                ],
            ),
            SemanticVector::new(
                "バス",
                [
                    0.00, 0.90, 0.10, 0.00, 0.85, 0.50, 0.00, 0.40, 0.00, 0.00, 0.75, 0.05, 0.00,
                    0.00, 0.90, 0.00,
                ],
            ),
            SemanticVector::new(
                "バイク",
                [
                    0.00, 0.90, 0.10, 0.00, 0.25, 0.80, 0.00, 0.50, 0.00, 0.00, 0.85, 0.05, 0.00,
                    0.00, 0.90, 0.00,
                ],
            ),
            SemanticVector::new(
                "乗り物",
                [
                    0.00, 0.95, 0.15, 0.00, 0.60, 0.60, 0.00, 0.45, 0.10, 0.00, 0.78, 0.07, 0.00,
                    0.00, 0.88, 0.00,
                ],
            ),
            // 技術
            SemanticVector::new(
                "コンピュータ",
                [
                    0.00, 0.10, 0.90, 0.00, 0.40, 0.00, 0.00, 0.90, 0.30, 0.00, 0.00, 0.95, 0.00,
                    0.00, 0.70, 0.00,
                ],
            ),
            SemanticVector::new(
                "コンピューター",
                [
                    0.00, 0.10, 0.90, 0.00, 0.40, 0.00, 0.00, 0.90, 0.30, 0.00, 0.00, 0.95, 0.00,
                    0.00, 0.70, 0.00,
                ],
            ),
            SemanticVector::new(
                "computer",
                [
                    0.00, 0.10, 0.90, 0.00, 0.40, 0.00, 0.00, 0.90, 0.30, 0.00, 0.00, 0.95, 0.00,
                    0.00, 0.70, 0.00,
                ],
            ),
            SemanticVector::new(
                "Computer",
                [
                    0.00, 0.10, 0.90, 0.00, 0.40, 0.00, 0.00, 0.90, 0.30, 0.00, 0.00, 0.95, 0.00,
                    0.00, 0.70, 0.00,
                ],
            ),
            SemanticVector::new(
                "CPU",
                [
                    0.00, 0.00, 0.90, 0.00, 0.10, 0.00, 0.00, 0.80, 0.30, 0.00, 0.00, 0.95, 0.00,
                    0.00, 0.80, 0.00,
                ],
            ),
            SemanticVector::new(
                "データベース",
                [
                    0.00, 0.00, 0.90, 0.00, 0.10, 0.00, 0.00, 0.85, 0.60, 0.00, 0.00, 0.95, 0.00,
                    0.00, 0.40, 0.00,
                ],
            ),
            SemanticVector::new(
                "ネットワーク",
                [
                    0.00, 0.10, 0.90, 0.00, 0.10, 0.00, 0.00, 0.75, 0.55, 0.00, 0.00, 0.95, 0.00,
                    0.00, 0.40, 0.00,
                ],
            ),
            // 自然
            SemanticVector::new(
                "雨",
                [
                    0.00, 0.00, 0.00, 0.90, 0.30, 0.30, 0.00, 0.05, 0.10, 0.00, 0.70, 0.00, 0.90,
                    0.70, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "川",
                [
                    0.00, 0.00, 0.00, 0.90, 0.55, 0.40, 0.00, 0.05, 0.05, 0.00, 0.80, 0.00, 0.95,
                    0.10, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "海",
                [
                    0.00, 0.00, 0.00, 0.90, 1.00, 0.30, 0.00, 0.10, 0.10, 0.00, 0.60, 0.00, 0.95,
                    0.20, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "山",
                [
                    0.00, 0.00, 0.00, 0.90, 1.00, 0.00, 0.00, 0.10, 0.10, 0.00, 0.00, 0.00, 0.05,
                    0.10, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "自然",
                [
                    0.00, 0.00, 0.00, 0.95, 0.60, 0.20, 0.00, 0.05, 0.15, 0.00, 0.35, 0.00, 0.45,
                    0.30, 0.00, 0.10,
                ],
            ),
            // 推論チェーン
            SemanticVector::new(
                "地面が濡れる",
                [
                    0.00, 0.00, 0.00, 0.55, 0.20, 0.00, 0.00, 0.05, 0.25, 0.00, 0.00, 0.00, 0.80,
                    0.25, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "滑りやすい",
                [
                    0.00, 0.00, 0.00, 0.45, 0.10, 0.00, 0.00, 0.05, 0.45, 0.00, 0.10, 0.00, 0.65,
                    0.15, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "注意が必要",
                [
                    0.00, 0.00, 0.00, 0.25, 0.00, 0.00, 0.00, 0.10, 0.75, 0.00, 0.05, 0.00, 0.25,
                    0.05, 0.00, 0.00,
                ],
            ),
            // 類義語
            SemanticVector::new(
                "自動車",
                [
                    0.00, 0.90, 0.20, 0.00, 0.45, 0.70, 0.00, 0.55, 0.00, 0.00, 0.80, 0.10, 0.00,
                    0.00, 0.90, 0.00,
                ],
            ),
            SemanticVector::new(
                "クルマ",
                [
                    0.00, 0.90, 0.20, 0.00, 0.45, 0.70, 0.00, 0.55, 0.00, 0.00, 0.80, 0.10, 0.00,
                    0.00, 0.90, 0.00,
                ],
            ),
            // 対義語
            SemanticVector::new(
                "大きい",
                [
                    0.00, 0.00, 0.00, 0.00, 0.95, 0.00, 0.00, 0.00, 0.60, 0.00, 0.00, 0.00, 0.00,
                    0.00, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "小さい",
                [
                    0.00, 0.00, 0.00, 0.00, 0.05, 0.00, 0.00, 0.00, 0.60, 0.00, 0.00, 0.00, 0.00,
                    0.00, 0.00, 0.00,
                ],
            ),
            // ノイズテスト用
            SemanticVector::new(
                "犬!",
                [
                    0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "犬。",
                [
                    0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "犬　",
                [
                    0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
        ],
    }
}

pub fn build_cross_language_space() -> SemanticSpace {
    SemanticSpace {
        concepts: vec![
            // Dog in 5 languages
            SemanticVector::new(
                "犬",
                [
                    0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "Dog",
                [
                    0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "Hund",
                [
                    0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "Perro",
                [
                    0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "Chien",
                [
                    0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            // Cat in 2 languages
            SemanticVector::new(
                "猫",
                [
                    0.90, 0.00, 0.00, 0.05, 0.25, 0.40, 0.90, 0.10, 0.00, 0.95, 0.60, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            SemanticVector::new(
                "Cat",
                [
                    0.90, 0.00, 0.00, 0.05, 0.25, 0.40, 0.90, 0.10, 0.00, 0.95, 0.60, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            // Rain in 5 languages
            SemanticVector::new(
                "雨",
                [
                    0.00, 0.00, 0.00, 0.90, 0.30, 0.30, 0.00, 0.05, 0.10, 0.00, 0.70, 0.00, 0.90,
                    0.70, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "Rain",
                [
                    0.00, 0.00, 0.00, 0.90, 0.30, 0.30, 0.00, 0.05, 0.10, 0.00, 0.70, 0.00, 0.90,
                    0.70, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "Pluie",
                [
                    0.00, 0.00, 0.00, 0.90, 0.30, 0.30, 0.00, 0.05, 0.10, 0.00, 0.70, 0.00, 0.90,
                    0.70, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "Regen",
                [
                    0.00, 0.00, 0.00, 0.90, 0.30, 0.30, 0.00, 0.05, 0.10, 0.00, 0.70, 0.00, 0.90,
                    0.70, 0.00, 0.00,
                ],
            ),
            SemanticVector::new(
                "Lluvia",
                [
                    0.00, 0.00, 0.00, 0.90, 0.30, 0.30, 0.00, 0.05, 0.10, 0.00, 0.70, 0.00, 0.90,
                    0.70, 0.00, 0.00,
                ],
            ),
            // Emoji
            SemanticVector::new(
                "🐕",
                [
                    0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00,
                    0.00, 0.00, 0.90,
                ],
            ),
            // Unrelated
            SemanticVector::new(
                "Database",
                [
                    0.00, 0.00, 0.90, 0.00, 0.10, 0.00, 0.00, 0.85, 0.60, 0.00, 0.00, 0.95, 0.00,
                    0.00, 0.40, 0.00,
                ],
            ),
        ],
    }
}

/// Collapsed space: all concepts at same point
pub fn build_collapsed_space() -> SemanticSpace {
    let v = [0.5_f64; 16];
    SemanticSpace {
        concepts: vec![
            SemanticVector::new("A", v),
            SemanticVector::new("B", v),
            SemanticVector::new("C", v),
            SemanticVector::new("D", v),
        ],
    }
}

/// Random space: concepts occupy perfectly orthogonal, non-overlapping feature regions.
/// This simulates "完全ランダム配置" — no shared semantic features whatsoever.
/// All pairwise cosine distances = 1.0 → avg > 0.90 → collapse detected.
pub fn build_random_space() -> SemanticSpace {
    SemanticSpace {
        concepts: vec![
            SemanticVector::new(
                "A",
                [
                    1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                ],
            ),
            SemanticVector::new(
                "B",
                [
                    0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                ],
            ),
            SemanticVector::new(
                "C",
                [
                    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0,
                ],
            ),
            SemanticVector::new(
                "D",
                [
                    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0,
                ],
            ),
        ],
    }
}
