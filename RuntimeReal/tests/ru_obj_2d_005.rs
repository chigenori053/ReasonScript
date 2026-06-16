use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{
    GraphType, RelationType, StateType, TransitionType, UnitType,
};
use reasonscript_runtime_real::core::{ReasonUnit, State, Transition};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph};
use ndarray::array;
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::fs;
use std::path::Path;
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum SpatialRelation {
    LeftOf,
    RightOf,
    Above,
    Below,
    Inside,
    Contains,
}

impl SpatialRelation {
    fn as_str(&self) -> &'static str {
        match self {
            Self::LeftOf => "left_of",
            Self::RightOf => "right_of",
            Self::Above => "above",
            Self::Below => "below",
            Self::Inside => "inside",
            Self::Contains => "contains",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
struct Constraint {
    source: String,
    relation: SpatialRelation,
    target: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum ConflictType {
    DirectConflict,
    CyclicConflict,
    ContainmentConflict,
    GeometricConflict,
}

impl ConflictType {
    fn as_str(&self) -> &'static str {
        match self {
            Self::DirectConflict => "DirectConflict",
            Self::CyclicConflict => "CyclicConflict",
            Self::ContainmentConflict => "ContainmentConflict",
            Self::GeometricConflict => "GeometricConflict",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ConstraintConflict {
    conflict_type: ConflictType,
    description: String,
    nodes: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ValidationReport {
    passed: bool,
    checks: Vec<String>,
    conflicts: Vec<ConstraintConflict>,
}

#[test]
fn ru_obj_2d_005_detects_conflicting_spatial_worlds_before_layout() {
    let cases = vec![
        (
            "ST-011 Direct Horizontal Conflict",
            vec![
                ("Circle", "left_of", "Rectangle"),
                ("Circle", "right_of", "Rectangle"),
            ],
            ConflictType::DirectConflict,
        ),
        (
            "ST-012 Direct Vertical Conflict",
            vec![
                ("Triangle", "above", "Rectangle"),
                ("Triangle", "below", "Rectangle"),
            ],
            ConflictType::DirectConflict,
        ),
        (
            "ST-013 Containment Conflict",
            vec![
                ("Star", "inside", "Rectangle"),
                ("Rectangle", "inside", "Star"),
            ],
            ConflictType::ContainmentConflict,
        ),
        (
            "ST-014 Ordering Cycle",
            vec![("A", "left_of", "B"), ("B", "left_of", "C"), ("C", "left_of", "A")],
            ConflictType::CyclicConflict,
        ),
        (
            "ST-015 Containment Cycle",
            vec![("A", "inside", "B"), ("B", "inside", "C"), ("C", "inside", "A")],
            ConflictType::ContainmentConflict,
        ),
        (
            "CF-005 Above Cycle",
            vec![("A", "above", "B"), ("B", "above", "C"), ("C", "above", "A")],
            ConflictType::CyclicConflict,
        ),
        (
            "CF-006 Self Containment",
            vec![("Rectangle", "inside", "Rectangle")],
            ConflictType::ContainmentConflict,
        ),
        (
            "CF-008 Containment Ordering Contradiction",
            vec![("A", "inside", "B"), ("B", "left_of", "A")],
            ConflictType::GeometricConflict,
        ),
    ];

    let mut reports = Vec::new();
    let mut graphs = Vec::new();
    for (case_name, relations, expected_type) in cases {
        let graph = build_constraint_graph(relations);
        let constraints = extract_constraints(&graph).expect("constraints must be extracted");
        let report = validate_constraint_graph(&constraints);
        let repeated_report = validate_constraint_graph(&constraints);

        assert_eq!(report, repeated_report, "{case_name} must be deterministic");
        assert!(!report.passed, "{case_name} must reject the world");
        assert!(
            report
                .conflicts
                .iter()
                .any(|conflict| conflict.conflict_type == expected_type),
            "{case_name} must include expected conflict type"
        );
        assert!(
            !report.conflicts[0].description.is_empty(),
            "{case_name} must explain the conflict"
        );

        reports.push((case_name.to_string(), report));
        graphs.push((case_name.to_string(), constraints));
    }

    let artifact_dir = Path::new("artifacts/ru_obj_2d_005");
    fs::create_dir_all(artifact_dir).expect("artifact directory must be created");
    let scene_json_path = artifact_dir.join("scene.json");
    let scene_png_path = artifact_dir.join("scene.png");
    let _ = fs::remove_file(&scene_json_path);
    let _ = fs::remove_file(&scene_png_path);

    fs::write(
        artifact_dir.join("constraint_graph.json"),
        constraint_graph_json(&graphs),
    )
    .expect("constraint_graph.json must be generated");
    fs::write(
        artifact_dir.join("validation_report.json"),
        validation_report_json(&reports),
    )
    .expect("validation_report.json must be generated");

    assert!(artifact_dir.join("constraint_graph.json").exists());
    assert!(artifact_dir.join("validation_report.json").exists());
    assert!(
        !scene_json_path.exists(),
        "scene.json must not be generated for invalid worlds"
    );
    assert!(
        !scene_png_path.exists(),
        "scene.png must not be generated for invalid worlds"
    );
}

fn build_constraint_graph(relations: Vec<(&str, &str, &str)>) -> ReasonGraph {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);
    let mut nodes = HashMap::new();

    for (source, _, target) in &relations {
        for name in [*source, *target] {
            nodes
                .entry(name.to_string())
                .or_insert_with(|| add_object_node(&mut graph, name));
        }
    }

    for (source, relation, target) in relations {
        let source_id = *nodes.get(source).expect("source node must exist");
        let target_id = *nodes.get(target).expect("target node must exist");
        add_relation(&mut graph, source_id, target_id, relation);
    }

    graph
}

fn add_object_node(graph: &mut ReasonGraph, name: &str) -> Uuid {
    let state = State::new(
        StateType::Object,
        ReasonUnit::new(name, UnitType::Composite, array![0.0]),
    );
    let state_id = graph.add_state(state);
    graph.add_node(Node::new(state_id))
}

fn add_relation(graph: &mut ReasonGraph, source: Uuid, target: Uuid, relation_label: &str) {
    let transition_unit = ReasonUnit::new(relation_label, UnitType::Symbolic, array![1.0]);
    let transition = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Subsumption(transition_unit),
    );
    graph.add_edge(Edge::new(source, target, RelationType::Spatial, transition));
}

fn extract_constraints(graph: &ReasonGraph) -> Result<Vec<Constraint>, String> {
    let mut constraints = graph
        .edges
        .iter()
        .filter(|edge| edge.relation == RelationType::Spatial)
        .map(|edge| {
            Ok(Constraint {
                source: object_name(graph, edge.source)?,
                relation: parse_relation(relation_label(edge).as_str())?,
                target: object_name(graph, edge.target)?,
            })
        })
        .collect::<Result<Vec<_>, String>>()?;
    constraints.sort();
    Ok(constraints)
}

fn validate_constraint_graph(constraints: &[Constraint]) -> ValidationReport {
    let checks = constraints
        .iter()
        .map(|constraint| {
            format!(
                "{} {} {}",
                constraint.source,
                constraint.relation.as_str(),
                constraint.target
            )
        })
        .collect();
    let mut conflicts = Vec::new();

    conflicts.extend(detect_direct_conflicts(constraints));
    conflicts.extend(detect_self_containment(constraints));
    conflicts.extend(detect_ordering_cycles(
        constraints,
        SpatialRelation::LeftOf,
        ConflictType::CyclicConflict,
        "left_of ordering cycle detected",
    ));
    conflicts.extend(detect_ordering_cycles(
        constraints,
        SpatialRelation::Above,
        ConflictType::CyclicConflict,
        "above ordering cycle detected",
    ));
    conflicts.extend(detect_containment_cycles(constraints));
    conflicts.extend(detect_containment_ordering_conflicts(constraints));

    conflicts.sort_by(|a, b| {
        (
            a.conflict_type.as_str(),
            a.description.as_str(),
            a.nodes.join("|"),
        )
            .cmp(&(
                b.conflict_type.as_str(),
                b.description.as_str(),
                b.nodes.join("|"),
            ))
    });
    conflicts.dedup_by(|a, b| {
        a.conflict_type == b.conflict_type
            && a.description == b.description
            && a.nodes == b.nodes
    });

    ValidationReport {
        passed: conflicts.is_empty(),
        checks,
        conflicts,
    }
}

fn detect_direct_conflicts(constraints: &[Constraint]) -> Vec<ConstraintConflict> {
    let mut by_pair: BTreeMap<(&str, &str), BTreeSet<&SpatialRelation>> = BTreeMap::new();
    for constraint in constraints {
        by_pair
            .entry((&constraint.source, &constraint.target))
            .or_default()
            .insert(&constraint.relation);
    }

    let mut conflicts = Vec::new();
    for ((source, target), relations) in by_pair {
        if relations.contains(&SpatialRelation::LeftOf)
            && relations.contains(&SpatialRelation::RightOf)
        {
            conflicts.push(ConstraintConflict {
                conflict_type: ConflictType::DirectConflict,
                description: "left_of and right_of cannot both be true".to_string(),
                nodes: vec![source.to_string(), target.to_string()],
            });
        }
        if relations.contains(&SpatialRelation::Above) && relations.contains(&SpatialRelation::Below)
        {
            conflicts.push(ConstraintConflict {
                conflict_type: ConflictType::DirectConflict,
                description: "above and below cannot both be true".to_string(),
                nodes: vec![source.to_string(), target.to_string()],
            });
        }
    }
    conflicts
}

fn detect_self_containment(constraints: &[Constraint]) -> Vec<ConstraintConflict> {
    constraints
        .iter()
        .filter(|constraint| {
            constraint.source == constraint.target
                && matches!(
                    constraint.relation,
                    SpatialRelation::Inside | SpatialRelation::Contains
                )
        })
        .map(|constraint| ConstraintConflict {
            conflict_type: ConflictType::ContainmentConflict,
            description: "object cannot contain itself".to_string(),
            nodes: vec![constraint.source.clone()],
        })
        .collect()
}

fn detect_ordering_cycles(
    constraints: &[Constraint],
    relation: SpatialRelation,
    conflict_type: ConflictType,
    description: &str,
) -> Vec<ConstraintConflict> {
    let graph = adjacency_for(constraints, &relation);
    cycles_in_graph(&graph)
        .into_iter()
        .map(|nodes| ConstraintConflict {
            conflict_type: conflict_type.clone(),
            description: description.to_string(),
            nodes,
        })
        .collect()
}

fn detect_containment_cycles(constraints: &[Constraint]) -> Vec<ConstraintConflict> {
    let graph = containment_adjacency(constraints);
    cycles_in_graph(&graph)
        .into_iter()
        .map(|nodes| ConstraintConflict {
            conflict_type: ConflictType::ContainmentConflict,
            description: "containment graph must be acyclic".to_string(),
            nodes,
        })
        .collect()
}

fn detect_containment_ordering_conflicts(constraints: &[Constraint]) -> Vec<ConstraintConflict> {
    let containment = containment_adjacency(constraints);
    let mut conflicts = Vec::new();

    for constraint in constraints {
        if !matches!(
            constraint.relation,
            SpatialRelation::LeftOf
                | SpatialRelation::RightOf
                | SpatialRelation::Above
                | SpatialRelation::Below
        ) {
            continue;
        }

        if is_descendant(&containment, &constraint.target, &constraint.source) {
            conflicts.push(ConstraintConflict {
                conflict_type: ConflictType::GeometricConflict,
                description: "parent object cannot be ordered relative to its contained child"
                    .to_string(),
                nodes: vec![constraint.source.clone(), constraint.target.clone()],
            });
        }
    }

    conflicts
}

fn adjacency_for(
    constraints: &[Constraint],
    relation: &SpatialRelation,
) -> BTreeMap<String, BTreeSet<String>> {
    let mut graph = BTreeMap::new();
    for constraint in constraints
        .iter()
        .filter(|constraint| &constraint.relation == relation)
    {
        graph
            .entry(constraint.source.clone())
            .or_insert_with(BTreeSet::new)
            .insert(constraint.target.clone());
        graph.entry(constraint.target.clone()).or_insert_with(BTreeSet::new);
    }
    graph
}

fn containment_adjacency(constraints: &[Constraint]) -> BTreeMap<String, BTreeSet<String>> {
    let mut graph = BTreeMap::new();
    for constraint in constraints {
        match constraint.relation {
            SpatialRelation::Inside => {
                graph
                    .entry(constraint.source.clone())
                    .or_insert_with(BTreeSet::new)
                    .insert(constraint.target.clone());
                graph
                    .entry(constraint.target.clone())
                    .or_insert_with(BTreeSet::new);
            }
            SpatialRelation::Contains => {
                graph
                    .entry(constraint.target.clone())
                    .or_insert_with(BTreeSet::new)
                    .insert(constraint.source.clone());
                graph
                    .entry(constraint.source.clone())
                    .or_insert_with(BTreeSet::new);
            }
            _ => {}
        }
    }
    graph
}

fn cycles_in_graph(graph: &BTreeMap<String, BTreeSet<String>>) -> Vec<Vec<String>> {
    let mut cycles = BTreeSet::new();
    for node in graph.keys() {
        let mut path = Vec::new();
        collect_cycles(node, node, graph, &mut path, &mut cycles);
    }
    cycles.into_iter().collect()
}

fn collect_cycles(
    start: &str,
    current: &str,
    graph: &BTreeMap<String, BTreeSet<String>>,
    path: &mut Vec<String>,
    cycles: &mut BTreeSet<Vec<String>>,
) {
    path.push(current.to_string());
    if let Some(next_nodes) = graph.get(current) {
        for next in next_nodes {
            if next == start {
                cycles.insert(canonical_cycle(path));
            } else if !path.contains(next) {
                collect_cycles(start, next, graph, path, cycles);
            }
        }
    }
    path.pop();
}

fn canonical_cycle(path: &[String]) -> Vec<String> {
    let mut best = path.to_vec();
    for i in 1..path.len() {
        let rotated = path[i..]
            .iter()
            .chain(path[..i].iter())
            .cloned()
            .collect::<Vec<_>>();
        if rotated < best {
            best = rotated;
        }
    }
    best
}

fn is_descendant(
    containment: &BTreeMap<String, BTreeSet<String>>,
    child: &str,
    parent: &str,
) -> bool {
    let mut stack = vec![child.to_string()];
    let mut visited = BTreeSet::new();

    while let Some(current) = stack.pop() {
        if !visited.insert(current.clone()) {
            continue;
        }
        if let Some(next_nodes) = containment.get(&current) {
            for next in next_nodes {
                if next == parent {
                    return true;
                }
                stack.push(next.clone());
            }
        }
    }

    false
}

fn parse_relation(label: &str) -> Result<SpatialRelation, String> {
    match label {
        "left_of" => Ok(SpatialRelation::LeftOf),
        "right_of" => Ok(SpatialRelation::RightOf),
        "above" => Ok(SpatialRelation::Above),
        "below" => Ok(SpatialRelation::Below),
        "inside" => Ok(SpatialRelation::Inside),
        "contains" => Ok(SpatialRelation::Contains),
        other => Err(format!("unsupported spatial relation: {other}")),
    }
}

fn relation_label(edge: &Edge) -> String {
    match &edge.transition.op {
        TransitionOp::Addition(unit)
        | TransitionOp::Subsumption(unit)
        | TransitionOp::Refinement { target: unit, .. } => unit.label.clone(),
    }
}

fn object_name(graph: &ReasonGraph, object_id: Uuid) -> Result<String, String> {
    graph
        .get_node_state(&object_id)
        .map(|state| state.value.label.clone())
        .ok_or_else(|| format!("state is missing for node {object_id}"))
}

fn constraint_graph_json(graphs: &[(String, Vec<Constraint>)]) -> String {
    let cases = graphs
        .iter()
        .map(|(case_name, constraints)| {
            let constraints_json = constraints
                .iter()
                .map(|constraint| {
                    format!(
                        "      {{ \"source\": \"{}\", \"relation\": \"{}\", \"target\": \"{}\" }}",
                        constraint.source,
                        constraint.relation.as_str(),
                        constraint.target
                    )
                })
                .collect::<Vec<_>>()
                .join(",\n");
            format!(
                "    {{\n      \"case\": \"{}\",\n      \"constraints\": [\n{}\n      ]\n    }}",
                case_name, constraints_json
            )
        })
        .collect::<Vec<_>>()
        .join(",\n");

    format!("{{\n  \"cases\": [\n{}\n  ]\n}}\n", cases)
}

fn validation_report_json(reports: &[(String, ValidationReport)]) -> String {
    let cases = reports
        .iter()
        .map(|(case_name, report)| {
            let conflicts = report
                .conflicts
                .iter()
                .map(|conflict| {
                    format!(
                        "        {{ \"type\": \"{}\", \"description\": \"{}\", \"nodes\": {} }}",
                        conflict.conflict_type.as_str(),
                        conflict.description,
                        json_string_array(&conflict.nodes)
                    )
                })
                .collect::<Vec<_>>()
                .join(",\n");
            format!(
                "    {{\n      \"case\": \"{}\",\n      \"passed\": {},\n      \"checks\": {},\n      \"conflicts\": [\n{}\n      ]\n    }}",
                case_name,
                report.passed,
                json_string_array(&report.checks),
                conflicts
            )
        })
        .collect::<Vec<_>>()
        .join(",\n");

    format!("{{\n  \"cases\": [\n{}\n  ]\n}}\n", cases)
}

fn json_string_array(values: &[String]) -> String {
    let body = values
        .iter()
        .map(|value| format!("\"{value}\""))
        .collect::<Vec<_>>()
        .join(", ");
    format!("[{body}]")
}
