// WOTLK Clones - Config Sync 3.3.5a (Tauri 2)
const KINDS = ['addons', 'configs', 'bindings'];

const ACCOUNT_CONFIG_FILES = [
  ['config-cache.wtf', 'Config general'],
  ['macros-cache.txt', 'Macros'],
];
const CHARACTER_CONFIG_FILES = [
  ['config-cache.wtf', 'Config general'],
  ['macros-cache.txt', 'Macros'],
  ['layout-local.txt', 'Layout de UI'],
  ['addons.txt', 'Lista de addons activados'],
  ['chat-cache.txt', 'Configuración de chat'],
];

const state = {
  settings: null,
  wtfRoot: '',
  accounts: [],
  allChars: [],   // lista cruda de CharacterInfo (incluye has_activity)
  charMap: {}, // "acc / realm / char" -> path (ya filtrado según hideEmptyChars)
  panels: {},  // "kind_scope" -> {srcSelect, checks:{name:input}, listEl, searchEl, render}
  addonExclListEl: null,
  addonExclSearchEl: null,
  addonExclNames: [],
  addonOnlyListEl: null,
  addonOnlySearchEl: null,
  configExclListEl: null,
  scopeChecks: {},
  templatesColEl: null,
  logLines: [],
  backupChecks: {},
};

// ================================================================ i18n
function lang() {
  return (state.settings && state.settings.lang) || 'es';
}

function t(key, vars) {
  const dict = window.I18N[lang()] || window.I18N.es;
  let s = dict[key] ?? window.I18N.es[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) s = s.split('{' + k + '}').join(v);
  }
  return s;
}

function kindLabel(kind) {
  return t('kind.' + kind);
}

function scopeLabel(kind, scope) {
  return `${t('kind.' + kind)} - ${t('scope.' + scope)}`;
}

function configFileLabel(fname) {
  const map = {
    'config-cache.wtf': t('configFile.general'),
    'macros-cache.txt': t('configFile.macros'),
    'layout-cache.txt': t('configFile.layout'),
    'layout-local.txt': t('configFile.layout'),
    'addons.txt': t('configFile.addonList'),
    'chat.wtf': t('configFile.chat'),
    'chat-cache.wtf': t('configFile.chat'),
    'chat-cache.txt': t('configFile.chat'),
  };
  return map[fname] || fname;
}

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

function logClass(s) {
  s = s.trim();
  if (/ERROR/i.test(s)) return 'log-error';
  if (/^==.*==$/.test(s)) return 'log-head';
  if (/^  /.test(s)) return 'log-dim';
  return '';
}

