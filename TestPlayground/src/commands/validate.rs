use crate::cli::Format;
use crate::commands::invoke_pipeline;
use crate::diagnostics::PlaygroundError;

/// TV-5: Round Trip Validation
///
/// Runs the source file through all pipeline stages (parse → AST → Semantic
/// AST → Reason IR) and reports the result of each validation check.
/// Also verifies IR schema conformance.
pub fn run(source: &str, format: &Format) -> Result<(), PlaygroundError> {
    invoke_pipeline("validate", source, format)
}
