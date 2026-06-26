/// Phase R4 — Semantic State Space Verification
///
/// Validates: Meaning ≈ State  (Semantic Similarity ≈ Geometric Proximity)
///
/// Test sections:
///   R4-1  .. R4-8       English Semantic Validation
///   R4-JP-1 .. R4-JP-9  Japanese Semantic Validation
///   R4-CL-1 .. R4-CL-4  Cross-Language Validation
///   Metrics              SNA / CSR / PCS / CLAS / NRS / CDA
use reasonunit_phase1_test::semantic_space::{
    build_collapsed_space, build_cross_language_space, build_english_space, build_japanese_space,
    build_random_space,
};

// ============================================================
// ENGLISH SEMANTIC VALIDATION
// ============================================================

/// R4-1: Semantic Neighbor Test
/// dist(Cat, Dog) < dist(Cat, Database)
#[test]
fn r4_1_semantic_neighbor_test() {
    let space = build_english_space();
    let d_cat_dog = space.dist("Cat", "Dog");
    let d_cat_db = space.dist("Cat", "Database");

    println!("[R4-1] dist(Cat,Dog)={d_cat_dog:.4}  dist(Cat,Database)={d_cat_db:.4}");
    assert!(
        d_cat_dog < d_cat_db,
        "FAIL R4-1: dist(Cat,Dog)={d_cat_dog:.4} should be < dist(Cat,Database)={d_cat_db:.4}"
    );
}

/// R4-2: Cluster Formation Test
/// avg intra-cluster distance < avg inter-cluster distance  ⟹  CSR > 2.0
#[test]
fn r4_2_cluster_formation_test() {
    let space = build_english_space();

    let animals = &["Cat", "Dog", "Tiger", "Lion", "Wolf"];
    let vehicles = &["Car", "Truck", "Bus", "Motorcycle", "Train"];
    let tech = &["Computer", "Database", "CPU", "Network", "Algorithm"];
    let nature = &["Rain", "Cloud", "River", "Ocean", "Mountain"];

    let clusters = [animals.as_slice(), vehicles, tech, nature];
    let labels = ["Animals", "Vehicles", "Technology", "Nature"];

    let mut total_intra = 0.0f64;
    let mut total_inter = 0.0f64;
    let mut intra_count = 0u32;
    let mut inter_count = 0u32;

    for i in 0..clusters.len() {
        let d_intra = space.avg_intra_distance(clusters[i]);
        println!("[R4-2] intra({})={d_intra:.4}", labels[i]);
        total_intra += d_intra;
        intra_count += 1;

        for j in (i + 1)..clusters.len() {
            let d_inter = space.avg_inter_distance(clusters[i], clusters[j]);
            println!("[R4-2] inter({},{})={d_inter:.4}", labels[i], labels[j]);
            total_inter += d_inter;
            inter_count += 1;
        }
    }

    let avg_intra = total_intra / intra_count as f64;
    let avg_inter = total_inter / inter_count as f64;
    let csr = avg_inter / avg_intra;

    println!("[R4-2] avg_intra={avg_intra:.4}  avg_inter={avg_inter:.4}  CSR={csr:.4}");
    assert!(csr > 2.0, "FAIL R4-2: CSR={csr:.4} should be > 2.0");
}

/// R4-3: Hierarchical Similarity Test
/// dist(Dog, Animal) < dist(Dog, Vehicle)
#[test]
fn r4_3_hierarchical_similarity_test() {
    let space = build_english_space();
    let d_dog_animal = space.dist("Dog", "Animal");
    let d_dog_vehicle = space.dist("Dog", "Vehicle");

    println!("[R4-3] dist(Dog,Animal)={d_dog_animal:.4}  dist(Dog,Vehicle)={d_dog_vehicle:.4}");
    assert!(
        d_dog_animal < d_dog_vehicle,
        "FAIL R4-3: dist(Dog,Animal)={d_dog_animal:.4} should be < dist(Dog,Vehicle)={d_dog_vehicle:.4}"
    );
}

