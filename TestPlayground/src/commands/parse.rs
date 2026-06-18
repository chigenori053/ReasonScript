use crate::cli::Format;
use crate::commands::invoke_pipeline;
use crate::diagnostics::PlaygroundError;

/// TV-1: Parse Validation
///
/// Runs the source file through the ReasonScript parser and reports
/// whether syntax analysis succeeded or failed.
pub fn run(source: &str, format: &Format) -> Result<(), PlaygroundError> {
    invoke_pipeline("parse", source, format)
}
