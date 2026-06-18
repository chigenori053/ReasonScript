use crate::cli::Format;
use crate::commands::invoke_pipeline;
use crate::diagnostics::PlaygroundError;

/// TV-3: Semantic AST Validation
///
/// Parses the source file and displays the Semantic AST (ModuleNode).
/// For Language Surface files this is the result of projecting the surface
/// ProgramNode into the semantic layer. For Phase 2 files the parser
/// produces the semantic ModuleNode directly.
pub fn run(source: &str, format: &Format) -> Result<(), PlaygroundError> {
    invoke_pipeline("semantic", source, format)
}
