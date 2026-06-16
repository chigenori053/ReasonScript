use ndarray::{array, Array1};
use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{
    GraphType, RelationType, StateType, TransitionType, UnitType,
};
use reasonscript_runtime_real::core::{ReasonUnit, State, Transition};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::Path;
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq)]
enum SceneObject {
    Rectangle {
        x: u32,
        y: u32,
        width: u32,
        height: u32,
    },
    Circle {
        x: u32,
        y: u32,
        radius: u32,
    },
    Triangle {
        x: u32,
        y: u32,
    },
}

#[derive(Debug, PartialEq)]
struct SceneIr {
    objects: Vec<SceneObject>,
}

#[test]
fn ru_obj_2d_002_spatial_scene_graph_projects_to_visible_png() {
    let (graph, scene_id) = build_scene_graph();

    let scene = project_scene(&graph, scene_id).expect("Scene Graph must project into Scene IR");
    validate_scene_constraints(&scene).expect("spatial constraints must pass");

    assert_eq!(
        scene,
        SceneIr {
            objects: vec![
                SceneObject::Rectangle {
                    x: 300,
                    y: 300,
                    width: 120,
                    height: 80,
                },
                SceneObject::Circle {
                    x: 150,
                    y: 300,
                    radius: 40,
                },
                SceneObject::Triangle { x: 300, y: 150 },
            ],
        }
    );

    let output_path = Path::new("output/scene.png");
    render_scene_png(&scene, output_path).expect("scene.png must be generated");

    let bytes = fs::read(output_path).expect("scene.png must be readable");
    assert!(bytes.starts_with(&[137, 80, 78, 71, 13, 10, 26, 10]));
    assert!(bytes.len() > 100);
}

fn build_scene_graph() -> (ReasonGraph, Uuid) {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);

    let scene_id = add_unit_node(
        &mut graph,
        "SceneUnit",
        StateType::Object,
        UnitType::Composite,
        array![0.0],
    );
    let rectangle_id = add_object_node(&mut graph, "RectangleUnit", "rectangle");
    let circle_id = add_object_node(&mut graph, "CircleUnit", "circle");
    let triangle_id = add_object_node(&mut graph, "TriangleUnit", "triangle");

    add_relation(
        &mut graph,
        scene_id,
        rectangle_id,
        RelationType::PartOf,
        "has",
    );
    add_relation(&mut graph, scene_id, circle_id, RelationType::PartOf, "has");
    add_relation(
        &mut graph,
        scene_id,
        triangle_id,
        RelationType::PartOf,
        "has",
    );

    add_numeric_attr(&mut graph, rectangle_id, "x", 300.0);
    add_numeric_attr(&mut graph, rectangle_id, "y", 300.0);
    add_numeric_attr(&mut graph, rectangle_id, "width", 120.0);
    add_numeric_attr(&mut graph, rectangle_id, "height", 80.0);
    add_numeric_attr(&mut graph, circle_id, "radius", 40.0);

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

    (graph, scene_id)
}

fn add_object_node(graph: &mut ReasonGraph, unit_label: &str, shape_label: &str) -> Uuid {
    let object_id = add_unit_node(
        graph,
        unit_label,
        StateType::Object,
        UnitType::Composite,
        array![0.0],
    );
    let shape_id = add_unit_node(
        graph,
        shape_label,
        StateType::Attribute,
        UnitType::Symbolic,
        array![1.0],
    );
    add_relation(
        graph,
        object_id,
        shape_id,
        RelationType::Dependency,
        "shape",
    );
    object_id
}