function log(text, forcedCls = '') {
  const lv = document.getElementById('logView');
  for (const part of String(text).split('\n')) {
    if (!part.trim()) continue;
    state.logLines.push(part);
    const cls = forcedCls || logClass(part);
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

// ================================================================ idioma
function applyLang() {
  document.documentElement.lang = lang();
  document.querySelectorAll('[data-i18n]').forEach((n) => {
    n.textContent = t(n.getAttribute('data-i18n'));
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach((n) => {
    n.placeholder = t(n.getAttribute('data-i18n-placeholder'));
  });
  const langNames = { es: 'Español', en: 'English', ru: 'Русский' };
  document.querySelectorAll('.lang-btn').forEach((b) => {
    b.classList.toggle('active', b.dataset.lang === lang());
    b.title = langNames[b.dataset.lang] || b.dataset.lang;
  });
  rebuildTabs();
}

function setLang(newLang) {
  if (!window.I18N[newLang] || newLang === lang()) return;
  state.settings.lang = newLang;
  saveSettings();
  applyLang();
}

function rebuildTabs() {
  const host = document.getElementById('mainTabs');
  host.textContent = '';
  host.appendChild(buildMainTabs());
  for (const key of Object.keys(state.panels)) {
    const [kind, scope] = key.split('_');
    refreshPanel(kind, scope);
  }
  refreshTemplates();
  refreshAddonExcludes();
}

// ================================================================ progreso
let progressDone = 0;
let progressTotal = 0;
let progressUnlisten = null;

function setProgressFill(frac) {
  const fill = document.getElementById('progressFill');
  fill.style.width = Math.round(Math.min(1, Math.max(0, frac)) * 100) + '%';
}

async function startProgress(total, title, indeterminate = false) {
  progressDone = 0;
  progressTotal = Math.max(total, 1);
  const fill = document.getElementById('progressFill');
  fill.classList.toggle('indeterminate', indeterminate);
  document.getElementById('progressTitle').textContent = title;
  document.getElementById('progressText').textContent = t('progress.preparing');
  setProgressFill(0);
  document.getElementById('progressOverlay').classList.remove('hidden');
  if (!progressUnlisten) {
    try {
      progressUnlisten = await window.__TAURI__.event.listen('sync-progress', (e) => {
        const { done, current } = e.payload;
        if (done > 0) progressDone = Math.min(progressDone + 1, progressTotal);
        setProgressFill(progressDone / progressTotal);
        if (current) document.getElementById('progressText').textContent = t('progress.copyingTo', { dst: current });
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
  const fill = document.getElementById('progressFill');
  fill.classList.remove('indeterminate');
  document.getElementById('progressOverlay').classList.add('hidden');
  setProgressFill(0);
  if (ok) {
    document.getElementById('successText').textContent = msg;
    document.getElementById('successOverlay').classList.remove('hidden');
  }
}

// ================================================================ backups
async function refreshBackups() {
  const list = document.getElementById('backupsList');
  list.textContent = '';
  state.backupChecks = {};
  let backups = [];
  try {
    backups = await invoke('get_backups');
  } catch (e) {
    list.appendChild(el('div', { class: 'empty-hint', text: t('backups.readError', { err: e }) }));
    return;
  }
  if (!backups.length) {
    list.appendChild(el('div', { class: 'empty-hint', text: t('backups.noBackups') }));
    return;
  }
  for (const b of backups) {
    const date = new Date(Number(b.ts)).toLocaleString(lang());
    const detail = b.accounts.length
      ? t('backups.accounts', { list: b.accounts.join(', '), files: b.files })
      : t('backups.files', { files: b.files });
    const checkInput = el('input', { type: 'checkbox' });
    state.backupChecks[b.path] = checkInput;
    const restoreBtn = btn(t('backups.restore'), 'small', () => {
      confirm(t('backups.restoreConfirm', { date }), () => doRestore(b));
    });
    const delBtn = btn(t('backups.delete'), 'small outline', () => {
      confirm(t('backups.deleteConfirm', { date }), () => doDelete(b));
    });
    list.appendChild(
      el(
        'div',
        { class: 'backup-card' },
        checkInput,
        el(
          'div',
          { class: 'backup-info' },
          el('div', { class: 'backup-name', text: date }),
          el('div', { class: 'backup-detail', text: detail })
        ),
        el('div', { class: 'backup-actions' }, restoreBtn, delBtn)
      )
    );
  }
}

function selectAllBackups() {
  for (const cb of Object.values(state.backupChecks || {})) cb.checked = true;
}

function selectNoneBackups() {
  for (const cb of Object.values(state.backupChecks || {})) cb.checked = false;
}

async function deleteBackupPaths(paths) {
  let ok = 0;
  let failed = 0;
  for (const p of paths) {
    try {
      await invoke('delete_backup', { backupPath: p });
      ok++;
    } catch (e) {
      failed++;
      log('ERROR: ' + e);
    }
  }
  await refreshBackups();
  if (failed) snack(t('backups.deletedBulkErrors', { ok, failed }));
  else snack(t('backups.deletedBulk', { count: ok }), true);
}

function doDeleteSelected() {
  const paths = Object.entries(state.backupChecks || {})
    .filter(([, cb]) => cb.checked)
    .map(([p]) => p);
  if (!paths.length) {
    snack(t('backups.noneSelected'));
    return;
  }
  confirm(t('backups.deleteSelectedConfirm', { count: paths.length }), () => deleteBackupPaths(paths));
}

async function openBackupsFolder() {
  try {
    await invoke('open_backups_folder');
  } catch (e) {
    snack(t('common.error', { err: e }));
  }
}

async function doRestore(b) {
  if (!state.wtfRoot) {
    snack(t('wtf.loadFirst'));
    return;
  }
  await startProgress(1, t('backups.restoring'), true);
  try {
    const lines = await invoke('restore_backup', { backupPath: b.path, wtfRoot: state.wtfRoot });
    lines.forEach((l) => log(l));
    log(t('backups.restoredLog'), 'log-ok');
    finishProgress(true, t('backups.restored'));
  } catch (e) {
    log('ERROR: ' + e);
    snack(t('common.error', { err: e }));
    finishProgress(false);
  }
}

async function doDelete(b) {
  try {
    await invoke('delete_backup', { backupPath: b.path });
    snack(t('backups.deleted'), true);
    await refreshBackups();
  } catch (e) {
    snack(t('common.error', { err: e }));
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
  const title = t('scope.' + scope);
  const dstLabel = scope === 'account' ? t('scope.accountDst') : t('scope.characterDst');

  const srcSelect = el('select');
  const searchEl =
    scope === 'character'
      ? el('input', { type: 'text', class: 'search', placeholder: t('search.placeholder') })
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
    if (!names.length) listEl.appendChild(el('div', { class: 'empty-hint', text: t('list.empty') }));
  }

  const selectAllBtn = btn(t('scope.selectAll'), 'outline small', () => {
    const q = (searchEl?.value || '').trim().toLowerCase();
    for (const n of Object.keys(checks)) if (!q || n.toLowerCase().includes(q)) checks[n].checked = true;
  });
  const selectNoneBtn = btn(t('scope.selectNone'), 'outline small', () => {
    for (const n of Object.keys(checks)) checks[n].checked = false;
  });

  const runBtn = btn(t('scope.runBtn', { scope: title.toLowerCase() }), 'run', () => {
    const src = srcSelect.value;
    const dsts = Object.keys(checks).filter((n) => checks[n].checked && n !== src);
    if (!src || !dsts.length) {
      snack(t('scope.noSelection'));
      return;
    }
    confirm(t('scope.overwrite', { dsts: dsts.join(', ') }), () => doRun(src, dsts));
  });

  async function doRun(src, dsts) {
    await startProgress(dsts.length, t('scope.sending', { kind: kindLabel(kind) }));
    try {
      const lines = await invoke('run_sync', {
        jobType: kind, scope, wtfRoot: state.wtfRoot, src, dsts, settingsData: state.settings,
      });
      lines.forEach((l) => log(l));
      log(t('common.done'), 'log-ok');
      finishProgress(true, t('scope.applied', { kind: kindLabel(kind) }));
    } catch (e) {
      log('ERROR: ' + e);
      snack(t('common.error', { err: e }));
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
        el('div', { class: 'field-label', text: t('scope.sourceLabel', { kind: kindLabel(kind) }) }),
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
  const searchEl = el('input', { type: 'text', class: 'search excl-search', placeholder: t('addons.exclSearch') });
  searchEl.oninput = renderAddonExcludes;
  state.addonExclListEl = listEl;
  state.addonExclSearchEl = searchEl;
  return el(
    'div',
    { class: 'panel scope-panel' },
    el('div', { class: 'field-label', text: t('addons.exclTitle') }),
    el('div', { class: 'note-text', text: t('addons.exclNote') }),
    searchEl,
    box
  );
}

async function refreshAddonExcludes() {
  state.addonExclNames = [];
  if (state.wtfRoot) {
    try {
      state.addonExclNames = await invoke('scan_all_addons', { wtfRoot: state.wtfRoot });
    } catch (e) {
      /* ignore */
    }
  }
  renderAddonExcludes();
  renderAddonOnly();
}

function renderAddonExcludes() {
  const listEl = state.addonExclListEl;
  if (!listEl) return;
  listEl.textContent = '';
  const q = (state.addonExclSearchEl?.value || '').trim().toLowerCase();
  const names = state.addonExclNames.filter((n) => (q ? n.toLowerCase().includes(q) : true));
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
    listEl.appendChild(el('div', { class: 'empty-hint', text: t('addons.exclEmpty') }));
}

function buildAddonOnlyPanel() {
  const listEl = el('div', { class: 'checklist' });
  const box = el('div', { class: 'checklist-box' }, listEl);
  const searchEl = el('input', { type: 'text', class: 'search excl-search', placeholder: t('addons.exclSearch') });
  searchEl.oninput = renderAddonOnly;
  state.addonOnlyListEl = listEl;
  state.addonOnlySearchEl = searchEl;
  return el(
    'div',
    { class: 'panel scope-panel' },
    el('div', { class: 'field-label', text: t('addons.onlyTitle') }),
    el('div', { class: 'note-text', text: t('addons.onlyNote') }),
    searchEl,
    box
  );
}

function renderAddonOnly() {
  const listEl = state.addonOnlyListEl;
  if (!listEl) return;
  listEl.textContent = '';
  const q = (state.addonOnlySearchEl?.value || '').trim().toLowerCase();
  const names = state.addonExclNames.filter((n) => (q ? n.toLowerCase().includes(q) : true));
  for (const name of names) {
    const cb = el(
      'label',
      { class: 'check' },
      el('input', { type: 'checkbox' }),
      el('span', { class: 'name', text: name })
    );
    const input = cb.querySelector('input');
    input.checked = state.settings.addon_only.includes(name);
    input.onchange = () => {
      if (input.checked) {
        if (!state.settings.addon_only.includes(name)) state.settings.addon_only.push(name);
      } else {
        state.settings.addon_only = state.settings.addon_only.filter((x) => x !== name);
      }
      saveSettings();
    };
    listEl.appendChild(cb);
  }
  if (!names.length)
    listEl.appendChild(el('div', { class: 'empty-hint', text: t('addons.exclEmpty') }));
}

function buildConfigExclPanel() {
  const listEl = el('div', { class: 'checklist' });
  const box = el('div', { class: 'checklist-box' }, listEl);
  state.configExclListEl = listEl;
  renderConfigExcludes();
  return el(
    'div',
    { class: 'panel scope-panel' },
    el('div', { class: 'field-label', text: t('configs.exclTitle') }),
    el('div', { class: 'note-text', text: t('configs.exclNote') }),
    box
  );
}

function renderConfigExcludes() {
  const listEl = state.configExclListEl;
  if (!listEl) return;
  listEl.textContent = '';
  const seen = new Set();
  const all = [...ACCOUNT_CONFIG_FILES, ...CHARACTER_CONFIG_FILES].filter(([fname]) => {
    if (seen.has(fname)) return false;
    seen.add(fname);
    return true;
  });
  for (const [fname] of all) {
    const cb = el(
      'label',
      { class: 'check excl' },
      el('input', { type: 'checkbox' }),
      el('span', { class: 'name', text: `${configFileLabel(fname)}  (${fname})` })
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
}

function buildBindingsNote() {
  return el(
    'div',
    { class: 'panel' },
    el('div', { class: 'note-text', text: t('bindings.note') })
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
        el('span', { class: 'name', text: kindLabel(kind) })
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
      makeScopeColumn('account', t('scope.account')),
      el('div', { class: 'v-divider' }),
      makeScopeColumn('character', t('scope.character'))
    )
  );

  const nameField = el('input', { type: 'text', placeholder: t('templates.namePlaceholder'), style: 'width:300px' });

  const backupCheck = el(
    'label',
    { class: 'check' },
    el('input', { type: 'checkbox' }),
    el('span', { class: 'name', text: t('templates.backupToggle') })
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
      snack(t('templates.noName'));
      return;
    }
    const selected = Object.keys(state.scopeChecks).filter((k) => state.scopeChecks[k].checked);
    if (!selected.length) {
      snack(t('templates.noSection'));
      return;
    }
    const { jobs, missing } = collectCurrentJobs(selected);
    if (!jobs.length) {
      snack(t('templates.noJobs'));
      return;
    }
    state.settings.templates = state.settings.templates.filter((x) => x.name !== name);
    state.settings.templates.push({
      name,
      jobs,
      excludes: {
        addon_excludes: [...state.settings.addon_excludes],
        addon_only: [...state.settings.addon_only],
        config_excludes: [...state.settings.config_excludes],
      },
    });
    saveSettings();
    nameField.value = '';
    refreshTemplates();
    let msg = t('templates.saved', { name });
    if (missing.length) msg += t('templates.missing', { list: missing.join(', ') });
    snack(msg, true);
  }

  const left = el(
    'div',
    { class: 'templates-left' },
    el(
      'div',
      { class: 'panel scope-panel' },
      el('div', { class: 'field-label', text: t('templates.saveTitle'), style: 'font-size:14px;font-weight:700' }),
      el('div', { class: 'note-text', text: t('templates.saveNote') }),
      el('div', { class: 'checklist-box', style: 'height:auto;min-height:190px' }, scopeChecksRow),
      el('div', { class: 'row' }, nameField, btn(t('templates.saveBtn'), '', saveTemplate)),
      el('div', { class: 'row' }, backupCheck),
      el('div', { class: 'note-text', text: t('templates.backupNote') })
    )
  );

  const templatesCol = el('div', { class: 'templates-col' });
  state.templatesColEl = templatesCol;
  const right = el(
    'div',
    { class: 'templates-right' },
    el('div', { class: 'field-label', text: t('templates.savedTitle'), style: 'color:var(--gold);font-size:15px;font-weight:700' }),
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
    else missing.push(scopeLabel(kind, scope));
  }
  return { jobs, missing };
}

function applyTemplateExcludes(tpl) {
  if (!tpl.excludes) return;
  state.settings.addon_excludes = [...(tpl.excludes.addon_excludes || [])];
  state.settings.addon_only = [...(tpl.excludes.addon_only || [])];
  state.settings.config_excludes = [...(tpl.excludes.config_excludes || [])];
  saveSettings();
  renderAddonExcludes();
  renderAddonOnly();
  renderConfigExcludes();
}

function applyJobs(jobs) {
  if (!state.wtfRoot) {
    snack(t('wtf.loadFirst'));
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
    snack(t('jobs.noDests'));
    return;
  }
  await startProgress(total, t('jobs.applying', { count: jobs.length }));
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
    log(t('jobs.done'), 'log-ok');
    finishProgress(true, hadError ? t('jobs.withErrors') : t('jobs.ok'));
  } catch (e) {
    hadError = true;
    log('ERROR: ' + e);
    finishProgress(false);
  }
}

function refreshTemplates() {
  const col = state.templatesColEl;
  if (!col) return;
  col.textContent = '';
  for (const tpl of state.settings.templates) {
    const included = tpl.jobs
      .map((j) => scopeLabel(j.type, j.scope))
      .join(', ');
    const applyBtn = btn(t('templates.apply'), 'outline small', () => {
      if (applyJobs(tpl.jobs)) {
        applyTemplateExcludes(tpl);
        snack(t('templates.applied', { name: tpl.name }), true);
      }
    });
    const applyRunBtn = btn(t('templates.applyRun'), 'small', () => {
      if (applyJobs(tpl.jobs)) {
        applyTemplateExcludes(tpl);
        runJobs(tpl.jobs);
      }
    });
    const delBtn = el('button', { class: 'icon-btn', text: '\u2715' });
    delBtn.title = t('templates.delete');
    delBtn.onclick = () => {
      state.settings.templates = state.settings.templates.filter((x) => x.name !== tpl.name);
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
        el('div', { class: 'tpl-included', text: included || t('templates.noSections') })
      )
    );
  }
  if (!state.settings.templates.length)
    col.appendChild(el('div', { class: 'empty-hint', text: t('templates.empty') }));
}

// ================================================================ tabs
function buildKindTab(kind) {
  const items = [
    { label: t('scope.account'), element: buildScopePanel(kind, 'account') },
    { label: t('scope.character'), element: buildScopePanel(kind, 'character') },
  ];
  if (kind === 'addons') {
    items.push({ label: t('tabs.only'), element: buildAddonOnlyPanel() });
    items.push({ label: t('tabs.exclusions'), element: buildAddonExclPanel() });
  } else if (kind === 'configs') {
    items.push({ label: t('tabs.exclusions'), element: buildConfigExclPanel() });
  } else {
    items.push({ label: t('tabs.exclusions'), element: buildBindingsNote() });
  }
  return makeTabs(items);
}

function buildMainTabs() {
  return makeTabs([
    { label: t('tabs.templates'), element: buildTemplatesTab() },
    { label: kindLabel('addons'), element: buildKindTab('addons') },
    { label: kindLabel('configs'), element: buildKindTab('configs') },
    { label: kindLabel('bindings'), element: buildKindTab('bindings') },
  ]);
}

// ================================================================ WTF
async function doReload() {
  const root = document.getElementById('wtfField').value.trim();
  if (!root) {
    snack(t('wtf.invalid'));
    return;
  }
  let valid = false;
  try {
    valid = await invoke('is_dir', { path: root });
  } catch (e) {
    /* ignore */
  }
  if (!valid) {
    snack(t('wtf.invalid'));
    return;
  }
  const accounts = await invoke('list_accounts', { wtfRoot: root });
  const chars = await invoke('list_characters', { wtfRoot: root });
  state.wtfRoot = root;
  state.accounts = accounts;
  state.allChars = chars;
  rebuildCharMap();
  state.settings.wtf_root = root;
  saveSettings();
  for (const key of Object.keys(state.panels)) {
    const [kind, scope] = key.split('_');
    refreshPanel(kind, scope);
  }
  await refreshAddonExcludes();
  log(t('wtf.loaded', { accounts: accounts.length, chars: chars.length }));
}

function rebuildCharMap() {
  state.charMap = {};
  for (const c of state.allChars) {
    if (state.settings.hide_empty_characters && !c.has_activity) continue;
    state.charMap[c.key] = c.path;
  }
}

async function browse() {
  try {
    const path = await window.__TAURI__.dialog.open({ directory: true, title: t('wtf.browseTitle') });
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
    document.body.textContent = t('app.tauriOnly');
    return;
  }

  state.settings = {
    wtf_root: '',
    src: {},
    addon_excludes: [],
    addon_only: [],
    config_excludes: [],
    templates: [],
    backup_enabled: true,
    lang: 'es',
    hide_empty_characters: false,
  };
  try {
    const loaded = await invoke('get_settings');
    if (loaded && typeof loaded === 'object') {
      state.settings = loaded;
      if (state.settings.backup_enabled === undefined) state.settings.backup_enabled = true;
      if (!state.settings.lang || !window.I18N[state.settings.lang]) state.settings.lang = 'es';
      if (!Array.isArray(state.settings.addon_only)) state.settings.addon_only = [];
      if (state.settings.hide_empty_characters === undefined) state.settings.hide_empty_characters = false;
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

  document.getElementById('backupsBtn').onclick = async () => {
    document.getElementById('backupsOverlay').classList.remove('hidden');
    await refreshBackups();
  };
  document.getElementById('backupsClose').onclick = () =>
    document.getElementById('backupsOverlay').classList.add('hidden');
  document.getElementById('backupsOpenFolder').onclick = openBackupsFolder;
  document.getElementById('backupsSelectAll').onclick = selectAllBackups;
  document.getElementById('backupsSelectNone').onclick = selectNoneBackups;
  document.getElementById('backupsDeleteSelected').onclick = doDeleteSelected;

  document.querySelectorAll('.lang-btn').forEach((b) => {
    b.onclick = () => setLang(b.dataset.lang);
  });

  const hideEmptyChk = document.getElementById('hideEmptyChars');
  hideEmptyChk.checked = !!state.settings.hide_empty_characters;
  hideEmptyChk.onchange = () => {
    state.settings.hide_empty_characters = hideEmptyChk.checked;
    saveSettings();
    rebuildCharMap();
    for (const key of Object.keys(state.panels)) {
      const [kind, scope] = key.split('_');
      if (scope === 'character') refreshPanel(kind, scope);
    }
  };

  document.getElementById('wtfField').value = state.settings.wtf_root || '';
  applyLang();
  if (state.settings.wtf_root) await doReload();
}

init();
