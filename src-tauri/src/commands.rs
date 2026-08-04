use serde::Serialize;
use tauri::{AppHandle, Emitter};

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
pub fn get_backups(app: AppHandle) -> Vec<sync::BackupInfo> {
    sync::list_backups(&app)
}

#[tauri::command]
pub fn restore_backup(backup_path: String, wtf_root: String) -> Result<Vec<String>, String> {
    sync::restore_backup(&backup_path, &wtf_root)
}

#[tauri::command]
pub fn delete_backup(backup_path: String) -> Result<(), String> {
    sync::delete_backup(&backup_path)
}

#[derive(Serialize, Clone)]
pub struct SyncProgress {
    pub done: u32,
    pub total: u32,
    pub current: String,
}

#[tauri::command]
pub fn run_sync(
    app: AppHandle,
    job_type: String,
    scope: String,
    wtf_root: String,
    src: String,
    dsts: Vec<String>,
    settings_data: Settings,
) -> Vec<String> {
    let job = settings::Job {
        job_type: job_type.clone(),
        scope: scope.clone(),
        src: src.clone(),
        dsts: dsts.clone(),
    };
    let total = dsts.len() as u32;
    let mut out = Vec::new();
    let _ = app.emit(
        "sync-progress",
        SyncProgress {
            done: 0,
            total,
            current: "Creando backup...".into(),
        },
    );
    if settings_data.backup_enabled {
        match sync::make_backup(&app, &wtf_root, &job, &settings_data) {
            Ok(p) => out.push(format!("\n== Backup guardado en: {} ==", p)),
            Err(e) => out.push(format!("\n== ERROR creando backup: {} ==", e)),
        }
    }
    for (i, dst) in dsts.iter().enumerate() {
        let one = settings::Job {
            job_type: job_type.clone(),
            scope: scope.clone(),
            src: src.clone(),
            dsts: vec![dst.clone()],
        };
        out.extend(sync::run(&one, &wtf_root, &settings_data));
        let _ = app.emit(
            "sync-progress",
            SyncProgress {
                done: (i + 1) as u32,
                total,
                current: dst.clone(),
            },
        );
    }
    out
}
