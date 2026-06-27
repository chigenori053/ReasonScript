use std::path::{Path, PathBuf};
use std::process::Command;

use crate::dto::{
    DiagnosticPhase, DiagnosticSeverity, IdeError, PlatformDiagnostic, ProjectState,
    ProjectStateMetadata, SourceFileState, WorkspaceState,
};

const MANIFEST_DIR: &str = env!("CARGO_MANIFEST_DIR");

// ---------------------------------------------------------------------------
// Repository root / environment helpers
// ---------------------------------------------------------------------------

fn resolve_repo_root() -> Result<PathBuf, IdeError> {
    let manifest = PathBuf::from(MANIFEST_DIR);
    manifest
        .parent()
        .and_then(|p| p.parent())
        .and_then(|p| p.parent())
        .map(|p| p.to_path_buf())
        .ok_or_else(|| {
            IdeError::Internal(
                "Failed to resolve ReasonScript repository root from CARGO_MANIFEST_DIR"
                    .to_string(),
            )
        })
}

fn build_pythonpath(repo_root: &Path) -> String {
    let root = repo_root.to_string_lossy().to_string();
    let existing = std::env::var("PYTHONPATH").unwrap_or_default();
    if existing.is_empty() {
        root
    } else {
        format!("{}:{}", root, existing)
    }
}

fn python_exe(repo: &Path) -> PathBuf {
    let candidates = [
        repo.join("playground/.venv/bin/python3"),
        repo.join("playground/.venv/bin/python"),
        repo.join(".venv/bin/python3"),
        repo.join(".venv/bin/python"),
        PathBuf::from("python3"),
        PathBuf::from("python"),
    ];
    for c in &candidates {
        if c.is_absolute() {
            if c.exists() {
                return c.clone();
            }
        } else {
            return c.clone();
        }
    }
    PathBuf::from("python3")
}

// ---------------------------------------------------------------------------
// Diagnostic construction helpers
// ---------------------------------------------------------------------------

pub fn diagnostic_from_pipeline_error(
    message: impl Into<String>,
    stderr: Option<String>,
) -> PlatformDiagnostic {
    PlatformDiagnostic {
        code: Some("PIPELINE-ERROR".to_string()),
        severity: DiagnosticSeverity::Error,
        message: message.into(),
        span: None,
        source: Some("compiler_bridge".to_string()),
        phase: DiagnosticPhase::Pipeline,
        related_information: vec![],
        fix_suggestion: None,
        metadata: serde_json::json!({ "stderr": stderr }),
    }
}

/// Extract an error code like CAL-020, FN-001, NS-002 from an error string.
fn extract_code(s: &str) -> Option<String> {
    let patterns = ["CAL-", "FN-", "NS-", "ST-", "RT-"];
    for pat in &patterns {
        if let Some(pos) = s.find(pat) {
            let rest = &s[pos..];
            let end = rest
                .find(|c: char| !c.is_alphanumeric() && c != '-')
                .unwrap_or(rest.len());
            return Some(rest[..end].to_string());
        }
    }
    None
}

/// Infer diagnostic phase from an error string's prefix or content.
fn infer_phase(s: &str) -> DiagnosticPhase {
    let lower = s.to_lowercase();
    if lower.contains("[parse]") || lower.starts_with("parse") {
        DiagnosticPhase::Parse
    } else if lower.contains("[semantic]") || lower.contains("semantic") {
        DiagnosticPhase::Semantic
    } else if lower.contains("type") || lower.contains("typecheck") {
        DiagnosticPhase::Typecheck
    } else if lower.contains("execution_plan") || lower.contains("executionplan") {
        DiagnosticPhase::ExecutionPlan
    } else if lower.contains("[compile]") || lower.contains("undefined") || lower.contains("cal-") {
        DiagnosticPhase::Semantic
    } else {
        DiagnosticPhase::Toolchain
    }
}

/// Remove leading `[Phase]` prefix and trim whitespace.
fn normalize_message(s: &str) -> String {
    let trimmed = s.trim();
    // Strip [Parse], [Semantic], [Compile] etc.
    if let Some(rest) = trimmed.strip_prefix('[') {
        if let Some(end) = rest.find(']') {
            return rest[end + 1..].trim().to_string();
        }
    }
    trimmed.to_string()
}

pub fn diagnostic_from_error_string(error: &str) -> PlatformDiagnostic {
    let code = extract_code(error);
    let phase = infer_phase(error);
    let message = normalize_message(error);

    PlatformDiagnostic {
        code: code.or(Some("COMPILER-ERROR".to_string())),
        severity: DiagnosticSeverity::Error,
        message,
        span: None,
        source: Some("compiler".to_string()),
        phase,
        related_information: vec![],
        fix_suggestion: None,
        metadata: serde_json::Value::Null,
    }
}

