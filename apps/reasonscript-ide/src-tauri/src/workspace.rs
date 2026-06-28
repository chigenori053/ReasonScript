use std::collections::HashSet;
use std::path::{Path, PathBuf};

use crate::dto::{FileNode, FileNodeKind, IdeError, WorkspaceScanStatus, WorkspaceState};

const SCHEMA_VERSION: &str = "reasonscript-workspace/0.1";
const MAX_DEPTH: usize = 8;
const MAX_FILES: usize = 5000;

fn default_ignored_names() -> HashSet<&'static str> {
    [
        ".git",
        "node_modules",
        "target",
        "dist",
        "build",
        "__pycache__",
        ".venv",
        ".DS_Store",
        ".pytest_cache",
        ".mypy_cache",
        ".vscode",
        ".idea",
    ]
    .iter()
    .copied()
    .collect()
}

fn extension_of(path: &Path) -> Option<String> {
    path.extension()
        .and_then(|e| e.to_str())
        .map(|s| s.to_string())
}

/// Scan a directory recursively, respecting ignore rules and depth/file limits.
/// Returns the list of FileNodes and updates the file counter.
fn scan_dir(
    root: &Path,
    dir: &Path,
    depth: usize,
    file_count: &mut usize,
    ignored_names: &HashSet<&str>,
    truncated: &mut bool,
) -> Vec<FileNode> {
    if depth > MAX_DEPTH || *truncated {
        return vec![];
    }

    let read_dir = match std::fs::read_dir(dir) {
        Ok(rd) => rd,
        Err(_) => return vec![],
    };

    let mut entries: Vec<(String, PathBuf, std::fs::FileType)> = read_dir
        .filter_map(|e| e.ok())
        .filter_map(|e| {
            let file_type = e.file_type().ok()?;
            let name = e.file_name().into_string().ok()?;
            Some((name, e.path(), file_type))
        })
        .collect();

    // Sort: directories first, then files; both alphabetically ascending
    entries.sort_by(|(an, _, at), (bn, _, bt)| {
        let a_is_dir = at.is_dir();
        let b_is_dir = bt.is_dir();
        match (a_is_dir, b_is_dir) {
            (true, false) => std::cmp::Ordering::Less,
            (false, true) => std::cmp::Ordering::Greater,
            _ => an.to_lowercase().cmp(&bn.to_lowercase()),
        }
    });

    let mut nodes = Vec::new();

    for (name, path, file_type) in entries {
        if *truncated {
            break;
        }

        let is_ignored = ignored_names.contains(name.as_str());

        let relative_path = path
            .strip_prefix(root)
            .unwrap_or(&path)
            .to_string_lossy()
            .to_string();

        if file_type.is_symlink() {
            let node = FileNode {
                name,
                path: path.to_string_lossy().to_string(),
                relative_path,
                kind: FileNodeKind::Symlink,
                extension: extension_of(&path),
                children: vec![],
                is_ignored,
                metadata: serde_json::Value::Null,
            };
            if !is_ignored {
                *file_count += 1;
                if *file_count >= MAX_FILES {
                    *truncated = true;
                }
            }
            nodes.push(node);
        } else if file_type.is_dir() {
            if is_ignored {
                let node = FileNode {
                    name,
                    path: path.to_string_lossy().to_string(),
                    relative_path,
                    kind: FileNodeKind::Directory,
                    extension: None,
                    children: vec![],
                    is_ignored: true,
                    metadata: serde_json::Value::Null,
                };
                nodes.push(node);
            } else {
                let children =
                    scan_dir(root, &path, depth + 1, file_count, ignored_names, truncated);
                let node = FileNode {
                    name,
                    path: path.to_string_lossy().to_string(),
                    relative_path,
                    kind: FileNodeKind::Directory,
                    extension: None,
                    children,
                    is_ignored: false,
                    metadata: serde_json::Value::Null,
                };
                nodes.push(node);
            }
        } else if file_type.is_file() {
            let node = FileNode {
                name,
                path: path.to_string_lossy().to_string(),
                relative_path,
                kind: FileNodeKind::File,
                extension: extension_of(&path),
                children: vec![],
                is_ignored,
                metadata: serde_json::Value::Null,
            };
            if !is_ignored {
                *file_count += 1;
                if *file_count >= MAX_FILES {
                    *truncated = true;
                }
            }
            nodes.push(node);
        } else {
            let node = FileNode {
                name,
                path: path.to_string_lossy().to_string(),
                relative_path,
                kind: FileNodeKind::Unknown,
                extension: extension_of(&path),
                children: vec![],
                is_ignored,
                metadata: serde_json::Value::Null,
            };
            nodes.push(node);
        }
    }

    nodes
}

