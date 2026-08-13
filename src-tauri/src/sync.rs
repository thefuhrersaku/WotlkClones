use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};

use serde::Serialize;
use tauri::Manager;

use crate::settings::{
    Job, JUNK_SUFFIXES, Settings, ACCOUNT_CONFIG_FILES, BINDINGS_FILE, CHARACTER_CONFIG_FILES,
};

// ================================================================ utilidades
pub fn clean_junk(dst_dir: &Path, log: &mut Vec<String>) {
    if !dst_dir.is_dir() {
        return;
    }
    if let Ok(entries) = fs::read_dir(dst_dir) {
        for e in entries.flatten() {
            let name = e.file_name().to_string_lossy().to_lowercase();
            if JUNK_SUFFIXES.iter().any(|s| name.ends_with(s)) {
                match fs::remove_file(e.path()) {
                    Ok(_) => log.push(format!("  borrado basura: {}", e.path().display())),
                    Err(err) => log.push(format!("  ERROR borrando {}: {}", e.path().display(), err)),
                }
            }
        }
    }
}

pub fn copy_replace(src_file: &Path, dst_dir: &Path, log: &mut Vec<String>) {
    if !src_file.is_file() {
        return;
    }
    if let Err(err) = fs::create_dir_all(dst_dir) {
        log.push(format!("  ERROR creando {}: {}", dst_dir.display(), err));
        return;
    }
    let dst_file = dst_dir.join(src_file.file_name().expect("file name"));
    if dst_file.exists() {
        if let Err(err) = fs::remove_file(&dst_file) {
            log.push(format!("  ERROR borrando {}: {}", dst_file.display(), err));
            return;
        }
    }
    match fs::copy(src_file, &dst_file) {
        Ok(_) => log.push(format!("  copiado: {} -> {}", src_file.display(), dst_file.display())),
        Err(err) => log.push(format!(
            "  ERROR copiando {} -> {}: {}",
            src_file.display(),
            dst_file.display(),
            err
        )),
    }
}

/// Si `only` tiene elementos, ese addon se copia únicamente si está en `only`
/// (las exclusiones se ignoran en ese caso). Si `only` está vacío, se usa el
/// criterio normal de exclusiones.
pub fn should_copy_addon(filename: &str, only: &[String], excludes: &[String]) -> bool {
    let base = Path::new(filename)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or(filename)
        .to_lowercase();
    if !only.is_empty() {
        return only.iter().any(|x| x.to_lowercase() == base);
    }
    !excludes.iter().any(|x| x.to_lowercase() == base)
}

fn copy_savedvariables(
    src_root: &Path,
    dst_root: &Path,
    only: &[String],
    excludes: &[String],
    log: &mut Vec<String>,
) {
    let src_sv = src_root.join("SavedVariables");
    let dst_sv = dst_root.join("SavedVariables");
    if !src_sv.is_dir() {
        return;
    }
    clean_junk(&dst_sv, log);
    if let Err(err) = fs::create_dir_all(&dst_sv) {
        log.push(format!("  ERROR creando {}: {}", dst_sv.display(), err));
        return;
    }
    if let Ok(entries) = fs::read_dir(&src_sv) {
        for e in entries.flatten() {
            let name = e.file_name().to_string_lossy().to_lowercase();
            if JUNK_SUFFIXES.iter().any(|s| name.ends_with(s)) {
                continue;
            }
            if !should_copy_addon(&name, only, excludes) {
                log.push(format!("  omitido (exclusión/solo): {}", e.file_name().to_string_lossy()));
                continue;
            }
            copy_replace(&e.path(), &dst_sv, log);
        }
    }
}

// ============================================================== listados
pub fn list_accounts(wtf_root: &str) -> Vec<String> {
    let acc_dir = Path::new(wtf_root).join("Account");
    let mut out = Vec::new();
    if let Ok(entries) = fs::read_dir(&acc_dir) {
        for e in entries.flatten() {
            if e.path().is_dir() {
                out.push(e.file_name().to_string_lossy().to_string());
            }
        }
    }
    out.sort();
    out
}

