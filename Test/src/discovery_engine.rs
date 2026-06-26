/// DiscoveryEngine — Phase R5 Unsupervised Semantic State Discovery
///
/// Takes raw, UNLABELED concept state vectors and autonomously discovers:
///   - Clusters        (semantic groupings)
///   - Hierarchy       (super-concept centroids)
///   - Nearest neighbors
///   - Outliers
///   - Path coherence
///
/// Constraints enforced here:
///   - No category labels exposed to algorithms (only used for eval metrics)
///   - No semantic feature names
///   - No knowledge injection

pub const DIM: usize = 16;
pub type Vec16 = [f64; DIM];

// ---------------------------------------------------------------------------
// Data model
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
pub struct RawConcept {
    pub label: String,
    pub state: Vec16,
}

impl RawConcept {
    pub fn new(label: &str, state: Vec16) -> Self {
        Self {
            label: label.to_string(),
            state,
        }
    }
}

// ---------------------------------------------------------------------------
// DiscoveryEngine
// ---------------------------------------------------------------------------

pub struct DiscoveryEngine {
    pub labels: Vec<String>,
    pub states: Vec<Vec16>,
}

impl DiscoveryEngine {
    pub fn new(concepts: Vec<RawConcept>) -> Self {
        let labels = concepts.iter().map(|c| c.label.clone()).collect();
        let states = concepts.iter().map(|c| c.state).collect();
        Self { labels, states }
    }

    pub fn len(&self) -> usize {
        self.labels.len()
    }

    // -----------------------------------------------------------------------
    // Distance
    // -----------------------------------------------------------------------

    pub fn cosine_dist(a: &Vec16, b: &Vec16) -> f64 {
        let dot: f64 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
        let na: f64 = a.iter().map(|x| x * x).sum::<f64>().sqrt();
        let nb: f64 = b.iter().map(|x| x * x).sum::<f64>().sqrt();
        if na < 1e-12 || nb < 1e-12 {
            return 1.0;
        }
        (1.0 - dot / (na * nb)).clamp(0.0, 1.0)
    }

    pub fn dist_by_label(&self, a: &str, b: &str) -> f64 {
        let ia = self.idx(a).expect("label a not found");
        let ib = self.idx(b).expect("label b not found");
        Self::cosine_dist(&self.states[ia], &self.states[ib])
    }

    fn idx(&self, label: &str) -> Option<usize> {
        self.labels.iter().position(|l| l == label)
    }

    // -----------------------------------------------------------------------
    // Farthest-first centroid initialization (deterministic)
    // -----------------------------------------------------------------------

    fn init_centroid_indices(&self, k: usize) -> Vec<usize> {
        assert!(k <= self.len(), "k exceeds number of concepts");
        let mut selected = vec![0usize];
        while selected.len() < k {
            let next = (0..self.len())
                .filter(|i| !selected.contains(i))
                .max_by(|&i, &j| {
                    let di = selected
                        .iter()
                        .map(|&s| Self::cosine_dist(&self.states[i], &self.states[s]))
                        .fold(f64::MAX, f64::min);
                    let dj = selected
                        .iter()
                        .map(|&s| Self::cosine_dist(&self.states[j], &self.states[s]))
                        .fold(f64::MAX, f64::min);
                    di.partial_cmp(&dj).unwrap_or(std::cmp::Ordering::Equal)
                })
                .expect("no next centroid found");
            selected.push(next);
        }
        selected
    }

    // -----------------------------------------------------------------------
    // K-means clustering (cosine distance, farthest-first init)
    // -----------------------------------------------------------------------

