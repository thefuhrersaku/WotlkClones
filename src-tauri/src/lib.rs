pub mod commands;
pub mod settings;
pub mod sync;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            commands::get_settings,
            commands::save_settings,
            commands::is_dir,
            commands::list_accounts,
            commands::list_characters,
            commands::scan_all_addons,
            commands::run_sync,
            commands::get_backups,
            commands::restore_backup,
            commands::delete_backup,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
