use tauri::Manager;
use tauri_plugin_shell::ShellExt;

struct BackendProcess(tauri_plugin_shell::process::CommandChild);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let sidecar = app
                .shell()
                .sidecar("backend")
                .expect("backend sidecar not found");
            let (mut rx, child) = sidecar.spawn().expect("failed to spawn backend");
            app.manage(BackendProcess(child));
            tauri::async_runtime::spawn(async move {
                while rx.recv().await.is_some() {}
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
