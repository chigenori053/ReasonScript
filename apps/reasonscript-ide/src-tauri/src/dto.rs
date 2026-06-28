use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Source location
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Diagnostics
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// ProjectState
// ---------------------------------------------------------------------------

/// Lightweight workspace reference embedded in ProjectState.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectWorkspaceMeta {
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
    pub workspace: ProjectWorkspaceMeta,
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

// ---------------------------------------------------------------------------
// Workspace / File Tree
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FileNodeKind {
    File,
    Directory,
    Symlink,
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileNode {
    pub name: String,
    pub path: String,
    pub relative_path: String,
    pub kind: FileNodeKind,
    pub extension: Option<String>,
    pub children: Vec<FileNode>,
    pub is_ignored: bool,
    pub metadata: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WorkspaceScanStatus {
    Complete,
    Partial,
    Failed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceState {
    pub schema_version: String,
    pub root_path: String,
    pub root_name: String,
    pub files: Vec<FileNode>,
    pub selected_path: Option<String>,
    pub active_file_path: Option<String>,
    pub ignored_patterns: Vec<String>,
    pub scan_status: WorkspaceScanStatus,
    pub metadata: serde_json::Value,
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

#[derive(Debug, thiserror::Error)]
pub enum IdeError {
    #[allow(dead_code)]
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
    #[error("Workspace error: {0}")]
    Workspace(String),
}

impl Serialize for IdeError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(&self.to_string())
    }
}
