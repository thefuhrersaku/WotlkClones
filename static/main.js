// WOTLK Clones - Config Sync 3.3.5a (Tauri 2)
const KINDS = ['addons', 'configs', 'bindings'];

const ACCOUNT_CONFIG_FILES = [
  ['config-cache.wtf', 'Config general'],
  ['macros-cache.txt', 'Macros'],
];
const CHARACTER_CONFIG_FILES = [
  ['config-cache.wtf', 'Config general'],
  ['macros-cache.txt', 'Macros'],
  ['layout-cache.txt', 'Layout de UI'],
  ['addons.txt', 'Lista de addons activados'],
];

const KIND_SHORT = { addons: 'Addons', configs: 'Configs', bindings: 'Bindeos' };
const SCOPE_LABELS = {
  addons_account: 'Addons - Cuenta',
  addons_character: 'Addons - Personaje',
  configs_account: 'Configs - Cuenta',
  configs_character: 'Configs - Personaje',
  bindings_account: 'Bindeos - Cuenta',
  bindings_character: 'Bindeos - Personaje',
};

const state = {
  settings: null,
  wtfRoot: '',
  accounts: [],
  charMap: {}, // "acc / realm / char" -> path
  panels: {},  // "kind_scope" -> {srcSelect, checks:{name:input}, listEl, searchEl, render}
  addonExclListEl: null,
  scopeChecks: {},
  templatesColEl: null,
  logLines: [],
};

// ================================================================ helpers
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') node.className = v;
    else if (k === 'text') node.textContent = v;
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (typeof c === 'string') node.appendChild(document.createTextNode(c));
    else if (c) node.appendChild(c);
  }
  return node;
}

function btn(text, cls = '', onClick) {
  const b = el('button', { class: 'btn' + (cls ? ' ' + cls : ''), text });
  b.onclick = onClick;
  return b;
}

function invoke(cmd, args) {
  return window.__TAURI__.core.invoke(cmd, args);
}

function saveSettings() {
  invoke('save_settings', { settingsData: state.settings }).catch((e) => console.error(e));
}

let snackTimer;
function snack(msg, ok = false) {
  const sb = document.getElementById('snackbar');
  sb.textContent = msg;
  sb.classList.remove('hidden');
  if (ok) sb.classList.add('ok');
  else sb.classList.remove('ok');
  clearTimeout(snackTimer);
  snackTimer = setTimeout(() => sb.classList.add('hidden'), 3500);
}

function logClass(t) {
  const s = t.trim();
  if (/ERROR/i.test(s)) return 'log-error';
  if (/^==.*==$/.test(s)) return 'log-head';
  if (/^  /.test(s)) return 'log-dim';
  if (/^(Listo|Plantilla ejecutada)/.test(s)) return 'log-ok';
  return '';
}

function log(text) {
  const lv = document.getElementById('logView');
  for (const part of String(text).split('\n')) {
    if (!part.trim()) continue;
    state.logLines.push(part);
    const cls = logClass(part);
    lv.appendChild(el('div', { class: 'log-line' + (cls ? ' ' + cls : ''), text: part }));
    lv.scrollTop = lv.scrollHeight;
  }
}

function confirm(msg, onYes) {
  const ov = document.getElementById('confirmOverlay');
  document.getElementById('confirmText').textContent = msg;
  ov.classList.remove('hidden');
  document.getElementById('confirmYes').onclick = () => {
    ov.classList.add('hidden');
    onYes();
  };
  document.getElementById('confirmNo').onclick = () => ov.classList.add('hidden');
}

function openHistory() {
  document.getElementById('historyOverlay').classList.remove('hidden');
}

// ================================================================ progreso
let progressDone = 0;
let progressTotal = 0;
let progressUnlisten = null;

function setProgressFill(frac) {
  const fill = document.getElementById('progressFill');
  fill.style.width = Math.round(Math.min(1, Math.max(0, frac)) * 100) + '%';
}