fn fallback_diagnostic() -> PlatformDiagnostic {
    PlatformDiagnostic {
        code: Some("COMPILER-ERROR".to_string()),
        severity: DiagnosticSeverity::Error,
        message: "Compiler failed without structured diagnostics.".to_string(),
        span: None,
        source: Some("compiler_bridge".to_string()),
        phase: DiagnosticPhase::Toolchain,
        related_information: vec![],
        fix_suggestion: None,
        metadata: serde_json::Value::Null,
    }
}

// ---------------------------------------------------------------------------
// ProjectState builder for error cases
// ---------------------------------------------------------------------------

fn project_state_with_diagnostics(
    source: &str,
    uri: &str,
    compiler_mode: &str,
    diagnostics: Vec<PlatformDiagnostic>,
    repo_root: Option<&Path>,
) -> ProjectState {
    ProjectState {
        schema_version: "project-state/0.1".to_string(),
        compiler_version: "0.1.0".to_string(),
        workspace: WorkspaceState {
            root_uri: repo_root.map(|p| p.to_string_lossy().to_string()),
            project_name: Some("playground".to_string()),
        },
        source_files: vec![SourceFileState {
            uri: uri.to_string(),
            text: source.to_string(),
            language_id: "reasonscript".to_string(),
        }],
        surface_ast: None,
        semantic_ast: None,
        reason_ir: None,
        execution_plan: None,
        diagnostics,
        validation: None,
        analyzer: None,
        runtime_operations: None,
        simulation: None,
        knowledge: None,
        metadata: ProjectStateMetadata {
            compiler_mode: compiler_mode.to_string(),
            source_filename: uri.to_string(),
        },
        generated_at: chrono_now(),
    }
}

// ---------------------------------------------------------------------------
// Diagnostic extraction from pipeline JSON output
// ---------------------------------------------------------------------------

fn pipeline_error_to_diagnostic(err: &serde_json::Value, uri: &str) -> PlatformDiagnostic {
    let message = err
        .get("message")
        .and_then(|v| v.as_str())
        .unwrap_or("Unknown error")
        .to_string();
    let phase_str = err.get("phase").and_then(|v| v.as_str()).unwrap_or("parse");
    let line = err.get("line").and_then(|v| v.as_u64()).map(|l| l as u32);
    let phase = match phase_str.to_lowercase().as_str() {
        "parse" => DiagnosticPhase::Parse,
        "semantic" | "validation" | "compile" => DiagnosticPhase::Semantic,
        "ir" => DiagnosticPhase::Ir,
        "execution_plan" => DiagnosticPhase::ExecutionPlan,
        "runtime" => DiagnosticPhase::Runtime,
        "simulation" => DiagnosticPhase::Simulation,
        "knowledge" => DiagnosticPhase::Knowledge,
        "analyzer" => DiagnosticPhase::Analyzer,
        _ => DiagnosticPhase::Parse,
    };
    let span = line.map(|l| crate::dto::SourceSpan {
        uri: uri.to_string(),
        start_line: l.saturating_sub(1),
        start_column: 0,
        end_line: l.saturating_sub(1),
        end_column: 0,
        start_offset: None,
        end_offset: None,
    });
    PlatformDiagnostic {
        code: extract_code(&message),
        severity: DiagnosticSeverity::Error,
        message: normalize_message(&message),
        span,
        source: Some("reasonscript".to_string()),
        phase,
        related_information: vec![],
        fix_suggestion: None,
        metadata: serde_json::Value::Null,
    }
}

fn extract_diagnostics_from_raw(raw: &serde_json::Value, uri: &str) -> Vec<PlatformDiagnostic> {
    // Prefer raw["errors"] array (legacy pipeline format)
    if let Some(errors) = raw.get("errors").and_then(|v| v.as_array()) {
        if !errors.is_empty() {
            return errors
                .iter()
                .map(|e| pipeline_error_to_diagnostic(e, uri))
                .collect();
        }
    }
    // Fallback: raw["error"] string
    if let Some(err_str) = raw.get("error").and_then(|v| v.as_str()) {
        if !err_str.is_empty() {
            return vec![diagnostic_from_error_string(err_str)];
        }
    }
    // Last resort
    vec![fallback_diagnostic()]
}

// ---------------------------------------------------------------------------
// Python pipeline script
// ---------------------------------------------------------------------------

const PIPELINE_SCRIPT: &str = r#"
import sys, json
from playground.backend.main import _run_pipeline_artifacts, SourceRequest

source = sys.stdin.read()
filename = sys.argv[1]
compiler_mode = sys.argv[2]