#[derive(Serialize, Clone, Debug)]
pub struct CharacterInfo {
    pub account: String,
    pub realm: String,
    pub character: String,
    pub path: String,
    pub key: String,
    pub has_activity: bool,
}

/// Un personaje se considera "sin actividad" (nunca se llegó a loguear de
/// verdad, la carpeta quedó solo por reservar el nombre) si no tiene ningún
/// SavedVariables, ni config-cache.wtf, ni chat.wtf.
fn character_has_activity(char_path: &Path) -> bool {
    let sv = char_path.join("SavedVariables");
    let has_saved_vars = fs::read_dir(&sv)
        .map(|mut entries| entries.next().is_some())
        .unwrap_or(false);
    has_saved_vars
        || char_path.join("config-cache.wtf").is_file()
        || char_path.join("chat.wtf").is_file()
}

pub fn list_characters(wtf_root: &str) -> Vec<CharacterInfo> {
    let acc_dir = Path::new(wtf_root).join("Account");
    let mut out = Vec::new();
    if let Ok(accounts) = fs::read_dir(&acc_dir) {
        for acc in accounts.flatten() {
            if !acc.path().is_dir() {
                continue;
            }
            let account = acc.file_name().to_string_lossy().to_string();
            if let Ok(realms) = fs::read_dir(acc.path()) {
                for realm in realms.flatten() {
                    let realm_name = realm.file_name().to_string_lossy().to_string();
                    if !realm.path().is_dir() || realm_name == "SavedVariables" {
                        continue;
                    }
                    if let Ok(chars) = fs::read_dir(realm.path()) {
                        for ch in chars.flatten() {
                            if !ch.path().is_dir() {
                                continue;
                            }
                            let character = ch.file_name().to_string_lossy().to_string();
                            out.push(CharacterInfo {
                                account: account.clone(),
                                realm: realm_name.clone(),
                                character: character.clone(),
                                path: ch.path().to_string_lossy().to_string(),
                                key: format!("{} / {} / {}", account, realm_name, character),
                                has_activity: character_has_activity(&ch.path()),
                            });
                        }
                    }
                }
            }
        }
    }
    out.sort_by(|a, b| {
        a.account
            .cmp(&b.account)
            .then_with(|| a.realm.cmp(&b.realm))
            .then_with(|| a.character.cmp(&b.character))
    });
    out
}

fn char_key_to_path(wtf_root: &str, key: &str) -> Option<String> {
    list_characters(wtf_root)
        .into_iter()
        .find(|c| c.key == key)
        .map(|c| c.path)
}

fn char_paths_for_keys(wtf_root: &str, keys: &[String]) -> Vec<(String, String)> {
    keys.iter()
        .filter_map(|k| char_key_to_path(wtf_root, k).map(|p| (k.clone(), p)))
        .collect()
}

pub fn scan_all_addons(wtf_root: &str) -> Vec<String> {
    let mut names: BTreeSet<String> = BTreeSet::new();
    let acc_dir = Path::new(wtf_root).join("Account");
    if !acc_dir.is_dir() {
        return Vec::new();
    }
    if let Ok(accounts) = fs::read_dir(&acc_dir) {
        for acc in accounts.flatten() {
            let sv = acc.path().join("SavedVariables");
            collect_sv_names(&sv, &mut names);
        }
    }
    for ch in list_characters(wtf_root) {
        let sv = Path::new(&ch.path).join("SavedVariables");
        collect_sv_names(&sv, &mut names);
    }
    names.into_iter().collect()
}

fn collect_sv_names(sv: &Path, names: &mut BTreeSet<String>) {
    if !sv.is_dir() {
        return;
    }
    if let Ok(entries) = fs::read_dir(sv) {
        for n in entries.flatten() {
            let name = n.file_name().to_string_lossy().to_lowercase();
            if JUNK_SUFFIXES.iter().any(|s| name.ends_with(s)) {
                continue;
            }
            if let Some(stem) = n.path().file_stem() {
                names.insert(stem.to_string_lossy().to_string());
            }
        }
    }
}

