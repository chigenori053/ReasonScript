#[cfg(test)]
mod tests {
    use crate::dto::*;
    use serde_json;

    #[test]
    fn source_span_serialization() {
        let span = SourceSpan {
            uri: "ide.rsn".to_string(),
            start_line: 0,
            start_column: 0,
            end_line: 0,
            end_column: 10,
            start_offset: Some(0),
            end_offset: Some(10),
        };
        let json = serde_json::to_string(&span).unwrap();
        let back: SourceSpan = serde_json::from_str(&json).unwrap();
        assert_eq!(back.uri, "ide.rsn");
        assert_eq!(back.end_column, 10);
    }

    #[test]
    fn platform_diagnostic_serialization() {
        let diag = PlatformDiagnostic {
            code: Some("E001".to_string()),
            severity: DiagnosticSeverity::Error,
            message: "Unexpected token".to_string(),
            span: Some(SourceSpan {
                uri: "ide.rsn".to_string(),
                start_line: 3,
                start_column: 0,
                end_line: 3,
                end_column: 5,
                start_offset: None,
                end_offset: None,
            }),
            source: Some("reasonscript".to_string()),
            phase: DiagnosticPhase::Parse,
            related_information: vec![],
            fix_suggestion: None,
            metadata: serde_json::Value::Null,
        };
        let json = serde_json::to_string_pretty(&diag).unwrap();
        assert!(json.contains("\"severity\": \"error\""));
        assert!(json.contains("\"phase\": \"parse\""));
        assert!(json.contains("E001"));
        let back: PlatformDiagnostic = serde_json::from_str(&json).unwrap();
        assert_eq!(back.message, "Unexpected token");
    }

    #[test]
    fn project_state_serialization() {
        let state = ProjectState {
            schema_version: "project-state/0.1".to_string(),
            compiler_version: "0.1.0".to_string(),
            workspace: ProjectWorkspaceMeta {
                root_uri: None,
                project_name: Some("test".to_string()),
            },
            source_files: vec![SourceFileState {
                uri: "test.rsn".to_string(),
                text: "module Test {}".to_string(),
                language_id: "reasonscript".to_string(),
            }],
            surface_ast: None,
            semantic_ast: None,
            reason_ir: None,
            execution_plan: None,
            diagnostics: vec![],
            validation: None,
            analyzer: None,
            runtime_operations: None,
            simulation: None,
            knowledge: None,
            metadata: ProjectStateMetadata {
                compiler_mode: "normal".to_string(),
                source_filename: "test.rsn".to_string(),
            },
            generated_at: "2026-01-01T00:00:00Z".to_string(),
        };
        let json = serde_json::to_string_pretty(&state).unwrap();
        assert!(json.contains("\"schema_version\": \"project-state/0.1\""));
        assert!(json.contains("\"compiler_version\": \"0.1.0\""));
        let back: ProjectState = serde_json::from_str(&json).unwrap();
        assert_eq!(back.schema_version, "project-state/0.1");
        assert!(back.diagnostics.is_empty());
    }

    #[test]
    fn project_state_schema_version_present() {
        let state = ProjectState {
            schema_version: "project-state/0.1".to_string(),
            compiler_version: "0.1.0".to_string(),
            workspace: ProjectWorkspaceMeta { root_uri: None, project_name: None },
            source_files: vec![],
            surface_ast: None,
            semantic_ast: None,
            reason_ir: None,
            execution_plan: None,
            diagnostics: vec![],
            validation: None,
            analyzer: None,
            runtime_operations: None,
            simulation: None,
            knowledge: None,
            metadata: ProjectStateMetadata {
                compiler_mode: "normal".to_string(),
                source_filename: "".to_string(),
            },
            generated_at: "2026-01-01T00:00:00Z".to_string(),
        };
        let v: serde_json::Value = serde_json::to_value(&state).unwrap();
        assert_eq!(v["schema_version"], "project-state/0.1");
        assert_eq!(v["compiler_version"], "0.1.0");
    }
}