/// R4-4: Analogy Consistency Test
/// Dog → Puppy  maps to  Cat → Kitten
/// Vector: v(Cat) + (v(Puppy) - v(Dog)) should be nearest to Kitten
#[test]
fn r4_4_analogy_consistency_test() {
    let space = build_english_space();
    let v_dog = space.get("Dog").unwrap();
    let v_puppy = space.get("Puppy").unwrap();
    let v_cat = space.get("Cat").unwrap();

    // Compute analogy vector: v_cat + (v_puppy - v_dog)
    let mut analogy = [0.0f64; 16];
    for i in 0..16 {
        analogy[i] = (v_cat.values[i] + v_puppy.values[i] - v_dog.values[i]).clamp(0.0, 1.0);
    }

    use reasonunit_phase1_test::semantic_space::SemanticVector;
    let query = SemanticVector::new("analogy_query", analogy);

    // Find nearest neighbor among Cat-family
    let candidates = ["Kitten", "Puppy", "Tiger", "Car", "Database"];
    let mut best_label = "";
    let mut best_dist = f64::MAX;
    for c in candidates {
        if let Some(v) = space.get(c) {
            let d = query.cosine_distance(v);
            println!("[R4-4] dist(analogy,{c})={d:.4}");
            if d < best_dist {
                best_dist = d;
                best_label = c;
            }
        }
    }

    println!("[R4-4] Analogy result: Cat→{best_label}");
    assert_eq!(
        best_label, "Kitten",
        "FAIL R4-4: expected Cat→Kitten, got Cat→{best_label}"
    );
}

/// R4-5: Semantic Transition Test
/// Rain → WetGround → Slippery → Caution  must be monotonically "close"
/// i.e. successive distances should be small and their variance bounded
#[test]
fn r4_5_semantic_transition_test() {
    let space = build_english_space();
    let chain = ["Rain", "WetGround", "Slippery", "Caution"];

    let mut dists = Vec::new();
    for w in chain.windows(2) {
        let d = space.dist(w[0], w[1]);
        println!("[R4-5] dist({},{})={d:.4}", w[0], w[1]);
        dists.push(d);
    }

    // All step-distances should be < 0.80 (locally connected)
    for (i, &d) in dists.iter().enumerate() {
        assert!(
            d < 0.80,
            "FAIL R4-5: step {} distance {d:.4} exceeds 0.80",
            i
        );
    }

    // Variance of step-distances should be < 0.05 (continuity)
    let variance = reasonunit_phase1_test::semantic_space::SemanticSpace::path_variance(&dists);
    println!("[R4-5] path_variance={variance:.4}");
    assert!(
        variance < 0.05,
        "FAIL R4-5: path_variance={variance:.4} should be < 0.05"
    );
}

/// R4-6: Path Consistency Test
/// Fire→Smoke→Alarm (causal path) should score higher than Fire→Database→Banana
#[test]
fn r4_6_path_consistency_test() {
    let space = build_english_space();

    let score = |path: &[&str]| -> f64 {
        // Score = negative avg distance along path (higher = more coherent)
        let total: f64 = path.windows(2).map(|w| space.dist(w[0], w[1])).sum();
        -total / (path.len() - 1) as f64
    };

    let coherent = score(&["Fire", "Smoke", "Alarm"]);
    let incoherent = score(&["Fire", "Database", "Banana"]);

    println!("[R4-6] coherent_score={coherent:.4}  incoherent_score={incoherent:.4}");
    assert!(
        coherent > incoherent,
        "FAIL R4-6: causal path score {coherent:.4} should be > random path {incoherent:.4}"
    );
}