req = SourceRequest(source=source, filename=filename, compiler_mode=compiler_mode)
artifacts, errors = _run_pipeline_artifacts(req)

out = {
    "ok": not bool(errors),
    "errors": errors,
    "ast": artifacts.get("ast"),
    "semantic_ast": artifacts.get("semantic_ast"),
    "reason_ir": artifacts.get("reason_ir"),
    "execution_plan": artifacts.get("execution_plan"),
    "simulation": artifacts.get("simulation"),
    "knowledge": artifacts.get("knowledge"),
    "validation": artifacts.get("validation"),
}
print(json.dumps(out))
"#;

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

pub fn build_project_state_from_source(
    source: &str,
    uri: Option<&str>,
    compiler_mode: &str,
) -> Result<ProjectState, IdeError> {
    let repo_root = resolve_repo_root()?;
    let pythonpath = build_pythonpath(&repo_root);
    let python = python_exe(&repo_root);

    eprintln!("[ide] repo_root={}", repo_root.display());
    eprintln!("[ide] pythonpath={}", pythonpath);
    eprintln!("[ide] python={}", python.display());

    let uri_str = uri.unwrap_or("ide.rsn");

    let output = Command::new(&python)
        .current_dir(&repo_root)
        .env("PYTHONPATH", &pythonpath)
        .arg("-c")
        .arg(PIPELINE_SCRIPT)
        .arg(uri_str)
        .arg(compiler_mode)
        .stdin(std::process::Stdio::piped())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .and_then(|mut child| {
            use std::io::Write;
            if let Some(mut stdin) = child.stdin.take() {
                stdin.write_all(source.as_bytes())?;
            }
            child.wait_with_output()
        })
        .map_err(|e| IdeError::Pipeline(format!("Failed to spawn Python: {e}")))?;

    // Python process crashed or couldn't import → normalise to ProjectState with diagnostic
    if !output.status.success() && output.stdout.is_empty() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        eprintln!("[ide] python stderr:\n{}", stderr);
        let diag = diagnostic_from_pipeline_error(
            "Python pipeline failed while compiling ReasonScript source.",
            Some(stderr),
        );
        return Ok(project_state_with_diagnostics(
            source,
            uri_str,
            compiler_mode,
            vec![diag],
            Some(&repo_root),
        ));
    }

    // JSON parse failure → normalise
    let raw: serde_json::Value = match serde_json::from_slice(&output.stdout) {
        Ok(v) => v,
        Err(e) => {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            let diag = PlatformDiagnostic {
                code: Some("PROJECTSTATE-NORMALIZATION-ERROR".to_string()),
                severity: DiagnosticSeverity::Error,
                message: "Failed to normalize compiler output into ProjectState.".to_string(),
                span: None,
                source: Some("compiler_bridge".to_string()),
                phase: DiagnosticPhase::Pipeline,
                related_information: vec![],
                fix_suggestion: None,
                metadata: serde_json::json!({
                    "parse_error": e.to_string(),
                    "stderr": stderr,
                }),
            };
            return Ok(project_state_with_diagnostics(
                source, uri_str, compiler_mode, vec![diag], Some(&repo_root),
            ));
        }
    };

    let ok = raw.get("ok").and_then(|v| v.as_bool()).unwrap_or(false);

    // Compiler returned errors → extract diagnostics, still build ProjectState
    if !ok {
        let diagnostics = extract_diagnostics_from_raw(&raw, uri_str);
        // Include partial artifacts when available
        return Ok(ProjectState {
            schema_version: "project-state/0.1".to_string(),
            compiler_version: "0.1.0".to_string(),
            workspace: WorkspaceState {
                root_uri: Some(repo_root.to_string_lossy().to_string()),
                project_name: Some("playground".to_string()),
            },
            source_files: vec![SourceFileState {
                uri: uri_str.to_string(),
                text: source.to_string(),
                language_id: "reasonscript".to_string(),
            }],
            surface_ast: raw.get("ast").cloned(),
            semantic_ast: raw.get("semantic_ast").cloned(),
            reason_ir: raw.get("reason_ir").cloned(),
            execution_plan: raw.get("execution_plan").cloned(),
            diagnostics,
            validation: raw.get("validation").cloned(),
            analyzer: None,
            runtime_operations: None,
            simulation: raw.get("simulation").cloned(),
            knowledge: raw.get("knowledge").cloned(),
            metadata: ProjectStateMetadata {
                compiler_mode: compiler_mode.to_string(),
                source_filename: uri_str.to_string(),
            },
            generated_at: chrono_now(),
        });
    }

    // Success path
    let errors = raw
        .get("errors")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let diagnostics: Vec<PlatformDiagnostic> = errors
        .iter()
        .map(|e| pipeline_error_to_diagnostic(e, uri_str))
        .collect();

    Ok(ProjectState {
        schema_version: "project-state/0.1".to_string(),
        compiler_version: "0.1.0".to_string(),
        workspace: WorkspaceState {
            root_uri: Some(repo_root.to_string_lossy().to_string()),
            project_name: Some("playground".to_string()),
        },
        source_files: vec![SourceFileState {
            uri: uri_str.to_string(),
            text: source.to_string(),
            language_id: "reasonscript".to_string(),
        }],
        surface_ast: raw.get("ast").cloned(),
        semantic_ast: raw.get("semantic_ast").cloned(),
        reason_ir: raw.get("reason_ir").cloned(),
        execution_plan: raw.get("execution_plan").cloned(),
        diagnostics,
        validation: raw.get("validation").cloned(),
        analyzer: None,
        runtime_operations: None,
        simulation: raw.get("simulation").cloned(),
        knowledge: raw.get("knowledge").cloned(),
        metadata: ProjectStateMetadata {
            compiler_mode: compiler_mode.to_string(),
            source_filename: uri_str.to_string(),
        },
        generated_at: chrono_now(),
    })
}

