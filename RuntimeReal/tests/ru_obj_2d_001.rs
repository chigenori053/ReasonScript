use ndarray::{array, Array1};
use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{
    GraphType, RelationType, StateType, TransitionType, UnitType,
};
use reasonscript_runtime_real::core::{ReasonUnit, State, Transition};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph};
use std::collections::HashMap;
use std::fs;
use std::path::Path;
use uuid::Uuid;

#[derive(Debug, PartialEq)]
struct Drawable2D {
    object_type: String,
    x: u32,
    y: u32,
    width: u32,
    height: u32,
}

#[test]
fn ru_obj_2d_001_rectangle_graph_projects_to_visible_png() {
    let (graph, rectangle_id) = build_rectangle_graph();

    let drawable = project_rectangle(&graph, rectangle_id)
        .expect("RectangleUnit must project into Drawable2D IR");
    validate_constraints(&drawable).expect("rectangle constraints must pass");

    assert_eq!(
        drawable,
        Drawable2D {
            object_type: "rectangle".to_string(),
            x: 50,
            y: 50,
            width: 120,
            height: 80,
        }
    );

    let output_path = Path::new("output/ru_obj_2d_rectangle.png");
    render_rectangle_png(&drawable, output_path).expect("visible rectangle PNG must be generated");

    let bytes = fs::read(output_path).expect("PNG output must be readable");
    assert!(bytes.starts_with(&[137, 80, 78, 71, 13, 10, 26, 10]));
    assert!(bytes.len() > 100);
}

fn build_rectangle_graph() -> (ReasonGraph, Uuid) {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);

    let rectangle_id = add_unit_node(
        &mut graph,
        "RectangleUnit",
        StateType::Object,
        UnitType::Composite,
        array![0.0],
    );
    let position_id = add_unit_node(
        &mut graph,
        "PositionUnit",
        StateType::Attribute,
        UnitType::Composite,
        array![0.0],
    );
    let size_id = add_unit_node(
        &mut graph,
        "SizeUnit",
        StateType::Attribute,
        UnitType::Composite,
        array![0.0],
    );
    let shape_id = add_unit_node(
        &mut graph,
        "ShapeUnit",
        StateType::Attribute,
        UnitType::Composite,
        array![0.0],
    );

    let x_id = add_unit_node(
        &mut graph,
        "x",
        StateType::Attribute,
        UnitType::Real,
        array![50.0],
    );
    let y_id = add_unit_node(
        &mut graph,
        "y",
        StateType::Attribute,
        UnitType::Real,
        array![50.0],
    );
    let width_id = add_unit_node(
        &mut graph,
        "width",
        StateType::Attribute,
        UnitType::Real,
        array![120.0],
    );
    let height_id = add_unit_node(
        &mut graph,
        "height",
        StateType::Attribute,
        UnitType::Real,
        array![80.0],
    );
    let rectangle_kind_id = add_unit_node(
        &mut graph,
        "rectangle",
        StateType::Attribute,
        UnitType::Symbolic,
        array![1.0],
    );

    add_relation(&mut graph, rectangle_id, position_id, RelationType::PartOf);
    add_relation(&mut graph, rectangle_id, size_id, RelationType::PartOf);
    add_relation(&mut graph, rectangle_id, shape_id, RelationType::PartOf);
    add_relation(&mut graph, position_id, x_id, RelationType::Dependency);
    add_relation(&mut graph, position_id, y_id, RelationType::Dependency);
    add_relation(&mut graph, size_id, width_id, RelationType::Dependency);
    add_relation(&mut graph, size_id, height_id, RelationType::Dependency);
    add_relation(
        &mut graph,
        shape_id,
        rectangle_kind_id,
        RelationType::Dependency,
    );

    (graph, rectangle_id)
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

fn add_relation(graph: &mut ReasonGraph, source: Uuid, target: Uuid, relation: RelationType) {
    let transition_unit =
        ReasonUnit::new("ru-obj-2d-001 relation", UnitType::Symbolic, array![1.0]);
    let transition = Transition::new(
        TransitionType::Deduction,
        TransitionOp::Subsumption(transition_unit),
    );
    graph.add_edge(Edge::new(source, target, relation, transition));
}

fn project_rectangle(graph: &ReasonGraph, rectangle_id: Uuid) -> Result<Drawable2D, String> {
    let parts = outgoing_by_label(graph, rectangle_id, RelationType::PartOf)?;
    let position_id = *parts
        .get("PositionUnit")
        .ok_or_else(|| "Position is missing".to_string())?;
    let size_id = *parts
        .get("SizeUnit")
        .ok_or_else(|| "Size is missing".to_string())?;
    let shape_id = *parts
        .get("ShapeUnit")
        .ok_or_else(|| "Shape is missing".to_string())?;

    let position_attrs = outgoing_by_label(graph, position_id, RelationType::Dependency)?;
    let size_attrs = outgoing_by_label(graph, size_id, RelationType::Dependency)?;
    let shape_attrs = outgoing_by_label(graph, shape_id, RelationType::Dependency)?;

    let object_type = shape_attrs
        .keys()
        .next()
        .cloned()
        .ok_or_else(|| "Shape kind is missing".to_string())?;

    if object_type != "rectangle" {
        return Err(format!("unsupported shape: {object_type}"));
    }

    Ok(Drawable2D {
        object_type,
        x: read_u32_attr(graph, &position_attrs, "x")?,
        y: read_u32_attr(graph, &position_attrs, "y")?,
        width: read_u32_attr(graph, &size_attrs, "width")?,
        height: read_u32_attr(graph, &size_attrs, "height")?,
    })
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

fn validate_constraints(drawable: &Drawable2D) -> Result<(), String> {
    if drawable.width == 0 {
        return Err("width must be greater than 0".to_string());
    }
    if drawable.height == 0 {
        return Err("height must be greater than 0".to_string());
    }
    Ok(())
}

fn render_rectangle_png(drawable: &Drawable2D, output_path: &Path) -> std::io::Result<()> {
    let canvas_width = drawable.x + drawable.width + 50;
    let canvas_height = drawable.y + drawable.height + 50;
    let mut rgba = vec![255; (canvas_width * canvas_height * 4) as usize];

    let left = drawable.x;
    let right = drawable.x + drawable.width - 1;
    let top = drawable.y;
    let bottom = drawable.y + drawable.height - 1;

    for y in top..=bottom {
        for x in left..=right {
            if x == left || x == right || y == top || y == bottom {
                let index = ((y * canvas_width + x) * 4) as usize;
                rgba[index] = 0;
                rgba[index + 1] = 0;
                rgba[index + 2] = 0;
                rgba[index + 3] = 255;
            }
        }
    }

    if let Some(parent) = output_path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(
        output_path,
        encode_png_rgba(canvas_width, canvas_height, &rgba),
    )
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
