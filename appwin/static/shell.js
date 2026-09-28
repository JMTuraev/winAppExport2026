"use strict";
/* AppWin shell: rail + 2nd-level panel + tabs (EksportMonitor pages in iframes) + Ctrl+K + status bar + Bugun + Superadmin. */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const dmy = iso => iso ? `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}` : '—';
const hm = iso => iso ? iso.slice(11, 16) : '';
const fmt = (n, d = 1) => (n == null || isNaN(n)) ? '—' : Number(n).toLocaleString('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d });
const todayISO = () => { const d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); };
const initials = n => (n || '?').split(/\s+/).map(x => x[0]).slice(0, 2).join('').toUpperCase();
function toast(msg, err = false) { const t = $('#toast'); t.textContent = msg; t.className = 'toast show' + (err ? ' err' : ''); clearTimeout(t._h); t._h = setTimeout(() => t.className = 'toast', err ? 7000 : 3500); }
async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const ct = r.headers.get('content-type') || '';
  const d = ct.includes('json') ? await r.json() : null;
  if (r.status === 401) { location.href = '/login'; throw new Error('Kirish talab qilinadi'); }
  if (!r.ok) throw new Error((d && d.error) || ('Xato: ' + r.status));
  return d;
}

// ---------------------------------------------------------------- icons
const I = {
  home: '<path d="M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  building: '<rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M10 21v-3h4v3"/>',
  table: '<rect x="3" y="4" width="18" height="16" rx="1"/><path d="M3 10h18M9 4v16"/>',
  doc: '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5M8 13h8M8 17h8"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
  shop: '<path d="M3 7l2-4h14l2 4M3 7h18v13H3zM9 11h6"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
  upload: '<path d="M12 16V4M6 10l6-6 6 6M4 20h16"/>',
  list: '<path d="M4 6h16M4 12h16M4 18h10"/>',
  bars: '<path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/>',
  grid: '<path d="M4 5h6v6H4zM14 5h6v6h-6zM4 15h6v6H4zM14 15h6v6h-6z"/>',
  trend: '<path d="M3 20h18M4 16l5-6 4 3 7-8"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.6 3 4 5.9 4 9s-1.4 6-4 9c-2.6-3-4-5.9-4-9s1.4-6 4-9z"/>',
  leaf: '<path d="M12 21c4-4 7-7 7-11a7 7 0 0 0-14 0c0 4 3 7 7 11z"/>',
  move: '<path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/>',
  check: '<path d="M9 11l3 3 8-8"/><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9"/>',
  hist: '<path d="M12 3l9 4v5c0 5-4 8-9 9-5-1-9-4-9-9V7z"/><path d="M9 12l2 2 4-4"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
  box: '<path d="M3 7l9-4 9 4v10l-9 4-9-4z"/><path d="M3 7l9 4 9-4M12 11v10"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2 20a7 7 0 0 1 14 0M16 4.5a3.5 3.5 0 0 1 0 7M22 20a7 7 0 0 0-5-6.7"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M15 8l3 3M18 5l3 3"/>',
  out: '<path d="M10 17l5-5-5-5M15 12H3M21 3v18"/>',
  disk: '<rect x="3" y="8" width="18" height="8" rx="2"/><circle cx="17" cy="12" r="1"/>',
  warn: '<path d="M12 9v4M12 17h.01M10.3 3.9L2.6 17a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
};
const svg = (n, s = 20) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${I[n] || ''}</svg>`;

// ---------------------------------------------------------------- pages
const PAGES = {
  today: { t: 'Bugun', ic: 'home', kind: 'today' },
  dash:  { t: 'Dashboard', ic: 'chart' }, daily: { t: 'Kunlik hisobot', ic: 'upload' }, nom: { t: 'Номма-ном', ic: 'list' }, svod: { t: 'Свод (туманлар)', ic: 'bars' },
  prod:  { t: 'Тармоқ ва маҳсулот', ic: 'grid' }, dyn: { t: 'Динамика', ic: 'trend' }, geo: { t: 'Экспорт географияси', ic: 'globe' }, kar: { t: 'Мева-сабзавот', ic: 'leaf' },
  reg:   { t: 'Korxonalar', ic: 'building' }, mov: { t: 'Корхона ҳаракати', ic: 'move' }, iss: { t: 'Muammo va vazifalar', ic: 'check' },
  rep:   { t: 'Ҳисоботлар', ic: 'doc' },
  docs:  { t: 'Hujjatlar', ic: 'doc', kind: 'soon' }, chat: { t: 'Chat', ic: 'chat', kind: 'soon' },
  cat:   { t: 'Каталог', ic: 'box' }, market: { t: 'Market (WB · Ozon)', ic: 'shop', kind: 'soon' },
  set:   { t: 'Sozlamalar', ic: 'gear' }, ctrl: { t: 'Nazorat va tarix', ic: 'hist' }, admin: { t: 'Superadmin', ic: 'shield', kind: 'admin', sa: true },
};
const GROUPS = [
  { id: 'today', t: 'Bugun', ic: 'home', pages: ['today'] },
  { id: 'tahlil', t: 'Tahlil', ic: 'chart', title: 'Tahlil va jadvallar', pages: ['dash', 'daily', 'nom', 'svod', 'prod', 'dyn', 'geo', 'kar'] },
  { id: 'korxona', t: 'Korxona', ic: 'building', title: 'Korxonalar', pages: ['reg', 'mov', 'iss'] },
  { id: 'hisobot', t: 'Hisobot', ic: 'table', title: 'Hisobotlar', pages: ['rep'] },
  { id: 'hujjat', t: 'Hujjat', ic: 'doc', pages: ['docs'] },
  { id: 'chat', t: 'Chat', ic: 'chat', pages: ['chat'] },
  { id: 'katalog', t: 'Katalog', ic: 'box', title: 'Katalog va Market', pages: ['cat', 'market'] },
  { id: 'admin', t: 'Admin', ic: 'shield', title: 'Sozlamalar va nazorat', pages: ['set', 'ctrl', 'admin'], bottom: true },
];
const SOON = {
  docs: ['Маълумотнома, доклад, xatlar — shablon + bazadan jonli raqamlar', 'Ichida tahrir, Word/PDF ga chiqarish', 'Kiruvchi/chiquvchi xatlar reyestri', 'Versiyalar va tasdiqlash bosqichi'],
  chat: ['Faqat ofis tarmog\'ida, internetga chiqmaydi', 'Kanallar, korxona threadlari, shaxsiy xabarlar', 'Ovozli xabar (matn bilan)', 'Har fayl korxona yoki vazifaga bog\'lanadi', 'Xabardan vazifa yaratish'],
  market: ['Buxoro tadbirkorlari mahsulotini Wildberries va Ozon orqali sotish', 'Tadqiqot hujjati: claude/market-wb-ozon.md'],
};

// ---------------------------------------------------------------- state
const S = { me: null, srv: null, online: 0, tabs: [], active: null, group: null, pinned: [], seq: 0, status: null };
try { S.pinned = JSON.parse(localStorage.getItem('aw-pinned') || '["dash","daily","nom","reg"]'); } catch (_) { S.pinned = ['dash', 'daily', 'nom', 'reg']; }
const savePinned = () => { try { localStorage.setItem('aw-pinned', JSON.stringify(S.pinned)); } catch (_) {} };
const isSA = () => S.me && S.me.role === 'superadmin';
const canWrite = () => S.me && (S.me.role === 'superadmin' || S.me.role === 'operator');

// ---------------------------------------------------------------- rail + panel
function renderRail() {
  const r = $('#rail'); r.innerHTML = '';
  GROUPS.forEach(g => {
    if (g.bottom) { const sp = document.createElement('div'); sp.className = 'sp'; r.appendChild(sp); }
    const b = document.createElement('button'); b.className = 'rb' + (g.id === 'admin' && isSA() ? ' sa' : ''); b.dataset.g = g.id; b.title = g.title || g.t; b.setAttribute('aria-label', g.t);
    b.innerHTML = svg(g.ic) + `<span>${g.t}</span>` + (g.id === 'korxona' ? '<span class="n" id="rail-iss" hidden></span>' : '');
    b.onclick = () => clickGroup(g);
    r.appendChild(b);
  });
  markRail();
}
function markRail() {
  const t = S.tabs.find(x => x.id === S.active); const g = t ? GROUPS.find(g => g.pages.includes(t.page)) : null;
  $$('#rail .rb').forEach(b => b.classList.toggle('on', !!g && b.dataset.g === g.id));
}
function clickGroup(g) {
  if (g.pages.length === 1) { openPage(g.pages[0]); $('#panel').classList.add('off'); S.group = null; return; }
  if (S.group === g.id && !$('#panel').classList.contains('off')) { $('#panel').classList.add('off'); S.group = null; return; }
  S.group = g.id; renderPanel(); $('#panel').classList.remove('off');
}
function renderPanel() {
  const g = GROUPS.find(x => x.id === S.group); const p = $('#panel'); if (!g) { p.classList.add('off'); return; }
  const act = S.tabs.find(x => x.id === S.active);
  const item = (pid, k) => {
    const pg = PAGES[pid]; if (pg.sa && !isSA()) return '';
    const on = act && act.page === pid; const pin = S.pinned.indexOf(pid);
    return `<div class="pi${on ? ' on' : ''}" data-p="${pid}" role="button" tabindex="0">${svg(pg.ic, 14)}<span class="t">${esc(pg.t)}</span>` +
      (pid === 'daily' && S.status && !S.status.gtd_today ? `<span class="badge pill warn">${esc(dmy(todayISO()).slice(0, 5))} yo'q</span>` : '') +
      (pg.kind === 'soon' ? '<span class="soon">keyingi bosqich</span>' : '') +
      (pin >= 0 && pin < 4 ? `<span class="k">F${pin + 1}</span>` : '') +
      `<button class="pin${pin >= 0 ? ' on' : ''}" data-pin="${pid}" title="${pin >= 0 ? 'Qadalganlardan olish' : 'Qadash (F1–F4)'}">★</button></div>`;
  };
  const pinnedHere = g.pages.filter(x => S.pinned.includes(x)), rest = g.pages.filter(x => !S.pinned.includes(x));
  p.innerHTML = `<div class="hd"><h2>${esc(g.title || g.t)}</h2><button id="panel-x" title="Panelni yig'ish">${svg('out', 12).replace('<svg', '<svg style="transform:rotate(180deg)"')}</button></div>` +
    (pinnedHere.length ? `<div class="sec">Qadalgan</div>${pinnedHere.map(item).join('')}` : '') +
    (rest.length ? `<div class="sec">${pinnedHere.length ? 'Boshqa sahifalar' : 'Sahifalar'}</div>${rest.map(item).join('')}` : '') +
    `<div class="ft">★ bilan sahifani «Qadalgan»ga qo'shing — F1…F4 bilan ochiladi. Ctrl+bosish — yangi tabda.</div>`;
  $('#panel-x').onclick = () => { p.classList.add('off'); S.group = null; };
  $$('.pi', p).forEach(b => { b.onclick = e => { if (e.target.closest('.pin')) return; openPage(b.dataset.p, null, e.ctrlKey || e.metaKey); }; b.onkeydown = e => { if (e.key === 'Enter') openPage(b.dataset.p, null, e.ctrlKey); }; });
  $$('.pin', p).forEach(b => b.onclick = e => { e.stopPropagation(); togglePin(b.dataset.pin); });
}
function togglePin(pid) { const i = S.pinned.indexOf(pid); if (i >= 0) S.pinned.splice(i, 1); else S.pinned.push(pid); savePinned(); renderPanel(); renderTabs(); }

