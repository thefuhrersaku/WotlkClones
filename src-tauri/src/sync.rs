use std::collections::BTreeSet;
use std::fs;
use std::path::Path;

use serde::Serialize;

use crate::settings::{Job, JUNK_SUFFIXES, Settings};

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

pub fn is_excluded(filename: &str, excludes: &[String]) -> bool {
    let base = Path::new(filename)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or(filename)
        .to_lowercase();
    excludes.iter().any(|x| x.to_lowercase() == base)
}

fn copy_savedvariables(src_root: &Path, dst_root: &Path, excludes: &[String], log: &mut Vec<String>) {
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
            if is_excluded(&name, excludes) {
                log.push(format!("  omitido (exclusión): {}", e.file_name().to_string_lossy()));
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

// ============================================================== sync
fn sync_addons_account(wtf_root: &str, src: &str, dsts: &[String], s: &Settings, log: &mut Vec<String>) {
    let src_dir = Path::new(wtf_root).join("Account").join(src);
    for dst in dsts {
        let dst_dir = Path::new(wtf_root).join("Account").join(dst);
        log.push(format!("\n== Addons cuenta: {} -> {} ==", src, dst));
        copy_savedvariables(&src_dir, &dst_dir, &s.addon_excludes, log);
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
        copy_savedvariables(Path::new(&src_path), Path::new(&dst_path), &s.addon_excludes, log);
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
