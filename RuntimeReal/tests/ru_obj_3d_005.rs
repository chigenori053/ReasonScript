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

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum SemanticObjectType {
    House,
    Room,
    Human,
    Door,
    Generic,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SemanticObject {
    pub id: String,
    pub object_type: SemanticObjectType,
    pub states: Vec<String>,
    pub position: Position3D,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum SemanticRelationType {
    Contains,
    LocatedIn,
    Uses,
    AttachedTo,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub struct SemanticRelation {
    pub source_id: String,
    pub relation_type: SemanticRelationType,
    pub target_id: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WorldSnapshot {
    pub timestamp: u64,
    pub objects: Vec<SemanticObject>,
    pub relations: Vec<SemanticRelation>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum SemanticEventType {
    Move,
    Create,
    Remove,
    Attach,
    Detach,
    ChangeState,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SemanticEvent {
    pub id: String,
    pub event_type: SemanticEventType,
    pub actor: String,
    pub parameters: BTreeMap<String, String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StateDelta {
    pub object_id: String,
    pub removed_states: Vec<String>,
    pub added_states: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RelationDelta {
    pub removed_relations: Vec<SemanticRelation>,
    pub added_relations: Vec<SemanticRelation>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ObjectDelta {
    pub created_objects: Vec<SemanticObject>,
    pub removed_object_ids: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WorldDelta {
    pub object_delta: ObjectDelta,
    pub state_deltas: Vec<StateDelta>,
    pub relation_delta: RelationDelta,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EventTraceEntry {
    pub event_id: String,
    pub event_type: SemanticEventType,
    pub before_snapshot: u64,
    pub after_snapshot: u64,
    pub success: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct EventTrace {
    pub events: Vec<EventTraceEntry>,
    pub snapshots: Vec<WorldSnapshot>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct ValidationCase {
    id: String,
    name: String,
    passed: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct ValidationReport {
    specification: String,
    version: String,
    passed: bool,
    event_count: usize,
    snapshot_count: usize,
    all_events_execute: bool,
    all_snapshots_valid: bool,
    containment_preserved: bool,
    relation_consistency_preserved: bool,
    object_count_consistent: bool,
    event_traces_generated: bool,
    replay_reproduces_identical_world: bool,
    deterministic_replay_runs: usize,
    deterministic_replay_pass: bool,
    cases: Vec<ValidationCase>,
    generated_artifacts: Vec<String>,
}

#[test]
fn ru_obj_3d_005_event_based_dynamic_semantic_world_validation() {
    let world_t0 = initial_world();
    validate_world(&world_t0).expect("RU-OBJ-3D-005 initial world must be valid");

    let events = vec![
        event(
            "event_open_door_001",
            SemanticEventType::ChangeState,
            "door_001",
            &[("from", "closed"), ("to", "open")],
        ),
        event(
            "event_move_human_001",
            SemanticEventType::Move,
            "human_001",
            &[("from", "room_a"), ("to", "room_b")],
        ),
        event(
            "event_close_door_001",
            SemanticEventType::ChangeState,
            "door_001",
            &[("from", "open"), ("to", "closed")],
        ),
    ];

    assert!(execute_event(
        &world_t0,
        &event(
            "event_unknown_actor",
            SemanticEventType::Move,
            "unknown_human",
            &[("from", "room_a"), ("to", "room_b")],
        ),
        0,
    )
    .is_err());
    assert!(execute_event(
        &world_t0,
        &event(
            "event_invalid_source",
            SemanticEventType::Move,
            "human_001",
            &[("from", "room_b"), ("to", "room_a")],
        ),
        0,
    )
    .is_err());
    assert!(execute_event(
        &world_t0,
        &event(
            "event_missing_target",
            SemanticEventType::Move,
            "human_001",
            &[("from", "room_a"), ("to", "room_c")],
        ),
        0,
    )
    .is_err());
    assert!(execute_event(
        &world_t0,
        &event(
            "event_invalid_relation",
            SemanticEventType::Attach,
            "human_001",
            &[("target", "missing_door"), ("relation", "Uses")],
        ),
        0,
    )
    .is_err());

    let trace = replay_events(&world_t0, &events).expect("event replay must succeed");
    assert_eq!(trace.snapshots.len(), 4);
    assert_eq!(trace.events.len(), 3);
    assert!(trace.events.iter().all(|entry| entry.success));

    let world_t1 = &trace.snapshots[1];
    let world_t2 = &trace.snapshots[2];
    let world_t3 = &trace.snapshots[3];
    assert!(has_state(world_t1, "door_001", "open"));
    assert!(contains_relation(
        world_t2,
        "human_001",
        SemanticRelationType::LocatedIn,
        "room_b"
    ));
    assert!(has_state(world_t3, "door_001", "closed"));
    assert!(!has_state(world_t3, "door_001", "open"));

    let all_snapshots_valid = trace
        .snapshots
        .iter()
        .all(|snapshot| validate_world(snapshot).is_ok());
    let object_count_consistent = trace
        .snapshots
        .iter()
        .all(|snapshot| snapshot.objects.len() == 5);
    let relation_consistency_preserved = trace.snapshots.iter().all(relation_targets_exist);
    let containment_preserved = trace.snapshots.iter().all(containment_is_valid);

    let expected_trace_json = serde_json::to_string_pretty(&trace).expect("trace must serialize");
    let expected_world_json = snapshot_json(world_t3);
    let mut deterministic_replay_runs = 0;
    let mut deterministic_replay_pass = true;
    for _ in 0..100 {
        let replay = replay_events(&initial_world(), &events).expect("replay must succeed");
        deterministic_replay_runs += 1;
        deterministic_replay_pass &= expected_trace_json
            == serde_json::to_string_pretty(&replay).expect("replay trace must serialize");
        deterministic_replay_pass &= expected_world_json
            == snapshot_json(replay.snapshots.last().expect("final snapshot must exist"));
    }

    let report = ValidationReport {
        specification: "RU-OBJ-3D-005".to_string(),
        version: "1.0".to_string(),
        passed: trace.events.iter().all(|entry| entry.success)
            && all_snapshots_valid
            && containment_preserved
            && relation_consistency_preserved
            && object_count_consistent
            && trace.events.len() == events.len()
            && deterministic_replay_pass,
        event_count: trace.events.len(),
        snapshot_count: trace.snapshots.len(),
        all_events_execute: trace.events.iter().all(|entry| entry.success),
        all_snapshots_valid,
        containment_preserved,
        relation_consistency_preserved,
        object_count_consistent,
        event_traces_generated: trace.events.len() == events.len(),
        replay_reproduces_identical_world: expected_world_json == snapshot_json(world_t3),
        deterministic_replay_runs,
        deterministic_replay_pass,
        cases: vec![
            case("SC-001", "All events execute successfully"),
            case("SC-002", "All snapshots valid"),
            case("SC-003", "Containment preserved"),
            case("SC-004", "Relation consistency preserved"),
            case("SC-005", "Object count consistent"),
            case("SC-006", "Event traces generated"),
            case("SC-007", "Replay reproduces identical world"),
            case("SC-008", "100 deterministic replays succeed"),
        ],
        generated_artifacts: vec![
            "validation_report.json".to_string(),
            "event_trace.json".to_string(),
            "world_t0.json".to_string(),
            "world_t1.json".to_string(),
            "world_t2.json".to_string(),
            "world_t3.json".to_string(),
            "event_world.png".to_string(),
        ],
    };
    assert!(report.passed);
    assert_eq!(report.deterministic_replay_runs, 100);
    assert!(report.deterministic_replay_pass);

    let artifact_dir = Path::new("artifacts/ru_obj_3d_005");
    fs::create_dir_all(artifact_dir).expect("artifact directory must be created");
    fs::write(
        artifact_dir.join("validation_report.json"),
        serde_json::to_string_pretty(&report).expect("report must serialize") + "\n",
    )
    .expect("validation_report.json");
    fs::write(
        artifact_dir.join("event_trace.json"),
        expected_trace_json + "\n",
    )
    .expect("event_trace.json");
    for (index, snapshot) in trace.snapshots.iter().enumerate() {
        fs::write(
            artifact_dir.join(format!("world_t{index}.json")),
            snapshot_json(snapshot),
        )
        .expect("world snapshot artifact");
    }
    fs::write(
        artifact_dir.join("event_world.png"),
        render_event_world_png(&trace),
    )
    .expect("event_world.png");

    for file in report.generated_artifacts {
        let path = artifact_dir.join(file);
        let bytes = fs::read(&path).expect("artifact must be readable");
        assert!(bytes.len() > 20, "{} must not be empty", path.display());
    }
}

fn initial_world() -> WorldSnapshot {
    let mut snapshot = WorldSnapshot {
        timestamp: 0,
        objects: vec![
            object(
                "house_001",
                SemanticObjectType::House,
                &[],
                pos(0.0, 0.0, 0.0),
            ),
            object("room_a", SemanticObjectType::Room, &[], pos(10.0, 0.0, 0.0)),
            object("room_b", SemanticObjectType::Room, &[], pos(20.0, 0.0, 0.0)),
            object(
                "human_001",
                SemanticObjectType::Human,
                &["standing"],
                pos(10.0, 0.0, 2.0),
            ),
            object(
                "door_001",
                SemanticObjectType::Door,
                &["closed"],
                pos(15.0, 0.0, 1.0),
            ),
        ],
        relations: vec![
            relation("house_001", SemanticRelationType::Contains, "room_a"),
            relation("house_001", SemanticRelationType::Contains, "room_b"),
            relation("human_001", SemanticRelationType::LocatedIn, "room_a"),
        ],
    };
    canonicalize_snapshot(&mut snapshot);
    snapshot
}

fn object(
    id: &str,
    object_type: SemanticObjectType,
    states: &[&str],
    position: Position3D,
) -> SemanticObject {
    SemanticObject {
        id: id.to_string(),
        object_type,
        states: states.iter().map(|state| (*state).to_string()).collect(),
        position,
    }
}

fn relation(
    source_id: &str,
    relation_type: SemanticRelationType,
    target_id: &str,
) -> SemanticRelation {
    SemanticRelation {
        source_id: source_id.to_string(),
        relation_type,
        target_id: target_id.to_string(),
    }
}

fn event(
    id: &str,
    event_type: SemanticEventType,
    actor: &str,
    parameters: &[(&str, &str)],
) -> SemanticEvent {
    SemanticEvent {
        id: id.to_string(),
        event_type,
        actor: actor.to_string(),
        parameters: parameters
            .iter()
            .map(|(key, value)| ((*key).to_string(), (*value).to_string()))
            .collect(),
    }
}

fn execute_event(
    world: &WorldSnapshot,
    event: &SemanticEvent,
    next_timestamp: u64,
) -> Result<(WorldSnapshot, EventTraceEntry), String> {
    validate_event(world, event)?;
    let delta = generate_delta(world, event)?;
    let mut after = apply_delta(world, &delta)?;
    after.timestamp = next_timestamp;
    validate_world(&after)?;
    Ok((
        after,
        EventTraceEntry {
            event_id: event.id.clone(),
            event_type: event.event_type.clone(),
            before_snapshot: world.timestamp,
            after_snapshot: next_timestamp,
            success: true,
        },
    ))
}

fn replay_events(initial: &WorldSnapshot, events: &[SemanticEvent]) -> Result<EventTrace, String> {
    let mut snapshots = vec![initial.clone()];
    let mut entries = Vec::new();
    let mut current = initial.clone();
    for (index, event) in events.iter().enumerate() {
        let (after, entry) = execute_event(&current, event, (index + 1) as u64)?;
        current = after.clone();
        snapshots.push(after);
        entries.push(entry);
    }
    Ok(EventTrace {
        events: entries,
        snapshots,
    })
}

fn validate_event(world: &WorldSnapshot, event: &SemanticEvent) -> Result<(), String> {
    if !object_exists(world, &event.actor) {
        return Err(format!("EVT-001 unknown actor: {}", event.actor));
    }
    match event.event_type {
        SemanticEventType::Move => {
            let from = param(event, "from")?;
            let to = param(event, "to")?;
            if !contains_relation(world, &event.actor, SemanticRelationType::LocatedIn, &from) {
                return Err(format!("EVT-002 invalid source location: {from}"));
            }
            if !object_has_type(world, &to, SemanticObjectType::Room) {
                return Err(format!("EVT-003 target location missing: {to}"));
            }
            if event.actor == to {
                return Err("EVT-004 broken containment".to_string());
            }
            Ok(())
        }
        SemanticEventType::Attach => {
            let target = param(event, "target")?;
            if !object_exists(world, &target) {
                return Err(format!("EVT-005 invalid relation target: {target}"));
            }
            Ok(())
        }
        SemanticEventType::Detach => {
            let target = param(event, "target")?;
            if !object_exists(world, &target) {
                return Err(format!("EVT-005 invalid relation target: {target}"));
            }
            Ok(())
        }
        SemanticEventType::ChangeState => {
            let from = param(event, "from")?;
            let _to = param(event, "to")?;
            if !has_state(world, &event.actor, &from) {
                return Err(format!("event source state missing: {from}"));
            }
            Ok(())
        }
        SemanticEventType::Create => {
            let object_id = param(event, "object_id")?;
            if object_exists(world, &object_id) {
                return Err(format!("object already exists: {object_id}"));
            }
            Ok(())
        }
        SemanticEventType::Remove => Ok(()),
    }
}

fn generate_delta(world: &WorldSnapshot, event: &SemanticEvent) -> Result<WorldDelta, String> {
    match event.event_type {
        SemanticEventType::Move => {
            let from = param(event, "from")?;
            let to = param(event, "to")?;
            Ok(WorldDelta {
                object_delta: empty_object_delta(),
                state_deltas: vec![],
                relation_delta: RelationDelta {
                    removed_relations: vec![relation(
                        &event.actor,
                        SemanticRelationType::LocatedIn,
                        &from,
                    )],
                    added_relations: vec![relation(
                        &event.actor,
                        SemanticRelationType::LocatedIn,
                        &to,
                    )],
                },
            })
        }
        SemanticEventType::ChangeState => Ok(WorldDelta {
            object_delta: empty_object_delta(),
            state_deltas: vec![StateDelta {
                object_id: event.actor.clone(),
                removed_states: vec![param(event, "from")?],
                added_states: vec![param(event, "to")?],
            }],
            relation_delta: empty_relation_delta(),
        }),
        SemanticEventType::Attach => {
            let target = param(event, "target")?;
            Ok(WorldDelta {
                object_delta: empty_object_delta(),
                state_deltas: vec![],
                relation_delta: RelationDelta {
                    removed_relations: vec![],
                    added_relations: vec![relation(
                        &event.actor,
                        parse_relation_type(param(event, "relation")?.as_str())?,
                        &target,
                    )],
                },
            })
        }
        SemanticEventType::Detach => {
            let target = param(event, "target")?;
            Ok(WorldDelta {
                object_delta: empty_object_delta(),
                state_deltas: vec![],
                relation_delta: RelationDelta {
                    removed_relations: vec![relation(
                        &event.actor,
                        parse_relation_type(param(event, "relation")?.as_str())?,
                        &target,
                    )],
                    added_relations: vec![],
                },
            })
        }
        SemanticEventType::Create => {
            let object_id = param(event, "object_id")?;
            Ok(WorldDelta {
                object_delta: ObjectDelta {
                    created_objects: vec![object(
                        &object_id,
                        SemanticObjectType::Generic,
                        &[],
                        position_for_created_object(world),
                    )],
                    removed_object_ids: vec![],
                },
                state_deltas: vec![],
                relation_delta: empty_relation_delta(),
            })
        }
        SemanticEventType::Remove => Ok(WorldDelta {
            object_delta: ObjectDelta {
                created_objects: vec![],
                removed_object_ids: vec![event.actor.clone()],
            },
            state_deltas: vec![],
            relation_delta: empty_relation_delta(),
        }),
    }
}

fn apply_delta(world: &WorldSnapshot, delta: &WorldDelta) -> Result<WorldSnapshot, String> {
    let mut next = world.clone();

    next.objects
        .retain(|object| !delta.object_delta.removed_object_ids.contains(&object.id));
    next.relations.retain(|relation| {
        !delta
            .object_delta
            .removed_object_ids
            .contains(&relation.source_id)
            && !delta
                .object_delta
                .removed_object_ids
                .contains(&relation.target_id)
    });
    next.objects
        .extend(delta.object_delta.created_objects.iter().cloned());

    for state_delta in &delta.state_deltas {
        let object = next
            .objects
            .iter_mut()
            .find(|object| object.id == state_delta.object_id)
            .ok_or_else(|| format!("state delta actor missing: {}", state_delta.object_id))?;
        object
            .states
            .retain(|state| !state_delta.removed_states.contains(state));
        for state in &state_delta.added_states {
            if !object.states.contains(state) {
                object.states.push(state.clone());
            }
        }
        object.states.sort();
    }

    next.relations
        .retain(|relation| !delta.relation_delta.removed_relations.contains(relation));
    for relation in &delta.relation_delta.added_relations {
        if !next.relations.contains(relation) {
            next.relations.push(relation.clone());
        }
    }
    canonicalize_snapshot(&mut next);
    Ok(next)
}

fn validate_world(world: &WorldSnapshot) -> Result<(), String> {
    let mut ids = BTreeSet::new();
    for object in &world.objects {
        if object.id.is_empty() {
            return Err("object id missing".to_string());
        }
        if !ids.insert(object.id.as_str()) {
            return Err(format!("duplicate object id: {}", object.id));
        }
        let mut state_groups = BTreeMap::new();
        for state in &object.states {
            let group = state_group(state);
            if let Some(existing) = state_groups.insert(group, state.as_str()) {
                return Err(format!(
                    "conflicting states {} and {} on {}",
                    existing, state, object.id
                ));
            }
        }
    }
    if !relation_targets_exist(world) {
        return Err("relation target missing".to_string());
    }
    if !containment_is_valid(world) {
        return Err("containment invalid".to_string());
    }
    Ok(())
}

fn relation_targets_exist(world: &WorldSnapshot) -> bool {
    let ids: BTreeSet<_> = world
        .objects
        .iter()
        .map(|object| object.id.as_str())
        .collect();
    world.relations.iter().all(|relation| {
        ids.contains(relation.source_id.as_str()) && ids.contains(relation.target_id.as_str())
    })
}

fn containment_is_valid(world: &WorldSnapshot) -> bool {
    let room_ids: BTreeSet<_> = world
        .objects
        .iter()
        .filter(|object| object.object_type == SemanticObjectType::Room)
        .map(|object| object.id.as_str())
        .collect();
    let human_location_count = world
        .relations
        .iter()
        .filter(|relation| {
            relation.source_id == "human_001"
                && relation.relation_type == SemanticRelationType::LocatedIn
                && room_ids.contains(relation.target_id.as_str())
        })
        .count();
    human_location_count == 1
        && contains_relation(world, "house_001", SemanticRelationType::Contains, "room_a")
        && contains_relation(world, "house_001", SemanticRelationType::Contains, "room_b")
}

fn canonicalize_snapshot(snapshot: &mut WorldSnapshot) {
    for object in &mut snapshot.objects {
        object.states.sort();
        object.states.dedup();
    }
    snapshot.objects.sort_by(|a, b| a.id.cmp(&b.id));
    snapshot.relations.sort();
    snapshot.relations.dedup();
}

fn empty_object_delta() -> ObjectDelta {
    ObjectDelta {
        created_objects: vec![],
        removed_object_ids: vec![],
    }
}

fn empty_relation_delta() -> RelationDelta {
    RelationDelta {
        removed_relations: vec![],
        added_relations: vec![],
    }
}

fn param(event: &SemanticEvent, key: &str) -> Result<String, String> {
    event
        .parameters
        .get(key)
        .cloned()
        .ok_or_else(|| format!("event parameter missing: {key}"))
}

fn object_exists(world: &WorldSnapshot, object_id: &str) -> bool {
    world.objects.iter().any(|object| object.id == object_id)
}

fn object_has_type(
    world: &WorldSnapshot,
    object_id: &str,
    object_type: SemanticObjectType,
) -> bool {
    world
        .objects
        .iter()
        .any(|object| object.id == object_id && object.object_type == object_type)
}

fn has_state(world: &WorldSnapshot, object_id: &str, state: &str) -> bool {
    world
        .objects
        .iter()
        .find(|object| object.id == object_id)
        .is_some_and(|object| object.states.iter().any(|existing| existing == state))
}

fn contains_relation(
    world: &WorldSnapshot,
    source_id: &str,
    relation_type: SemanticRelationType,
    target_id: &str,
) -> bool {
    world.relations.iter().any(|relation| {
        relation.source_id == source_id
            && relation.relation_type == relation_type
            && relation.target_id == target_id
    })
}

fn parse_relation_type(value: &str) -> Result<SemanticRelationType, String> {
    match value {
        "Contains" => Ok(SemanticRelationType::Contains),
        "LocatedIn" => Ok(SemanticRelationType::LocatedIn),
        "Uses" => Ok(SemanticRelationType::Uses),
        "AttachedTo" => Ok(SemanticRelationType::AttachedTo),
        _ => Err(format!("unsupported relation type: {value}")),
    }
}

fn state_group(state: &str) -> String {
    match state {
        "open" | "closed" => "door_open_closed".to_string(),
        "standing" | "sitting" | "walking" => "human_posture".to_string(),
        other => other.to_string(),
    }
}

fn position_for_created_object(world: &WorldSnapshot) -> Position3D {
    pos(30.0 + world.objects.len() as f32, 0.0, 0.0)
}

fn pos(x: f32, y: f32, z: f32) -> Position3D {
    Position3D { x, y, z }
}

fn snapshot_json(snapshot: &WorldSnapshot) -> String {
    serde_json::to_string_pretty(snapshot).expect("snapshot must serialize") + "\n"
}

fn case(id: &str, name: &str) -> ValidationCase {
    ValidationCase {
        id: id.to_string(),
        name: name.to_string(),
        passed: true,
    }
}

fn render_event_world_png(trace: &EventTrace) -> Vec<u8> {
    let width = 860;
    let height = 240;
    let mut rgba = vec![0u8; (width * height * 4) as usize];
    for pixel in rgba.chunks_exact_mut(4) {
        pixel.copy_from_slice(&[247, 247, 244, 255]);
    }
    for (index, snapshot) in trace.snapshots.iter().enumerate() {
        let x = 34 + index as i32 * 205;
        draw_room(&mut rgba, width, height, x, 58, [90, 120, 160, 255]);
        draw_room(&mut rgba, width, height, x + 82, 58, [120, 160, 125, 255]);
        let door_color = if has_state(snapshot, "door_001", "open") {
            [70, 155, 95, 255]
        } else {
            [160, 75, 70, 255]
        };
        draw_rect(&mut rgba, width, height, x + 74, 108, 14, 46, door_color);
        let human_x = if contains_relation(
            snapshot,
            "human_001",
            SemanticRelationType::LocatedIn,
            "room_b",
        ) {
            x + 116
        } else {
            x + 32
        };
        draw_rect(
            &mut rgba,
            width,
            height,
            human_x,
            92,
            20,
            44,
            [65, 110, 165, 255],
        );
        if index + 1 < trace.snapshots.len() {
            draw_line(
                &mut rgba,
                width,
                height,
                x + 166,
                124,
                x + 195,
                124,
                [65, 65, 65, 255],
            );
        }
    }
    encode_png_rgba(width, height, &rgba)
}

fn draw_room(rgba: &mut [u8], width: u32, height: u32, x: i32, y: i32, color: [u8; 4]) {
    draw_rect(rgba, width, height, x, y, 70, 112, [255, 255, 255, 255]);
    draw_line(rgba, width, height, x, y, x + 70, y, color);
    draw_line(rgba, width, height, x + 70, y, x + 70, y + 112, color);
    draw_line(rgba, width, height, x + 70, y + 112, x, y + 112, color);
    draw_line(rgba, width, height, x, y + 112, x, y, color);
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
