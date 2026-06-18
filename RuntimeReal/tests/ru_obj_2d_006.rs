use ndarray::array;
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
struct SceneNode {
    name: String,
    children: Vec<SceneNode>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct HierarchicalSceneGraph {
    root: SceneNode,
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
    violations: Vec<String>,
}

#[test]
fn ru_obj_2d_006_builds_hierarchical_scene_layout_from_containment() {
    let graph = build_hierarchy_graph();
    let hierarchy =
        build_hierarchy(&graph).expect("containment relations must produce hierarchy tree");
    let repeated_hierarchy = build_hierarchy(&graph).expect("hierarchy must be reproducible");
    assert_eq!(hierarchy, repeated_hierarchy);

    assert_eq!(hierarchy.root.name, "World");
    assert!(contains_path(&hierarchy.root, &["World", "House"]));
    assert!(contains_path(&hierarchy.root, &["World", "House", "RoomA"]));
    assert!(contains_path(&hierarchy.root, &["World", "House", "RoomB"]));
    assert!(contains_path(
        &hierarchy.root,
        &["World", "House", "RoomA", "Table"]
    ));
    assert!(contains_path(
        &hierarchy.root,
        &["World", "House", "RoomA", "Chair"]
    ));
    assert!(contains_path(
        &hierarchy.root,
        &["World", "House", "RoomB", "Bed"]
    ));

    let layout = layout_hierarchy(&hierarchy);
    let repeated_layout = layout_hierarchy(&hierarchy);
    assert_eq!(layout, repeated_layout);

    assert_eq!(
        layout.get("World"),
        Some(&Bounds {
            x: 500.0,
            y: 500.0,
            width: 800.0,
            height: 800.0
        })
    );
    assert_eq!(
        layout.get("House"),
        Some(&Bounds {
            x: 500.0,
            y: 500.0,
            width: 600.0,
            height: 600.0
        })
    );
    assert_eq!(
        layout.get("RoomA"),
        Some(&Bounds {
            x: 350.0,
            y: 500.0,
            width: 250.0,
            height: 250.0
        })
    );
    assert_eq!(
        layout.get("RoomB"),
        Some(&Bounds {
            x: 650.0,
            y: 500.0,
            width: 250.0,
            height: 250.0
        })
    );

    let report = validate_hierarchy_layout(&hierarchy, &layout);
    assert!(report.passed);
    assert!(report.violations.is_empty());

    assert!(build_hierarchy(&build_cycle_graph()).is_err());
    assert!(build_hierarchy(&build_recursive_cycle_graph()).is_err());
    assert!(build_hierarchy(&build_multiple_parent_graph()).is_err());

    let artifact_dir = Path::new("artifacts/ru_obj_2d_006");
    fs::create_dir_all(artifact_dir).expect("artifact directory must be created");
    fs::write(
        artifact_dir.join("hierarchy_scene.json"),
        hierarchy_scene_json(&hierarchy),
    )
    .expect("hierarchy_scene.json must be generated");
    fs::write(
        artifact_dir.join("hierarchy_layout.json"),
        hierarchy_layout_json(&layout),
    )
    .expect("hierarchy_layout.json must be generated");
    fs::write(
        artifact_dir.join("validation_report.json"),
        validation_report_json(&report),
    )
    .expect("validation_report.json must be generated");
    render_hierarchy_png(&layout, artifact_dir.join("hierarchy_scene.png").as_path())
        .expect("hierarchy_scene.png must be generated");

    for path in [
        "artifacts/ru_obj_2d_006/hierarchy_scene.json",
        "artifacts/ru_obj_2d_006/hierarchy_layout.json",
        "artifacts/ru_obj_2d_006/validation_report.json",
        "artifacts/ru_obj_2d_006/hierarchy_scene.png",
    ] {
        let bytes = fs::read(path).expect("artifact must be readable");
        assert!(bytes.len() > 20, "{path} must not be empty");
    }
}

fn build_hierarchy_graph() -> ReasonGraph {
    build_graph(vec![
        ("World", "contains", "House"),
        ("House", "contains", "RoomA"),
        ("House", "contains", "RoomB"),
        ("RoomA", "contains", "Table"),
        ("RoomA", "contains", "Chair"),
        ("RoomB", "contains", "Bed"),
    ])
}

fn build_cycle_graph() -> ReasonGraph {
    build_graph(vec![("A", "contains", "B"), ("B", "contains", "A")])
}

fn build_recursive_cycle_graph() -> ReasonGraph {
    build_graph(vec![
        ("A", "contains", "B"),
        ("B", "contains", "C"),
        ("C", "contains", "A"),
    ])
}

fn build_multiple_parent_graph() -> ReasonGraph {
    build_graph(vec![
        ("RoomA", "contains", "Table"),
        ("RoomB", "contains", "Table"),
    ])
}

fn build_graph(relations: Vec<(&str, &str, &str)>) -> ReasonGraph {
    let mut graph = ReasonGraph::new(GraphType::ReasonGraph);
    let mut nodes = HashMap::new();

    for (source, _, target) in &relations {
        for name in [*source, *target] {
            nodes
                .entry(name.to_string())
                .or_insert_with(|| add_object_node(&mut graph, name));
        }
    }

    for (source, relation, target) in relations {
        let source_id = *nodes.get(source).expect("source node must exist");
        let target_id = *nodes.get(target).expect("target node must exist");
        add_relation(&mut graph, source_id, target_id, relation);
    }

    graph
}

fn add_object_node(graph: &mut ReasonGraph, name: &str) -> Uuid {
    let state = State::new(
        StateType::Object,
        ReasonUnit::new(name, UnitType::Composite, array![0.0]),
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

fn build_hierarchy(graph: &ReasonGraph) -> Result<HierarchicalSceneGraph, String> {
    let containment = containment_edges(graph)?;
    let mut children_by_parent: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    let mut parent_by_child: BTreeMap<String, String> = BTreeMap::new();
    let mut all_nodes = BTreeSet::new();

    for (parent, child) in containment {
        all_nodes.insert(parent.clone());
        all_nodes.insert(child.clone());

        if let Some(existing_parent) = parent_by_child.insert(child.clone(), parent.clone()) {
            return Err(format!(
                "{child} has multiple parents: {existing_parent} and {parent}"
            ));
        }

        children_by_parent.entry(parent).or_default().insert(child);
    }

    let roots = all_nodes
        .iter()
        .filter(|node| !parent_by_child.contains_key(*node))
        .cloned()
        .collect::<Vec<_>>();
    if roots.len() != 1 {
        return Err(format!("expected exactly one root, got {}", roots.len()));
    }

    let mut visiting = BTreeSet::new();
    let mut visited = BTreeSet::new();
    let root = build_scene_node(&roots[0], &children_by_parent, &mut visiting, &mut visited)?;

    if visited.len() != all_nodes.len() {
        return Err("hierarchy contains unreachable or cyclic nodes".to_string());
    }

    Ok(HierarchicalSceneGraph { root })
}

fn containment_edges(graph: &ReasonGraph) -> Result<Vec<(String, String)>, String> {
    graph
        .edges
        .iter()
        .filter(|edge| edge.relation == RelationType::Spatial)
        .map(|edge| match relation_label(edge).as_str() {
            "contains" => Ok((
                object_name(graph, edge.source)?,
                object_name(graph, edge.target)?,
            )),
            "inside" => Ok((
                object_name(graph, edge.target)?,
                object_name(graph, edge.source)?,
            )),
            other => Err(format!("unsupported hierarchical relation: {other}")),
        })
        .collect()
}

fn build_scene_node(
    name: &str,
    children_by_parent: &BTreeMap<String, BTreeSet<String>>,
    visiting: &mut BTreeSet<String>,
    visited: &mut BTreeSet<String>,
) -> Result<SceneNode, String> {
    if !visiting.insert(name.to_string()) {
        return Err(format!("containment cycle detected at {name}"));
    }

    let mut children = Vec::new();
    if let Some(child_names) = children_by_parent.get(name) {
        for child_name in child_names {
            children.push(build_scene_node(
                child_name,
                children_by_parent,
                visiting,
                visited,
            )?);
        }
    }

    visiting.remove(name);
    visited.insert(name.to_string());
    Ok(SceneNode {
        name: name.to_string(),
        children,
    })
}

fn layout_hierarchy(hierarchy: &HierarchicalSceneGraph) -> BTreeMap<String, Bounds> {
    let mut layout = BTreeMap::new();
    let root_bounds = Bounds {
        x: 500.0,
        y: 500.0,
        width: 800.0,
        height: 800.0,
    };
    layout.insert(hierarchy.root.name.clone(), root_bounds);
    layout_children(&hierarchy.root, root_bounds, &mut layout);
    layout
}

fn layout_children(
    parent: &SceneNode,
    parent_bounds: Bounds,
    layout: &mut BTreeMap<String, Bounds>,
) {
    if parent.children.is_empty() {
        return;
    }

    let child_count = parent.children.len() as f32;
    for (index, child) in parent.children.iter().enumerate() {
        let child_bounds = child_bounds(parent_bounds, child_count, index as f32);
        layout.insert(child.name.clone(), child_bounds);
        layout_children(child, child_bounds, layout);
    }
}

fn child_bounds(parent: Bounds, child_count: f32, index: f32) -> Bounds {
    if child_count == 1.0 {
        return Bounds {
            x: parent.x,
            y: parent.y,
            width: parent.width * 0.75,
            height: parent.height * 0.75,
        };
    }

    let child_width = parent.width / child_count - 50.0;
    let child_height = parent.height * 0.416_666_66;
    let left = parent.x - parent.width / 2.0;
    let spacing = parent.width / child_count;
    Bounds {
        x: left + spacing * index + spacing / 2.0,
        y: parent.y,
        width: child_width,
        height: child_height,
    }
}

fn validate_hierarchy_layout(
    hierarchy: &HierarchicalSceneGraph,
    layout: &BTreeMap<String, Bounds>,
) -> ValidationReport {
    let mut violations = Vec::new();
    validate_node(&hierarchy.root, layout, &mut violations);

    ValidationReport {
        passed: violations.is_empty(),
        violations,
    }
}

fn validate_node(
    parent: &SceneNode,
    layout: &BTreeMap<String, Bounds>,
    violations: &mut Vec<String>,
) {
    let Some(parent_bounds) = layout.get(&parent.name) else {
        violations.push(format!("{} has no layout", parent.name));
        return;
    };

    for child in &parent.children {
        match layout.get(&child.name) {
            Some(child_bounds) if contains(parent_bounds, child_bounds) => {}
            Some(_) => violations.push(format!("{} is outside {}", child.name, parent.name)),
            None => violations.push(format!("{} has no layout", child.name)),
        }
    }

    for i in 0..parent.children.len() {
        for j in (i + 1)..parent.children.len() {
            let left = layout.get(&parent.children[i].name);
            let right = layout.get(&parent.children[j].name);
            if let (Some(left), Some(right)) = (left, right) {
                if overlaps(left, right) {
                    violations.push(format!(
                        "{} overlaps {}",
                        parent.children[i].name, parent.children[j].name
                    ));
                }
            }
        }
    }

    for child in &parent.children {
        validate_node(child, layout, violations);
    }
}

fn contains(parent: &Bounds, child: &Bounds) -> bool {
    child.x - child.width / 2.0 >= parent.x - parent.width / 2.0
        && child.x + child.width / 2.0 <= parent.x + parent.width / 2.0
        && child.y - child.height / 2.0 >= parent.y - parent.height / 2.0
        && child.y + child.height / 2.0 <= parent.y + parent.height / 2.0
}

fn overlaps(a: &Bounds, b: &Bounds) -> bool {
    a.x - a.width / 2.0 < b.x + b.width / 2.0
        && a.x + a.width / 2.0 > b.x - b.width / 2.0
        && a.y - a.height / 2.0 < b.y + b.height / 2.0
        && a.y + a.height / 2.0 > b.y - b.height / 2.0
}

fn contains_path(root: &SceneNode, path: &[&str]) -> bool {
    if path.is_empty() || root.name != path[0] {
        return false;
    }
    if path.len() == 1 {
        return true;
    }
    root.children
        .iter()
        .any(|child| contains_path(child, &path[1..]))
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

fn hierarchy_scene_json(hierarchy: &HierarchicalSceneGraph) -> String {
    format!(
        "{{\n  \"root\": {}\n}}\n",
        scene_node_json(&hierarchy.root, 1)
    )
}

fn scene_node_json(node: &SceneNode, indent: usize) -> String {
    let spaces = "  ".repeat(indent);
    if node.children.is_empty() {
        return format!("{{ \"name\": \"{}\", \"children\": [] }}", node.name);
    }

    let children = node
        .children
        .iter()
        .map(|child| format!("{}  {}", spaces, scene_node_json(child, indent + 1)))
        .collect::<Vec<_>>()
        .join(",\n");
    format!(
        "{{\n{}  \"name\": \"{}\",\n{}  \"children\": [\n{}\n{}  ]\n{}}}",
        spaces, node.name, spaces, children, spaces, spaces
    )
}

fn hierarchy_layout_json(layout: &BTreeMap<String, Bounds>) -> String {
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
        "{{\n  \"passed\": {},\n  \"violations\": {}\n}}\n",
        report.passed,
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

fn render_hierarchy_png(
    layout: &BTreeMap<String, Bounds>,
    output_path: &Path,
) -> std::io::Result<()> {
    let canvas_width = 1000;
    let canvas_height = 1000;
    let mut rgba = vec![255; (canvas_width * canvas_height * 4) as usize];

    for name in ["World", "House", "RoomA", "RoomB", "Table", "Chair", "Bed"] {
        if let Some(bounds) = layout.get(name) {
            draw_rectangle(&mut rgba, canvas_width, *bounds);
        }
    }

    fs::write(
        output_path,
        encode_png_rgba(canvas_width, canvas_height, &rgba),
    )
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
    if x >= canvas_width || y >= 1000 {
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