async function startProgress(total, title) {
  progressDone = 0;
  progressTotal = Math.max(total, 1);
  document.getElementById('progressTitle').textContent = title;
  document.getElementById('progressText').textContent = 'Preparando...';
  setProgressFill(0);
  document.getElementById('progressOverlay').classList.remove('hidden');
  if (!progressUnlisten) {
    try {
      progressUnlisten = await window.__TAURI__.event.listen('sync-progress', (e) => {
        const { done, current } = e.payload;
        if (done > 0) progressDone = Math.min(progressDone + 1, progressTotal);
        setProgressFill(progressDone / progressTotal);
        if (current) document.getElementById('progressText').textContent = 'Copiando a: ' + current;
      });
    } catch (err) {
      console.error(err);
    }
  }
}

function finishProgress(ok, msg) {
  if (progressUnlisten) {
    progressUnlisten();
    progressUnlisten = null;
  }
  document.getElementById('progressOverlay').classList.add('hidden');
  setProgressFill(0);
  if (ok) {
    document.getElementById('successText').textContent = msg;
    document.getElementById('successOverlay').classList.remove('hidden');
  }
}

function makeTabs(items) {
  const bar = el('div', { class: 'tabbar' });
  const view = el('div', { class: 'tabview' });
  const buttons = [];
  items.forEach((it, i) => {
    const b = el('button', { class: 'tab', text: it.label });
    b.onclick = () => setActive(i);
    bar.appendChild(b);
    buttons.push(b);
    const pane = el('div', { class: 'tabview-pane' });
    pane.appendChild(it.element);
    view.appendChild(pane);
    it._pane = pane;
  });
  function setActive(i) {
    buttons.forEach((b, j) => b.classList.toggle('active', j === i));
    items.forEach((it, j) => (it._pane.style.display = j === i ? '' : 'none'));
  }
  setActive(0);
  return el('div', { class: 'tabs-wrap', style: 'display:flex;flex-direction:column;flex:1;min-height:0' }, bar, view);
}

// ============================================================== paneles de scope
function buildScopePanel(kind, scope) {
  const title = scope === 'account' ? 'Cuenta' : 'Personaje';
  const dstLabel = scope === 'account' ? 'Cuentas destino:' : 'Personajes destino:';

  const srcSelect = el('select');
  const searchEl =
    scope === 'character'
      ? el('input', { type: 'text', class: 'search', placeholder: 'Buscar personaje...' })
      : null;

  const listEl = el('div', { class: 'checklist' });
  const box = el('div', { class: 'checklist-box' }, listEl);
  const checks = {};

  function items() {
    return scope === 'account' ? state.accounts : Object.keys(state.charMap);
  }
  function filtered() {
    const q = (searchEl?.value || '').trim().toLowerCase();
    return Object.keys(checks).filter((n) => (q ? n.toLowerCase().includes(q) : true));
  }
  function render() {
    listEl.textContent = '';
    const names = filtered();
    for (const n of names) {
      const input = checks[n];
      const label = el('label', { class: 'check' }, input, el('span', { class: 'name', text: n }));
      listEl.appendChild(label);
    }
    if (!names.length) listEl.appendChild(el('div', { class: 'empty-hint', text: 'Sin resultados.' }));
  }

  const selectAllBtn = btn('Seleccionar todas', 'outline small', () => {
    const q = (searchEl?.value || '').trim().toLowerCase();
    for (const n of Object.keys(checks)) if (!q || n.toLowerCase().includes(q)) checks[n].checked = true;
  });
  const selectNoneBtn = btn('Deseleccionar todas', 'outline small', () => {
    for (const n of Object.keys(checks)) checks[n].checked = false;
  });

  const runBtn = btn(`Enviar a los demás (${title.toLowerCase()})`, 'run', () => {
    const src = srcSelect.value;
    const dsts = Object.keys(checks).filter((n) => checks[n].checked && n !== src);
    if (!src || !dsts.length) {
      snack('Elegí origen y al menos un destino distinto.');
      return;
    }
    confirm(`Se va a sobrescribir en: ${dsts.join(', ')}. ¿Seguir?`, () => doRun(src, dsts));
  });

  async function doRun(src, dsts) {
    await startProgress(dsts.length, `Enviando ${KIND_SHORT[kind]} a los demás...`);
    try {
      const lines = await invoke('run_sync', {
        jobType: kind, scope, wtfRoot: state.wtfRoot, src, dsts, settingsData: state.settings,
      });
      lines.forEach((l) => log(l));
      log('Listo.');
      finishProgress(true, `${KIND_SHORT[kind]} aplicados correctamente.`);
    } catch (e) {
      log('ERROR: ' + e);
      snack('Error: ' + e);
      finishProgress(false);
    }
  }

  const panelEl = el(
    'div',
    { class: 'panel scope-panel' },
    el(
      'div',
      { class: 'scope-head' },
      el(
        'div',
        { class: 'row' },
        el('div', { class: 'field-label', text: `${KIND_SHORT[kind]} origen (main):` }),
        srcSelect,
        searchEl
      ),
      el('div', { class: 'scope-head-right' }, selectAllBtn, selectNoneBtn)
    ),
    el('div', { class: 'field-label', text: dstLabel }),
    box,
    runBtn
  );

  srcSelect.onchange = () => {
    state.settings.src[`${kind}_${scope}`] = srcSelect.value;
    saveSettings();
  };
  if (searchEl) searchEl.oninput = render;

  state.panels[`${kind}_${scope}`] = { srcSelect, checks, listEl, searchEl, render };
  return panelEl;
}