fn add_numeric_attr(graph: &mut ReasonGraph, object_id: Uuid, label: &str, value: f64) {
    let attr_id = add_unit_node(
        graph,
        label,
        StateType::Attribute,
        UnitType::Real,
        array![value],
    );
    add_relation(
        graph,
        object_id,
        attr_id,
        RelationType::Dependency,
        "defines",
    );
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

fn project_scene(graph: &ReasonGraph, scene_id: Uuid) -> Result<SceneIr, String> {
    let object_ids = outgoing_ids(graph, scene_id, RelationType::PartOf);
    if object_ids.len() != 3 {
        return Err(format!("expected 3 objects, got {}", object_ids.len()));
    }

    let mut seen_shapes = HashSet::new();
    let mut projected = HashMap::new();
    for object_id in object_ids {
        let object = project_base_object(graph, object_id)?;
        let shape = object_shape(&object).to_string();
        if !seen_shapes.insert(shape) {
            return Err("object duplication detected".to_string());
        }
        projected.insert(object_id, object);
    }

    let relations = spatial_relations(graph);
    let rectangle_id = projected
        .iter()
        .find_map(|(id, object)| matches!(object, SceneObject::Rectangle { .. }).then_some(*id))
        .ok_or_else(|| "Rectangle is missing".to_string())?;

    for relation in relations {
        if relation.target != rectangle_id {
            continue;
        }

        let anchor = projected
            .get(&rectangle_id)
            .cloned()
            .ok_or_else(|| "relation anchor is missing".to_string())?;
        let source = projected
            .get_mut(&relation.source)
            .ok_or_else(|| "relation source is missing".to_string())?;
        apply_spatial_relation(source, &anchor, relation.label.as_str())?;
    }

    Ok(SceneIr {
        objects: vec![
            take_object(&projected, "rectangle")?,
            take_object(&projected, "circle")?,
            take_object(&projected, "triangle")?,
        ],
    })
}

fn project_base_object(graph: &ReasonGraph, object_id: Uuid) -> Result<SceneObject, String> {
    let attrs = outgoing_by_label(graph, object_id, RelationType::Dependency)?;
    let shape = attrs
        .keys()
        .find(|label| matches!(label.as_str(), "rectangle" | "circle" | "triangle"))
        .ok_or_else(|| "Shape is missing".to_string())?;

    match shape.as_str() {
        "rectangle" => Ok(SceneObject::Rectangle {
            x: read_u32_attr(graph, &attrs, "x")?,
            y: read_u32_attr(graph, &attrs, "y")?,
            width: read_u32_attr(graph, &attrs, "width")?,
            height: read_u32_attr(graph, &attrs, "height")?,
        }),
        "circle" => Ok(SceneObject::Circle {
            x: 0,
            y: 0,
            radius: read_u32_attr(graph, &attrs, "radius")?,
        }),
        "triangle" => Ok(SceneObject::Triangle { x: 0, y: 0 }),
        other => Err(format!("unsupported shape: {other}")),
    }
}

fn apply_spatial_relation(
    source: &mut SceneObject,
    anchor: &SceneObject,
    relation: &str,
) -> Result<(), String> {
    let (anchor_x, anchor_y) = anchor_position(anchor);
    match (source, relation) {
        (SceneObject::Circle { x, y, radius }, "left_of") => {
            *x = anchor_x.saturating_sub(150);
            *y = anchor_y;
            if *radius == 0 {
                return Err("circle radius must be greater than 0".to_string());
            }
        }
        (SceneObject::Triangle { x, y }, "above") => {
            *x = anchor_x;
            *y = anchor_y.saturating_sub(150);
        }
        (_, "right_of" | "below") => {
            return Err(format!(
                "{relation} relation is defined but not used in this scene"
            ));
        }
        (_, other) => return Err(format!("unsupported spatial relation: {other}")),
    }
    Ok(())
}

fn validate_scene_constraints(scene: &SceneIr) -> Result<(), String> {
    let rectangle = scene
        .objects
        .iter()
        .find_map(|object| match object {
            SceneObject::Rectangle {
                x,
                y,
                width,
                height,
            } => Some((*x, *y, *width, *height)),
            _ => None,
        })
        .ok_or_else(|| "Rectangle is missing".to_string())?;
    let circle = scene
        .objects
        .iter()
        .find_map(|object| match object {
            SceneObject::Circle { x, y, radius } => Some((*x, *y, *radius)),
            _ => None,
        })
        .ok_or_else(|| "Circle is missing".to_string())?;
    let triangle = scene
        .objects
        .iter()
        .find_map(|object| match object {
            SceneObject::Triangle { x, y } => Some((*x, *y)),
            _ => None,
        })
        .ok_or_else(|| "Triangle is missing".to_string())?;

    if rectangle.2 == 0 || rectangle.3 == 0 {
        return Err("rectangle size must be greater than 0".to_string());
    }
    if circle.2 == 0 {
        return Err("circle radius must be greater than 0".to_string());
    }
    if circle.0 >= rectangle.0 {
        return Err("Circle.x < Rectangle.x constraint failed".to_string());
    }
    if triangle.1 >= rectangle.1 {
        return Err("Triangle.y < Rectangle.y constraint failed".to_string());
    }
    Ok(())
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
        let label = graph
            .get_node_state(&edge.target)
            .ok_or_else(|| format!("target state not found for node {}", edge.target))?
            .value
            .label
            .clone();
        labels.insert(label, edge.target);
    }
    Ok(labels)
}

