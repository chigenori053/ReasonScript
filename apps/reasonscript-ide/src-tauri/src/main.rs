// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod compiler_bridge;
mod dto;
#[cfg(test)]
mod dto_tests;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            commands::build_project_state,
            commands::open_file,
            commands::save_file,
            commands::list_project_files,
            commands::export_project_state,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
