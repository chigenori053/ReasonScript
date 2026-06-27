use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SourceSpan {
    pub uri: String,
    pub start_line: u32,
    pub start_column: u32,
    pub end_line: u32,
    pub end_column: u32,
    pub start_offset: Option<u32>,
    pub end_offset: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum DiagnosticSeverity {
    Error,
    Warning,
    Hint,
    Info,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum DiagnosticPhase {
    Parse,
    Semantic,
    Typecheck,
    Lowering,
    Ir,
    #[serde(rename = "execution_plan")]
    ExecutionPlan,
    Runtime,
    Simulation,
    Knowledge,
    Analyzer,
    Toolchain,
    Lsp,
    Pipeline,
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiagnosticRelatedInfo {
    pub span: Option<SourceSpan>,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlatformDiagnostic {
    pub code: Option<String>,
    pub severity: DiagnosticSeverity,
    pub message: String,
    pub span: Option<SourceSpan>,
    pub source: Option<String>,
    pub phase: DiagnosticPhase,
    pub related_information: Vec<DiagnosticRelatedInfo>,
    pub fix_suggestion: Option<String>,
    pub metadata: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceState {
    pub root_uri: Option<String>,
    pub project_name: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SourceFileState {
    pub uri: String,
    pub text: String,
    pub language_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectStateMetadata {
    pub compiler_mode: String,
    pub source_filename: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectState {
    pub schema_version: String,
    pub compiler_version: String,
    pub workspace: WorkspaceState,
    pub source_files: Vec<SourceFileState>,
    pub surface_ast: Option<serde_json::Value>,
    pub semantic_ast: Option<serde_json::Value>,
    pub reason_ir: Option<serde_json::Value>,
    pub execution_plan: Option<serde_json::Value>,
    pub diagnostics: Vec<PlatformDiagnostic>,
    pub validation: Option<serde_json::Value>,
    pub analyzer: Option<serde_json::Value>,
    pub runtime_operations: Option<serde_json::Value>,
    pub simulation: Option<serde_json::Value>,
    pub knowledge: Option<serde_json::Value>,
    pub metadata: ProjectStateMetadata,
    pub generated_at: String,
}

#[derive(Debug, thiserror::Error)]
pub enum IdeError {
    #[error("Compiler error: {0}")]
    Compiler(String),
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("Pipeline error: {0}")]
    Pipeline(String),
    #[error("Internal error: {0}")]
    Internal(String),
}

impl Serialize for IdeError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(&self.to_string())
    }
}