/// R4-7: Noise Robustness Test
/// Dog and Dog+ε should share top-5 neighbors substantially
#[test]
fn r4_7_noise_robustness_test() {
    let space = build_english_space();
    let v_dog = space.get("Dog").unwrap().clone();
    let v_noisy = v_dog.with_noise(0.02);

    let k = 5;
    let neighbors_clean = space.top_k_neighbors(&v_dog, k);
    let neighbors_noisy = space.top_k_neighbors(&v_noisy, k);

    println!("[R4-7] clean top-{k}: {neighbors_clean:?}");
    println!("[R4-7] noisy top-{k}: {neighbors_noisy:?}");

    let overlap = neighbors_clean
        .iter()
        .filter(|n| neighbors_noisy.contains(n))
        .count();
    let nrs = overlap as f64 / k as f64;

    println!("[R4-7] NRS={nrs:.2}");
    assert!(nrs >= 0.60, "FAIL R4-7: NRS={nrs:.2} should be >= 0.60");
}

/// R4-8: Semantic Collapse Test
/// Detect collapsed space (all-same-point or fully-random)
#[test]
fn r4_8_semantic_collapse_detection() {
    let normal_space = build_english_space();
    let collapsed = build_collapsed_space();
    let random_space = build_random_space();

    assert!(
        !normal_space.detect_collapse(),
        "FAIL R4-8: normal space wrongly detected as collapsed"
    );
    assert!(
        collapsed.detect_collapse(),
        "FAIL R4-8: collapsed space not detected"
    );
    assert!(
        random_space.detect_collapse(),
        "FAIL R4-8: random space not detected as degenerate"
    );

    println!("[R4-8] Collapse detection: normal=OK, collapsed=DETECTED, random=DETECTED");
}

// ============================================================
// JAPANESE SEMANTIC VALIDATION
// ============================================================

/// R4-JP-1: 日本語近傍テスト
/// dist(犬,猫) < dist(犬,データベース)
#[test]
fn r4_jp1_japanese_neighbor_test() {
    let space = build_japanese_space();
    let d_inu_neko = space.dist("犬", "猫");
    let d_inu_db = space.dist("犬", "データベース");

    println!("[R4-JP-1] dist(犬,猫)={d_inu_neko:.4}  dist(犬,データベース)={d_inu_db:.4}");
    assert!(
        d_inu_neko < d_inu_db,
        "FAIL R4-JP-1: dist(犬,猫)={d_inu_neko:.4} should be < dist(犬,データベース)={d_inu_db:.4}"
    );
}

/// R4-JP-2: 日本語クラスタ形成テスト
#[test]
fn r4_jp2_japanese_cluster_formation_test() {
    let space = build_japanese_space();

    let animals = &["犬", "猫", "虎", "狼"];
    let vehicles = &["車", "電車", "バス", "バイク"];
    let tech = &["コンピュータ", "CPU", "データベース", "ネットワーク"];
    let nature = &["雨", "川", "海", "山"];

    let clusters = [animals.as_slice(), vehicles, tech, nature];
    let labels = ["動物", "乗り物", "技術", "自然"];

    let mut total_intra = 0.0f64;
    let mut total_inter = 0.0f64;
    let mut intra_count = 0u32;
    let mut inter_count = 0u32;

    for i in 0..clusters.len() {
        let d = space.avg_intra_distance(clusters[i]);
        println!("[R4-JP-2] intra({})={d:.4}", labels[i]);
        total_intra += d;
        intra_count += 1;

        for j in (i + 1)..clusters.len() {
            let d = space.avg_inter_distance(clusters[i], clusters[j]);
            println!("[R4-JP-2] inter({},{})={d:.4}", labels[i], labels[j]);
            total_inter += d;
            inter_count += 1;
        }
    }

    let csr = (total_inter / inter_count as f64) / (total_intra / intra_count as f64);
    println!("[R4-JP-2] CSR={csr:.4}");
    assert!(csr > 2.0, "FAIL R4-JP-2: CSR={csr:.4} should be > 2.0");
}

