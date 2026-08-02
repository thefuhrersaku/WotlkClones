#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WoW Config Sync - 3.3.5a
Copia (no linkea) config-cache.wtf, bindings-cache.wtf, macros-cache.txt,
layout-cache.txt y SavedVariables desde una cuenta/personaje "main" hacia
otras cuentas/personajes. Antes de copiar, borra en destino los archivos
con el mismo nombre y cualquier .bak/.old.

Estructura esperada (WTF root):
  WTF/Account/<CUENTA>/config-cache.wtf
  WTF/Account/<CUENTA>/macros-cache.txt
  WTF/Account/<CUENTA>/SavedVariables/*.lua
  WTF/Account/<CUENTA>/<REALM>/<PERSONAJE>/config-cache.wtf
  WTF/Account/<CUENTA>/<REALM>/<PERSONAJE>/bindings-cache.wtf
  WTF/Account/<CUENTA>/<REALM>/<PERSONAJE>/macros-cache.txt
  WTF/Account/<CUENTA>/<REALM>/<PERSONAJE>/layout-cache.txt
  WTF/Account/<CUENTA>/<REALM>/<PERSONAJE>/addons.txt
  WTF/Account/<CUENTA>/<REALM>/<PERSONAJE>/SavedVariables/*.lua

Las exclusiones de SavedVariables (addons que NO se copian, ej. ActionBarSaver)
se guardan en un JSON al lado del script/exe y persisten entre ejecuciones.
"""

import os
import sys
import json
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

ACCOUNT_LEVEL_FILES = ["config-cache.wtf", "macros-cache.txt"]
CHARACTER_LEVEL_FILES = {
    "config":   "config-cache.wtf",
    "bindings": "bindings-cache.wtf",
    "macros":   "macros-cache.txt",
    "layout":   "layout-cache.txt",
    "addons":   "addons.txt",
}
JUNK_SUFFIXES = (".bak", ".old")
DEFAULT_EXCLUDES = ["ActionBarSaver"]

# ---------------------------------------------------------------- paleta --
BG        = "#141210"   # negro cálido, casi carbón
BG_PANEL  = "#1c1915"   # paneles / notebook
BG_FIELD  = "#211d18"   # entries, listboxes
GOLD      = "#c8aa6e"   # dorado WoW clásico (parchment gold)
GOLD_HI   = "#f0c674"   # dorado más claro para hover/selección
TEXT      = "#e8e2d0"   # texto principal, hueso/pergamino
TEXT_DIM  = "#9a9284"   # texto secundario
BORDER    = "#3a3226"


def settings_path():
    """Carpeta del .exe (si está congelado por pyinstaller) o del script."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "wow_config_sync_settings.json")


def load_excludes():
    p = settings_path()
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            ex = data.get("excludes", [])
            if isinstance(ex, list):
                return sorted(set(ex))
        except (OSError, json.JSONDecodeError):
            pass
    return sorted(set(DEFAULT_EXCLUDES))


def save_excludes(excludes):
    p = settings_path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"excludes": sorted(set(excludes))}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def log(widget, text):
    widget.insert(tk.END, text + "\n")
    widget.see(tk.END)
    widget.update_idletasks()


def clean_junk(dst_dir, logw):
    """Borra .bak/.old sueltos en un directorio (no recursivo)."""
    if not os.path.isdir(dst_dir):
        return
    for name in os.listdir(dst_dir):
        if name.lower().endswith(JUNK_SUFFIXES):
            p = os.path.join(dst_dir, name)
            try:
                os.remove(p)
                log(logw, f"  borrado basura: {p}")
            except OSError as e:
                log(logw, f"  ERROR borrando {p}: {e}")


def copy_replace(src_file, dst_dir, logw):
    """Borra el destino homónimo si existe y copia el archivo (nunca symlink)."""
    if not os.path.isfile(src_file):
        return
    os.makedirs(dst_dir, exist_ok=True)
    dst_file = os.path.join(dst_dir, os.path.basename(src_file))
    if os.path.exists(dst_file) or os.path.islink(dst_file):
        try:
            os.remove(dst_file)
        except OSError as e:
            log(logw, f"  ERROR borrando {dst_file}: {e}")
            return
    shutil.copy2(src_file, dst_file)
    log(logw, f"  copiado: {src_file} -> {dst_file}")


def is_excluded(filename, excludes):
    base = os.path.splitext(filename)[0]  # ej: "ActionBarSaver.lua" -> "ActionBarSaver"
    return base in excludes


def copy_savedvariables(src_root, dst_root, excludes, logw):
    src_sv = os.path.join(src_root, "SavedVariables")
    dst_sv = os.path.join(dst_root, "SavedVariables")
    if not os.path.isdir(src_sv):
        return
    clean_junk(dst_sv, logw)
    os.makedirs(dst_sv, exist_ok=True)
    for name in os.listdir(src_sv):
        if name.lower().endswith(JUNK_SUFFIXES):
            continue
        if is_excluded(name, excludes):
            log(logw, f"  omitido (exclusión): {name}")
            continue
        copy_replace(os.path.join(src_sv, name), dst_sv, logw)


def list_accounts(wtf_root):
    acc_dir = os.path.join(wtf_root, "Account")
    if not os.path.isdir(acc_dir):
        return []
    return sorted(d for d in os.listdir(acc_dir)
                  if os.path.isdir(os.path.join(acc_dir, d)))


def list_characters(wtf_root):
    """Devuelve lista de tuplas (cuenta, realm, personaje, path_absoluto)."""
    out = []
    acc_dir = os.path.join(wtf_root, "Account")
    for acc in list_accounts(wtf_root):
        acc_path = os.path.join(acc_dir, acc)
        for realm in os.listdir(acc_path):
            realm_path = os.path.join(acc_path, realm)
            if not os.path.isdir(realm_path) or realm == "SavedVariables":
                continue
            for char in os.listdir(realm_path):
                char_path = os.path.join(realm_path, char)
                if os.path.isdir(char_path):
                    out.append((acc, realm, char, char_path))
    return sorted(out)


def sync_account(wtf_root, src_acc, dst_accs, excludes, logw):
    src_dir = os.path.join(wtf_root, "Account", src_acc)
    for dst_acc in dst_accs:
        dst_dir = os.path.join(wtf_root, "Account", dst_acc)
        log(logw, f"\n== Cuenta {src_acc} -> {dst_acc} ==")
        clean_junk(dst_dir, logw)
        for fname in ACCOUNT_LEVEL_FILES:
            copy_replace(os.path.join(src_dir, fname), dst_dir, logw)
        copy_savedvariables(src_dir, dst_dir, excludes, logw)


def sync_character(src_path, dst_paths, options, excludes, logw):
    for dst_path in dst_paths:
        log(logw, f"\n== Personaje {src_path} -> {dst_path} ==")
        clean_junk(dst_path, logw)
        for key, fname in CHARACTER_LEVEL_FILES.items():
            if options.get(key):
                copy_replace(os.path.join(src_path, fname), dst_path, logw)
        if options.get("savedvars"):
            copy_savedvariables(src_path, dst_path, excludes, logw)


# ------------------------------------------------------------------ GUI --
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WoW Config Sync")
        self.geometry("820x700")
        self.configure(bg=BG)
        self.wtf_root = tk.StringVar()
        self.excludes = load_excludes()

        self._build_style()
        self._build_header()
        self._build_wtf_picker()
        self._build_notebook()
        self._build_log()

        self._char_map = {}  # display string -> path

    # -- estilo -------------------------------------------------------
    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=BG, foreground=TEXT,
                         fieldbackground=BG_FIELD, bordercolor=BORDER,
                         font=("Georgia", 10))
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=BG_PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Dim.TLabel", background=BG, foreground=TEXT_DIM, font=("Georgia", 9))
        style.configure("Title.TLabel", background=BG, foreground=GOLD_HI,
                         font=("Georgia", 20, "bold"))
        style.configure("Subtitle.TLabel", background=BG, foreground=TEXT_DIM,
                         font=("Georgia", 10, "italic"))

        style.configure("TButton", background=BG_FIELD, foreground=GOLD,
                         bordercolor=GOLD, lightcolor=BG_FIELD, darkcolor=BG_FIELD,
                         focusthickness=1, focuscolor=GOLD, padding=6, font=("Georgia", 10, "bold"))
        style.map("TButton",
                  background=[("active", "#2a251d")],
                  foreground=[("active", GOLD_HI)],
                  bordercolor=[("active", GOLD_HI)])

        style.configure("TEntry", fieldbackground=BG_FIELD, foreground=TEXT,
                         bordercolor=BORDER, insertcolor=GOLD)
        style.configure("TCombobox", fieldbackground=BG_FIELD, foreground=TEXT,
                         background=BG_FIELD, bordercolor=BORDER, arrowcolor=GOLD)
        style.map("TCombobox", fieldbackground=[("readonly", BG_FIELD)],
                  foreground=[("readonly", TEXT)])

        style.configure("TNotebook", background=BG, bordercolor=BORDER, tabmargins=(4, 4, 4, 0))
        style.configure("TNotebook.Tab", background=BG_PANEL, foreground=TEXT_DIM,
                         padding=(14, 6), font=("Georgia", 10, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", BG)],
                  foreground=[("selected", GOLD_HI)])

        style.configure("TLabelframe", background=BG_PANEL, bordercolor=GOLD, foreground=GOLD)
        style.configure("TLabelframe.Label", background=BG_PANEL, foreground=GOLD, font=("Georgia", 10, "bold"))
        style.configure("TCheckbutton", background=BG_PANEL, foreground=TEXT, font=("Georgia", 10))
        style.map("TCheckbutton", foreground=[("active", GOLD_HI)])

        self.option_add("*TCombobox*Listbox.background", BG_FIELD)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", GOLD)
        self.option_add("*TCombobox*Listbox.selectForeground", "#1a1a1a")

    def _build_header(self):
        header = ttk.Frame(self, padding=(16, 14, 16, 8))
        header.pack(fill=tk.X)
        ttk.Label(header, text="WoW Config Sync", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Wrath of the Lich King · cliente 3.3.5a",
                  style="Subtitle.TLabel").pack(anchor="w")
        sep = tk.Frame(self, bg=GOLD, height=1)
        sep.pack(fill=tk.X, padx=16, pady=(4, 0))

    def _build_wtf_picker(self):
        top = ttk.Frame(self, padding=16)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Carpeta WTF:").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.wtf_root, width=56).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Buscar...", command=self.browse).pack(side=tk.LEFT)
        ttk.Button(top, text="Cargar", command=self.reload).pack(side=tk.LEFT, padx=6)

    def _build_notebook(self):
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        # --- Tab cuenta ---
        acc_tab = ttk.Frame(nb, padding=14, style="Panel.TFrame")
        nb.add(acc_tab, text="Configuración de cuenta")
        ttk.Label(acc_tab, text="Cuenta origen (main):", background=BG_PANEL).grid(row=0, column=0, sticky="w")
        self.acc_src = tk.StringVar()
        self.acc_src_box = ttk.Combobox(acc_tab, textvariable=self.acc_src, state="readonly", width=30)
        self.acc_src_box.grid(row=0, column=1, sticky="w", padx=4)

        ttk.Label(acc_tab, text="Cuentas destino:", background=BG_PANEL).grid(row=1, column=0, sticky="nw", pady=4)
        self.acc_dst_list = tk.Listbox(acc_tab, selectmode=tk.MULTIPLE, height=8, exportselection=False,
                                        bg=BG_FIELD, fg=TEXT, selectbackground=GOLD, selectforeground="#1a1a1a",
                                        highlightbackground=BORDER, highlightcolor=GOLD, relief=tk.FLAT)
        self.acc_dst_list.grid(row=1, column=1, sticky="w", padx=4)

        ttk.Button(acc_tab, text="Copiar a las demás",
                   command=self.run_account_sync).grid(row=2, column=0, columnspan=2, pady=10, sticky="w")
        ttk.Label(acc_tab, text="Copia config-cache.wtf, macros-cache.txt y SavedVariables a nivel cuenta.\n"
                                 "Borra antes los homónimos y cualquier .bak/.old en destino.",
                  style="Dim.TLabel", background=BG_PANEL).grid(row=3, column=0, columnspan=2, sticky="w")

        # --- Tab personaje ---
        char_tab = ttk.Frame(nb, padding=14, style="Panel.TFrame")
        nb.add(char_tab, text="Configuración de personaje")
        ttk.Label(char_tab, text="Personaje origen (main):", background=BG_PANEL).grid(row=0, column=0, sticky="w")
        self.char_src = tk.StringVar()
        self.char_src_box = ttk.Combobox(char_tab, textvariable=self.char_src, state="readonly", width=45)
        self.char_src_box.grid(row=0, column=1, sticky="w", padx=4)

        ttk.Label(char_tab, text="Personajes destino:", background=BG_PANEL).grid(row=1, column=0, sticky="nw", pady=4)
        self.char_dst_list = tk.Listbox(char_tab, selectmode=tk.MULTIPLE, height=10, exportselection=False, width=45,
                                         bg=BG_FIELD, fg=TEXT, selectbackground=GOLD, selectforeground="#1a1a1a",
                                         highlightbackground=BORDER, highlightcolor=GOLD, relief=tk.FLAT)
        self.char_dst_list.grid(row=1, column=1, sticky="w", padx=4)

        opts = ttk.LabelFrame(char_tab, text="Qué copiar", padding=8)
        opts.grid(row=2, column=0, columnspan=2, sticky="w", pady=8)
        self.opt_vars = {}
        labels = [("config", "Config general (config-cache.wtf)"),
                  ("bindings", "Bindeos (bindings-cache.wtf)"),
                  ("macros", "Macros (macros-cache.txt)"),
                  ("layout", "Layout de UI (layout-cache.txt)"),
                  ("addons", "Lista de addons activados (addons.txt)"),
                  ("savedvars", "SavedVariables (addons)")]
        for i, (key, label) in enumerate(labels):
            v = tk.BooleanVar(value=True)
            self.opt_vars[key] = v
            ttk.Checkbutton(opts, text=label, variable=v).grid(row=i // 2, column=i % 2, sticky="w", padx=6, pady=2)

        ttk.Button(char_tab, text="Enviar a los demás",
                   command=self.run_char_sync).grid(row=3, column=0, columnspan=2, pady=10, sticky="w")

        # --- Tab exclusiones ---
        exc_tab = ttk.Frame(nb, padding=14, style="Panel.TFrame")
        nb.add(exc_tab, text="Exclusiones")
        ttk.Label(exc_tab, text="Addons que NUNCA se copian (SavedVariables), por nombre exacto de archivo sin .lua:",
                  background=BG_PANEL, wraplength=560, justify="left").grid(row=0, column=0, columnspan=2, sticky="w")

        self.exc_list = tk.Listbox(exc_tab, height=10, width=40, exportselection=False,
                                    bg=BG_FIELD, fg=TEXT, selectbackground=GOLD, selectforeground="#1a1a1a",
                                    highlightbackground=BORDER, highlightcolor=GOLD, relief=tk.FLAT)
        self.exc_list.grid(row=1, column=0, sticky="w", pady=8)
        for name in self.excludes:
            self.exc_list.insert(tk.END, name)

        side = ttk.Frame(exc_tab, style="Panel.TFrame")
        side.grid(row=1, column=1, sticky="nw", padx=10, pady=8)
        self.exc_entry = ttk.Entry(side, width=26)
        self.exc_entry.pack(anchor="w", pady=(0, 4))
        ttk.Button(side, text="Agregar", command=self.add_exclude).pack(anchor="w", fill=tk.X, pady=2)
        ttk.Button(side, text="Quitar seleccionado", command=self.remove_exclude).pack(anchor="w", fill=tk.X, pady=2)

        ttk.Label(exc_tab, text="Ej: ActionBarSaver  (coincide con ActionBarSaver.lua y su carpeta en SavedVariables).\n"
                                 "Todo lo que NO esté en esta lista se copia normalmente.",
                  style="Dim.TLabel", background=BG_PANEL, wraplength=560, justify="left").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def _build_log(self):
        ttk.Label(self, text="Registro:", padding=(16, 4, 16, 0)).pack(anchor="w")
        self.logw = tk.Text(self, height=13, bg=BG_FIELD, fg=GOLD, insertbackground=GOLD,
                             relief=tk.FLAT, highlightthickness=1,
                             highlightbackground=BORDER, highlightcolor=GOLD,
                             font=("Consolas", 9))
        self.logw.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4, 16))

    # -- exclusiones ----------------------------------------------------
    def add_exclude(self):
        name = self.exc_entry.get().strip()
        if not name:
            return
        name = os.path.splitext(name)[0]
        if name not in self.excludes:
            self.excludes.append(name)
            self.excludes.sort()
            self.exc_list.delete(0, tk.END)
            for n in self.excludes:
                self.exc_list.insert(tk.END, n)
            save_excludes(self.excludes)
        self.exc_entry.delete(0, tk.END)

    def remove_exclude(self):
        sel = self.exc_list.curselection()
        if not sel:
            return
        name = self.exc_list.get(sel[0])
        if name in self.excludes:
            self.excludes.remove(name)
        self.exc_list.delete(0, tk.END)
        for n in self.excludes:
            self.exc_list.insert(tk.END, n)
        save_excludes(self.excludes)

    # -- wtf / listados ---------------------------------------------------
    def browse(self):
        d = filedialog.askdirectory(title="Seleccioná la carpeta WTF")
        if d:
            self.wtf_root.set(d)
            self.reload()

    def reload(self):
        root = self.wtf_root.get().strip()
        if not root or not os.path.isdir(root):
            messagebox.showerror("Error", "Carpeta WTF inválida.")
            return
        accounts = list_accounts(root)
        self.acc_src_box["values"] = accounts
        self.acc_dst_list.delete(0, tk.END)
        for a in accounts:
            self.acc_dst_list.insert(tk.END, a)

        chars = list_characters(root)
        self._char_map = {}
        display = []
        for acc, realm, char, path in chars:
            key = f"{acc} / {realm} / {char}"
            self._char_map[key] = path
            display.append(key)
        self.char_src_box["values"] = display
        self.char_dst_list.delete(0, tk.END)
        for d in display:
            self.char_dst_list.insert(tk.END, d)

        log(self.logw, f"Cargado: {len(accounts)} cuentas, {len(chars)} personajes.")

    def run_account_sync(self):
        root = self.wtf_root.get().strip()
        src = self.acc_src.get()
        dst_idx = self.acc_dst_list.curselection()
        dsts = [self.acc_dst_list.get(i) for i in dst_idx]
        if not src or not dsts:
            messagebox.showwarning("Falta info", "Elegí cuenta origen y al menos un destino.")
            return
        dsts = [d for d in dsts if d != src]
        if not dsts:
            messagebox.showwarning("Falta info", "El destino no puede ser igual al origen.")
            return
        if not messagebox.askyesno("Confirmar", f"Se va a sobrescribir la config de: {', '.join(dsts)}. ¿Seguir?"):
            return
        sync_account(root, src, dsts, self.excludes, self.logw)
        log(self.logw, "Listo.")

    def run_char_sync(self):
        root = self.wtf_root.get().strip()
        src_key = self.char_src.get()
        dst_idx = self.char_dst_list.curselection()
        dst_keys = [self.char_dst_list.get(i) for i in dst_idx]
        if not src_key or not dst_keys:
            messagebox.showwarning("Falta info", "Elegí personaje origen y al menos un destino.")
            return
        dst_keys = [k for k in dst_keys if k != src_key]
        if not dst_keys:
            messagebox.showwarning("Falta info", "El destino no puede ser igual al origen.")
            return
        options = {k: v.get() for k, v in self.opt_vars.items()}
        if not any(options.values()):
            messagebox.showwarning("Falta info", "Marcá al menos una opción para copiar.")
            return
        if not messagebox.askyesno("Confirmar", f"Se va a sobrescribir la config de {len(dst_keys)} personaje(s). ¿Seguir?"):
            return
        src_path = self._char_map[src_key]
        dst_paths = [self._char_map[k] for k in dst_keys]
        sync_character(src_path, dst_paths, options, self.excludes, self.logw)
        log(self.logw, "Listo.")


if __name__ == "__main__":
    App().mainloop()
