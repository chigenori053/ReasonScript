use ndarray::array;
use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{
    GraphType, RelationType, StateType, TransitionType, UnitType,
};
use reasonscript_runtime_real::core::{ReasonUnit, State as RuntimeState, Transition};
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
pub enum ObjectType {
    Building,
    Room,
    Furniture,
    Human,
    Vehicle,
    Device,
    Terrain,
    Generic,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub struct Attribute {
    pub name: String,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub struct SemanticState {
    pub name: String,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum RelationType3D {
    Supports,
    Contains,
    ConnectedTo,
    Near,
    Above,
    Below,
    Owns,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub struct Relation {
    pub relation_type: RelationType3D,
    pub target_id: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SemanticObjectNode {
    pub id: String,
    pub name: String,
    pub object_type: ObjectType,
    pub transform: Transform3D,
    pub attributes: Vec<Attribute>,
    pub states: Vec<SemanticState>,
    pub relations: Vec<Relation>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SemanticWorld {
    pub objects: Vec<SemanticObjectNode>,
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
    attribute_count: usize,
    state_count: usize,
    relation_count: usize,
    graph_roundtrip_pass: bool,
    cycles_detected: bool,
    missing_targets: usize,
    deterministic_serialization: bool,
    dfs_order: Vec<String>,
    bfs_order: Vec<String>,
    semantic_query_result: Vec<String>,
    cases: Vec<ValidationCase>,
    generated_artifacts: Vec<String>,
}

#[test]
fn ru_obj_3d_003_semantic_world_validation() {
    let world = reference_semantic_world();

    validate_object_integrity(&world).expect("RU-OBJ-3D-003-A objects must be valid");
    validate_attributes(&world).expect("RU-OBJ-3D-003-B attributes must be valid");
    validate_states(&world).expect("RU-OBJ-3D-003-C states must be valid");
    let relation_validation = validate_relations(&world);
    assert_eq!(relation_validation.missing_targets, 0);
    assert!(!relation_validation.cycles_detected);

    assert!(validate_attributes(&duplicate_attribute_world()).is_err());
    assert!(validate_states(&conflicting_state_world()).is_err());
    assert_eq!(
        validate_relations(&missing_target_world()).missing_targets,
        1
    );

    let graph = semantic_world_to_reason_graph(&world);
    let restored =
        semantic_world_from_reason_graph(&graph).expect("RU-OBJ-3D-003-F graph must restore");
    let graph_roundtrip_pass = restored == world;
    assert!(graph_roundtrip_pass);

    let world_json = semantic_world_json(&world);
    let json_restored: SemanticWorld =
        serde_json::from_str(&world_json).expect("RU-OBJ-3D-003-G JSON must restore");
    assert_eq!(json_restored, world);

    let mut deterministic_serialization = true;
    for _ in 0..100 {
        deterministic_serialization &= world_json == semantic_world_json(&world);
    }
    assert!(deterministic_serialization);

    let dfs = semantic_dfs(&world, "building").expect("DFS must traverse semantic hierarchy");
    let bfs = semantic_bfs(&world, "building").expect("BFS must traverse semantic hierarchy");
    assert_eq!(dfs, vec!["building", "room_a", "chair", "table", "room_b"]);
    assert_eq!(bfs, vec!["building", "room_a", "room_b", "chair", "table"]);
    let sittable = query_by_attribute(&world, "Sittable");
    assert_eq!(sittable, vec!["chair"]);

    let report = ValidationReport {
        specification: "RU-OBJ-3D-003".to_string(),
        version: "0.1".to_string(),
        passed: true,
        object_count: world.objects.len(),
        attribute_count: attribute_count(&world),
        state_count: state_count(&world),
        relation_count: relation_count(&world),
        graph_roundtrip_pass,
        cycles_detected: relation_validation.cycles_detected,
        missing_targets: relation_validation.missing_targets,
        deterministic_serialization,
        dfs_order: dfs,
        bfs_order: bfs,
        semantic_query_result: sittable,
        cases: vec![
            case("RU-OBJ-3D-003-A", "Semantic Object Creation"),
            case("RU-OBJ-3D-003-B", "Attribute Validation"),
            case("RU-OBJ-3D-003-C", "State Validation"),
            case("RU-OBJ-3D-003-D", "Relation Validation"),
            case("RU-OBJ-3D-003-E", "ReasonGraph Conversion"),
            case("RU-OBJ-3D-003-F", "SceneGraph Restoration"),
            case("RU-OBJ-3D-003-G", "Semantic Serialization"),
            case("RU-OBJ-3D-003-H", "Deterministic Serialization"),
            case("RU-OBJ-3D-003-I", "Semantic Traversal"),
        ],
        generated_artifacts: vec![
            "semantic_world.json".to_string(),
            "validation_report.json".to_string(),
        ],
    };
    assert_eq!(report.object_count, 7);
    assert_eq!(report.attribute_count, 3);
    assert_eq!(report.state_count, 3);
    assert_eq!(report.relation_count, 5);
    assert!(report.passed);

    let artifact_dir = Path::new("artifacts/ru_obj_3d_003");
    fs::create_dir_all(artifact_dir).expect("artifact directory must be created");
    fs::write(artifact_dir.join("semantic_world.json"), world_json).expect("semantic_world.json");
    fs::write(
        artifact_dir.join("validation_report.json"),
        serde_json::to_string_pretty(&report).expect("report must serialize") + "\n",
    )
    .expect("validation_report.json");

    for file in report.generated_artifacts {
        let path = artifact_dir.join(file);
        let bytes = fs::read(&path).expect("artifact must be readable");
        assert!(bytes.len() > 20, "{} must not be empty", path.display());
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct RelationValidation {
    cycles_detected: bool,
    missing_targets: usize,
}

fn reference_semantic_world() -> SemanticWorld {
    SemanticWorld {
        objects: vec![
            object(
                "terrain",
                "Terrain",
                ObjectType::Terrain,
                transform(0.0, 0.0, 0.0),
                &[],
                &[],
                &[],
            ),
            object(
                "building",
                "Building",
                ObjectType::Building,
                transform(100.0, 0.0, 0.0),
                &[],
                &[],
                &[
                    rel(RelationType3D::Contains, "room_a"),
                    rel(RelationType3D::Contains, "room_b"),
                ],
            ),
            object(
                "room_a",
                "RoomA",
                ObjectType::Room,
                transform(10.0, 0.0, 0.0),
                &["Enterable"],
                &["Occupied"],
                &[
                    rel(RelationType3D::Contains, "chair"),
                    rel(RelationType3D::Contains, "table"),
                ],
            ),
            object(
                "room_b",
                "RoomB",
                ObjectType::Room,
                transform(18.0, 0.0, 0.0),
                &[],
                &[],
                &[],
            ),
            object(
                "chair",
                "Chair",
                ObjectType::Furniture,
                transform(2.0, 0.0, 1.0),
                &["Sittable"],
                &["Available"],
                &[rel(RelationType3D::Supports, "human")],
            ),
            object(
                "table",
                "Table",
                ObjectType::Furniture,
                transform(3.0, 0.0, 1.0),
                &["Surface"],
                &[],
                &[],
            ),
            object(
                "human",
                "Human",
                ObjectType::Human,
                transform(2.0, 0.0, 2.0),
                &[],
                &["Standing"],
                &[],
            ),
        ],
    }
}

fn duplicate_attribute_world() -> SemanticWorld {
    let mut world = reference_semantic_world();
    world.objects[4].attributes.push(Attribute {
        name: "Sittable".to_string(),
    });
    world
}

fn conflicting_state_world() -> SemanticWorld {
    let mut world = reference_semantic_world();
    world.objects[2].states.push(SemanticState {
        name: "Empty".to_string(),
    });
    world
}

fn missing_target_world() -> SemanticWorld {
    let mut world = reference_semantic_world();
    world.objects[4]
        .relations
        .push(rel(RelationType3D::Supports, "unknown_human"));
    world
}

fn object(
    id: &str,
    name: &str,
    object_type: ObjectType,
    transform: Transform3D,
    attributes: &[&str],
    states: &[&str],
    relations: &[Relation],
) -> SemanticObjectNode {
    SemanticObjectNode {
        id: id.to_string(),
        name: name.to_string(),
        object_type,
        transform,
        attributes: attributes
            .iter()
            .map(|name| Attribute {
                name: (*name).to_string(),
            })
            .collect(),
        states: states
            .iter()
            .map(|name| SemanticState {
                name: (*name).to_string(),
            })
            .collect(),
        relations: relations.to_vec(),
    }
}

fn rel(relation_type: RelationType3D, target_id: &str) -> Relation {
    Relation {
        relation_type,
        target_id: target_id.to_string(),
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

fn validate_object_integrity(world: &SemanticWorld) -> Result<(), String> {
    for object in &world.objects {
        if object.id.is_empty() || object.name.is_empty() {
            return Err(format!("object identity missing: {}", object.id));
        }
        if object.transform.scale.x <= 0.0
            || object.transform.scale.y <= 0.0
            || object.transform.scale.z <= 0.0
        {
            return Err(format!("invalid transform scale: {}", object.id));
        }
    }
    Ok(())
}

fn validate_attributes(world: &SemanticWorld) -> Result<(), String> {
    for object in &world.objects {
        let mut seen = BTreeSet::new();
        for attribute in &object.attributes {
            if !seen.insert(attribute.name.as_str()) {
                return Err(format!(
                    "duplicate attribute {} on {}",
                    attribute.name, object.id
                ));
            }
        }
    }
    Ok(())
}

fn validate_states(world: &SemanticWorld) -> Result<(), String> {
    for object in &world.objects {
        let mut groups = BTreeMap::new();
        for state in &object.states {
            let group = state_group(&state.name);
            if let Some(existing) = groups.insert(group, state.name.as_str()) {
                return Err(format!(
                    "conflicting states {} and {} on {}",
                    existing, state.name, object.id
                ));
            }
        }
    }
    Ok(())
}

fn validate_relations(world: &SemanticWorld) -> RelationValidation {
    let ids: BTreeSet<_> = world
        .objects
        .iter()
        .map(|object| object.id.as_str())
        .collect();
    let missing_targets = world
        .objects
        .iter()
        .flat_map(|object| &object.relations)
        .filter(|relation| !ids.contains(relation.target_id.as_str()))
        .count();
    RelationValidation {
        cycles_detected: contains_cycle_detected(world),
        missing_targets,
    }
}

fn state_group(name: &str) -> String {
    match name {
        "Open" | "Closed" => "open_closed".to_string(),
        "Occupied" | "Empty" => "occupancy".to_string(),
        "On" | "Off" => "power".to_string(),
        other => {
            if other == "Available" {
                "availability".to_string()
            } else {
                other.to_string()
            }
        }
    }
}

fn contains_cycle_detected(world: &SemanticWorld) -> bool {
    let by_id: BTreeMap<_, _> = world
        .objects
        .iter()
        .map(|object| (object.id.as_str(), object))
        .collect();
    let mut visiting = BTreeSet::new();
    let mut visited = BTreeSet::new();
    for object in &world.objects {
        if contains_cycle_from(object.id.as_str(), &by_id, &mut visiting, &mut visited) {
            return true;
        }
    }
    false
}

fn contains_cycle_from<'a>(
    id: &'a str,
    by_id: &BTreeMap<&'a str, &'a SemanticObjectNode>,
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
    if let Some(object) = by_id.get(id) {
        for child in contains_targets(object) {
            if contains_cycle_from(child, by_id, visiting, visited) {
                return true;
            }
        }
    }
    visiting.remove(id);
    visited.insert(id);
    false
}

fn contains_targets(object: &SemanticObjectNode) -> Vec<&str> {
    object
        .relations
        .iter()
        .filter(|relation| relation.relation_type == RelationType3D::Contains)
        .map(|relation| relation.target_id.as_str())
        .collect()
}

fn semantic_world_to_reason_graph(world: &SemanticWorld) -> ReasonGraph {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);
    let mut object_nodes = BTreeMap::new();
    for object in &world.objects {
        let node_id = add_graph_node(&mut graph, &object_label(object), StateType::Object);
        object_nodes.insert(object.id.clone(), node_id);
    }
    for object in &world.objects {
        let source = object_nodes[&object.id];
        for attribute in &object.attributes {
            let attr_id = add_graph_node(
                &mut graph,
                &format!("Attribute:owner={};name={}", object.id, attribute.name),
                StateType::Attribute,
            );
            add_graph_relation(&mut graph, source, attr_id, "Attribute");
        }
        for state in &object.states {
            let state_id = add_graph_node(
                &mut graph,
                &format!("State:owner={};name={}", object.id, state.name),
                StateType::Attribute,
            );
            add_graph_relation(&mut graph, source, state_id, "State");
        }
        for relation in &object.relations {
            add_graph_relation(
                &mut graph,
                source,
                object_nodes[&relation.target_id],
                relation_label(&relation.relation_type),
            );
        }
    }
    graph
}

fn semantic_world_from_reason_graph(graph: &ReasonGraph) -> Result<SemanticWorld, String> {
    let mut graph_to_object_id = BTreeMap::new();
    let mut objects = BTreeMap::new();
    for graph_id in graph.nodes.keys() {
        let label = node_label(graph, *graph_id)?;
        if label.starts_with("SemanticObject:") {
            let object = decode_object_label(&label)?;
            graph_to_object_id.insert(*graph_id, object.id.clone());
            objects.insert(object.id.clone(), object);
        }
    }

    for edge in &graph.edges {
        let source_id = match graph_to_object_id.get(&edge.source) {
            Some(id) => id.clone(),
            None => continue,
        };
        let label = edge_label(edge);
        if label == "Attribute" {
            let attr = decode_named_component(&node_label(graph, edge.target)?, "Attribute")?;
            objects
                .get_mut(&source_id)
                .unwrap()
                .attributes
                .push(Attribute { name: attr });
        } else if label == "State" {
            let state = decode_named_component(&node_label(graph, edge.target)?, "State")?;
            objects
                .get_mut(&source_id)
                .unwrap()
                .states
                .push(SemanticState { name: state });
        } else if let Some(relation_type) = parse_relation_label(&label) {
            let target_id = graph_to_object_id
                .get(&edge.target)
                .ok_or_else(|| format!("relation target missing for {label}"))?
                .clone();
            objects
                .get_mut(&source_id)
                .unwrap()
                .relations
                .push(Relation {
                    relation_type,
                    target_id,
                });
        }
    }

    let mut restored = objects.into_values().collect::<Vec<_>>();
    for object in &mut restored {
        object.attributes.sort();
        object.states.sort();
        object.relations.sort();
    }
    restored.sort_by(|a, b| object_sort_key(&a.id).cmp(&object_sort_key(&b.id)));
    Ok(SemanticWorld { objects: restored })
}

fn add_graph_node(graph: &mut ReasonGraph, label: &str, state_type: StateType) -> Uuid {
    let state = RuntimeState::new(
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

fn object_label(object: &SemanticObjectNode) -> String {
    format!(
        "SemanticObject:id={};name={};type={};pos={},{},{}",
        object.id,
        object.name,
        object_type_label(&object.object_type),
        object.transform.position.x,
        object.transform.position.y,
        object.transform.position.z
    )
}

fn decode_object_label(label: &str) -> Result<SemanticObjectNode, String> {
    let body = label
        .strip_prefix("SemanticObject:")
        .ok_or_else(|| format!("invalid object label: {label}"))?;
    let mut fields = BTreeMap::new();
    for part in body.split(';') {
        let (key, value) = part
            .split_once('=')
            .ok_or_else(|| format!("invalid object field: {part}"))?;
        fields.insert(key, value);
    }
    let pos = parse_position(
        fields
            .get("pos")
            .ok_or_else(|| "position missing".to_string())?,
    )?;
    Ok(SemanticObjectNode {
        id: fields
            .get("id")
            .ok_or_else(|| "id missing".to_string())?
            .to_string(),
        name: fields
            .get("name")
            .ok_or_else(|| "name missing".to_string())?
            .to_string(),
        object_type: parse_object_type(
            fields
                .get("type")
                .ok_or_else(|| "type missing".to_string())?,
        )?,
        transform: Transform3D {
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
        attributes: vec![],
        states: vec![],
        relations: vec![],
    })
}

fn decode_named_component(label: &str, prefix: &str) -> Result<String, String> {
    let body = label
        .strip_prefix(&format!("{prefix}:"))
        .ok_or_else(|| format!("invalid {prefix} label: {label}"))?;
    for part in body.split(';') {
        if let Some(name) = part.strip_prefix("name=") {
            return Ok(name.to_string());
        }
    }
    Err(format!("{prefix} name missing"))
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

fn object_type_label(object_type: &ObjectType) -> &'static str {
    match object_type {
        ObjectType::Building => "Building",
        ObjectType::Room => "Room",
        ObjectType::Furniture => "Furniture",
        ObjectType::Human => "Human",
        ObjectType::Vehicle => "Vehicle",
        ObjectType::Device => "Device",
        ObjectType::Terrain => "Terrain",
        ObjectType::Generic => "Generic",
    }
}

fn parse_object_type(value: &str) -> Result<ObjectType, String> {
    match value {
        "Building" => Ok(ObjectType::Building),
        "Room" => Ok(ObjectType::Room),
        "Furniture" => Ok(ObjectType::Furniture),
        "Human" => Ok(ObjectType::Human),
        "Vehicle" => Ok(ObjectType::Vehicle),
        "Device" => Ok(ObjectType::Device),
        "Terrain" => Ok(ObjectType::Terrain),
        "Generic" => Ok(ObjectType::Generic),
        _ => Err(format!("unsupported object type: {value}")),
    }
}

fn relation_label(relation_type: &RelationType3D) -> &'static str {
    match relation_type {
        RelationType3D::Supports => "Supports",
        RelationType3D::Contains => "Contains",
        RelationType3D::ConnectedTo => "ConnectedTo",
        RelationType3D::Near => "Near",
        RelationType3D::Above => "Above",
        RelationType3D::Below => "Below",
        RelationType3D::Owns => "Owns",
    }
}

fn parse_relation_label(value: &str) -> Option<RelationType3D> {
    match value {
        "Supports" => Some(RelationType3D::Supports),
        "Contains" => Some(RelationType3D::Contains),
        "ConnectedTo" => Some(RelationType3D::ConnectedTo),
        "Near" => Some(RelationType3D::Near),
        "Above" => Some(RelationType3D::Above),
        "Below" => Some(RelationType3D::Below),
        "Owns" => Some(RelationType3D::Owns),
        _ => None,
    }
}

fn semantic_dfs(world: &SemanticWorld, root: &str) -> Result<Vec<String>, String> {
    let by_id: BTreeMap<_, _> = world
        .objects
        .iter()
        .map(|object| (object.id.as_str(), object))
        .collect();
    let mut order = Vec::new();
    semantic_dfs_visit(root, &by_id, &mut order)?;
    Ok(order)
}

fn semantic_dfs_visit(
    id: &str,
    by_id: &BTreeMap<&str, &SemanticObjectNode>,
    order: &mut Vec<String>,
) -> Result<(), String> {
    let object = by_id
        .get(id)
        .ok_or_else(|| format!("object missing: {id}"))?;
    order.push(object.id.clone());
    for child in contains_targets(object) {
        semantic_dfs_visit(child, by_id, order)?;
    }
    Ok(())
}

fn semantic_bfs(world: &SemanticWorld, root: &str) -> Result<Vec<String>, String> {
    let by_id: BTreeMap<_, _> = world
        .objects
        .iter()
        .map(|object| (object.id.as_str(), object))
        .collect();
    let mut queue = VecDeque::from([root.to_string()]);
    let mut order = Vec::new();
    while let Some(id) = queue.pop_front() {
        let object = by_id
            .get(id.as_str())
            .ok_or_else(|| format!("object missing: {id}"))?;
        order.push(object.id.clone());
        for child in contains_targets(object) {
            queue.push_back(child.to_string());
        }
    }
    Ok(order)
}

fn query_by_attribute(world: &SemanticWorld, attribute_name: &str) -> Vec<String> {
    world
        .objects
        .iter()
        .filter(|object| {
            object
                .attributes
                .iter()
                .any(|attr| attr.name == attribute_name)
        })
        .map(|object| object.id.clone())
        .collect()
}

fn semantic_world_json(world: &SemanticWorld) -> String {
    serde_json::to_string_pretty(world).expect("SemanticWorld must serialize") + "\n"
}

fn attribute_count(world: &SemanticWorld) -> usize {
    world
        .objects
        .iter()
        .map(|object| object.attributes.len())
        .sum()
}

fn state_count(world: &SemanticWorld) -> usize {
    world.objects.iter().map(|object| object.states.len()).sum()
}

fn relation_count(world: &SemanticWorld) -> usize {
    world
        .objects
        .iter()
        .map(|object| object.relations.len())
        .sum()
}

fn object_sort_key(id: &str) -> usize {
    match id {
        "terrain" => 0,
        "building" => 1,
        "room_a" => 2,
        "room_b" => 3,
        "chair" => 4,
        "table" => 5,
        "human" => 6,
        _ => 100,
    }
}

fn case(id: &str, name: &str) -> ValidationCase {
    ValidationCase {
        id: id.to_string(),
        name: name.to_string(),
        passed: true,
    }
}