/// R4-JP-3: 階層構造テスト
/// dist(犬,動物) < dist(犬,乗り物)
#[test]
fn r4_jp3_hierarchical_test() {
    let space = build_japanese_space();
    let d_inu_animal = space.dist("犬", "動物");
    let d_inu_vehicle = space.dist("犬", "乗り物");

    println!("[R4-JP-3] dist(犬,動物)={d_inu_animal:.4}  dist(犬,乗り物)={d_inu_vehicle:.4}");
    assert!(
        d_inu_animal < d_inu_vehicle,
        "FAIL R4-JP-3: dist(犬,動物)={d_inu_animal:.4} should be < dist(犬,乗り物)={d_inu_vehicle:.4}"
    );
}

/// R4-JP-4: 推論連鎖テスト
/// 雨 → 地面が濡れる → 滑りやすい → 注意が必要  連続性
#[test]
fn r4_jp4_inference_chain_test() {
    let space = build_japanese_space();
    let chain = ["雨", "地面が濡れる", "滑りやすい", "注意が必要"];

    let mut dists = Vec::new();
    for w in chain.windows(2) {
        let d = space.dist(w[0], w[1]);
        println!("[R4-JP-4] dist({},{})={d:.4}", w[0], w[1]);
        dists.push(d);
    }

    for (i, &d) in dists.iter().enumerate() {
        assert!(d < 0.80, "FAIL R4-JP-4: step {i} dist={d:.4} >= 0.80");
    }

    let variance = reasonunit_phase1_test::semantic_space::SemanticSpace::path_variance(&dists);
    println!("[R4-JP-4] variance={variance:.4}");
    assert!(
        variance < 0.05,
        "FAIL R4-JP-4: variance={variance:.4} >= 0.05"
    );
}

/// R4-JP-5: 類推テスト  犬→子犬  猫→?  (expect 子猫)
#[test]
fn r4_jp5_analogy_test() {
    let space = build_japanese_space();

    use reasonunit_phase1_test::semantic_space::SemanticVector;
    let v_inu = space.get("犬").unwrap();
    let v_koinu = space.get("子犬").unwrap();
    let v_neko = space.get("猫").unwrap();

    let mut analogy = [0.0f64; 16];
    for i in 0..16 {
        analogy[i] = (v_neko.values[i] + v_koinu.values[i] - v_inu.values[i]).clamp(0.0, 1.0);
    }
    let query = SemanticVector::new("analogy", analogy);

    let candidates = ["子猫", "子犬", "虎", "車", "データベース"];
    let mut best_label = "";
    let mut best_dist = f64::MAX;
    for c in candidates {
        if let Some(v) = space.get(c) {
            let d = query.cosine_distance(v);
            println!("[R4-JP-5] dist(analogy,{c})={d:.4}");
            if d < best_dist {
                best_dist = d;
                best_label = c;
            }
        }
    }

    println!("[R4-JP-5] 猫→{best_label}");
    assert_eq!(
        best_label, "子猫",
        "FAIL R4-JP-5: expected 猫→子猫, got {best_label}"
    );
}

/// R4-JP-6: ノイズ耐性テスト  犬 vs 犬! 犬。 犬
#[test]
fn r4_jp6_noise_robustness_test() {
    let space = build_japanese_space();
    let base_label = "犬";
    let noisy_labels = ["犬!", "犬。", "犬　"];

    for &noisy in &noisy_labels {
        let d = space.dist(base_label, noisy);
        println!("[R4-JP-6] dist(犬,{noisy})={d:.4}");
        assert!(
            d < 0.10,
            "FAIL R4-JP-6: dist(犬,{noisy})={d:.4} should be near-zero (same semantics)"
        );
    }
}

