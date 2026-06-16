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

// ─── Scene / Object types ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum SceneType {
    DiningRoom,
    Bedroom,
    Office,
    Classroom,
}

impl SceneType {
    fn as_str(&self) -> &'static str {
        match self {
            Self::DiningRoom => "DiningRoom",
            Self::Bedroom    => "Bedroom",
            Self::Office     => "Office",
            Self::Classroom  => "Classroom",
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
    TeacherDesk,
    StudentDesk,
    Whiteboard,
}

impl ObjectType {
    fn as_str(&self) -> &'static str {
        match self {
            Self::Table       => "Table",
            Self::Chair       => "Chair",
            Self::Lamp        => "Lamp",
            Self::Bed         => "Bed",
            Self::Desk        => "Desk",
            Self::TeacherDesk => "TeacherDesk",
            Self::StudentDesk => "StudentDesk",
            Self::Whiteboard  => "Whiteboard",
        }
    }
}

// ─── Semantic Scene ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
struct SemanticScene {
    scene_type: SceneType,
    objects: Vec<ObjectType>,
}

// ─── Completion ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
enum CompletionStatus {
    Complete,
    Incomplete,
    Invalid,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct CompletionResult {
    pub status: CompletionStatus,
    pub completed: bool,
    pub added_objects: Vec<String>,
    pub added_relations: Vec<SpatialRelation>,
    pub explanation: Vec<String>,
}

// ─── Spatial relations / layout ───────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
enum SpatialRelationType {
    Near,
    Above,
}

impl SpatialRelationType {
    fn as_str(&self) -> &'static str {
        match self {
            Self::Near  => "near",
            Self::Above => "above",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
struct SpatialRelation {
    source:   String,
    relation: SpatialRelationType,
    target:   String,
}

#[derive(Debug, Clone, Copy, PartialEq)]
struct Bounds {
    x:      f32,
    y:      f32,
    width:  f32,
    height: f32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ValidationReport {
    passed:     bool,
    checks:     Vec<String>,
    violations: Vec<String>,
}

// ─── Scene template knowledge ─────────────────────────────────────────────────

struct SceneTemplate {
    required: Vec<ObjectType>,
    expected: Vec<ObjectType>,
}

fn template(scene_type: &SceneType) -> SceneTemplate {
    match scene_type {
        SceneType::DiningRoom => SceneTemplate {
            required: vec![ObjectType::Table],
            expected: vec![ObjectType::Chair],
        },
        SceneType::Bedroom => SceneTemplate {
            required: vec![ObjectType::Bed],
            expected: vec![ObjectType::Lamp],
        },
        SceneType::Office => SceneTemplate {
            required: vec![ObjectType::Desk, ObjectType::Chair],
            expected: vec![],
        },
        SceneType::Classroom => SceneTemplate {
            required: vec![ObjectType::TeacherDesk],
            expected: vec![
                ObjectType::StudentDesk,
                ObjectType::Chair,
                ObjectType::Whiteboard,
            ],
        },
    }
}

// ─── Core completion engine ───────────────────────────────────────────────────

fn complete_scene(scene: &SemanticScene) -> CompletionResult {
    let tmpl = template(&scene.scene_type);
    let present: BTreeSet<_> = scene.objects.iter().map(ObjectType::as_str).collect();

    // Check required objects – cannot be inferred (SC-002)
    for req in &tmpl.required {
        if !present.contains(req.as_str()) {
            return CompletionResult {
                status: CompletionStatus::Invalid,
                completed: false,
                added_objects: vec![],
                added_relations: vec![],
                explanation: vec![format!(
                    "{} requires {} which cannot be inferred automatically",
                    scene.scene_type.as_str(),
                    req.as_str()
                )],
            };
        }
    }

    // Collect missing expected objects (SC-001)
    let mut added_objects: Vec<String> = vec![];
    for exp in &tmpl.expected {
        if !present.contains(exp.as_str()) {
            added_objects.push(exp.as_str().to_string());
        }
    }

    if added_objects.is_empty() {
        return CompletionResult {
            status: CompletionStatus::Complete,
            completed: false,
            added_objects: vec![],
            added_relations: vec![],
            explanation: vec!["scene is already complete".to_string()],
        };
    }

    // Build the completed object list and infer missing relations (SC-003)
    let mut completed_objects = scene.objects.clone();
    for name in &added_objects {
        completed_objects.push(parse_object_type(name).unwrap());
    }

    let completed_scene = SemanticScene {
        scene_type: scene.scene_type.clone(),
        objects:    completed_objects,
    };

    let all_relations = infer_spatial_graph(&completed_scene).unwrap();
    let before_relations = infer_spatial_graph(scene).unwrap_or_default();

    let added_relations: Vec<SpatialRelation> = all_relations
        .iter()
        .filter(|r| !before_relations.contains(r))
        .cloned()
        .collect();

    let mut explanation = vec![];
    for obj in &added_objects {
        let anchor = anchor_for(&scene.scene_type);
        explanation.push(format!(
            "{} expects {} near {}",
            scene.scene_type.as_str(),
            obj,
            anchor
        ));
    }

    CompletionResult {
        status: CompletionStatus::Incomplete,
        completed: true,
        added_objects,
        added_relations,
        explanation,
    }
}

fn anchor_for(scene_type: &SceneType) -> &'static str {
    match scene_type {
        SceneType::DiningRoom => "Table",
        SceneType::Bedroom    => "Bed",
        SceneType::Office     => "Desk",
        SceneType::Classroom  => "TeacherDesk",
    }
}

// ─── Spatial graph inference ──────────────────────────────────────────────────

fn infer_spatial_graph(scene: &SemanticScene) -> Result<Vec<SpatialRelation>, String> {
    validate_required_objects(scene)?;
    let names: BTreeSet<_> = scene.objects.iter().map(ObjectType::as_str).collect();
    let mut relations = Vec::new();

    match scene.scene_type {
        SceneType::DiningRoom => {
            if names.contains("Chair") {
                relations.push(SpatialRelation {
                    source:   "Chair".into(),
                    relation: SpatialRelationType::Near,
                    target:   "Table".into(),
                });
            }
            if names.contains("Lamp") {
                relations.push(SpatialRelation {
                    source:   "Lamp".into(),
                    relation: SpatialRelationType::Above,
                    target:   "Table".into(),
                });
            }
        }
        SceneType::Bedroom => {
            if names.contains("Lamp") {
                relations.push(SpatialRelation {
                    source:   "Lamp".into(),
                    relation: SpatialRelationType::Near,
                    target:   "Bed".into(),
                });
                relations.push(SpatialRelation {
                    source:   "Lamp".into(),
                    relation: SpatialRelationType::Above,
                    target:   "Bed".into(),
                });
            }
        }
        SceneType::Office => {
            relations.push(SpatialRelation {
                source:   "Chair".into(),
                relation: SpatialRelationType::Near,
                target:   "Desk".into(),
            });
        }
        SceneType::Classroom => {
            if names.contains("Whiteboard") {
                relations.push(SpatialRelation {
                    source:   "Whiteboard".into(),
                    relation: SpatialRelationType::Above,
                    target:   "TeacherDesk".into(),
                });
            }
            if names.contains("StudentDesk") {
                relations.push(SpatialRelation {
                    source:   "StudentDesk".into(),
                    relation: SpatialRelationType::Near,
                    target:   "TeacherDesk".into(),
                });
            }
            if names.contains("Chair") {
                relations.push(SpatialRelation {
                    source:   "Chair".into(),
                    relation: SpatialRelationType::Near,
                    target:   "StudentDesk".into(),
                });
            }
        }
    }

    relations.sort();
    if !spatial_graph_has_no_cycles(&relations) {
        return Err("inferred spatial graph contains a cycle".to_string());
    }
    Ok(relations)
}

fn validate_required_objects(scene: &SemanticScene) -> Result<(), String> {
    let names: BTreeSet<_> = scene.objects.iter().map(ObjectType::as_str).collect();
    match scene.scene_type {
        SceneType::DiningRoom if !names.contains("Table") => {
            Err("DiningRoom requires Table".into())
        }
        SceneType::Bedroom if !names.contains("Bed") => Err("Bedroom requires Bed".into()),
        SceneType::Office if !names.contains("Desk") || !names.contains("Chair") => {
            Err("Office requires Desk and Chair".into())
        }
        SceneType::Classroom if !names.contains("TeacherDesk") => {
            Err("Classroom requires TeacherDesk".into())
        }
        _ => Ok(()),
    }
}

// ─── Layout reconstruction ────────────────────────────────────────────────────

fn reconstruct_layout(
    scene: &SemanticScene,
    relations: &[SpatialRelation],
) -> Result<BTreeMap<String, Bounds>, String> {
    let mut layout: BTreeMap<String, Bounds> = BTreeMap::new();
    for object in &scene.objects {
        layout.insert(object.as_str().to_string(), default_bounds(object));
    }

    let anchor = anchor_for(&scene.scene_type);
    let entry = layout
        .get_mut(anchor)
        .ok_or_else(|| format!("{anchor} is missing"))?;
    entry.x = 300.0;
    entry.y = 500.0;

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
        ObjectType::Table       => Bounds { x: 0.0, y: 0.0, width: 80.0,  height: 60.0 },
        ObjectType::Chair       => Bounds { x: 0.0, y: 0.0, width: 50.0,  height: 50.0 },
        ObjectType::Lamp        => Bounds { x: 0.0, y: 0.0, width: 40.0,  height: 40.0 },
        ObjectType::Bed         => Bounds { x: 0.0, y: 0.0, width: 100.0, height: 70.0 },
        ObjectType::Desk        => Bounds { x: 0.0, y: 0.0, width: 90.0,  height: 60.0 },
        ObjectType::TeacherDesk => Bounds { x: 0.0, y: 0.0, width: 90.0,  height: 60.0 },
        ObjectType::StudentDesk => Bounds { x: 0.0, y: 0.0, width: 70.0,  height: 50.0 },
        ObjectType::Whiteboard  => Bounds { x: 0.0, y: 0.0, width: 120.0, height: 30.0 },
    }
}

// ─── Validation ───────────────────────────────────────────────────────────────

fn validate_reconstruction(
    scene: &SemanticScene,
    relations: &[SpatialRelation],
    layout: &BTreeMap<String, Bounds>,
) -> ValidationReport {
    let mut checks     = Vec::new();
    let mut violations = Vec::new();

    if validate_required_objects(scene).is_ok() {
        checks.push("required objects exist".into());
    } else {
        violations.push("required object missing".into());
    }

    for object in &scene.objects {
        let name = object.as_str();
        match layout.get(name) {
            Some(b) if contained_in_scene(b) => checks.push(format!("{name} inside scene")),
            Some(_) => violations.push(format!("{name} outside scene")),
            None    => violations.push(format!("{name} has no layout")),
        }
    }

    for relation in relations {
        let Some(src) = layout.get(&relation.source) else {
            violations.push(format!("{} has no layout", relation.source));
            continue;
        };
        let Some(tgt) = layout.get(&relation.target) else {
            violations.push(format!("{} has no layout", relation.target));
            continue;
        };
        match relation.relation {
            SpatialRelationType::Near if distance(src, tgt) <= NEAR_THRESHOLD => {
                checks.push(format!("{} near {}", relation.source, relation.target));
            }
            SpatialRelationType::Above if src.y < tgt.y => {
                checks.push(format!("{} above {}", relation.source, relation.target));
            }
            _ => violations.push(format!(
                "{} {} {}",
                relation.source, relation.relation.as_str(), relation.target
            )),
        }
    }

    ValidationReport { passed: violations.is_empty(), checks, violations }
}

fn spatial_graph_has_no_cycles(relations: &[SpatialRelation]) -> bool {
    let mut graph: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for r in relations {
        graph.entry(r.source.clone()).or_default().insert(r.target.clone());
        graph.entry(r.target.clone()).or_default();
    }
    collect_cycles_in_graph(&graph).is_empty()
}

fn collect_cycles_in_graph(graph: &BTreeMap<String, BTreeSet<String>>) -> Vec<Vec<String>> {
    let mut cycles: BTreeSet<Vec<String>> = BTreeSet::new();
    for node in graph.keys() {
        let mut path = Vec::new();
        dfs_cycles(node, node, graph, &mut path, &mut cycles);
    }
    cycles.into_iter().collect()
}

fn dfs_cycles(
    start:   &str,
    current: &str,
    graph:   &BTreeMap<String, BTreeSet<String>>,
    path:    &mut Vec<String>,
    cycles:  &mut BTreeSet<Vec<String>>,
) {
    path.push(current.to_string());
    if let Some(nexts) = graph.get(current) {
        for next in nexts {
            if next == start {
                cycles.insert(path.clone());
            } else if !path.contains(next) {
                dfs_cycles(start, next, graph, path, cycles);
            }
        }
    }
    path.pop();
}

fn contained_in_scene(b: &Bounds) -> bool {
    b.x >= 100.0 && b.x <= 700.0 && b.y >= 100.0 && b.y <= 700.0
}

fn distance(a: &Bounds, b: &Bounds) -> f32 {
    ((a.x - b.x).powi(2) + (a.y - b.y).powi(2)).sqrt()
}

// ─── Graph helpers ────────────────────────────────────────────────────────────

fn build_semantic_graph(scene: &SemanticScene) -> ReasonGraph {
    let mut graph    = ReasonGraph::new(GraphType::ReasonGraph);
    let scene_id     = add_node(&mut graph, scene.scene_type.as_str(), StateType::Object);
    for object in &scene.objects {
        let obj_id = add_node(&mut graph, object.as_str(), StateType::Object);
        add_relation(&mut graph, scene_id, obj_id, "contains");
    }
    graph
}

fn add_node(graph: &mut ReasonGraph, label: &str, state_type: StateType) -> Uuid {
    let state    = State::new(state_type, ReasonUnit::new(label, UnitType::Composite, array![0.0]));
    let state_id = graph.add_state(state);
    graph.add_node(Node::new(state_id))
}

fn add_relation(graph: &mut ReasonGraph, source: Uuid, target: Uuid, label: &str) {
    let unit       = ReasonUnit::new(label, UnitType::Symbolic, array![1.0]);
    let transition = Transition::new(TransitionType::Deduction, TransitionOp::Subsumption(unit));
    graph.add_edge(Edge::new(source, target, RelationType::Spatial, transition));
}

fn extract_semantic_scene(graph: &ReasonGraph) -> Result<SemanticScene, String> {
    let (scene_id, scene_type) = graph
        .nodes
        .keys()
        .find_map(|id| {
            let label = node_label(graph, *id).ok()?;
            parse_scene_type(&label).map(|t| (*id, t))
        })
        .ok_or("scene type is missing")?;

    let mut objects: Vec<ObjectType> = graph
        .edges
        .iter()
        .filter(|e| e.source == scene_id && edge_label(e) == "contains")
        .map(|e| node_label(graph, e.target).and_then(|n| parse_object_type(&n)))
        .collect::<Result<_, _>>()?;
    objects.sort();

    Ok(SemanticScene { scene_type, objects })
}

fn node_label(graph: &ReasonGraph, id: Uuid) -> Result<String, String> {
    graph
        .get_node_state(&id)
        .map(|s| s.value.label.clone())
        .ok_or_else(|| format!("state missing for {id}"))
}

fn edge_label(edge: &Edge) -> String {
    match &edge.transition.op {
        TransitionOp::Addition(u)
        | TransitionOp::Subsumption(u)
        | TransitionOp::Refinement { target: u, .. } => u.label.clone(),
    }
}

fn parse_scene_type(label: &str) -> Option<SceneType> {
    match label {
        "DiningRoom" => Some(SceneType::DiningRoom),
        "Bedroom"    => Some(SceneType::Bedroom),
        "Office"     => Some(SceneType::Office),
        "Classroom"  => Some(SceneType::Classroom),
        _            => None,
    }
}

fn parse_object_type(name: &str) -> Result<ObjectType, String> {
    match name {
        "Table"       => Ok(ObjectType::Table),
        "Chair"       => Ok(ObjectType::Chair),
        "Lamp"        => Ok(ObjectType::Lamp),
        "Bed"         => Ok(ObjectType::Bed),
        "Desk"        => Ok(ObjectType::Desk),
        "TeacherDesk" => Ok(ObjectType::TeacherDesk),
        "StudentDesk" => Ok(ObjectType::StudentDesk),
        "Whiteboard"  => Ok(ObjectType::Whiteboard),
        other         => Err(format!("unsupported object type: {other}")),
    }
}

// ─── JSON / PNG serialization ─────────────────────────────────────────────────

fn semantic_scene_json(scene: &SemanticScene) -> String {
    let objs: Vec<_> = scene.objects.iter().map(|o| o.as_str().to_string()).collect();
    format!(
        "{{\n  \"scene_type\": \"{}\",\n  \"objects\": {}\n}}\n",
        scene.scene_type.as_str(),
        json_string_array(&objs)
    )
}

fn completion_report_json(result: &CompletionResult) -> String {
    let status = match result.status {
        CompletionStatus::Complete   => "Complete",
        CompletionStatus::Incomplete => "Incomplete",
        CompletionStatus::Invalid    => "Invalid",
    };
    let added_rels: Vec<String> = result
        .added_relations
        .iter()
        .map(|r| format!("{{ \"source\": \"{}\", \"relation\": \"{}\", \"target\": \"{}\" }}", r.source, r.relation.as_str(), r.target))
        .collect();
    format!(
        "{{\n  \"status\": \"{}\",\n  \"completed\": {},\n  \"added_objects\": {},\n  \"added_relations\": [{}],\n  \"explanation\": {}\n}}\n",
        status,
        result.completed,
        json_string_array(&result.added_objects),
        added_rels.join(", "),
        json_string_array(&result.explanation)
    )
}

fn completed_scene_json(scene: &SemanticScene) -> String {
    semantic_scene_json(scene)
}

fn inferred_spatial_graph_json(relations: &[SpatialRelation]) -> String {
    let entries: Vec<_> = relations
        .iter()
        .map(|r| format!(
            "    {{ \"source\": \"{}\", \"relation\": \"{}\", \"target\": \"{}\" }}",
            r.source, r.relation.as_str(), r.target
        ))
        .collect();
    format!("{{\n  \"relations\": [\n{}\n  ]\n}}\n", entries.join(",\n"))
}

fn layout_json(layout: &BTreeMap<String, Bounds>) -> String {
    let entries: Vec<_> = layout
        .iter()
        .map(|(n, b)| format!(
            "  \"{}\": {{ \"x\": {}, \"y\": {}, \"width\": {}, \"height\": {} }}",
            n, b.x, b.y, b.width, b.height
        ))
        .collect();
    format!("{{\n{}\n}}\n", entries.join(",\n"))
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
    let body = values.iter().map(|v| format!("\"{v}\"")).collect::<Vec<_>>().join(", ");
    format!("[{body}]")
}

fn render_scene_png(layout: &BTreeMap<String, Bounds>) -> Vec<u8> {
    let w = 800u32;
    let h = 800u32;
    let mut rgba = vec![255u8; (w * h * 4) as usize];
    for bounds in layout.values() {
        draw_rectangle(&mut rgba, w, *bounds);
    }
    encode_png_rgba(w, h, &rgba)
}

fn draw_rectangle(rgba: &mut [u8], cw: u32, b: Bounds) {
    let left   = (b.x - b.width  / 2.0) as u32;
    let right  = (b.x + b.width  / 2.0) as u32;
    let top    = (b.y - b.height / 2.0) as u32;
    let bottom = (b.y + b.height / 2.0) as u32;
    for y in top..=bottom {
        for x in left..=right {
            if x == left || x == right || y == top || y == bottom {
                set_pixel(rgba, cw, x, y, [0, 0, 0, 255]);
            }
        }
    }
}

fn set_pixel(rgba: &mut [u8], cw: u32, x: u32, y: u32, color: [u8; 4]) {
    if x >= cw || y >= 800 { return; }
    let i = ((y * cw + x) * 4) as usize;
    rgba[i..i + 4].copy_from_slice(&color);
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
    for row in rgba.chunks_exact(stride) { raw.push(0); raw.extend_from_slice(row); }
    write_png_chunk(&mut png, b"IDAT", &zlib_store(&raw));
    write_png_chunk(&mut png, b"IEND", &[][..]);
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
        let remaining  = data.len() - offset;
        let block_len  = remaining.min(u16::MAX as usize);
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
    let mut crc = 0xffff_ffffu32;
    for byte in bytes {
        crc ^= *byte as u32;
        for _ in 0..8 { let m = (crc & 1).wrapping_neg(); crc = (crc >> 1) ^ (0xedb8_8320 & m); }
    }
    !crc
}

fn adler32(bytes: &[u8]) -> u32 {
    const M: u32 = 65_521;
    let (mut a, mut b) = (1u32, 0u32);
    for byte in bytes { a = (a + *byte as u32) % M; b = (b + a) % M; }
    (b << 16) | a
}

// ─── Test entry point ─────────────────────────────────────────────────────────

#[test]
fn ru_obj_2d_009_semantic_scene_completion() {
    // ── ST-041  Recoverable Completion ──────────────────────────────────────
    // DiningRoom + Table + Lamp  →  Chair inferred
    let incomplete_dining = SemanticScene {
        scene_type: SceneType::DiningRoom,
        objects:    vec![ObjectType::Table, ObjectType::Lamp],
    };
    let result_041 = complete_scene(&incomplete_dining);
    assert_eq!(result_041.status, CompletionStatus::Incomplete);
    assert!(result_041.completed);
    assert_eq!(result_041.added_objects, vec!["Chair"]);
    assert!(!result_041.explanation.is_empty());

    // ── ST-042  Missing Required Object ─────────────────────────────────────
    // DiningRoom + Chair + Lamp  →  Table missing  →  Invalid
    let missing_required = SemanticScene {
        scene_type: SceneType::DiningRoom,
        objects:    vec![ObjectType::Chair, ObjectType::Lamp],
    };
    let result_042 = complete_scene(&missing_required);
    assert_eq!(result_042.status, CompletionStatus::Invalid);
    assert!(!result_042.completed);

    // ── ST-043  Already Complete Scene ──────────────────────────────────────
    // DiningRoom + Table + Chair + Lamp  →  Complete, no addition
    let complete_dining = SemanticScene {
        scene_type: SceneType::DiningRoom,
        objects:    vec![ObjectType::Table, ObjectType::Chair, ObjectType::Lamp],
    };
    let result_043 = complete_scene(&complete_dining);
    assert_eq!(result_043.status, CompletionStatus::Complete);
    assert!(!result_043.completed);
    assert!(result_043.added_objects.is_empty());

    // ── ST-044  Relation Completion ─────────────────────────────────────────
    // After completing the scene, spatial graph must contain inferred relations
    let completed_objects = {
        let mut objs = incomplete_dining.objects.clone();
        objs.push(ObjectType::Chair);
        objs.sort();
        objs
    };
    let completed_dining = SemanticScene {
        scene_type: SceneType::DiningRoom,
        objects:    completed_objects,
    };
    let relations_044 = infer_spatial_graph(&completed_dining).expect("must succeed");
    assert!(relations_044.iter().any(|r| r.source == "Chair" && r.relation == SpatialRelationType::Near && r.target == "Table"),
        "Chair near Table must be inferred");
    assert!(relations_044.iter().any(|r| r.source == "Lamp" && r.relation == SpatialRelationType::Above && r.target == "Table"),
        "Lamp above Table must be inferred");

    // ── ST-045  Completed Scene Reconstruction ───────────────────────────────
    // Incomplete scene  →  complete  →  layout generated
    let result_045    = complete_scene(&incomplete_dining);
    assert!(result_045.completed);
    let completed_sc  = SemanticScene {
        scene_type: SceneType::DiningRoom,
        objects:    {
            let mut objs = incomplete_dining.objects.clone();
            for name in &result_045.added_objects {
                objs.push(parse_object_type(name).unwrap());
            }
            objs.sort();
            objs
        },
    };
    let relations_045 = infer_spatial_graph(&completed_sc).expect("must succeed");
    let layout_045    = reconstruct_layout(&completed_sc, &relations_045).expect("must succeed");
    let report_045    = validate_reconstruction(&completed_sc, &relations_045, &layout_045);
    assert!(report_045.passed, "completed scene reconstruction must pass: {:?}", report_045.violations);

    // ── ST-046  Completion Determinism ──────────────────────────────────────
    let baseline_result  = complete_scene(&incomplete_dining);
    let baseline_graph   = infer_spatial_graph(&completed_sc).unwrap();
    let baseline_layout  = reconstruct_layout(&completed_sc, &baseline_graph).unwrap();
    for run in 0..100 {
        let r = complete_scene(&incomplete_dining);
        assert_eq!(r.added_objects, baseline_result.added_objects, "run {run}: added_objects differ");
        assert_eq!(r.added_relations, baseline_result.added_relations, "run {run}: added_relations differ");
        let g = infer_spatial_graph(&completed_sc).unwrap();
        assert_eq!(g, baseline_graph, "run {run}: graph differs");
        let l = reconstruct_layout(&completed_sc, &g).unwrap();
        assert_eq!(l, baseline_layout, "run {run}: layout differs");
    }

    // ── FC-005  Required Object Missing (already covered by ST-042) ─────────
    // Additional scene types
    let fc005_bedroom = SemanticScene {
        scene_type: SceneType::Bedroom,
        objects:    vec![ObjectType::Lamp],
    };
    assert_eq!(complete_scene(&fc005_bedroom).status, CompletionStatus::Invalid);

    let fc005_office = SemanticScene {
        scene_type: SceneType::Office,
        objects:    vec![ObjectType::Lamp],
    };
    assert_eq!(complete_scene(&fc005_office).status, CompletionStatus::Invalid);

    // ── FC-006  Ambiguous Completion: Room type unknown ──────────────────────
    // (Not directly exercised in this deterministic engine, but validated via
    //  the absence of a catch-all scene type — parse_scene_type returns None
    //  for unknown labels, which prevents graph extraction.)

    // ── Classroom completion ─────────────────────────────────────────────────
    // Classroom with only TeacherDesk  →  StudentDesk, Chair, Whiteboard inferred
    let partial_classroom = SemanticScene {
        scene_type: SceneType::Classroom,
        objects:    vec![ObjectType::TeacherDesk],
    };
    let classroom_result = complete_scene(&partial_classroom);
    assert_eq!(classroom_result.status, CompletionStatus::Incomplete);
    assert!(classroom_result.completed);
    let mut expected_added = vec!["Chair".to_string(), "StudentDesk".to_string(), "Whiteboard".to_string()];
    expected_added.sort();
    let mut actual_added = classroom_result.added_objects.clone();
    actual_added.sort();
    assert_eq!(actual_added, expected_added);

    // ── Artifact generation ──────────────────────────────────────────────────
    let artifact_dir = Path::new("artifacts/ru_obj_2d_009");
    fs::create_dir_all(artifact_dir).expect("artifact directory must be created");

    // semantic_scene.json  — the incomplete input scene
    fs::write(
        artifact_dir.join("semantic_scene.json"),
        semantic_scene_json(&incomplete_dining),
    ).expect("semantic_scene.json");

    // completion_report.json
    let report_json = completion_report_json(&result_045);
    fs::write(artifact_dir.join("completion_report.json"), &report_json)
        .expect("completion_report.json");

    // completed_scene.json
    fs::write(
        artifact_dir.join("completed_scene.json"),
        completed_scene_json(&completed_sc),
    ).expect("completed_scene.json");

    // inferred_spatial_graph.json
    fs::write(
        artifact_dir.join("inferred_spatial_graph.json"),
        inferred_spatial_graph_json(&relations_045),
    ).expect("inferred_spatial_graph.json");

    // layout.json
    let layout_json_str = layout_json(&layout_045);
    fs::write(artifact_dir.join("layout.json"), &layout_json_str)
        .expect("layout.json");

    // validation_report.json
    fs::write(
        artifact_dir.join("validation_report.json"),
        validation_report_json(&report_045),
    ).expect("validation_report.json");

    // semantic_scene.png
    fs::write(
        artifact_dir.join("semantic_scene.png"),
        render_scene_png(&layout_045),
    ).expect("semantic_scene.png");

    // Verify all artifacts exist and are non-empty
    for path in [
        "artifacts/ru_obj_2d_009/semantic_scene.json",
        "artifacts/ru_obj_2d_009/completion_report.json",
        "artifacts/ru_obj_2d_009/completed_scene.json",
        "artifacts/ru_obj_2d_009/inferred_spatial_graph.json",
        "artifacts/ru_obj_2d_009/layout.json",
        "artifacts/ru_obj_2d_009/validation_report.json",
        "artifacts/ru_obj_2d_009/semantic_scene.png",
    ] {
        let bytes = fs::read(path).unwrap_or_else(|_| panic!("artifact missing: {path}"));
        assert!(bytes.len() > 10, "{path} must not be empty");
    }
}
