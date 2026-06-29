export interface SourceSpan {
  uri: string;
  start_line: number;
  start_column: number;
  end_line: number;
  end_column: number;
  start_offset?: number;
  end_offset?: number;
}

export type DiagnosticSeverity = "error" | "warning" | "hint" | "info";
export type DiagnosticPhase =
  | "parse" | "semantic" | "typecheck" | "lowering" | "ir"
  | "execution_plan" | "runtime" | "simulation" | "knowledge"
  | "analyzer" | "toolchain" | "lsp";

export interface DiagnosticRelatedInfo {
  span?: SourceSpan;
  message: string;
}

export interface PlatformDiagnostic {
  code?: string;
  severity: DiagnosticSeverity;
  message: string;
  stage?: string;
  source_range?: SourceSpan | null;
  span?: SourceSpan;
  source?: string;
  phase: DiagnosticPhase;
  related_information: DiagnosticRelatedInfo[];
  fix_suggestion?: string;
  metadata: unknown;
}

export interface ProjectWorkspaceMeta {
  root_uri?: string;
  project_name?: string;
}

// ---------------------------------------------------------------------------
// Workspace / File Tree
// ---------------------------------------------------------------------------

export type FileNodeKind = "file" | "directory" | "symlink" | "unknown";

export interface FileNode {
  name: string;
  path: string;
  relative_path: string;
  kind: FileNodeKind;
  extension?: string | null;
  children: FileNode[];
  is_ignored: boolean;
  metadata?: Record<string, unknown>;
}

export type WorkspaceScanStatus = "complete" | "partial" | "failed";

export interface WorkspaceState {
  schema_version: string;
  root_path: string;
  root_name: string;
  files: FileNode[];
  selected_path?: string | null;
  active_file_path?: string | null;
  ignored_patterns: string[];
  scan_status: WorkspaceScanStatus;
  metadata?: Record<string, unknown>;
}

export interface SourceFileState {
  uri: string;
  text: string;
  language_id: string;
}

export interface ProjectStateMetadata {
  compiler_mode: string;
  source_filename: string;
}

// ---------------------------------------------------------------------------
// Artifact selection model
// ---------------------------------------------------------------------------

export type ArtifactKind =
  | "diagnostic"
  | "surface_ast"
  | "semantic_ast"
  | "reason_ir"
  | "execution_plan"
  | "validation"
  | "dependency"
  | "analyzer"
  | "source";

export interface ArtifactSelection {
  kind: ArtifactKind;
  id: string;
  label?: string;
  span?: SourceSpan | null;
  relatedIds?: string[];
  /** "span" | "symbol_fallback" | "none" */
  navigation_mode?: string;
  metadata?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Typed Reason IR / ExecutionPlan shapes (best-effort, fields may be absent)
// ---------------------------------------------------------------------------

export interface ReasonIREffect {
  function?: string;
  return_path?: string;
  node_type?: string;
  [key: string]: unknown;
}

export interface ReasonIRTransition {
  transition_id?: string;
  effect?: ReasonIREffect;
  [key: string]: unknown;
}

export interface ReasonIR {
  schema_version?: string;
  goal?: unknown;
  transitions?: ReasonIRTransition[];
  [key: string]: unknown;
}

export interface ExecutionPlanStep {
  step_id?: string;
  transition_id?: string;
  source?: string;
  target?: string;
  [key: string]: unknown;
}

export interface ExecutionPlan {
  schema_version?: string;
  selected_steps?: ExecutionPlanStep[];
  goal?: string;
  reachable?: boolean;
  distance?: number;
  path_signature?: string;
  [key: string]: unknown;
}

export interface ProjectState {
  schema_version: string;
  compiler_version: string;
  workspace: ProjectWorkspaceMeta;
  source_files: SourceFileState[];
  surface_ast: unknown;
  semantic_ast: unknown;
  reason_ir: unknown;
  execution_plan: unknown;
  diagnostics: PlatformDiagnostic[];
  validation: unknown;
  analyzer: unknown;
  runtime_operations: unknown;
  simulation: unknown;
  knowledge: unknown;
  metadata: ProjectStateMetadata;
  generated_at: string;
}