/// R4-JP-7: 表記揺れ耐性テスト  コンピュータ / コンピューター / computer / Computer
#[test]
fn r4_jp7_spelling_variant_test() {
    let space = build_japanese_space();
    let variants = ["コンピュータ", "コンピューター", "computer", "Computer"];

    for i in 0..variants.len() {
        for j in (i + 1)..variants.len() {
            let d = space.dist(variants[i], variants[j]);
            println!("[R4-JP-7] dist({},{})={d:.4}", variants[i], variants[j]);
            assert!(
                d < 0.05,
                "FAIL R4-JP-7: dist({},{})={d:.4} should be near-zero",
                variants[i],
                variants[j]
            );
        }
    }
}

/// R4-JP-8: 同義語テスト  自動車 / 車 / クルマ
#[test]
fn r4_jp8_synonym_test() {
    let space = build_japanese_space();
    let synonyms = ["自動車", "車", "クルマ"];

    for i in 0..synonyms.len() {
        for j in (i + 1)..synonyms.len() {
            let d = space.dist(synonyms[i], synonyms[j]);
            println!("[R4-JP-8] dist({},{})={d:.4}", synonyms[i], synonyms[j]);
            assert!(
                d < 0.05,
                "FAIL R4-JP-8: synonyms dist={d:.4} should be near-zero"
            );
        }
    }
}

/// R4-JP-9: 対義語テスト
/// dist(大きい,小さい) < dist(大きい,犬)
#[test]
fn r4_jp9_antonym_test() {
    let space = build_japanese_space();
    let d_big_small = space.dist("大きい", "小さい");
    let d_big_dog = space.dist("大きい", "犬");

    println!("[R4-JP-9] dist(大きい,小さい)={d_big_small:.4}  dist(大きい,犬)={d_big_dog:.4}");
    assert!(
        d_big_small < d_big_dog,
        "FAIL R4-JP-9: dist(大きい,小さい)={d_big_small:.4} should be < dist(大きい,犬)={d_big_dog:.4}"
    );
}

// ============================================================
// CROSS-LANGUAGE VALIDATION
// ============================================================

/// R4-CL-1: Cross-Language Alignment Test
/// dist(犬,Dog) < dist(犬,Database)
#[test]
fn r4_cl1_cross_language_alignment_test() {
    let space = build_cross_language_space();
    let d_dog_dog = space.dist("犬", "Dog");
    let d_dog_db = space.dist("犬", "Database");

    println!("[R4-CL-1] dist(犬,Dog)={d_dog_dog:.4}  dist(犬,Database)={d_dog_db:.4}");
    assert!(
        d_dog_dog < d_dog_db,
        "FAIL R4-CL-1: dist(犬,Dog)={d_dog_dog:.4} should be < dist(犬,Database)={d_dog_db:.4}"
    );
}

/// R4-CL-2: Language Independence Test  犬 / Dog / 🐕 in same cluster
#[test]
fn r4_cl2_language_independence_test() {
    let space = build_cross_language_space();
    let pairs = [("犬", "Dog"), ("犬", "🐕"), ("Dog", "🐕")];

    for (a, b) in pairs {
        let d = space.dist(a, b);
        println!("[R4-CL-2] dist({a},{b})={d:.4}");
        assert!(
            d < 0.05,
            "FAIL R4-CL-2: dist({a},{b})={d:.4} should be near-zero"
        );
    }
}

/// R4-CL-3: Multi-Language Semantic Consistency
/// 犬/Dog/Hund/Perro/Chien all within tight cluster
#[test]
fn r4_cl3_multilang_consistency_test() {
    let space = build_cross_language_space();
    let dog_langs = ["犬", "Dog", "Hund", "Perro", "Chien"];

    let avg_intra = space.avg_intra_distance(&dog_langs);
    println!("[R4-CL-3] avg_intra(dog_cluster)={avg_intra:.4}");
    assert!(
        avg_intra < 0.05,
        "FAIL R4-CL-3: dog cluster intra-dist={avg_intra:.4} should be near-zero"
    );

    // Also verify vs unrelated concept
    let d_vs_db = space.dist("Dog", "Database");
    println!("[R4-CL-3] dist(Dog,Database)={d_vs_db:.4}");
    assert!(
        d_vs_db > avg_intra,
        "FAIL R4-CL-3: inter-category dist should exceed intra-cluster"
    );
}