/// Open a directory as workspace. Validates and scans.
pub fn open_workspace_path(path: String) -> Result<WorkspaceState, IdeError> {
    let raw = PathBuf::from(&path);
    if !raw.exists() {
        return Err(IdeError::Workspace(format!(
            "Path does not exist: {}",
            path
        )));
    }
    if !raw.is_dir() {
        return Err(IdeError::Workspace(format!(
            "Path is not a directory: {}",
            path
        )));
    }

    let root = std::fs::canonicalize(&raw)?;
    let root_name = root
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("workspace")
        .to_string();

    let ignored_names = default_ignored_names();
    let ignored_patterns: Vec<String> = ignored_names.iter().map(|s| s.to_string()).collect();

    let mut file_count = 0usize;
    let mut truncated = false;
    let files = scan_dir(
        &root,
        &root,
        0,
        &mut file_count,
        &ignored_names,
        &mut truncated,
    );

    let (scan_status, metadata) = if truncated {
        (
            WorkspaceScanStatus::Partial,
            serde_json::json!({ "warning": "Workspace scan truncated by max_files", "file_count": file_count }),
        )
    } else {
        (
            WorkspaceScanStatus::Complete,
            serde_json::json!({ "file_count": file_count }),
        )
    };

    Ok(WorkspaceState {
        schema_version: SCHEMA_VERSION.to_string(),
        root_path: root.to_string_lossy().to_string(),
        root_name,
        files,
        selected_path: None,
        active_file_path: None,
        ignored_patterns,
        scan_status,
        metadata,
    })
}

/// List files in workspace root (used for refresh).
pub fn list_files_in_workspace(root_path: String) -> Result<Vec<FileNode>, IdeError> {
    let root = std::fs::canonicalize(PathBuf::from(&root_path))?;
    if !root.is_dir() {
        return Err(IdeError::Workspace("Not a directory".to_string()));
    }
    let ignored_names = default_ignored_names();
    let mut file_count = 0usize;
    let mut truncated = false;
    let files = scan_dir(
        &root,
        &root,
        0,
        &mut file_count,
        &ignored_names,
        &mut truncated,
    );
    Ok(files)
}

/// Validate that a relative path stays within the workspace root.
pub fn resolve_workspace_file(root_path: &str, relative_path: &str) -> Result<PathBuf, IdeError> {
    let root = std::fs::canonicalize(Path::new(root_path))?;
    let joined = root.join(relative_path);
    let target = std::fs::canonicalize(&joined)
        .map_err(|_| IdeError::Workspace(format!("File not found: {}", relative_path)))?;

    if !target.starts_with(&root) {
        return Err(IdeError::Internal(
            "Path escapes workspace root".to_string(),
        ));
    }
    Ok(target)
}

