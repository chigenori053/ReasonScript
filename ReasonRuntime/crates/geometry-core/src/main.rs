use reasonscript_geometry_runtime::{
    canonicalize, derive_relations, digest, execute_ru, execute_rus, from_visual, mirp_projection,
    GeometryState, ReasonStep, Tolerance,
};
use reasonscript_vision_runtime::{spatial::observe_spatial, VisionObservation};
use serde_json::{json, Value};
use std::{env, fs};
fn main() {
    let args: Vec<_> = env::args().collect();
    let output = run(&args);
    match output {
        Ok(v) => println!("{}", v),
        Err(e) => {
            println!(
                "{}",
                json!({"ok":false,"status":"ERROR","diagnostics":[{"code":"GEO-CLI-001","message":e}]})
            );
            std::process::exit(1)
        }
    }
}
fn run(args: &[String]) -> Result<Value, String> {
    let op = args.get(1).map(String::as_str).unwrap_or("");
    if op == "rus" {
        let state_path = args
            .get(2)
            .ok_or("usage: reason-geometry rus <geometry-state.json> <steps.json>")?;
        let steps_path = args
            .get(3)
            .ok_or("usage: reason-geometry rus <geometry-state.json> <steps.json>")?;
        let mut state: GeometryState =
            serde_json::from_slice(&fs::read(state_path).map_err(|e| e.to_string())?)
                .map_err(|e| e.to_string())?;
        canonicalize(&mut state)?;
        let steps: Vec<ReasonStep> =
            serde_json::from_slice(&fs::read(steps_path).map_err(|e| e.to_string())?)
                .map_err(|e| e.to_string())?;
        let (results, trace) = execute_rus(&state, &steps, &Tolerance::default())?;
        return Ok(
            json!({"ok":true,"results":results,"trace":trace,"mirp_delta":{"schema":"reasonscript-geometry-mirp-delta/1.0","source_state":state.state_id,"results":results,"provenance":trace.provenance}}),
        );
    }
    let path = args
        .get(2)
        .ok_or("usage: reason-geometry <run|observe> <vision-observation.json>")?;
    let input: VisionObservation =
        serde_json::from_slice(&fs::read(path).map_err(|e| e.to_string())?)
            .map_err(|e| e.to_string())?;
    let observation = observe_spatial(&input).map_err(|e| e.to_string())?;
    let vision_trace = json!({"task_id":observation.source_id,"runtime":"VISION","worker_id":"local","input_hash":digest(&input)?,"operations":[{"operation":"observe_spatial","object_count":observation.objects.len()}],"output_hash":digest(&observation)?,"provenance":observation.provenance,"status":"KNOWN"});
    if op == "observe" {
        return Ok(json!({"ok":true,"observation":observation,"trace":vision_trace}));
    }
    if op != "run" {
        return Err("unsupported operation".into());
    }
    let mut state = from_visual(&observation)?;
    derive_relations(&mut state, &Tolerance::default(), 100.0)?;
    let mirp = mirp_projection(&state);
    let mut steps = vec![];
    if state.primitives.len() >= 2 {
        let ids: Vec<_> = state
            .primitives
            .iter()
            .filter(|p| p.geometry_type == "Point")
            .map(|p| p.geometry_id.clone())
            .collect();
        if ids.len() >= 2 {
            let (r, t) = execute_ru(&state, "DistanceRU", &ids[..2], &Tolerance::default())?;
            steps.push(json!({"result":r,"trace":t}))
        }
    }
    let trace = json!({"task_id":state.state_id,"runtime":"GEOMETRY","worker_id":"local","input_hash":digest(&observation)?,"operations":[{"ru":"ObjectToGeometryRU","rus":["ObjectToGeometryRU","SpatialRelationRU"],"ruo":"from_visual"},{"ru":"SpatialRelationRU","ruo":"derive_relations"},{"ru":"MIRPProjectionRU","ruo":"mirp_projection"},{"calculation_steps":steps}],"output_hash":digest(&state)?,"provenance":state.provenance,"status":"KNOWN"});
    Ok(
        json!({"ok":true,"observation":observation,"vision_trace":vision_trace,"geometry_state":state,"mirp":mirp,"semantic_state":mirp,"trace":trace}),
    )
}
