use std::collections::BTreeMap;

use runtime::search::{
    BeamSearch, BranchNode, ExpandedParent, Expansion, SearchConfig, TransitionSignature,
};

fn config() -> SearchConfig {
    SearchConfig {
        beam_width: 2,
        quantization_unit: 2,
        global_window: 8,
        fallback_stagnation_steps: 1,
        fallback_extra_width: 1,
        exploration_injection_stride: 2,
        enable_depth_diversification: true,
        dominance_top_k: 2,
        max_visited_records: 64,
    }
}

fn root(state: &str, score_raw: i64) -> Expansion<String> {
    Expansion {
        transition_signature: TransitionSignature::from_fields([("kind", "root"), ("state", state)]),
        state: state.to_string(),
        state_hash: state.to_string(),
        score_raw,
        is_goal: false,
    }
}

fn child(state: &str, edge: &str, score_raw: i64, is_goal: bool) -> Expansion<String> {
    Expansion {
        transition_signature: TransitionSignature::from_fields([("edge", edge), ("state", state)]),
        state: state.to_string(),
        state_hash: state.to_string(),
        score_raw,
        is_goal,
    }
}

fn transition_signature(fields: [(&str, &str); 2]) -> TransitionSignature {
    TransitionSignature::from_fields(fields)
}

fn expand_non_monotonic(node: &BranchNode<String>) -> Vec<Expansion<String>> {
    match node.state.as_str() {
        "root" => vec![
            child("greedy", "root->greedy", 10, false),
            child("dip", "root->dip", 3, false),
        ],
        "greedy" => vec![
            child("greedy_goal", "greedy->goal", 11, true),
            child("greedy_dead", "greedy->dead", 9, false),
        ],
        "dip" => vec![
            child("optimal_goal", "dip->goal", 20, true),
            child("revisit_greedy", "dip->greedy", 8, false),
        ],
        _ => Vec::new(),
    }
}

#[test]
fn non_monotonic_path_reaches_optimal_goal() {
    let mut search = BeamSearch::new(config(), vec![root("root", 0)]);

    let first = search.step(expand_non_monotonic);
    assert_eq!(first.beam.len(), 2);
    assert!(first.beam.iter().any(|node| node.state == "dip"));

    let second = search.step(expand_non_monotonic);
    let best = second.best_goal.expect("goal should be found");

    assert_eq!(best.state, "optimal_goal");
    assert_eq!(best.score_raw, 20);
}

#[test]
fn dominance_pruning_keeps_better_shallower_state() {
    let mut search = BeamSearch::new(config(), vec![root("root", 0)]);
    let first = search.step(expand_non_monotonic);
    let dip = first
        .beam
        .iter()
        .find(|node| node.state == "dip")
        .cloned()
        .expect("dip branch should survive");

    let revisit = ExpandedParent {
        parent: dip,
        children: vec![
            child("greedy", "dip->greedy-worse", 8, false),
            child("optimal_goal", "dip->goal", 20, true),
        ],
    };

    let outcome = search.step_from_expanded(vec![revisit]);

    assert_eq!(outcome.pruned_children, 1);
    assert!(outcome.beam.iter().any(|node| node.state == "optimal_goal"));
    assert!(
        !outcome
            .beam
            .iter()
            .any(|node| node.transition_signature == transition_signature([("edge", "dip->greedy-worse"), ("state", "greedy")]))
    );
}

#[test]
fn k_best_dominance_prevents_incorrect_prune() {
    let mut search = BeamSearch::new(config(), vec![root("root", 0)]);
    let first = search.step(|node| match node.state.as_str() {
        "root" => vec![
            child("shared", "root->shared-a", 10, false),
            child("shared", "root->shared-b", 9, false),
        ],
        _ => Vec::new(),
    });

    assert_eq!(first.beam.len(), 1);

    let shared_parent = first.beam[0].clone();
    let second = search.step_from_expanded(vec![ExpandedParent {
        parent: shared_parent,
        children: vec![child("shared", "shared->shared-low", 9, false)],
    }]);

    assert_eq!(second.pruned_children, 0);
}