    pub fn kmeans(&self, k: usize, max_iter: usize) -> Vec<usize> {
        let seed_indices = self.init_centroid_indices(k);
        let mut centroids: Vec<Vec16> = seed_indices.iter().map(|&i| self.states[i]).collect();
        let mut assignments = vec![0usize; self.len()];

        for _ in 0..max_iter {
            // Assign each concept to nearest centroid
            let new_assignments: Vec<usize> = self
                .states
                .iter()
                .map(|s| {
                    (0..k)
                        .min_by(|&a, &b| {
                            Self::cosine_dist(s, &centroids[a])
                                .partial_cmp(&Self::cosine_dist(s, &centroids[b]))
                                .unwrap_or(std::cmp::Ordering::Equal)
                        })
                        .unwrap_or(0)
                })
                .collect();

            if new_assignments == assignments {
                break;
            }
            assignments = new_assignments;

            // Recompute centroids as unnormalized mean
            for cid in 0..k {
                let members: Vec<&Vec16> = self
                    .states
                    .iter()
                    .enumerate()
                    .filter(|(i, _)| assignments[*i] == cid)
                    .map(|(_, s)| s)
                    .collect();
                if members.is_empty() {
                    continue;
                }
                let mut c = [0.0f64; DIM];
                for s in &members {
                    for d in 0..DIM {
                        c[d] += s[d];
                    }
                }
                let n = members.len() as f64;
                for d in 0..DIM {
                    c[d] /= n;
                }
                centroids[cid] = c;
            }
        }

        assignments
    }

    // -----------------------------------------------------------------------
    // Centroids from cluster assignments
    // -----------------------------------------------------------------------

    pub fn cluster_centroids(&self, assignments: &[usize], k: usize) -> Vec<Vec16> {
        let mut centroids = vec![[0.0f64; DIM]; k];
        let mut counts = vec![0u32; k];
        for (i, &c) in assignments.iter().enumerate() {
            if c < k {
                for d in 0..DIM {
                    centroids[c][d] += self.states[i][d];
                }
                counts[c] += 1;
            }
        }
        for c in 0..k {
            if counts[c] > 0 {
                for d in 0..DIM {
                    centroids[c][d] /= counts[c] as f64;
                }
            }
        }
        centroids
    }

    // -----------------------------------------------------------------------
    // Nearest neighbors
    // -----------------------------------------------------------------------

    pub fn nearest_neighbors(&self, label: &str, k: usize) -> Vec<String> {
        let idx = self.idx(label).expect("label not found");
        let mut dists: Vec<(usize, f64)> = self
            .states
            .iter()
            .enumerate()
            .filter(|(i, _)| *i != idx)
            .map(|(i, s)| (i, Self::cosine_dist(&self.states[idx], s)))
            .collect();
        dists.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
        dists
            .into_iter()
            .take(k)
            .map(|(i, _)| self.labels[i].clone())
            .collect()
    }

    // -----------------------------------------------------------------------
    // Cluster purity  (evaluation only — uses ground truth)
    // -----------------------------------------------------------------------

    pub fn cluster_purity(discovered: &[usize], ground_truth: &[usize], n_clusters: usize) -> f64 {
        let n = discovered.len();
        let n_true = *ground_truth.iter().max().unwrap_or(&0) + 1;
        let mut total_correct = 0usize;

        for cid in 0..n_clusters {
            let mut counts = vec![0u32; n_true];
            for i in 0..n {
                if discovered[i] == cid && ground_truth[i] < n_true {
                    counts[ground_truth[i]] += 1;
                }
            }
            total_correct += *counts.iter().max().unwrap_or(&0) as usize;
        }

        total_correct as f64 / n as f64
    }

    // -----------------------------------------------------------------------
    // Hierarchical Emergence Score
    // Each concept must be closer to its own cluster centroid than to any other
    // -----------------------------------------------------------------------

    pub fn hierarchical_emergence_score(&self, assignments: &[usize], k: usize) -> f64 {
        let centroids = self.cluster_centroids(assignments, k);
        let correct = self
            .states
            .iter()
            .enumerate()
            .filter(|(i, s)| {
                let own_c = assignments[*i];
                let d_own = Self::cosine_dist(s, &centroids[own_c]);
                (0..k)
                    .filter(|&c| c != own_c)
                    .all(|c| Self::cosine_dist(s, &centroids[c]) > d_own)
            })
            .count();
        correct as f64 / self.len() as f64
    }

    // -----------------------------------------------------------------------
    // Cluster Separation Ratio  (SBS)
    // -----------------------------------------------------------------------

