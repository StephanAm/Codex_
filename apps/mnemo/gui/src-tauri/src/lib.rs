// Copyright (C) 2026 Stephan Marais
// SPDX-License-Identifier: AGPL-3.0-or-later

use std::fs;
use std::io::Write;
use std::net::TcpStream;
use std::path::PathBuf;
use std::sync::Mutex;
use serde::{Deserialize, Serialize};
use tauri::Manager;
use tauri_plugin_shell::ShellExt;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct GuiConfig {
    #[serde(default = "default_true")]
    start_backend_on_startup: bool,
    #[serde(default = "default_true")]
    kill_backend_on_exit: bool,
}

fn default_true() -> bool { true }

impl Default for GuiConfig {
    fn default() -> Self {
        GuiConfig { start_backend_on_startup: true, kill_backend_on_exit: true }
    }
}

struct GuiConfigState {
    path: PathBuf,
    config: Mutex<GuiConfig>,
}

fn load_gui_config(path: &PathBuf) -> GuiConfig {
    fs::read_to_string(path)
        .ok()
        .and_then(|c| serde_json::from_str(&c).ok())
        .unwrap_or_default()
}

fn save_gui_config(path: &PathBuf, config: &GuiConfig) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let content = serde_json::to_string_pretty(config).map_err(|e| e.to_string())?;
    fs::write(path, content).map_err(|e| e.to_string())
}

fn shutdown_backend() {
    if let Ok(mut stream) = TcpStream::connect("127.0.0.1:8765") {
        let _ = stream.write_all(
            b"POST /shutdown HTTP/1.0\r\nHost: 127.0.0.1:8765\r\nContent-Length: 0\r\n\r\n",
        );
    }
}

#[tauri::command]
fn get_gui_config(state: tauri::State<GuiConfigState>) -> GuiConfig {
    state.config.lock().unwrap().clone()
}

#[tauri::command]
fn set_gui_config(state: tauri::State<GuiConfigState>, config: GuiConfig) -> Result<(), String> {
    save_gui_config(&state.path, &config)?;
    *state.config.lock().unwrap() = config;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![get_gui_config, set_gui_config])
        .setup(|app| {
            let config_path = app
                .path()
                .app_config_dir()?
                .join("gui_config.json");

            let gui_config = load_gui_config(&config_path);
            let start_backend = gui_config.start_backend_on_startup;

            app.manage(GuiConfigState {
                path: config_path,
                config: Mutex::new(gui_config),
            });

            if start_backend {
                let sidecar = app
                    .shell()
                    .sidecar("backend")
                    .expect("backend sidecar not found");
                let (mut rx, _child) = sidecar.spawn().expect("failed to spawn backend");
                tauri::async_runtime::spawn(async move {
                    while rx.recv().await.is_some() {}
                });
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                let kill = app_handle
                    .state::<GuiConfigState>()
                    .config
                    .lock()
                    .unwrap()
                    .kill_backend_on_exit;
                if kill {
                    shutdown_backend();
                }
            }
        });
}