function refreshPanel(kind, scope) {
  const p = state.panels[`${kind}_${scope}`];
  if (!p) return;
  const items = scope === 'account' ? state.accounts : Object.keys(state.charMap);
  p.srcSelect.textContent = '';
  for (const it of items) p.srcSelect.appendChild(el('option', { value: it, text: it }));
  const saved = state.settings.src[`${kind}_${scope}`];
  p.srcSelect.value = saved && items.includes(saved) ? saved : items[0] || '';
  for (const k of Object.keys(p.checks)) delete p.checks[k];
  for (const it of items) {
    const cb = el(
      'label',
      { class: 'check' },
      el('input', { type: 'checkbox' }),
      el('span', { class: 'name', text: it })
    );
    p.checks[it] = cb.querySelector('input');
  }
  if (p.searchEl) p.searchEl.value = '';
  p.render();
}

// ================================================================ exclusiones
function buildAddonExclPanel() {
  const listEl = el('div', { class: 'checklist' });
  const box = el('div', { class: 'checklist-box' }, listEl);
  state.addonExclListEl = listEl;
  return el(
    'div',
    { class: 'panel scope-panel' },
    el('div', { class: 'field-label', text: 'Addons que NUNCA se copian (SavedVariables):' }),
    el('div', { class: 'note-text', text: 'Se detectan escaneando la carpeta WTF cargada. Tildado = excluido.' }),
    box
  );
}

async function refreshAddonExcludes() {
  const listEl = state.addonExclListEl;
  if (!listEl) return;
  listEl.textContent = '';
  let names = [];
  if (state.wtfRoot) {
    try {
      names = await invoke('scan_all_addons', { wtfRoot: state.wtfRoot });
    } catch (e) {
      /* ignore */
    }
  }
  for (const name of names) {
    const cb = el(
      'label',
      { class: 'check excl' },
      el('input', { type: 'checkbox' }),
      el('span', { class: 'name', text: name })
    );
    const input = cb.querySelector('input');
    input.checked = state.settings.addon_excludes.includes(name);
    input.onchange = () => {
      if (input.checked) {
        if (!state.settings.addon_excludes.includes(name)) state.settings.addon_excludes.push(name);
      } else {
        state.settings.addon_excludes = state.settings.addon_excludes.filter((x) => x !== name);
      }
      saveSettings();
    };
    listEl.appendChild(cb);
  }
  if (!names.length)
    listEl.appendChild(el('div', { class: 'empty-hint', text: 'Cargá una carpeta WTF para ver los addons detectados.' }));
}