// ---------------------------------------------------------------------------
// Unit tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    fn make_temp_workspace() -> TempDir {
        let dir = TempDir::new().unwrap();
        let root = dir.path();
        // Create some files and directories
        fs::create_dir_all(root.join("src")).unwrap();
        fs::write(root.join("src/main.rsn"), "module Hello {}").unwrap();
        fs::write(root.join("README.md"), "# Test").unwrap();
        // Ignored directories
        fs::create_dir_all(root.join(".git/objects")).unwrap();
        fs::create_dir_all(root.join("node_modules/pkg")).unwrap();
        fs::write(root.join("node_modules/pkg/index.js"), "").unwrap();
        dir
    }

    #[test]
    fn open_workspace_rejects_nonexistent_path() {
        let result = open_workspace_path("/does/not/exist/999xyz".to_string());
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("does not exist"));
    }

    #[test]
    fn open_workspace_rejects_file_path() {
        let dir = TempDir::new().unwrap();
        let file = dir.path().join("not_a_dir.txt");
        fs::write(&file, "content").unwrap();
        let result = open_workspace_path(file.to_string_lossy().to_string());
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("not a directory"));
    }

    #[test]
    fn workspace_scan_ignores_target_node_modules_git() {
        let dir = make_temp_workspace();
        let ws = open_workspace_path(dir.path().to_string_lossy().to_string()).unwrap();

        // Find ignored dirs
        fn find_node<'a>(files: &'a [FileNode], name: &str) -> Option<&'a FileNode> {
            for f in files {
                if f.name == name {
                    return Some(f);
                }
            }
            None
        }

        let git = find_node(&ws.files, ".git");
        assert!(git.is_some(), ".git should appear but be marked ignored");
        assert!(git.unwrap().is_ignored);
        assert!(
            git.unwrap().children.is_empty(),
            ".git children not scanned"
        );

        let nm = find_node(&ws.files, "node_modules");
        assert!(nm.is_some());
        assert!(nm.unwrap().is_ignored);
        assert!(nm.unwrap().children.is_empty());
    }

    #[test]
    fn workspace_scan_sorts_directories_first() {
        let dir = TempDir::new().unwrap();
        let root = dir.path();
        fs::write(root.join("a_file.txt"), "").unwrap();
        fs::create_dir_all(root.join("b_dir")).unwrap();
        fs::write(root.join("b_dir/inner.txt"), "").unwrap();
        fs::write(root.join("c_file.txt"), "").unwrap();

        let ws = open_workspace_path(root.to_string_lossy().to_string()).unwrap();
        // Directories should come before files
        assert_eq!(ws.files[0].name, "b_dir");
        assert!(ws.files[0].kind_is_dir());
    }

    #[test]
    fn path_escape_is_rejected() {
        let dir = TempDir::new().unwrap();
        let result = resolve_workspace_file(&dir.path().to_string_lossy(), "../../etc/passwd");
        assert!(result.is_err());
    }

    #[test]
    fn file_node_serializes() {
        let node = FileNode {
            name: "main.rsn".to_string(),
            path: "/ws/src/main.rsn".to_string(),
            relative_path: "src/main.rsn".to_string(),
            kind: FileNodeKind::File,
            extension: Some("rsn".to_string()),
            children: vec![],
            is_ignored: false,
            metadata: serde_json::Value::Null,
        };
        let json = serde_json::to_string(&node).unwrap();
        assert!(json.contains("\"kind\":\"file\""));
        assert!(json.contains("main.rsn"));
    }

    #[test]
    fn workspace_state_serializes() {
        let ws = WorkspaceState {
            schema_version: "reasonscript-workspace/0.1".to_string(),
            root_path: "/ws".to_string(),
            root_name: "ws".to_string(),
            files: vec![],
            selected_path: None,
            active_file_path: None,
            ignored_patterns: vec![".git".to_string()],
            scan_status: WorkspaceScanStatus::Complete,
            metadata: serde_json::Value::Null,
        };
        let json = serde_json::to_string(&ws).unwrap();
        assert!(json.contains("reasonscript-workspace/0.1"));
        assert!(json.contains("\"scan_status\":\"complete\""));
    }

    impl FileNode {
        fn kind_is_dir(&self) -> bool {
            matches!(self.kind, FileNodeKind::Directory)
        }
    }
}
