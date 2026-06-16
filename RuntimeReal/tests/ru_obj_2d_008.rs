use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{
    GraphType, RelationType, StateType, TransitionType, UnitType,
};
use reasonscript_runtime_real::core::{ReasonUnit, State, Transition};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph};
use ndarray::array;
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;
use uuid::Uuid;

const NEAR_THRESHOLD: f32 = 150.0;

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum SceneType {
    DiningRoom,
    Bedroom,
    Office,
    LivingRoom,
}

impl SceneType {
    fn as_str(&self) -> &'static str {
        match self {
            Self::DiningRoom => "DiningRoom",
            Self::Bedroom => "Bedroom",
            Self::Office => "Office",
            Self::LivingRoom => "LivingRoom",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum ObjectType {
    Table,
    Chair,
    Lamp,
    Bed,
    Desk,
}

impl ObjectType {
    fn as_str(&self) -> &'static str {
        match self {
            Self::Table => "Table",
            Self::Chair => "Chair",
            Self::Lamp => "Lamp",
            Self::Bed => "Bed",
            Self::Desk => "Desk",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct SemanticScene {
    scene_type: SceneType,
    objects: Vec<ObjectType>,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum SpatialRelationType {
    Near,
    Above,
}

impl SpatialRelationType {
    fn as_str(&self) -> &'static str {
        match self {
            Self::Near => "near",
            Self::Above => "above",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
struct SpatialRelation {
    source: String,
    relation: SpatialRelationType,
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
fn ru_obj_2d_008_reconstructs_scene_from_semantic_knowledge() {
    let dining = SemanticScene {
        scene_type: SceneType::DiningRoom,
        objects: vec![ObjectType::Table, ObjectType::Chair, ObjectType::Lamp],
    };
    let bedroom = SemanticScene {
        scene_type: SceneType::Bedroom,
        objects: vec![ObjectType::Bed, ObjectType::Lamp],
    };
    let office = SemanticScene {
        scene_type: SceneType::Office,
        objects: vec![ObjectType::Desk, ObjectType::Chair],
    };

    let dining_graph = build_semantic_graph(&dining);
    let dining_scene = extract_semantic_scene(&dining_graph).expect("DiningRoom scene must extract");
    let dining_relations = infer_spatial_graph(&dining_scene).expect("DiningRoom must infer");
    let dining_layout = reconstruct_layout(&dining_scene, &dining_relations).expect("DiningRoom must layout");
    let dining_report = validate_reconstruction(&dining_scene, &dining_relations, &dining_layout);
    assert!(dining_report.passed);
    assert_eq!(
        dining_relations,
        vec![
            SpatialRelation {
                source: "Chair".to_string(),
                relation: SpatialRelationType::Near,
                target: "Table".to_string(),
            },
            SpatialRelation {
                source: "Lamp".to_string(),
                relation: SpatialRelationType::Above,
                target: "Table".to_string(),
            },
        ]
    );
    assert_eq!(position(&dining_layout, "Table"), (300.0, 500.0));
    assert_eq!(position(&dining_layout, "Chair"), (390.0, 500.0));
    assert_eq!(position(&dining_layout, "Lamp"), (300.0, 430.0));

    let bedroom_scene = extract_semantic_scene(&build_semantic_graph(&bedroom))
        .expect("Bedroom scene must extract");
    let bedroom_relations = infer_spatial_graph(&bedroom_scene).expect("Bedroom must infer");
    assert_eq!(
        bedroom_relations,
        vec![
            SpatialRelation {
                source: "Lamp".to_string(),
                relation: SpatialRelationType::Near,
                target: "Bed".to_string(),
            },
            SpatialRelation {
                source: "Lamp".to_string(),
                relation: SpatialRelationType::Above,
                target: "Bed".to_string(),
            },
        ]
    );
    let bedroom_layout = reconstruct_layout(&bedroom_scene, &bedroom_relations)
        .expect("Bedroom must layout");
    assert!(validate_reconstruction(&bedroom_scene, &bedroom_relations, &bedroom_layout).passed);

    let office_scene = extract_semantic_scene(&build_semantic_graph(&office))
        .expect("Office scene must extract");
    let office_relations = infer_spatial_graph(&office_scene).expect("Office must infer");
    assert_eq!(
        office_relations,
        vec![SpatialRelation {
            source: "Chair".to_string(),
            relation: SpatialRelationType::Near,
            target: "Desk".to_string(),
        }]
    );
    let office_layout = reconstruct_layout(&office_scene, &office_relations).expect("Office must layout");
    assert!(validate_reconstruction(&office_scene, &office_relations, &office_layout).passed);

    let missing_required = SemanticScene {
        scene_type: SceneType::DiningRoom,
        objects: vec![ObjectType::Chair, ObjectType::Lamp],
    };
    assert!(infer_spatial_graph(&missing_required).is_err());

    let invalid_template = SemanticScene {
        scene_type: SceneType::LivingRoom,
        objects: vec![ObjectType::Chair, ObjectType::Lamp],
    };
    assert!(infer_spatial_graph(&invalid_template).is_err());

    assert!(spatial_graph_has_no_cycles(&dining_relations));

    let graph_json = inferred_spatial_graph_json(&dining_relations);
    let dining_layout_json = layout_json(&dining_layout);
    for _ in 0..100 {
        let next_relations = infer_spatial_graph(&dining_scene).expect("graph must reproduce");
        let next_layout = reconstruct_layout(&dining_scene, &next_relations)
            .expect("layout must reproduce");
        assert_eq!(dining_relations, next_relations);
        assert_eq!(graph_json, inferred_spatial_graph_json(&next_relations));
        assert_eq!(dining_layout, next_layout);
        assert_eq!(dining_layout_json, layout_json(&next_layout));
    }

    let artifact_dir = Path::new("artifacts/ru_obj_2d_008");
    fs::create_dir_all(artifact_dir).expect("artifact directory must be created");
    fs::write(
        artifact_dir.join("semantic_scene.json"),
        semantic_scene_json(&dining_scene),
    )
    .expect("semantic_scene.json must be generated");
    fs::write(
        artifact_dir.join("inferred_spatial_graph.json"),
        graph_json,
    )
    .expect("inferred_spatial_graph.json must be generated");
    fs::write(artifact_dir.join("layout.json"), dining_layout_json)
        .expect("layout.json must be generated");
    fs::write(
        artifact_dir.join("validation_report.json"),
        validation_report_json(&dining_report),
    )
    .expect("validation_report.json must be generated");
    fs::write(
        artifact_dir.join("semantic_scene.png"),
        render_scene_png(&dining_layout),
    )
    .expect("semantic_scene.png must be generated");

    for path in [
        "artifacts/ru_obj_2d_008/semantic_scene.json",
        "artifacts/ru_obj_2d_008/inferred_spatial_graph.json",
        "artifacts/ru_obj_2d_008/layout.json",
        "artifacts/ru_obj_2d_008/validation_report.json",
        "artifacts/ru_obj_2d_008/semantic_scene.png",
    ] {
        let bytes = fs::read(path).expect("artifact must be readable");
        assert!(bytes.len() > 20, "{path} must not be empty");
    }
}

fn build_semantic_graph(scene: &SemanticScene) -> ReasonGraph {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);
    let scene_id = add_node(&mut graph, scene.scene_type.as_str(), StateType::Object);

    for object in &scene.objects {
        let object_id = add_node(&mut graph, object.as_str(), StateType::Object);
        add_relation(&mut graph, scene_id, object_id, "contains");
        for affordance in affordances(object) {
            let affordance_id = add_node(&mut graph, affordance, StateType::Attribute);
            add_relation(&mut graph, object_id, affordance_id, "affords");
        }
    }

    graph
}

fn add_node(graph: &mut ReasonGraph, label: &str, state_type: StateType) -> Uuid {
    let state = State::new(
        state_type,
        ReasonUnit::new(label, UnitType::Composite, array![0.0]),
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

fn affordances(object: &ObjectType) -> Vec<&'static str> {
    match object {
        ObjectType::Table => vec!["supports_eating", "supports_work"],
        ObjectType::Chair => vec!["supports_sitting"],
        ObjectType::Lamp => vec!["supports_illumination"],
        ObjectType::Bed => vec!["supports_sleeping"],
        ObjectType::Desk => vec!["supports_work"],
    }
}

fn extract_semantic_scene(graph: &ReasonGraph) -> Result<SemanticScene, String> {
    let scene_node = graph
        .nodes
        .keys()
        .find_map(|id| {
            let label = object_name(graph, *id).ok()?;
            parse_scene_type(&label).map(|scene_type| (*id, scene_type))
        })
        .ok_or_else(|| "scene type is missing".to_string())?;

    let mut objects = graph
        .edges
        .iter()
        .filter(|edge| edge.source == scene_node.0 && relation_label(edge) == "contains")
        .map(|edge| object_name(graph, edge.target).and_then(|name| parse_object_type(&name)))
        .collect::<Result<Vec<_>, String>>()?;
    objects.sort();

    Ok(SemanticScene {
        scene_type: scene_node.1,
        objects,
    })
}

fn infer_spatial_graph(scene: &SemanticScene) -> Result<Vec<SpatialRelation>, String> {
    validate_required_objects(scene)?;
    let names = scene
        .objects
        .iter()
        .map(ObjectType::as_str)
        .collect::<BTreeSet<_>>();
    let mut relations = Vec::new();

    match scene.scene_type {
        SceneType::DiningRoom => {
            if names.contains("Chair") {
                relations.push(SpatialRelation {
                    source: "Chair".to_string(),
                    relation: SpatialRelationType::Near,
                    target: "Table".to_string(),
                });
            }
            if names.contains("Lamp") {
                relations.push(SpatialRelation {
                    source: "Lamp".to_string(),
                    relation: SpatialRelationType::Above,
                    target: "Table".to_string(),
                });
            }
        }
        SceneType::Bedroom => {
            if names.contains("Lamp") {
                relations.push(SpatialRelation {
                    source: "Lamp".to_string(),
                    relation: SpatialRelationType::Near,
                    target: "Bed".to_string(),
                });
                relations.push(SpatialRelation {
                    source: "Lamp".to_string(),
                    relation: SpatialRelationType::Above,
                    target: "Bed".to_string(),
                });
            }
        }
        SceneType::Office => {
            relations.push(SpatialRelation {
                source: "Chair".to_string(),
                relation: SpatialRelationType::Near,
                target: "Desk".to_string(),
            });
        }
        SceneType::LivingRoom => return Err("invalid scene template: LivingRoom".to_string()),
    }

    relations.sort();
    if !spatial_graph_has_no_cycles(&relations) {
        return Err("inferred spatial graph contains an ambiguous cycle".to_string());
    }
    Ok(relations)
}

fn validate_required_objects(scene: &SemanticScene) -> Result<(), String> {
    let names = scene
        .objects
        .iter()
        .map(ObjectType::as_str)
        .collect::<BTreeSet<_>>();
    match scene.scene_type {
        SceneType::DiningRoom if !names.contains("Table") => {
            Err("DiningRoom requires Table".to_string())
        }
        SceneType::Bedroom if !names.contains("Bed") => Err("Bedroom requires Bed".to_string()),
        SceneType::Office if !names.contains("Desk") || !names.contains("Chair") => {
            Err("Office requires Desk and Chair".to_string())
        }
        SceneType::LivingRoom => Err("invalid scene template: LivingRoom".to_string()),
        _ => Ok(()),
    }
}

fn reconstruct_layout(
    scene: &SemanticScene,
    relations: &[SpatialRelation],
) -> Result<BTreeMap<String, Bounds>, String> {
    let mut layout = BTreeMap::new();
    for object in &scene.objects {
        layout.insert(object.as_str().to_string(), default_bounds(object));
    }

    let anchor = match scene.scene_type {
        SceneType::DiningRoom => "Table",
        SceneType::Bedroom => "Bed",
        SceneType::Office => "Desk",
        SceneType::LivingRoom => return Err("invalid scene template: LivingRoom".to_string()),
    };
    layout
        .get_mut(anchor)
        .ok_or_else(|| format!("{anchor} is missing"))?
        .x = 300.0;
    layout
        .get_mut(anchor)
        .ok_or_else(|| format!("{anchor} is missing"))?
        .y = 500.0;

    for relation in relations {
        let target = *layout
            .get(&relation.target)
            .ok_or_else(|| format!("target {} is missing", relation.target))?;
        let source = layout
            .get_mut(&relation.source)
            .ok_or_else(|| format!("source {} is missing", relation.source))?;
        match relation.relation {
            SpatialRelationType::Near => {
                source.x = target.x + 90.0;
                source.y = target.y;
            }
            SpatialRelationType::Above => {
                source.x = target.x;
                source.y = target.y - 70.0;
            }
        }
    }

    Ok(layout)
}

fn default_bounds(object: &ObjectType) -> Bounds {
    match object {
        ObjectType::Table => Bounds {
            x: 0.0,
            y: 0.0,
            width: 80.0,
            height: 60.0,
        },
        ObjectType::Chair => Bounds {
            x: 0.0,
            y: 0.0,
            width: 50.0,
            height: 50.0,
        },
        ObjectType::Lamp => Bounds {
            x: 0.0,
            y: 0.0,
            width: 40.0,
            height: 40.0,
        },
        ObjectType::Bed => Bounds {
            x: 0.0,
            y: 0.0,
            width: 100.0,
            height: 70.0,
        },
        ObjectType::Desk => Bounds {
            x: 0.0,
            y: 0.0,
            width: 90.0,
            height: 60.0,
        },
    }
}

fn validate_reconstruction(
    scene: &SemanticScene,
    relations: &[SpatialRelation],
    layout: &BTreeMap<String, Bounds>,
) -> ValidationReport {
    let mut checks = Vec::new();
    let mut violations = Vec::new();

    if let Err(error) = validate_required_objects(scene) {
        violations.push(error);
    } else {
        checks.push("required objects exist".to_string());
    }

    for object in &scene.objects {
        let name = object.as_str();
        match layout.get(name) {
            Some(bounds) if contained_in_scene(bounds) => checks.push(format!("{name} inside scene")),
            Some(_) => violations.push(format!("{name} outside scene")),
            None => violations.push(format!("{name} has no layout")),
        }
    }

    for relation in relations {
        let Some(source) = layout.get(&relation.source) else {
            violations.push(format!("{} has no layout", relation.source));
            continue;
        };
        let Some(target) = layout.get(&relation.target) else {
            violations.push(format!("{} has no layout", relation.target));
            continue;
        };
        match relation.relation {
            SpatialRelationType::Near if distance(source, target) <= NEAR_THRESHOLD => {
                checks.push(format!("{} near {}", relation.source, relation.target));
            }
            SpatialRelationType::Above if source.y < target.y => {
                checks.push(format!("{} above {}", relation.source, relation.target));
            }
            _ => violations.push(format!(
                "{} {} {}",
                relation.source,
                relation.relation.as_str(),
                relation.target
            )),
        }
    }

    ValidationReport {
        passed: violations.is_empty(),
        checks,
        violations,
    }
}

fn spatial_graph_has_no_cycles(relations: &[SpatialRelation]) -> bool {
    let mut graph: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for relation in relations {
        graph
            .entry(relation.source.clone())
            .or_default()
            .insert(relation.target.clone());
        graph.entry(relation.target.clone()).or_default();
    }
    cycles_in_graph(&graph).is_empty()
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
                cycles.insert(path.clone());
            } else if !path.contains(next) {
                collect_cycles(start, next, graph, path, cycles);
            }
        }
    }
    path.pop();
}

fn contained_in_scene(bounds: &Bounds) -> bool {
    bounds.x >= 100.0 && bounds.x <= 700.0 && bounds.y >= 100.0 && bounds.y <= 700.0
}

fn distance(a: &Bounds, b: &Bounds) -> f32 {
    ((a.x - b.x).powi(2) + (a.y - b.y).powi(2)).sqrt()
}

fn position(layout: &BTreeMap<String, Bounds>, name: &str) -> (f32, f32) {
    let bounds = layout.get(name).expect("object must exist");
    (bounds.x, bounds.y)
}

fn parse_scene_type(label: &str) -> Option<SceneType> {
    match label {
        "DiningRoom" => Some(SceneType::DiningRoom),
        "Bedroom" => Some(SceneType::Bedroom),
        "Office" => Some(SceneType::Office),
        "LivingRoom" => Some(SceneType::LivingRoom),
        _ => None,
    }
}

fn parse_object_type(label: &str) -> Result<ObjectType, String> {
    match label {
        "Table" => Ok(ObjectType::Table),
        "Chair" => Ok(ObjectType::Chair),
        "Lamp" => Ok(ObjectType::Lamp),
        "Bed" => Ok(ObjectType::Bed),
        "Desk" => Ok(ObjectType::Desk),
        other => Err(format!("unsupported object type: {other}")),
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

fn semantic_scene_json(scene: &SemanticScene) -> String {
    let objects = scene
        .objects
        .iter()
        .map(|object| object.as_str().to_string())
        .collect::<Vec<_>>();
    format!(
        "{{\n  \"scene_type\": \"{}\",\n  \"objects\": {}\n}}\n",
        scene.scene_type.as_str(),
        json_string_array(&objects)
    )
}

fn inferred_spatial_graph_json(relations: &[SpatialRelation]) -> String {
    let relations = relations
        .iter()
        .map(|relation| {
            format!(
                "    {{ \"source\": \"{}\", \"relation\": \"{}\", \"target\": \"{}\" }}",
                relation.source,
                relation.relation.as_str(),
                relation.target
            )
        })
        .collect::<Vec<_>>()
        .join(",\n");
    format!("{{\n  \"relations\": [\n{}\n  ]\n}}\n", relations)
}

fn layout_json(layout: &BTreeMap<String, Bounds>) -> String {
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

fn render_scene_png(layout: &BTreeMap<String, Bounds>) -> Vec<u8> {
    let canvas_width = 800;
    let canvas_height = 800;
    let mut rgba = vec![255; (canvas_width * canvas_height * 4) as usize];
    for bounds in layout.values() {
        draw_rectangle(&mut rgba, canvas_width, *bounds);
    }
    encode_png_rgba(canvas_width, canvas_height, &rgba)
}

fn draw_rectangle(rgba: &mut [u8], canvas_width: u32, bounds: Bounds) {
    let left = (bounds.x - bounds.width / 2.0) as u32;
    let right = (bounds.x + bounds.width / 2.0) as u32;
    let top = (bounds.y - bounds.height / 2.0) as u32;
    let bottom = (bounds.y + bounds.height / 2.0) as u32;

    for y in top..=bottom {
        for x in left..=right {
            if x == left || x == right || y == top || y == bottom {
                set_black_pixel(rgba, canvas_width, x, y);
            }
        }
    }
}

fn set_black_pixel(rgba: &mut [u8], canvas_width: u32, x: u32, y: u32) {
    if x >= canvas_width || y >= 800 {
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