function buildConfigExclPanel() {
  const listEl = el('div', { class: 'checklist' });
  const all = [...ACCOUNT_CONFIG_FILES, ...CHARACTER_CONFIG_FILES];
  for (const [fname, label] of all) {
    const cb = el(
      'label',
      { class: 'check excl' },
      el('input', { type: 'checkbox' }),
      el('span', { class: 'name', text: `${label}  (${fname})` })
    );
    const input = cb.querySelector('input');
    input.checked = state.settings.config_excludes.includes(fname);
    input.onchange = () => {
      if (input.checked) {
        if (!state.settings.config_excludes.includes(fname)) state.settings.config_excludes.push(fname);
      } else {
        state.settings.config_excludes = state.settings.config_excludes.filter((x) => x !== fname);
      }
      saveSettings();
    };
    listEl.appendChild(cb);
  }
  const box = el('div', { class: 'checklist-box' }, listEl);
  return el(
    'div',
    { class: 'panel scope-panel' },
    el('div', { class: 'field-label', text: 'Archivos de configuración que NUNCA se copian:' }),
    el('div', {
      class: 'note-text',
      text: 'Aplica tanto a nivel cuenta como personaje (si el archivo no corresponde a ese nivel, se ignora).',
    }),
    box
  );
}

function buildBindingsNote() {
  return el(
    'div',
    { class: 'panel' },
    el('div', {
      class: 'note-text',
      text: 'Los bindeos siempre se copian completos (bindings-cache.wtf), tanto a nivel cuenta como personaje según cómo tengas configurado "keybindings por personaje" en el juego. No hay exclusiones parciales acá.',
    })
  );
}

// ================================================================ plantillas
function buildTemplatesTab() {
  const scopeChecksRow = el('div', { class: 'scope-checks-row' });

  function makeScopeColumn(scope, heading) {
    const col = el('div', { class: 'scope-checks-col' }, el('div', { class: 'heading', text: heading }));
    for (const kind of KINDS) {
      const cb = el(
        'label',
        { class: 'check' },
        el('input', { type: 'checkbox' }),
        el('span', { class: 'name', text: KIND_SHORT[kind] })
      );
      const input = cb.querySelector('input');
      state.scopeChecks[`${kind}_${scope}`] = input;
      col.appendChild(cb);
    }
    return col;
  }

  scopeChecksRow.appendChild(
    el(
      'div',
      { class: 'row' },
      makeScopeColumn('account', 'Cuenta'),
      el('div', { class: 'v-divider' }),
      makeScopeColumn('character', 'Personaje')
    )
  );

  const nameField = el('input', { type: 'text', placeholder: 'Nombre de la plantilla', style: 'width:300px' });

  const backupCheck = el(
    'label',
    { class: 'check' },
    el('input', { type: 'checkbox' }),
    el('span', { class: 'name', text: 'Hacer backup automático antes de aplicar' })
  );
  const backupInput = backupCheck.querySelector('input');
  backupInput.checked = !!state.settings.backup_enabled;
  backupInput.onchange = () => {
    state.settings.backup_enabled = backupInput.checked;
    saveSettings();
  };

  function saveTemplate() {
    const name = nameField.value.trim();
    if (!name) {
      snack('Ponele un nombre a la plantilla.');
      return;
    }
    const selected = Object.keys(state.scopeChecks).filter((k) => state.scopeChecks[k].checked);
    if (!selected.length) {
      snack('Tildá al menos una sección (Addons, Configs o Bindeos) para esta plantilla.');
      return;
    }
    const { jobs, missing } = collectCurrentJobs(selected);
    if (!jobs.length) {
      snack('Ninguna de las secciones tildadas tiene origen + destinos elegidos ahora mismo.');
      return;
    }
    state.settings.templates = state.settings.templates.filter((t) => t.name !== name);
    state.settings.templates.push({ name, jobs });
    saveSettings();
    nameField.value = '';
    refreshTemplates();
    let msg = `Plantilla "${name}" guardada.`;
    if (missing.length) msg += ` (sin datos, no incluidas: ${missing.join(', ')})`;
    snack(msg, true);
  }

  const left = el(
    'div',
    { class: 'templates-left' },
    el(
      'div',
      { class: 'panel scope-panel' },
      el('div', { class: 'field-label', text: 'Guardar la selección actual como plantilla', style: 'font-size:14px;font-weight:700' }),
      el('div', {
        class: 'note-text',
        text: 'Elegí qué secciones incluir. Solo se guarda el origen/destino de las secciones tildadas acá, las demás quedan afuera aunque tengan algo tildado en su pestaña.',
      }),
      el('div', { class: 'checklist-box', style: 'height:auto' }, scopeChecksRow),
      el('div', { class: 'row' }, nameField, btn('Guardar plantilla actual', '', saveTemplate)),
      el('div', { class: 'row' }, backupCheck),
      el('div', {
        class: 'note-text',
        text: 'Antes de sobrescribir se guarda una copia de lo que había en la carpeta de configuración de la app (backups).',
      })
    )
  );

  const templatesCol = el('div', { class: 'templates-col' });
  state.templatesColEl = templatesCol;
  const right = el(
    'div',
    { class: 'templates-right' },
    el('div', { class: 'field-label', text: 'Plantillas guardadas', style: 'color:var(--gold);font-size:15px;font-weight:700' }),
    templatesCol
  );

  return el('div', { class: 'templates-tab' }, left, right);
}