fn chrono_now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let s = secs % 60;
    let m = (secs / 60) % 60;
    let h = (secs / 3600) % 24;
    let days = secs / 86400;
    let year = 1970 + days / 365;
    format!("{year}-01-01T{h:02}:{m:02}:{s:02}Z")
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn repo_root_ends_with_reasonscript() {
        let root = resolve_repo_root().expect("should resolve");
        let name = root.file_name().and_then(|n| n.to_str()).unwrap_or("");
        assert_eq!(
            name, "ReasonScript",
            "repo root should be 'ReasonScript', got: {}",
            root.display()
        );
    }

    #[test]
    fn build_pythonpath_includes_root() {
        let root = resolve_repo_root().unwrap();
        let path = build_pythonpath(&root);
        assert!(path.contains(root.to_str().unwrap()));
    }

    #[test]
    fn build_pythonpath_preserves_existing() {
        std::env::set_var("PYTHONPATH", "/some/existing/path");
        let root = resolve_repo_root().unwrap();
        let path = build_pythonpath(&root);
        assert!(path.contains(root.to_str().unwrap()));
        assert!(path.contains("/some/existing/path"));
        std::env::remove_var("PYTHONPATH");
    }

    #[test]
    fn diagnostic_from_pipeline_error_fields() {
        let d = diagnostic_from_pipeline_error(
            "Python pipeline failed.",
            Some("Traceback...".to_string()),
        );
        assert_eq!(d.code.as_deref(), Some("PIPELINE-ERROR"));
        assert!(matches!(d.severity, DiagnosticSeverity::Error));
        assert!(matches!(d.phase, DiagnosticPhase::Pipeline));
        assert_eq!(d.message, "Python pipeline failed.");
        assert!(d.metadata.get("stderr").is_some());
    }

    #[test]
    fn extract_code_cal() {
        assert_eq!(extract_code("[Parse] CAL-020 undefined variable"), Some("CAL-020".to_string()));
        assert_eq!(extract_code("FN-001 missing return"), Some("FN-001".to_string()));
        assert_eq!(extract_code("no code here"), None);
    }

    #[test]
    fn infer_phase_parse() {
        assert!(matches!(infer_phase("[Parse] something"), DiagnosticPhase::Parse));
        assert!(matches!(infer_phase("[Semantic] undefined"), DiagnosticPhase::Semantic));
        assert!(matches!(infer_phase("some unknown error"), DiagnosticPhase::Toolchain));
    }

    #[test]
    fn normalize_message_strips_prefix() {
        assert_eq!(normalize_message("[Parse] CAL-020 undefined"), "CAL-020 undefined");
        assert_eq!(normalize_message("plain error"), "plain error");
    }

    #[test]
    fn diagnostic_from_error_string_cal() {
        let d = diagnostic_from_error_string("[Parse] CAL-020 undefined variable: Unknown");
        assert_eq!(d.code.as_deref(), Some("CAL-020"));
        assert!(matches!(d.phase, DiagnosticPhase::Parse));
        assert_eq!(d.message, "CAL-020 undefined variable: Unknown");
    }

    #[test]
    fn project_state_with_diagnostics_preserves_source() {
        let root = resolve_repo_root().ok();
        let diag = fallback_diagnostic();
        let ps = project_state_with_diagnostics(
            "module Test {}",
            "test.rsn",
            "normal",
            vec![diag],
            root.as_deref(),
        );
        assert_eq!(ps.source_files[0].text, "module Test {}");
        assert_eq!(ps.diagnostics.len(), 1);
        assert_eq!(ps.schema_version, "project-state/0.1");
    }
}
