use crate::cli::Format;
use crate::commands::invoke_pipeline;
use crate::diagnostics::PlaygroundError;

/// TV-4: IR Validation
///
/// Compiles the source file through the full pipeline and displays
/// the resulting Reason IR document (schema_version: reason-ir/0.1).
pub fn run(source: &str, format: &Format) -> Result<(), PlaygroundError> {
    invoke_pipeline("ir", source, format)
}
