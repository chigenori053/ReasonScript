use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Position3D {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Transform3D {
    pub position: Position3D,
    pub rotation: Position3D,
    pub scale: Position3D,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum ObjectType {
    Building,
    Room,
    Furniture,
    Human,
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
    Contains,
    Supports,
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
pub struct SemanticSceneGraph {
    pub objects: Vec<SemanticObjectNode>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct StateDelta {
    pub object_id: String,
    pub removed_states: Vec<String>,
    pub added_states: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RelationDelta {
    pub source_id: String,
    pub removed_relations: Vec<Relation>,
    pub added_relations: Vec<Relation>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TransformDelta {
    pub object_id: String,
    pub old_position: Position3D,
    pub new_position: Position3D,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WorldSnapshot {
    pub timestamp: u64,
    pub scene_graph: SemanticSceneGraph,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TransitionTrace {
    pub snapshots: Vec<WorldSnapshot>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
struct WorldTransition {
    id: String,
    state_deltas: Vec<StateDelta>,
    relation_deltas: Vec<RelationDelta>,
    transform_deltas: Vec<TransformDelta>,
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
    snapshot_count: usize,
    transition_count: usize,
    state_transition_pass: bool,
    relation_transition_pass: bool,
    containment_preserved: bool,
    deterministic_replay: bool,
    cases: Vec<ValidationCase>,
    generated_artifacts: Vec<String>,
}

#[test]
fn ru_obj_3d_004_dynamic_semantic_world_validation() {
    let world_t0 = initial_world();
    validate_world(&world_t0).expect("RU-OBJ-3D-004 initial world must be valid");

    let transition_0 = WorldTransition {
        id: "dt_001_state_relation_change".to_string(),
        state_deltas: vec![
            StateDelta {
                object_id: "chair".to_string(),
                removed_states: vec!["Available".to_string()],
                added_states: vec!["Occupied".to_string()],
            },
            StateDelta {
                object_id: "human".to_string(),
                removed_states: vec!["Standing".to_string()],
                added_states: vec!["Walking".to_string()],
            },
        ],
        relation_deltas: vec![RelationDelta {
            source_id: "chair".to_string(),
            removed_relations: vec![rel(RelationType3D::Supports, "human")],
            added_relations: vec![],
        }],
        transform_deltas: vec![TransformDelta {
            object_id: "human".to_string(),
            old_position: pos(2.0, 0.0, 2.0),
            new_position: pos(14.0, 0.0, 2.0),
        }],
    };
    let world_t1 = apply_transition(&world_t0, &transition_0)
        .expect("RU-OBJ-3D-004 t0 -> t1 transition must apply");

    let transition_1 = WorldTransition {
        id: "dt_004_compound_transition".to_string(),
        state_deltas: vec![StateDelta {
            object_id: "human".to_string(),
            removed_states: vec!["Walking".to_string()],
            added_states: vec!["Sitting".to_string()],
        }],
        relation_deltas: vec![
            RelationDelta {
                source_id: "room_a".to_string(),
                removed_relations: vec![rel(RelationType3D::Contains, "human")],
                added_relations: vec![],
            },
            RelationDelta {
                source_id: "room_b".to_string(),
                removed_relations: vec![],
                added_relations: vec![rel(RelationType3D::Contains, "human")],
            },
        ],
        transform_deltas: vec![TransformDelta {
            object_id: "human".to_string(),
            old_position: pos(14.0, 0.0, 2.0),
            new_position: pos(22.0, 0.0, 2.0),
        }],
    };
    let world_t2 = apply_transition(&world_t1, &transition_1)
        .expect("RU-OBJ-3D-004 t1 -> t2 transition must apply");

    let trace = TransitionTrace {
        snapshots: vec![
            WorldSnapshot {
                timestamp: 0,
                scene_graph: world_t0.clone(),
            },
            WorldSnapshot {
                timestamp: 1,
                scene_graph: world_t1.clone(),
            },
            WorldSnapshot {
                timestamp: 2,
                scene_graph: world_t2.clone(),
            },
        ],
    };

    assert!(trace
        .snapshots
        .iter()
        .all(|snapshot| validate_world(&snapshot.scene_graph).is_ok()));
    assert!(has_state(&world_t1, "chair", "Occupied"));
    assert!(has_state(&world_t2, "human", "Sitting"));
    assert!(contains_relation(
        &world_t2,
        "room_b",
        RelationType3D::Contains,
        "human"
    ));
    assert!(!contains_relation(
        &world_t2,
        "chair",
        RelationType3D::Supports,
        "human"
    ));
    assert_eq!(
        object_position(&world_t2, "human"),
        Some(pos(22.0, 0.0, 2.0))
    );

    assert!(validate_world(&conflicting_state_world()).is_err());
    assert!(validate_world(&missing_relation_target_world()).is_err());

    let replay_json = serde_json::to_string_pretty(&trace).expect("trace must serialize");
    let mut deterministic_replay = true;
    for _ in 0..100 {
        let replay = replay_transitions(
            &initial_world(),
            &[transition_0.clone(), transition_1.clone()],
        )
        .expect("deterministic replay must apply");
        deterministic_replay &= replay_json
            == serde_json::to_string_pretty(&replay).expect("replay trace must serialize");
    }
    assert!(deterministic_replay);

    let report = ValidationReport {
        specification: "RU-OBJ-3D-004".to_string(),
        version: "0.1".to_string(),
        passed: true,
        snapshot_count: trace.snapshots.len(),
        transition_count: 2,
        state_transition_pass: has_state(&world_t1, "chair", "Occupied")
            && has_state(&world_t2, "human", "Sitting"),
        relation_transition_pass: !contains_relation(
            &world_t2,
            "chair",
            RelationType3D::Supports,
            "human",
        ),
        containment_preserved: contains_relation(
            &world_t2,
            "room_b",
            RelationType3D::Contains,
            "human",
        ),
        deterministic_replay,
        cases: vec![
            case("RU-OBJ-3D-004-A", "State Change"),
            case("RU-OBJ-3D-004-B", "Object Relocation"),
            case("RU-OBJ-3D-004-C", "Relation Change"),
            case("RU-OBJ-3D-004-D", "Compound Transition"),
            case("RU-OBJ-3D-004-E", "Snapshot Validation"),
            case("RU-OBJ-3D-004-F", "Transition Trace"),
            case("RU-OBJ-3D-004-G", "Deterministic Replay"),
        ],
        generated_artifacts: vec![
            "world_t0.json".to_string(),
            "world_t1.json".to_string(),
            "world_t2.json".to_string(),
            "transition_trace.json".to_string(),
            "validation_report.json".to_string(),
            "world_transition.png".to_string(),
        ],
    };
    assert!(report.passed);
    assert_eq!(report.snapshot_count, 3);
    assert_eq!(report.transition_count, 2);
    assert!(report.state_transition_pass);
    assert!(report.relation_transition_pass);
    assert!(report.containment_preserved);
    assert!(report.deterministic_replay);

    let artifact_dir = Path::new("artifacts/ru_obj_3d_004");
    fs::create_dir_all(artifact_dir).expect("artifact directory must be created");
    fs::write(
        artifact_dir.join("world_t0.json"),
        semantic_world_json(&world_t0),
    )
    .expect("world_t0.json");
    fs::write(
        artifact_dir.join("world_t1.json"),
        semantic_world_json(&world_t1),
    )
    .expect("world_t1.json");
    fs::write(
        artifact_dir.join("world_t2.json"),
        semantic_world_json(&world_t2),
    )
    .expect("world_t2.json");
    fs::write(
        artifact_dir.join("transition_trace.json"),
        replay_json + "\n",
    )
    .expect("transition_trace.json");
    fs::write(
        artifact_dir.join("validation_report.json"),
        serde_json::to_string_pretty(&report).expect("report must serialize") + "\n",
    )
    .expect("validation_report.json");
    fs::write(
        artifact_dir.join("world_transition.png"),
        render_transition_png(&trace),
    )
    .expect("world_transition.png");

    for file in report.generated_artifacts {
        let path = artifact_dir.join(file);
        let bytes = fs::read(&path).expect("artifact must be readable");
        assert!(bytes.len() > 20, "{} must not be empty", path.display());
    }
}

fn initial_world() -> SemanticSceneGraph {
    SemanticSceneGraph {
        objects: vec![
            object(
                "building",
                "Building",
                ObjectType::Building,
                transform(0.0, 0.0, 0.0),
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
                &[],
                &[
                    rel(RelationType3D::Contains, "chair"),
                    rel(RelationType3D::Contains, "human"),
                ],
            ),
            object(
                "room_b",
                "RoomB",
                ObjectType::Room,
                transform(20.0, 0.0, 0.0),
                &["Enterable"],
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
        position: pos(x, y, z),
        rotation: pos(0.0, 0.0, 0.0),
        scale: pos(1.0, 1.0, 1.0),
    }
}

fn pos(x: f32, y: f32, z: f32) -> Position3D {
    Position3D { x, y, z }
}

fn apply_transition(
    world: &SemanticSceneGraph,
    transition: &WorldTransition,
) -> Result<SemanticSceneGraph, String> {
    let mut next = world.clone();
    for delta in &transition.state_deltas {
        let object = find_object_mut(&mut next, &delta.object_id)?;
        object
            .states
            .retain(|state| !delta.removed_states.contains(&state.name));
        for state in &delta.added_states {
            if !object.states.iter().any(|existing| existing.name == *state) {
                object.states.push(SemanticState {
                    name: state.clone(),
                });
            }
        }
        object.states.sort();
    }
    for delta in &transition.relation_deltas {
        let object = find_object_mut(&mut next, &delta.source_id)?;
        object
            .relations
            .retain(|relation| !delta.removed_relations.contains(relation));
        for relation in &delta.added_relations {
            if !object.relations.contains(relation) {
                object.relations.push(relation.clone());
            }
        }
        object.relations.sort();
    }
    for delta in &transition.transform_deltas {
        let object = find_object_mut(&mut next, &delta.object_id)?;
        if object.transform.position != delta.old_position {
            return Err(format!("stale transform delta for {}", delta.object_id));
        }
        object.transform.position = delta.new_position;
    }
    validate_world(&next)?;
    Ok(next)
}

fn replay_transitions(
    initial: &SemanticSceneGraph,
    transitions: &[WorldTransition],
) -> Result<TransitionTrace, String> {
    let mut snapshots = vec![WorldSnapshot {
        timestamp: 0,
        scene_graph: initial.clone(),
    }];
    let mut current = initial.clone();
    for (index, transition) in transitions.iter().enumerate() {
        current = apply_transition(&current, transition)?;
        snapshots.push(WorldSnapshot {
            timestamp: (index + 1) as u64,
            scene_graph: current.clone(),
        });
    }
    Ok(TransitionTrace { snapshots })
}

fn find_object_mut<'a>(
    world: &'a mut SemanticSceneGraph,
    object_id: &str,
) -> Result<&'a mut SemanticObjectNode, String> {
    world
        .objects
        .iter_mut()
        .find(|object| object.id == object_id)
        .ok_or_else(|| format!("object not found: {object_id}"))
}

fn validate_world(world: &SemanticSceneGraph) -> Result<(), String> {
    let mut ids = BTreeSet::new();
    for object in &world.objects {
        if object.id.is_empty() || object.name.is_empty() {
            return Err(format!("object identity missing: {}", object.id));
        }
        if !ids.insert(object.id.as_str()) {
            return Err(format!("duplicate object id: {}", object.id));
        }
        if object.transform.scale.x <= 0.0
            || object.transform.scale.y <= 0.0
            || object.transform.scale.z <= 0.0
        {
            return Err(format!("invalid transform scale: {}", object.id));
        }
        let mut attributes = BTreeSet::new();
        for attribute in &object.attributes {
            if !attributes.insert(attribute.name.as_str()) {
                return Err(format!("duplicate attribute on {}", object.id));
            }
        }
        let mut state_groups = BTreeMap::new();
        for state in &object.states {
            let group = state_group(&state.name);
            if let Some(existing) = state_groups.insert(group, state.name.as_str()) {
                return Err(format!(
                    "conflicting states {} and {} on {}",
                    existing, state.name, object.id
                ));
            }
        }
    }
    for object in &world.objects {
        for relation in &object.relations {
            if !ids.contains(relation.target_id.as_str()) {
                return Err(format!(
                    "missing relation target {} from {}",
                    relation.target_id, object.id
                ));
            }
        }
    }
    validate_containment(world)
}

fn validate_containment(world: &SemanticSceneGraph) -> Result<(), String> {
    let mut parents = BTreeMap::new();
    for object in &world.objects {
        for relation in &object.relations {
            if relation.relation_type == RelationType3D::Contains {
                if let Some(previous) =
                    parents.insert(relation.target_id.as_str(), object.id.as_str())
                {
                    return Err(format!(
                        "object {} has multiple containers: {}, {}",
                        relation.target_id, previous, object.id
                    ));
                }
            }
        }
    }
    let required = ["room_a", "room_b", "chair", "human"];
    for object_id in required {
        if !parents.contains_key(object_id) {
            return Err(format!("contained object missing parent: {object_id}"));
        }
    }
    Ok(())
}

fn state_group(name: &str) -> String {
    match name {
        "Open" | "Closed" => "open_closed".to_string(),
        "Available" | "Occupied" => "availability".to_string(),
        "Standing" | "Walking" | "Sitting" => "posture".to_string(),
        other => other.to_string(),
    }
}

fn conflicting_state_world() -> SemanticSceneGraph {
    let mut world = initial_world();
    find_object_mut(&mut world, "chair")
        .expect("chair must exist")
        .states
        .push(SemanticState {
            name: "Occupied".to_string(),
        });
    world
}

fn missing_relation_target_world() -> SemanticSceneGraph {
    let mut world = initial_world();
    find_object_mut(&mut world, "chair")
        .expect("chair must exist")
        .relations
        .push(rel(RelationType3D::Supports, "unknown_human"));
    world
}

fn has_state(world: &SemanticSceneGraph, object_id: &str, state_name: &str) -> bool {
    world
        .objects
        .iter()
        .find(|object| object.id == object_id)
        .is_some_and(|object| object.states.iter().any(|state| state.name == state_name))
}

fn contains_relation(
    world: &SemanticSceneGraph,
    source_id: &str,
    relation_type: RelationType3D,
    target_id: &str,
) -> bool {
    world
        .objects
        .iter()
        .find(|object| object.id == source_id)
        .is_some_and(|object| {
            object.relations.iter().any(|relation| {
                relation.relation_type == relation_type && relation.target_id == target_id
            })
        })
}

fn object_position(world: &SemanticSceneGraph, object_id: &str) -> Option<Position3D> {
    world
        .objects
        .iter()
        .find(|object| object.id == object_id)
        .map(|object| object.transform.position)
}

fn semantic_world_json(world: &SemanticSceneGraph) -> String {
    serde_json::to_string_pretty(world).expect("world must serialize") + "\n"
}

fn case(id: &str, name: &str) -> ValidationCase {
    ValidationCase {
        id: id.to_string(),
        name: name.to_string(),
        passed: true,
    }
}

fn render_transition_png(trace: &TransitionTrace) -> Vec<u8> {
    let width = 720;
    let height = 260;
    let mut rgba = vec![245u8; (width * height * 4) as usize];
    for pixel in rgba.chunks_exact_mut(4) {
        pixel.copy_from_slice(&[246, 247, 244, 255]);
    }

    for (index, snapshot) in trace.snapshots.iter().enumerate() {
        let x_offset = 40 + index as i32 * 220;
        draw_room(&mut rgba, width, height, x_offset, 58, [120, 150, 190, 255]);
        draw_room(
            &mut rgba,
            width,
            height,
            x_offset + 90,
            58,
            [150, 180, 145, 255],
        );
        for object in &snapshot.scene_graph.objects {
            match object.id.as_str() {
                "chair" => draw_rect(
                    &mut rgba,
                    width,
                    height,
                    x_offset + 24,
                    120,
                    28,
                    24,
                    [70, 100, 145, 255],
                ),
                "human" => {
                    let px = if contains_relation(
                        &snapshot.scene_graph,
                        "room_b",
                        RelationType3D::Contains,
                        "human",
                    ) {
                        x_offset + 120
                    } else if object.transform.position.x > 10.0 {
                        x_offset + 72
                    } else {
                        x_offset + 34
                    };
                    let color = if has_state(&snapshot.scene_graph, "human", "Sitting") {
                        [170, 90, 80, 255]
                    } else if has_state(&snapshot.scene_graph, "human", "Walking") {
                        [205, 145, 65, 255]
                    } else {
                        [80, 135, 95, 255]
                    };
                    draw_rect(&mut rgba, width, height, px, 90, 20, 42, color);
                }
                _ => {}
            }
        }
        draw_line(
            &mut rgba,
            width,
            height,
            x_offset + 170,
            125,
            x_offset + 205,
            125,
            [70, 70, 70, 255],
        );
    }

    encode_png_rgba(width, height, &rgba)
}

fn draw_room(rgba: &mut [u8], width: u32, height: u32, x: i32, y: i32, color: [u8; 4]) {
    draw_rect(rgba, width, height, x, y, 72, 116, [255, 255, 255, 255]);
    draw_line(rgba, width, height, x, y, x + 72, y, color);
    draw_line(rgba, width, height, x + 72, y, x + 72, y + 116, color);
    draw_line(rgba, width, height, x + 72, y + 116, x, y + 116, color);
    draw_line(rgba, width, height, x, y + 116, x, y, color);
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
    for yy in y.max(0)..(y + h).min(height as i32) {
        for xx in x.max(0)..(x + w).min(width as i32) {
            let offset = ((yy as u32 * width + xx as u32) * 4) as usize;
            rgba[offset..offset + 4].copy_from_slice(&color);
        }
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
        draw_rect(rgba, width, height, x0, y0, 2, 2, color);
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

fn encode_png_rgba(width: u32, height: u32, rgba: &[u8]) -> Vec<u8> {
    let mut raw = Vec::with_capacity(((width * 4 + 1) * height) as usize);
    for y in 0..height {
        raw.push(0);
        let start = (y * width * 4) as usize;
        raw.extend_from_slice(&rgba[start..start + (width * 4) as usize]);
    }

    let mut png = Vec::new();
    png.extend_from_slice(&[137, 80, 78, 71, 13, 10, 26, 10]);
    let mut ihdr = Vec::new();
    ihdr.extend_from_slice(&width.to_be_bytes());
    ihdr.extend_from_slice(&height.to_be_bytes());
    ihdr.extend_from_slice(&[8, 6, 0, 0, 0]);
    write_png_chunk(&mut png, b"IHDR", &ihdr);
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
    let mut remaining = data;
    while !remaining.is_empty() {
        let chunk_len = remaining.len().min(65_535);
        let final_block = chunk_len == remaining.len();
        out.push(if final_block { 1 } else { 0 });
        let len = chunk_len as u16;
        out.extend_from_slice(&len.to_le_bytes());
        out.extend_from_slice(&(!len).to_le_bytes());
        out.extend_from_slice(&remaining[..chunk_len]);
        remaining = &remaining[chunk_len..];
    }
    out.extend_from_slice(&adler32(data).to_be_bytes());
    out
}

fn crc32(data: &[u8]) -> u32 {
    let mut crc = 0xffff_ffffu32;
    for &byte in data {
        crc ^= byte as u32;
        for _ in 0..8 {
            crc = if crc & 1 != 0 {
                (crc >> 1) ^ 0xedb8_8320
            } else {
                crc >> 1
            };
        }
    }
    !crc
}

fn adler32(data: &[u8]) -> u32 {
    let mut a = 1u32;
    let mut b = 0u32;
    for &byte in data {
        a = (a + byte as u32) % 65_521;
        b = (b + a) % 65_521;
    }
    (b << 16) | a
}