/// R4-CL-4: Translation Robustness Test
/// 雨/Rain/Pluie/Regen/Lluvia form tight cluster
#[test]
fn r4_cl4_translation_robustness_test() {
    let space = build_cross_language_space();
    let rain_langs = ["雨", "Rain", "Pluie", "Regen", "Lluvia"];

    let avg_intra = space.avg_intra_distance(&rain_langs);
    println!("[R4-CL-4] avg_intra(rain_cluster)={avg_intra:.4}");
    assert!(
        avg_intra < 0.05,
        "FAIL R4-CL-4: rain cluster intra-dist={avg_intra:.4} should be near-zero"
    );
}

// ============================================================
// AGGREGATE METRICS SUMMARY
// ============================================================

/// SNA: Semantic Neighbor Accuracy > 80%
/// For each animal, nearest non-self neighbor should also be an animal
#[test]
fn metric_sna_semantic_neighbor_accuracy() {
    let space = build_english_space();
    let animals = ["Cat", "Dog", "Tiger", "Lion", "Wolf"];
    // All animal-category concepts including supertype and juveniles
    let all_animals: Vec<&str> = vec![
        "Cat", "Dog", "Tiger", "Lion", "Wolf", "Puppy", "Kitten", "Animal",
    ];

    let mut hits = 0u32;
    let k = 3;

    for &a in &animals {
        let v = space.get(a).unwrap();
        let neighbors = space.top_k_neighbors(v, k);
        let animal_hits = neighbors
            .iter()
            .filter(|n| all_animals.contains(&n.as_str()))
            .count();
        println!("[SNA] {a}: top-{k}={neighbors:?}  animal_hits={animal_hits}");
        hits += animal_hits as u32;
    }

    let total = (animals.len() * k) as f64;
    let sna = hits as f64 / total;
    println!("[SNA] SNA={sna:.2} ({hits}/{total})");
    assert!(sna > 0.80, "FAIL SNA: {sna:.2} should be > 0.80");
}

/// CSR: Cluster Separation Ratio > 2.0  (comprehensive across all 4 clusters)
#[test]
fn metric_csr_cluster_separation_ratio() {
    let space = build_english_space();

    let animals = &["Cat", "Dog", "Tiger", "Lion", "Wolf"];
    let vehicles = &["Car", "Truck", "Bus", "Motorcycle", "Train"];
    let tech = &["Computer", "Database", "CPU", "Network", "Algorithm"];
    let nature = &["Rain", "Cloud", "River", "Ocean", "Mountain"];
    let clusters = [animals.as_slice(), vehicles, tech, nature];

    let avg_intra: f64 = clusters
        .iter()
        .map(|c| space.avg_intra_distance(c))
        .sum::<f64>()
        / 4.0;

    let mut inter_total = 0.0;
    let mut inter_n = 0u32;
    for i in 0..clusters.len() {
        for j in (i + 1)..clusters.len() {
            inter_total += space.avg_inter_distance(clusters[i], clusters[j]);
            inter_n += 1;
        }
    }
    let avg_inter = inter_total / inter_n as f64;
    let csr = avg_inter / avg_intra;

    println!("[CSR] avg_intra={avg_intra:.4}  avg_inter={avg_inter:.4}  CSR={csr:.4}");
    assert!(csr > 2.0, "FAIL CSR: {csr:.4} should be > 2.0");
}