// ============================================================== backup
fn dst_dir_for(wtf_root: &str, job: &Job, dst: &str) -> PathBuf {
    if job.scope == "account" {
        Path::new(wtf_root).join("Account").join(dst)
    } else {
        char_key_to_path(wtf_root, dst).map(PathBuf::from).unwrap_or_default()
    }
}

fn backup_file(src: &Path, dst: &Path) {
    if !src.is_file() {
        return;
    }
    if let Some(parent) = dst.parent() {
        if fs::create_dir_all(parent).is_err() {
            return;
        }
    }
    let _ = fs::copy(src, dst);
}

fn backup_savedvars(src: &Path, dst: &Path) {
    if !src.is_dir() {
        return;
    }
    if let Ok(entries) = fs::read_dir(src) {
        for e in entries.flatten() {
            if !e.path().is_file() {
                continue;
            }
            let name = e.file_name().to_string_lossy().to_lowercase();
            if JUNK_SUFFIXES.iter().any(|s| name.ends_with(s)) {
                continue;
            }
            backup_file(&e.path(), &dst.join(e.file_name()));
        }
    }
}

/// Guarda una copia de lo que se va a sobrescribir en <app_config>/backups/backup_<ts>,
/// manteniendo la estructura Account/... para que sea fácil de restaurar a mano.
pub const BACKUP_RETENTION_DAYS: u64 = 7;
const MS_PER_DAY: u64 = 24 * 60 * 60 * 1000;

/// Borra las carpetas de backup (backup_<timestamp_ms>) más viejas que
/// BACKUP_RETENTION_DAYS. Devuelve cuántas borró.
pub fn prune_old_backups(app: &tauri::AppHandle) -> u64 {
    let root = backups_root(app);
    let now_ms = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0);
    let max_age_ms = BACKUP_RETENTION_DAYS * MS_PER_DAY;
    let mut removed = 0u64;
    if let Ok(entries) = fs::read_dir(&root) {
        for e in entries.flatten() {
            if !e.path().is_dir() {
                continue;
            }
            let name = e.file_name().to_string_lossy().to_string();
            let Some(ts) = name.strip_prefix("backup_").and_then(|n| n.parse::<u64>().ok()) else {
                continue;
            };
            let age = now_ms.saturating_sub(ts);
            if age > max_age_ms {
                if fs::remove_dir_all(e.path()).is_ok() {
                    removed += 1;
                }
            }
        }
    }
    removed
}

pub fn make_backup(
    app: &tauri::AppHandle,
    wtf_root: &str,
    job: &Job,
    s: &Settings,
) -> Result<String, String> {
    let root = app
        .path()
        .app_config_dir()
        .map_err(|e| e.to_string())?
        .join("backups");
    fs::create_dir_all(&root).map_err(|e| e.to_string())?;
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let backup_root = root.join(format!("backup_{}", ts));
    fs::create_dir_all(&backup_root).map_err(|e| e.to_string())?;

    for dst in &job.dsts {
        let dst_dir = dst_dir_for(wtf_root, job, dst);
        if dst_dir.as_os_str().is_empty() {
            continue;
        }
        let Ok(rel) = dst_dir.strip_prefix(wtf_root) else {
            continue;
        };
        let target = backup_root.join(rel);
        match job.job_type.as_str() {
            "addons" => backup_savedvars(
                &dst_dir.join("SavedVariables"),
                &target.join("SavedVariables"),
            ),
            "configs" => {
                let list: &[(&str, &str)] = if job.scope == "character" {
                    &CHARACTER_CONFIG_FILES
                } else {
                    &ACCOUNT_CONFIG_FILES
                };
                for (fname, _) in list {
                    if s.config_excludes.iter().any(|x| x == fname) {
                        continue;
                    }
                    backup_file(&dst_dir.join(fname), &target.join(fname));
                }
            }
            "bindings" => backup_file(&dst_dir.join(BINDINGS_FILE), &target.join(BINDINGS_FILE)),
            _ => {}
        }
    }
    prune_old_backups(app);
    Ok(backup_root.display().to_string())
}

#[derive(Serialize, Clone, Debug)]
pub struct BackupInfo {
    pub id: String,
    pub path: String,
    pub ts: u64,
    pub files: u64,
    pub accounts: Vec<String>,
}