    pub fn cluster_separation_ratio(&self, assignments: &[usize], _k: usize) -> f64 {
        let n = self.len();
        let mut intra = (0.0f64, 0u32);
        let mut inter = (0.0f64, 0u32);

        for i in 0..n {
            for j in (i + 1)..n {
                let d = Self::cosine_dist(&self.states[i], &self.states[j]);
                if assignments[i] == assignments[j] {
                    intra.0 += d;
                    intra.1 += 1;
                } else {
                    inter.0 += d;
                    inter.1 += 1;
                }
            }
        }

        if intra.1 == 0 {
            return f64::MAX;
        }
        (inter.0 / inter.1 as f64) / (intra.0 / intra.1 as f64)
    }

    // -----------------------------------------------------------------------
    // Outlier detection
    // A concept is an outlier when its avg distance to ALL OTHER concepts
    // exceeds mean + threshold * std_dev of the same distribution.
    // -----------------------------------------------------------------------

    pub fn detect_outliers_global(&self, threshold_sigma: f64) -> Vec<String> {
        let n = self.len();
        let avg_dists: Vec<f64> = (0..n)
            .map(|i| {
                let sum: f64 = (0..n)
                    .filter(|&j| j != i)
                    .map(|j| Self::cosine_dist(&self.states[i], &self.states[j]))
                    .sum();
                sum / (n - 1) as f64
            })
            .collect();

        let mean = avg_dists.iter().sum::<f64>() / n as f64;
        let std = (avg_dists.iter().map(|d| (d - mean).powi(2)).sum::<f64>() / n as f64).sqrt();

        self.labels
            .iter()
            .enumerate()
            .filter(|(i, _)| avg_dists[*i] > mean + threshold_sigma * std)
            .map(|(_, l)| l.clone())
            .collect()
    }

    // -----------------------------------------------------------------------
    // Path consistency score  (1 = perfectly coherent, 0 = incoherent)
    // -----------------------------------------------------------------------

    pub fn path_consistency_score(&self, chain: &[&str]) -> f64 {
        let dists: Vec<f64> = chain
            .windows(2)
            .map(|w| self.dist_by_label(w[0], w[1]))
            .collect();
        // Lower avg distance → more coherent path
        let avg = dists.iter().sum::<f64>() / dists.len() as f64;
        1.0 - avg
    }

    /// Returns step-distances for the given chain
    pub fn path_distances(&self, chain: &[&str]) -> Vec<f64> {
        chain
            .windows(2)
            .map(|w| self.dist_by_label(w[0], w[1]))
            .collect()
    }

    // -----------------------------------------------------------------------
    // Cross-language / symbol alignment: are two labels in the same cluster?
    // -----------------------------------------------------------------------

    pub fn same_cluster(&self, a: &str, b: &str, assignments: &[usize]) -> bool {
        match (self.idx(a), self.idx(b)) {
            (Some(ia), Some(ib)) => assignments[ia] == assignments[ib],
            _ => false,
        }
    }

    // -----------------------------------------------------------------------
    // Aggregate Emergence Score (ES)
    // -----------------------------------------------------------------------

    pub fn emergence_score(cp: f64, na: f64, hes: f64, sbs: f64, clas: f64) -> f64 {
        let sbs_norm = ((sbs - 1.0) / 3.0).clamp(0.0, 1.0); // normalize: 1→0, 4→1
        (cp + na + hes + sbs_norm + clas) / 5.0
    }
}

// ---------------------------------------------------------------------------
// Ground-truth category helper  (used ONLY by eval functions, not by algorithms)
// ---------------------------------------------------------------------------

pub fn true_category(label: &str) -> usize {
    match label {
        "Dog" | "Cat" | "Tiger" | "Lion" | "Wolf" => 0,
        "Car" | "Truck" | "Bus" | "Train" | "Motorcycle" => 1,
        "Computer" | "Database" | "CPU" | "Network" | "Algorithm" => 2,
        "Rain" | "Cloud" | "River" | "Ocean" | "Mountain" => 3,
        _ => 4,
    }
}

// ---------------------------------------------------------------------------
// Dataset builders  — raw unlabeled concept states
// ---------------------------------------------------------------------------

