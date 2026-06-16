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

const MIN_GAP: f32 = 30.0;
const NEAR_THRESHOLD: f32 = 150.0;
const FAR_THRESHOLD: f32 = 300.0;

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum SpatialRelation {
    LeftOf,
    RightOf,
    Above,
    Below,
    Near,
    Far,
}

impl SpatialRelation {
    fn as_str(&self) -> &'static str {
        match self {
            Self::LeftOf => "left_of",
            Self::RightOf => "right_of",
            Self::Above => "above",
            Self::Below => "below",
            Self::Near => "near",
            Self::Far => "far",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
struct SpatialConstraint {
    source: String,
    relation: SpatialRelation,
    target: String,
}

#[derive(Debug, Clone, Copy, PartialEq)]
struct Bounds {
    x: f32,
    y: f32,
    width: f32,
    height: f32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ValidationReport {
    passed: bool,
    checks: Vec<String>,
    violations: Vec<String>,
}

#[test]
fn ru_obj_2d_007_generates_deterministic_spatial_relation_layout() {
    let graph = build_valid_spatial_graph();
    let containment = extract_containment(&graph).expect("containment must be extracted");
    let constraints = extract_spatial_constraints(&graph).expect("spatial constraints must be extracted");
    let validation = validate_spatial_constraints(&containment, &constraints);
    assert!(validation.passed);

    let layout = solve_layout(&containment, &constraints).expect("spatial layout must solve");
    let layout_report = validate_layout(&containment, &constraints, &layout);
    assert!(layout_report.passed);
    assert!(layout_report.violations.is_empty());

    assert_left_of(&layout, "Table", "Chair");
    assert_right_of(&layout, "Chair", "Table");
    assert_above(&layout, "Lamp", "Table");
    assert_below(&layout, "Table", "Lamp");
    assert_near(&layout, "Chair", "Table");
    assert_far(&layout, "Bed", "Desk");

    assert_rejects(vec![("A", "left_of", "B"), ("B", "left_of", "C"), ("C", "left_of", "A")]);
    assert_rejects(vec![("A", "above", "B"), ("B", "above", "C"), ("C", "above", "A")]);
    assert_rejects(vec![("A", "near", "B"), ("A", "far", "B")]);
    assert_rejects(vec![("A", "left_of", "B"), ("A", "right_of", "B")]);
    assert_rejects(vec![("A", "above", "B"), ("A", "below", "B")]);
    assert_cross_container_rejected();

    let scene_json = spatial_scene_json(&containment, &constraints);
    let layout_json = spatial_layout_json(&layout);
    let png = render_spatial_scene_png(&layout);

    for _ in 0..100 {
        let next_layout = solve_layout(&containment, &constraints).expect("layout must reproduce");
        assert_eq!(layout, next_layout);
        assert_eq!(layout_json, spatial_layout_json(&next_layout));
        assert_eq!(png, render_spatial_scene_png(&next_layout));
    }

    let artifact_dir = Path::new("artifacts/ru_obj_2d_007");
    fs::create_dir_all(artifact_dir).expect("artifact directory must be created");
    fs::write(artifact_dir.join("spatial_scene.json"), scene_json)
        .expect("spatial_scene.json must be generated");
    fs::write(artifact_dir.join("spatial_layout.json"), layout_json)
        .expect("spatial_layout.json must be generated");
    fs::write(
        artifact_dir.join("validation_report.json"),
        validation_report_json(&layout_report),
    )
    .expect("validation_report.json must be generated");
    fs::write(artifact_dir.join("spatial_scene.png"), png)
        .expect("spatial_scene.png must be generated");

    for path in [
        "artifacts/ru_obj_2d_007/spatial_scene.json",
        "artifacts/ru_obj_2d_007/spatial_layout.json",
        "artifacts/ru_obj_2d_007/validation_report.json",
        "artifacts/ru_obj_2d_007/spatial_scene.png",
    ] {
        let bytes = fs::read(path).expect("artifact must be readable");
        assert!(bytes.len() > 20, "{path} must not be empty");
    }
}

fn build_valid_spatial_graph() -> ReasonGraph {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);
    let world = add_object_node(&mut graph, "World");
    let room = add_object_node(&mut graph, "Room");
    let room_b = add_object_node(&mut graph, "RoomB");
    let table = add_object_node(&mut graph, "Table");
    let chair = add_object_node(&mut graph, "Chair");
    let lamp = add_object_node(&mut graph, "Lamp");
    let bed = add_object_node(&mut graph, "Bed");
    let desk = add_object_node(&mut graph, "Desk");

    add_relation(&mut graph, world, room, "contains");
    add_relation(&mut graph, world, room_b, "contains");
    add_relation(&mut graph, room, table, "contains");
    add_relation(&mut graph, room, chair, "contains");
    add_relation(&mut graph, room, lamp, "contains");
    add_relation(&mut graph, room_b, bed, "contains");
    add_relation(&mut graph, room_b, desk, "contains");

    add_relation(&mut graph, table, chair, "left_of");
    add_relation(&mut graph, chair, table, "right_of");
    add_relation(&mut graph, lamp, table, "above");
    add_relation(&mut graph, table, lamp, "below");
    add_relation(&mut graph, chair, table, "near");
    add_relation(&mut graph, bed, desk, "far");

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

fn extract_containment(graph: &ReasonGraph) -> Result<BTreeMap<String, BTreeSet<String>>, String> {
    let mut containment = BTreeMap::new();
    for edge in graph.edges.iter().filter(|edge| edge.relation == RelationType::Spatial) {
        match relation_label(edge).as_str() {
            "contains" => {
                let parent = object_name(graph, edge.source)?;
                let child = object_name(graph, edge.target)?;
                containment.entry(parent).or_insert_with(BTreeSet::new).insert(child);
            }
            "inside" => {
                let parent = object_name(graph, edge.target)?;
                let child = object_name(graph, edge.source)?;
                containment.entry(parent).or_insert_with(BTreeSet::new).insert(child);
            }
            _ => {}
        }
    }
    Ok(containment)
}

fn extract_spatial_constraints(graph: &ReasonGraph) -> Result<Vec<SpatialConstraint>, String> {
    let mut constraints = graph
        .edges
        .iter()
        .filter(|edge| edge.relation == RelationType::Spatial)
        .filter_map(|edge| {
            parse_spatial_relation(relation_label(edge).as_str()).map(|relation| {
                Ok(SpatialConstraint {
                    source: object_name(graph, edge.source)?,
                    relation,
                    target: object_name(graph, edge.target)?,
                })
            })
        })
        .collect::<Result<Vec<_>, String>>()?;
    constraints.sort();
    Ok(constraints)
}

fn validate_spatial_constraints(
    containment: &BTreeMap<String, BTreeSet<String>>,
    constraints: &[SpatialConstraint],
) -> ValidationReport {
    let mut checks = Vec::new();
    let mut violations = Vec::new();

    for constraint in constraints {
        checks.push(format!(
            "{} {} {}",
            constraint.source,
            constraint.relation.as_str(),
            constraint.target
        ));
        if common_parent(containment, &constraint.source, &constraint.target).is_none() {
            violations.push(format!(
                "CrossContainerSpatialRelation: {} {} {}",
                constraint.source,
                constraint.relation.as_str(),
                constraint.target
            ));
        }
    }

    violations.extend(detect_direct_conflicts(constraints));
    violations.extend(detect_cycles(constraints, SpatialRelation::LeftOf, "left_of cycle"));
    violations.extend(detect_cycles(constraints, SpatialRelation::Above, "above cycle"));
    violations.extend(detect_near_far_conflicts(constraints));

    violations.sort();
    violations.dedup();

    ValidationReport {
        passed: violations.is_empty(),
        checks,
        violations,
    }
}

fn solve_layout(
    containment: &BTreeMap<String, BTreeSet<String>>,
    constraints: &[SpatialConstraint],
) -> Result<BTreeMap<String, Bounds>, String> {
    let validation = validate_spatial_constraints(containment, constraints);
    if !validation.passed {
        return Err(validation.violations.join("; "));
    }

    let mut layout = initial_containment_layout(containment);

    for relation in [
        SpatialRelation::LeftOf,
        SpatialRelation::RightOf,
        SpatialRelation::Above,
        SpatialRelation::Below,
        SpatialRelation::Near,
        SpatialRelation::Far,
    ] {
        for constraint in constraints
            .iter()
            .filter(|constraint| constraint.relation == relation)
        {
            apply_constraint(containment, &mut layout, constraint)?;
        }
    }

    Ok(layout)
}

fn initial_containment_layout(
    containment: &BTreeMap<String, BTreeSet<String>>,
) -> BTreeMap<String, Bounds> {
    let mut layout = BTreeMap::new();
    layout.insert(
        "World".to_string(),
        Bounds {
            x: 500.0,
            y: 500.0,
            width: 900.0,
            height: 700.0,
        },
    );
    layout.insert(
        "Room".to_string(),
        Bounds {
            x: 350.0,
            y: 500.0,
            width: 380.0,
            height: 360.0,
        },
    );
    layout.insert(
        "RoomB".to_string(),
        Bounds {
            x: 760.0,
            y: 500.0,
            width: 380.0,
            height: 360.0,
        },
    );

    for children in containment.values() {
        for child in children {
            layout.entry(child.clone()).or_insert(Bounds {
                x: 0.0,
                y: 0.0,
                width: 50.0,
                height: 50.0,
            });
        }
    }

    layout.insert(
        "Table".to_string(),
        Bounds {
            x: 270.0,
            y: 535.0,
            width: 60.0,
            height: 60.0,
        },
    );
    layout.insert(
        "Chair".to_string(),
        Bounds {
            x: 390.0,
            y: 535.0,
            width: 60.0,
            height: 60.0,
        },
    );
    layout.insert(
        "Lamp".to_string(),
        Bounds {
            x: 270.0,
            y: 430.0,
            width: 50.0,
            height: 50.0,
        },
    );
    layout.insert(
        "Bed".to_string(),
        Bounds {
            x: 600.0,
            y: 500.0,
            width: 60.0,
            height: 60.0,
        },
    );
    layout.insert(
        "Desk".to_string(),
        Bounds {
            x: 920.0,
            y: 500.0,
            width: 60.0,
            height: 60.0,
        },
    );

    layout
}

fn apply_constraint(
    containment: &BTreeMap<String, BTreeSet<String>>,
    layout: &mut BTreeMap<String, Bounds>,
    constraint: &SpatialConstraint,
) -> Result<(), String> {
    let parent = common_parent(containment, &constraint.source, &constraint.target)
        .ok_or_else(|| "missing common parent".to_string())?;
    let parent_bounds = *layout
        .get(&parent)
        .ok_or_else(|| format!("parent {parent} has no layout"))?;
    let target = *layout
        .get(&constraint.target)
        .ok_or_else(|| format!("target {} has no layout", constraint.target))?;
    let mut source = *layout
        .get(&constraint.source)
        .ok_or_else(|| format!("source {} has no layout", constraint.source))?;

    match constraint.relation {
        SpatialRelation::LeftOf => {
            source.x = target.x - target.width / 2.0 - source.width / 2.0 - MIN_GAP;
            source.y = target.y;
        }
        SpatialRelation::RightOf => {
            source.x = target.x + target.width / 2.0 + source.width / 2.0 + MIN_GAP;
            source.y = target.y;
        }
        SpatialRelation::Above => {
            source.x = target.x;
            source.y = target.y - target.height / 2.0 - source.height / 2.0 - MIN_GAP;
        }
        SpatialRelation::Below => {
            source.x = target.x;
            source.y = target.y + target.height / 2.0 + source.height / 2.0 + MIN_GAP;
        }
        SpatialRelation::Near => {}
        SpatialRelation::Far => {
            source.x = target.x - FAR_THRESHOLD - 20.0;
            source.y = target.y;
        }
    }

    if !contains(&parent_bounds, &source) {
        return Err(format!(
            "{} {} {} violates containment",
            constraint.source,
            constraint.relation.as_str(),
            constraint.target
        ));
    }

    layout.insert(constraint.source.clone(), source);
    Ok(())
}

fn validate_layout(
    containment: &BTreeMap<String, BTreeSet<String>>,
    constraints: &[SpatialConstraint],
    layout: &BTreeMap<String, Bounds>,
) -> ValidationReport {
    let mut checks = Vec::new();
    let mut violations = Vec::new();

    for (parent, children) in containment {
        let Some(parent_bounds) = layout.get(parent) else {
            violations.push(format!("{parent} has no layout"));
            continue;
        };
        for child in children {
            let Some(child_bounds) = layout.get(child) else {
                violations.push(format!("{child} has no layout"));
                continue;
            };
            if contains(parent_bounds, child_bounds) {
                checks.push(format!("{child} inside {parent}"));
            } else {
                violations.push(format!("{child} outside {parent}"));
            }
        }
    }

    for constraint in constraints {
        let Some(source) = layout.get(&constraint.source) else {
            violations.push(format!("{} has no layout", constraint.source));
            continue;
        };
        let Some(target) = layout.get(&constraint.target) else {
            violations.push(format!("{} has no layout", constraint.target));
            continue;
        };
        let passed = match constraint.relation {
            SpatialRelation::LeftOf => source.x < target.x && target_left(target) - source_right(source) >= MIN_GAP,
            SpatialRelation::RightOf => source.x > target.x && source_left(source) - target_right(target) >= MIN_GAP,
            SpatialRelation::Above => source.y < target.y,
            SpatialRelation::Below => source.y > target.y,
            SpatialRelation::Near => distance(source, target) <= NEAR_THRESHOLD,
            SpatialRelation::Far => distance(source, target) >= FAR_THRESHOLD,
        };
        let check = format!(
            "{} {} {}",
            constraint.source,
            constraint.relation.as_str(),
            constraint.target
        );
        if passed {
            checks.push(check);
        } else {
            violations.push(check);
        }
    }

    ValidationReport {
        passed: violations.is_empty(),
        checks,
        violations,
    }
}

fn assert_rejects(relations: Vec<(&str, &str, &str)>) {
    let graph = build_flat_spatial_graph(relations);
    let containment = extract_containment(&graph).expect("containment must be extracted");
    let constraints = extract_spatial_constraints(&graph).expect("constraints must be extracted");
    let validation = validate_spatial_constraints(&containment, &constraints);
    assert!(!validation.passed);
}

fn assert_cross_container_rejected() {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);
    let world = add_object_node(&mut graph, "World");
    let room_a = add_object_node(&mut graph, "RoomA");
    let room_b = add_object_node(&mut graph, "RoomB");
    let table = add_object_node(&mut graph, "Table");
    let bed = add_object_node(&mut graph, "Bed");
    add_relation(&mut graph, world, room_a, "contains");
    add_relation(&mut graph, world, room_b, "contains");
    add_relation(&mut graph, room_a, table, "contains");
    add_relation(&mut graph, room_b, bed, "contains");
    add_relation(&mut graph, table, bed, "left_of");

    let containment = extract_containment(&graph).expect("containment must be extracted");
    let constraints = extract_spatial_constraints(&graph).expect("constraints must be extracted");
    let validation = validate_spatial_constraints(&containment, &constraints);
    assert!(!validation.passed);
    assert!(validation
        .violations
        .iter()
        .any(|violation| violation.contains("CrossContainerSpatialRelation")));
}

fn build_flat_spatial_graph(relations: Vec<(&str, &str, &str)>) -> ReasonGraph {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);
    let room = add_object_node(&mut graph, "Room");
    let mut nodes = HashMap::new();
    for (source, _, target) in &relations {
        for name in [*source, *target] {
            nodes.entry(name.to_string()).or_insert_with(|| {
                let node = add_object_node(&mut graph, name);
                add_relation(&mut graph, room, node, "contains");
                node
            });
        }
    }
    for (source, relation, target) in relations {
        add_relation(
            &mut graph,
            *nodes.get(source).expect("source must exist"),
            *nodes.get(target).expect("target must exist"),
            relation,
        );
    }
    graph
}

fn detect_direct_conflicts(constraints: &[SpatialConstraint]) -> Vec<String> {
    let mut by_pair: BTreeMap<(&str, &str), BTreeSet<&SpatialRelation>> = BTreeMap::new();
    for constraint in constraints {
        by_pair
            .entry((&constraint.source, &constraint.target))
            .or_default()
            .insert(&constraint.relation);
    }

    let mut violations = Vec::new();
    for ((source, target), relations) in by_pair {
        if relations.contains(&SpatialRelation::LeftOf)
            && relations.contains(&SpatialRelation::RightOf)
        {
            violations.push(format!("{source} cannot be both left_of and right_of {target}"));
        }
        if relations.contains(&SpatialRelation::Above) && relations.contains(&SpatialRelation::Below)
        {
            violations.push(format!("{source} cannot be both above and below {target}"));
        }
        if relations.contains(&SpatialRelation::Near) && relations.contains(&SpatialRelation::Far) {
            violations.push(format!("{source} cannot be both near and far {target}"));
        }
    }
    violations
}

fn detect_near_far_conflicts(constraints: &[SpatialConstraint]) -> Vec<String> {
    let mut unordered = BTreeMap::new();
    for constraint in constraints {
        if !matches!(constraint.relation, SpatialRelation::Near | SpatialRelation::Far) {
            continue;
        }
        let mut pair = [constraint.source.clone(), constraint.target.clone()];
        pair.sort();
        unordered
            .entry((pair[0].clone(), pair[1].clone()))
            .or_insert_with(BTreeSet::new)
            .insert(constraint.relation.clone());
    }

    unordered
        .into_iter()
        .filter(|(_, relations)| {
            relations.contains(&SpatialRelation::Near) && relations.contains(&SpatialRelation::Far)
        })
        .map(|((a, b), _)| format!("{a} and {b} cannot be both near and far"))
        .collect()
}

fn detect_cycles(
    constraints: &[SpatialConstraint],
    relation: SpatialRelation,
    label: &str,
) -> Vec<String> {
    let mut graph = BTreeMap::new();
    for constraint in constraints
        .iter()
        .filter(|constraint| constraint.relation == relation)
    {
        graph
            .entry(constraint.source.clone())
            .or_insert_with(BTreeSet::new)
            .insert(constraint.target.clone());
        graph
            .entry(constraint.target.clone())
            .or_insert_with(BTreeSet::new);
    }

    cycles_in_graph(&graph)
        .into_iter()
        .map(|cycle| format!("{label}: {}", cycle.join(" -> ")))
        .collect()
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
    for index in 1..path.len() {
        let rotated = path[index..]
            .iter()
            .chain(path[..index].iter())
            .cloned()
            .collect::<Vec<_>>();
        if rotated < best {
            best = rotated;
        }
    }
    best
}

fn common_parent(
    containment: &BTreeMap<String, BTreeSet<String>>,
    a: &str,
    b: &str,
) -> Option<String> {
    containment.iter().find_map(|(parent, children)| {
        (children.contains(a) && children.contains(b)).then(|| parent.clone())
    })
}

fn contains(parent: &Bounds, child: &Bounds) -> bool {
    source_left(child) >= source_left(parent)
        && source_right(child) <= source_right(parent)
        && source_top(child) >= source_top(parent)
        && source_bottom(child) <= source_bottom(parent)
}

fn distance(a: &Bounds, b: &Bounds) -> f32 {
    ((a.x - b.x).powi(2) + (a.y - b.y).powi(2)).sqrt()
}

fn source_left(bounds: &Bounds) -> f32 {
    bounds.x - bounds.width / 2.0
}

fn source_right(bounds: &Bounds) -> f32 {
    bounds.x + bounds.width / 2.0
}

fn source_top(bounds: &Bounds) -> f32 {
    bounds.y - bounds.height / 2.0
}

fn source_bottom(bounds: &Bounds) -> f32 {
    bounds.y + bounds.height / 2.0
}

fn target_left(bounds: &Bounds) -> f32 {
    source_left(bounds)
}

fn target_right(bounds: &Bounds) -> f32 {
    source_right(bounds)
}

fn assert_left_of(layout: &BTreeMap<String, Bounds>, source: &str, target: &str) {
    let source = layout.get(source).expect("source must exist");
    let target = layout.get(target).expect("target must exist");
    assert!(source.x < target.x);
    assert!(target_left(target) - source_right(source) >= MIN_GAP);
}

fn assert_right_of(layout: &BTreeMap<String, Bounds>, source: &str, target: &str) {
    let source = layout.get(source).expect("source must exist");
    let target = layout.get(target).expect("target must exist");
    assert!(source.x > target.x);
    assert!(source_left(source) - target_right(target) >= MIN_GAP);
}

fn assert_above(layout: &BTreeMap<String, Bounds>, source: &str, target: &str) {
    let source = layout.get(source).expect("source must exist");
    let target = layout.get(target).expect("target must exist");
    assert!(source.y < target.y);
}

fn assert_below(layout: &BTreeMap<String, Bounds>, source: &str, target: &str) {
    let source = layout.get(source).expect("source must exist");
    let target = layout.get(target).expect("target must exist");
    assert!(source.y > target.y);
}

fn assert_near(layout: &BTreeMap<String, Bounds>, source: &str, target: &str) {
    let source = layout.get(source).expect("source must exist");
    let target = layout.get(target).expect("target must exist");
    assert!(distance(source, target) <= NEAR_THRESHOLD);
}

fn assert_far(layout: &BTreeMap<String, Bounds>, source: &str, target: &str) {
    let source = layout.get(source).expect("source must exist");
    let target = layout.get(target).expect("target must exist");
    assert!(distance(source, target) >= FAR_THRESHOLD);
}

fn parse_spatial_relation(label: &str) -> Option<SpatialRelation> {
    match label {
        "left_of" => Some(SpatialRelation::LeftOf),
        "right_of" => Some(SpatialRelation::RightOf),
        "above" => Some(SpatialRelation::Above),
        "below" => Some(SpatialRelation::Below),
        "near" => Some(SpatialRelation::Near),
        "far" => Some(SpatialRelation::Far),
        _ => None,
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

fn spatial_scene_json(
    containment: &BTreeMap<String, BTreeSet<String>>,
    constraints: &[SpatialConstraint],
) -> String {
    let containment_json = containment
        .iter()
        .map(|(parent, children)| {
            format!(
                "    {{ \"parent\": \"{}\", \"children\": {} }}",
                parent,
                json_string_array(&children.iter().cloned().collect::<Vec<_>>())
            )
        })
        .collect::<Vec<_>>()
        .join(",\n");
    let constraints_json = constraints
        .iter()
        .map(|constraint| {
            format!(
                "    {{ \"source\": \"{}\", \"relation\": \"{}\", \"target\": \"{}\" }}",
                constraint.source,
                constraint.relation.as_str(),
                constraint.target
            )
        })
        .collect::<Vec<_>>()
        .join(",\n");

    format!(
        "{{\n  \"containment\": [\n{}\n  ],\n  \"spatial_relations\": [\n{}\n  ]\n}}\n",
        containment_json, constraints_json
    )
}

fn spatial_layout_json(layout: &BTreeMap<String, Bounds>) -> String {
    let entries = layout
        .iter()
        .map(|(name, bounds)| {
            format!(
                "  \"{}\": {{ \"x\": {}, \"y\": {}, \"width\": {}, \"height\": {} }}",
                name, bounds.x, bounds.y, bounds.width, bounds.height
            )
        })
        .collect::<Vec<_>>()
        .join(",\n");
    format!("{{\n{}\n}}\n", entries)
}

fn validation_report_json(report: &ValidationReport) -> String {
    format!(
        "{{\n  \"passed\": {},\n  \"checks\": {},\n  \"violations\": {}\n}}\n",
        report.passed,
        json_string_array(&report.checks),
        json_string_array(&report.violations)
    )
}

fn json_string_array(values: &[String]) -> String {
    let body = values
        .iter()
        .map(|value| format!("\"{value}\""))
        .collect::<Vec<_>>()
        .join(", ");
    format!("[{body}]")
}

fn render_spatial_scene_png(layout: &BTreeMap<String, Bounds>) -> Vec<u8> {
    let canvas_width = 1100;
    let canvas_height = 900;
    let mut rgba = vec![255; (canvas_width * canvas_height * 4) as usize];

    for name in ["World", "Room", "RoomB", "Lamp", "Table", "Chair", "Bed", "Desk"] {
        if let Some(bounds) = layout.get(name) {
            draw_rectangle(&mut rgba, canvas_width, *bounds);
        }
    }

    encode_png_rgba(canvas_width, canvas_height, &rgba)
}

fn draw_rectangle(rgba: &mut [u8], canvas_width: u32, bounds: Bounds) {
    let left = source_left(&bounds) as u32;
    let right = source_right(&bounds) as u32;
    let top = source_top(&bounds) as u32;
    let bottom = source_bottom(&bounds) as u32;

    for y in top..=bottom {
        for x in left..=right {
            if x == left || x == right || y == top || y == bottom {
                set_black_pixel(rgba, canvas_width, x, y);
            }
        }
    }
}

fn set_black_pixel(rgba: &mut [u8], canvas_width: u32, x: u32, y: u32) {
    if x >= canvas_width || y >= 900 {
        return;
    }
    let index = ((y * canvas_width + x) * 4) as usize;
    rgba[index] = 0;
    rgba[index + 1] = 0;
    rgba[index + 2] = 0;
    rgba[index + 3] = 255;
}

fn encode_png_rgba(width: u32, height: u32, rgba: &[u8]) -> Vec<u8> {
    let mut png = Vec::new();
    png.extend_from_slice(&[137, 80, 78, 71, 13, 10, 26, 10]);

    let mut ihdr = Vec::new();
    ihdr.extend_from_slice(&width.to_be_bytes());
    ihdr.extend_from_slice(&height.to_be_bytes());
    ihdr.extend_from_slice(&[8, 6, 0, 0, 0]);
    write_png_chunk(&mut png, b"IHDR", &ihdr);

    let stride = (width * 4) as usize;
    let mut raw = Vec::with_capacity((stride + 1) * height as usize);
    for row in rgba.chunks_exact(stride) {
        raw.push(0);
        raw.extend_from_slice(row);
    }
    write_png_chunk(&mut png, b"IDAT", &zlib_store(&raw));
    write_png_chunk(&mut png, b"IEND", &[]);
    png
}

fn write_png_chunk(png: &mut Vec<u8>, kind: &[u8; 4], data: &[u8]) {
    png.extend_from_slice(&(data.len() as u32).to_be_bytes());
    png.extend_from_slice(kind);
    png.extend_from_slice(data);

    let mut crc_input = Vec::with_capacity(kind.len() + data.len());
    crc_input.extend_from_slice(kind);
    crc_input.extend_from_slice(data);
    png.extend_from_slice(&crc32(&crc_input).to_be_bytes());
}

fn zlib_store(data: &[u8]) -> Vec<u8> {
    let mut out = vec![0x78, 0x01];
    let mut offset = 0;
    while offset < data.len() {
        let remaining = data.len() - offset;
        let block_len = remaining.min(u16::MAX as usize);
        let final_block = offset + block_len == data.len();
        out.push(if final_block { 1 } else { 0 });
        out.extend_from_slice(&(block_len as u16).to_le_bytes());
        out.extend_from_slice(&(!(block_len as u16)).to_le_bytes());
        out.extend_from_slice(&data[offset..offset + block_len]);
        offset += block_len;
    }
    out.extend_from_slice(&adler32(data).to_be_bytes());
    out
}

fn crc32(bytes: &[u8]) -> u32 {
    let mut crc = 0xffff_ffff;
    for byte in bytes {
        crc ^= *byte as u32;
        for _ in 0..8 {
            let mask = (crc & 1).wrapping_neg();
            crc = (crc >> 1) ^ (0xedb8_8320 & mask);
        }
    }
    !crc
}

fn adler32(bytes: &[u8]) -> u32 {
    const MOD_ADLER: u32 = 65_521;
    let mut a = 1;
    let mut b = 0;
    for byte in bytes {
        a = (a + *byte as u32) % MOD_ADLER;
        b = (b + a) % MOD_ADLER;
    }
    (b << 16) | a
}
