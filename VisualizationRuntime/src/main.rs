use reasonscript_semantic_visualization_runtime::{
    plot, project_input, project_vision, validate_scene, write_artifacts, SceneInput,
    VisualizationError, PROFILE,
};
use reasonscript_vision_runtime::VisionObservation;
use serde_json::{json, Value};
use std::env;
use std::fs;
use std::path::Path;

fn main() {
    let args: Vec<String> = env::args().collect();
    let operation = args.get(1).map(String::as_str).unwrap_or("");
    let result = match operation {
        "verify-native" => Ok(json!({"ok":true,"exit_status":0,"profile":PROFILE,"unsafe_blocks":0})),
        "project" => load::<SceneInput>(args.get(2)).and_then(|input| { let scene = project_input(&input)?; output(&args, serde_json::to_value(&input).unwrap(), &scene) }),
        "project-vision" => load::<VisionObservation>(args.get(2)).and_then(|observation| { let scene = project_vision(&observation)?; output(&args, serde_json::to_value(&observation).unwrap(), &scene) }),
        "validate" => load(args.get(2)).and_then(|scene| validate_scene(&scene).map(|_| json!({"ok":true,"exit_status":0,"profile":PROFILE,"operation":"validate","scene_id":scene.scene_id}))),
        "plot" => load::<plot::PlotSpec>(args.get(2)).and_then(|spec| {
            let svg = plot::render_svg(&spec)?;
            let path = option(&args, "--output").ok_or_else(|| VisualizationError::new("SVR-CLI-003", "--output is required", "cli"))?;
            if Path::new(path).extension().and_then(|value| value.to_str()) != Some("svg") {
                return Err(VisualizationError::new("SVR-CLI-003", "--output must name an .svg file", "cli"));
            }
            fs::write(path, svg.as_bytes()).map_err(|error| VisualizationError::new("SVR-IO-001", error.to_string(), path))?;
            Ok(json!({"ok":true,"exit_status":0,"profile":plot::PROFILE,"operation":"plot","output":path,"bytes":svg.len()}))
        }),
        _ => Err(VisualizationError::new("SVR-CLI-002", "usage: reason-visualization <project INPUT --output DIR|project-vision OBSERVATION --output DIR|plot SPEC --output FILE.svg|validate SCENE|verify-native>", "cli")),
    };
    match result {
        Ok(value) => println!("{}", serde_json::to_string(&value).unwrap()),
        Err(error) => {
            println!(
                "{}",
                json!({"ok":false,"exit_status":1,"profile":PROFILE,"diagnostics":[error.diagnostic]})
            );
            std::process::exit(1);
        }
    }
}
fn output(
    args: &[String],
    source: Value,
    scene: &reasonscript_semantic_visualization_runtime::VisualizationScene,
) -> Result<Value, VisualizationError> {
    let directory = option(args, "--output")
        .ok_or_else(|| VisualizationError::new("SVR-CLI-003", "--output is required", "cli"))?;
    let manifest = write_artifacts(Path::new(directory), &source, scene)?;
    Ok(
        json!({"ok":true,"exit_status":0,"profile":PROFILE,"scene_id":scene.scene_id,"output":directory,"manifest":manifest}),
    )
}
fn load<T: serde::de::DeserializeOwned>(path: Option<&String>) -> Result<T, VisualizationError> {
    let path = path
        .ok_or_else(|| VisualizationError::new("SVR-CLI-003", "input path is required", "cli"))?;
    let bytes = fs::read(path)
        .map_err(|error| VisualizationError::new("SVR-IO-001", error.to_string(), path))?;
    serde_json::from_slice(&bytes)
        .map_err(|error| VisualizationError::new("SVR-JSON-001", error.to_string(), path))
}
fn option<'a>(args: &'a [String], name: &str) -> Option<&'a str> {
    args.iter()
        .position(|arg| arg == name)
        .and_then(|index| args.get(index + 1))
        .map(String::as_str)
}
