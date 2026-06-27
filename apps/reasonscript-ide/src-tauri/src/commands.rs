use crate::compiler_bridge::build_project_state_from_source;
use crate::dto::{IdeError, ProjectState};
use std::path::PathBuf;

#[tauri::command]
pub async fn build_project_state(
    source: String,
    uri: Option<String>,
) -> Result<ProjectState, IdeError> {
    eprintln!(
        "[ide] build_project_state source_len={} uri={:?}",
        source.len(),
        uri
    );
    tokio::task::spawn_blocking(move || {
        build_project_state_from_source(&source, uri.as_deref(), "normal")
    })
    .await
    .map_err(|e| IdeError::Pipeline(e.to_string()))?
}

#[tauri::command]
pub async fn open_file(path: String) -> Result<String, IdeError> {
    let content = tokio::fs::read_to_string(&path).await?;
    Ok(content)
}

#[tauri::command]
pub async fn save_file(path: String, content: String) -> Result<(), IdeError> {
    tokio::fs::write(&path, content).await?;
    Ok(())
}

#[tauri::command]
pub async fn list_project_files(root: String) -> Result<Vec<String>, IdeError> {
    let root_path = PathBuf::from(&root);
    let mut files: Vec<String> = Vec::new();
    collect_rsn_files(&root_path, &mut files)?;
    Ok(files)
}

fn collect_rsn_files(dir: &PathBuf, out: &mut Vec<String>) -> Result<(), IdeError> {
    let entries = std::fs::read_dir(dir)?;
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
            if !name.starts_with('.') && name != "node_modules" && name != "target" {
                collect_rsn_files(&path, out)?;
            }
        } else if path.extension().and_then(|e| e.to_str()) == Some("rsn") {
            if let Some(s) = path.to_str() {
                out.push(s.to_string());
            }
        }
    }
    Ok(())
}

#[tauri::command]
pub async fn export_project_state(
    state: ProjectState,
    path: String,
) -> Result<(), IdeError> {
    let json = serde_json::to_string_pretty(&state)?;
    tokio::fs::write(&path, json).await?;
    Ok(())
}
