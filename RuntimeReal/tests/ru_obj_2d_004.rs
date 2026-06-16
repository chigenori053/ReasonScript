use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{
    GraphType, RelationType, StateType, TransitionType, UnitType,
};
use reasonscript_runtime_real::core::{ReasonUnit, State, Transition};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph};
use ndarray::{array, Array1};
use std::collections::{BTreeMap, HashMap};
use std::fs;
use std::path::Path;
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq, Eq)]
enum ObjectType {
    Circle,
    Rectangle,
    Triangle,
    Star,
}

impl ObjectType {
    fn as_str(&self) -> &'static str {
        match self {
            Self::Circle => "circle",
            Self::Rectangle => "rectangle",
            Self::Triangle => "triangle",
            Self::Star => "star",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum SpatialRelation {
    LeftOf,
    Above,
    Inside,
}

impl SpatialRelation {
    fn as_str(&self) -> &'static str {
        match self {
            Self::LeftOf => "left_of",
            Self::Above => "above",
            Self::Inside => "inside",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct Constraint {
    source: String,
    relation: SpatialRelation,
    target: String,
}

#[derive(Debug, Clone, PartialEq)]
struct SceneObject {
    name: String,
    object_type: ObjectType,
    x: f32,
    y: f32,
    width: f32,
    height: f32,
}

#[derive(Debug, Clone, PartialEq)]
struct SceneIr {
    scene: Vec<SceneObject>,
    constraints: Vec<Constraint>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ValidationReport {
    passed: bool,
    checks: Vec<String>,
    violations: Vec<String>,
}

#[test]
fn ru_obj_2d_004_multi_object_constraints_solve_to_scene_layout() {
    let (graph, scene_id) = build_relation_only_scene_graph();

    let constraints = generate_constraints(&graph).expect("semantic relations must become constraints");
    assert_eq!(constraints.len(), 3);

    let scene = solve_layout(&graph, scene_id, constraints.clone()).expect("layout must solve");
    let report = validate_constraints(&scene);

    assert_eq!(object_position(&scene, "Circle"), (150.0, 300.0));
    assert_eq!(object_position(&scene, "Rectangle"), (300.0, 300.0));
    assert_eq!(object_position(&scene, "Triangle"), (300.0, 150.0));
    assert_eq!(object_position(&scene, "Star"), (300.0, 300.0));
    assert!(report.passed);
    assert!(report.violations.is_empty());
    assert_eq!(report.checks.len(), 3);

    fs::create_dir_all("artifacts").expect("artifacts directory must be created");
    fs::write("artifacts/scene.json", scene_json(&scene)).expect("scene.json must be generated");
    fs::write("artifacts/validation_report.json", report_json(&report))
        .expect("validation_report.json must be generated");
    render_scene_png(&scene, Path::new("artifacts/scene.png")).expect("scene.png must be generated");

    for path in [
        "artifacts/scene.png",
        "artifacts/scene.json",
        "artifacts/validation_report.json",
    ] {
        let bytes = fs::read(path).expect("artifact must be readable");
        assert!(bytes.len() > 20, "{path} must not be empty");
    }
}

fn build_relation_only_scene_graph() -> (ReasonGraph, Uuid) {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);
    let scene_id = add_unit_node(
        &mut graph,
        "Scene",
        StateType::Object,
        UnitType::Composite,
        array![0.0],
    );

    let circle_id = add_object_node(&mut graph, "Circle", ObjectType::Circle);
    let rectangle_id = add_object_node(&mut graph, "Rectangle", ObjectType::Rectangle);
    let triangle_id = add_object_node(&mut graph, "Triangle", ObjectType::Triangle);
    let star_id = add_object_node(&mut graph, "Star", ObjectType::Star);

    add_relation(&mut graph, scene_id, circle_id, RelationType::PartOf, "has");
    add_relation(&mut graph, scene_id, rectangle_id, RelationType::PartOf, "has");
    add_relation(&mut graph, scene_id, triangle_id, RelationType::PartOf, "has");
    add_relation(&mut graph, scene_id, star_id, RelationType::PartOf, "has");

    add_relation(
        &mut graph,
        circle_id,
        rectangle_id,
        RelationType::Spatial,
        "left_of",
    );
    add_relation(
        &mut graph,
        triangle_id,
        rectangle_id,
        RelationType::Spatial,
        "above",
    );
    add_relation(
        &mut graph,
        star_id,
        rectangle_id,
        RelationType::Spatial,
        "inside",
    );

    (graph, scene_id)
}

fn add_object_node(graph: &mut ReasonGraph, name: &str, object_type: ObjectType) -> Uuid {
    let object_id = add_unit_node(
        graph,
        name,
        StateType::Object,
        UnitType::Composite,
        array![0.0],
    );
    let shape_id = add_unit_node(
        graph,
        object_type.as_str(),
        StateType::Attribute,
        UnitType::Symbolic,
        array![1.0],
    );
    add_relation(graph, object_id, shape_id, RelationType::Dependency, "shape");
    object_id
}

fn add_unit_node(
    graph: &mut ReasonGraph,
    label: &str,
    state_type: StateType,
    unit_type: UnitType,
    vector: Array1<f64>,
) -> Uuid {
    let state = State::new(state_type, ReasonUnit::new(label, unit_type, vector));
    let state_id = graph.add_state(state);
    graph.add_node(Node::new(state_id))
}

fn add_relation(
    graph: &mut ReasonGraph,
    source: Uuid,
    target: Uuid,
    relation: RelationType,
    relation_label: &str,
) {
    let transition_unit = ReasonUnit::new(relation_label, UnitType::Symbolic, array![1.0]);
    let transition = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Subsumption(transition_unit),
    );
    graph.add_edge(Edge::new(source, target, relation, transition));
}

fn generate_constraints(graph: &ReasonGraph) -> Result<Vec<Constraint>, String> {
    graph
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
        .collect()
}

fn solve_layout(
    graph: &ReasonGraph,
    scene_id: Uuid,
    constraints: Vec<Constraint>,
) -> Result<SceneIr, String> {
    let mut objects = BTreeMap::new();
    for object_id in outgoing_ids(graph, scene_id, RelationType::PartOf) {
        let name = object_name(graph, object_id)?;
        let object_type = object_type(graph, object_id)?;
        objects.insert(name.clone(), default_object(name, object_type));
    }

    let rectangle = objects
        .get_mut("Rectangle")
        .ok_or_else(|| "Rectangle root is missing".to_string())?;
    rectangle.x = 300.0;
    rectangle.y = 300.0;

    for constraint in &constraints {
        let target = objects
            .get(&constraint.target)
            .cloned()
            .ok_or_else(|| format!("target {} is missing", constraint.target))?;
        let source = objects
            .get_mut(&constraint.source)
            .ok_or_else(|| format!("source {} is missing", constraint.source))?;

        match constraint.relation {
            SpatialRelation::LeftOf => {
                source.x = target.x - 150.0;
                source.y = target.y;
            }
            SpatialRelation::Above => {
                source.x = target.x;
                source.y = target.y - 150.0;
            }
            SpatialRelation::Inside => {
                source.x = target.x;
                source.y = target.y;
            }
        }
    }

    Ok(SceneIr {
        scene: objects.into_values().collect(),
        constraints,
    })
}

fn default_object(name: String, object_type: ObjectType) -> SceneObject {
    let (width, height) = match object_type {
        ObjectType::Circle => (80.0, 80.0),
        ObjectType::Rectangle => (120.0, 80.0),
        ObjectType::Triangle => (90.0, 80.0),
        ObjectType::Star => (30.0, 30.0),
    };

    SceneObject {
        name,
        object_type,
        x: 0.0,
        y: 0.0,
        width,
        height,
    }
}

fn validate_constraints(scene: &SceneIr) -> ValidationReport {
    let mut checks = Vec::new();
    let mut violations = Vec::new();

    for constraint in &scene.constraints {
        let source = object_by_name(scene, &constraint.source);
        let target = object_by_name(scene, &constraint.target);

        match (source, target) {
            (Some(source), Some(target)) => {
                let passed = match constraint.relation {
                    SpatialRelation::LeftOf => source.x < target.x,
                    SpatialRelation::Above => source.y < target.y,
                    SpatialRelation::Inside => {
                        let left = target.x - target.width / 2.0;
                        let right = target.x + target.width / 2.0;
                        let top = target.y - target.height / 2.0;
                        let bottom = target.y + target.height / 2.0;
                        source.x >= left && source.x <= right && source.y >= top && source.y <= bottom
                    }
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
            _ => violations.push(format!(
                "{} {} {} references a missing object",
                constraint.source,
                constraint.relation.as_str(),
                constraint.target
            )),
        }
    }

    ValidationReport {
        passed: violations.is_empty(),
        checks,
        violations,
    }
}

fn object_type(graph: &ReasonGraph, object_id: Uuid) -> Result<ObjectType, String> {
    let attrs = outgoing_by_label(graph, object_id, RelationType::Dependency)?;
    attrs
        .keys()
        .find_map(|label| match label.as_str() {
            "circle" => Some(ObjectType::Circle),
            "rectangle" => Some(ObjectType::Rectangle),
            "triangle" => Some(ObjectType::Triangle),
            "star" => Some(ObjectType::Star),
            _ => None,
        })
        .ok_or_else(|| format!("object type is missing for {}", object_name(graph, object_id).unwrap_or_default()))
}

fn outgoing_ids(graph: &ReasonGraph, source: Uuid, relation: RelationType) -> Vec<Uuid> {
    graph
        .edges
        .iter()
        .filter(|edge| edge.source == source && edge.relation == relation)
        .map(|edge| edge.target)
        .collect()
}

fn outgoing_by_label(
    graph: &ReasonGraph,
    source: Uuid,
    relation: RelationType,
) -> Result<HashMap<String, Uuid>, String> {
    let mut labels = HashMap::new();
    for edge in graph
        .edges
        .iter()
        .filter(|edge| edge.source == source && edge.relation == relation)
    {
        labels.insert(object_name(graph, edge.target)?, edge.target);
    }
    Ok(labels)
}

fn object_name(graph: &ReasonGraph, object_id: Uuid) -> Result<String, String> {
    graph
        .get_node_state(&object_id)
        .map(|state| state.value.label.clone())
        .ok_or_else(|| format!("state is missing for node {object_id}"))
}

fn parse_relation(label: &str) -> Result<SpatialRelation, String> {
    match label {
        "left_of" => Ok(SpatialRelation::LeftOf),
        "above" => Ok(SpatialRelation::Above),
        "inside" => Ok(SpatialRelation::Inside),
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

fn object_by_name<'a>(scene: &'a SceneIr, name: &str) -> Option<&'a SceneObject> {
    scene.scene.iter().find(|object| object.name == name)
}

fn object_position(scene: &SceneIr, name: &str) -> (f32, f32) {
    let object = object_by_name(scene, name).expect("object must exist");
    (object.x, object.y)
}

fn scene_json(scene: &SceneIr) -> String {
    let objects = scene
        .scene
        .iter()
        .map(|object| {
            format!(
                "    {{ \"name\": \"{}\", \"type\": \"{}\", \"x\": {}, \"y\": {}, \"width\": {}, \"height\": {} }}",
                object.name,
                object.object_type.as_str(),
                object.x,
                object.y,
                object.width,
                object.height
            )
        })
        .collect::<Vec<_>>()
        .join(",\n");
    let constraints = scene
        .constraints
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
        "{{\n  \"scene\": [\n{}\n  ],\n  \"constraints\": [\n{}\n  ]\n}}\n",
        objects, constraints
    )
}

fn report_json(report: &ValidationReport) -> String {
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

fn render_scene_png(scene: &SceneIr, output_path: &Path) -> std::io::Result<()> {
    let canvas_width = 600;
    let canvas_height = 500;
    let mut rgba = vec![255; (canvas_width * canvas_height * 4) as usize];

    for object in &scene.scene {
        match object.object_type {
            ObjectType::Circle => draw_circle(&mut rgba, canvas_width, object.x as u32, object.y as u32, 40),
            ObjectType::Rectangle => draw_rectangle(
                &mut rgba,
                canvas_width,
                object.x as u32,
                object.y as u32,
                object.width as u32,
                object.height as u32,
            ),
            ObjectType::Triangle => draw_triangle(
                &mut rgba,
                canvas_width,
                object.x as u32,
                object.y as u32,
                object.width as u32,
                object.height as u32,
            ),
            ObjectType::Star => draw_star(&mut rgba, canvas_width, object.x as u32, object.y as u32, 15),
        }
    }

    fs::write(output_path, encode_png_rgba(canvas_width, canvas_height, &rgba))
}

fn draw_rectangle(rgba: &mut [u8], canvas_width: u32, x: u32, y: u32, width: u32, height: u32) {
    let left = x - width / 2;
    let right = x + width / 2;
    let top = y - height / 2;
    let bottom = y + height / 2;
    for py in top..=bottom {
        for px in left..=right {
            if px == left || px == right || py == top || py == bottom {
                set_black_pixel(rgba, canvas_width, px, py);
            }
        }
    }
}

fn draw_circle(rgba: &mut [u8], canvas_width: u32, cx: u32, cy: u32, radius: u32) {
    let r = radius as i32;
    let cx = cx as i32;
    let cy = cy as i32;
    for y in (cy - r)..=(cy + r) {
        for x in (cx - r)..=(cx + r) {
            let distance = (x - cx).pow(2) + (y - cy).pow(2);
            if (distance - r.pow(2)).abs() <= r {
                set_black_pixel(rgba, canvas_width, x as u32, y as u32);
            }
        }
    }
}

fn draw_triangle(rgba: &mut [u8], canvas_width: u32, x: u32, y: u32, width: u32, height: u32) {
    let top = (x, y - height / 2);
    let left = (x - width / 2, y + height / 2);
    let right = (x + width / 2, y + height / 2);
    draw_line(rgba, canvas_width, top, left);
    draw_line(rgba, canvas_width, left, right);
    draw_line(rgba, canvas_width, right, top);
}

fn draw_star(rgba: &mut [u8], canvas_width: u32, cx: u32, cy: u32, radius: u32) {
    draw_line(rgba, canvas_width, (cx - radius, cy), (cx + radius, cy));
    draw_line(rgba, canvas_width, (cx, cy - radius), (cx, cy + radius));
    draw_line(
        rgba,
        canvas_width,
        (cx - radius, cy - radius),
        (cx + radius, cy + radius),
    );
    draw_line(
        rgba,
        canvas_width,
        (cx - radius, cy + radius),
        (cx + radius, cy - radius),
    );
}

fn draw_line(rgba: &mut [u8], canvas_width: u32, start: (u32, u32), end: (u32, u32)) {
    let (mut x0, mut y0) = (start.0 as i32, start.1 as i32);
    let (x1, y1) = (end.0 as i32, end.1 as i32);
    let dx = (x1 - x0).abs();
    let sx = if x0 < x1 { 1 } else { -1 };
    let dy = -(y1 - y0).abs();
    let sy = if y0 < y1 { 1 } else { -1 };
    let mut err = dx + dy;

    loop {
        set_black_pixel(rgba, canvas_width, x0 as u32, y0 as u32);
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

fn set_black_pixel(rgba: &mut [u8], canvas_width: u32, x: u32, y: u32) {
    if x >= canvas_width || y >= 500 {
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