fn count_files(p: &Path) -> u64 {
    let mut n = 0;
    if p.is_dir() {
        if let Ok(entries) = fs::read_dir(p) {
            for e in entries.flatten() {
                n += count_files(&e.path());
            }
        }
    } else if p.is_file() {
        n = 1;
    }
    n
}

pub fn backups_root(app: &tauri::AppHandle) -> std::path::PathBuf {
    app.path()
        .app_config_dir()
        .map(|d| d.join("backups"))
        .unwrap_or_default()
}

pub fn list_backups(app: &tauri::AppHandle) -> Vec<BackupInfo> {
    prune_old_backups(app);
    let mut out = Vec::new();
    if let Ok(entries) = fs::read_dir(backups_root(app)) {
        for e in entries.flatten() {
            if !e.path().is_dir() {
                continue;
            }
            let name = e.file_name().to_string_lossy().to_string();
            let ts = name
                .strip_prefix("backup_")
                .and_then(|n| n.parse::<u64>().ok())
                .unwrap_or(0);
            let mut files = 0u64;
            let mut accounts = Vec::new();
            let acc = e.path().join("Account");
            if let Ok(acc_entries) = fs::read_dir(&acc) {
                for acc_e in acc_entries.flatten() {
                    if !acc_e.path().is_dir() {
                        continue;
                    }
                    accounts.push(acc_e.file_name().to_string_lossy().to_string());
                    files += count_files(&acc_e.path());
                }
            }
            out.push(BackupInfo {
                id: name.clone(),
                path: e.path().display().to_string(),
                ts,
                files,
                accounts,
            });
        }
    }
    out.sort_by(|a, b| b.ts.cmp(&a.ts));
    out
}

fn copy_tree(src: &Path, dst: &Path, log: &mut Vec<String>) {
    if src.is_dir() {
        if fs::create_dir_all(dst).is_err() {
            return;
        }
        if let Ok(entries) = fs::read_dir(src) {
            for e in entries.flatten() {
                copy_tree(&e.path(), &dst.join(e.file_name()), log);
            }
        }
    } else if src.is_file() {
        match fs::copy(src, dst) {
            Ok(_) => log.push(format!("  restaurado: {}", dst.display())),
            Err(err) => log.push(format!("  ERROR restaurando {}: {}", dst.display(), err)),
        }
    }
}

pub fn restore_backup(backup_path: &str, wtf_root: &str) -> Result<Vec<String>, String> {
    let src_root = Path::new(backup_path);
    let dst_root = Path::new(wtf_root);
    if !src_root.is_dir() {
        return Err("El backup seleccionado ya no existe.".to_string());
    }
    if !dst_root.is_dir() {
        return Err("La carpeta WTF configurada ya no existe.".to_string());
    }
    let mut log = Vec::new();
    copy_tree(src_root, dst_root, &mut log);
    Ok(log)
}

pub fn delete_backup(backup_path: &str) -> Result<(), String> {
    let p = Path::new(backup_path);
    if !p.is_dir() {
        return Err("El backup seleccionado ya no existe.".to_string());
    }
    fs::remove_dir_all(p).map_err(|e| e.to_string())
}

// ============================================================== sync
fn sync_addons_account(wtf_root: &str, src: &str, dsts: &[String], s: &Settings, log: &mut Vec<String>) {
    let src_dir = Path::new(wtf_root).join("Account").join(src);
    for dst in dsts {
        let dst_dir = Path::new(wtf_root).join("Account").join(dst);
        log.push(format!("\n== Addons cuenta: {} -> {} ==", src, dst));
        copy_savedvariables(&src_dir, &dst_dir, &s.addon_only, &s.addon_excludes, log);
    }
}

fn sync_addons_character(wtf_root: &str, src: &str, dsts: &[String], s: &Settings, log: &mut Vec<String>) {
    let Some(src_path) = char_key_to_path(wtf_root, src) else {
        log.push(format!("\n== ERROR: origen de personaje no encontrado: {}", src));
        return;
    };
    let dsts_paths = char_paths_for_keys(wtf_root, dsts);
    for (dst_key, dst_path) in dsts_paths {
        log.push(format!("\n== Addons personaje: {} -> {} ==", src, dst_key));
        copy_savedvariables(Path::new(&src_path), Path::new(&dst_path), &s.addon_only, &s.addon_excludes, log);
    }
}

