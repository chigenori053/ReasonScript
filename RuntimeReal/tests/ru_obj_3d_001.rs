use ndarray::array;
use reasonscript_runtime_real::core::transition::TransitionOp;
use reasonscript_runtime_real::core::types::{
    GraphType, RelationType, StateType, TransitionType, UnitType,
};
use reasonscript_runtime_real::core::{ReasonUnit, State, Transition};
use reasonscript_runtime_real::graph::{Edge, Node, ReasonGraph};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Position3D {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Rotation3D {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Scale3D {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Cube3D {
    pub position: Position3D,
    pub rotation: Rotation3D,
    pub scale: Scale3D,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Sphere3D {
    pub position: Position3D,
    pub radius: f32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Cylinder3D {
    pub position: Position3D,
    pub radius: f32,
    pub height: f32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum Object3D {
    Cube(Cube3D),
    Sphere(Sphere3D),
    Cylinder(Cylinder3D),
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Scene3D {
    pub objects: Vec<Object3D>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
struct ValidationCase {
    id: String,
    name: String,
    passed: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
struct FailureCondition {
    id: String,
    name: String,
    rejected: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
struct ValidationReport {
    specification: String,
    version: String,
    passed: bool,
    cases: Vec<ValidationCase>,
    failure_conditions: Vec<FailureCondition>,
    generated_artifacts: Vec<String>,
}

#[test]
fn ru_obj_3d_001_object_representation_validation() {
    let cube = Cube3D {
        position: Position3D {
            x: 0.0,
            y: 0.0,
            z: 0.0,
        },
        rotation: Rotation3D {
            x: 0.0,
            y: 0.0,
            z: 0.0,
        },
        scale: Scale3D {
            x: 1.0,
            y: 1.0,
            z: 1.0,
        },
    };
    let sphere = Sphere3D {
        position: Position3D {
            x: 3.0,
            y: 0.0,
            z: 0.0,
        },
        radius: 1.0,
    };
    let cylinder = Cylinder3D {
        position: Position3D {
            x: -3.0,
            y: 0.0,
            z: 0.0,
        },
        radius: 1.0,
        height: 2.0,
    };

    let cube_object = extract_object_3d(&build_cube_reason_unit_graph(&cube))
        .expect("ST-301 Cube3D must be generated");
    let sphere_object = extract_object_3d(&build_sphere_reason_unit_graph(&sphere))
        .expect("ST-302 Sphere3D must be generated");
    let cylinder_object = extract_object_3d(&build_cylinder_reason_unit_graph(&cylinder))
        .expect("ST-303 Cylinder3D must be generated");

    assert_eq!(cube_object, Object3D::Cube(cube.clone()));
    assert_eq!(sphere_object, Object3D::Sphere(sphere.clone()));
    assert_eq!(cylinder_object, Object3D::Cylinder(cylinder.clone()));
    validate_object_3d(&cube_object).expect("cube constraints must pass");
    validate_object_3d(&sphere_object).expect("sphere constraints must pass");
    validate_object_3d(&cylinder_object).expect("cylinder constraints must pass");

    let cube_json = object_json(&cube_object);
    let sphere_json = object_json(&sphere_object);
    let cylinder_json = object_json(&cylinder_object);
    assert_eq!(
        serde_json::from_str::<Object3D>(&cube_json).expect("cube JSON must restore"),
        cube_object
    );
    assert_eq!(
        serde_json::from_str::<Object3D>(&sphere_json).expect("sphere JSON must restore"),
        sphere_object
    );
    assert_eq!(
        serde_json::from_str::<Object3D>(&cylinder_json).expect("cylinder JSON must restore"),
        cylinder_object
    );

    let scene = Scene3D {
        objects: vec![
            cube_object.clone(),
            sphere_object.clone(),
            cylinder_object.clone(),
        ],
    };
    validate_scene_3d(&scene).expect("ST-305 Scene3D must validate");
    let scene3d_json = scene_json(&scene);
    assert_eq!(
        serde_json::from_str::<Scene3D>(&scene3d_json).expect("scene JSON must restore"),
        scene
    );

    assert!(validate_object_3d(&Object3D::Sphere(Sphere3D {
        position: Position3D {
            x: 0.0,
            y: 0.0,
            z: 0.0
        },
        radius: 0.0,
    }))
    .is_err());
    assert!(validate_object_3d(&Object3D::Cylinder(Cylinder3D {
        position: Position3D {
            x: 0.0,
            y: 0.0,
            z: 0.0
        },
        radius: 1.0,
        height: 0.0,
    }))
    .is_err());
    assert!(validate_object_3d(&Object3D::Cube(Cube3D {
        position: Position3D {
            x: 0.0,
            y: 0.0,
            z: 0.0
        },
        rotation: Rotation3D {
            x: 0.0,
            y: 0.0,
            z: 0.0
        },
        scale: Scale3D {
            x: 1.0,
            y: -1.0,
            z: 1.0
        },
    }))
    .is_err());
    assert!(extract_object_3d(&build_cube_without_position_graph(&cube)).is_err());

    for _ in 0..100 {
        assert_eq!(cube_json, object_json(&cube_object));
        assert_eq!(sphere_json, object_json(&sphere_object));
        assert_eq!(cylinder_json, object_json(&cylinder_object));
        assert_eq!(scene3d_json, scene_json(&scene));
    }

    let scene_png = render_scene_png(&scene);
    assert!(scene_png.len() > 20, "ST-308 scene.png must be non-empty");

    let artifact_dir = Path::new("artifacts/ru_obj_3d_001");
    fs::create_dir_all(artifact_dir).expect("artifact directory must be created");
    fs::write(artifact_dir.join("cube.json"), &cube_json).expect("cube.json");
    fs::write(artifact_dir.join("sphere.json"), &sphere_json).expect("sphere.json");
    fs::write(artifact_dir.join("cylinder.json"), &cylinder_json).expect("cylinder.json");
    fs::write(artifact_dir.join("scene3d.json"), &scene3d_json).expect("scene3d.json");

    let report = ValidationReport {
        specification: "RU-OBJ-3D-001".to_string(),
        version: "runtime-real-validation/0.1".to_string(),
        passed: true,
        cases: vec![
            case("ST-301", "Cube Creation"),
            case("ST-302", "Sphere Creation"),
            case("ST-303", "Cylinder Creation"),
            case("ST-304", "Object3D IR Serialization"),
            case("ST-305", "Scene3D Generation"),
            case("ST-306", "Validation Constraints"),
            case("ST-307", "Deterministic Serialization"),
            case("ST-308", "Renderable Scene"),
        ],
        failure_conditions: vec![
            failure("FC-301", "Invalid Radius"),
            failure("FC-302", "Invalid Height"),
            failure("FC-303", "Invalid Scale"),
            failure("FC-304", "Missing Transform"),
        ],
        generated_artifacts: vec![
            "cube.json".to_string(),
            "sphere.json".to_string(),
            "cylinder.json".to_string(),
            "scene3d.json".to_string(),
            "validation_report.json".to_string(),
            "scene.png".to_string(),
        ],
    };
    fs::write(
        artifact_dir.join("validation_report.json"),
        serde_json::to_string_pretty(&report).expect("report must serialize") + "\n",
    )
    .expect("validation_report.json");
    fs::write(artifact_dir.join("scene.png"), scene_png).expect("scene.png");

    for file in report.generated_artifacts {
        let path = artifact_dir.join(file);
        let bytes = fs::read(&path).expect("artifact must be readable");
        assert!(bytes.len() > 20, "{} must not be empty", path.display());
    }
}

fn validate_scene_3d(scene: &Scene3D) -> Result<(), String> {
    if scene.objects.is_empty() {
        return Err("Scene3D must contain at least one Object3D".to_string());
    }
    for object in &scene.objects {
        validate_object_3d(object)?;
    }
    Ok(())
}

fn validate_object_3d(object: &Object3D) -> Result<(), String> {
    match object {
        Object3D::Cube(cube) => {
            if cube.scale.x <= 0.0 || cube.scale.y <= 0.0 || cube.scale.z <= 0.0 {
                Err("cube scale must be positive on all axes".to_string())
            } else {
                Ok(())
            }
        }
        Object3D::Sphere(sphere) => {
            if sphere.radius <= 0.0 {
                Err("sphere radius must be positive".to_string())
            } else {
                Ok(())
            }
        }
        Object3D::Cylinder(cylinder) => {
            if cylinder.radius <= 0.0 {
                Err("cylinder radius must be positive".to_string())
            } else if cylinder.height <= 0.0 {
                Err("cylinder height must be positive".to_string())
            } else {
                Ok(())
            }
        }
    }
}

fn build_cube_reason_unit_graph(cube: &Cube3D) -> ReasonGraph {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);
    let cube_id = add_node(&mut graph, "Cube", StateType::Object);
    add_component(
        &mut graph,
        cube_id,
        "has_position",
        &format_vec3(
            "Position3D",
            cube.position.x,
            cube.position.y,
            cube.position.z,
        ),
    );
    add_component(
        &mut graph,
        cube_id,
        "has_rotation",
        &format_vec3(
            "Rotation3D",
            cube.rotation.x,
            cube.rotation.y,
            cube.rotation.z,
        ),
    );
    add_component(
        &mut graph,
        cube_id,
        "has_scale",
        &format_vec3("Scale3D", cube.scale.x, cube.scale.y, cube.scale.z),
    );
    graph
}

fn build_cube_without_position_graph(cube: &Cube3D) -> ReasonGraph {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);
    let cube_id = add_node(&mut graph, "Cube", StateType::Object);
    add_component(
        &mut graph,
        cube_id,
        "has_rotation",
        &format_vec3(
            "Rotation3D",
            cube.rotation.x,
            cube.rotation.y,
            cube.rotation.z,
        ),
    );
    add_component(
        &mut graph,
        cube_id,
        "has_scale",
        &format_vec3("Scale3D", cube.scale.x, cube.scale.y, cube.scale.z),
    );
    graph
}

fn build_sphere_reason_unit_graph(sphere: &Sphere3D) -> ReasonGraph {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);
    let sphere_id = add_node(&mut graph, "Sphere", StateType::Object);
    add_component(
        &mut graph,
        sphere_id,
        "has_position",
        &format_vec3(
            "Position3D",
            sphere.position.x,
            sphere.position.y,
            sphere.position.z,
        ),
    );
    add_component(
        &mut graph,
        sphere_id,
        "has_radius",
        &format_scalar("Radius", sphere.radius),
    );
    graph
}

fn build_cylinder_reason_unit_graph(cylinder: &Cylinder3D) -> ReasonGraph {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);
    let cylinder_id = add_node(&mut graph, "Cylinder", StateType::Object);
    add_component(
        &mut graph,
        cylinder_id,
        "has_position",
        &format_vec3(
            "Position3D",
            cylinder.position.x,
            cylinder.position.y,
            cylinder.position.z,
        ),
    );
    add_component(
        &mut graph,
        cylinder_id,
        "has_radius",
        &format_scalar("Radius", cylinder.radius),
    );
    add_component(
        &mut graph,
        cylinder_id,
        "has_height",
        &format_scalar("Height", cylinder.height),
    );
    graph
}

fn add_component(graph: &mut ReasonGraph, source: Uuid, relation: &str, label: &str) {
    let component_id = add_node(graph, label, StateType::Attribute);
    add_relation(graph, source, component_id, relation);
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
    let unit = ReasonUnit::new(relation_label, UnitType::Symbolic, array![1.0]);
    let transition = Transition::new(TransitionType::Deduction, TransitionOp::Subsumption(unit));
    graph.add_edge(Edge::new(source, target, RelationType::Spatial, transition));
}

fn extract_object_3d(graph: &ReasonGraph) -> Result<Object3D, String> {
    let (root_id, root_label) = graph
        .nodes
        .keys()
        .find_map(|id| {
            let label = node_label(graph, *id).ok()?;
            matches!(label.as_str(), "Cube" | "Sphere" | "Cylinder").then_some((*id, label))
        })
        .ok_or_else(|| "3D object ReasonUnit is missing".to_string())?;

    match root_label.as_str() {
        "Cube" => Ok(Object3D::Cube(Cube3D {
            position: parse_vec3(&required_component(graph, root_id, "has_position")?)?,
            rotation: parse_rotation3d(&required_component(graph, root_id, "has_rotation")?)?,
            scale: parse_scale3d(&required_component(graph, root_id, "has_scale")?)?,
        })),
        "Sphere" => Ok(Object3D::Sphere(Sphere3D {
            position: parse_vec3(&required_component(graph, root_id, "has_position")?)?,
            radius: parse_scalar(&required_component(graph, root_id, "has_radius")?)?,
        })),
        "Cylinder" => Ok(Object3D::Cylinder(Cylinder3D {
            position: parse_vec3(&required_component(graph, root_id, "has_position")?)?,
            radius: parse_scalar(&required_component(graph, root_id, "has_radius")?)?,
            height: parse_scalar(&required_component(graph, root_id, "has_height")?)?,
        })),
        _ => Err("unsupported 3D object ReasonUnit".to_string()),
    }
}

fn required_component(graph: &ReasonGraph, source: Uuid, relation: &str) -> Result<String, String> {
    graph
        .edges
        .iter()
        .find(|edge| edge.source == source && edge_label(edge) == relation)
        .map(|edge| node_label(graph, edge.target))
        .transpose()?
        .ok_or_else(|| format!("{relation} component is missing"))
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

fn format_vec3(kind: &str, x: f32, y: f32, z: f32) -> String {
    format!("{kind}:x={x};y={y};z={z}")
}

fn format_scalar(kind: &str, value: f32) -> String {
    format!("{kind}:value={value}")
}

fn parse_vec3(label: &str) -> Result<Position3D, String> {
    let (_, body) = label
        .split_once(':')
        .ok_or_else(|| format!("invalid Vec3 component: {label}"))?;
    let mut x = None;
    let mut y = None;
    let mut z = None;
    for part in body.split(';') {
        let (key, value) = part
            .split_once('=')
            .ok_or_else(|| format!("invalid Vec3 field: {part}"))?;
        let parsed = value
            .parse::<f32>()
            .map_err(|_| format!("invalid float: {value}"))?;
        match key {
            "x" => x = Some(parsed),
            "y" => y = Some(parsed),
            "z" => z = Some(parsed),
            _ => return Err(format!("unsupported Vec3 field: {key}")),
        }
    }
    Ok(Position3D {
        x: x.ok_or_else(|| "x is missing".to_string())?,
        y: y.ok_or_else(|| "y is missing".to_string())?,
        z: z.ok_or_else(|| "z is missing".to_string())?,
    })
}

fn parse_rotation3d(label: &str) -> Result<Rotation3D, String> {
    let value = parse_vec3(label)?;
    Ok(Rotation3D {
        x: value.x,
        y: value.y,
        z: value.z,
    })
}

fn parse_scale3d(label: &str) -> Result<Scale3D, String> {
    let value = parse_vec3(label)?;
    Ok(Scale3D {
        x: value.x,
        y: value.y,
        z: value.z,
    })
}

fn parse_scalar(label: &str) -> Result<f32, String> {
    let (_, body) = label
        .split_once(':')
        .ok_or_else(|| format!("invalid scalar component: {label}"))?;
    let (_, value) = body
        .split_once('=')
        .ok_or_else(|| format!("invalid scalar field: {body}"))?;
    value
        .parse::<f32>()
        .map_err(|_| format!("invalid float: {value}"))
}

fn object_json(object: &Object3D) -> String {
    serde_json::to_string_pretty(object).expect("Object3D must serialize") + "\n"
}

fn scene_json(scene: &Scene3D) -> String {
    serde_json::to_string_pretty(scene).expect("Scene3D must serialize") + "\n"
}

fn case(id: &str, name: &str) -> ValidationCase {
    ValidationCase {
        id: id.to_string(),
        name: name.to_string(),
        passed: true,
    }
}

fn failure(id: &str, name: &str) -> FailureCondition {
    FailureCondition {
        id: id.to_string(),
        name: name.to_string(),
        rejected: true,
    }
}

fn render_scene_png(scene: &Scene3D) -> Vec<u8> {
    let width = 900u32;
    let height = 560u32;
    let mut rgba = vec![248u8; (width * height * 4) as usize];
    for px in rgba.chunks_exact_mut(4) {
        px[1] = 250;
        px[2] = 252;
        px[3] = 255;
    }
    draw_grid(&mut rgba, width, height);
    for object in &scene.objects {
        match object {
            Object3D::Cube(cube) => draw_cube(&mut rgba, width, height, cube),
            Object3D::Sphere(sphere) => draw_sphere(&mut rgba, width, height, sphere),
            Object3D::Cylinder(cylinder) => draw_cylinder(&mut rgba, width, height, cylinder),
        }
    }
    encode_png_rgba(width, height, &rgba)
}

fn project(position: Position3D) -> (i32, i32) {
    let origin_x = 450.0;
    let origin_y = 320.0;
    let sx = origin_x + position.x * 82.0 - position.z * 48.0;
    let sy = origin_y - position.y * 82.0 + position.z * 34.0;
    (sx.round() as i32, sy.round() as i32)
}

fn draw_grid(rgba: &mut [u8], width: u32, height: u32) {
    for x in (90..=810).step_by(90) {
        draw_line(rgba, width, height, x, 455, 450, 190, [212, 220, 225, 255]);
        draw_line(rgba, width, height, x, 455, 450, 520, [226, 232, 236, 255]);
    }
}

fn draw_cube(rgba: &mut [u8], width: u32, height: u32, cube: &Cube3D) {
    let center = cube.position;
    let sx = cube.scale.x * 35.0;
    let sy = cube.scale.y * 35.0;
    let sz = cube.scale.z * 35.0;
    let (cx, cy) = project(center);
    let dx = (sx, 0.0);
    let dy = (0.0, -sy);
    let dz = (-sz * 0.58, sz * 0.42);
    let p = |x: f32, y: f32| (cx + x.round() as i32, cy + y.round() as i32);
    let vertices = [
        p(-dx.0 + dz.0, -dx.1 + dz.1),
        p(dx.0 + dz.0, dx.1 + dz.1),
        p(dx.0 - dz.0, dx.1 - dz.1),
        p(-dx.0 - dz.0, -dx.1 - dz.1),
        p(-dx.0 + dy.0 + dz.0, -dx.1 + dy.1 + dz.1),
        p(dx.0 + dy.0 + dz.0, dx.1 + dy.1 + dz.1),
        p(dx.0 + dy.0 - dz.0, dx.1 + dy.1 - dz.1),
        p(-dx.0 + dy.0 - dz.0, -dx.1 + dy.1 - dz.1),
    ];
    let color = [42, 94, 155, 255];
    for (a, b) in [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ] {
        draw_line(
            rgba,
            width,
            height,
            vertices[a].0,
            vertices[a].1,
            vertices[b].0,
            vertices[b].1,
            color,
        );
    }
}

fn draw_sphere(rgba: &mut [u8], width: u32, height: u32, sphere: &Sphere3D) {
    let (cx, cy) = project(sphere.position);
    let radius = (sphere.radius * 38.0).round() as i32;
    draw_circle_outline(rgba, width, height, cx, cy, radius, [36, 132, 91, 255]);
    draw_circle_outline(
        rgba,
        width,
        height,
        cx,
        cy,
        (radius as f32 * 0.58) as i32,
        [76, 166, 120, 255],
    );
}

fn draw_cylinder(rgba: &mut [u8], width: u32, height: u32, cylinder: &Cylinder3D) {
    let (cx, cy) = project(cylinder.position);
    let rx = (cylinder.radius * 38.0).round() as i32;
    let ry = (cylinder.radius * 14.0).round() as i32;
    let top_y = cy - (cylinder.height * 42.0).round() as i32;
    let color = [160, 82, 45, 255];
    draw_ellipse_outline(rgba, width, height, cx, top_y, rx, ry, color);
    draw_ellipse_outline(rgba, width, height, cx, cy, rx, ry, [190, 116, 74, 255]);
    draw_line(rgba, width, height, cx - rx, top_y, cx - rx, cy, color);
    draw_line(rgba, width, height, cx + rx, top_y, cx + rx, cy, color);
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

fn draw_ellipse_outline(
    rgba: &mut [u8],
    width: u32,
    height: u32,
    cx: i32,
    cy: i32,
    rx: i32,
    ry: i32,
    color: [u8; 4],
) {
    for deg in 0..360 {
        let theta = (deg as f32).to_radians();
        let x = cx + (theta.cos() * rx as f32).round() as i32;
        let y = cy + (theta.sin() * ry as f32).round() as i32;
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
