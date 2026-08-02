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
"""

import os
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


def log(widget, text):
    widget.insert(tk.END, text + "\n")
    widget.see(tk.END)
    widget.update_idletasks()


def clean_junk(dst_dir, logw):
    """Borra .bak/.old sueltos en un directorio (no recursivo)."""
    if not os.path.isdir(dst_dir):
        return
    for name in os.listdir(dst_dir):
        low = name.lower()
        if low.endswith(JUNK_SUFFIXES):
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


def copy_savedvariables(src_root, dst_root, logw):
    src_sv = os.path.join(src_root, "SavedVariables")
    dst_sv = os.path.join(dst_root, "SavedVariables")
    if not os.path.isdir(src_sv):
        return
    clean_junk(dst_sv, logw)
    os.makedirs(dst_sv, exist_ok=True)
    for name in os.listdir(src_sv):
        if name.lower().endswith(JUNK_SUFFIXES):
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


def sync_account(wtf_root, src_acc, dst_accs, logw):
    src_dir = os.path.join(wtf_root, "Account", src_acc)
    for dst_acc in dst_accs:
        dst_dir = os.path.join(wtf_root, "Account", dst_acc)
        log(logw, f"\n== Cuenta {src_acc} -> {dst_acc} ==")
        clean_junk(dst_dir, logw)
        for fname in ACCOUNT_LEVEL_FILES:
            copy_replace(os.path.join(src_dir, fname), dst_dir, logw)
        copy_savedvariables(src_dir, dst_dir, logw)


def sync_character(src_path, dst_paths, options, logw):
    for dst_path in dst_paths:
        log(logw, f"\n== Personaje {src_path} -> {dst_path} ==")
        clean_junk(dst_path, logw)
        for key, fname in CHARACTER_LEVEL_FILES.items():
            if options.get(key):
                copy_replace(os.path.join(src_path, fname), dst_path, logw)
        if options.get("savedvars"):
            copy_savedvariables(src_path, dst_path, logw)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WoW Config Sync - 3.3.5a")
        self.geometry("780x640")
        self.wtf_root = tk.StringVar()

        top = ttk.Frame(self, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Carpeta WTF:").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.wtf_root, width=60).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Buscar...", command=self.browse).pack(side=tk.LEFT)
        ttk.Button(top, text="Cargar", command=self.reload).pack(side=tk.LEFT, padx=4)

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # --- Tab cuenta ---
        acc_tab = ttk.Frame(nb, padding=8)
        nb.add(acc_tab, text="Configuración de cuenta")
        ttk.Label(acc_tab, text="Cuenta origen (main):").grid(row=0, column=0, sticky="w")
        self.acc_src = tk.StringVar()
        self.acc_src_box = ttk.Combobox(acc_tab, textvariable=self.acc_src, state="readonly", width=30)
        self.acc_src_box.grid(row=0, column=1, sticky="w", padx=4)

        ttk.Label(acc_tab, text="Cuentas destino:").grid(row=1, column=0, sticky="nw", pady=4)
        self.acc_dst_list = tk.Listbox(acc_tab, selectmode=tk.MULTIPLE, height=8, exportselection=False)
        self.acc_dst_list.grid(row=1, column=1, sticky="w", padx=4)

        ttk.Button(acc_tab, text="Copiar a las demás",
                   command=self.run_account_sync).grid(row=2, column=0, columnspan=2, pady=8, sticky="w")
        ttk.Label(acc_tab, text="Copia config-cache.wtf, macros-cache.txt y SavedVariables a nivel cuenta.\n"
                                 "Borra antes los homónimos y cualquier .bak/.old en destino.",
                  foreground="#555").grid(row=3, column=0, columnspan=2, sticky="w")

        # --- Tab personaje ---
        char_tab = ttk.Frame(nb, padding=8)
        nb.add(char_tab, text="Configuración de personaje")
        ttk.Label(char_tab, text="Personaje origen (main):").grid(row=0, column=0, sticky="w")
        self.char_src = tk.StringVar()
        self.char_src_box = ttk.Combobox(char_tab, textvariable=self.char_src, state="readonly", width=45)
        self.char_src_box.grid(row=0, column=1, sticky="w", padx=4)

        ttk.Label(char_tab, text="Personajes destino:").grid(row=1, column=0, sticky="nw", pady=4)
        self.char_dst_list = tk.Listbox(char_tab, selectmode=tk.MULTIPLE, height=10, exportselection=False, width=45)
        self.char_dst_list.grid(row=1, column=1, sticky="w", padx=4)

        opts = ttk.LabelFrame(char_tab, text="Qué copiar", padding=6)
        opts.grid(row=2, column=0, columnspan=2, sticky="w", pady=6)
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
            ttk.Checkbutton(opts, text=label, variable=v).grid(row=i // 2, column=i % 2, sticky="w", padx=6)

        ttk.Button(char_tab, text="Enviar a los demás",
                   command=self.run_char_sync).grid(row=3, column=0, columnspan=2, pady=8, sticky="w")

        # --- Log ---
        ttk.Label(self, text="Log:").pack(anchor="w", padx=8)
        self.logw = tk.Text(self, height=14)
        self.logw.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self._char_map = {}  # display string -> path

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
        sync_account(root, src, dsts, self.logw)
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
        sync_character(src_path, dst_paths, options, self.logw)
        log(self.logw, "Listo.")


if __name__ == "__main__":
    App().mainloop()