function collectCurrentJobs(selectedScopes) {
  const jobs = [];
  const missing = [];
  for (const key of selectedScopes) {
    const p = state.panels[key];
    if (!p) continue;
    const [kind, scope] = key.split('_');
    const src = p.srcSelect.value;
    const dsts = Object.keys(p.checks).filter((n) => p.checks[n].checked && n !== src);
    if (src && dsts.length) jobs.push({ type: kind, scope, src, dsts });
    else missing.push(SCOPE_LABELS[key]);
  }
  return { jobs, missing };
}

function applyJobs(jobs) {
  if (!state.wtfRoot) {
    snack('Cargá la carpeta WTF primero.');
    return false;
  }
  for (const key of Object.keys(state.panels)) {
    const p = state.panels[key];
    const pJobs = jobs.filter((j) => `${j.type}_${j.scope}` === key);
    if (pJobs.length) {
      const j = pJobs[0];
      const options = Array.from(p.srcSelect.options).map((o) => o.value);
      if (options.includes(j.src)) p.srcSelect.value = j.src;
      for (const n of Object.keys(p.checks)) p.checks[n].checked = j.dsts.includes(n);
    } else {
      for (const n of Object.keys(p.checks)) p.checks[n].checked = false;
    }
    if (p.searchEl) p.searchEl.value = '';
    p.render();
  }
  return true;
}

async function runJobs(jobs) {
  const total = jobs.reduce((n, j) => n + j.dsts.length, 0);
  if (!total) {
    snack('No hay destinos para ejecutar.');
    return;
  }
  await startProgress(total, `Aplicando plantilla (${jobs.length} sección${jobs.length === 1 ? '' : 'es'})...`);
  let hadError = false;
  try {
    for (const j of jobs) {
      try {
        const lines = await invoke('run_sync', {
          jobType: j.type, scope: j.scope, wtfRoot: state.wtfRoot, src: j.src, dsts: j.dsts, settingsData: state.settings,
        });
        lines.forEach((l) => log(l));
      } catch (e) {
        hadError = true;
        log('ERROR: ' + e);
      }
    }
    log('Plantilla ejecutada.');
    finishProgress(true, hadError ? 'Plantilla aplicada con errores. Revisá el Historial.' : 'Plantilla aplicada correctamente.');
  } catch (e) {
    hadError = true;
    log('ERROR: ' + e);
    finishProgress(false);
  }
}

function refreshTemplates() {
  const col = state.templatesColEl;
  col.textContent = '';
  for (const tpl of state.settings.templates) {
    const included = tpl.jobs
      .map((j) => SCOPE_LABELS[`${j.type}_${j.scope}`] || `${j.type}/${j.scope}`)
      .join(', ');
    const applyBtn = btn('Aplicar', 'outline small', () => {
      if (applyJobs(tpl.jobs))
        snack(`Plantilla "${tpl.name}" aplicada. Revisá y ejecutá cada sección, o usá "Aplicar y ejecutar".`, true);
    });
    const applyRunBtn = btn('Aplicar y ejecutar', 'small', () => {
      if (applyJobs(tpl.jobs)) runJobs(tpl.jobs);
    });
    const delBtn = el('button', { class: 'icon-btn', text: '\u2715' });
    delBtn.title = 'Eliminar';
    delBtn.onclick = () => {
      state.settings.templates = state.settings.templates.filter((t) => t.name !== tpl.name);
      saveSettings();
      refreshTemplates();
    };
    col.appendChild(
      el(
        'div',
        { class: 'tpl-card' },
        el(
          'div',
          { class: 'tpl-head' },
          el('div', { class: 'tpl-name', text: tpl.name }),
          el('div', { class: 'tpl-btns' }, applyBtn, applyRunBtn, delBtn)
        ),
        el('div', { class: 'tpl-included', text: included || '(sin secciones)' })
      )
    );
  }
  if (!state.settings.templates.length)
    col.appendChild(el('div', { class: 'empty-hint', text: 'Todavía no guardaste ninguna plantilla.' }));
}