// ---------------------------------------------------------------- tabs
function openPage(pid, arg = null, newTab = false, title = null) {
  const pg = PAGES[pid]; if (!pg) return;
  if (pg.sa && !isSA()) { toast('Bu bo\'lim faqat superadmin uchun', true); return; }
  let t = newTab ? null : S.tabs.find(x => x.page === pid && (arg == null ? x.arg == null : x.arg === arg));
  if (!t && !newTab && arg == null) t = S.tabs.find(x => x.page === pid && x.arg == null);
  if (t) { activate(t.id); if (arg != null && t.win) try { t.win.go(pid, arg); } catch (_) {} return; }
  t = { id: 'tab' + (++S.seq), page: pid, arg, title: title || pg.t, kind: pg.kind || 'legacy', view: null, win: null };
  S.tabs.push(t);
  const v = document.createElement('div'); v.className = 'view' + (t.kind === 'legacy' ? '' : ' int'); v.id = t.id; t.view = v; $('#content').appendChild(v);
  if (t.kind === 'legacy') mountLegacy(t); else if (t.kind === 'today') renderToday(t); else if (t.kind === 'admin') renderAdmin(t); else renderSoon(t);
  activate(t.id);
}
function activate(id) {
  S.active = id; S.tabs.forEach(t => t.view.classList.toggle('on', t.id === id)); renderTabs(); markRail(); if (S.group) renderPanel();
  const t = S.tabs.find(x => x.id === id); if (t) { document.title = t.title + ' — Eksport Monitor'; heartbeat(t); if (t.kind === 'legacy' && t.win) try { t.win.dispatchEvent(new Event('resize')); } catch (_) {} }
}
function closeTab(id) {
  const i = S.tabs.findIndex(x => x.id === id); if (i < 0) return;
  const t = S.tabs[i]; if (t.kind === 'today' && S.tabs.length === 1) return;
  t.view.remove(); S.tabs.splice(i, 1);
  if (S.active === id) { const n = S.tabs[Math.max(0, i - 1)]; if (n) activate(n.id); else openPage('today'); } else renderTabs();
}
function renderTabs() {
  const box = $('#tabs'); box.innerHTML = '';
  S.tabs.forEach(t => {
    const pg = PAGES[t.page]; const b = document.createElement('button'); b.className = 'tab' + (t.id === S.active ? ' on' : '') + (S.pinned.includes(t.page) && t.arg == null ? ' pinned' : '');
    b.innerHTML = svg(pg.ic, 14) + `<span class="t">${esc(t.title)}</span>` + (t.kind === 'today' && S.tabs.length === 1 ? '' : '<span class="x" title="Yopish (Ctrl+W)">×</span>');
    b.onclick = e => { if (e.target.classList.contains('x')) closeTab(t.id); else activate(t.id); };
    b.onauxclick = e => { if (e.button === 1) closeTab(t.id); };
    box.appendChild(b);
  });
}

