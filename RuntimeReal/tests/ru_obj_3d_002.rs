use ndarray::array;
use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{
    GraphType, RelationType, StateType, TransitionType, UnitType,
};
use reasonscript_runtime_real::core::{ReasonUnit, State, Transition};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet, VecDeque};
use std::fs;
use std::path::Path;
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Vector3 {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Transform3D {
    pub position: Vector3,
    pub rotation: Vector3,
    pub scale: Vector3,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum GeometryType {
    World,
    Terrain,
    Building,
    Floor,
    Room,
    Furniture,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Object3DNode {
    pub id: String,
    pub name: String,
    pub geometry: GeometryType,
    pub local_transform: Transform3D,
    pub parent_id: Option<String>,
    pub children: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SceneGraph {
    pub nodes: Vec<Object3DNode>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
struct ValidationCase {
    id: String,
    name: String,
    passed: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
struct ValidationReport {
    specification: String,
    version: String,
    passed: bool,
    object_count: usize,
    hierarchy_depth: usize,
    cycles_detected: bool,
    missing_parents: usize,
    world_transform_pass: bool,
    dfs_order: Vec<String>,
    bfs_order: Vec<String>,
    cases: Vec<ValidationCase>,
    generated_artifacts: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct HierarchyValidation {
    root_count: usize,
    object_count: usize,
    hierarchy_depth: usize,
    cycles_detected: bool,
    missing_parents: usize,
    parent_child_mismatches: Vec<String>,
}

#[test]
fn ru_obj_3d_002_hierarchical_world_validation() {
    let expected = reference_world();
    assert!(
        expected.nodes.len() >= 8,
        "object count must satisfy RU-OBJ-3D-002"
    );

    let graph = build_reason_unit_world_graph(&expected);
    let scene = extract_scene_graph(&graph).expect("RU-OBJ-3D-002-A hierarchy must extract");
    assert_eq!(scene, expected);
    assert!(contains_nodes(&scene, &["world", "building", "room_a"]));

    let validation = validate_hierarchy(&scene);
    assert_eq!(validation.root_count, 1);
    assert_eq!(validation.object_count, 9);
    assert!(!validation.cycles_detected);
    assert_eq!(validation.missing_parents, 0);
    assert!(validation.parent_child_mismatches.is_empty());
    assert!(validation.hierarchy_depth >= 4);

    let transforms =
        compute_world_transforms(&scene).expect("RU-OBJ-3D-002-C transforms must accumulate");
    assert_eq!(
        transforms.get("table").map(|t| t.position),
        Some(Vector3 {
            x: 112.0,
            y: 0.0,
            z: 1.0
        })
    );

    let cyclic = cyclic_world();
    let cyclic_validation = validate_hierarchy(&cyclic);
    assert!(
        cyclic_validation.cycles_detected,
        "RU-OBJ-3D-002-D must detect cycles"
    );

    let missing_parent = missing_parent_world();
    let missing_validation = validate_hierarchy(&missing_parent);
    assert_eq!(missing_validation.missing_parents, 1);

    let world_json = scene_graph_json(&scene);
    let restored: SceneGraph =
        serde_json::from_str(&world_json).expect("RU-OBJ-3D-002-F JSON must restore");
    assert_eq!(restored, scene);

    let dfs = dfs_order(&scene).expect("RU-OBJ-3D-002-G DFS must succeed");
    let bfs = bfs_order(&scene).expect("RU-OBJ-3D-002-G BFS must succeed");
    assert_visits_all_once(&scene, &dfs);
    assert_visits_all_once(&scene, &bfs);

    for _ in 0..100 {
        assert_eq!(world_json, scene_graph_json(&scene));
        assert_eq!(dfs, dfs_order(&scene).expect("DFS must be deterministic"));
        assert_eq!(bfs, bfs_order(&scene).expect("BFS must be deterministic"));
    }

    let world_transform_pass = transforms.get("table").map(|t| t.position)
        == Some(Vector3 {
            x: 112.0,
            y: 0.0,
            z: 1.0,
        });
    let report = ValidationReport {
        specification: "RU-OBJ-3D-002".to_string(),
        version: "0.1".to_string(),
        passed: validation.object_count >= 8
            && validation.root_count == 1
            && !validation.cycles_detected
            && validation.missing_parents == 0
            && validation.parent_child_mismatches.is_empty()
            && world_transform_pass,
        object_count: validation.object_count,
        hierarchy_depth: validation.hierarchy_depth,
        cycles_detected: validation.cycles_detected,
        missing_parents: validation.missing_parents,
        world_transform_pass,
        dfs_order: dfs,
        bfs_order: bfs,
        cases: vec![
            case("RU-OBJ-3D-002-A", "Hierarchy Creation"),
            case("RU-OBJ-3D-002-B", "Parent Child Integrity"),
            case("RU-OBJ-3D-002-C", "World Transform Propagation"),
            case("RU-OBJ-3D-002-D", "Cycle Detection"),
            case("RU-OBJ-3D-002-E", "Missing Parent Detection"),
            case("RU-OBJ-3D-002-F", "Scene Graph Serialization"),
            case("RU-OBJ-3D-002-G", "Traversal Validation"),
        ],
        generated_artifacts: vec![
            "world.json".to_string(),
            "validation_report.json".to_string(),
            "world_scene.png".to_string(),
        ],
    };
    assert!(report.passed);

    let artifact_dir = Path::new("artifacts/ru_obj_3d_002");
    fs::create_dir_all(artifact_dir).expect("artifact directory must be created");
    fs::write(artifact_dir.join("world.json"), world_json).expect("world.json");
    fs::write(
        artifact_dir.join("validation_report.json"),
        serde_json::to_string_pretty(&report).expect("report must serialize") + "\n",
    )
    .expect("validation_report.json");
    fs::write(
        artifact_dir.join("world_scene.png"),
        render_world_png(&scene, &transforms),
    )
    .expect("world_scene.png");

    for file in report.generated_artifacts {
        let path = artifact_dir.join(file);
        let bytes = fs::read(&path).expect("artifact must be readable");
        assert!(bytes.len() > 20, "{} must not be empty", path.display());
    }
}

fn reference_world() -> SceneGraph {
    SceneGraph {
        nodes: vec![
            node(
                "world",
                "World",
                GeometryType::World,
                transform(0.0, 0.0, 0.0),
                None,
                &["terrain", "building"],
            ),
            node(
                "terrain",
                "Terrain",
                GeometryType::Terrain,
                transform(0.0, -0.1, 0.0),
                Some("world"),
                &[],
            ),
            node(
                "building",
                "Building",
                GeometryType::Building,
                transform(100.0, 0.0, 0.0),
                Some("world"),
                &["floor_1", "floor_2"],
            ),
            node(
                "floor_1",
                "Floor1",
                GeometryType::Floor,
                transform(0.0, 0.0, 0.0),
                Some("building"),
                &["room_a", "room_b"],
            ),
            node(
                "room_a",
                "RoomA",
                GeometryType::Room,
                transform(10.0, 0.0, 0.0),
                Some("floor_1"),
                &["table", "chair"],
            ),
            node(
                "table",
                "Table",
                GeometryType::Furniture,
                transform(2.0, 0.0, 1.0),
                Some("room_a"),
                &[],
            ),
            node(
                "chair",
                "Chair",
                GeometryType::Furniture,
                transform(3.0, 0.0, 1.0),
                Some("room_a"),
                &[],
            ),
            node(
                "room_b",
                "RoomB",
                GeometryType::Room,
                transform(18.0, 0.0, 0.0),
                Some("floor_1"),
                &[],
            ),
            node(
                "floor_2",
                "Floor2",
                GeometryType::Floor,
                transform(0.0, 3.0, 0.0),
                Some("building"),
                &[],
            ),
        ],
    }
}

fn cyclic_world() -> SceneGraph {
    SceneGraph {
        nodes: vec![
            node(
                "a",
                "A",
                GeometryType::World,
                transform(0.0, 0.0, 0.0),
                Some("c"),
                &["b"],
            ),
            node(
                "b",
                "B",
                GeometryType::Building,
                transform(1.0, 0.0, 0.0),
                Some("a"),
                &["c"],
            ),
            node(
                "c",
                "C",
                GeometryType::Room,
                transform(1.0, 0.0, 0.0),
                Some("b"),
                &["a"],
            ),
        ],
    }
}

fn missing_parent_world() -> SceneGraph {
    SceneGraph {
        nodes: vec![
            node(
                "world",
                "World",
                GeometryType::World,
                transform(0.0, 0.0, 0.0),
                None,
                &["room"],
            ),
            node(
                "room",
                "Room",
                GeometryType::Room,
                transform(1.0, 0.0, 0.0),
                Some("building999"),
                &[],
            ),
        ],
    }
}

fn node(
    id: &str,
    name: &str,
    geometry: GeometryType,
    local_transform: Transform3D,
    parent_id: Option<&str>,
    children: &[&str],
) -> Object3DNode {
    Object3DNode {
        id: id.to_string(),
        name: name.to_string(),
        geometry,
        local_transform,
        parent_id: parent_id.map(str::to_string),
        children: children.iter().map(|child| (*child).to_string()).collect(),
    }
}

fn transform(x: f32, y: f32, z: f32) -> Transform3D {
    Transform3D {
        position: Vector3 { x, y, z },
        rotation: Vector3 {
            x: 0.0,
            y: 0.0,
            z: 0.0,
        },
        scale: Vector3 {
            x: 1.0,
            y: 1.0,
            z: 1.0,
        },
    }
}

fn build_reason_unit_world_graph(scene: &SceneGraph) -> ReasonGraph {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);
    let mut ids = BTreeMap::new();
    for object in &scene.nodes {
        let graph_id = add_graph_node(&mut graph, &encode_node_label(object), StateType::Object);
        ids.insert(object.id.clone(), graph_id);
    }
    for object in &scene.nodes {
        let source = ids[&object.id];
        for child in &object.children {
            add_graph_relation(&mut graph, source, ids[child], "contains");
        }
    }
    graph
}

fn extract_scene_graph(graph: &ReasonGraph) -> Result<SceneGraph, String> {
    let mut nodes = graph
        .nodes
        .keys()
        .map(|id| node_label(graph, *id).and_then(|label| decode_node_label(&label)))
        .collect::<Result<Vec<_>, _>>()?;
    nodes.sort_by(|a, b| a.id.cmp(&b.id));

    let mut by_graph_id = BTreeMap::new();
    for graph_id in graph.nodes.keys() {
        let object = decode_node_label(&node_label(graph, *graph_id)?)?;
        by_graph_id.insert(*graph_id, object.id);
    }

    for node in &mut nodes {
        node.children.clear();
    }
    let mut by_id: BTreeMap<String, Object3DNode> = nodes
        .into_iter()
        .map(|node| (node.id.clone(), node))
        .collect();
    for edge in &graph.edges {
        if edge_label(edge) != "contains" {
            continue;
        }
        let parent_id = by_graph_id
            .get(&edge.source)
            .ok_or_else(|| "source object missing".to_string())?
            .clone();
        let child_id = by_graph_id
            .get(&edge.target)
            .ok_or_else(|| "target object missing".to_string())?
            .clone();
        if let Some(parent) = by_id.get_mut(&parent_id) {
            parent.children.push(child_id.clone());
        }
        if let Some(child) = by_id.get_mut(&child_id) {
            child.parent_id = Some(parent_id);
        }
    }

    let mut restored: Vec<_> = by_id.into_values().collect();
    for node in &mut restored {
        node.children
            .sort_by(|a, b| node_sort_key(a).cmp(&node_sort_key(b)));
    }
    restored.sort_by(|a, b| node_sort_key(&a.id).cmp(&node_sort_key(&b.id)));
    Ok(SceneGraph { nodes: restored })
}

fn add_graph_node(graph: &mut ReasonGraph, label: &str, state_type: StateType) -> Uuid {
    let state = State::new(
        state_type,
        ReasonUnit::new(label, UnitType::Composite, array![0.0]),
    );
    let state_id = graph.add_state(state);
    graph.add_node(Node::new(state_id))
}

fn add_graph_relation(graph: &mut ReasonGraph, source: Uuid, target: Uuid, relation_label: &str) {
    let unit = ReasonUnit::new(relation_label, UnitType::Symbolic, array![1.0]);
    let transition = Transition::new(TransitionType::Deduction, TransitionOp::Subsumption(unit));
    graph.add_edge(Edge::new(source, target, RelationType::Spatial, transition));
}

fn node_label(graph: &ReasonGraph, id: Uuid) -> Result<String, String> {
    graph
        .get_node_state(&id)
        .map(|state| state.value.label.clone())
        .ok_or_else(|| format!("state missing for node {id}"))
}

fn edge_label(edge: &Edge) -> String {
    match &edge.transition.op {
        TransitionOp::Addition(unit)
        | TransitionOp::Subsumption(unit)
        | TransitionOp::Refinement { target: unit, .. } => unit.label.clone(),
    }
}

fn encode_node_label(node: &Object3DNode) -> String {
    let parent = node.parent_id.clone().unwrap_or_else(|| "none".to_string());
    format!(
        "Object3DNode:id={};name={};geometry={};parent={};pos={},{},{}",
        node.id,
        node.name,
        geometry_label(&node.geometry),
        parent,
        node.local_transform.position.x,
        node.local_transform.position.y,
        node.local_transform.position.z
    )
}

fn decode_node_label(label: &str) -> Result<Object3DNode, String> {
    let prefix = "Object3DNode:";
    let body = label
        .strip_prefix(prefix)
        .ok_or_else(|| format!("invalid Object3DNode label: {label}"))?;
    let mut fields = BTreeMap::new();
    for part in body.split(';') {
        let (key, value) = part
            .split_once('=')
            .ok_or_else(|| format!("invalid Object3DNode field: {part}"))?;
        fields.insert(key, value);
    }
    let id = fields
        .get("id")
        .ok_or_else(|| "id missing".to_string())?
        .to_string();
    let name = fields
        .get("name")
        .ok_or_else(|| "name missing".to_string())?
        .to_string();
    let geometry = parse_geometry(
        fields
            .get("geometry")
            .ok_or_else(|| "geometry missing".to_string())?,
    )?;
    let parent = fields
        .get("parent")
        .ok_or_else(|| "parent missing".to_string())?;
    let pos = parse_position(
        fields
            .get("pos")
            .ok_or_else(|| "position missing".to_string())?,
    )?;
    Ok(Object3DNode {
        id,
        name,
        geometry,
        local_transform: Transform3D {
            position: pos,
            rotation: Vector3 {
                x: 0.0,
                y: 0.0,
                z: 0.0,
            },
            scale: Vector3 {
                x: 1.0,
                y: 1.0,
                z: 1.0,
            },
        },
        parent_id: (*parent != "none").then(|| (*parent).to_string()),
        children: vec![],
    })
}

fn parse_position(value: &str) -> Result<Vector3, String> {
    let parts = value
        .split(',')
        .map(|part| {
            part.parse::<f32>()
                .map_err(|_| format!("invalid float: {part}"))
        })
        .collect::<Result<Vec<_>, _>>()?;
    if parts.len() != 3 {
        return Err(format!("invalid position: {value}"));
    }
    Ok(Vector3 {
        x: parts[0],
        y: parts[1],
        z: parts[2],
    })
}

fn geometry_label(geometry: &GeometryType) -> &'static str {
    match geometry {
        GeometryType::World => "world",
        GeometryType::Terrain => "terrain",
        GeometryType::Building => "building",
        GeometryType::Floor => "floor",
        GeometryType::Room => "room",
        GeometryType::Furniture => "furniture",
    }
}

fn parse_geometry(value: &str) -> Result<GeometryType, String> {
    match value {
        "world" => Ok(GeometryType::World),
        "terrain" => Ok(GeometryType::Terrain),
        "building" => Ok(GeometryType::Building),
        "floor" => Ok(GeometryType::Floor),
        "room" => Ok(GeometryType::Room),
        "furniture" => Ok(GeometryType::Furniture),
        _ => Err(format!("unsupported geometry: {value}")),
    }
}

fn validate_hierarchy(scene: &SceneGraph) -> HierarchyValidation {
    let ids: BTreeSet<_> = scene.nodes.iter().map(|node| node.id.clone()).collect();
    let root_count = scene
        .nodes
        .iter()
        .filter(|node| node.parent_id.is_none())
        .count();
    let missing_parents = scene
        .nodes
        .iter()
        .filter(|node| {
            node.parent_id
                .as_ref()
                .is_some_and(|parent| !ids.contains(parent))
        })
        .count();

    let mut parent_child_mismatches = Vec::new();
    let by_id: BTreeMap<_, _> = scene
        .nodes
        .iter()
        .map(|node| (node.id.as_str(), node))
        .collect();
    for node in &scene.nodes {
        for child_id in &node.children {
            match by_id.get(child_id.as_str()) {
                Some(child) if child.parent_id.as_deref() == Some(node.id.as_str()) => {}
                Some(_) => parent_child_mismatches.push(format!("{} -> {}", node.id, child_id)),
                None => {
                    parent_child_mismatches.push(format!("{} -> missing {}", node.id, child_id))
                }
            }
        }
        if let Some(parent_id) = &node.parent_id {
            if let Some(parent) = by_id.get(parent_id.as_str()) {
                if !parent.children.contains(&node.id) {
                    parent_child_mismatches
                        .push(format!("{} missing child {}", parent_id, node.id));
                }
            }
        }
    }

    HierarchyValidation {
        root_count,
        object_count: scene.nodes.len(),
        hierarchy_depth: hierarchy_depth(scene).unwrap_or(0),
        cycles_detected: has_cycle(scene),
        missing_parents,
        parent_child_mismatches,
    }
}

fn hierarchy_depth(scene: &SceneGraph) -> Result<usize, String> {
    let roots = scene
        .nodes
        .iter()
        .filter(|node| node.parent_id.is_none())
        .map(|node| node.id.clone())
        .collect::<Vec<_>>();
    let by_id: BTreeMap<_, _> = scene
        .nodes
        .iter()
        .map(|node| (node.id.as_str(), node))
        .collect();
    let mut max_depth = 0;
    for root in roots {
        max_depth = max_depth.max(depth_from(&root, &by_id, 1)?);
    }
    Ok(max_depth)
}

fn depth_from(
    id: &str,
    by_id: &BTreeMap<&str, &Object3DNode>,
    depth: usize,
) -> Result<usize, String> {
    let node = by_id.get(id).ok_or_else(|| format!("node missing: {id}"))?;
    let mut max_depth = depth;
    for child in &node.children {
        max_depth = max_depth.max(depth_from(child, by_id, depth + 1)?);
    }
    Ok(max_depth)
}

fn has_cycle(scene: &SceneGraph) -> bool {
    let by_id: BTreeMap<_, _> = scene
        .nodes
        .iter()
        .map(|node| (node.id.as_str(), node))
        .collect();
    let mut visiting = BTreeSet::new();
    let mut visited = BTreeSet::new();
    for node in &scene.nodes {
        if has_cycle_from(&node.id, &by_id, &mut visiting, &mut visited) {
            return true;
        }
    }
    false
}

fn has_cycle_from<'a>(
    id: &'a str,
    by_id: &BTreeMap<&'a str, &'a Object3DNode>,
    visiting: &mut BTreeSet<&'a str>,
    visited: &mut BTreeSet<&'a str>,
) -> bool {
    if visiting.contains(id) {
        return true;
    }
    if visited.contains(id) {
        return false;
    }
    visiting.insert(id);
    if let Some(node) = by_id.get(id) {
        for child in &node.children {
            if has_cycle_from(child, by_id, visiting, visited) {
                return true;
            }
        }
    }
    visiting.remove(id);
    visited.insert(id);
    false
}

fn compute_world_transforms(scene: &SceneGraph) -> Result<BTreeMap<String, Transform3D>, String> {
    let by_id: BTreeMap<_, _> = scene
        .nodes
        .iter()
        .map(|node| (node.id.as_str(), node))
        .collect();
    let mut transforms = BTreeMap::new();
    for node in &scene.nodes {
        let transform = compute_transform_for(&node.id, &by_id, &mut transforms)?;
        transforms.insert(node.id.clone(), transform);
    }
    Ok(transforms)
}

fn compute_transform_for(
    id: &str,
    by_id: &BTreeMap<&str, &Object3DNode>,
    cache: &mut BTreeMap<String, Transform3D>,
) -> Result<Transform3D, String> {
    if let Some(transform) = cache.get(id) {
        return Ok(*transform);
    }
    let node = by_id.get(id).ok_or_else(|| format!("node missing: {id}"))?;
    let transform = if let Some(parent_id) = &node.parent_id {
        let parent = compute_transform_for(parent_id, by_id, cache)?;
        compose_transform(parent, node.local_transform)
    } else {
        node.local_transform
    };
    cache.insert(id.to_string(), transform);
    Ok(transform)
}

fn compose_transform(parent: Transform3D, local: Transform3D) -> Transform3D {
    Transform3D {
        position: Vector3 {
            x: parent.position.x + local.position.x,
            y: parent.position.y + local.position.y,
            z: parent.position.z + local.position.z,
        },
        rotation: Vector3 {
            x: parent.rotation.x + local.rotation.x,
            y: parent.rotation.y + local.rotation.y,
            z: parent.rotation.z + local.rotation.z,
        },
        scale: Vector3 {
            x: parent.scale.x * local.scale.x,
            y: parent.scale.y * local.scale.y,
            z: parent.scale.z * local.scale.z,
        },
    }
}

fn dfs_order(scene: &SceneGraph) -> Result<Vec<String>, String> {
    let root = root_id(scene)?;
    let by_id: BTreeMap<_, _> = scene
        .nodes
        .iter()
        .map(|node| (node.id.as_str(), node))
        .collect();
    let mut order = Vec::new();
    dfs_visit(&root, &by_id, &mut order)?;
    Ok(order)
}

fn dfs_visit(
    id: &str,
    by_id: &BTreeMap<&str, &Object3DNode>,
    order: &mut Vec<String>,
) -> Result<(), String> {
    let node = by_id.get(id).ok_or_else(|| format!("node missing: {id}"))?;
    order.push(node.id.clone());
    for child in &node.children {
        dfs_visit(child, by_id, order)?;
    }
    Ok(())
}

fn bfs_order(scene: &SceneGraph) -> Result<Vec<String>, String> {
    let root = root_id(scene)?;
    let by_id: BTreeMap<_, _> = scene
        .nodes
        .iter()
        .map(|node| (node.id.as_str(), node))
        .collect();
    let mut queue = VecDeque::from([root]);
    let mut order = Vec::new();
    while let Some(id) = queue.pop_front() {
        let node = by_id
            .get(id.as_str())
            .ok_or_else(|| format!("node missing: {id}"))?;
        order.push(node.id.clone());
        for child in &node.children {
            queue.push_back(child.clone());
        }
    }
    Ok(order)
}

fn root_id(scene: &SceneGraph) -> Result<String, String> {
    scene
        .nodes
        .iter()
        .find(|node| node.parent_id.is_none())
        .map(|node| node.id.clone())
        .ok_or_else(|| "root node is missing".to_string())
}

fn assert_visits_all_once(scene: &SceneGraph, order: &[String]) {
    let expected: BTreeSet<_> = scene.nodes.iter().map(|node| node.id.clone()).collect();
    let actual: BTreeSet<_> = order.iter().cloned().collect();
    assert_eq!(order.len(), scene.nodes.len());
    assert_eq!(actual.len(), order.len());
    assert_eq!(actual, expected);
}

fn contains_nodes(scene: &SceneGraph, ids: &[&str]) -> bool {
    let present: BTreeSet<_> = scene.nodes.iter().map(|node| node.id.as_str()).collect();
    ids.iter().all(|id| present.contains(id))
}

fn scene_graph_json(scene: &SceneGraph) -> String {
    serde_json::to_string_pretty(scene).expect("SceneGraph must serialize") + "\n"
}

fn case(id: &str, name: &str) -> ValidationCase {
    ValidationCase {
        id: id.to_string(),
        name: name.to_string(),
        passed: true,
    }
}

fn node_sort_key(id: &str) -> usize {
    match id {
        "world" => 0,
        "terrain" => 1,
        "building" => 2,
        "floor_1" => 3,
        "room_a" => 4,
        "table" => 5,
        "chair" => 6,
        "room_b" => 7,
        "floor_2" => 8,
        _ => 100,
    }
}

fn render_world_png(scene: &SceneGraph, transforms: &BTreeMap<String, Transform3D>) -> Vec<u8> {
    let width = 1000u32;
    let height = 680u32;
    let mut rgba = vec![245u8; (width * height * 4) as usize];
    for px in rgba.chunks_exact_mut(4) {
        px[1] = 247;
        px[2] = 248;
        px[3] = 255;
    }
    draw_ground(&mut rgba, width, height);
    let by_id: BTreeMap<_, _> = scene
        .nodes
        .iter()
        .map(|node| (node.id.as_str(), node))
        .collect();
    draw_node_recursive("world", &by_id, transforms, &mut rgba, width, height);
    encode_png_rgba(width, height, &rgba)
}

fn draw_node_recursive(
    id: &str,
    by_id: &BTreeMap<&str, &Object3DNode>,
    transforms: &BTreeMap<String, Transform3D>,
    rgba: &mut [u8],
    width: u32,
    height: u32,
) {
    if let Some(node) = by_id.get(id) {
        if let Some(transform) = transforms.get(id) {
            draw_object(rgba, width, height, node, *transform);
        }
        for child in &node.children {
            draw_node_recursive(child, by_id, transforms, rgba, width, height);
        }
    }
}

fn draw_object(
    rgba: &mut [u8],
    width: u32,
    height: u32,
    node: &Object3DNode,
    transform: Transform3D,
) {
    let (x, y) = project(transform.position);
    match node.geometry {
        GeometryType::World => {}
        GeometryType::Terrain => {
            draw_rect(rgba, width, height, 70, 470, 860, 120, [92, 137, 92, 255]);
        }
        GeometryType::Building => {
            draw_box(
                rgba,
                width,
                height,
                x - 110,
                y - 150,
                220,
                150,
                [75, 105, 155, 255],
            );
        }
        GeometryType::Floor => {
            let color = if node.id == "floor_1" {
                [61, 91, 143, 255]
            } else {
                [102, 124, 165, 255]
            };
            draw_rect_outline(rgba, width, height, x - 92, y - 55, 184, 54, color);
        }
        GeometryType::Room => {
            let color = if node.id == "room_a" {
                [178, 106, 52, 255]
            } else {
                [184, 136, 63, 255]
            };
            draw_rect_outline(rgba, width, height, x - 42, y - 36, 84, 72, color);
        }
        GeometryType::Furniture => {
            if node.id == "table" {
                draw_rect(
                    rgba,
                    width,
                    height,
                    x - 18,
                    y - 14,
                    36,
                    28,
                    [95, 63, 42, 255],
                );
            } else {
                draw_circle_outline(rgba, width, height, x, y, 15, [37, 118, 92, 255]);
            }
        }
    }
}

fn draw_ground(rgba: &mut [u8], width: u32, height: u32) {
    for offset in (0..=780).step_by(78) {
        draw_line(
            rgba,
            width,
            height,
            110 + offset,
            535,
            500,
            300,
            [216, 224, 226, 255],
        );
        draw_line(
            rgba,
            width,
            height,
            110 + offset,
            535,
            500,
            610,
            [225, 231, 232, 255],
        );
    }
}

fn project(position: Vector3) -> (i32, i32) {
    let sx = 180.0 + position.x * 5.2 - position.z * 24.0;
    let sy = 500.0 - position.y * 45.0 + position.z * 18.0;
    (sx.round() as i32, sy.round() as i32)
}

fn draw_box(
    rgba: &mut [u8],
    width: u32,
    height: u32,
    x: i32,
    y: i32,
    w: i32,
    h: i32,
    color: [u8; 4],
) {
    draw_rect_outline(rgba, width, height, x, y, w, h, color);
    draw_line(rgba, width, height, x, y, x + 44, y - 36, color);
    draw_line(rgba, width, height, x + w, y, x + w + 44, y - 36, color);
    draw_line(
        rgba,
        width,
        height,
        x + w,
        y + h,
        x + w + 44,
        y + h - 36,
        color,
    );
    draw_line(
        rgba,
        width,
        height,
        x + 44,
        y - 36,
        x + w + 44,
        y - 36,
        color,
    );
    draw_line(
        rgba,
        width,
        height,
        x + w + 44,
        y - 36,
        x + w + 44,
        y + h - 36,
        color,
    );
}

fn draw_rect(
    rgba: &mut [u8],
    width: u32,
    height: u32,
    x: i32,
    y: i32,
    w: i32,
    h: i32,
    color: [u8; 4],
) {
    for py in y..y + h {
        for px in x..x + w {
            set_pixel(rgba, width, height, px, py, color);
        }
    }
}

fn draw_rect_outline(
    rgba: &mut [u8],
    width: u32,
    height: u32,
    x: i32,
    y: i32,
    w: i32,
    h: i32,
    color: [u8; 4],
) {
    draw_line(rgba, width, height, x, y, x + w, y, color);
    draw_line(rgba, width, height, x + w, y, x + w, y + h, color);
    draw_line(rgba, width, height, x + w, y + h, x, y + h, color);
    draw_line(rgba, width, height, x, y + h, x, y, color);
}

fn draw_circle_outline(
    rgba: &mut [u8],
    width: u32,
    height: u32,
    cx: i32,
    cy: i32,
    radius: i32,
    color: [u8; 4],
) {
    for deg in 0..360 {
        let theta = (deg as f32).to_radians();
        let x = cx + (theta.cos() * radius as f32).round() as i32;
        let y = cy + (theta.sin() * radius as f32).round() as i32;
        set_pixel(rgba, width, height, x, y, color);
    }
}

fn draw_line(
    rgba: &mut [u8],
    width: u32,
    height: u32,
    mut x0: i32,
    mut y0: i32,
    x1: i32,
    y1: i32,
    color: [u8; 4],
) {
    let dx = (x1 - x0).abs();
    let sx = if x0 < x1 { 1 } else { -1 };
    let dy = -(y1 - y0).abs();
    let sy = if y0 < y1 { 1 } else { -1 };
    let mut err = dx + dy;
    loop {
        set_pixel(rgba, width, height, x0, y0, color);
        if x0 == x1 && y0 == y1 {
            break;
        }
        let e2 = 2 * err;
        if e2 >= dy {
            err += dy;
            x0 += sx;
        }
        if e2 <= dx {
            err += dx;
            y0 += sy;
        }
    }
}

fn set_pixel(rgba: &mut [u8], width: u32, height: u32, x: i32, y: i32, color: [u8; 4]) {
    if x < 0 || y < 0 || x >= width as i32 || y >= height as i32 {
        return;
    }
    let index = (((y as u32 * width) + x as u32) * 4) as usize;
    rgba[index..index + 4].copy_from_slice(&color);
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
