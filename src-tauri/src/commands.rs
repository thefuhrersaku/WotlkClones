use tauri::AppHandle;

use crate::settings::{self, Settings};
use crate::sync;

#[tauri::command]
pub fn get_settings(app: AppHandle) -> Settings {
    settings::load_settings(&app)
}

#[tauri::command]
pub fn save_settings(app: AppHandle, settings_data: Settings) -> Result<(), String> {
    settings::save_settings(&app, &settings_data)
}

#[tauri::command]
pub fn is_dir(path: String) -> bool {
    std::path::Path::new(&path).is_dir()
}

#[tauri::command]
pub fn list_accounts(wtf_root: String) -> Vec<String> {
    sync::list_accounts(&wtf_root)
}

#[tauri::command]
pub fn list_characters(wtf_root: String) -> Vec<sync::CharacterInfo> {
    sync::list_characters(&wtf_root)
}

#[tauri::command]
pub fn scan_all_addons(wtf_root: String) -> Vec<String> {
    sync::scan_all_addons(&wtf_root)
}

#[tauri::command]
pub fn run_sync(
    job_type: String,
    scope: String,
    wtf_root: String,
    src: String,
    dsts: Vec<String>,
    settings_data: Settings,
) -> Vec<String> {
    let job = settings::Job {
        job_type,
        scope,
        src,
        dsts,
    };
    sync::run(&job, &wtf_root, &settings_data)
}