/// Full 20-concept dataset (interleaved order, no category grouping)
pub fn build_r5_full_dataset() -> DiscoveryEngine {
    DiscoveryEngine::new(vec![
        RawConcept::new(
            "Dog",
            [
                0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Car",
            [
                0.00, 0.90, 0.20, 0.00, 0.45, 0.70, 0.00, 0.55, 0.00, 0.00, 0.80, 0.10, 0.00, 0.00,
                0.90, 0.00,
            ],
        ),
        RawConcept::new(
            "Computer",
            [
                0.00, 0.10, 0.90, 0.00, 0.40, 0.00, 0.00, 0.90, 0.30, 0.00, 0.00, 0.95, 0.00, 0.00,
                0.70, 0.00,
            ],
        ),
        RawConcept::new(
            "Rain",
            [
                0.00, 0.00, 0.00, 0.90, 0.30, 0.30, 0.00, 0.05, 0.10, 0.00, 0.70, 0.00, 0.90, 0.70,
                0.00, 0.00,
            ],
        ),
        RawConcept::new(
            "Cat",
            [
                0.90, 0.00, 0.00, 0.05, 0.25, 0.40, 0.90, 0.10, 0.00, 0.95, 0.60, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Train",
            [
                0.00, 0.90, 0.20, 0.00, 1.00, 0.65, 0.00, 0.55, 0.00, 0.00, 0.70, 0.10, 0.00, 0.00,
                0.90, 0.00,
            ],
        ),
        RawConcept::new(
            "Database",
            [
                0.00, 0.00, 0.90, 0.00, 0.10, 0.00, 0.00, 0.85, 0.60, 0.00, 0.00, 0.95, 0.00, 0.00,
                0.40, 0.00,
            ],
        ),
        RawConcept::new(
            "Cloud",
            [
                0.00, 0.00, 0.00, 0.90, 0.50, 0.20, 0.00, 0.05, 0.15, 0.00, 0.30, 0.00, 0.60, 0.90,
                0.00, 0.00,
            ],
        ),
        RawConcept::new(
            "Tiger",
            [
                0.90, 0.00, 0.00, 0.15, 0.70, 0.80, 0.05, 0.10, 0.00, 0.95, 0.75, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Bus",
            [
                0.00, 0.90, 0.10, 0.00, 0.85, 0.50, 0.00, 0.40, 0.00, 0.00, 0.75, 0.05, 0.00, 0.00,
                0.90, 0.00,
            ],
        ),
        RawConcept::new(
            "CPU",
            [
                0.00, 0.00, 0.90, 0.00, 0.10, 0.00, 0.00, 0.80, 0.30, 0.00, 0.00, 0.95, 0.00, 0.00,
                0.80, 0.00,
            ],
        ),
        RawConcept::new(
            "River",
            [
                0.00, 0.00, 0.00, 0.90, 0.55, 0.40, 0.00, 0.05, 0.05, 0.00, 0.80, 0.00, 0.95, 0.10,
                0.00, 0.00,
            ],
        ),
        RawConcept::new(
            "Lion",
            [
                0.90, 0.00, 0.00, 0.15, 0.80, 0.75, 0.05, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Truck",
            [
                0.00, 0.90, 0.10, 0.00, 0.90, 0.50, 0.00, 0.45, 0.00, 0.00, 0.75, 0.05, 0.00, 0.00,
                0.90, 0.00,
            ],
        ),
        RawConcept::new(
            "Network",
            [
                0.00, 0.10, 0.90, 0.00, 0.10, 0.00, 0.00, 0.75, 0.55, 0.00, 0.00, 0.95, 0.00, 0.00,
                0.40, 0.00,
            ],
        ),
        RawConcept::new(
            "Ocean",
            [
                0.00, 0.00, 0.00, 0.90, 1.00, 0.30, 0.00, 0.10, 0.10, 0.00, 0.60, 0.00, 0.95, 0.20,
                0.00, 0.00,
            ],
        ),
        RawConcept::new(
            "Wolf",
            [
                0.90, 0.00, 0.00, 0.20, 0.60, 0.70, 0.15, 0.10, 0.00, 0.95, 0.75, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Motorcycle",
            [
                0.00, 0.90, 0.10, 0.00, 0.25, 0.80, 0.00, 0.50, 0.00, 0.00, 0.85, 0.05, 0.00, 0.00,
                0.90, 0.00,
            ],
        ),
        RawConcept::new(
            "Algorithm",
            [
                0.00, 0.00, 0.80, 0.00, 0.00, 0.00, 0.00, 0.90, 0.90, 0.00, 0.00, 0.90, 0.00, 0.00,
                0.10, 0.00,
            ],
        ),
        RawConcept::new(
            "Mountain",
            [
                0.00, 0.00, 0.00, 0.90, 1.00, 0.00, 0.00, 0.10, 0.10, 0.00, 0.00, 0.00, 0.05, 0.10,
                0.00, 0.00,
            ],
        ),
    ])
}

/// Mixed 8-concept dataset — 2 per category, interleaved
pub fn build_r5_mixed_dataset() -> DiscoveryEngine {
    DiscoveryEngine::new(vec![
        RawConcept::new(
            "Dog",
            [
                0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Cat",
            [
                0.90, 0.00, 0.00, 0.05, 0.25, 0.40, 0.90, 0.10, 0.00, 0.95, 0.60, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Car",
            [
                0.00, 0.90, 0.20, 0.00, 0.45, 0.70, 0.00, 0.55, 0.00, 0.00, 0.80, 0.10, 0.00, 0.00,
                0.90, 0.00,
            ],
        ),
        RawConcept::new(
            "Train",
            [
                0.00, 0.90, 0.20, 0.00, 1.00, 0.65, 0.00, 0.55, 0.00, 0.00, 0.70, 0.10, 0.00, 0.00,
                0.90, 0.00,
            ],
        ),
        RawConcept::new(
            "Database",
            [
                0.00, 0.00, 0.90, 0.00, 0.10, 0.00, 0.00, 0.85, 0.60, 0.00, 0.00, 0.95, 0.00, 0.00,
                0.40, 0.00,
            ],
        ),
        RawConcept::new(
            "CPU",
            [
                0.00, 0.00, 0.90, 0.00, 0.10, 0.00, 0.00, 0.80, 0.30, 0.00, 0.00, 0.95, 0.00, 0.00,
                0.80, 0.00,
            ],
        ),
        RawConcept::new(
            "Rain",
            [
                0.00, 0.00, 0.00, 0.90, 0.30, 0.30, 0.00, 0.05, 0.10, 0.00, 0.70, 0.00, 0.90, 0.70,
                0.00, 0.00,
            ],
        ),
        RawConcept::new(
            "Ocean",
            [
                0.00, 0.00, 0.00, 0.90, 1.00, 0.30, 0.00, 0.10, 0.10, 0.00, 0.60, 0.00, 0.95, 0.20,
                0.00, 0.00,
            ],
        ),
    ])
}

/// 5-animal dataset for hierarchical test
pub fn build_r5_animal_dataset() -> DiscoveryEngine {
    DiscoveryEngine::new(vec![
        RawConcept::new(
            "Dog",
            [
                0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Cat",
            [
                0.90, 0.00, 0.00, 0.05, 0.25, 0.40, 0.90, 0.10, 0.00, 0.95, 0.60, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Tiger",
            [
                0.90, 0.00, 0.00, 0.15, 0.70, 0.80, 0.05, 0.10, 0.00, 0.95, 0.75, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Lion",
            [
                0.90, 0.00, 0.00, 0.15, 0.80, 0.75, 0.05, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Wolf",
            [
                0.90, 0.00, 0.00, 0.20, 0.60, 0.70, 0.15, 0.10, 0.00, 0.95, 0.75, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
    ])
}

/// Boundary dataset: 2 animals + 2 vehicles
pub fn build_r5_boundary_dataset() -> DiscoveryEngine {
    DiscoveryEngine::new(vec![
        RawConcept::new(
            "Dog",
            [
                0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Cat",
            [
                0.90, 0.00, 0.00, 0.05, 0.25, 0.40, 0.90, 0.10, 0.00, 0.95, 0.60, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Car",
            [
                0.00, 0.90, 0.20, 0.00, 0.45, 0.70, 0.00, 0.55, 0.00, 0.00, 0.80, 0.10, 0.00, 0.00,
                0.90, 0.00,
            ],
        ),
        RawConcept::new(
            "Train",
            [
                0.00, 0.90, 0.20, 0.00, 1.00, 0.65, 0.00, 0.55, 0.00, 0.00, 0.70, 0.10, 0.00, 0.00,
                0.90, 0.00,
            ],
        ),
    ])
}

/// Outlier dataset: 3 animals + 1 tech intruder
pub fn build_r5_outlier_dataset() -> DiscoveryEngine {
    DiscoveryEngine::new(vec![
        RawConcept::new(
            "Dog",
            [
                0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Cat",
            [
                0.90, 0.00, 0.00, 0.05, 0.25, 0.40, 0.90, 0.10, 0.00, 0.95, 0.60, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Tiger",
            [
                0.90, 0.00, 0.00, 0.15, 0.70, 0.80, 0.05, 0.10, 0.00, 0.95, 0.75, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Database",
            [
                0.00, 0.00, 0.90, 0.00, 0.10, 0.00, 0.00, 0.85, 0.60, 0.00, 0.00, 0.95, 0.00, 0.00,
                0.40, 0.00,
            ],
        ),
    ])
}

/// Semantic chain dataset
pub fn build_r5_transition_dataset() -> DiscoveryEngine {
    DiscoveryEngine::new(vec![
        RawConcept::new(
            "Rain",
            [
                0.00, 0.00, 0.00, 0.90, 0.30, 0.30, 0.00, 0.05, 0.10, 0.00, 0.70, 0.00, 0.90, 0.70,
                0.00, 0.00,
            ],
        ),
        RawConcept::new(
            "WetGround",
            [
                0.00, 0.00, 0.00, 0.60, 0.20, 0.00, 0.00, 0.05, 0.20, 0.00, 0.00, 0.00, 0.80, 0.30,
                0.00, 0.00,
            ],
        ),
        RawConcept::new(
            "Slippery",
            [
                0.00, 0.00, 0.00, 0.50, 0.15, 0.00, 0.00, 0.05, 0.40, 0.00, 0.10, 0.00, 0.70, 0.20,
                0.00, 0.00,
            ],
        ),
        RawConcept::new(
            "Caution",
            [
                0.00, 0.00, 0.00, 0.30, 0.00, 0.00, 0.00, 0.10, 0.70, 0.00, 0.05, 0.00, 0.30, 0.10,
                0.00, 0.00,
            ],
        ),
        // Incoherent path reference (not in chain, just for comparison)
        RawConcept::new(
            "Database",
            [
                0.00, 0.00, 0.90, 0.00, 0.10, 0.00, 0.00, 0.85, 0.60, 0.00, 0.00, 0.95, 0.00, 0.00,
                0.40, 0.00,
            ],
        ),
        RawConcept::new(
            "Banana",
            [
                0.00, 0.00, 0.00, 0.40, 0.15, 0.00, 0.00, 0.05, 0.00, 0.95, 0.00, 0.00, 0.20, 0.00,
                0.00, 0.90,
            ],
        ),
    ])
}

/// Cross-language dataset: Dog in 5 languages + unrelated anchor
pub fn build_r5_crosslang_dataset() -> DiscoveryEngine {
    DiscoveryEngine::new(vec![
        RawConcept::new(
            "Dog",
            [
                0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "犬",
            [
                0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Hund",
            [
                0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Perro",
            [
                0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Chien",
            [
                0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Database",
            [
                0.00, 0.00, 0.90, 0.00, 0.10, 0.00, 0.00, 0.85, 0.60, 0.00, 0.00, 0.95, 0.00, 0.00,
                0.40, 0.00,
            ],
        ),
    ])
}

/// Symbol dataset: Dog + Japanese + emoji + unrelated
pub fn build_r5_symbol_dataset() -> DiscoveryEngine {
    DiscoveryEngine::new(vec![
        RawConcept::new(
            "Dog",
            [
                0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "犬",
            [
                0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "🐕",
            [
                0.90, 0.00, 0.00, 0.05, 0.35, 0.55, 0.90, 0.10, 0.00, 0.95, 0.70, 0.00, 0.00, 0.00,
                0.00, 0.90,
            ],
        ),
        RawConcept::new(
            "Database",
            [
                0.00, 0.00, 0.90, 0.00, 0.10, 0.00, 0.00, 0.85, 0.60, 0.00, 0.00, 0.95, 0.00, 0.00,
                0.40, 0.00,
            ],
        ),
    ])
}
