pub mod ast;
pub mod ir;
pub mod parse;
pub mod semantic;
pub mod validate;

use crate::cli::Format;
use crate::diagnostics::PlaygroundError;
use std::path::Path;
use std::process::Command;

/// Invoke the Python pipeline script for a given stage.
///
/// The script is located at `<CARGO_MANIFEST_DIR>/scripts/pipeline.py`.
/// The repo root (parent of `CARGO_MANIFEST_DIR`) is set as the working
/// directory so that `from frontend.*` imports resolve correctly.
pub fn invoke_pipeline(
    stage: &str,
    source: &str,
    format: &Format,
) -> Result<(), PlaygroundError> {
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    let script = Path::new(manifest_dir).join("scripts").join("pipeline.py");
    let repo_root = Path::new(manifest_dir)
        .parent()
        .expect("CARGO_MANIFEST_DIR has no parent");
    let source_path = Path::new(source);
    let resolved_source = if source_path.is_absolute() {
        source_path.to_path_buf()
    } else {
        std::env::current_dir()
            .map_err(|e| PlaygroundError::RuntimeError(format!("failed to resolve cwd: {}", e)))?
            .join(source_path)
    };

    let output = Command::new("python3")
        .arg(&script)
        .arg(stage)
        .arg(&resolved_source)
        .arg("--format")
        .arg(format.as_str())
        .current_dir(repo_root)
        .output()
        .map_err(|e| PlaygroundError::RuntimeError(format!("failed to launch Python: {}", e)))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);

    if !stdout.is_empty() {
        print!("{}", stdout);
    }

    if output.status.success() {
        Ok(())
    } else {
        let details = if stderr.is_empty() {
            stdout.trim().to_string()
        } else {
            stderr.trim().to_string()
        };
        Err(PlaygroundError::PipelineFailure {
            stage: stage.to_string(),
            details,
        })
    }
}