// ================================================================ tabs
function buildKindTab(kind) {
  let exclPanel;
  if (kind === 'addons') exclPanel = buildAddonExclPanel();
  else if (kind === 'configs') exclPanel = buildConfigExclPanel();
  else exclPanel = buildBindingsNote();
  return makeTabs([
    { label: 'Cuenta', element: buildScopePanel(kind, 'account') },
    { label: 'Personaje', element: buildScopePanel(kind, 'character') },
    { label: 'Exclusiones', element: exclPanel },
  ]);
}

function buildMainTabs() {
  return makeTabs([
    { label: 'Plantillas', element: buildTemplatesTab() },
    { label: 'Addons', element: buildKindTab('addons') },
    { label: 'Configs', element: buildKindTab('configs') },
    { label: 'Bindeos', element: buildKindTab('bindings') },
  ]);
}

// ================================================================ WTF
async function doReload() {
  const root = document.getElementById('wtfField').value.trim();
  if (!root) {
    snack('Carpeta WTF inválida.');
    return;
  }
  let valid = false;
  try {
    valid = await invoke('is_dir', { path: root });
  } catch (e) {
    /* ignore */
  }
  if (!valid) {
    snack('Carpeta WTF inválida.');
    return;
  }
  const accounts = await invoke('list_accounts', { wtfRoot: root });
  const chars = await invoke('list_characters', { wtfRoot: root });
  state.wtfRoot = root;
  state.accounts = accounts;
  state.charMap = {};
  for (const c of chars) state.charMap[c.key] = c.path;
  state.settings.wtf_root = root;
  saveSettings();
  for (const key of Object.keys(state.panels)) {
    const [kind, scope] = key.split('_');
    refreshPanel(kind, scope);
  }
  await refreshAddonExcludes();
  log(`Cargado: ${accounts.length} cuentas, ${chars.length} personajes.`);
}

async function browse() {
  try {
    const path = await window.__TAURI__.dialog.open({ directory: true, title: 'Seleccioná la carpeta WTF' });
    if (path) {
      document.getElementById('wtfField').value = path;
      await doReload();
    }
  } catch (e) {
    /* cancelado */
  }
}

// ================================================================ init
async function init() {
  if (!window.__TAURI__) {
    document.body.textContent = 'Esta app debe ejecutarse dentro de Tauri.';
    return;
  }

  state.settings = {
    wtf_root: '',
    src: {},
    addon_excludes: ['ActionBarSaver'],
    config_excludes: [],
    templates: [],
    backup_enabled: true,
  };
  try {
    const loaded = await invoke('get_settings');
    if (loaded && typeof loaded === 'object') {
      state.settings = loaded;
      if (state.settings.backup_enabled === undefined) state.settings.backup_enabled = true;
    }
  } catch (e) {
    console.error(e);
  }

  document.getElementById('browseBtn').onclick = browse;
  document.getElementById('loadBtn').onclick = () => doReload();
  document.getElementById('historyBtn').onclick = openHistory;
  document.getElementById('historyClose').onclick = () =>
    document.getElementById('historyOverlay').classList.add('hidden');
  document.getElementById('successOk').onclick = () =>
    document.getElementById('successOverlay').classList.add('hidden');

  document.getElementById('mainTabs').appendChild(buildMainTabs());

  document.getElementById('wtfField').value = state.settings.wtf_root || '';
  refreshTemplates();
  if (state.settings.wtf_root) await doReload();
}

init();
