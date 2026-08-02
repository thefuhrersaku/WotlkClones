#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WoW Config Sync - 3.3.5a  (interfaz con Flet)

Copia (nunca linkea) SavedVariables, config-cache.wtf, macros-cache.txt,
layout-cache.txt, addons.txt y bindings-cache.wtf entre cuentas/personajes.
Antes de copiar cada archivo: borra el homónimo en destino y cualquier
.bak/.old sueltos en esa carpeta.

Requiere: pip install flet
Ejecutar: python wow_config_sync.py
Empaquetar a exe (Windows): pip install flet flet-cli && flet pack wow_config_sync.py --name wow_config_sync
"""

import os
import sys
import json
import shutil
import flet as ft

# ================================================================== paleta
BG        = "#090b10"
PANEL_A   = "#151b28"
PANEL_B   = "#0d1119"
FIELD     = "#10151f"
GOLD      = "#c8a24c"
GOLD_HI   = "#f2ca77"
GOLD_DIM  = "#5a4a26"
ICE       = "#5fb0cf"
TEXT      = "#eef1f5"
TEXT_DIM  = "#8b93a3"
DANGER    = "#c0604c"
OK        = "#6fae6f"

ACCOUNT_CONFIG_FILES = {"config-cache.wtf": "Config general", "macros-cache.txt": "Macros"}
CHARACTER_CONFIG_FILES = {
    "config-cache.wtf": "Config general",
    "macros-cache.txt": "Macros",
    "layout-cache.txt": "Layout de UI",
    "addons.txt": "Lista de addons activados",
}
BINDINGS_FILE = "bindings-cache.wtf"
JUNK_SUFFIXES = (".bak", ".old")
DEFAULT_ADDON_EXCLUDES = ["ActionBarSaver"]

# ============================================================ persistencia
def settings_path():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "wow_config_sync_settings.json")


def load_settings():
    p = settings_path()
    default = {
        "wtf_root": "",
        "src": {},                 # ej: {"addons_account": "RAMIROVELEZ", ...}
        "addon_excludes": list(DEFAULT_ADDON_EXCLUDES),
        "config_excludes": [],     # nombres de archivo excluidos (config-cache.wtf, etc.)
        "templates": [],           # [{"name": ..., "jobs": [...]}]
    }
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in default.items():
                data.setdefault(k, v)
            return data
        except (OSError, json.JSONDecodeError):
            pass
    return default


def save_settings(s):
    try:
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ================================================================ lógica de copia
def clean_junk(dst_dir, log_cb):
    if not os.path.isdir(dst_dir):
        return
    for name in os.listdir(dst_dir):
        if name.lower().endswith(JUNK_SUFFIXES):
            p = os.path.join(dst_dir, name)
            try:
                os.remove(p)
                log_cb(f"  borrado basura: {p}")
            except OSError as e:
                log_cb(f"  ERROR borrando {p}: {e}")


def copy_replace(src_file, dst_dir, log_cb):
    if not os.path.isfile(src_file):
        return
    os.makedirs(dst_dir, exist_ok=True)
    dst_file = os.path.join(dst_dir, os.path.basename(src_file))
    if os.path.exists(dst_file) or os.path.islink(dst_file):
        try:
            os.remove(dst_file)
        except OSError as e:
            log_cb(f"  ERROR borrando {dst_file}: {e}")
            return
    shutil.copy2(src_file, dst_file)
    log_cb(f"  copiado: {src_file} -> {dst_file}")


def is_excluded(filename, excludes):
    return os.path.splitext(filename)[0] in excludes


def copy_savedvariables(src_root, dst_root, excludes, log_cb):
    src_sv = os.path.join(src_root, "SavedVariables")
    dst_sv = os.path.join(dst_root, "SavedVariables")
    if not os.path.isdir(src_sv):
        return
    clean_junk(dst_sv, log_cb)
    os.makedirs(dst_sv, exist_ok=True)
    for name in os.listdir(src_sv):
        if name.lower().endswith(JUNK_SUFFIXES):
            continue
        if is_excluded(name, excludes):
            log_cb(f"  omitido (exclusión): {name}")
            continue
        copy_replace(os.path.join(src_sv, name), dst_sv, log_cb)


def list_accounts(wtf_root):
    acc_dir = os.path.join(wtf_root, "Account")
    if not os.path.isdir(acc_dir):
        return []
    return sorted(d for d in os.listdir(acc_dir) if os.path.isdir(os.path.join(acc_dir, d)))


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


def scan_all_addons(wtf_root):
    """Nombres base (sin .lua) de todos los addons con SavedVariables en todo el WTF."""
    names = set()
    acc_dir = os.path.join(wtf_root, "Account")
    if not os.path.isdir(acc_dir):
        return []
    for acc in list_accounts(wtf_root):
        sv = os.path.join(acc_dir, acc, "SavedVariables")
        if os.path.isdir(sv):
            for n in os.listdir(sv):
                if not n.lower().endswith(JUNK_SUFFIXES):
                    names.add(os.path.splitext(n)[0])
    for acc, realm, char, path in list_characters(wtf_root):
        sv = os.path.join(path, "SavedVariables")
        if os.path.isdir(sv):
            for n in os.listdir(sv):
                if not n.lower().endswith(JUNK_SUFFIXES):
                    names.add(os.path.splitext(n)[0])
    return sorted(names)


def sync_addons_account(wtf_root, src, dsts, excludes, log_cb):
    src_dir = os.path.join(wtf_root, "Account", src)
    for dst in dsts:
        dst_dir = os.path.join(wtf_root, "Account", dst)
        log_cb(f"\n== Addons cuenta: {src} -> {dst} ==")
        copy_savedvariables(src_dir, dst_dir, excludes, log_cb)


def sync_addons_character(src_path, dst_paths, excludes, log_cb):
    for dst_path in dst_paths:
        log_cb(f"\n== Addons personaje: {src_path} -> {dst_path} ==")
        copy_savedvariables(src_path, dst_path, excludes, log_cb)


def sync_configs_account(wtf_root, src, dsts, excluded_files, log_cb):
    src_dir = os.path.join(wtf_root, "Account", src)
    for dst in dsts:
        dst_dir = os.path.join(wtf_root, "Account", dst)
        log_cb(f"\n== Config cuenta: {src} -> {dst} ==")
        clean_junk(dst_dir, log_cb)
        for fname in ACCOUNT_CONFIG_FILES:
            if fname in excluded_files:
                continue
            copy_replace(os.path.join(src_dir, fname), dst_dir, log_cb)


def sync_configs_character(src_path, dst_paths, excluded_files, log_cb):
    for dst_path in dst_paths:
        log_cb(f"\n== Config personaje: {src_path} -> {dst_path} ==")
        clean_junk(dst_path, log_cb)
        for fname in CHARACTER_CONFIG_FILES:
            if fname in excluded_files:
                continue
            copy_replace(os.path.join(src_path, fname), dst_path, log_cb)


def sync_bindings_account(wtf_root, src, dsts, log_cb):
    src_dir = os.path.join(wtf_root, "Account", src)
    for dst in dsts:
        dst_dir = os.path.join(wtf_root, "Account", dst)
        log_cb(f"\n== Bindeos cuenta: {src} -> {dst} ==")
        clean_junk(dst_dir, log_cb)
        copy_replace(os.path.join(src_dir, BINDINGS_FILE), dst_dir, log_cb)


def sync_bindings_character(src_path, dst_paths, log_cb):
    for dst_path in dst_paths:
        log_cb(f"\n== Bindeos: {src_path} -> {dst_path} ==")
        clean_junk(dst_path, log_cb)
        copy_replace(os.path.join(src_path, BINDINGS_FILE), dst_path, log_cb)


JOB_RUNNERS = {
    ("addons", "account"): lambda wtf, src, dsts, s, log: sync_addons_account(wtf, src, dsts, s["addon_excludes"], log),
    ("addons", "character"): lambda wtf, src, dsts, s, log: sync_addons_character(src, dsts, s["addon_excludes"], log),
    ("configs", "account"): lambda wtf, src, dsts, s, log: sync_configs_account(wtf, src, dsts, s["config_excludes"], log),
    ("configs", "character"): lambda wtf, src, dsts, s, log: sync_configs_character(src, dsts, s["config_excludes"], log),
    ("bindings", "character"): lambda wtf, src, dsts, s, log: sync_bindings_character(src, dsts, log),
    ("bindings", "account"): lambda wtf, src, dsts, s, log: sync_bindings_account(wtf, src, dsts, log),
}


# ======================================================================= UI
def main(page: ft.Page):
    page.title = "WoW Config Sync"
    page.bgcolor = BG
    page.window.width = 980
    page.window.height = 860
    page.window.min_width = 760
    page.window.min_height = 640
    page.window.maximized = True
    page.padding = 0

    settings = load_settings()
    state = {
        "wtf_root": settings["wtf_root"],
        "accounts": [],
        "char_map": {},   # "acc / realm / char" -> path
        "panels": {},      # (kind, scope) -> {"src": Dropdown, "checks": {name: Checkbox}, "column": Column}
    }

    def log_cb(text):
        log_view.controls.append(ft.Text(text, color=GOLD_HI, font_family="Consolas", size=12, selectable=True))
        page.update()

    def snack(msg, color=DANGER):
        page.show_dialog(ft.SnackBar(ft.Text(msg, color=TEXT), bgcolor=color))

    def confirm(msg, on_yes):
        def _yes(e):
            page.pop_dialog()
            on_yes()

        def _no(e):
            page.pop_dialog()

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=PANEL_A,
            title=ft.Text("Confirmar", color=GOLD_HI),
            content=ft.Text(msg, color=TEXT),
            actions=[
                ft.TextButton("Cancelar", on_click=_no, style=ft.ButtonStyle(color=TEXT_DIM)),
                ft.TextButton("Confirmar", on_click=_yes, style=ft.ButtonStyle(color=GOLD_HI)),
            ],
        )
        page.show_dialog(dlg)

    # ---------------------------------------------------------- helpers UI
    def make_tabview(items):
        """items: lista de (label, control). Arma un Tabs funcional con esta versión de flet."""
        bar = ft.TabBar(
            tabs=[ft.Tab(label=lbl) for lbl, _ in items],
            indicator_color=GOLD, label_color=GOLD_HI,
            unselected_label_color=TEXT_DIM, divider_color=GOLD_DIM,
        )
        view = ft.TabBarView(controls=[c for _, c in items], expand=True)
        return ft.Tabs(length=len(items), selected_index=0, expand=True,
                        content=ft.Column([bar, view], expand=True, spacing=6))

    def gold_button(text, on_click, outlined=False, small=False):
        return ft.ElevatedButton(
            content=text,
            on_click=on_click,
            color=GOLD_HI if outlined else "#1a1408",
            bgcolor=FIELD if outlined else GOLD,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=9),
                side=ft.BorderSide(1.2, GOLD_DIM if outlined else GOLD),
                padding=ft.Padding(14, 8 if small else 12, 14, 8 if small else 12),
                text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, size=12 if small else 13),
            ),
        )

    def panel(content, radius=16, pad=18):
        return ft.Container(
            content=content,
            padding=pad,
            border_radius=radius,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                colors=[PANEL_A, PANEL_B],
            ),
            border=ft.Border.all(1.4, GOLD_DIM),
            shadow=ft.BoxShadow(blur_radius=16, spread_radius=1,
                                 color=ft.Colors.with_opacity(0.35, "#000000"),
                                 offset=ft.Offset(0, 5)),
        )

    def field_box(content, height=None):
        return ft.Container(
            content=content, padding=8, border_radius=10, bgcolor=FIELD,
            border=ft.Border.all(1, GOLD_DIM), height=height,
        )

    # ------------------------------------------------- panel cuenta/personaje
    def make_checklist():
        col = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO)
        return field_box(col, height=190), col

    def build_scope_panel(kind, scope, title, items_getter, dst_label):
        """items_getter() -> lista de nombres candidatos (cuentas o 'acc / realm / char')."""
        src_dd = ft.Dropdown(
            options=[], width=340, bgcolor=FIELD, color=TEXT,
            border_color=GOLD_DIM, border_radius=9,
        )

        box, checklist_col = make_checklist()
        checks = {}

        def on_src_change(e):
            settings["src"].setdefault(f"{kind}_{scope}", None)
            settings["src"][f"{kind}_{scope}"] = src_dd.value
            save_settings(settings)

        src_dd.on_select = on_src_change

        search_field = None
        if scope == "character":
            search_field = ft.TextField(
                hint_text="Buscar personaje...", width=220, bgcolor=FIELD, color=TEXT,
                border_color=GOLD_DIM, border_radius=9, dense=True,
                on_change=lambda e: render_rows(),
            )

        def render_rows():
            q = (search_field.value or "").strip().lower() if search_field else ""
            rows = [cb for name, cb in checks.items() if q in name.lower()]
            checklist_col.controls = rows
            page.update()

        def select_all(e):
            q = (search_field.value or "").strip().lower() if search_field else ""
            for name, cb in checks.items():
                if q in name.lower():
                    cb.value = True
            page.update()

        def select_none(e):
            q = (search_field.value or "").strip().lower() if search_field else ""
            for name, cb in checks.items():
                if q in name.lower():
                    cb.value = False
            page.update()

        def do_run():
            wtf = state["wtf_root"]
            src = src_dd.value
            dsts = [n for n, cb in checks.items() if cb.value and n != src]
            if not src or not dsts:
                snack("Elegí origen y al menos un destino distinto.")
                return
            runner = JOB_RUNNERS[(kind, scope)]
            runner(wtf, src, dsts, settings, log_cb)
            log_cb("Listo.")

        def run_click(e):
            confirm(f"Se va a sobrescribir en: {', '.join([n for n, cb in checks.items() if cb.value])}. ¿Seguir?", do_run)

        run_btn = gold_button(f"Enviar a los demás ({title.lower()})", run_click)

        src_row_controls = [src_dd]
        if search_field:
            src_row_controls.append(search_field)

        header_row = ft.Row([
            ft.Column([
                ft.Text(f"{title} origen (main):", color=TEXT, size=13),
                ft.Row(src_row_controls, spacing=8),
            ], spacing=4),
            ft.Column([
                gold_button("Seleccionar todas", select_all, outlined=True, small=True),
                gold_button("Deseleccionar todas", select_none, outlined=True, small=True),
            ], spacing=6),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        col = ft.Column([
            header_row,
            ft.Text(f"{dst_label}:", color=TEXT, size=13),
            box,
            run_btn,
        ], spacing=10)

        state["panels"][(kind, scope)] = {
            "src": src_dd, "checks": checks, "checklist_col": checklist_col,
            "render_rows": render_rows, "search_field": search_field,
            "items_getter": items_getter,
        }
        return panel(col)

    def refresh_panel(kind, scope):
        p = state["panels"][(kind, scope)]
        items = p["items_getter"]()
        p["src"].options = [ft.dropdown.Option(i) for i in items]
        saved_src = settings["src"].get(f"{kind}_{scope}")
        p["src"].value = saved_src if saved_src in items else (items[0] if items else None)

        p["checks"].clear()
        for name in items:
            cb = ft.Checkbox(label=name, value=False, fill_color=GOLD, check_color="#1a1408",
                              label_style=ft.TextStyle(color=TEXT, size=12), on_change=lambda e: None)
            p["checks"][name] = cb
        if p.get("search_field") is not None:
            p["search_field"].value = ""
        p["render_rows"]()

    # -------------------------------------------------------- exclusiones
    def build_addon_excludes_panel():
        box, col = make_checklist()

        def toggle(name):
            def _h(e):
                if e.control.value:
                    if name not in settings["addon_excludes"]:
                        settings["addon_excludes"].append(name)
                else:
                    if name in settings["addon_excludes"]:
                        settings["addon_excludes"].remove(name)
                save_settings(settings)
            return _h

        state["addon_excl_col"] = col
        return panel(ft.Column([
            ft.Text("Addons que NUNCA se copian (SavedVariables):", color=TEXT, size=13),
            ft.Text("Se detectan escaneando la carpeta WTF cargada. Tildado = excluido.", color=TEXT_DIM, size=11),
            box,
        ], spacing=10)), toggle

    addon_excl_panel, addon_toggle_factory = build_addon_excludes_panel()

    def refresh_addon_excludes():
        names = scan_all_addons(state["wtf_root"]) if state["wtf_root"] else []
        rows = []
        for name in names:
            cb = ft.Checkbox(label=name, value=name in settings["addon_excludes"],
                              fill_color=DANGER, check_color="#1a0808",
                              label_style=ft.TextStyle(color=TEXT, size=12))
            cb.on_change = addon_toggle_factory(name)
            rows.append(cb)
        state["addon_excl_col"].controls = rows or [ft.Text("Cargá una carpeta WTF para ver los addons detectados.", color=TEXT_DIM, size=12)]

    def build_config_excludes_panel():
        col = ft.Column(spacing=4)
        rows = []
        all_files = {**ACCOUNT_CONFIG_FILES, **CHARACTER_CONFIG_FILES}

        def toggle(fname):
            def _h(e):
                if e.control.value:
                    if fname not in settings["config_excludes"]:
                        settings["config_excludes"].append(fname)
                else:
                    if fname in settings["config_excludes"]:
                        settings["config_excludes"].remove(fname)
                save_settings(settings)
            return _h

        for fname, label in all_files.items():
            cb = ft.Checkbox(label=f"{label}  ({fname})", value=fname in settings["config_excludes"],
                              fill_color=DANGER, check_color="#1a0808",
                              label_style=ft.TextStyle(color=TEXT, size=12))
            cb.on_change = toggle(fname)
            rows.append(cb)
        col.controls = rows
        return panel(ft.Column([
            ft.Text("Archivos de configuración que NUNCA se copian:", color=TEXT, size=13),
            ft.Text("Aplica tanto a nivel cuenta como personaje (si el archivo no corresponde a ese nivel, se ignora).",
                    color=TEXT_DIM, size=11),
            field_box(col),
        ], spacing=10))

    bindings_excl_note = panel(ft.Text(
        "Los bindeos siempre se copian completos (bindings-cache.wtf), tanto a nivel cuenta como personaje "
        "según cómo tengas configurado \"keybindings por personaje\" en el juego. No hay exclusiones parciales acá.",
        color=TEXT_DIM, size=12))

    # ------------------------------------------------------------ plantillas
    SCOPE_LABELS = {
        ("addons", "account"): "Addons - Cuenta",
        ("addons", "character"): "Addons - Personaje",
        ("configs", "account"): "Configs - Cuenta",
        ("configs", "character"): "Configs - Personaje",
        ("bindings", "account"): "Bindeos - Cuenta",
        ("bindings", "character"): "Bindeos - Personaje",
    }

    templates_col = ft.Column(spacing=8)
    tpl_name_field = ft.TextField(label="Nombre de la plantilla", width=300,
                                   bgcolor=FIELD, color=TEXT, border_color=GOLD_DIM, border_radius=9)
    scope_checks = {}
    scope_rows = []
    for key, label in SCOPE_LABELS.items():
        cb = ft.Checkbox(label=label, value=False, fill_color=GOLD, check_color="#1a1408",
                          label_style=ft.TextStyle(color=TEXT, size=12))
        scope_checks[key] = cb
        scope_rows.append(cb)

    def collect_current_jobs(selected_scopes):
        jobs = []
        missing = []
        for key in selected_scopes:
            p = state["panels"].get(key)
            if not p:
                continue
            kind, scope = key
            src = p["src"].value
            dsts = [n for n, cb in p["checks"].items() if cb.value and n != src]
            if src and dsts:
                jobs.append({"type": kind, "scope": scope, "src": src, "dsts": dsts})
            else:
                missing.append(SCOPE_LABELS[key])
        return jobs, missing

    def apply_jobs(jobs):
        if not state["wtf_root"]:
            snack("Cargá la carpeta WTF primero.")
            return False
        for (kind, scope), p in state["panels"].items():
            p_jobs = [j for j in jobs if j["type"] == kind and j["scope"] == scope]
            if not p_jobs:
                continue
            j = p_jobs[0]
            if j["src"] in [o.key for o in p["src"].options]:
                p["src"].value = j["src"]
            for name, cb in p["checks"].items():
                cb.value = name in j["dsts"]
            if p.get("search_field") is not None:
                p["search_field"].value = ""
            p["render_rows"]()
        page.update()
        return True

    def run_jobs(jobs):
        for j in jobs:
            runner = JOB_RUNNERS.get((j["type"], j["scope"]))
            if runner:
                runner(state["wtf_root"], j["src"], j["dsts"], settings, log_cb)
        log_cb("Plantilla ejecutada.")

    def refresh_templates():
        rows = []
        for tpl in settings["templates"]:
            name = tpl["name"]
            included = ", ".join(SCOPE_LABELS.get((j["type"], j["scope"]), f'{j["type"]}/{j["scope"]}') for j in tpl["jobs"])

            def _apply(e, t=tpl):
                if apply_jobs(t["jobs"]):
                    snack(f'Plantilla "{t["name"]}" aplicada. Revisá y ejecutá cada sección, o usá "Aplicar y ejecutar".', OK)

            def _apply_run(e, t=tpl):
                if apply_jobs(t["jobs"]):
                    run_jobs(t["jobs"])

            def _delete(e, t=tpl):
                settings["templates"].remove(t)
                save_settings(settings)
                refresh_templates()

            rows.append(ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(name, color=GOLD_HI, size=14, weight=ft.FontWeight.BOLD, expand=True),
                        gold_button("Aplicar", _apply, outlined=True, small=True),
                        gold_button("Aplicar y ejecutar", _apply_run, small=True),
                        ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=DANGER, on_click=_delete),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(included or "(sin secciones)", color=TEXT_DIM, size=11),
                ], spacing=4),
                padding=10, border_radius=9, bgcolor=FIELD, border=ft.Border.all(1, GOLD_DIM),
            ))
        templates_col.controls = rows or [ft.Text("Todavía no guardaste ninguna plantilla.", color=TEXT_DIM)]
        page.update()

    def save_template(e):
        name = tpl_name_field.value.strip()
        if not name:
            snack("Ponele un nombre a la plantilla.")
            return
        selected_scopes = [key for key, cb in scope_checks.items() if cb.value]
        if not selected_scopes:
            snack("Tildá al menos una sección (Addons, Configs o Bindeos) para esta plantilla.")
            return
        jobs, missing = collect_current_jobs(selected_scopes)
        if not jobs:
            snack("Ninguna de las secciones tildadas tiene origen + destinos elegidos ahora mismo.")
            return
        settings["templates"] = [t for t in settings["templates"] if t["name"] != name]
        settings["templates"].append({"name": name, "jobs": jobs})
        save_settings(settings)
        tpl_name_field.value = ""
        refresh_templates()
        msg = f'Plantilla "{name}" guardada.'
        if missing:
            msg += f' (sin datos, no incluidas: {", ".join(missing)})'
        snack(msg, OK)

    templates_tab_content = ft.Column([
        panel(ft.Column([
            ft.Text("Guardar la selección actual como plantilla", color=TEXT, size=14, weight=ft.FontWeight.BOLD),
            ft.Text("Elegí qué secciones incluir. Solo se guarda el origen/destino de las secciones tildadas acá, "
                    "las demás quedan afuera aunque tengan algo tildado en su pestaña.",
                    color=TEXT_DIM, size=11),
            field_box(ft.Column(scope_rows, spacing=2)),
            ft.Row([tpl_name_field, gold_button("Guardar plantilla actual", save_template)]),
        ], spacing=8)),
        ft.Container(height=10),
        ft.Text("Plantillas guardadas", color=GOLD, size=15, weight=ft.FontWeight.BOLD),
        templates_col,
    ], spacing=10, scroll=ft.ScrollMode.AUTO)

    # --------------------------------------------------------------- tabs
    def sub_tabs(kind, has_account, has_character, extra_account=None, extra_character=None, extra_excl=None):
        items = []
        if has_account:
            content = build_scope_panel(
                kind, "account", "Cuenta",
                lambda: state["accounts"],
                "Cuentas destino",
            ) if extra_account is None else extra_account
            items.append(("Cuenta", ft.Container(content, padding=14)))
        if has_character:
            content = build_scope_panel(
                kind, "character", "Personaje",
                lambda: list(state["char_map"].keys()),
                "Personajes destino",
            ) if extra_character is None else extra_character
            items.append(("Personaje", ft.Container(content, padding=14)))
        excl = extra_excl if extra_excl is not None else ft.Container()
        items.append(("Exclusiones", ft.Container(excl, padding=14)))
        return make_tabview(items)

    addons_tabs = sub_tabs("addons", True, True, extra_excl=addon_excl_panel)
    configs_excl_panel = build_config_excludes_panel()
    configs_tabs = sub_tabs("configs", True, True, extra_excl=configs_excl_panel)
    bindings_tabs = sub_tabs("bindings", True, True, extra_excl=bindings_excl_note)

    main_tabs = make_tabview([
        ("Addons", addons_tabs),
        ("Configs", configs_tabs),
        ("Bindeos", bindings_tabs),
        ("Plantillas", ft.Container(templates_tab_content, padding=14)),
    ])

    # ------------------------------------------------------------ WTF picker
    wtf_field = ft.TextField(value=state["wtf_root"], width=440, bgcolor=FIELD, color=TEXT,
                              border_color=GOLD_DIM, border_radius=9, label="Carpeta WTF")

    def do_reload():
        root = wtf_field.value.strip()
        if not root or not os.path.isdir(root):
            snack("Carpeta WTF inválida.")
            return
        state["wtf_root"] = root
        settings["wtf_root"] = root
        save_settings(settings)

        state["accounts"] = list_accounts(root)
        chars = list_characters(root)
        state["char_map"] = {f"{a} / {r} / {c}": p for a, r, c, p in chars}

        for kind_scope in [("addons", "account"), ("addons", "character"),
                            ("configs", "account"), ("configs", "character"),
                            ("bindings", "account"), ("bindings", "character")]:
            if kind_scope in state["panels"]:
                refresh_panel(*kind_scope)
        refresh_addon_excludes()
        page.update()
        log_cb(f"Cargado: {len(state['accounts'])} cuentas, {len(chars)} personajes.")

    async def async_browse(e):
        path = await file_picker.get_directory_path(dialog_title="Seleccioná la carpeta WTF")
        if path:
            wtf_field.value = path
            page.update()
            do_reload()

    file_picker = ft.FilePicker()
    page.services = [file_picker]

    # --------------------------------------------------------------- header
    header = panel(ft.Column([
        ft.Text("❖  WoW Config Sync  ❖", color=GOLD_HI, size=24, weight=ft.FontWeight.BOLD),
        ft.Text("Wrath of the Lich King  ·  cliente 3.3.5a", color=TEXT_DIM, size=12, italic=True),
    ], spacing=2), pad=16)

    # ------------------------------------------------------------------ log
    log_view = ft.ListView(spacing=2, auto_scroll=True, expand=True)

    def open_history(e):
        dlg = ft.AlertDialog(
            modal=False,
            bgcolor=PANEL_A,
            title=ft.Text("❖  Historial  ❖", color=GOLD_HI),
            content=ft.Container(
                content=log_view, width=680, height=420, padding=10,
                border_radius=10, bgcolor=FIELD, border=ft.Border.all(1.4, GOLD_DIM),
            ),
            actions=[ft.TextButton("Cerrar", on_click=lambda e: page.pop_dialog(),
                                    style=ft.ButtonStyle(color=GOLD_HI))],
        )
        page.show_dialog(dlg)

    history_btn = gold_button("❖ Historial", open_history, outlined=True)

    wtf_bar = panel(ft.Row([
        wtf_field,
        gold_button("Buscar...", async_browse, outlined=True),
        gold_button("Cargar", lambda e: do_reload()),
        ft.Container(expand=True),
        history_btn,
    ], alignment=ft.MainAxisAlignment.START, spacing=10), pad=14)

    page.add(
        ft.Container(
            content=ft.Column([
                header,
                wtf_bar,
                main_tabs,
            ], spacing=12, expand=True),
            padding=18, expand=True,
        )
    )

    if state["wtf_root"] and os.path.isdir(state["wtf_root"]):
        do_reload()


if __name__ == "__main__":
    ft.app(target=main)