// ---------------------------------------------------------------- legacy pages (EksportMonitor in an iframe)
const LEGACY_CSS = `.side{display:none!important}.app{min-height:100vh}.main{margin-left:0!important}.side-tip{display:none!important}`;
function mountLegacy(t) {
  const f = document.createElement('iframe'); f.title = t.title; f.src = '/legacy?_=' + Date.now();
  f.addEventListener('load', () => {
    const w = f.contentWindow, d = f.contentDocument; if (!w || !d) return;
    t.win = w;
    const st = d.createElement('style'); st.textContent = LEGACY_CSS; d.head.appendChild(st);
    try { w.go(t.page, t.arg); } catch (e) { console.warn(e); }
    // company card opened inside → own tab title; page switches inside the legacy UI are mirrored to the tab
    const origGo = w.go;
    w.go = (p, a) => { origGo(p, a); if (p !== t.page) { t.page = p; t.arg = a ?? null; t.title = PAGES[p] ? PAGES[p].t : p; renderTabs(); markRail(); } else if (a != null && a !== t.arg) { t.arg = a; } };
    // 401 inside the iframe → back to login
    const origFetch = w.fetch; w.fetch = async (...a) => { const r = await origFetch(...a); if (r.status === 401) location.href = '/login'; return r; };
    // Ctrl+K from inside the iframe
    d.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openPalette(); } if (e.key === 'F1' || e.key === 'F2' || e.key === 'F3' || e.key === 'F4') { e.preventDefault(); const pid = S.pinned[+e.key.slice(1) - 1]; if (pid) openPage(pid); } });
  });
  t.view.appendChild(f);
}
function openCompany(inn, name) { openPage('reg', inn, true, name || ('Korxona ' + inn)); }

