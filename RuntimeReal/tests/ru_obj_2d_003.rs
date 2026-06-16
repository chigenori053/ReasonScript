use ndarray::{array, Array1};
use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{
    GraphType, RelationType, StateType, TransitionType, UnitType,
};
use reasonscript_runtime_real::core::{ReasonUnit, State, Transition};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::fs;
use std::path::Path;
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq, Eq)]
enum SpatialRelation {
    LeftOf,
    RightOf,
}

impl SpatialRelation {
    fn as_str(&self) -> &'static str {
        match self {
            Self::LeftOf => "left_of",
            Self::RightOf => "right_of",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct StateDelta {
    object: String,
    relation_before: SpatialRelation,
    relation_after: SpatialRelation,
    target: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct RelationChange {
    source: String,
    relation_before: SpatialRelation,
    relation_after: SpatialRelation,
    target: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct SceneDelta {
    added_objects: Vec<String>,
    removed_objects: Vec<String>,
    moved_objects: Vec<String>,
    changed_relations: Vec<RelationChange>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum Shape {
    Rectangle,
    Circle,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct SceneObject {
    name: String,
    shape: Shape,
    x: u32,
    y: u32,
    width: Option<u32>,
    height: Option<u32>,
    radius: Option<u32>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct SceneIr {
    objects: Vec<SceneObject>,
    relations: Vec<RelationChange>,
}

#[test]
fn ru_obj_2d_003_state_transition_projects_to_scene_and_visual_delta() {
    let (before_graph, scene_id) = build_scene_graph(SpatialRelation::LeftOf);

    let scene_before = project_scene(&before_graph, scene_id)
        .expect("initial ReasonGraph must project into Scene A");
    validate_scene_constraints(&scene_before).expect("Scene A constraints must pass");

    let state_delta = StateDelta {
        object: "Circle".to_string(),
        relation_before: SpatialRelation::LeftOf,
        relation_after: SpatialRelation::RightOf,
        target: "Rectangle".to_string(),
    };

    let after_graph = apply_state_delta(&before_graph, &state_delta)
        .expect("left_of -> right_of StateDelta must be applied");
    let scene_after = project_scene(&after_graph, scene_id)
        .expect("target ReasonGraph must project into Scene B");
    validate_scene_constraints(&scene_after).expect("Scene B constraints must pass");

    let scene_delta = compare_scenes(&scene_before, &scene_after);

    assert_eq!(circle_x(&scene_before), 150);
    assert_eq!(rectangle_x(&scene_before), 300);
    assert!(circle_x(&scene_before) < rectangle_x(&scene_before));
    assert_eq!(circle_x(&scene_after), 500);
    assert_eq!(rectangle_x(&scene_after), 300);
    assert!(circle_x(&scene_after) > rectangle_x(&scene_after));
    assert_eq!(rectangle_x(&scene_before), rectangle_x(&scene_after));
    assert_eq!(scene_delta.added_objects, Vec::<String>::new());
    assert_eq!(scene_delta.removed_objects, Vec::<String>::new());
    assert_eq!(scene_delta.moved_objects, vec!["Circle".to_string()]);
    assert_eq!(
        scene_delta.changed_relations,
        vec![RelationChange {
            source: "Circle".to_string(),
            relation_before: SpatialRelation::LeftOf,
            relation_after: SpatialRelation::RightOf,
            target: "Rectangle".to_string(),
        }]
    );

    fs::create_dir_all("output").expect("output directory must be created");
    fs::write("output/scene_before.json", scene_json(&scene_before))
        .expect("scene_before.json must be generated");
    fs::write("output/scene_after.json", scene_json(&scene_after))
        .expect("scene_after.json must be generated");
    fs::write("output/scene_delta.json", scene_delta_json(&scene_delta))
        .expect("scene_delta.json must be generated");

    render_scene_png(&scene_before, Path::new("output/scene_before.png"))
        .expect("scene_before.png must be generated");
    render_scene_png(&scene_after, Path::new("output/scene_after.png"))
        .expect("scene_after.png must be generated");

    for path in [
        "output/scene_before.png",
        "output/scene_after.png",
        "output/scene_delta.json",
        "output/scene_before.json",
        "output/scene_after.json",
    ] {
        let bytes = fs::read(path).expect("artifact must be readable");
        assert!(bytes.len() > 20, "{path} must not be empty");
    }
}

fn build_scene_graph(relation: SpatialRelation) -> (ReasonGraph, Uuid) {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);
    let scene_id = add_unit_node(
        &mut graph,
        "SceneUnit",
        StateType::Object,
        UnitType::Composite,
        array![0.0],
    );
    let rectangle_id = add_object_node(&mut graph, "Rectangle", Shape::Rectangle);
    let circle_id = add_object_node(&mut graph, "Circle", Shape::Circle);

    add_relation(
        &mut graph,
        scene_id,
        rectangle_id,
        RelationType::PartOf,
        "has",
    );
    add_relation(&mut graph, scene_id, circle_id, RelationType::PartOf, "has");
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
        relation.as_str(),
    );

    (graph, scene_id)
}

fn add_object_node(graph: &mut ReasonGraph, object_name: &str, shape: Shape) -> Uuid {
    let object_id = add_unit_node(
        graph,
        object_name,
        StateType::Object,
        UnitType::Composite,
        array![0.0],
    );
    let shape_label = match shape {
        Shape::Rectangle => "rectangle",
        Shape::Circle => "circle",
    };
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

fn apply_state_delta(graph: &ReasonGraph, delta: &StateDelta) -> Result<ReasonGraph, String> {
    let mut next = graph.clone();
    let mut changed = false;

    for edge in &mut next.edges {
        if edge.relation != RelationType::Spatial {
            continue;
        }

        let source = graph
            .get_node_state(&edge.source)
            .ok_or_else(|| "spatial source state is missing".to_string())?
            .value
            .label
            .clone();
        let target = graph
            .get_node_state(&edge.target)
            .ok_or_else(|| "spatial target state is missing".to_string())?
            .value
            .label
            .clone();

        if source == delta.object
            && target == delta.target
            && relation_label(edge) == delta.relation_before.as_str()
        {
            edge.transition.op = TransitionOp::Subsumption(ReasonUnit::new(
                delta.relation_after.as_str(),
                UnitType::Symbolic,
                array![1.0],
            ));
            changed = true;
        }
    }

    if changed {
        Ok(next)
    } else {
        Err("matching StateDelta relation was not found".to_string())
    }
}

fn project_scene(graph: &ReasonGraph, scene_id: Uuid) -> Result<SceneIr, String> {
    let object_ids = outgoing_ids(graph, scene_id, RelationType::PartOf);
    if object_ids.len() != 2 {
        return Err(format!("expected 2 objects, got {}", object_ids.len()));
    }

    let mut projected = HashMap::new();
    for object_id in object_ids {
        projected.insert(object_id, project_base_object(graph, object_id)?);
    }

    let relations = spatial_relation_changes(graph)?;
    for relation in &relations {
        let target_id = object_id_by_name(graph, &projected, &relation.target)?;
        let source_id = object_id_by_name(graph, &projected, &relation.source)?;
        let anchor = projected
            .get(&target_id)
            .cloned()
            .ok_or_else(|| "relation target object is missing".to_string())?;
        let source = projected
            .get_mut(&source_id)
            .ok_or_else(|| "relation source object is missing".to_string())?;
        apply_spatial_relation(source, &anchor, &relation.relation_after)?;
    }

    Ok(SceneIr {
        objects: vec![
            take_object(&projected, "Rectangle")?,
            take_object(&projected, "Circle")?,
        ],
        relations,
    })
}

fn project_base_object(graph: &ReasonGraph, object_id: Uuid) -> Result<SceneObject, String> {
    let attrs = outgoing_by_label(graph, object_id, RelationType::Dependency)?;
    let name = graph
        .get_node_state(&object_id)
        .ok_or_else(|| "object state is missing".to_string())?
        .value
        .label
        .clone();
    let shape = attrs
        .keys()
        .find(|label| matches!(label.as_str(), "rectangle" | "circle"))
        .ok_or_else(|| "Shape is missing".to_string())?;

    match shape.as_str() {
        "rectangle" => Ok(SceneObject {
            name,
            shape: Shape::Rectangle,
            x: read_u32_attr(graph, &attrs, "x")?,
            y: read_u32_attr(graph, &attrs, "y")?,
            width: Some(read_u32_attr(graph, &attrs, "width")?),
            height: Some(read_u32_attr(graph, &attrs, "height")?),
            radius: None,
        }),
        "circle" => Ok(SceneObject {
            name,
            shape: Shape::Circle,
            x: 0,
            y: 0,
            width: None,
            height: None,
            radius: Some(read_u32_attr(graph, &attrs, "radius")?),
        }),
        other => Err(format!("unsupported shape: {other}")),
    }
}

fn apply_spatial_relation(
    source: &mut SceneObject,
    anchor: &SceneObject,
    relation: &SpatialRelation,
) -> Result<(), String> {
    match (&source.shape, relation) {
        (Shape::Circle, SpatialRelation::LeftOf) => {
            source.x = anchor.x.saturating_sub(150);
            source.y = anchor.y;
        }
        (Shape::Circle, SpatialRelation::RightOf) => {
            source.x = anchor.x + 200;
            source.y = anchor.y;
        }
        _ => {
            return Err(format!(
                "unsupported relation {} for source {}",
                relation.as_str(),
                source.name
            ))
        }
    }
    Ok(())
}

fn validate_scene_constraints(scene: &SceneIr) -> Result<(), String> {
    let rectangle = object_by_name(scene, "Rectangle")?;
    let circle = object_by_name(scene, "Circle")?;

    if rectangle.width == Some(0) || rectangle.height == Some(0) {
        return Err("rectangle size must be greater than 0".to_string());
    }
    if circle.radius == Some(0) {
        return Err("circle radius must be greater than 0".to_string());
    }

    for relation in &scene.relations {
        match relation.relation_after {
            SpatialRelation::LeftOf if circle.x >= rectangle.x => {
                return Err("Circle.x < Rectangle.x constraint failed".to_string())
            }
            SpatialRelation::RightOf if circle.x <= rectangle.x => {
                return Err("Circle.x > Rectangle.x constraint failed".to_string())
            }
            _ => {}
        }
    }

    Ok(())
}

fn compare_scenes(before: &SceneIr, after: &SceneIr) -> SceneDelta {
    let before_names: BTreeSet<_> = before
        .objects
        .iter()
        .map(|object| object.name.clone())
        .collect();
    let after_names: BTreeSet<_> = after
        .objects
        .iter()
        .map(|object| object.name.clone())
        .collect();
    let before_by_name = before
        .objects
        .iter()
        .map(|object| (object.name.clone(), object))
        .collect::<BTreeMap<_, _>>();
    let after_by_name = after
        .objects
        .iter()
        .map(|object| (object.name.clone(), object))
        .collect::<BTreeMap<_, _>>();

    let moved_objects = before_names
        .intersection(&after_names)
        .filter(|name| {
            let before = before_by_name.get(*name).expect("before object must exist");
            let after = after_by_name.get(*name).expect("after object must exist");
            before.x != after.x || before.y != after.y
        })
        .cloned()
        .collect();

    let changed_relations = before
        .relations
        .iter()
        .filter_map(|before_relation| {
            after
                .relations
                .iter()
                .find(|after_relation| {
                    after_relation.source == before_relation.source
                        && after_relation.target == before_relation.target
                })
                .and_then(|after_relation| {
                    (before_relation.relation_after != after_relation.relation_after).then(|| {
                        RelationChange {
                            source: before_relation.source.clone(),
                            relation_before: before_relation.relation_after.clone(),
                            relation_after: after_relation.relation_after.clone(),
                            target: before_relation.target.clone(),
                        }
                    })
                })
        })
        .collect();

    SceneDelta {
        added_objects: after_names.difference(&before_names).cloned().collect(),
        removed_objects: before_names.difference(&after_names).cloned().collect(),
        moved_objects,
        changed_relations,
    }
}

fn spatial_relation_changes(graph: &ReasonGraph) -> Result<Vec<RelationChange>, String> {
    graph
        .edges
        .iter()
        .filter(|edge| edge.relation == RelationType::Spatial)
        .map(|edge| {
            let source = graph
                .get_node_state(&edge.source)
                .ok_or_else(|| "spatial source state is missing".to_string())?
                .value
                .label
                .clone();
            let target = graph
                .get_node_state(&edge.target)
                .ok_or_else(|| "spatial target state is missing".to_string())?
                .value
                .label
                .clone();
            let relation_after = parse_spatial_relation(relation_label(edge).as_str())?;
            Ok(RelationChange {
                source,
                relation_before: relation_after.clone(),
                relation_after,
                target,
            })
        })
        .collect()
}

fn parse_spatial_relation(label: &str) -> Result<SpatialRelation, String> {
    match label {
        "left_of" => Ok(SpatialRelation::LeftOf),
        "right_of" => Ok(SpatialRelation::RightOf),
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

fn object_id_by_name(
    graph: &ReasonGraph,
    objects: &HashMap<Uuid, SceneObject>,
    name: &str,
) -> Result<Uuid, String> {
    objects
        .keys()
        .find(|id| {
            graph
                .get_node_state(id)
                .map(|state| state.value.label == name)
                .unwrap_or(false)
        })
        .copied()
        .ok_or_else(|| format!("{name} object is missing"))
}

fn take_object(objects: &HashMap<Uuid, SceneObject>, name: &str) -> Result<SceneObject, String> {
    objects
        .values()
        .find(|object| object.name == name)
        .cloned()
        .ok_or_else(|| format!("{name} is missing"))
}

fn object_by_name<'a>(scene: &'a SceneIr, name: &str) -> Result<&'a SceneObject, String> {
    scene
        .objects
        .iter()
        .find(|object| object.name == name)
        .ok_or_else(|| format!("{name} is missing"))
}

fn circle_x(scene: &SceneIr) -> u32 {
    object_by_name(scene, "Circle")
        .expect("Circle must exist")
        .x
}

fn rectangle_x(scene: &SceneIr) -> u32 {
    object_by_name(scene, "Rectangle")
        .expect("Rectangle must exist")
        .x
}

fn scene_json(scene: &SceneIr) -> String {
    let objects = scene
        .objects
        .iter()
        .map(|object| match object.shape {
            Shape::Rectangle => format!(
                "    {{ \"name\": \"{}\", \"type\": \"rectangle\", \"x\": {}, \"y\": {}, \"width\": {}, \"height\": {} }}",
                object.name,
                object.x,
                object.y,
                object.width.expect("rectangle width must exist"),
                object.height.expect("rectangle height must exist")
            ),
            Shape::Circle => format!(
                "    {{ \"name\": \"{}\", \"type\": \"circle\", \"x\": {}, \"y\": {}, \"radius\": {} }}",
                object.name,
                object.x,
                object.y,
                object.radius.expect("circle radius must exist")
            ),
        })
        .collect::<Vec<_>>()
        .join(",\n");
    let relations = scene
        .relations
        .iter()
        .map(|relation| {
            format!(
                "    {{ \"source\": \"{}\", \"relation\": \"{}\", \"target\": \"{}\" }}",
                relation.source,
                relation.relation_after.as_str(),
                relation.target
            )
        })
        .collect::<Vec<_>>()
        .join(",\n");

    format!(
        "{{\n  \"scene\": [\n{}\n  ],\n  \"relations\": [\n{}\n  ]\n}}\n",
        objects, relations
    )
}

fn scene_delta_json(delta: &SceneDelta) -> String {
    let moved_objects = json_string_array(&delta.moved_objects);
    let changed_relations = delta
        .changed_relations
        .iter()
        .map(|relation| {
            format!(
                "    {{ \"source\": \"{}\", \"relation_before\": \"{}\", \"relation_after\": \"{}\", \"target\": \"{}\" }}",
                relation.source,
                relation.relation_before.as_str(),
                relation.relation_after.as_str(),
                relation.target
            )
        })
        .collect::<Vec<_>>()
        .join(",\n");

    format!(
        "{{\n  \"added_objects\": {},\n  \"removed_objects\": {},\n  \"moved_objects\": {},\n  \"changed_relations\": [\n{}\n  ]\n}}\n",
        json_string_array(&delta.added_objects),
        json_string_array(&delta.removed_objects),
        moved_objects,
        changed_relations
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
    let canvas_width = 700;
    let canvas_height = 500;
    let mut rgba = vec![255; (canvas_width * canvas_height * 4) as usize];

    for object in &scene.objects {
        match object.shape {
            Shape::Rectangle => draw_rectangle(
                &mut rgba,
                canvas_width,
                object.x,
                object.y,
                object.width.expect("rectangle width must exist"),
                object.height.expect("rectangle height must exist"),
            ),
            Shape::Circle => draw_circle(
                &mut rgba,
                canvas_width,
                object.x,
                object.y,
                object.radius.expect("circle radius must exist"),
            ),
        }
    }

    fs::write(
        output_path,
        encode_png_rgba(canvas_width, canvas_height, &rgba),
    )
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