#[test]
fn merge_result_is_identical_for_different_parallel_completion_orders() {
    let mut search_a = BeamSearch::new(config(), vec![root("root", 0)]);
    let first = search_a.step(expand_non_monotonic);
    let mut parents: Vec<_> = first.beam.to_vec();
    parents.sort_by(|left, right| left.branch_id.cmp(&right.branch_id));

    let expanded_in_order: Vec<_> = parents
        .iter()
        .cloned()
        .map(|parent| ExpandedParent {
            children: expand_non_monotonic(&parent),
            parent,
        })
        .collect();

    let mut reversed = expanded_in_order.clone();
    reversed.reverse();

    let snapshot = search_a.snapshot();
    let mut search_b = BeamSearch::from_snapshot(config(), snapshot.clone());
    let outcome_a = search_a.step_from_expanded(expanded_in_order);
    let outcome_b = search_b.step_from_expanded(reversed);

    assert_eq!(outcome_a.beam, outcome_b.beam);
    assert_eq!(outcome_a.best_goal, outcome_b.best_goal);
}

#[test]
fn snapshot_resume_replays_identically() {
    let mut search = BeamSearch::new(config(), vec![root("root", 0)]);
    let _ = search.step(expand_non_monotonic);
    let snapshot = search.snapshot();

    let mut resumed = BeamSearch::from_snapshot(config(), snapshot);
    let outcome_original = search.step(expand_non_monotonic);
    let outcome_resumed = resumed.step(expand_non_monotonic);

    assert_eq!(outcome_original.beam, outcome_resumed.beam);
    assert_eq!(outcome_original.best_goal, outcome_resumed.best_goal);
    assert_eq!(search.snapshot(), resumed.snapshot());
}

#[test]
fn window_safety_keeps_active_ancestors() {
    let mut search = BeamSearch::new(
        SearchConfig {
            global_window: 0,
            exploration_injection_stride: 0,
            ..config()
        },
        vec![root("root", 0)],
    );

    let chain: BTreeMap<&str, Vec<Expansion<String>>> = BTreeMap::from([
        ("root", vec![child("d1", "root->d1", 1, false)]),
        ("d1", vec![child("d2", "d1->d2", 2, false)]),
        ("d2", vec![child("d3", "d2->d3", 3, false)]),
    ]);

    let expander =
        |node: &BranchNode<String>| chain.get(node.state.as_str()).cloned().unwrap_or_default();

    let _ = search.step(expander);
    let _ = search.step(expander);
    let _ = search.step(expander);
    let snapshot = search.snapshot();

    assert!(snapshot.active_lineage_set.contains("root"));
    assert!(snapshot.global_visited.contains_key("d1"));
    assert!(snapshot.global_visited.contains_key("d2"));
    assert!(snapshot.global_visited.contains_key("d3"));
}

#[test]
fn transition_signature_normalization_keeps_branch_ids_identical() {
    let mut search = BeamSearch::new(config(), vec![root("root", 0)]);
    let first = search.step(|node| match node.state.as_str() {
        "root" => vec![
            Expansion {
                transition_signature: TransitionSignature::from_fields([
                    ("kind", "move"),
                    ("target", "same"),
                ]),
                state: "same".to_string(),
                state_hash: "same".to_string(),
                score_raw: 1,
                is_goal: false,
            },
            Expansion {
                transition_signature: TransitionSignature::from_fields([
                    ("target", "same"),
                    ("kind", "move"),
                ]),
                state: "same".to_string(),
                state_hash: "same".to_string(),
                score_raw: 1,
                is_goal: false,
            },
        ],
        _ => Vec::new(),
    });

    assert_eq!(first.beam.len(), 1);
    assert_eq!(first.beam[0].transition_signature.as_str(), "kind=move|target=same");
}

#[test]
fn parallel_stress_is_stable_across_parent_orderings() {
    let stress_config = SearchConfig {
        beam_width: 3,
        fallback_extra_width: 0,
        exploration_injection_stride: 0,
        ..config()
    };
    let mut search_a = BeamSearch::new(stress_config.clone(), vec![root("root", 0)]);

    let first = search_a.step(|node| match node.state.as_str() {
        "root" => vec![
            child("a", "root->a", 5, false),
            child("b", "root->b", 4, false),
            child("c", "root->c", 3, false),
        ],
        _ => Vec::new(),
    });

    let mut ordered: Vec<_> = first
        .beam
        .iter()
        .cloned()
        .map(|parent| ExpandedParent {
            children: vec![
                child(&format!("{}1", parent.state), "x", parent.score_raw + 1, false),
                child(&format!("{}2", parent.state), "y", parent.score_raw + 2, false),
            ],
            parent,
        })
        .collect();
    let mut reversed = ordered.clone();
    reversed.reverse();

    let snapshot = search_a.snapshot();
    let mut search_b = BeamSearch::from_snapshot(stress_config, snapshot);
    let outcome_a = search_a.step_from_expanded(std::mem::take(&mut ordered));
    let outcome_b = search_b.step_from_expanded(reversed);

    assert_eq!(outcome_a.beam, outcome_b.beam);
}