// ---------------------------------------------------------------- «Bugun»
async function renderToday(t) {
  const v = t.view; v.innerHTML = '<div class="empty">Yuklanmoqda…</div>';
  let d; try { d = await api('/api/my/today'); } catch (e) { v.innerHTML = `<div class="err">${esc(e.message)}</div>`; return; }
  S.status = d; const st = S.srv || {}; const me = S.me || {};
  const now = new Date(); const DOW = ['Yakshanba', 'Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba']; const MON = ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentyabr', 'oktyabr', 'noyabr', 'dekabr'];
  const gtdOk = d.gtd_today; const overdue = d.issues_overdue || 0;
  const week = []; for (let i = 6; i >= 0; i--) { const x = new Date(now); x.setDate(now.getDate() - i); week.push(x); }
  const upl = Object.fromEntries((d.uploads_week || []).map(r => [r.report_date, r.n]));
  const DS = ['Ya', 'Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh'];
  const iso = x => x.getFullYear() + '-' + String(x.getMonth() + 1).padStart(2, '0') + '-' + String(x.getDate()).padStart(2, '0');
  v.innerHTML = `
  <div class="pg-h"><div><div class="sub">${DOW[now.getDay()]}, ${now.getDate()} ${MON[now.getMonth()]} ${now.getFullYear()}</div>
    <h1>Xayrli kun, ${esc((me.name || '').split(' ')[0])}.</h1></div><span class="sp"></span>
    ${canWrite() ? `<button class="btn" data-go="iss">${svg('check', 14)} Vazifa</button><button class="btn p" data-go="daily">${svg('upload', 14)} GTD yuklash</button>` : `<button class="btn" data-go="dash">${svg('chart', 14)} Dashboard</button>`}</div>
  <div class="kpis">
    <div class="kpi"><div class="l">Oxirgi ma'lumot</div><div class="v ${gtdOk ? 'ok' : 'warn'}">${d.last_date ? dmy(d.last_date).slice(0, 5) : '—'}</div><div class="s">${gtdOk ? 'bugungi GTD yuklangan' : 'bugungi GTD hali yo\'q'}</div></div>
    <div class="kpi"><div class="l">Ochiq muammo va vazifalar</div><div class="v ${overdue ? 'bad' : ''}">${d.issues_total || 0}</div><div class="s">${overdue ? overdue + ' ta muddati o\'tgan' : 'muddati o\'tgani yo\'q'}</div></div>
    <div class="kpi"><div class="l">Hozir tizimda</div><div class="v">${(d.online || []).length}</div><div class="s">${esc((d.online || []).slice(0, 3).map(o => o.name.split(' ')[0]).join(', '))}${(d.online || []).length > 3 ? ' …' : ''}</div></div>
    <div class="kpi"><div class="l">Server</div><div class="v" style="font-size:16px;margin-top:6px">${esc(st.ip || '')}:${st.port || ''}</div><div class="s">${st.host || ''} · ${st.uptime_min != null ? Math.floor(st.uptime_min / 60) + ' soat ' + (st.uptime_min % 60) + ' daq' : ''}</div></div>
    <div class="kpi"><div class="l">Oxirgi zaxira</div><div class="v" style="font-size:16px;margin-top:6px">${st.last_backup ? esc(st.last_backup.replace('export_', '').slice(0, 16).replace('_', ' ')) : '—'}</div><div class="s">${st.db_mb ? 'baza ' + st.db_mb + ' MB' : ''}</div></div>
  </div>
  <div class="grid2">
    <div class="card"><div class="hd"><h2>Kunlik GTD holati</h2><span class="sub">oxirgi 7 kun</span><span class="sp"></span><button class="lnk" data-go="daily">Kunlik hisobot →</button></div>
      <div class="week">${week.map(x => { const k = iso(x), n = upl[k], tdy = k === d.today; return `<div class="d${n ? '' : ' no'}${tdy ? ' today' : ''}"><small>${DS[x.getDay()]}</small><b>${x.getDate()}</b><small>${n ? n + ' qator' : (tdy ? 'yuklanmagan' : '—')}</small></div>`; }).join('')}</div>
      ${gtdOk ? '' : `<div style="padding:0 14px 12px"><div class="note warn">${svg('warn', 18)}<span class="sp">Bugungi bojxona GTD fayli hali yuklanmagan.</span>${canWrite() ? '<button class="btn p sm" data-go="daily">Yuklash</button>' : ''}</div></div>`}
    </div>
    <div class="card"><div class="hd"><h2>Ochiq muammo va vazifalar</h2><span class="sub">${d.issues_total || 0} ta</span><span class="sp"></span><button class="lnk" data-go="iss">Doska →</button></div>
      ${(d.open_issues || []).length ? d.open_issues.slice(0, 7).map(i => { const od = i.due_date && i.due_date < d.today, tdy = i.due_date === d.today;
        return `<div class="row click" data-inn="${esc(i.inn || '')}" data-name="${esc(i.company || '')}"><span class="t"><b style="font-weight:500">${esc(i.title)}</b>${i.company ? ` <span class="m">· ${esc(i.company)}</span>` : ''}</span>${i.due_date ? `<span class="pill ${od ? 'bad' : (tdy ? 'warn' : 'gray')}">${od ? 'muddati o\'tgan · ' : ''}${dmy(i.due_date).slice(0, 5)}</span>` : ''}${i.responsible ? `<span class="m">${esc(i.responsible)}</span>` : ''}</div>`; }).join('') : '<div class="empty">Ochiq vazifa yo\'q</div>'}
    </div>
    <div class="card"><div class="hd"><h2>Hozir tizimda</h2><span class="sub">kim qayerda</span></div>
      ${(d.online || []).length ? d.online.map(o => `<div class="od"><span class="dot"></span><span class="who">${esc(o.name)}</span><span class="m">${esc(pageTitle(o.page) || '—')}</span><span class="m mono" style="font-family:var(--mono);font-size:10px">${esc((o.ip || '').split('.').slice(-1)[0] ? '.' + (o.ip || '').split('.').slice(-1)[0] : '')}</span></div>`).join('') : '<div class="empty">—</div>'}
    </div>
    <div class="card"><div class="hd"><h2>Mening oxirgi harakatlarim</h2><span class="sub">audit jurnalidan</span></div>
      ${(d.my_audit || []).length ? d.my_audit.map(a => `<div class="row"><span class="mono">${esc(dmy(a.ts).slice(0, 5))} ${esc(hm(a.ts))}</span><span class="pill ${a.ok ? 'acc' : 'bad'}">${esc(a.action)}</span><span class="t m">${esc(a.detail || '')}</span></div>`).join('') : '<div class="empty">Hali harakat yo\'q</div>'}
    </div>
  </div>`;
  $$('[data-go]', v).forEach(b => b.onclick = () => openPage(b.dataset.go));
  $$('.row[data-inn]', v).forEach(r => r.onclick = () => r.dataset.inn ? openCompany(r.dataset.inn, r.dataset.name) : openPage('iss'));
  const ri = $('#rail-iss'); if (ri) { ri.hidden = !overdue; ri.textContent = overdue; }
}
function pageTitle(p) { if (!p) return ''; const [pid, rest] = p.split(':'); return (PAGES[pid] ? PAGES[pid].t : pid) + (rest ? ' · ' + rest : ''); }

// ---------------------------------------------------------------- «keyingi bosqich»
function renderSoon(t) {
  const pg = PAGES[t.page];
  t.view.innerHTML = `<div class="soonbox"><h1>${svg(pg.ic, 22).replace('<svg', '<svg style="display:inline-block;vertical-align:-4px;margin-right:8px"')}${esc(pg.t)}</h1><p>Bu bo'lim keyingi bosqichda qo'shiladi. Rejada:</p><ul>${(SOON[t.page] || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul></div>`;
}

