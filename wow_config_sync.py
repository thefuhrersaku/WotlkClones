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

Requiere: pip install customtkinter
"""

import os
import sys
import json
import shutil
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk

# ---------------------------------------------------------------- paleta --
BG       = "#0f0d0a"   # fondo ventana
PANEL    = "#1a1611"   # paneles / tabs
FIELD    = "#221d16"   # entries, scrollframes
GOLD     = "#c8a557"   # dorado principal
GOLD_HI  = "#e8c979"   # dorado hover / texto destacado
GOLD_DIM = "#8a723f"   # dorado apagado (bordes secundarios)
TEXT     = "#efe6d3"   # texto principal
TEXT_DIM = "#a89f8c"   # texto secundario
DANGER   = "#b0503f"

ctk.set_appearance_mode("dark")

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
    widget.configure(state="normal")
    widget.insert("end", text + "\n")
    widget.see("end")
    widget.configure(state="disabled")
    widget.update_idletasks()


def clean_junk(dst_dir, logw):
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
    base = os.path.splitext(filename)[0]
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
def gold_button(parent, text, command, small=False, **kw):
    return ctk.CTkButton(
        parent, text=text, command=command,
        fg_color=FIELD, hover_color="#332b1f", text_color=GOLD,
        border_width=1, border_color=GOLD_DIM,
        corner_radius=8, font=ctk.CTkFont(family="Georgia", size=12 if small else 13, weight="bold"),
        **kw,
    )


def title_font(size=13, weight="normal", slant="roman"):
    return ctk.CTkFont(family="Georgia", size=size, weight=weight, slant=slant)


class CheckList(ctk.CTkScrollableFrame):
    """Reemplazo de listbox multi-selección: una fila con checkbox por item."""

    def __init__(self, parent, height=180, **kw):
        super().__init__(parent, fg_color=FIELD, corner_radius=10,
                          border_width=1, border_color=GOLD_DIM,
                          height=height, **kw)
        self._vars = {}

    def set_items(self, items):
        for w in self.winfo_children():
            w.destroy()
        self._vars = {}
        for name in items:
            v = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(
                self, text=name, variable=v, text_color=TEXT,
                fg_color=GOLD, hover_color=GOLD_HI, border_color=GOLD_DIM,
                checkmark_color="#1a1610", font=title_font(12),
            )
            cb.pack(anchor="w", padx=6, pady=3)
            self._vars[name] = v

    def selected(self):
        return [name for name, v in self._vars.items() if v.get()]

    def select_all(self):
        for v in self._vars.values():
            v.set(True)

    def select_none(self):
        for v in self._vars.values():
            v.set(False)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WoW Config Sync")
        self.geometry("880x780")
        self.configure(fg_color=BG)
        self.excludes = load_excludes()
        self._char_map = {}

        self._build_header()
        self._build_wtf_picker()
        self._build_tabs()
        self._build_log()

    # ---------------------------------------------------------- header --
    def _build_header(self):
        panel = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=16,
                              border_width=2, border_color=GOLD)
        panel.pack(fill="x", padx=18, pady=(16, 8))
        inner = ctk.CTkFrame(panel, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=14)
        ctk.CTkLabel(inner, text="WoW Config Sync", text_color=GOLD_HI,
                     font=title_font(24, "bold")).pack(anchor="w")
        ctk.CTkLabel(inner, text="Wrath of the Lich King  ·  cliente 3.3.5a",
                     text_color=TEXT_DIM, font=title_font(12, slant="italic")).pack(anchor="w")

    # ------------------------------------------------------- wtf picker --
    def _build_wtf_picker(self):
        panel = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14,
                              border_width=2, border_color=GOLD)
        panel.pack(fill="x", padx=18, pady=8)
        row = ctk.CTkFrame(panel, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(row, text="Carpeta WTF:", text_color=TEXT,
                     font=title_font(13)).pack(side="left")
        self.wtf_root = ctk.StringVar()
        ctk.CTkEntry(row, textvariable=self.wtf_root, width=420,
                     fg_color=FIELD, border_color=GOLD_DIM, text_color=TEXT,
                     corner_radius=8).pack(side="left", padx=8)
        gold_button(row, "Buscar...", self.browse).pack(side="left", padx=3)
        gold_button(row, "Cargar", self.reload).pack(side="left", padx=3)

    # ------------------------------------------------------------ tabs --
    def _build_tabs(self):
        self.tabs = ctk.CTkTabview(
            self, fg_color=PANEL, corner_radius=14,
            border_width=2, border_color=GOLD,
            segmented_button_fg_color=FIELD,
            segmented_button_selected_color=GOLD,
            segmented_button_selected_hover_color=GOLD_HI,
            segmented_button_unselected_color=PANEL,
            segmented_button_unselected_hover_color="#2a241a",
            text_color=TEXT_DIM,
            text_color_disabled=TEXT_DIM,
        )
        self.tabs.pack(fill="both", expand=True, padx=18, pady=8)
        acc_tab = self.tabs.add("Configuración de cuenta")
        char_tab = self.tabs.add("Configuración de personaje")
        exc_tab = self.tabs.add("Exclusiones")
        self._build_account_tab(acc_tab)
        self._build_character_tab(char_tab)
        self._build_exclusions_tab(exc_tab)

    def _build_account_tab(self, tab):
        left = ctk.CTkFrame(tab, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=8)
        right = ctk.CTkFrame(tab, fg_color="transparent")
        right.pack(side="left", fill="y", padx=(0, 4), pady=8)

        ctk.CTkLabel(left, text="Cuenta origen (main):", text_color=TEXT,
                     font=title_font(13)).pack(anchor="w")
        self.acc_src = ctk.StringVar()
        self.acc_src_box = ctk.CTkComboBox(
            left, variable=self.acc_src, values=[], state="readonly",
            fg_color=FIELD, border_color=GOLD_DIM, button_color=GOLD_DIM,
            button_hover_color=GOLD, dropdown_fg_color=FIELD,
            text_color=TEXT, corner_radius=8, width=280,
        )
        self.acc_src_box.pack(anchor="w", pady=(4, 12))

        ctk.CTkLabel(left, text="Cuentas destino:", text_color=TEXT,
                     font=title_font(13)).pack(anchor="w")
        self.acc_dst_list = CheckList(left, height=220)
        self.acc_dst_list.pack(fill="x", pady=(4, 12))

        gold_button(left, "Copiar a las demás", self.run_account_sync).pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(left, text="Copia config-cache.wtf, macros-cache.txt y SavedVariables a nivel cuenta.\n"
                                 "Borra antes los homónimos y cualquier .bak/.old en destino.",
                     text_color=TEXT_DIM, font=title_font(11), justify="left").pack(anchor="w")

        gold_button(right, "Seleccionar todas", lambda: self.acc_dst_list.select_all(), small=True).pack(fill="x", pady=3)
        gold_button(right, "Deseleccionar todas", lambda: self.acc_dst_list.select_none(), small=True).pack(fill="x", pady=3)

    def _build_character_tab(self, tab):
        left = ctk.CTkFrame(tab, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=8)
        right = ctk.CTkFrame(tab, fg_color="transparent")
        right.pack(side="left", fill="y", padx=(0, 4), pady=8)

        ctk.CTkLabel(left, text="Personaje origen (main):", text_color=TEXT,
                     font=title_font(13)).pack(anchor="w")
        self.char_src = ctk.StringVar()
        self.char_src_box = ctk.CTkComboBox(
            left, variable=self.char_src, values=[], state="readonly",
            fg_color=FIELD, border_color=GOLD_DIM, button_color=GOLD_DIM,
            button_hover_color=GOLD, dropdown_fg_color=FIELD,
            text_color=TEXT, corner_radius=8, width=340,
        )
        self.char_src_box.pack(anchor="w", pady=(4, 12))

        ctk.CTkLabel(left, text="Personajes destino:", text_color=TEXT,
                     font=title_font(13)).pack(anchor="w")
        self.char_dst_list = CheckList(left, height=170)
        self.char_dst_list.pack(fill="x", pady=(4, 12))

        opts_panel = ctk.CTkFrame(left, fg_color=FIELD, corner_radius=10,
                                   border_width=1, border_color=GOLD_DIM)
        opts_panel.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(opts_panel, text="Qué copiar", text_color=GOLD,
                     font=title_font(12, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        self.opt_vars = {}
        labels = [("config", "Config general (config-cache.wtf)"),
                  ("bindings", "Bindeos (bindings-cache.wtf)"),
                  ("macros", "Macros (macros-cache.txt)"),
                  ("layout", "Layout de UI (layout-cache.txt)"),
                  ("addons", "Lista de addons activados (addons.txt)"),
                  ("savedvars", "SavedVariables (addons)")]
        grid = ctk.CTkFrame(opts_panel, fg_color="transparent")
        grid.pack(fill="x", padx=8, pady=(0, 8))
        for i, (key, label) in enumerate(labels):
            v = ctk.BooleanVar(value=True)
            self.opt_vars[key] = v
            cb = ctk.CTkCheckBox(grid, text=label, variable=v, text_color=TEXT,
                                  fg_color=GOLD, hover_color=GOLD_HI, border_color=GOLD_DIM,
                                  checkmark_color="#1a1610", font=title_font(12))
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=6, pady=3)

        gold_button(left, "Enviar a los demás", self.run_char_sync).pack(anchor="w")

        gold_button(right, "Seleccionar todos", lambda: self.char_dst_list.select_all(), small=True).pack(fill="x", pady=3)
        gold_button(right, "Deseleccionar todos", lambda: self.char_dst_list.select_none(), small=True).pack(fill="x", pady=3)

    def _build_exclusions_tab(self, tab):
        ctk.CTkLabel(
            tab, text="Addons que NUNCA se copian (SavedVariables), por nombre exacto sin \".lua\":",
            text_color=TEXT, font=title_font(13), wraplength=560, justify="left",
        ).pack(anchor="w", padx=6, pady=(8, 6))

        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", padx=6)
        self.exc_entry = ctk.CTkEntry(row, width=260, fg_color=FIELD,
                                       border_color=GOLD_DIM, text_color=TEXT, corner_radius=8,
                                       placeholder_text="ej: ActionBarSaver")
        self.exc_entry.pack(side="left")
        gold_button(row, "Agregar", self.add_exclude, small=True).pack(side="left", padx=6)

        self.exc_list_frame = ctk.CTkScrollableFrame(
            tab, fg_color=FIELD, corner_radius=10, border_width=1,
            border_color=GOLD_DIM, height=260,
        )
        self.exc_list_frame.pack(fill="both", expand=True, padx=6, pady=10)
        self._refresh_exclude_rows()

        ctk.CTkLabel(
            tab, text="Todo lo que NO esté en esta lista se copia normalmente.",
            text_color=TEXT_DIM, font=title_font(11), justify="left",
        ).pack(anchor="w", padx=6)

    def _refresh_exclude_rows(self):
        for w in self.exc_list_frame.winfo_children():
            w.destroy()
        for name in self.excludes:
            row = ctk.CTkFrame(self.exc_list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=name, text_color=TEXT, font=title_font(12)).pack(side="left", padx=4)
            ctk.CTkButton(row, text="Quitar", width=70, height=24,
                          fg_color="transparent", hover_color="#3a241f",
                          text_color=DANGER, border_width=1, border_color=DANGER,
                          corner_radius=6, font=title_font(11),
                          command=lambda n=name: self.remove_exclude(n)).pack(side="right", padx=4)

    def add_exclude(self):
        name = self.exc_entry.get().strip()
        if not name:
            return
        name = os.path.splitext(name)[0]
        if name not in self.excludes:
            self.excludes.append(name)
            self.excludes.sort()
            save_excludes(self.excludes)
            self._refresh_exclude_rows()
        self.exc_entry.delete(0, "end")

    def remove_exclude(self, name):
        if name in self.excludes:
            self.excludes.remove(name)
            save_excludes(self.excludes)
            self._refresh_exclude_rows()

    # -------------------------------------------------------------- log --
    def _build_log(self):
        ctk.CTkLabel(self, text="Registro", text_color=GOLD,
                     font=title_font(13, "bold")).pack(anchor="w", padx=22)
        self.logw = ctk.CTkTextbox(
            self, height=150, fg_color=FIELD, text_color=GOLD_HI,
            corner_radius=12, border_width=2, border_color=GOLD,
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self.logw.pack(fill="both", expand=True, padx=18, pady=(4, 16))
        self.logw.configure(state="disabled")

    # ----------------------------------------------------- wtf / listas --
    def browse(self):
        d = filedialog.askdirectory(title="Seleccioná la carpeta WTF")
        if d:
            self.wtf_root.set(d)
            self.reload()

    def reload(self):
        root = self.wtf_root.get().strip()
        if not root or not os.path.isdir(root):
            self._popup_error("Carpeta WTF inválida.")
            return
        accounts = list_accounts(root)
        self.acc_src_box.configure(values=accounts)
        if accounts:
            self.acc_src_box.set(accounts[0])
        self.acc_dst_list.set_items(accounts)

        chars = list_characters(root)
        self._char_map = {}
        display = []
        for acc, realm, char, path in chars:
            key = f"{acc} / {realm} / {char}"
            self._char_map[key] = path
            display.append(key)
        self.char_src_box.configure(values=display)
        if display:
            self.char_src_box.set(display[0])
        self.char_dst_list.set_items(display)

        log(self.logw, f"Cargado: {len(accounts)} cuentas, {len(chars)} personajes.")

    def _popup_error(self, msg):
        win = ctk.CTkToplevel(self)
        win.title("Error")
        win.configure(fg_color=PANEL)
        win.geometry("340x120")
        ctk.CTkLabel(win, text=msg, text_color=TEXT, wraplength=300).pack(padx=16, pady=16)
        gold_button(win, "Cerrar", win.destroy).pack(pady=6)

    def _popup_confirm(self, msg, on_yes):
        win = ctk.CTkToplevel(self)
        win.title("Confirmar")
        win.configure(fg_color=PANEL)
        win.geometry("420x160")
        ctk.CTkLabel(win, text=msg, text_color=TEXT, wraplength=380, justify="left").pack(padx=16, pady=16)
        row = ctk.CTkFrame(win, fg_color="transparent")
        row.pack(pady=6)

        def _yes():
            win.destroy()
            on_yes()

        gold_button(row, "Confirmar", _yes).pack(side="left", padx=6)
        gold_button(row, "Cancelar", win.destroy).pack(side="left", padx=6)

    def run_account_sync(self):
        root = self.wtf_root.get().strip()
        src = self.acc_src.get()
        dsts = [d for d in self.acc_dst_list.selected() if d != src]
        if not src or not dsts:
            self._popup_error("Elegí cuenta origen y al menos un destino distinto.")
            return

        def _do():
            sync_account(root, src, dsts, self.excludes, self.logw)
            log(self.logw, "Listo.")

        self._popup_confirm(f"Se va a sobrescribir la config de: {', '.join(dsts)}. ¿Seguir?", _do)

    def run_char_sync(self):
        root = self.wtf_root.get().strip()
        src_key = self.char_src.get()
        dst_keys = [k for k in self.char_dst_list.selected() if k != src_key]
        if not src_key or not dst_keys:
            self._popup_error("Elegí personaje origen y al menos un destino distinto.")
            return
        options = {k: v.get() for k, v in self.opt_vars.items()}
        if not any(options.values()):
            self._popup_error("Marcá al menos una opción para copiar.")
            return

        def _do():
            src_path = self._char_map[src_key]
            dst_paths = [self._char_map[k] for k in dst_keys]
            sync_character(src_path, dst_paths, options, self.excludes, self.logw)
            log(self.logw, "Listo.")

        self._popup_confirm(f"Se va a sobrescribir la config de {len(dst_keys)} personaje(s). ¿Seguir?", _do)


if __name__ == "__main__":
    App().mainloop()