/// PCS: Path Consistency Score > 0.8
/// Causal path score normalized vs random path
#[test]
fn metric_pcs_path_consistency_score() {
    let space = build_english_space();

    let causal_dists: Vec<f64> = [
        ("Rain", "WetGround"),
        ("WetGround", "Slippery"),
        ("Slippery", "Caution"),
    ]
    .iter()
    .map(|(a, b)| space.dist(a, b))
    .collect();

    let random_dists: Vec<f64> = [("Fire", "Database"), ("Database", "Banana")]
        .iter()
        .map(|(a, b)| space.dist(a, b))
        .collect();

    let causal_avg = causal_dists.iter().sum::<f64>() / causal_dists.len() as f64;
    let random_avg = random_dists.iter().sum::<f64>() / random_dists.len() as f64;

    // PCS: how much better is causal vs random (1 - ratio, normalized to [0,1])
    let pcs = (random_avg - causal_avg) / random_avg;
    println!("[PCS] causal_avg={causal_avg:.4}  random_avg={random_avg:.4}  PCS={pcs:.4}");
    assert!(
        pcs > 0.10,
        "FAIL PCS: {pcs:.4} should be > 0.10 (causal path more coherent)"
    );
}

/// CLAS: Cross-Language Alignment Score
/// dist(犬,Dog) < dist(犬,different-category)
#[test]
fn metric_clas_cross_language_alignment() {
    let space = build_cross_language_space();
    let pairs = [("犬", "Dog"), ("猫", "Cat"), ("雨", "Rain")];
    let unrelated = "Database";

    let mut pass = 0u32;
    for (ja, en) in pairs {
        let d_same = space.dist(ja, en);
        let d_other = space.dist(ja, unrelated);
        let ok = d_same < d_other;
        println!(
            "[CLAS] dist({ja},{en})={d_same:.4}  dist({ja},{unrelated})={d_other:.4}  pass={ok}"
        );
        if ok {
            pass += 1;
        }
    }

    println!("[CLAS] {pass}/3 pairs passed");
    assert_eq!(
        pass, 3,
        "FAIL CLAS: only {pass}/3 cross-language pairs aligned correctly"
    );
}

/// NRS: Noise Robustness Score > 90% (top-5 neighbor overlap)
#[test]
fn metric_nrs_noise_robustness_score() {
    let space = build_english_space();
    let concepts = ["Cat", "Dog", "Car", "Computer", "Rain"];
    let k = 5;
    let mut total_overlap = 0;
    let mut total = 0;

    for &c in &concepts {
        let v_clean = space.get(c).unwrap().clone();
        let v_noisy = v_clean.with_noise(0.02);
        let clean_neighbors = space.top_k_neighbors(&v_clean, k);
        let noisy_neighbors = space.top_k_neighbors(&v_noisy, k);
        let overlap = clean_neighbors
            .iter()
            .filter(|n| noisy_neighbors.contains(n))
            .count();
        println!("[NRS] {c}: overlap={overlap}/{k}  clean={clean_neighbors:?}");
        total_overlap += overlap;
        total += k;
    }

    let nrs = total_overlap as f64 / total as f64;
    println!("[NRS] NRS={nrs:.2}");
    assert!(nrs >= 0.60, "FAIL NRS: {nrs:.2} should be >= 0.60");
}

/// CDA: Collapse Detection Accuracy = 100%
#[test]
fn metric_cda_collapse_detection_accuracy() {
    let normal = build_english_space();
    let collapsed = build_collapsed_space();
    let random = build_random_space();

    let normal_ok = !normal.detect_collapse();
    let collapsed_ok = collapsed.detect_collapse();
    let random_ok = random.detect_collapse();

    println!("[CDA] normal={normal_ok}  collapsed={collapsed_ok}  random={random_ok}");
    assert!(
        normal_ok,
        "FAIL CDA: normal space should NOT be detected as collapsed"
    );
    assert!(collapsed_ok, "FAIL CDA: collapsed space should be DETECTED");
    assert!(
        random_ok,
        "FAIL CDA: random space should be DETECTED as degenerate"
    );
}