// ---------------------------------------------------------------- Superadmin
const A = { tab: 'users', users: null, audit: null, srv: null, f: {} };
async function renderAdmin(t) {
  const v = t.view;
  v.innerHTML = `<div class="pg-h"><h1>Superadmin</h1><span class="pill gold">faqat siz ko'rasiz</span>
    <div class="tabs2" id="a-tabs"><button data-t="users">Foydalanuvchilar</button><button data-t="online">Hozir tizimda</button><button data-t="audit">Audit jurnali</button><button data-t="server">Zaxira va server</button></div>
    <span class="sp"></span><button class="btn p" id="a-add">+ Foydalanuvchi qo'shish</button></div><div id="a-body"></div>`;
  $$('#a-tabs button', v).forEach(b => b.onclick = () => { A.tab = b.dataset.t; adminTab(v); });
  $('#a-add', v).onclick = () => userModal(null, () => adminTab(v));
  adminTab(v);
}
async function adminTab(v) {
  $$('#a-tabs button', v).forEach(b => b.classList.toggle('on', b.dataset.t === A.tab));
  const b = $('#a-body', v); b.innerHTML = '<div class="empty">Yuklanmoqda…</div>';
  try {
    if (A.tab === 'users') await adminUsers(b, v);
    else if (A.tab === 'online') await adminOnline(b);
    else if (A.tab === 'audit') await adminAudit(b);
    else await adminServer(b);
  } catch (e) { b.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
}
const ROLE_PILL = { superadmin: 'gold', operator: 'acc', viewer: 'blue', district: 'gray' };
async function adminUsers(b, v) {
  const d = await api('/api/admin/users'); A.users = d; const dn = Object.fromEntries(d.districts.map(x => [x.code, x.name_uz]));
  b.innerHTML = `<div class="card"><div class="hd"><h2>Foydalanuvchilar</h2><span class="sub">${d.users.length} ta · ${d.users.filter(u => u.online).length} onlayn · ${d.users.filter(u => !u.active).length} bloklangan</span></div>
    <table class="tbl"><thead><tr><th>Xodim</th><th>Login</th><th>Rol</th><th>Tumanlar</th><th>Oxirgi kirish</th><th>Holat</th><th></th></tr></thead><tbody>
    ${d.users.map(u => `<tr class="${u.active ? '' : 'dim'}"><td><span class="who"><span class="av${u.role === 'superadmin' ? ' sa' : ''}" style="background:${u.active ? (u.role === 'superadmin' ? '#14232B' : '') : '#DCE1DD'};color:${u.role === 'superadmin' ? '#fff' : ''}">${esc(initials(u.name))}</span>${esc(u.name)}</span></td>
      <td class="mono">${esc(u.login)}</td><td><span class="pill ${ROLE_PILL[u.role] || 'gray'}">${esc(u.role_name)}</span>${u.must_change ? ' <span class="pill warn" title="Birinchi kirishda parolni o\'zgartiradi">parol</span>' : ''}</td>
      <td class="m" style="color:var(--ink2)">${u.role === 'district' ? esc(u.districts.map(c => dn[c] || c).join(', ') || '—') : (u.role === 'viewer' ? 'hammasi (faqat o\'qish)' : 'hammasi')}</td>
      <td>${u.last_login ? esc(dmy(u.last_login).slice(0, 5) + ' ' + hm(u.last_login)) : '—'}</td>
      <td><span class="on-dot ${!u.active ? 'blk' : (u.online ? '' : 'off')}">${!u.active ? 'bloklangan' : (u.online ? 'onlayn' : 'oflayn')}</span></td>
      <td style="text-align:right;white-space:nowrap"><button class="btn sm" data-e="${u.id}">Tahrir</button> ${u.id !== S.me.id ? `<button class="btn sm${u.active ? ' bad' : ''}" data-a="${u.id}" data-v="${u.active ? 0 : 1}">${u.active ? 'Bloklash' : 'Ochish'}</button>` : ''}</td></tr>`).join('')}
    </tbody></table></div>`;
  $$('[data-e]', b).forEach(x => x.onclick = () => userModal(d.users.find(u => u.id === +x.dataset.e), () => adminTab(v)));
  $$('[data-a]', b).forEach(x => x.onclick = async () => { try { await api('/api/admin/user/active', { id: +x.dataset.a, active: x.dataset.v === '1' }); toast(x.dataset.v === '1' ? 'Foydalanuvchi ochildi' : 'Foydalanuvchi bloklandi'); adminTab(v); } catch (e) { toast(e.message, true); } });
}
function userModal(u, done) {
  const d = A.users || { districts: [], roles: {} }; const isNew = !u;
  const roles = d.roles || { superadmin: 'Superadmin', operator: 'Operator', viewer: "Ko'ruvchi", district: 'Tuman xodimi' };
  const sel = new Set(u ? u.districts : []);
  modal(`<div class="hd"><h2>${isNew ? 'Yangi foydalanuvchi' : 'Foydalanuvchi: ' + esc(u.name)}</h2><button class="x" data-x>×</button></div>
    <div class="bd"><div class="err" id="um-err" hidden></div>
      <div class="f2"><label class="fld">Ism familiya<input id="um-name" value="${esc(u ? u.name : '')}" placeholder="Dilshod Karimov"></label>
      <label class="fld">Login<input id="um-login" value="${esc(u ? u.login : '')}" ${isNew ? '' : 'disabled'} placeholder="d.karimov" autocapitalize="off"></label></div>
      <label class="fld">Rol<select id="um-role">${Object.entries(roles).map(([k, n]) => `<option value="${k}"${u && u.role === k ? ' selected' : (!u && k === 'operator' ? ' selected' : '')}>${esc(n)}</option>`).join('')}</select>
        <span class="h" id="um-rh"></span></label>
      <div class="fld" id="um-dist"><span>Tumanlar (tuman xodimi uchun)</span><div class="chips">${d.districts.map(x => `<button type="button" class="chip${sel.has(x.code) ? ' on' : ''}" data-c="${x.code}">${esc(x.name_uz.replace(' тумани', '').replace(' шаҳри', ' ш.'))}</button>`).join('')}</div></div>
      <label class="fld">${isNew ? 'Parol' : 'Yangi parol (bo\'sh qolsa o\'zgarmaydi)'}<input id="um-pwd" type="text" autocomplete="off" placeholder="kamida 6 belgi"><span class="h">Xodim birinchi kirishda parolni o'zi o'zgartiradi.</span></label>
    </div><div class="ft"><button class="btn" data-x>Bekor</button><button class="btn p" id="um-save">Saqlash</button></div>`, m => {
    const RH = { superadmin: 'Hamma narsa + bu panel', operator: 'GTD/jadval yuklash, korxona tahrir, Excel', viewer: 'Faqat ko\'rish va Excel yuklab olish', district: 'Faqat ko\'rish; o\'z tumanlari (filtr keyingi bosqichda)' };
    const rsel = $('#um-role', m), rh = $('#um-rh', m), dist = $('#um-dist', m);
    const upd = () => { rh.textContent = RH[rsel.value] || ''; dist.style.display = rsel.value === 'district' ? '' : 'none'; }; rsel.onchange = upd; upd();
    $$('.chip', m).forEach(c => c.onclick = () => { c.classList.toggle('on'); c.classList.contains('on') ? sel.add(c.dataset.c) : sel.delete(c.dataset.c); });
    $('#um-save', m).onclick = async () => {
      const body = { id: u ? u.id : null, name: $('#um-name', m).value, login: $('#um-login', m).value, role: rsel.value, districts: [...sel], password: $('#um-pwd', m).value || undefined };
      try { await api('/api/admin/user/save', body); toast('Saqlandi'); m.remove(); done(); } catch (e) { const er = $('#um-err', m); er.textContent = e.message; er.hidden = false; }
    };
    setTimeout(() => $(isNew ? '#um-name' : '#um-name', m).focus(), 50);
  });
}
async function adminOnline(b) {
  const d = await api('/api/admin/online');
  b.innerHTML = `<div class="card"><div class="hd"><h2>Hozir tizimda</h2><span class="sub">${d.online.length} ta · oxirgi 5 daqiqada faol</span><span class="sp"></span><button class="btn sm" id="ao-r">Yangilash</button></div>
    ${d.online.length ? `<table class="tbl"><thead><tr><th>Xodim</th><th>Rol</th><th>Qayerda</th><th>IP</th><th>Kompyuter</th><th>Kirgan</th><th>Oxirgi faollik</th><th></th></tr></thead><tbody>
    ${d.online.map(o => `<tr><td><span class="who"><span class="av">${esc(initials(o.name))}</span>${esc(o.name)}</span></td><td><span class="pill ${ROLE_PILL[o.role] || 'gray'}">${esc(o.role_name)}</span></td><td>${esc(pageTitle(o.page) || '—')}</td><td class="mono">${esc(o.ip || '')}</td><td class="mono">${esc(o.host || '')}</td><td>${esc(dmy(o.since).slice(0, 5) + ' ' + hm(o.since))}</td><td>${esc(hm(o.last_seen))}</td>
      <td style="text-align:right">${o.id !== S.me.id ? `<button class="btn sm" data-k="${o.id}">Sessiyani yopish</button>` : ''}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">Hozir hech kim yo\'q</div>'}</div>`;
  $('#ao-r', b).onclick = () => adminOnline(b);
  $$('[data-k]', b).forEach(x => x.onclick = async () => { try { await api('/api/admin/user/kick', { id: +x.dataset.k }); toast('Sessiya yopildi'); adminOnline(b); } catch (e) { toast(e.message, true); } });
}
async function adminAudit(b) {
  const f = A.f; const qs = Object.entries(f).filter(([, v]) => v).map(([k, v]) => k + '=' + encodeURIComponent(v)).join('&');
  const d = await api('/api/admin/audit' + (qs ? '?' + qs : '')); const users = A.users ? A.users.users : (await api('/api/admin/users')).users; if (!A.users) A.users = { users, districts: [], roles: {} };
  b.innerHTML = `<div class="card"><div class="hd"><h2>Audit jurnali</h2><span class="sub">kim · qachon · qayerdan · nima qildi — ${d.total} yozuv</span><span class="sp"></span>
    <div class="fbar"><select class="sel" id="af-u"><option value="">Hamma xodimlar</option>${users.map(u => `<option value="${u.id}"${f.user_id == u.id ? ' selected' : ''}>${esc(u.name)}</option>`).join('')}</select>
      <select class="sel" id="af-a"><option value="">Hamma harakatlar</option>${d.actions.map(a => `<option${f.action === a ? ' selected' : ''}>${esc(a)}</option>`).join('')}</select>
      <select class="sel" id="af-ok"><option value="">Hammasi</option><option value="1"${f.ok === '1' ? ' selected' : ''}>Muvaffaqiyatli</option><option value="0"${f.ok === '0' ? ' selected' : ''}>Rad etilgan / xato</option></select>
      <input class="inp" type="date" id="af-d1" value="${esc(f.date_from || '')}" title="dan"><input class="inp" type="date" id="af-d2" value="${esc(f.date_to || '')}" title="gacha">
      <input class="inp" id="af-t" placeholder="matn…" value="${esc(f.text || '')}" style="width:140px"><button class="btn sm" id="af-go">Qidirish</button><a class="btn sm" href="/api/admin/audit.xlsx${qs ? '?' + qs : ''}">Excel</a></div></div>
    <table class="tbl"><thead><tr><th>Vaqt</th><th>Xodim</th><th>IP</th><th>Harakat</th><th>Tafsilot</th><th>Natija</th></tr></thead><tbody>
    ${d.rows.map(r => `<tr class="${r.ok ? '' : 'bad'}"><td class="mono">${esc(dmy(r.ts).slice(0, 5))} ${esc(hm(r.ts))}</td><td>${esc(r.login || '—')}</td><td class="mono" style="color:var(--ink2)">${esc(r.ip || '')}</td><td><span class="pill ${r.ok ? (r.action === 'kirdi' || r.action === 'chiqdi' ? 'gray' : 'acc') : 'bad'}">${esc(r.action)}</span></td><td class="el" title="${esc(r.path || '')}">${esc(r.detail || r.path || '')}</td><td style="color:${r.ok ? 'var(--ok-ink)' : 'var(--bad)'}">${r.ok ? '✓' : '✕'}</td></tr>`).join('') || '<tr><td colspan="6" class="empty">Yozuv yo\'q</td></tr>'}
    </tbody></table></div>`;
  const go = () => { A.f = { user_id: $('#af-u', b).value, action: $('#af-a', b).value, ok: $('#af-ok', b).value, date_from: $('#af-d1', b).value, date_to: $('#af-d2', b).value, text: $('#af-t', b).value }; adminAudit(b); };
  $('#af-go', b).onclick = go; $('#af-t', b).onkeydown = e => { if (e.key === 'Enter') go(); };
  ['#af-u', '#af-a', '#af-ok', '#af-d1', '#af-d2'].forEach(s => $(s, b).onchange = go);
}
async function adminServer(b) {
  const d = await api('/api/admin/server');
  b.innerHTML = `<div class="agrid"><div class="card"><div class="hd"><h2>Zaxira</h2><span class="sub">${esc(d.db_path.split(/[\\/]/).slice(-2).join('/'))}</span><span class="sp"></span>
      ${canWrite() ? '<button class="btn p sm" id="bk-now">Hozir zaxiralash</button>' : ''}<button class="btn sm" data-go="ctrl">Tiklash / tarix →</button></div>
    <div style="padding:12px 14px;display:flex;gap:12px;align-items:center"><div style="width:44px;height:44px;border-radius:10px;background:var(--ok-soft);color:var(--ok-ink);display:flex;align-items:center;justify-content:center">${svg('disk', 20)}</div>
      <div><div style="font-weight:600">Oxirgi zaxira: ${d.last_backup ? esc(d.last_backup.replace('export_', '').replace('.db', '').replace('_', ' ')) : '—'}</div><div class="sub" style="font-size:11px;color:var(--ink2)">baza ${d.db_mb} MB · zaxiralar papkasi: data\\backups</div></div></div>
    ${d.backups.map(x => `<div class="row"><span class="t mono">${esc(x.name)}</span><span class="m">${x.mb} MB</span></div>`).join('')}
    <div style="padding:10px 14px;font-size:11px;color:var(--ink2)">Tashqi diskka avtomatik nusxa va o'chirishdagi «zaxira olinsinmi?» modali — Windows ilova (exe) bosqichida qo'shiladi.</div></div>
    <div class="card"><div class="hd"><h2>Server</h2></div><div class="srvg">
      <div><div class="l">Ofis tarmog'ida manzil</div><div class="mono" style="font-family:var(--mono)">http://${esc(d.ip)}:${d.port}/</div></div><div><div class="l">Kompyuter</div><div>${esc(d.host)}</div></div>
      <div><div class="l">Ish vaqti</div><div>${Math.floor(d.uptime_min / 60)} soat ${d.uptime_min % 60} daq</div></div><div><div class="l">Versiya</div><div>AppWin ${esc(d.version)} · Python ${esc(d.python)}</div></div>
      <div><div class="l">Bugun harakatlar</div><div>${d.audit_today} · <span style="color:var(--bad)">${d.audit_denied_today} rad etilgan</span></div></div><div><div class="l">Ochiq sessiyalar</div><div>${d.sessions_open}</div></div>
      <div><div class="l">Rejim</div><div>${d.readonly ? '<span class="pill bad">faqat ko\'rish (baza boshqa kompyuterda)</span>' : '<span class="pill ok">yozish mumkin</span>'}</div></div></div>
      <div style="padding:6px 14px 12px;font-size:11px;color:var(--ink2)">Xodimlar brauzerda shu manzilni ochadi. Kompyuter uxlab qolmasin, IP o'zgarmasin (routerda statik IP).</div></div></div>`;
  const bn = $('#bk-now', b); if (bn) bn.onclick = async () => { bn.disabled = true; try { const r = await api('/api/backups/create', {}); toast('Zaxira olindi: ' + r.name); adminServer(b); } catch (e) { toast(e.message, true); bn.disabled = false; } };
  $$('[data-go]', b).forEach(x => x.onclick = () => openPage(x.dataset.go));
}

// ---------------------------------------------------------------- modal helper
function modal(html, init) {
  const bg = document.createElement('div'); bg.className = 'mbg'; bg.innerHTML = `<div class="mdl" role="dialog" aria-modal="true">${html}</div>`;
  $('#overlay').appendChild(bg);
  $$('[data-x]', bg).forEach(x => x.onclick = () => bg.remove());
  bg.addEventListener('keydown', e => { if (e.key === 'Escape') bg.remove(); });
  init && init(bg); return bg;
}
function passwordModal(force) {
  modal(`<div class="hd"><h2>${force ? 'Yangi parol o\'rnating' : 'Parolni o\'zgartirish'}</h2>${force ? '' : '<button class="x" data-x>×</button>'}</div>
    <div class="bd">${force ? '<div class="note">Bu birinchi kirishingiz (yoki parol superadmin tomonidan tiklangan). Davom etish uchun o\'z parolingizni o\'rnating.</div>' : ''}<div class="err" id="pm-err" hidden></div>
      ${force ? '' : '<label class="fld">Joriy parol<input type="password" id="pm-old"></label>'}
      <label class="fld">Yangi parol<input type="password" id="pm-new" placeholder="kamida 6 belgi"></label>
      <label class="fld">Yangi parol (takror)<input type="password" id="pm-new2"></label></div>
    <div class="ft">${force ? '' : '<button class="btn" data-x>Bekor</button>'}<button class="btn p" id="pm-save">Saqlash</button></div>`, m => {
    const save = async () => {
      const n = $('#pm-new', m).value; if (n !== $('#pm-new2', m).value) { const e = $('#pm-err', m); e.textContent = 'Parollar mos emas'; e.hidden = false; return; }
      try { await api('/api/auth/password', { old: force ? '' : $('#pm-old', m).value, new: n }); toast('Parol o\'zgartirildi'); m.remove(); if (S.me) S.me.must_change = false; } catch (e) { const er = $('#pm-err', m); er.textContent = e.message; er.hidden = false; }
    };
    $('#pm-save', m).onclick = save; m.addEventListener('keydown', e => { if (e.key === 'Enter') save(); });
    setTimeout(() => $(force ? '#pm-new' : '#pm-old', m).focus(), 50);
  });
}

// ---------------------------------------------------------------- Ctrl+K
let K = null;
function openPalette() {
  if (K) { $('input', K).focus(); return; }
  K = document.createElement('div'); K.className = 'kbg';
  K.innerHTML = `<div class="kpal"><div class="in">${svg('search', 16)}<input placeholder="Sahifa, korxona nomi yoki INN…" autocomplete="off"><span class="kbd">Esc</span></div><div class="ls" id="k-ls"></div>
    <div class="ft"><span><b>↑↓</b> tanlash</span><span><b>Enter</b> ochish</span><span><b>Ctrl+Enter</b> yangi tabda</span></div></div>`;
  $('#overlay').appendChild(K);
  const inp = $('input', K), ls = $('#k-ls', K); let items = [], sel = 0, timer = null;
  const close = () => { K.remove(); K = null; };
  K.addEventListener('click', e => { if (e.target === K) close(); });
  const draw = () => {
    let h = '', lastSec = '';
    items.forEach((it, i) => { if (it.sec !== lastSec) { h += `<div class="sec">${esc(it.sec)}</div>`; lastSec = it.sec; }
      h += `<div class="ki${i === sel ? ' on' : ''}" data-i="${i}">${svg(it.ic || 'doc', 14)}<span class="t">${esc(it.t)}</span>${it.m ? `<span class="m">${esc(it.m)}</span>` : ''}${it.k ? `<span class="k">${esc(it.k)}</span>` : ''}</div>`; });
    ls.innerHTML = h || '<div class="empty">Topilmadi</div>';
    $$('.ki', ls).forEach(el => { el.onclick = e => run(items[+el.dataset.i], e.ctrlKey); });
    const on = $('.ki.on', ls); if (on) on.scrollIntoView({ block: 'nearest' });
  };
  const run = (it, nt) => { if (!it) return; close(); it.run(nt); };
  const build = async () => {
    const q = inp.value.trim(); const ql = q.toLowerCase();
    const pages = Object.entries(PAGES).filter(([pid, p]) => !(p.sa && !isSA())).filter(([, p]) => !q || p.t.toLowerCase().includes(ql) || norm(p.t).includes(norm(q)))
      .map(([pid, p]) => { const g = GROUPS.find(g => g.pages.includes(pid)); const pin = S.pinned.indexOf(pid); return { sec: 'Sahifalar', t: p.t, m: g ? (g.title || g.t) : '', ic: p.ic, k: pin >= 0 && pin < 4 ? 'F' + (pin + 1) : (p.kind === 'soon' ? 'keyingi bosqich' : ''), run: nt => openPage(pid, null, nt) }; });
    items = q ? pages.slice(0, 6) : pages; sel = 0; draw();
    if (q.length >= 2) {
      try { const d = await api('/api/companies/list?q=' + encodeURIComponent(q) + '&limit=8');
        if (inp.value.trim() !== q) return;
        const cs = (d.rows || []).slice(0, 8).map(r => ({ sec: 'Korxonalar', t: r.name, m: (r.district_name || r.district || '') + (r.ytd ? ' · ' + fmt(r.ytd) : ''), ic: 'building', k: r.inn, run: nt => openCompany(r.inn, r.name) }));
        items = [...items, ...cs]; draw();
      } catch (_) {}
    }
  };
  inp.oninput = () => { clearTimeout(timer); timer = setTimeout(build, 120); };
  inp.onkeydown = e => {
    if (e.key === 'Escape') { close(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(items.length - 1, sel + 1); draw(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(0, sel - 1); draw(); }
    else if (e.key === 'Enter') { e.preventDefault(); run(items[sel], e.ctrlKey); }
  };
  build(); inp.focus();
}
const _CYR = { а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'yo', ж: 'j', з: 'z', и: 'i', й: 'y', к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u', ф: 'f', х: 'x', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'sh', ъ: '', ы: 'i', ь: '', э: 'e', ю: 'yu', я: 'ya', ў: 'o', қ: 'q', ғ: 'g', ҳ: 'h' };
const norm = s => String(s ?? '').toLowerCase().replace(/[а-яёўқғҳ]/g, c => _CYR[c] ?? c).replace(/kh/g, 'x').replace(/[’'`ʻʼ]/g, '').replace(/[^a-z0-9]+/g, '');

// ---------------------------------------------------------------- user menu, status bar, heartbeat
function userMenu() {
  const old = $('.umenu'); if (old) { old.remove(); return; }
  const m = document.createElement('div'); m.className = 'umenu';
  m.innerHTML = `<div class="u"><b>${esc(S.me.name)}</b><span>${esc(S.me.login)} · ${esc(S.me.role_name)}</span></div>
    <button id="um-pwd">${svg('key', 14)} Parolni o'zgartirish</button>${isSA() ? `<button id="um-adm">${svg('shield', 14)} Superadmin panel</button>` : ''}
    <button id="um-tab">${svg('doc', 14)} Sahifani brauzerda ochish</button><button class="bad" id="um-out">${svg('out', 14)} Chiqish</button>`;
  document.body.appendChild(m);
  const closeM = e => { if (!m.contains(e.target) && e.target.id !== 'ume' && !e.target.closest('#ume')) { m.remove(); document.removeEventListener('mousedown', closeM); } };
  setTimeout(() => document.addEventListener('mousedown', closeM), 0);
  $('#um-pwd', m).onclick = () => { m.remove(); passwordModal(false); };
  const ad = $('#um-adm', m); if (ad) ad.onclick = () => { m.remove(); openPage('admin'); };
  $('#um-tab', m).onclick = () => { m.remove(); window.open('/legacy', '_blank'); };
  $('#um-out', m).onclick = async () => { try { await api('/api/auth/logout', {}); } catch (_) {} location.href = '/login'; };
}
async function refreshMe() {
  const d = await api('/api/auth/me');
  if (!d.user) { location.href = '/login'; return false; }
  S.me = d.user; S.srv = d.server; S.online = d.online;
  $('#u-name').textContent = S.me.name; $('#u-role').textContent = isSA() ? 'SUPERADMIN' : S.me.role_name; $('#u-role').classList.toggle('sa', isSA());
  $('#u-av').textContent = initials(S.me.name); $('#u-av').classList.toggle('sa', isSA());
  $('#s-srv').textContent = (S.srv.ip || location.hostname) + ':' + S.srv.port; $('#s-dot').className = 'dot' + (S.srv.readonly ? ' warn' : '');
  $('#s-online').textContent = S.online + ' xodim onlayn';
  $('#s-backup').textContent = 'Zaxira: ' + (S.srv.last_backup ? S.srv.last_backup.replace('export_', '').slice(0, 16).replace('_', ' ') : '—');
  $('#s-ver').textContent = 'v' + S.srv.version + ' · ' + (isSA() ? 'Superadmin rejimi' : (canWrite() ? 'Operator rejimi' : "Ko'rish rejimi")); $('#s-ver').className = isSA() ? 'sa' : 'dim';
  return true;
}
async function refreshData() {
  try { const st = await api('/api/status'); $('#s-data').textContent = "Ma'lumot: " + dmy(st.last_date) + (st.template ? ' · shablon ' + dmy(st.template.through) : ''); } catch (_) {}
}
function heartbeat(t) {
  const page = t ? t.page + (t.arg ? ':' + (t.title || t.arg) : '') : '';
  clearTimeout(heartbeat._h); heartbeat._h = setTimeout(() => fetch('/api/auth/page', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ page }) }).catch(() => {}), 400);
}

// ---------------------------------------------------------------- keyboard
document.addEventListener('keydown', e => {
  const k = e.key.toLowerCase();
  if ((e.ctrlKey || e.metaKey) && k === 'k') { e.preventDefault(); openPalette(); }
  else if ((e.ctrlKey || e.metaKey) && k === 't') { e.preventDefault(); openPalette(); }
  else if ((e.ctrlKey || e.metaKey) && k === 'w') { e.preventDefault(); if (S.active) closeTab(S.active); }
  else if (/^F[1-4]$/.test(e.key)) { const pid = S.pinned[+e.key.slice(1) - 1]; if (pid) { e.preventDefault(); openPage(pid); } }
  else if (e.ctrlKey && e.key === 'Tab') { e.preventDefault(); const i = S.tabs.findIndex(x => x.id === S.active); const n = S.tabs[(i + (e.shiftKey ? -1 : 1) + S.tabs.length) % S.tabs.length]; if (n) activate(n.id); }
});

// ---------------------------------------------------------------- boot
(async () => {
  if (!(await refreshMe())) return;
  renderRail(); $('#panel').classList.add('off');
  $('#k-open').onclick = openPalette; $('#tab-new').onclick = openPalette; $('#ume').onclick = userMenu;
  $('#s-online').onclick = () => isSA() ? (A.tab = 'online', openPage('admin')) : openPage('today');
  $('#bell').onclick = () => toast('Bildirishnomalar — chat bosqichida');
  if (window.pywebview) { $('#wc').hidden = false; }
  openPage('today');
  refreshData();
  if (S.me.must_change) passwordModal(true);
  setInterval(async () => { try { await refreshMe(); } catch (_) {} const t = S.tabs.find(x => x.id === S.active); if (t) heartbeat(t); }, 60000);
  setInterval(refreshData, 120000);
  // Bugun sahifasi ochiq bo'lsa 5 daqiqada yangilanadi
  setInterval(() => { const t = S.tabs.find(x => x.kind === 'today'); if (t && t.id === S.active) renderToday(t); }, 300000);
})();
