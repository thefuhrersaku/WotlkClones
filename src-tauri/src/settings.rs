use std::collections::HashMap;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

pub const DEFAULT_ADDON_EXCLUDES: [&str; 1] = ["ActionBarSaver"];

pub const ACCOUNT_CONFIG_FILES: [(&str, &str); 2] = [
    ("config-cache.wtf", "Config general"),
    ("macros-cache.txt", "Macros"),
];

pub const CHARACTER_CONFIG_FILES: [(&str, &str); 4] = [
    ("config-cache.wtf", "Config general"),
    ("macros-cache.txt", "Macros"),
    ("layout-cache.txt", "Layout de UI"),
    ("addons.txt", "Lista de addons activados"),
];

pub const BINDINGS_FILE: &str = "bindings-cache.wtf";

pub const JUNK_SUFFIXES: [&str; 2] = [".bak", ".old"];

pub const SETTINGS_FILE_NAME: &str = "wow_config_sync_settings.json";

#[derive(Serialize, Deserialize, Clone, Debug)]
#[serde(default)]
pub struct Job {
    #[serde(rename = "type")]
    pub job_type: String, // "addons" | "configs" | "bindings"
    pub scope: String,    // "account" | "character"
    pub src: String,
    pub dsts: Vec<String>,
}

impl Default for Job {
    fn default() -> Self {
        Job {
            job_type: String::new(),
            scope: String::new(),
            src: String::new(),
            dsts: Vec::new(),
        }
    }
}

#[derive(Serialize, Deserialize, Clone, Debug)]
#[serde(default)]
pub struct Template {
    pub name: String,
    pub jobs: Vec<Job>,
}

impl Default for Template {
    fn default() -> Self {
        Template {
            name: String::new(),
            jobs: Vec::new(),
        }
    }
}

#[derive(Serialize, Deserialize, Clone, Debug)]
#[serde(default)]
pub struct Settings {
    pub wtf_root: String,
    pub src: HashMap<String, Option<String>>,
    pub addon_excludes: Vec<String>,
    pub config_excludes: Vec<String>,
    pub templates: Vec<Template>,
    #[serde(default = "default_backup_enabled")]
    pub backup_enabled: bool,
}

fn default_backup_enabled() -> bool {
    true
}

impl Default for Settings {
    fn default() -> Self {
        Settings {
            wtf_root: String::new(),
            src: HashMap::new(),
            addon_excludes: DEFAULT_ADDON_EXCLUDES.iter().map(|s| s.to_string()).collect(),
            config_excludes: Vec::new(),
            templates: Vec::new(),
            backup_enabled: true,
        }
    }
}

pub fn settings_path(app: &AppHandle) -> PathBuf {
    app.path()
        .app_config_dir()
        .unwrap_or_else(|_| std::env::temp_dir().join("wotlk-clones"))
        .join(SETTINGS_FILE_NAME)
}

fn parse_settings(json: &str) -> Option<Settings> {
    serde_json::from_str::<Settings>(json).ok()
}

/// Si no hay settings en el directorio de config, intenta migrar el archivo
/// antiguo que quedaba al lado del script/exe de la versión Python.
fn migrate_legacy(app: &AppHandle) -> Option<Settings> {
    let exe_dir = app.path().resource_dir().ok()?;
    let legacy = exe_dir.join(SETTINGS_FILE_NAME);
    let json = std::fs::read_to_string(legacy).ok()?;
    let s = parse_settings(&json)?;
    let _ = save_settings(app, &s);
    Some(s)
}

pub fn load_settings(app: &AppHandle) -> Settings {
    let p = settings_path(app);
    if let Ok(json) = std::fs::read_to_string(&p) {
        if let Some(s) = parse_settings(&json) {
            return s;
        }
    }
    migrate_legacy(app).unwrap_or_default()
}

pub fn save_settings(app: &AppHandle, s: &Settings) -> Result<(), String> {
    let p = settings_path(app);
    if let Some(dir) = p.parent() {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    }
    let json = serde_json::to_string_pretty(s).map_err(|e| e.to_string())?;
    std::fs::write(&p, json).map_err(|e| e.to_string())
}