fn read_u32_attr(
    graph: &ReasonGraph,
    attrs: &HashMap<String, Uuid>,
    name: &str,
) -> Result<u32, String> {
    let node_id = attrs
        .get(name)
        .ok_or_else(|| format!("{name} is missing"))?;
    let state = graph
        .get_node_state(node_id)
        .ok_or_else(|| format!("{name} state is missing"))?;
    let value = state
        .value
        .vector
        .first()
        .ok_or_else(|| format!("{name} value is missing"))?;

    if !value.is_finite() || value.fract() != 0.0 || *value < 0.0 {
        return Err(format!("{name} must be a non-negative integer"));
    }

    Ok(*value as u32)
}

#[derive(Debug)]
struct SpatialRelation {
    source: Uuid,
    target: Uuid,
    label: String,
}

fn spatial_relations(graph: &ReasonGraph) -> Vec<SpatialRelation> {
    graph
        .edges
        .iter()
        .filter(|edge| edge.relation == RelationType::Spatial)
        .map(|edge| SpatialRelation {
            source: edge.source,
            target: edge.target,
            label: relation_label(edge),
        })
        .collect()
}

fn relation_label(edge: &Edge) -> String {
    match &edge.transition.op {
        TransitionOp::Addition(unit)
        | TransitionOp::Subsumption(unit)
        | TransitionOp::Refinement { target: unit, .. } => unit.label.clone(),
    }
}

fn object_shape(object: &SceneObject) -> &'static str {
    match object {
        SceneObject::Rectangle { .. } => "rectangle",
        SceneObject::Circle { .. } => "circle",
        SceneObject::Triangle { .. } => "triangle",
    }
}

fn anchor_position(object: &SceneObject) -> (u32, u32) {
    match object {
        SceneObject::Rectangle { x, y, .. }
        | SceneObject::Circle { x, y, .. }
        | SceneObject::Triangle { x, y } => (*x, *y),
    }
}

fn take_object(objects: &HashMap<Uuid, SceneObject>, shape: &str) -> Result<SceneObject, String> {
    objects
        .values()
        .find(|object| object_shape(object) == shape)
        .cloned()
        .ok_or_else(|| format!("{shape} is missing"))
}

fn render_scene_png(scene: &SceneIr, output_path: &Path) -> std::io::Result<()> {
    let mut rgba = vec![255; 500 * 500 * 4];

    for object in &scene.objects {
        match object {
            SceneObject::Rectangle {
                x,
                y,
                width,
                height,
            } => draw_rectangle(&mut rgba, 500, *x, *y, *width, *height),
            SceneObject::Circle { x, y, radius } => draw_circle(&mut rgba, 500, *x, *y, *radius),
            SceneObject::Triangle { x, y } => draw_triangle(&mut rgba, 500, *x, *y, 90, 80),
        }
    }

    if let Some(parent) = output_path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(output_path, encode_png_rgba(500, 500, &rgba))
}

fn draw_rectangle(rgba: &mut [u8], canvas_width: u32, x: u32, y: u32, width: u32, height: u32) {
    let right = x + width - 1;
    let bottom = y + height - 1;
    for py in y..=bottom {
        for px in x..=right {
            if px == x || px == right || py == y || py == bottom {
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
    let top = (x + width / 2, y);
    let left = (x, y + height);
    let right = (x + width, y + height);
    draw_line(rgba, canvas_width, top, left);
    draw_line(rgba, canvas_width, left, right);
    draw_line(rgba, canvas_width, right, top);
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
