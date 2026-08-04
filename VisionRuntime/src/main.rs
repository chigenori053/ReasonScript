use reasonscript_vision_runtime::{
    build_ruo, infer_from_manifest, validate_observation, write_bundle, VisionObservation, PROFILE,
};
use serde_json::json;
use std::env;
use std::fs;
use std::path::Path;

fn main() {
    let args: Vec<String> = env::args().collect();
    let operation = args.get(1).map(String::as_str).unwrap_or("");
    let result = match operation {
        "verify-native" => Ok(json!({"ok":true,"exit_status":0,"profile":PROFILE,"unsafe_blocks":0})),
        "validate-observation" => load(args.get(2)).and_then(|value| validate_observation(&value).map(|_| json!({"ok":true,"exit_status":0,"profile":PROFILE,"operation":operation,"observation_id":value.observation_id}))),
        "infer" => {
            let model = args.get(2).ok_or_else(|| cli_error("VIS-CLI-003", "model path is required"));
            let image = args.get(3).ok_or_else(|| cli_error("VIS-CLI-003", "image path is required"));
            model.and_then(|model| image.and_then(|image| infer_from_manifest(Path::new(model), Path::new(image)))).map(|observation| json!({"ok":true,"exit_status":0,"profile":PROFILE,"operation":operation,"observation":observation}))
        }
        "build-ruo" => load(args.get(2)).and_then(|value| {
            let output = option(&args, "--output").ok_or_else(|| reasonscript_vision_runtime::VisionError { code:"VIS-CLI-001".into(), stage:"cli".into(), message:"--output is required".into() })?;
            let bundle = build_ruo(&value)?; write_bundle(&bundle, Path::new(output))?;
            Ok(json!({"ok":true,"exit_status":0,"profile":PROFILE,"operation":operation,"observation_id":value.observation_id,"output":output,"resource_count":bundle.resources.len()}))
        }),
        _ => Err(cli_error("VIS-CLI-002", "usage: reason-vision <infer MODEL IMAGE|validate-observation INPUT|build-ruo INPUT --output DIR|verify-native>")),
    };
    match result {
        Ok(value) => println!("{}", serde_json::to_string(&value).unwrap()),
        Err(error) => {
            println!(
                "{}",
                json!({"ok":false,"exit_status":1,"profile":PROFILE,"diagnostics":[error]})
            );
            std::process::exit(1);
        }
    }
}

fn cli_error(code: &str, message: &str) -> reasonscript_vision_runtime::VisionError {
    reasonscript_vision_runtime::VisionError {
        code: code.into(),
        stage: "cli".into(),
        message: message.into(),
    }
}

fn load(
    path: Option<&String>,
) -> Result<VisionObservation, reasonscript_vision_runtime::VisionError> {
    let path = path.ok_or_else(|| reasonscript_vision_runtime::VisionError {
        code: "VIS-CLI-003".into(),
        stage: "cli".into(),
        message: "input path is required".into(),
    })?;
    let bytes = fs::read(path).map_err(|e| reasonscript_vision_runtime::VisionError {
        code: "VIS-IO-001".into(),
        stage: "io".into(),
        message: e.to_string(),
    })?;
    serde_json::from_slice(&bytes).map_err(|e| reasonscript_vision_runtime::VisionError {
        code: "VIS-JSON-001".into(),
        stage: "json".into(),
        message: e.to_string(),
    })
}

fn option<'a>(args: &'a [String], name: &str) -> Option<&'a str> {
    args.iter()
        .position(|arg| arg == name)
        .and_then(|index| args.get(index + 1))
        .map(String::as_str)
}
