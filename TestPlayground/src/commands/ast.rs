use crate::cli::Format;
use crate::commands::invoke_pipeline;
use crate::diagnostics::PlaygroundError;

/// TV-2: AST Validation
///
/// Parses the source file and displays the resulting AST structure.
/// For Language Surface files this is the surface ProgramNode.
/// For Phase 2 files this is the semantic ModuleNode.
pub fn run(source: &str, format: &Format) -> Result<(), PlaygroundError> {
    invoke_pipeline("ast", source, format)
}