fn sync_configs_account(wtf_root: &str, src: &str, dsts: &[String], s: &Settings, log: &mut Vec<String>) {
    let src_dir = Path::new(wtf_root).join("Account").join(src);
    for dst in dsts {
        let dst_dir = Path::new(wtf_root).join("Account").join(dst);
        log.push(format!("\n== Config cuenta: {} -> {} ==", src, dst));
        clean_junk(&dst_dir, log);
        for (fname, _) in crate::settings::ACCOUNT_CONFIG_FILES {
            if s.config_excludes.iter().any(|x| x == fname) {
                continue;
            }
            copy_replace(&src_dir.join(fname), &dst_dir, log);
        }
    }
}

fn sync_configs_character(wtf_root: &str, src: &str, dsts: &[String], s: &Settings, log: &mut Vec<String>) {
    let Some(src_path) = char_key_to_path(wtf_root, src) else {
        log.push(format!("\n== ERROR: origen de personaje no encontrado: {}", src));
        return;
    };
    let src_dir = Path::new(&src_path);
    let dsts_paths = char_paths_for_keys(wtf_root, dsts);
    for (dst_key, dst_path) in dsts_paths {
        log.push(format!("\n== Config personaje: {} -> {} ==", src, dst_key));
        let dst_dir = Path::new(&dst_path);
        clean_junk(dst_dir, log);
        for (fname, _) in crate::settings::CHARACTER_CONFIG_FILES {
            if s.config_excludes.iter().any(|x| x == fname) {
                continue;
            }
            copy_replace(&src_dir.join(fname), dst_dir, log);
        }
    }
}

fn sync_bindings_account(wtf_root: &str, src: &str, dsts: &[String], log: &mut Vec<String>) {
    let src_dir = Path::new(wtf_root).join("Account").join(src);
    for dst in dsts {
        let dst_dir = Path::new(wtf_root).join("Account").join(dst);
        log.push(format!("\n== Bindeos cuenta: {} -> {} ==", src, dst));
        clean_junk(&dst_dir, log);
        copy_replace(&src_dir.join(crate::settings::BINDINGS_FILE), &dst_dir, log);
    }
}

fn sync_bindings_character(wtf_root: &str, src: &str, dsts: &[String], log: &mut Vec<String>) {
    let Some(src_path) = char_key_to_path(wtf_root, src) else {
        log.push(format!("\n== ERROR: origen de personaje no encontrado: {}", src));
        return;
    };
    let src_dir = Path::new(&src_path);
    let dsts_paths = char_paths_for_keys(wtf_root, dsts);
    for (dst_key, dst_path) in dsts_paths {
        log.push(format!("\n== Bindeos: {} -> {} ==", src, dst_key));
        let dst_dir = Path::new(&dst_path);
        clean_junk(dst_dir, log);
        copy_replace(&src_dir.join(crate::settings::BINDINGS_FILE), dst_dir, log);
    }
}

pub fn run(job: &Job, wtf_root: &str, s: &Settings) -> Vec<String> {
    let mut log = Vec::new();
    match (job.job_type.as_str(), job.scope.as_str()) {
        ("addons", "account") => sync_addons_account(wtf_root, &job.src, &job.dsts, s, &mut log),
        ("addons", "character") => sync_addons_character(wtf_root, &job.src, &job.dsts, s, &mut log),
        ("configs", "account") => sync_configs_account(wtf_root, &job.src, &job.dsts, s, &mut log),
        ("configs", "character") => sync_configs_character(wtf_root, &job.src, &job.dsts, s, &mut log),
        ("bindings", "account") => sync_bindings_account(wtf_root, &job.src, &job.dsts, &mut log),
        ("bindings", "character") => sync_bindings_character(wtf_root, &job.src, &job.dsts, &mut log),
        (kind, scope) => log.push(format!("\n== ERROR: tipo no soportado: {} / {}", kind, scope)),
    }
    log
}
