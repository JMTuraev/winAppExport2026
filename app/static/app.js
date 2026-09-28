"use strict";
// ---------------------------------------------------------------- helpers
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const MONTHS = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
const MSHORT = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек'];
const DOWF = ['якшанба','душанба','сешанба','чоршанба','пайшанба','жума','шанба'];
const fmt = (n, d = 1) => (n == null || isNaN(n)) ? '—' : Number(n).toLocaleString('ru-RU', {minimumFractionDigits: d, maximumFractionDigits: d});
const fmt0 = n => (n == null || isNaN(n)) ? '—' : Number(n).toLocaleString('ru-RU', {maximumFractionDigits: 0});
const pct = (a, b) => b ? 100 * a / b : null;
// smart search: kirill ↔ lotin farqsiz («Бухоро» = «Buxoro» = «BUKHORO»); app/smart.py bilan bir xil jadval
const _CYR = { а:'a',б:'b',в:'v',г:'g',д:'d',е:'e',ё:'yo',ж:'j',з:'z',и:'i',й:'y',к:'k',л:'l',м:'m',н:'n',о:'o',п:'p',р:'r',с:'s',т:'t',у:'u',ф:'f',х:'x',ц:'ts',ч:'ch',ш:'sh',щ:'sh',ъ:'',ы:'i',ь:'',э:'e',ю:'yu',я:'ya',ў:'o',қ:'q',ғ:'g',ҳ:'h' };
const snorm = s => String(s ?? '').toLowerCase().replace(/[а-яёўқғҳ]/g, c => _CYR[c] ?? c).replace(/kh/g, 'x').replace(/[’'`ʻʼ]/g, '').replace(/[^a-z0-9]+/g, '');
const smatch = (q, ...fields) => { const ws = String(q ?? '').split(/\s+/).map(snorm).filter(Boolean); if (!ws.length) return true; const hay = fields.map(snorm).join(' '); return ws.every(w => hay.includes(w)); };
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const dmy = iso => iso ? `${iso.slice(8,10)}.${iso.slice(5,7)}.${iso.slice(0,4)}` : '—';
const short = n => (n || '').replace(' тумани', ' т.').replace(' шаҳри', ' ш.');
function toast(msg, err = false) { const t = $('#toast'); t.textContent = msg; t.className = 'toast show' + (err ? ' err' : ''); clearTimeout(t._h); t._h = setTimeout(() => t.className = 'toast', err ? 7000 : 3500); }
async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json() : null;
  if (!r.ok) throw new Error((data && data.error) || ('Xato: ' + r.status));
  return data;
}
async function download(path, name) {
  toast('Excel tayyorlanmoqda…');
  const r = await fetch(path);
  if (!r.ok) { let e = 'Xato'; try { e = (await r.json()).error } catch (_) {} ; toast(e, true); return; }
  let info = null; try { const h = r.headers.get('X-Export-Info'); if (h) info = JSON.parse(decodeURIComponent(h)); } catch (_) {}
  const blob = await r.blob(); const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  if (info) {
    const days = info.days.length ? info.days.map(d => dmy(d).slice(0, 5)).join(', ') : "yangi kun yo'q";
    const ns = info.new_rows.filter(x => x.category !== 'meva'), nm = info.new_rows.filter(x => x.category === 'meva');
    const nr = (ns.length ? ` · yangi korxona: ${ns.map(x => x.name).join(', ')}` : '') + (nm.length ? ` · yangi meva-sabzavot qatori: ${nm.map(x => x.name).join(', ')}` : '');
    toast(`Yuklab olindi: ${name} · shablon ${dmy(info.template_through)} gacha + ${days}${nr}`);
    if (info.warnings.length) setTimeout(() => toast('Diqqat: ' + info.warnings.join(' | '), true), 3600);
  } else toast('Yuklab olindi: ' + name);
}
try { if (localStorage.getItem('sideCollapsed') === '1') $('#app').classList.add('collapsed'); } catch (_) {}
$('#side-tg').onclick = () => { $('#app').classList.toggle('collapsed'); try { localStorage.setItem('sideCollapsed', $('#app').classList.contains('collapsed') ? '1' : '0'); } catch (_) {} setTimeout(() => Object.values(CH).forEach(c => c && c.resize()), 230); };
// yig'ilgan menyuda nom tooltip'i (fixed — sidebar ichki scroll'i uni kesmasin)
(() => {
  const tip = document.createElement('div'); tip.className = 'side-tip'; tip.id = 'side-tip'; document.body.appendChild(tip);
  const side = $('.side'); const hide = () => { tip.style.display = 'none'; };
  side.addEventListener('mouseover', e => {
    const b = e.target.closest('.nav'); if (!b || !$('#app').classList.contains('collapsed')) return hide();
    const r = b.getBoundingClientRect(); tip.textContent = b.dataset.t || '';
    tip.style.left = (r.right + 8) + 'px'; tip.style.top = (r.top + r.height / 2) + 'px'; tip.style.display = 'block';
  });
  side.addEventListener('mouseleave', hide); side.addEventListener('scroll', hide, { passive: true }); side.addEventListener('click', hide);
})();

// ---------------------------------------------------------------- state & nav
const S = { status: null, districts: [], dash: null, date: null };
const CH = {};
const loaders = {};
$$('.nav').forEach(b => b.addEventListener('click', () => go(b.dataset.p)));
function go(p, arg) {
  $$('.nav').forEach(x => x.classList.toggle('active', x.dataset.p === p));
  $$('.page').forEach(x => x.classList.toggle('active', x.id === 'p-' + p));
  window.scrollTo(0, 0);
  if (loaders[p]) loaders[p](arg).catch(e => toast(e.message, true));
}
async function loadStatus() {
  S.status = await api('/api/status');
  const st = S.status;
  $('#nav-last').textContent = st.last_date ? dmy(st.last_date).slice(0, 5) : '—';
  $('#nav-iss').textContent = st.open_issues ? String(st.open_issues) : '—';
  $('#nav-reg').textContent = st.unconfirmed ? st.unconfirmed + ' !' : (st.new_companies ? st.new_companies + ' янги' : fmt0(st.companies));
  if ($('#foot')) $('#foot').innerHTML = `Baza: <span class="mono">${esc(st.db_path.split(/[\\/]/).slice(-2).join('/'))}</span><br>Oxirgi ma'lumot: ${dmy(st.last_date)}<br>Qoldiq: ${dmy(st.opening_date)} gacha<br>Zaxira: ${esc(st.last_backup ? st.last_backup.slice(7, 23).replace('_', ' ') : '—')}<br>Kod: ${esc((st.code_time || '—').replace('T', ' ').slice(0, 16))}`;
  const b = $('#banner');
  if (st.readonly) { b.innerHTML = `<b>Faqat ko'rish rejimi.</b> Baza hozir <b>${esc(st.lock_owner.host)}</b> kompyuterida ochiq (${esc(st.lock_owner.since)}). Ikki joyda bir vaqtda yozish ma'lumotni buzadi — u yerda dasturni yoping va bu oynani qayta oching.`; b.classList.add('show'); }
  else b.classList.remove('show');
  if (K.pv) updateSaveState(); else $('#pv-save').disabled = st.readonly;
}

// ---------------------------------------------------------------- DASHBOARD
const C = { blue: '#2a78d6', aqua: '#1baf7a', orange: '#eb6834', yellow: '#eda100', magenta: '#e87ba4', green: '#008300', violet: '#4a3aa7', gray: '#b9bdb6', plan: '#8a929c', ink2: '#5A6470', grid: '#e3e6e2' };
Chart.defaults.font.family = '"IBM Plex Sans", system-ui, sans-serif'; Chart.defaults.font.size = 12; Chart.defaults.color = C.ink2;
Chart.defaults.plugins.tooltip.backgroundColor = '#182029'; Chart.defaults.plugins.tooltip.padding = 10; Chart.defaults.plugins.tooltip.cornerRadius = 6;
Chart.defaults.plugins.legend.labels.boxWidth = 10; Chart.defaults.plugins.legend.labels.boxHeight = 10; Chart.defaults.plugins.legend.labels.usePointStyle = true;
const F = { dists: new Set(), type: 'all', m1: 0, m2: 0, tar: '', pie: 'tar', topN: 10 };
const PIE13 = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#4a3aa7', '#008300', '#c23b22', '#17a2b8', '#8c6d1f', '#7b5ea7', '#5c8a3a', '#9aa0a6'];
let dashInit = false;
function initDashFilters() {
  const fd = $('#f-dist'); fd.innerHTML = '';
  const all = document.createElement('button'); all.className = 'chip on'; all.textContent = 'Барчаси'; all.onclick = () => { F.dists.clear(); renderDash(); }; fd.appendChild(all);
  S.districts.forEach(d => { const b = document.createElement('button'); b.className = 'chip'; b.textContent = short(d.name_uz); b.dataset.d = d.code;
    b.onclick = () => { F.dists.has(d.code) ? F.dists.delete(d.code) : F.dists.add(d.code); renderDash(); }; fd.appendChild(b); });
  $$('#f-type button').forEach(b => b.onclick = () => { F.type = b.dataset.v; renderDash(); });
  $$('#pie-mode button').forEach(b => b.onclick = () => { F.pie = b.dataset.v; renderDash(); });
  $('#f-m1').onchange = () => { F.m1 = +$('#f-m1').value; if (F.m2 < F.m1) F.m2 = F.m1; renderDash(); };
  $('#f-m2').onchange = () => { F.m2 = +$('#f-m2').value; if (F.m1 > F.m2) F.m1 = F.m2; renderDash(); };
  $('#f-tar').onchange = () => { F.tar = $('#f-tar').value; renderDash(); };
  $('#top-n').oninput = () => { const n = parseInt($('#top-n').value, 10); if (n >= 1) { F.topN = Math.min(500, n); renderDash(); } };
  $('#btn-reset').onclick = () => { F.dists.clear(); F.type = 'all'; F.m1 = 0; F.m2 = S.dash.month - 1; F.tar = ''; F.topN = 10; $('#top-n').value = 10; renderDash(); };
  $('#dash-date').onchange = () => { const v = $('#dash-date').value; if (v) loadDash(v).catch(e => toast(e.message, true)); };
  dashInit = true;
}
function renderOnboard() {
  const st = S.status;
  const steps = [
    { ok: st.opening_source === 'customs', t: "1. Bojxona oylik bazasi", d: st.opening_source === 'customs' ? `reyestr ${fmt0(st.companies)} INN · sanoat ${dmy(st.opening_date)} gacha` : "Sozlamalar → «1. Bojxona oylik bazasi» → Tekshirish → Almashtirish. Reyestr va yil boshidan sanoat eksporti", go: 'set' },
    { ok: !!st.template, t: "2. O'z jadvalingiz — Excel shabloni", d: st.template ? `«${st.template.file}» · ${dmy(st.template.through)} gacha` : "Sozlamalar → «2. O'z jadvalingiz»: eng oxirgi «… йил экспорт» faylini .xlsx qilib yuklang", go: 'set' },
    { ok: st.uploads > 0, t: "3. Kunlik GTD fayllari", d: st.uploads > 0 ? `${st.uploads} ta yuklash` : `Kunlik hisobot → ${st.opening_date ? dmy(isoNext(st.opening_date)) + ' dan boshlab' : 'kunni tanlang'} → GTD faylini tashlang → Saqlash`, go: 'daily' },
  ];
  $('#onboard-steps').innerHTML = steps.map(x => `<div class="check"><div class="ic ${x.ok ? 'ok' : (x.opt ? 'warn' : 'bad')}">${x.ok ? '✓' : (x.opt ? '–' : '!')}</div><div style="flex:1"><b>${x.t}</b><span>${esc(x.d)}</span></div>${x.ok ? '' : `<button class="btn sm" data-go="${x.go}">Ochish</button>`}</div>`).join('');
  $$('#onboard-steps [data-go]').forEach(b => b.onclick = () => go(b.dataset.go));
}
// LOCAL date -> 'YYYY-MM-DD' (toISOString is UTC: in Asia/Tashkent, 00:00 local is 19:00 of the day before -> wrong day)
const localISO = d => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
const todayISO = () => localISO(new Date());
const isoNext = iso => { const d = new Date(iso + 'T00:00:00'); d.setDate(d.getDate() + 1); return localISO(d); };
async function loadDash(date) {
  if (!S.districts.length) S.districts = await api('/api/districts');
  if (!dashInit) initDashFilters();
  const st = S.status;
  const empty = !st.last_date || st.companies === 0;
  $('#onboard').hidden = !(empty || st.uploads === 0 || !st.prognoz);
  renderOnboard();
  $('#dash-body').hidden = empty;
  if (empty) { S.dash = null; return; }
  const D = date || st.last_date;
  S.dash = await api('/api/dashboard?date=' + D);
  const d = S.dash;
  if (d.empty) { $('#dash-body').hidden = true; return; }
  $('#dash-date').value = d.date; if (d.opening_date) $('#dash-date').min = d.opening_date; else $('#dash-date').removeAttribute('min');
  const m1 = $('#f-m1'), m2 = $('#f-m2'); m1.innerHTML = ''; m2.innerHTML = '';
  for (let i = 0; i < d.month; i++) { m1.add(new Option(MSHORT[i], i)); m2.add(new Option(MSHORT[i], i)); }
  F.m1 = Math.min(F.m1, d.month - 1); F.m2 = d.month - 1;
  const tars = [...new Set(d.companies.filter(c => c.t === 'sanoat').map(c => c.tarmoq).filter(Boolean))].sort();
  const ft = $('#f-tar'); const keep = F.tar; ft.innerHTML = '<option value="">Барча тармоқлар</option>'; tars.forEach(t => ft.add(new Option(t, t))); ft.value = tars.includes(keep) ? keep : ''; F.tar = ft.value;
  $('#dash-sub').textContent = `${d.year} йил · ${dmy(d.date)} ҳолатига · минг АҚШ долл.`;
  renderDash();
}
loaders.dash = () => loadDash(S.dash ? S.dash.date : null);

function planOf(key, kind) { // key: year|period|month|prev
  const d = S.dash, t = kind || F.type;
  if (!F.dists.size) { const p = d.region_plan[t]; return p ? p[key] : null; }
  return d.districts.filter(x => F.dists.has(x.code)).reduce((s, x) => s + ((x.plan[t] || {})[key] || 0), 0);
}
function renderDash() {
  const d = S.dash; if (!d) return;
  const cm = d.month - 1;
  $$('#f-dist .chip').forEach(b => b.classList.toggle('on', b.dataset.d ? F.dists.has(b.dataset.d) : F.dists.size === 0));
  $$('#f-type button').forEach(b => b.classList.toggle('on', b.dataset.v === F.type));
  $$('#pie-mode button').forEach(b => b.classList.toggle('on', b.dataset.v === F.pie));
  $('#f-m1').value = F.m1; $('#f-m2').value = F.m2;
  const inD = code => !F.dists.size || F.dists.has(code);
  const useS = F.type !== 'meva', useM = F.type !== 'sanoat' && !F.tar;
  const comps = d.companies.filter(c => c.t === 'sanoat' && inD(c.d) && (!F.tar || c.tarmoq === F.tar));
  // Тур=Мева: корхона сони мева қаторлари бўйича (номманом «Мева-сабзавотлар» қаторлари), саноат эмас
  const mevaComps = d.companies.filter(c => c.t === 'meva' && inD(c.d));
  const cntComps = F.type === 'meva' ? mevaComps : comps;
  const dists = d.districts.filter(x => inD(x.code));
  const sumRange = (c, a, b) => { let s = 0; for (let i = a; i <= b; i++) s += c.m[i] || 0; return s; };
  const fullRange = F.m1 === 0 && F.m2 === cm;
  const sanP = useS ? comps.reduce((s, c) => s + sumRange(c, F.m1, F.m2), 0) : 0;
  const sanY = useS ? comps.reduce((s, c) => s + c.total, 0) : 0;
  const mevY = useM ? dists.reduce((s, x) => s + x.meva.ytd, 0) : 0;
  const mevMon = useM ? dists.reduce((s, x) => s + x.meva.month, 0) : 0;
  let mevP = 0, mevNote = '';
  if (useM) {
    if (fullRange) mevP = mevY;
    else if (F.m1 === cm) mevP = mevMon;
    else { mevP = F.m2 === cm ? mevMon : 0; mevNote = 'мева-сабзавот: ойлик тақсимот фақат жорий ой учун маълум'; }
  }
  const total = sanP + mevP, ytd = sanY + mevY;
  const label = F.m1 === F.m2 ? MSHORT[F.m1] : MSHORT[F.m1] + '–' + MSHORT[F.m2];
  $('#k1l').textContent = 'Экспорт · ' + label;
  $('#k1').textContent = fmt(total);
  $('#k1d').textContent = (F.dists.size ? dists.length + ' туман' : 'вилоят') + (F.tar ? ' · ' + F.tar : '') + ' · ' + cntComps.filter(c => c.total > 0).length + ' корхона' + (F.type === 'meva' ? ' (мева қаторлари)' : '') + (mevNote ? ' · ' + mevNote : '');
  const pPeriod = planOf('period'), pYear = planOf('year'), pPrev = planOf('prev'), pMonth = planOf('month');
  if (F.tar) { ['#k2', '#k3'].forEach(s => $(s).textContent = '—'); $('#k2d').textContent = 'тармоқ бўйича прогноз йўқ'; $('#k3d').textContent = ''; }
  else {
    $('#k2').innerHTML = fmt(pct(ytd, pPeriod)) + '<small>%</small>';
    $('#k2d').textContent = `давр прогнози ${fmt0(pPeriod)} · йиллик ${fmt0(pYear)} (${fmt(pct(ytd, pYear))}%)`;
    $('#k3l').textContent = 'Ўтган йил шу даврга';
    $('#k3').innerHTML = fmt(pct(ytd, pPrev)) + '<small>%</small>';
    const dlt = ytd - pPrev;
    $('#k3d').innerHTML = `ўтган йил: ${fmt0(pPrev)} · <b style="color:${dlt >= 0 ? 'var(--ok)' : 'var(--bad)'}">${dlt >= 0 ? '▲ +' : '▼ '}${fmt0(dlt)}</b> · ${d.prev_year_days} кун${d.prev_year_source && d.prev_year_source.mode === 'exact' ? ' · расмий давр якуни' : (d.prev_year_source && d.prev_year_source.mode !== 'none' ? ' · даврий натижалар' : '')}`;
  }
  const monFact = comps.reduce((s, c) => s + (c.m[cm] || 0), 0) * (useS ? 1 : 0) + mevMon;
  $('#k4l').textContent = MONTHS[cm] + ' (жорий ой)';
  $('#k4').textContent = fmt(monFact);
  $('#k4d').textContent = F.tar ? '' : `ой прогнози ${fmt0(pMonth)} · ${fmt(pct(monFact, pMonth))}%`;
  const dayS = useS ? comps.reduce((s, c) => s + c.day, 0) : 0, dayM = useM ? dists.reduce((s, x) => s + x.meva.day, 0) : 0;
  $('#k5l').textContent = 'Кун: ' + dmy(d.date);
  $('#k5').textContent = fmt(dayS + dayM, 2);
  $('#k5d').textContent = `саноат ${fmt(dayS, 2)} · мева ${fmt(dayM, 2)} · ${cntComps.filter(c => c.day > 0).length} корхона`;

  // --- month line chart
  const idx = []; for (let i = F.m1; i <= F.m2; i++) idx.push(i);
  const sanM = idx.map(i => comps.reduce((s, c) => s + (c.m[i] || 0), 0));
  // the month chart is industry only (meva-sabzavot is not shown here) — plan line is the sanoat plan
  const sPeriod = planOf('period', 'sanoat'), sMonth = planOf('month', 'sanoat');
  const monthsPlan = (!F.dists.size && d.region_plan.sanoat && d.region_plan.sanoat.months) || null;
  const avgPrev = cm > 0 && sPeriod != null && sMonth != null ? (sPeriod - sMonth) / cm : null;
  const rej = idx.map(i => F.tar ? null : (monthsPlan && monthsPlan[i + 1] != null ? monthsPlan[i + 1] : (i === cm ? sMonth : avgPrev)));
  $('#c1h').textContent = (F.dists.size ? dists.map(x => short(x.name)).join(', ') : 'вилоят') + ' · саноат · минг долл.';
  $('#c1n').textContent = (!monthsPlan && !F.tar ? `Режа (саноат): жорий ой — ой прогнози, олдинги ойлар — давр прогнозидан ўртача (${fmt0(avgPrev)}).` : '');
  const line = (label, data, color, dash) => ({ label, data, borderColor: color, backgroundColor: color, borderWidth: 2, pointRadius: 4, pointHoverRadius: 7, pointBackgroundColor: '#fff', pointBorderWidth: 2, tension: .3, borderDash: dash || [], spanGaps: false });
  const ds = [line('Саноат', sanM, C.blue)];
  if (!F.tar) ds.push(line('Режа', rej, C.plan, [6, 4]));
  const mdata = { labels: idx.map(i => MSHORT[i]), datasets: ds };
  const mopts = { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
    plugins: { legend: { position: 'top', align: 'end' }, tooltip: { boxWidth: 10, boxHeight: 10, boxPadding: 3,
      callbacks: { labelColor: c => ({ borderColor: c.dataset.borderColor, backgroundColor: c.dataset.borderColor, borderWidth: 0, borderRadius: 2 }),
        title: it => it[0].label + ' · ' + (F.dists.size ? dists.length + ' туман' : 'вилоят'),
        label: c => ' ' + c.dataset.label + ': ' + (c.parsed.y == null ? 'маълум эмас' : fmt(c.parsed.y)),
        footer: it => { const s = it.filter(i => i.dataset.label !== 'Режа').reduce((a, i) => a + (i.parsed.y || 0), 0); const r = it.find(i => i.dataset.label === 'Режа'); return 'Жами: ' + fmt(s) + (r && r.parsed.y ? '  ·  режага ' + fmt(pct(s, r.parsed.y)) + '%' : ''); } } } },
    scales: { x: { grid: { display: false }, border: { color: C.grid } }, y: { beginAtZero: true, grid: { color: C.grid }, border: { display: false }, ticks: { callback: v => fmt0(v) } } } };
  if (CH.m) { CH.m.data = mdata; CH.m.options = mopts; CH.m.update(); } else CH.m = new Chart($('#c-month'), { type: 'line', data: mdata, options: mopts });

  // --- pie
  const tm = {};
  if (F.pie === 'tar') { comps.forEach(c => { const k = c.tarmoq || 'Бошқа'; tm[k] = (tm[k] || 0) + c.total; }); if (useM && mevY) tm['Мева-сабзавот (карантин)'] = mevY; }
  else { dists.forEach(x => { const s = useS ? comps.filter(c => c.d === x.code).reduce((a, c) => a + c.total, 0) : 0; tm[x.name] = s + (useM ? x.meva.ytd : 0); }); }
  $('#c2t').textContent = F.pie === 'tar' ? 'Тармоқлар улуши' : 'Туманлар улуши';
  const arr = Object.entries(tm).filter(x => x[1] > 0).sort((a, b) => b[1] - a[1]);
  const lim = F.pie === 'dist' ? arr.length : 7;   // districts: every district gets its own slice, no «Бошқа»
  const top = arr.slice(0, lim); const other = arr.slice(lim).reduce((s, x) => s + x[1], 0);
  const pl = top.map(x => x[0]), pv = top.map(x => x[1]); if (other > 0) { pl.push('Бошқа'); pv.push(other); }
  const cols = F.pie === 'dist' ? PIE13 : [C.blue, C.orange, C.aqua, C.yellow, C.magenta, C.green, C.violet, C.gray];
  const psum = pv.reduce((s, x) => s + x, 0);
  const pdata = { labels: pl, datasets: [{ data: pv, backgroundColor: cols.slice(0, pl.length), borderColor: '#fff', borderWidth: 2, hoverOffset: 6 }] };
  $('#c-pie').parentElement.style.height = (F.pie === 'dist' ? 330 : 270) + 'px';
  const popts = { responsive: true, maintainAspectRatio: false, cutout: '62%', plugins: { legend: { position: 'right', labels: { font: { size: F.pie === 'dist' ? 10.5 : 11 }, padding: F.pie === 'dist' ? 6 : 10,
      generateLabels: ch => ch.data.labels.map((l, i) => ({ text: short(l.replace(' саноати', '').replace(' маҳсулотлари', '')) + ' · ' + fmt(pct(ch.data.datasets[0].data[i], psum)) + '%', fillStyle: ch.data.datasets[0].backgroundColor[i], strokeStyle: '#fff', pointStyle: 'circle', index: i })) } },
      tooltip: { callbacks: { label: c => ' ' + fmt(c.parsed) + ' (' + fmt(pct(c.parsed, psum)) + '%)' } } } };
  if (CH.p) { CH.p.data = pdata; CH.p.options = popts; CH.p.update(); CH.p.resize(); } else CH.p = new Chart($('#c-pie'), { type: 'doughnut', data: pdata, options: popts });

  // --- district bars
  const rows = dists.map(x => { const cs = comps.filter(c => c.d === x.code);
    const act = (useS ? cs.reduce((s, c) => s + c.total, 0) : 0) + (useM ? x.meva.ytd : 0);
    const p = F.tar ? {} : (x.plan[F.type] || {});      // тармоқ филтри: тармоқ бўйича режа/ўтган йил йўқ — «—»
    return { code: x.code, name: x.name, act, per: p.period, yr: p.year, prev: p.prev,
      mon: (useS ? cs.reduce((s, c) => s + (c.m[cm] || 0), 0) : 0) + (useM ? x.meva.month : 0), day: (useS ? cs.reduce((s, c) => s + c.day, 0) : 0) + (useM ? x.meva.day : 0) }; }).sort((a, b) => b.act - a.act);
  $('#c-dist-w').style.height = Math.max(220, rows.length * (F.tar ? 26 : 38) + 50) + 'px';
  const barLabels = { id: 'barLabels', afterDatasetsDraw(ch) { const { ctx } = ch; ctx.save(); ctx.font = '11px "IBM Plex Mono", monospace'; ctx.textBaseline = 'middle';
    ch.data.datasets.forEach((dsx, di) => { const meta = ch.getDatasetMeta(di); if (meta.hidden) return;
      meta.data.forEach((bar, i) => { const v = dsx.data[i]; if (v == null) return; let t = fmt(v); ctx.fillStyle = '#5A6470';
        if (di === 0 && dsx.pctOf && dsx.pctOf[i]) { t += '  ' + fmt(pct(v, dsx.pctOf[i])) + '%'; ctx.fillStyle = v >= dsx.pctOf[i] ? '#2E8B57' : '#B23A3A'; }
        ctx.textAlign = 'left'; ctx.fillText(t, bar.x + 6, bar.y); }); }); ctx.restore(); } };
  const ddata = { labels: rows.map(r => short(r.name)), datasets: [
    { label: 'Амалда (йил боши)', data: rows.map(r => r.act), pctOf: F.tar ? null : rows.map(r => r.per), backgroundColor: C.blue, borderRadius: { topRight: 4, bottomRight: 4 }, borderSkipped: false, barPercentage: .7, categoryPercentage: .7 },
    ...(F.tar ? [] : [{ label: 'Давр прогнози', data: rows.map(r => r.per), backgroundColor: C.gray, borderRadius: { topRight: 4, bottomRight: 4 }, borderSkipped: false, barPercentage: .7, categoryPercentage: .7 }])] };
  const dopts = { indexAxis: 'y', responsive: true, maintainAspectRatio: false, layout: { padding: { right: 130 } }, plugins: { legend: { position: 'top', align: 'end' }, tooltip: { callbacks: { label: c => ' ' + c.dataset.label + ': ' + fmt(c.parsed.x) } } },
    scales: { x: { grid: { color: C.grid }, border: { display: false }, ticks: { callback: v => fmt0(v) } }, y: { grid: { display: false }, border: { color: C.grid } } } };
  if (CH.d) { CH.d.data = ddata; CH.d.options = dopts; CH.d.update(); CH.d.resize(); } else CH.d = new Chart($('#c-dist'), { type: 'bar', data: ddata, options: dopts, plugins: [barLabels] });

  // --- top 10
  const ranked = comps.map(c => ({ ...c, v: sumRange(c, F.m1, F.m2) })).filter(c => c.v > 0).sort((a, b) => b.v - a.v);
  const t10 = ranked.slice(0, F.topN);
  $('#top-n-l').textContent = t10.length < F.topN ? t10.length : F.topN;
  $('#c4h').textContent = label + ' · саноат · минг долл.';
  $('#top-n-of').textContent = '/ ' + ranked.length;
  const mx = t10.length ? t10[0].v : 1;
  const dname = Object.fromEntries(S.districts.map(x => [x.code, x.name_uz]));
  $('#rank').innerHTML = t10.map((c, i) => `<div class="r"><span class="muted mono">${i + 1}</span><span class="nm" title="${esc(c.name)}">${esc(c.name)} <span class="muted" style="font-size:12px">· ${esc(short(dname[c.d]))}</span></span><span class="v mono">${fmt(c.v)}</span><div class="b"><i style="width:${100 * c.v / mx}%"></i></div></div>`).join('') || '<div class="empty">маълумот йўқ</div>';

  // --- table
  $('#t-mon-h').textContent = MSHORT[cm];
  const tot = rows.reduce((a, r) => ({ act: a.act + r.act, per: a.per + (r.per || 0), yr: a.yr + (r.yr || 0), prev: a.prev + (r.prev || 0), mon: a.mon + r.mon, day: a.day + r.day }), { act: 0, per: 0, yr: 0, prev: 0, mon: 0, day: 0 });
  if (!F.dists.size && !F.tar) { tot.per = planOf('period'); tot.yr = planOf('year'); tot.prev = planOf('prev'); }
  if (F.tar) { tot.per = null; tot.yr = null; tot.prev = null; }
  const tr = (r, cls) => { const pp = pct(r.act, r.per), gg = pct(r.act, r.prev);
    return `<tr class="${cls}"><td>${esc(r.name)}</td><td class="num">${fmt(r.yr)}</td><td class="num">${fmt(r.per)}</td><td class="num">${fmt(r.act)}</td><td class="num">${r.per != null ? (r.act - r.per >= 0 ? '+' : '−') + fmt(Math.abs(r.act - r.per)) : '—'}</td><td class="num">${fmt(pp)}</td><td><div class="bar"><i class="${pp >= 100 ? 'over' : ''}" style="width:${Math.min(100, pp || 0)}%"></i></div></td><td class="num">${fmt(r.prev)}</td><td class="num">${fmt(gg)}</td><td class="num">${fmt(r.mon)}</td><td class="num">${fmt(r.day, 2)}</td></tr>`; };
  $('#t-dist tbody').innerHTML = rows.map(r => tr(r, '')).join('') + tr({ ...tot, name: F.dists.size ? 'Жами (танланган)' : 'Бухоро вилояти' }, 'total');
}

// ---------------------------------------------------------------- KUNLIK
const K = { y: null, m: null, sel: null, pv: null, file: null };
function nextDate(iso) { return isoNext(iso); }   // local date, not UTC (O1)
async function gotoDay(iso) { K.sel = iso; K.y = +iso.slice(0, 4); K.m = +iso.slice(5, 7); await drawCal(); await showDay(); }
loaders.daily = async () => {
  if (!S.districts.length) S.districts = await api('/api/districts');
  const today = todayISO();
  const last = S.status.last_date || today;
  let start = nextDate(last); if (start > today) start = today;   // the first day still waiting for a GTD file
  if (!K.sel) { K.sel = start; K.y = +start.slice(0, 4); K.m = +start.slice(5, 7); }
  $('#d-badge').textContent = S.status.last_date ? 'Oxirgi ma\'lumot: ' + dmy(S.status.last_date) : 'Baza bo\'sh';
  await Promise.all([drawCal(), showDay()]);
};
$('#cal-prev').onclick = () => { K.m--; if (K.m < 1) { K.m = 12; K.y--; } drawCal().catch(e => toast(e.message, true)); };
$('#cal-next').onclick = () => { K.m++; if (K.m > 12) { K.m = 1; K.y++; } drawCal().catch(e => toast(e.message, true)); };
async function drawCal() {
  const c = await api(`/api/calendar?y=${K.y}&m=${K.m}`);
  const el = $('#cal'); el.innerHTML = ['Ду', 'Се', 'Чо', 'Па', 'Жу', 'Ша', 'Як'].map(x => `<div class="dow">${x}</div>`).join('');
  $('#cal-title').textContent = MONTHS[K.m - 1] + ' ' + K.y;
  const off = (new Date(K.y, K.m - 1, 1).getDay() + 6) % 7;
  for (let i = 0; i < off; i++) el.insertAdjacentHTML('beforeend', '<div></div>');
  const today = todayISO();
  let msum = 0;
  c.days.forEach(x => { const wd = new Date(x.date).getDay(); const fut = x.date > today;
    let dot = 'none', s = '', st = '';
    if (x.state === 'loaded') { dot = 'ok'; s = fmt((x.san || 0) + (x.mev || 0)); st = x.gtd + ' ГТД'; msum += (x.san || 0) + (x.mev || 0); }
    else if (x.state === 'opening') { dot = 'open'; st = 'қолдиқ'; }
    else if (S.status.template && x.date <= S.status.template.through && !fut) { dot = 'open'; st = 'жадвалда'; }
    else if (!fut && wd !== 0 && c.first_date && x.date > c.first_date) { dot = 'warn'; st = 'файл йўқ'; }
    const cls = ['day', (wd === 0 || wd === 6) ? 'off' : '', fut ? 'future' : '', x.date === K.sel ? 'sel' : ''].join(' ');
    el.insertAdjacentHTML('beforeend', `<button class="${cls}" data-k="${x.date}" ${fut ? 'disabled' : ''}><span class="n">${+x.date.slice(8)}<i class="dot ${dot}"></i></span><span class="s">${s}</span><span class="st">${st}</span></button>`); });
  $('#cal-sum').textContent = fmt(msum);
  el.querySelectorAll('.day').forEach(b => b.onclick = () => { if (b.disabled) return; K.sel = b.dataset.k; el.querySelectorAll('.day').forEach(x => x.classList.toggle('sel', x === b)); showDay().catch(e => toast(e.message, true)); });
}
async function showDay() {
  const D = K.sel; const x = await api('/api/day?date=' + D);
  const dt = new Date(D);
  $('#d-sel-t').textContent = dmy(D) + ' · ' + DOWF[dt.getDay()];
  const dn = Object.fromEntries(S.districts.map(v => [v.code, v.name_uz]));
  if (x.exact) {
    $('#d-day').innerHTML = `${fmt(x.day.total, 2)}<small> минг $</small><div class="muted" style="font-size:12px;font-family:inherit">саноат ${fmt(x.day.sanoat, 2)} · мева ${fmt(x.day.meva, 2)}</div>`;
    $('#d-ytd').innerHTML = `${fmt(x.ytd.total)}<small> минг $</small><div class="muted" style="font-size:12px;font-family:inherit">саноат ${fmt(x.ytd.sanoat)} · мева ${fmt(x.ytd.meva)}</div>`;
    $('#dl-day').disabled = false; $('#dl-cum').disabled = false; $('#dl-svn').disabled = false;
    $('#d-note').textContent = x.date === x.opening_date ? 'Бу кун — бошланғич қолдиқ санаси: рақамлар сизнинг эски жадвалингиздан олинган.' : '';
  } else {
    $('#d-day').innerHTML = '<small>қолдиқ ичида</small>'; $('#d-ytd').innerHTML = '<small>—</small>';
    $('#dl-day').disabled = true; $('#dl-cum').disabled = true; $('#dl-svn').disabled = true;
    $('#d-note').textContent = `Бу сана бошланғич қолдиқ (${dmy(x.opening_date)} гача) ичида — кунлик тафсилот базада йўқ.`;
  }
  $('#dl-day').textContent = '📗 ' + dmy(D).slice(0, 5) + ' · kunlik Excel';
  $('#dl-cum').textContent = '📗 «' + dmy(isoNext(D)) + ' йил экспорт» · o\'sib boruvchi';
  $('#dl-day').onclick = () => download('/api/export/day?date=' + D, `${dmy(D)} кунлик ГТД свод.xlsx`);
  $('#dl-cum').onclick = () => download('/api/export/cumulative?date=' + D, `${dmy(isoNext(D))} йил экспорт.xlsx`);
  // СВОД (карантин) + 13 туман номма-ном (ҳар бири алоҳида варақ) — шаблонга боғлиқ эмас
  $('#dl-svn').textContent = '📗 «' + dmy(isoNext(D)) + '» свод (карантин) + туманлар номма-ном';
  $('#dl-svn').onclick = () => openSvnModal(D).catch(e => toast(e.message, true));
  const T = S.status.template;
  if (!T) { $('#dl-cum').disabled = true; $('#d-tpl').innerHTML = "O'sib boruvchi Excel uchun Sozlamalar → «2. O'z jadvalingiz» ga jadvalingizni (.xlsx) yuklang."; }
  else if (D < T.through) { $('#dl-cum').disabled = true; $('#d-tpl').innerHTML = `Shablon jadvalingiz <b>${dmy(T.through)}</b> gacha — bu kun uchun o'z faylingizdan foydalaning.`; }
  else if (+D.slice(5, 7) !== +T.cur_month) { $('#dl-cum').disabled = true; $('#d-tpl').innerHTML = `Yangi oy: jadvalingiz ${MONTHS[T.cur_month - 1]} oyi uchun. Jadvalni ${MONTHS[+D.slice(5, 7) - 1]} oyiga tayyorlab Sozlamalar → «2» ga yuklang.`; }
  else { $('#dl-cum').disabled = false; $('#d-tpl').innerHTML = `Excel: «${esc(T.file)}» (${dmy(T.through)} gacha) + ${D > T.through ? dmy(isoNext(T.through)).slice(0, 5) + ' – ' + dmy(D).slice(0, 5) + ' kunlari' : "qo'shimcha kun yo'q"}.`; }
  const ups = x.uploads || [];
  $('#d-uploads').innerHTML = ups.length ? '<div class="muted" style="font-size:12px;margin:10px 0 4px">Shu kunning GTD fayllari</div>' + ups.map(u => `<div class="check"><div class="ic ${u.status === 'saved' ? 'ok' : 'warn'}">${u.status === 'saved' ? '✓' : '–'}</div><div style="flex:1"><b>${esc(u.filename)}</b><span>${esc(u.loaded_at.slice(0, 16))} · sanoat ${fmt(u.sum_sanoat, 2)} · meva ${fmt(u.sum_meva, 2)}${u.status === 'saved' ? '' : ' · bekor qilingan' + (u.note ? ': ' + esc(u.note) : '')}</span></div>
      <button class="btn sm" data-dlup="${u.id}" data-name="${esc(u.filename)}">Fayl</button>${u.status === 'saved' ? `<button class="btn sm danger" data-voidday="${u.id}">Bekor qilish</button>` : ''}</div>`).join('') : '';
  $$('[data-dlup]').forEach(b => b.onclick = () => download('/api/uploads/file?id=' + b.dataset.dlup, b.dataset.name));
  $$('[data-voidday]').forEach(b => b.onclick = async () => {
    if (b.dataset.armed !== '1') { b.dataset.armed = '1'; b.textContent = 'Aniqmi?'; setTimeout(() => { b.dataset.armed = ''; b.textContent = 'Bekor qilish'; }, 4000); return; }
    try { await api('/api/uploads/void', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: +b.dataset.voidday, reason: dmy(D) + ' kuni sahifasidan bekor qilindi' }) });
      toast('Yuklash bekor qilindi (zaxira olindi)'); S.dash = null; await loadStatus(); await loaders.daily(); } catch (e) { toast(e.message, true); } });
  $('#d-res-t').textContent = 'Korxonalar · ' + dmy(D);
  $('#d-comp').innerHTML = x.companies.length ? x.companies.map(c => `<tr><td class="mono">${esc(c.inn)}</td><td>${esc(c.name)} ${c.new ? '<span class="pill gold">янги</span>' : ''}</td><td>${esc(short(dn[c.district_code] || '?'))}</td><td class="num">${c.gtd}</td><td class="num">${fmt(c.day, 2)}</td><td class="num">${fmt(c.month)}</td><td class="num">${fmt(c.ytd)}</td></tr>`).join('')
    + `<tr class="total"><td colspan="3">Саноат жами</td><td class="num">${x.companies.reduce((s, c) => s + c.gtd, 0)}</td><td class="num">${fmt(x.day.sanoat, 2)}</td><td></td><td class="num">${fmt(x.ytd.sanoat)}</td></tr>`
    + (x.memo_rows.length ? x.memo_rows.map(m => `<tr class="subrow"><td class="mono">${esc(m.inn)}</td><td colspan="3">${esc(m.exporter)} <span class="pill info">алоҳида ҳисоб</span></td><td class="num">${fmt(m.s, 2)}</td><td colspan="2"></td></tr>`).join('') : '')
    : `<tr><td colspan="7" class="empty">${x.exact ? 'бу кун учун ГТД юкланмаган' : 'қолдиқ даври'}</td></tr>`;
  $('#d-meva').innerHTML = x.meva_rows.length ? x.meva_rows.map(m => `<tr><td class="mono">${esc(m.inn)}</td><td>${esc(m.exporter)}</td><td>${esc(m.grown_district)}</td><td>${esc((m.product || '').slice(0, 50))}</td><td>${esc(m.country)}</td><td class="num">${fmt(m.stat_usd, 2)}</td></tr>`).join('') : '<tr><td colspan="6" class="empty">йўқ</td></tr>';
}
// upload
const drop = $('#drop');
['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', e => { if (e.dataTransfer.files[0]) preview(e.dataTransfer.files[0]); });
$('#file').onchange = e => { if (e.target.files[0]) preview(e.target.files[0]); e.target.value = ''; };
async function preview(file, replace = false) {
  if (S.status.readonly) { toast('Faqat ko\'rish rejimi — yuklab bo\'lmaydi', true); return; }
  if (!K.sel) { toast('Avval kalendardan fayl sanasini tanlang', true); return; }
  toast('Fayl tekshirilmoqda…'); K.file = file;
  try {
    const pv = await api('/api/upload/preview', { method: 'POST', body: file, headers: { 'X-Filename': encodeURIComponent(file.name), 'X-Date': K.sel || '', 'X-Replace': replace ? '1' : '0' } });
    K.pv = pv; renderPreview(pv); toast('Tekshiruv tayyor');
  } catch (e) { toast(e.message, true); }
}
function renderPreview(pv) {
  $('#pv').hidden = false;
  const c = pv.counts, s = pv.sums;
  $('#pv-steps').innerHTML = [[fmt0(pv.rows_total), 'faylda qator'], [c.sanoat, 'Buxoro (INN)'], [c.meva, 'meva-sabzavot'], [c.candidates, 'yangi korxona qatori'], [c.dups, 'dublikat'], [fmt(s.sanoat + s.meva, 2), 'ming $ (saqlanadi)']]
    .map(([v, l]) => `<div class="step"><b>${v}</b>${l}</div>`).join('');
  $('#pv-checks').innerHTML = `<div class="muted" style="font-size:12.5px;margin-bottom:4px">📄 ${esc(pv.file)} · ${Object.keys(pv.dates).map(dmy).join(', ')}</div>` + pv.checks.map(k => `<div class="check"><div class="ic ${k.level}">${k.level === 'ok' ? '✓' : (k.level === 'bad' ? '✕' : '!')}</div><div><b>${esc(k.title)}</b><span>${esc(k.detail)}</span></div></div>`).join('');
  const fdates = Object.keys(pv.dates).sort();
  if (K.sel && fdates.length && !fdates.includes(K.sel)) {     // the calendar is on another day than the file itself
    $('#pv-checks').insertAdjacentHTML('afterbegin',
      `<div class="check"><div class="ic bad">✕</div><div style="flex:1"><b>Kalendarda boshqa kun tanlangan</b>
       <span>Fayl ${fdates.map(dmy).join(', ')} kuniga tegishli, siz esa ${dmy(K.sel)} ni tanlagansiz.</span>
       <button class="btn primary" id="pv-fixdate" style="margin-top:6px">${dmy(fdates[0])} ni tanlash va qayta tekshirish</button></div></div>`);
    $('#pv-fixdate').onclick = async () => { await gotoDay(fdates[0]); await preview(K.file, !!pv.replace); };
  }
  const opts = S.districts.map(d => `<option value="${d.code}">${esc(d.name_uz)}</option>`).join('');
  $('#pv-cands').innerHTML = pv.candidates.length ? `<h2 style="margin-top:12px">Yangi korxonalar — tumanni tasdiqlang</h2>` + pv.candidates.map(k => `<div class="cand"><div><b>${esc(k.name)}</b> <span class="mono muted">${esc(k.inn)}</span><div class="muted" style="font-size:12px">${k.nomma_only ? '<span class="pill warn">номманом да бор, божхона базасида йўқ</span> ' : ''}${esc(k.address)}${k.sum != null ? ' · ' + fmt(k.sum, 2) + ' минг $' : ''}</div></div>
      <div><select class="sel" data-inn="${esc(k.inn)}" id="cand-${esc(k.inn)}"><option value="">— qo'shilmasin —</option>${opts}</select></div></div>`).join('') : '';
  if (pv.same_day && pv.same_day.length) {
    $('#pv-cands').insertAdjacentHTML('afterbegin', `<label class="check" style="cursor:pointer"><input type="checkbox" id="pv-replace" ${pv.replace ? 'checked' : ''} style="margin:4px 10px 0 2px"><div><b>Eskisini almashtirish</b><span>${pv.same_day.map(u => '«' + esc(u.filename) + '» · ' + esc(u.loaded_at.slice(0, 16)) + ' · ' + fmt(u.sum, 2) + ' ming $').join('; ')} — bekor qilinadi (tarixda qoladi), o'rniga shu fayl saqlanadi</span></div></label>`);
    $('#pv-replace').onchange = e => preview(K.file, e.target.checked);
  }
  pv.candidates.forEach(k => { const el = document.getElementById('cand-' + k.inn); if (el) el.value = (k.nomma_only && !k.address_ok) ? '' : (k.district_code || ''); });
  const qs = pv.questions || [];
  if (qs.length) {
    const dsel = (id, v) => `<select class="sel q-d" id="${id}"><option value="">— tumanni tanlang —</option>${opts}</select>`;
    $('#pv-cands').insertAdjacentHTML('beforeend', `<h2 style="margin-top:12px">Meva-sabzavot — aniqlashtiring</h2>` + qs.map((q, i) => q.type === 'md'
      ? `<div class="cand q" data-key="${esc(q.key)}" data-type="md"><div><b>${esc(q.name)}</b> <span class="mono muted">${esc(q.inn)}</span><div class="muted" style="font-size:12px"><span class="pill warn">Buxoro karantini, tumani aniqlanmadi</span> «${esc(q.grown || 'tuman ko‘rsatilmagan')}» · ${esc(q.products.join('; '))} · ${fmt(q.sum, 2)} минг $</div></div>
         <div>${dsel('q-d-' + i)}</div></div>`
      : `<div class="cand q" data-key="${esc(q.key)}" data-type="kind"><div><b>${esc(q.name)}</b> <span class="mono muted">${esc(q.inn)}</span><div class="muted" style="font-size:12px"><span class="pill warn">07/08 kodi, o'stirilgan viloyati yo'q</span> ${esc(q.products.join('; '))} · ${q.rows} qator · ${fmt(q.sum, 2)} минг $</div></div>
         <div style="display:flex;flex-direction:column;gap:6px"><select class="sel q-k"><option value="">— qayerga? —</option><option value="sanoat">Sanoat</option><option value="meva_x">Meva-sabzavot (umumiy svod, karantinsiz)</option><option value="meva">Meva-sabzavot + Buxoro karantini</option></select>${dsel('q-kd-' + i)}</div></div>`).join(''));
    qs.forEach((q, i) => { const d = document.getElementById((q.type === 'md' ? 'q-d-' : 'q-kd-') + i); if (q.type === 'kind') { d.hidden = true; d.value = q.district_code || ''; } });
    $$('#pv-cands .q').forEach(el => el.addEventListener('change', () => { const k = el.querySelector('.q-k'); if (k) el.querySelector('.q-d').hidden = k.value !== 'meva'; updateSaveState(); }));
  }
  updateSaveState();
}
function pvAnswers() {
  const ans = {}; let missing = 0;
  $$('#pv-cands .q').forEach(el => {
    const d = el.querySelector('.q-d').value;
    if (el.dataset.type === 'md') { if (d) ans[el.dataset.key] = { district_code: d }; else missing++; }
    else { const k = el.querySelector('.q-k').value; if (!k || (k === 'meva' && !d)) missing++; else ans[el.dataset.key] = { kind: k, district_code: k === 'meva' ? d : null }; }
  });
  return { ans, missing };
}
function updateSaveState() {
  const pv = K.pv; if (!pv) return;
  const { missing } = pvAnswers();
  $('#pv-save').disabled = !pv.can_save || missing > 0 || S.status.readonly;
  $('#pv-save').textContent = !pv.can_save ? 'Saqlab bo\'lmaydi — xatolarni ko\'ring' : (missing ? `Meva-sabzavot savollariga javob bering (${missing})` : 'Tasdiqlash va saqlash');
}
$('#pv-cancel').onclick = () => { K.pv = null; $('#pv').hidden = true; };
$('#pv-save').onclick = async () => {
  if (!K.pv) return;
  const accepted = {};
  $$('#pv-cands select').forEach(s => { if (s.value) accepted[s.dataset.inn] = { district_code: s.value }; });
  $('#pv-save').disabled = true;
  try {
    const r = await api('/api/upload/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: K.pv.token, accepted, replace: !!K.pv.replace, answers: pvAnswers().ans }) });
    toast(`Saqlandi: ${r.rows} qator, ${fmt(r.sum, 2)} ming $` + (r.new_inns.length ? `, yangi korxona: ${r.new_inns.length}` : ''));
    const dates = Object.keys(K.pv.dates).sort(); K.sel = dates[dates.length - 1]; K.y = +K.sel.slice(0, 4); K.m = +K.sel.slice(5, 7);
    K.pv = null; $('#pv').hidden = true; S.dash = null;
    await loadStatus(); await loaders.daily();
  } catch (e) { toast(e.message, true); $('#pv-save').disabled = false; }
};

// ---------------------------------------------------------------- NOMMA-NOM
const emptyGuard = (sel) => { if (!S.status.last_date) { $(sel).innerHTML = '<tr><td class="empty">Baza bo\'sh — avval Sozlamalar va Kunlik hisobot bo\'limida ma\'lumot kiriting</td></tr>'; return true; } return false; };
loaders.nom = async () => {
  if (emptyGuard('#t-nom tbody')) return;
  if (!S.districts.length) S.districts = await api('/api/districts');
  if (!S.dash) S.dash = await api('/api/dashboard?date=' + S.status.last_date);
  const sel = $('#nom-d'); if (sel.options.length <= 1) S.districts.forEach(d => sel.add(new Option(d.name_uz, d.code)));
  renderNom();
};
['#nom-q', '#nom-d', '#nom-t'].forEach(s => $(s).addEventListener('input', () => renderNom()));
$('#nom-xl').onclick = () => download('/api/export/nomma?date=' + S.dash.date + '&district=' + encodeURIComponent($('#nom-d').value) + '&t=' + ($('#nom-t').value || 'all') + '&q=' + encodeURIComponent($('#nom-q').value.trim()), `${$('#nom-d').value ? $('#nom-d').options[$('#nom-d').selectedIndex].text : 'Бухоро вилояти'} экспортёрлари ${dmy(isoNext(S.dash.date))}.xlsx`);
$('#t-nom').addEventListener('click', e => { const a = e.target.closest('.clink[data-inn]'); if (a) openCompany(a.dataset.inn); });
function renderNom() {
  const d = S.dash; if (!d) return;
  const q = $('#nom-q').value.trim(), dc = $('#nom-d').value, t = $('#nom-t').value;
  $('#nom-sub').textContent = `корхоналар × ойлар · ${dmy(d.date)} · минг долл.`;
  const cm = d.month;
  $('#t-nom thead').innerHTML = `<tr><th>№</th><th>№ туман</th><th>ИНН</th><th>Корхона номи</th>${MSHORT.slice(0, cm).map(m => `<th class="num">${m}</th>`).join('')}<th class="num">1 кунда</th><th class="num">Жами</th><th>Тармоқ</th></tr>`;
  let html = '', n = 0; const grand = new Array(cm).fill(0); let gDay = 0, gTot = 0;
  S.districts.forEach(dd => {
    if (dc && dd.code !== dc) return;
    const cs = d.companies.filter(c => c.d === dd.code && (!t || c.t === t) && (!q || smatch(q, c.inn, c.name))).sort((a, b) => b.total - a.total);
    if (!cs.length) return;
    const sums = new Array(cm).fill(0); let sd = 0, st = 0;
    cs.forEach(c => { c.m.forEach((v, i) => sums[i] += v || 0); sd += c.day; st += c.total; });
    sums.forEach((v, i) => grand[i] += v); gDay += sd; gTot += st;
    html += `<tbody class="dist"><tr class="total dist"><td></td><td></td><td></td><td>${esc(dd.name_uz)}</td>${sums.map(v => `<td class="num">${fmt(v)}</td>`).join('')}<td class="num">${fmt(sd, 2)}</td><td class="num">${fmt(st)}</td><td></td></tr>`;
    html += cs.map((c, i) => `<tr><td class="muted">${++n}</td><td class="muted">${i + 1}</td><td class="mono">${esc(c.inn)}</td><td><span class="clink" data-inn="${esc(c.inn)}">${esc(c.name)}</span>${c.t === 'meva' ? ' <span class="pill gold">мева</span>' : ''}</td>${c.m.map(v => `<td class="num">${v ? fmt(v) : ''}</td>`).join('')}<td class="num">${c.day ? fmt(c.day, 2) : ''}</td><td class="num">${fmt(c.total)}</td><td class="muted">${esc(c.tarmoq)}</td></tr>`).join('') + '</tbody>';
  });
  // har tuman — alohida <tbody>: svod qatori tepaga yopishadi va blok tugaganda keyingisi uni suradi
  $$('#t-nom tbody').forEach(b => b.remove());
  $('#t-nom thead').insertAdjacentHTML('afterend', `<tbody><tr class="total"><td></td><td></td><td></td><td>Жами (филтр)</td>${grand.map(v => `<td class="num">${fmt(v)}</td>`).join('')}<td class="num">${fmt(gDay, 2)}</td><td class="num">${fmt(gTot)}</td><td></td></tr></tbody>` + html);
  // tuman svod qatori tepaga yopishadi (thead ostida) — o'qilayotgan blok qaysi tumanniki ekani ko'rinib turadi
  $('#t-nom').style.setProperty('--nom-th', Math.max(0, ($('#t-nom thead').getBoundingClientRect().height || 33) - 1) + 'px');
  nomStickyPush();
}

// tuman svod qatori (sticky) blok tugaganda keyingi blok uni yuqoriga suradi — brauzer buni tbody ichida o'zi qilmaydi
function nomStickyPush() {
  const tw = $('#p-nom .tw'); if (!tw) return;
  const top = tw.getBoundingClientRect().top + (parseFloat(getComputedStyle($('#t-nom')).getPropertyValue('--nom-th')) || 32);
  $$('#t-nom tbody.dist').forEach(b => {
    const tr = b.firstElementChild; if (!tr) return;
    const h = tr.offsetHeight, end = b.getBoundingClientRect().bottom;
    const over = top + h - end;                     // qator blok chegarasidan qancha chiqib ketgan
    tr.style.transform = over > 0 ? `translateY(${-Math.min(over, h + 2)}px)` : '';
  });
}
$('#p-nom .tw').addEventListener('scroll', () => requestAnimationFrame(nomStickyPush), { passive: true });

// ---------------------------------------------------------------- SVOD
loaders.svod = async () => {
  if (emptyGuard('#t-svod tbody')) return;
  if (!S.districts.length) S.districts = await api('/api/districts');
  if (!S.dash) S.dash = await api('/api/dashboard?date=' + S.status.last_date);
  const d = S.dash, cm = d.month - 1;
  $('#svod-sub').textContent = `${dmy(d.date)} ҳолатига · минг АҚШ долл.`;
  $('#svod-prev').textContent = (d.prev_year_source && d.prev_year_source.text) ? d.prev_year_source.text : ((d.prev_year_label || '') + `, ${d.prev_year_days} кунга мутаносиб`);
  $('#svod-xl').onclick = () => download('/api/export/cumulative?date=' + d.date, `${dmy(isoNext(d.date))} йил экспорт.xlsx`);
  $('#t-svod thead').innerHTML = `<tr><th>Шаҳар ва туманлар</th><th class="num">Йил прогнози</th><th class="num">Янв–${MSHORT[cm]} прогноз</th><th class="num">Амалда</th><th class="num">Фарқ</th><th class="num">%</th><th class="num">${MSHORT[cm]} прогноз</th><th class="num">${MSHORT[cm]} амалда</th><th class="num">1 кунда</th><th class="num">Фарқ</th><th class="num">%</th><th class="num">Ўтган йил</th><th class="num">Фарқ</th><th class="num">%</th></tr>`;
  const agg = (code, kind) => { const cs = d.companies.filter(c => c.t === 'sanoat' && (!code || c.d === code)); const ds = d.districts.filter(x => !code || x.code === code);
    const s = { ytd: cs.reduce((a, c) => a + c.total, 0), mon: cs.reduce((a, c) => a + (c.m[cm] || 0), 0), day: cs.reduce((a, c) => a + c.day, 0) };
    const m = { ytd: ds.reduce((a, x) => a + x.meva.ytd, 0), mon: ds.reduce((a, x) => a + x.meva.month, 0), day: ds.reduce((a, x) => a + x.meva.day, 0) };
    return kind === 'sanoat' ? s : kind === 'meva' ? m : { ytd: s.ytd + m.ytd, mon: s.mon + m.mon, day: s.day + m.day }; };
  const row = (name, f, p, cls) => { p = p || {};
    const dP = f.ytd - (p.period || 0), dM = f.mon - (p.month || 0), dY = f.ytd - (p.prev || 0);
    const sg = v => (v >= 0 ? '+' : '−') + fmt(Math.abs(v));
    return `<tr class="${cls}"><td>${esc(name)}</td><td class="num">${fmt(p.year)}</td><td class="num">${fmt(p.period)}</td><td class="num">${fmt(f.ytd)}</td><td class="num">${sg(dP)}</td><td class="num">${fmt(pct(f.ytd, p.period))}</td><td class="num">${fmt(p.month)}</td><td class="num">${fmt(f.mon)}</td><td class="num">${fmt(f.day, 2)}</td><td class="num">${sg(dM)}</td><td class="num">${fmt(pct(f.mon, p.month))}</td><td class="num">${fmt(p.prev)}</td><td class="num">${sg(dY)}</td><td class="num">${fmt(pct(f.ytd, p.prev))}</td></tr>`; };
  let html = row('Бухоро вилояти жами', agg(null, 'all'), d.region_plan.all, 'total') + row('Саноат маҳсулотлари', agg(null, 'sanoat'), d.region_plan.sanoat, 'subrow') + row('Мева-сабзавотлар', agg(null, 'meva'), d.region_plan.meva, 'subrow');
  d.districts.forEach((x, i) => { html += row(`${i + 1}. ${x.name}`, agg(x.code, 'all'), x.plan.all, 'total') + row('Саноат', agg(x.code, 'sanoat'), x.plan.sanoat, 'subrow') + row('Мева-сабзавот', agg(x.code, 'meva'), x.plan.meva, 'subrow'); });
  $('#t-svod tbody').innerHTML = html;
};

// ---------------------------------------------------------------- KARANTIN
loaders.kar = async () => {
  if (emptyGuard('#t-kar-d tbody')) return;
  if (!S.districts.length) S.districts = await api('/api/districts');
  const k = await api('/api/karantin?date=' + S.status.last_date);
  const dn = Object.fromEntries(S.districts.map(v => [v.code, v.name_uz]));
  $('#kar-h').textContent = dmy(k.date) + ' ҳолатига'; $('#kar-h2').textContent = MONTHS[+k.date.slice(5, 7) - 1] + ' · ' + dmy(k.opening_date) + ' дан кейин';
  let t = { ytd: 0, month: 0, day: 0 };
  const rows = S.districts.map(d => { const v = k.by_district[d.code] || { ytd: 0, month: 0, day: 0 }; t.ytd += v.ytd; t.month += v.month; t.day += v.day;
    return `<tr><td>${esc(d.name_uz)}</td><td class="num">${fmt(v.ytd)}</td><td class="num">${fmt(v.month, 2)}</td><td class="num">${v.day ? fmt(v.day, 2) : ''}</td></tr>`; }).join('');
  $('#t-kar-d tbody').innerHTML = rows + `<tr class="total"><td>Жами</td><td class="num">${fmt(t.ytd)}</td><td class="num">${fmt(t.month, 2)}</td><td class="num">${fmt(t.day, 2)}</td></tr>`;
  $('#t-kar-r').innerHTML = k.rows.length ? k.rows.map(r => `<tr><td>${dmy(r.report_date).slice(0, 5)}</td><td>${esc(r.exporter)}</td><td>${esc(short(dn[r.district_code] || r.grown_district))}</td><td>${esc((r.product || '').slice(0, 50))}</td><td>${esc(r.country)}</td><td class="num">${fmt0(r.netto)}</td><td class="num">${fmt(r.stat_usd, 2)}</td></tr>`).join('') : '<tr><td colspan="7" class="empty">юкланган қатор йўқ</td></tr>';
};

// ---------------------------------------------------------------- KORXONALAR
const R = { list: null, inn: null, prof: null, tab: 'exp', names: null, tarmoq: null };
const KIND = { muammo: 'Муаммо', vazifa: 'Вазифа', murojaat: 'Мурожаат', izoh: 'Изоҳ' };
const KIND_PILL = { muammo: 'bad', vazifa: 'info', murojaat: 'gold', izoh: 'warn' };
const J = body => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
const sigPill = s => `<span class="pill ${s.lvl === 'bad' ? 'bad' : (s.lvl === 'info' ? 'info' : 'warn')}">${esc(s.t)}</span>`;
const pctTxt = p => p == null ? '—' : (p > 999 ? '>999' : fmt0(p)) + '%';
function shareBar(sh, rank, n) {
  if (sh == null) return '<span class="muted">—</span>';
  const w = Math.max(2, Math.min(100, sh));
  return `<div class="pbody"><div class="bar w"><i class="${sh >= 10 ? 'over' : ''}" style="width:${w}%"></i></div><span class="mono">${sh < 0.1 ? '<0,1' : fmt(sh)}%</span>${rank ? `<span class="muted" style="font-size:11.5px;white-space:nowrap">${rank}/${n}</span>` : ''}</div>`;
}
function pctBar(p, py) {
  if (p == null) return py != null ? `<span class="muted mono" title="шу давр режаси 0, йиллик режага нисбатан">йил ${pctTxt(py)}</span>` : '<span class="muted">—</span>';
  return `<div class="pbody"><div class="bar w"><i class="${p >= 100 ? 'over' : ''}" style="width:${Math.max(2, Math.min(100, p))}%"></i></div><span class="mono ${p < 50 ? 't-bad' : ''}">${pctTxt(p)}</span></div>`;
}
const daysAgo = (iso, today) => iso ? Math.round((new Date(today) - new Date(iso)) / 864e5) : null;
function openCompany(inn) { go('reg', inn); }


// ---------------------------------------------------------------- ko'p tanlovli filtr (checkbox ro'yxati)
function multiSel(sel, placeholder, onChange) {
  const host = $(sel);
  host.innerHTML = `<button type="button" class="sel ms-btn"><span class="t"></span><span class="n" hidden></span></button><div class="ms-pop" hidden></div>`;
  const btn = host.querySelector('.ms-btn'), pop = host.querySelector('.ms-pop'), txt = host.querySelector('.t'), cnt = host.querySelector('.n');
  const st = { opts: [], set: new Set() };
  const paint = () => {
    const n = st.set.size;
    const first = (st.opts.find(o => st.set.has(o.v)) || {}).t;
    txt.textContent = n === 0 ? placeholder : (first || `${n} та`);
    cnt.hidden = n < 2; cnt.textContent = '+' + (n - 1);
    btn.classList.toggle('on', n > 0);
  };
  const draw = () => {
    pop.innerHTML = `<button type="button" class="all">◻ Ҳаммасини бекор қилиш</button>` + st.opts.map((o, i) =>
      `<label><input type="checkbox" id="${host.id}-o${i}" value="${esc(o.v)}"${st.set.has(o.v) ? ' checked' : ''}><span>${esc(o.t)}</span></label>`).join('');
    pop.querySelector('.all').onclick = () => { st.set.clear(); draw(); paint(); onChange(); };
    pop.querySelectorAll('input').forEach(i => i.onchange = () => { i.checked ? st.set.add(i.value) : st.set.delete(i.value); paint(); onChange(); });
  };
  btn.onclick = e => { e.stopPropagation(); const open = pop.hidden; document.querySelectorAll('.ms-pop').forEach(x => x.hidden = true); if (open) { draw(); pop.hidden = false; } };
  pop.onclick = e => e.stopPropagation();
  host.addEventListener('keydown', e => { if (e.key === 'Escape') { pop.hidden = true; btn.focus(); } });
  return {
    get value() { return [...st.set].join(','); },
    get list() { return [...st.set]; },            // қийматида вергул бўлиши мумкин (тармоқ номлари) — массив кўриниши
    clear() { st.set.clear(); paint(); },
    toggle(v) { st.set.has(v) ? st.set.delete(v) : st.set.add(v); paint(); },
    has(v) { return st.set.has(v); },
    setOptions(list) { st.opts = list; [...st.set].forEach(v => { if (!list.some(o => o.v === v)) st.set.delete(v); }); paint(); if (!pop.hidden) draw(); },
    close() { pop.hidden = true; }
  };
}
document.addEventListener('click', () => document.querySelectorAll('.ms-pop').forEach(x => x.hidden = true));

const REG_STATUS = [['exporters', 'Экспортёрлар'], ['nophone', 'Телефони йўқ'], ['new', 'Янги корхоналар'], ['issues', 'Очиқ муаммоли'], ['big', 'Туманда улуши катта (10%+)'],
  ['nomonth', 'Шу ойда экспорт йўқ'], ['silent', '45+ кун экспорт йўқ'], ['notbase', 'Базада йўқ / Бухоро эмас'], ['unconfirmed', 'Тасдиқланмаган'],
  ['all', 'Бутун реестр']].map(([v, t]) => ({ v, t }));
const MS = {};
async function regFilters() {
  if (!S.districts.length) S.districts = await api('/api/districts');
  const sel = $('#iss-d'); if (sel.options.length <= 1) S.districts.forEach(d => sel.add(new Option(d.name_uz, d.code)));
  if (!MS.s) {
    const re = () => loadRegList().catch(e => toast(e.message, true));
    MS.s = multiSel('#reg-s', 'Барча ҳолатлар', re); MS.s.setOptions(REG_STATUS);
    MS.d = multiSel('#reg-d', 'Барча туманлар', re);
    MS.t = multiSel('#reg-t', 'Барча тармоқлар', re);
    MS.k = multiSel('#reg-k', 'Барча турлар', re); MS.k.setOptions([{ v: 'sanoat', t: 'Саноат' }, { v: 'meva', t: 'Мева-сабзавот' }]);
    MS.s.toggle('exporters');
    $('#reg-clr').onclick = () => { $('#reg-q').value = ''; ['s', 'd', 't', 'k'].forEach(x => MS[x].clear()); MS.s.toggle('exporters'); re(); };
  }
  MS.d.setOptions(S.districts.map(d => ({ v: d.code, t: d.name_uz })));
}
loaders.reg = async (inn) => {
  await regFilters();
  if (inn) return showProfile(inn);
  R.inn = null; $('#reg-prof').hidden = true; $('#reg-list').hidden = false;
  await loadRegList();
};
function regQuery() {
  return new URLSearchParams({ q: $('#reg-q').value.trim(), status: MS.s.value, district: MS.d.value, tarmoq: MS.t.value, kind: MS.k.value, sort: $('#reg-o').value });
}
async function loadRegList() {
  const L = await api('/api/companies/list?' + regQuery()); R.list = L;
  const k = L.kpi;
  MS.t.setOptions(L.tarmoqlar.map(t => ({ v: t, t })));
  $('#reg-mh').textContent = MONTHS[L.month - 1];
  $('#reg-sub').textContent = `${L.year} йил · ${dmy(L.today)} ҳолатига · минг АҚШ доллари`;
  const on = v => MS.s.has(v) ? ' on' : '';
  $('#reg-kpi').classList.remove('k6'); $('#reg-kpi').innerHTML = [
    `<div class="kpi click${on('nophone')}" data-s="nophone" style="border-top:3px solid var(--bad)"><div class="l">Телефони йўқ</div><div class="v ${k.nophone ? 't-bad' : ''}">${fmt0(k.nophone)}</div><div class="d">экспортёрлар орасида алоқаси киритилмаган</div></div>`,
    `<div class="kpi accent click${on('exporters')}" data-s="exporters"><div class="l">Экспортёрлар</div><div class="v">${fmt0(k.exporters)}</div><div class="d">йил бошидан экспорт қилганлар</div></div>`,
    `<div class="kpi gold click${on('new')}" data-s="new"><div class="l">Янги корхоналар</div><div class="v">${fmt0(k.new)}</div><div class="d">ГТД да биринчи марта чиққанлар</div></div>`,
    `<div class="kpi click${on('issues')}" data-s="issues"><div class="l">Очиқ муаммолар</div><div class="v ${k.issues ? 't-bad' : ''}">${fmt0(k.issues)}</div><div class="d">${k.overdue ? `<span class="t-bad">муддати ўтган: ${k.overdue}</span>` : 'муддати ўтгани йўқ'}</div></div>`].join('');
  $$('#reg-kpi .kpi.click').forEach(e => e.onclick = () => {
    if (e.dataset.s === 'nophone') { const was = MS.s.has('nophone'); MS.s.clear(); MS.s.toggle(was ? 'exporters' : 'nophone'); }   // faqat telefoni yo'qlar ro'yxati
    else MS.s.toggle(e.dataset.s);
    loadRegList().catch(er => toast(er.message, true)); });
  const filters = [$('#reg-q').value.trim(), MS.d.value, MS.t.value, MS.k.value].filter(Boolean).length + (MS.s.value === 'exporters' ? 0 : 1);
  $('#reg-clr').hidden = !filters;
  const badges = r => [r.new_date ? `<span class="pill gold">янги · ${dmy(r.new_date).slice(0, 5)}</span>` : '', r.excluded ? '<span class="pill info">алоҳида ҳисоб</span>' : '',
    r.kind === 'meva' ? '<span class="pill info">мева</span>' : '', r.issues ? `<span class="pill bad">${r.issues} муаммо</span>` : '', !r.registered ? '<span class="pill warn">реестрда йўқ</span>' : '',
    r.bukhara === 0 ? '<span class="pill bad">Бухоро эмас</span>' : (r.bukhara_from || r.bukhara_to) ? `<span class="pill warn">Бухоро ${r.bukhara_from ? dmy(r.bukhara_from) + ' дан' : ''}${r.bukhara_to ? ' ' + dmy(r.bukhara_to) + ' гача' : ''}</span>` : '', r.registered && !r.confirmed ? '<span class="pill warn">тасдиқланмаган</span>' : ''].filter(Boolean).join(' ');
  const rows = L.rows;
  let sm = 0; rows.forEach(r => { sm += r.month || 0; });
  const regShare = k.region_ytd ? 100 * k.sum_counted / k.region_ytd : null;   // алоҳида ҳисобдагилар вилоят жамига кирмайди
  $('#t-reg tbody').innerHTML = rows.length ? `<tr class="total"><td></td><td>Жами: ${fmt0(k.count)} та</td><td></td><td class="num">${fmt(k.sum_ytd)}${k.sum_excluded ? `<div class="muted" style="font-size:11px;font-weight:400">алоҳида ҳисоб: ${fmt(k.sum_excluded)}</div>` : ''}</td><td class="num">${fmt(sm)}</td><td></td><td class="num">${fmt(k.region_ytd)}</td><td>${regShare != null ? `<span class="mono">${fmt(regShare)}%</span> <span class="muted" style="font-size:11.5px">вилоят экспортидан</span>` : ''}</td><td></td></tr>` +
    rows.map(r => `<tr class="rowlink" data-inn="${esc(r.inn)}"><td class="mono">${esc(r.inn)}</td><td><span class="clink">${esc(r.name || '—')}</span> ${badges(r)}${r.tarmoq ? `<div class="muted" style="font-size:12px">${esc(r.tarmoq)}</div>` : ''}</td><td>${esc(short(r.district || '—'))}</td><td class="num">${r.ytd ? fmt(r.ytd) : '—'}</td><td class="num">${r.month ? fmt(r.month) : ''}</td><td class="mono">${r.last ? dmy(r.last) : '—'}</td>
      <td class="num">${r.district_ytd ? fmt(r.district_ytd) : '—'}</td><td>${shareBar(r.share, r.rank, r.district_n)}</td><td>${r.signals.map(sigPill).join(' ')}</td></tr>`).join('')
    : `<tr><td colspan="9" class="empty">Бу филтр бўйича корхона топилмади${filters > 1 ? ' — ' + filters + ' та шарт бирга қўлланилмоқда' : ''}.<br><button class="btn" style="margin-top:8px" onclick="document.getElementById('reg-clr').click()">✕ Filtrni tozalash</button></td></tr>`;
  $$('#t-reg tr[data-inn]').forEach(tr => tr.onclick = () => openCompany(tr.dataset.inn));
  const notes = [];
  if (k.count > rows.length) notes.push(`Биринчи ${fmt0(rows.length)} таси кўрсатилди — қидирув ёки филтрдан фойдаланинг (Excel да ҳаммаси).`);
  notes.push('Туманда улуши — корхонанинг йил бошидан экспорти ўз туманининг жами экспортига нисбатан; ёнида туман ичидаги ўрни. Алоҳида ҳисобдаги корхоналар (БНПЗ, SDK) туман жамига кирмайди.');
  if (!k.base_detail) notes.unshift('<b class="t-bad">Божхона ойлик базасини Sozlamalar → 1 орқали қайта юкланг</b> — корхона профилида маҳсулот, давлат ва ГТД тарихи шундан кейин чиқади (ҳозир фақат ойлик суммалар).');
  else if (k.base_legacy) notes.unshift('<b>Божхона базасини Sozlamalar → 1 орқали бир марта қайта юкланг</b> — маълумот дарахти (ГТД, божхона пости, транспорт, маҳсулот номлари, импорт) тўлиқ шундан кейин тўлади; суммалар ўзгармайди.');
  notes.push('Экспорт: божхона ойлик базаси + ундан кейинги кунлик ГТД (барча турлар, алоҳида ҳисобдагилар ҳам). Сигнал: режа бор экспорт йўқ · шу давр режасининг 50% дан кам · 45+ кун экспорт йўқ.');
  $('#reg-note').innerHTML = notes.join('<br>');
}
let regTm; $('#reg-q').addEventListener('input', () => { clearTimeout(regTm); regTm = setTimeout(() => loadRegList().catch(e => toast(e.message, true)), 250); });
$('#reg-o').addEventListener('change', () => loadRegList().catch(e => toast(e.message, true)));
$('#reg-xl').onclick = () => download('/api/export/companies?' + regQuery(), `Корхоналар ${dmy(R.list ? R.list.today : '')}.xlsx`);
// Алоқа маълумотларини Excel'дан юклаш (Раҳбар / телефон / Бош ҳисобчи / Масъул шахс … устунлари сарлавҳа бўйича танилади)
$('#reg-ci').onclick = () => $('#reg-ci-file').click();
$('#reg-ci-file').onchange = async () => {
  const f = $('#reg-ci-file').files[0]; if (!f) return; $('#reg-ci-file').value = '';
  $('#reg-ci').disabled = true; $('#reg-ci').textContent = 'Юкланмоқда…';
  try {
    const r = await api('/api/contacts/import', { method: 'POST', headers: { 'X-Filename': encodeURIComponent(f.name) }, body: f });
    const sk = r.skipped_n ? `<p class="note" style="margin-top:8px"><b>Базада йўқ ИНН (${r.skipped_n} та) — ўтказиб юборилди:</b></p><div class="tw" style="max-height:220px"><table><thead><tr><th>Варақ</th><th>ИНН</th><th>Корхона</th></tr></thead><tbody>${r.skipped.map(x => `<tr><td>${esc(x.sheet)}</td><td class="mono">${esc(x.inn)}</td><td>${esc(x.name)}</td></tr>`).join('')}</tbody></table></div>` : '';
    $('#colm-body').innerHTML = `<button class="x" id="ci-x">×</button><div class="cm-main"><h2 style="margin:0 0 10px;font-size:16px">Алоқа маълумотлари юкланди</h2>
      <div class="grid kpis" style="grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:10px">
        <div class="kpi"><div class="l">Қаторлар</div><div class="v">${r.rows}</div></div><div class="kpi accent"><div class="l">Янгиланди</div><div class="v">${r.updated}</div></div>
        <div class="kpi"><div class="l">Телефонлар</div><div class="v">${r.phones}</div></div><div class="kpi"><div class="l">Шахслар</div><div class="v">${r.persons}</div></div></div>
      <p class="note" style="margin:0">Варақлар: ${r.sheets.map(s => esc(s.name)).join(', ')} · ўзгармаган: ${r.unchanged}${r.no_inn ? ' · ИННсиз қаторлар: ' + r.no_inn : ''}</p>${sk}
      <div class="form-row" style="margin-top:12px"><button class="btn primary" id="ci-ok">Ёпиш</button></div></div>`;
    $('#col-modal').hidden = false; $('#ci-x').onclick = $('#ci-ok').onclick = closeModals;
    await loadRegList(); loadStatus().catch(() => {});
  } catch (e) { toast(e.message, true); }
  finally { $('#reg-ci').disabled = false; $('#reg-ci').textContent = '📇 Алоқа Excel юклаш'; }
};

// ---------------------------------------------------------------- profile
async function showProfile(inn, yr) {
  if (R.inn !== inn) { R.tab = 'exp'; R.year = null; }
  if (yr) R.year = yr;
  const p = await api('/api/company?inn=' + encodeURIComponent(inn) + (R.year ? '&year=' + R.year : ''));
  R.inn = inn; R.prof = p; R.year = p.year;
  $('#reg-list').hidden = true; const el = $('#reg-prof'); el.hidden = false;
  const c = p.company, k = p.kpi, ct = p.contacts || {};
  const open = p.issues.filter(i => i.status === 'open'), over = open.filter(i => i.overdue).length;
  const b = [];
  if (c.new_date) b.push(`<span class="pill gold">янги экспортёр · ${dmy(c.new_date)}</span>`);
  if (p.template.length) b.push(`<span class="pill ok">номма-номда бор</span>`); else if (c.source) b.push(`<span class="pill warn">номма-номда йўқ</span>`);
  if (c.in_base) b.push('<span class="pill info">божхона базасида</span>');
  else if (c.bukhara === 1) b.push('<span class="pill info">Бухоро деб тасдиқланган</span>');
  else if (c.bukhara === 0) b.push('<span class="pill bad">Бухоро эмас</span>');
  if (c.bukhara !== 0 && (c.bukhara_from || c.bukhara_to)) b.push(`<span class="pill warn">Бухорода ҳисобга олинади: ${c.bukhara_from ? dmy(c.bukhara_from) + ' дан' : ''}${c.bukhara_to ? ' ' + dmy(c.bukhara_to) + ' гача' : ''}</span>`);
  if (c.excluded) b.push('<span class="pill info">алоҳида ҳисоб</span>');
  if (c.opening_source === 'template') b.push('<span class="pill warn">йил боши: шаблон (қўлда)</span>');
  if (!c.source) b.push('<span class="pill warn">реестрда йўқ — фақат режада</span>');
  if (c.source && !c.confirmed) b.push('<span class="pill warn">тасдиқланмаган</span>');
  p.signals.forEach(s => b.push(sigPill(s)));
  const ago = daysAgo(k.last, p.today);
  el.innerHTML = `
    <div class="topbar"><button class="btn sm" id="pf-back">← Korxonalar</button><span class="sub">${p.year} йил · ${p.past ? 'йил якуни' : dmy(p.today) + ' ҳолатига'} · минг АҚШ доллари</span>
      <div class="right"><div class="seg yseg" id="pf-years">${(p.years || [p.year]).map(y => `<button data-y="${y}" class="${y === p.year ? 'on' : ''}">${y}<b>${fmt(p.year_totals[y] / 1000)}</b></button>`).join('')}</div><button class="btn" id="pf-xl">📗 Паспорт Excel</button></div></div>
    <div class="prof-h"><div style="flex:1;min-width:260px"><h1>${esc(c.name || inn)}</h1>
      <div class="meta"><span class="mono">ИНН ${esc(inn)}</span><span>·</span><span>${esc(c.district || '—')}</span><span>·</span><span>${esc(c.tarmoq || '—')}</span>${ct.director ? `<span>·</span><span>раҳбар: ${esc(ct.director)}</span>` : ''}${(ct.phones || []).slice(0, 2).map(ph => `<span>·</span>${telLink(ph)}`).join('')}</div>
      <div class="badges">${b.join('')}</div></div></div>
    <div class="grid kpis" style="margin-bottom:14px">
      <div class="kpi accent"><div class="l">${p.past ? p.year + ' йил жами' : 'Йил бошидан'}</div><div class="v">${fmt(k.ytd)}<small>минг $</small></div><div class="d">${p.past ? (p.year_totals[p.year - 1] != null ? `${p.year - 1}: ${fmt(p.year_totals[p.year - 1])}` : '') : MONTHS[p.month - 1] + ': ' + fmt(k.month)}</div></div>
      <div class="kpi"><div class="l">Туман экспортидаги улуши</div><div class="v">${k.share != null ? fmt(k.share) + '<small>%</small>' : '—'}</div><div class="d">${k.district_ytd ? `туман жами ${fmt(k.district_ytd)}${k.rank ? ` · ${esc(c.district || '')}да ${k.rank}-ўрин (${k.district_n} та экспортёр)` : ''}` : 'туман аниқланмаган'}</div></div>
      <div class="kpi"><div class="l">Охирги экспорт</div><div class="v" style="font-size:21px">${k.last ? dmy(k.last) : '—'}</div><div class="d">${ago != null ? (ago === 0 ? 'бугун' : ago + ' кун олдин') + ' · ' : ''}ГТД: ${fmt0(k.gtd)}</div></div>
      <div class="kpi"><div class="l">Давлатлар</div><div class="v">${fmt0(k.countries)}</div><div class="d">маҳсулот турлари (ТН ВЭД 4): ${fmt0(k.products)}</div></div>
      <div class="kpi ${open.length ? 'gold' : ''}"><div class="l">Очиқ муаммо ва вазифалар</div><div class="v">${open.length}</div><div class="d">${over ? `<span class="t-bad">муддати ўтган: ${over}</span>` : 'муддати ўтгани йўқ'}</div></div>
    </div>
    <div class="seg" id="pf-tabs" style="margin-bottom:14px">${[['exp', 'Экспорт таҳлили'], ['tree', 'Маҳсулот дарахти'], ['lgs', 'Логистика ва нарх'], ['iss', `Муаммо ва вазифалар (${open.length})`], ['info', 'Алоқа ва маълумотлар'], ['docs', `Ҳужжатлар (${p.docs.length})`], ['log', 'Тарих']]
      .map(([v, t]) => `<button data-v="${v}" class="${R.tab === v ? 'on' : ''}">${t}</button>`).join('')}</div>
    <div id="pf-body"></div>`;
  $('#pf-back').onclick = () => { R.inn = null; $('#reg-prof').hidden = true; $('#reg-list').hidden = false; loadRegList().catch(e => toast(e.message, true)); window.scrollTo(0, 0); };
  $('#pf-xl').onclick = () => download('/api/export/passport?inn=' + encodeURIComponent(inn), `Паспорт ${(c.name || inn).replace(/[\\/:*?"<>|]/g, '_').slice(0, 60)} ${inn}.xlsx`);
  $$('#pf-tabs button').forEach(bt => bt.onclick = () => { R.tab = bt.dataset.v; $$('#pf-tabs button').forEach(x => x.classList.toggle('on', x === bt)); renderProfTab(); });
  $$('#pf-years button').forEach(bt => bt.onclick = () => showProfile(inn, +bt.dataset.y).catch(e => toast(e.message, true)));
  renderProfTab();
}
const reloadProfile = () => showProfile(R.inn).then(() => loadStatus()).catch(e => toast(e.message, true));

function renderProfTab() {
  const p = R.prof, body = $('#pf-body');
  if (CH.pf) { CH.pf.destroy(); CH.pf = null; }
  ({ exp: tabExport, tree: tabTree, lgs: tabLogistics, iss: tabIssues, info: tabInfo, docs: tabDocs, log: tabLog })[R.tab](p, body);
}

// ---- Маҳсулот дарахти (korxona ichida): tarmoq → soha → mahsulot → ТН ВЭД
function tabTree(p, body) {
  const total = p.tree.reduce((s, x) => s + x.value, 0) || 1;
  const rows = [];
  const walk = (items, lvl, parentVal) => {
    for (const it of items) {
      const hs = !it.children, share = it.value / (lvl === 0 ? total : parentVal) * 100;
      rows.push(`<tr class="tn l${lvl} open"><td><span class="tg">${hs ? `<span class="hs">${esc(it.key)}</span>${esc(it.name !== it.key ? it.name : '')}` : esc(it.key)}</span></td>
        <td class="num">${fmt(it.value)}</td><td><div class="bar"><i style="width:${Math.min(100, share)}%"></i></div><span class="hint">${fmt(share)}%</span></td><td class="num">${fmt(it.netto_t)}</td><td class="num">${it.netto_t ? fmt(it.value / it.netto_t, 2) : '—'}</td><td class="num">${fmt0(it.gtd)}</td></tr>`);
      if (it.children) walk(it.children, lvl + 1, it.value);
    }
  };
  walk(p.tree, 0, total);
  body.innerHTML = `<div class="panel"><h2>Маҳсулот дарахти <span class="hint">${p.year} йил · тармоқ → соҳа → маҳсулот → ТН ВЭД · улуш: 1-даража жамидан, пастки даражалар юқори даражадан</span></h2>
    ${rows.length ? `<div class="tw" style="max-height:70vh"><table class="ptree"><thead><tr><th>Тармоқ / соҳа / маҳсулот / ТН ВЭД</th><th class="num">Қиймати</th><th style="min-width:110px">Улуши</th><th class="num">Нетто, т</th><th class="num">$/кг</th><th class="num">ГТД</th></tr></thead><tbody>${rows.join('')}</tbody></table></div>` : '<div class="empty">бу йил экспорт йўқ</div>'}
    <p class="note">Худди шу дарахт вилоят бўйича — «Тармоқ ва маҳсулот» саҳифасида; у ерда ушбу корхона ўз ТН ВЭД коди остида кўринади.</p></div>`;
}

// ---- Логистика ва нарх
function tabLogistics(p, body) {
  const L = p.logistics || {}, tot = (L.posts || []).reduce((s, x) => s + x.value, 0) || 1;
  const tbl = (title, hint, rows, codeLabel) => `<div class="panel"><h2>${title} <span class="hint">${hint}</span></h2>${rows && rows.length ? `<table><thead><tr><th>${codeLabel}</th><th>Номи</th><th class="num">Қиймати</th><th class="num">Улуши</th><th class="num">ГТД</th><th class="num">Нетто, т</th></tr></thead><tbody>
    ${rows.map(x => `<tr><td class="mono">${esc(x.code)}</td><td>${esc(x.name || '—')}</td><td class="num">${fmt(x.value)}</td><td class="num">${fmt(100 * x.value / tot)}%</td><td class="num">${fmt0(x.gtd)}</td><td class="num">${fmt(x.netto_t)}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">маълумот йўқ</div>'}</div>`;
  const pr = (p.products || []).filter(x => x.netto_t);
  body.innerHTML = `<div class="g2">
      ${tbl('Божхона постлари', 'қаерда расмийлаштирилган', L.posts, 'Пост')}
      ${tbl('Транспорт тури', 'чегарадаги транспорт (G25)', L.transport, 'Код')}
    </div>
    <div class="g2" style="margin-top:14px">
      ${tbl('Божхона режими', 'Коди', L.proc, 'Код')}
      ${tbl('Битим хусусияти', '24-графа', L.deal, 'Код')}
    </div>
    <div class="panel" style="margin-top:14px"><h2>Нарх — $/кг <span class="hint">корхона ва вилоят ўртачаси (шу йил, шу ТН ВЭД 4 бўйича барча Бухоро экспортёрлари)</span></h2>
      ${pr.length ? `<div class="tw" style="max-height:420px"><table><thead><tr><th>Маҳсулот</th><th>Код</th><th class="num">Қиймати</th><th class="num">Нетто, т</th><th class="num">Корхона $/кг</th><th class="num">Вилоят $/кг</th><th class="num">Фарқ</th><th class="num">Экспортёрлар</th></tr></thead><tbody>
      ${pr.map(x => { const d = x.region_usd_kg ? (x.usd_kg / x.region_usd_kg - 1) * 100 : null;
        return `<tr><td>${esc(x.name || '—')}</td><td class="mono">${esc(x.hs4)}</td><td class="num">${fmt(x.value)}</td><td class="num">${fmt(x.netto_t)}</td><td class="num">${fmt(x.usd_kg, 2)}</td><td class="num">${x.region_usd_kg != null ? fmt(x.region_usd_kg, 2) : '—'}</td><td class="num">${d == null ? '—' : `<span class="gr ${d >= 0 ? 'up' : 'dn'}">${d >= 0 ? '+' : ''}${fmt(d, 0)}%</span>`}</td><td class="num">${x.region_companies != null ? fmt0(x.region_companies) : '—'}</td></tr>`; }).join('')}</tbody></table></div>` : '<div class="empty">маълумот йўқ</div>'}
      <p class="note">$/кг = статистик қиймат / нетто. Вилоят ўртачаси — божхона базаси (саноат) бўйича; кундалик ГТД қаторлари корхона нархида бор, вилоят ўртачасида йўқ.</p></div>
    ${p.import_products && p.import_products.length ? `<div class="panel" style="margin-top:14px"><h2>Импорт таркиби <span class="hint">${p.year} йил · божхона базаси · ${fmt(p.kpi.import_ytd)} минг $</span></h2><table><thead><tr><th>Маҳсулот</th><th class="num">Қиймати</th><th class="num">Нетто, т</th></tr></thead><tbody>
      ${p.import_products.map(x => `<tr><td>${esc(x.name)}</td><td class="num">${fmt(x.value)}</td><td class="num">${fmt(x.netto_t)}</td></tr>`).join('')}</tbody></table></div>` : ''}
    <p class="note">Пост, транспорт, режим ва битим — фақат божхона базаси қаторлари бўйича (кундалик ГТД файлларида бу устунлар йўқ). Пост номлари ва код маънолари божхона лугати юкланганда чиқади.</p>`;
}

function tabExport(p, body) {
  const pm = p.district_months || new Array(12).fill(null), cm = p.month;
  const excl = !!(p.company && p.company.excluded);   // БНПЗ / SDK: туман жамисига кирмайди — улуши «—»
  let tp = 0, ta = 0;
  const mrows = MONTHS.map((m, i) => {
    const pl = pm[i], am = p.months[i], fut = i >= cm;
    if (!fut) { tp += pl || 0; ta += am || 0; }
    const pc = pl && !excl ? 100 * am / pl : null;
    return `<tr class="${fut ? 'subrow' : ''}"><td>${m}</td><td class="num">${pl ? fmt(pl) : '—'}</td><td class="num">${fut && !am ? '' : fmt(am)}</td><td class="num">${pc != null && !(fut && !am) ? fmt(pc) + '%' : ''}</td></tr>`;
  }).join('');
  const ptot = p.products.reduce((s, x) => s + x.value, 0) || 1, ctot = p.countries.reduce((s, x) => s + x.value, 0) || 1;
  body.innerHTML = `
    <div class="g3">
      <div class="panel"><h2>Ойлар кесимида <span class="hint">корхона (устун) ва туман жами (чизиқ)</span></h2><div class="cw" style="height:280px"><canvas id="c-pf"></canvas></div></div>
      <div class="panel"><h2>Туман ичидаги улуши <span class="hint">${esc((p.company && p.company.district) || 'туман аниқланмаган')}</span></h2><div class="tw" style="max-height:300px"><table><thead><tr><th>Ой</th><th class="num">Туман жами</th><th class="num">Корхона</th><th class="num">Улуши</th></tr></thead>
        <tbody>${mrows}<tr class="total"><td>${MONTHS[cm - 1]} гача</td><td class="num">${tp ? fmt(tp) : '—'}</td><td class="num">${fmt(ta)}</td><td class="num">${tp && !excl ? fmt(100 * ta / tp) + '%' : (excl ? '—' : '')}</td></tr></tbody></table></div>${excl ? '<p class="note">Алоҳида ҳисоб: корхона туман жамисига кирмайди — улуши ҳисобланмайди.</p>' : ''}
        ${p.kpi.import_ytd ? `<p class="note">Импорт (божхона базаси, йил бошидан): <b class="mono">${fmt(p.kpi.import_ytd)}</b> минг $</p>` : ''}</div>
    </div>
    <div class="g2" style="margin-top:14px">
      <div class="panel"><h2>Маҳсулотлар <span class="hint">ТН ВЭД 4 белги · йил бошидан</span></h2>${p.products.length ? `<div class="tw" style="max-height:340px"><table><thead><tr><th>Маҳсулот</th><th>Код</th><th class="num">Нетто, т</th><th class="num">Қиймати</th><th class="num">Улуши</th></tr></thead><tbody>
        ${p.products.map(x => `<tr><td>${esc(x.name || '—')}</td><td class="mono">${esc(x.hs4)}</td><td class="num">${fmt(x.netto_t)}</td><td class="num">${fmt(x.value)}</td><td class="num">${fmt(100 * x.value / ptot)}%</td></tr>`).join('')}</tbody></table></div>` : '<div class="empty">экспорт йўқ</div>'}</div>
      <div class="panel"><h2>Давлатлар <span class="hint">йил бошидан</span></h2>${p.countries.length ? `<div class="rank wide">${p.countries.map((x, i) => `<div class="r"><span class="muted mono">${i + 1}</span><span class="nm">${esc(x.country)}</span><span class="v mono">${fmt(x.value)} · ${fmt0(100 * x.value / ctot)}%</span><div class="b"><i style="width:${100 * x.value / p.countries[0].value}%"></i></div></div>`).join('')}</div>` : '<div class="empty">экспорт йўқ</div>'}</div>
    </div>
    ${p.base_detail ? (p.base_legacy ? '<div class="banner show" style="margin-top:14px">Божхона базасини Sozlamalar → 1 орқали бир марта қайта юкланг — ГТД рақамлари, божхона пости, транспорт ва маҳсулот номлари шундан кейин тўлиқ чиқади (суммалар ўзгармайди).</div>' : '') : '<div class="banner show" style="margin-top:14px">Божхона ойлик базасини Sozlamalar → 1 орқали қайта юкланг: база давридаги маҳсулот, давлат ва ГТД лар шундан кейин кўринади.</div>'}<div class="panel" style="margin-top:14px"><h2>ГТД тарихи <span class="hint">${fmt0(p.history_count)} та · ${p.base_through ? `${dmy(p.base_through)} гача божхона базаси, кейин кунлик ГТД` : 'кунлик ГТД'}</span></h2>
      ${p.history.length ? `<div class="tw" style="max-height:420px"><table><thead><tr><th>Сана</th><th>ГТД</th><th>Давлат</th><th>Маҳсулот</th><th class="num">Нетто, т</th><th class="num">Қиймати</th><th>Манба</th></tr></thead><tbody>
      ${p.history.map(h => `<tr><td class="mono">${dmy(h.date)}</td><td class="mono" style="font-size:12px">${esc(h.gtd)}</td><td>${esc(h.country)}</td><td style="max-width:420px">${esc(h.products)}</td><td class="num">${fmt(h.netto_t, 2)}</td><td class="num">${fmt(h.value, 2)}</td><td>${h.src === 'gtd' ? '<span class="pill ok">ГТД</span>' : '<span class="pill info">база</span>'}${h.counted === false ? ' <span class="pill bad" title="Бухоро ҳисобига кирмайди">ҳисобда йўқ</span>' : ''}</td></tr>`).join('')}
      </tbody></table></div>${p.history_count > p.history.length ? `<p class="note">Охирги ${p.history.length} таси кўрсатилди; тўлиқ рўйхат — Паспорт Excel нинг «ГТД тарихи» варағида.</p>` : ''}` : '<div class="empty">бу йил ГТД йўқ</div>'}</div>`;
  CH.pf = new Chart($('#c-pf'), {
    data: { labels: MSHORT, datasets: [
      { type: 'bar', label: 'Корхона', data: p.months.map((v, i) => i < cm || v ? v : null), backgroundColor: C.aqua, borderRadius: 3, order: 2 },
      ...(p.district_months ? [{ type: 'line', label: 'Туман жами', data: pm, borderColor: C.plan, backgroundColor: C.plan, borderDash: [5, 4], pointRadius: 2, tension: .25, order: 1 }] : [])] },
    options: { maintainAspectRatio: false, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: x => `${x.dataset.label}: ${fmt(x.raw)} минг $` } } },
      scales: { y: { beginAtZero: true, grid: { color: C.grid }, ticks: { callback: v => fmt0(v) } }, x: { grid: { display: false } } } } });
}

// ---------------------------------------------------------------- contacts: phones + persons
// +998 90 123-45-67 for Uzbek numbers; a number typed with another country code stays as +<digits>
function fmtPhone(v) {
  v = String(v || ''); let d = v.replace(/\D/g, '');
  if (!d) return v.trim().startsWith('+') ? '+' : '';
  let rest;
  if (d.startsWith('998')) rest = d.slice(3);
  else if (v.trim().startsWith('+')) return '+' + d;
  else if (d.length === 10 && d[0] === '8') rest = d.slice(1);
  else rest = d;
  rest = rest.slice(0, 9);
  return '+998' + (rest.length ? ' ' + rest.slice(0, 2) : '') + (rest.length > 2 ? ' ' + rest.slice(2, 5) : '') + (rest.length > 5 ? '-' + rest.slice(5, 7) : '') + (rest.length > 7 ? '-' + rest.slice(7, 9) : '');
}
const telLink = ph => `<a class="tel" href="tel:${esc(String(ph).replace(/[^\d+]/g, ''))}" title="қўнғироқ қилиш">📞 ${esc(ph)}</a>`;
// editable phone list: rows with ✕, «+ яна телефон» underneath; readPhones() returns the non-empty formatted values
function phonesEditor(box, phones, opt = {}) {
  box._opt = opt;
  const row = v => { const r = document.createElement('div'); r.className = 'ph';
    r.innerHTML = `<span class="ic">📞</span><input class="ct-ph" value="${esc(v)}" placeholder="+998 __ ___-__-__" inputmode="tel" autocomplete="off"><button class="x" type="button" title="олиб ташлаш">✕</button>`;
    const inp = r.querySelector('input');
    inp.addEventListener('input', () => { const f = fmtPhone(inp.value); if (f !== inp.value) inp.value = f; });
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); add(''); } });
    inp.addEventListener('paste', () => setTimeout(() => { inp.value = fmtPhone(inp.value); }, 0));
    r.querySelector('.x').onclick = () => { r.remove(); if (!box.querySelector('.ph')) add(''); mark(); };
    return r; };
  const list = document.createElement('div'); list.className = 'phones';
  const addBt = document.createElement('button'); addBt.type = 'button'; addBt.className = 'btn sm link'; addBt.textContent = '+ яна телефон';
  const add = v => { const r = row(v); list.appendChild(r); mark(); if (v === '' && list.children.length > 1) r.querySelector('input').focus(); };
  const mark = () => { list.querySelectorAll('.ph .tag').forEach(t => t.remove()); if (opt.primary && list.children.length > 1) { const t = document.createElement('span'); t.className = 'tag'; t.textContent = 'асосий'; list.children[0].insertBefore(t, list.children[0].querySelector('.x')); } };
  addBt.onclick = () => add('');
  box.innerHTML = ''; box.appendChild(list); box.appendChild(addBt);
  (phones.length ? phones : ['']).forEach(v => list.appendChild(row(v))); mark();
}
const readPhones = box => [...new Set([...box.querySelectorAll('input.ct-ph')].map(i => fmtPhone(i.value)).filter(v => v.replace(/\D/g, '').length >= 7))];

const ROLE_HINTS = ['Бош ҳисобчи', 'Экспорт менежери', 'Таъсисчи', 'Директор ўринбосари', 'Савдо бўлими', 'Логистика', 'Котиба', 'Ҳуқуқшунос'];
const initials = n => String(n || '').trim().split(/\s+/).slice(0, 2).map(w => w[0] || '').join('').toUpperCase() || '?';
function renderPersons(p) {
  const list = $('#ps-list'), form = $('#ps-form'), persons = p.persons || [];
  list.innerHTML = persons.length ? persons.map(ps => `<div class="person" data-id="${ps.id}"><div class="av">${esc(initials(ps.name))}</div>
      <div class="pbody"><div class="nm">${esc(ps.name)}${ps.role ? `<span class="role">${esc(ps.role)}</span>` : ''}</div>
        ${(ps.phones || []).length ? `<div class="phs">${ps.phones.map(telLink).join('')}</div>` : ''}${ps.note ? `<div class="nt">${esc(ps.note)}</div>` : ''}</div>
      <div class="acts"><button class="ib" data-ed="${ps.id}" title="таҳрирлаш">✎</button><button class="ib del" data-del="${ps.id}" title="олиб ташлаш">✕</button></div></div>`).join('')
    : '<div class="pempty">Ҳозирча йўқ — корхонанинг ҳисобчиси, экспорт менежери ёки бошқа масъул шахсларини қўшиб қўйинг.</div>';
  const openForm = ps => {
    form.innerHTML = `<div class="pform"><div class="ttl">${ps.id ? 'Шахсни таҳрирлаш' : 'Янги шахс'}</div><div class="ct-form">
      <div class="row2"><div class="f"><label>Исми</label><input id="ps-name" value="${esc(ps.name || '')}" placeholder="Фамилия Исм" autocomplete="off"></div>
        <div class="f"><label>Лавозими</label><input id="ps-role" list="dl-roles" value="${esc(ps.role || '')}" placeholder="Бош ҳисобчи…" autocomplete="off"><datalist id="dl-roles">${ROLE_HINTS.map(r => `<option value="${esc(r)}">`).join('')}</datalist></div></div>
      <div class="f"><label>Телефонлар</label><div id="ps-phones"></div></div>
      <div class="f"><label>Изоҳ</label><input id="ps-note" value="${esc(ps.note || '')}" placeholder="қайси масалада мурожаат қилиш мумкин" autocomplete="off"></div>
      <div class="ct-foot"><button class="btn primary" id="ps-save">Сақлаш</button><button class="btn" id="ps-cancel">Бекор</button></div></div></div>`;
    phonesEditor($('#ps-phones'), ps.phones || []);
    $('#ps-name').focus();
    $('#ps-cancel').onclick = () => { form.innerHTML = ''; };
    $('#ps-save').onclick = async () => {
      const d = { id: ps.id || 0, inn: p.inn, name: $('#ps-name').value.trim(), role: $('#ps-role').value.trim(), note: $('#ps-note').value.trim(), phones: readPhones($('#ps-phones')) };
      if (!d.name) { toast('Исмини киритинг', true); $('#ps-name').focus(); return; }
      try { await api('/api/company/person/save', J(d)); toast('Сақланди'); reloadProfile(); } catch (e) { toast(e.message, true); }
    };
    form.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  };
  $('#ps-add').onclick = () => openForm({});
  list.querySelectorAll('[data-ed]').forEach(bt => bt.onclick = () => openForm(persons.find(x => x.id === +bt.dataset.ed) || {}));
  list.querySelectorAll('[data-del]').forEach(bt => bt.onclick = async () => {
    if (!bt.dataset.sure) { bt.dataset.sure = '1'; bt.textContent = 'Тасдиқлаш?'; bt.style.fontSize = '12px'; setTimeout(() => { delete bt.dataset.sure; bt.textContent = '✕'; bt.style.fontSize = ''; }, 4000); return; }
    try { await api('/api/company/person/delete', J({ id: +bt.dataset.del })); toast('Олиб ташланди'); reloadProfile(); } catch (e) { toast(e.message, true); }
  });
}

async function tabInfo(p, body) {
  const c = p.company, ct = p.contacts || {}, reg = !!c.source;
  if (!R.tarmoq) R.tarmoq = await api('/api/tarmoqlar').catch(() => []);
  const src = { 'nomma-nom': 'номма-ном жадвали', baza: 'божхона ойлик базаси', gtd: 'кунлик ГТД' }[c.source] || '—';
  body.innerHTML = `<div class="g2">
    <div class="panel"><h2>Алоқа <span class="hint">қўлда киритилади</span></h2>
      <div class="ct-form">
        <div class="f"><label>Раҳбар</label><input id="ct-director" value="${esc(ct.director || '')}" placeholder="Фамилия Исм Шарифи" autocomplete="off"></div>
        <div class="f"><label>Телефонлар</label><div class="phones" id="ct-phones"></div></div>
        <div class="f"><label>Манзил</label><input id="ct-address" value="${esc(ct.address || '')}" placeholder="туман, кўча, уй" autocomplete="off"></div>
        <div class="f"><label>Email</label><input id="ct-email" type="email" value="${esc(ct.email || '')}" placeholder="info@korxona.uz" autocomplete="off"></div>
        <div class="f"><label>Изоҳ</label><textarea id="ct-note" rows="2" placeholder="қачон, ким билан гаплашилди; қулай вақт…">${esc(ct.note || '')}</textarea></div>
        <div class="ct-foot"><button class="btn primary" id="ct-save">Сақлаш</button>${ct.updated_at ? `<span class="note">янгиланган: ${esc(ct.updated_at.slice(0, 16))}</span>` : ''}</div>
      </div>
      <div class="ct-persons"><h3>Алоқадор шахслар <span class="cnt">${(p.persons || []).length} та</span><span class="hint">ҳисобчи, менежер, таъсисчи…</span><button class="btn sm" id="ps-add">+ Шахс қўшиш</button></h3>
        <div class="plist" id="ps-list"></div><div id="ps-form"></div></div></div>
    <div class="panel"><h2>Реестр маълумотлари <span class="hint">номма-ном ва ҳисоб учун</span></h2>${reg ? `<div class="kv">
      <label>Номи</label><input id="rg-name" value="${esc(c.name || '')}">
      <label>Туман</label><select id="rg-d">${S.districts.map(d => `<option value="${d.code}">${esc(d.name_uz)}</option>`).join('')}</select>
      <label>Тармоқ</label><input id="rg-t" list="dl-tar" value="${esc(c.tarmoq || '')}"><datalist id="dl-tar">${R.tarmoq.map(t => `<option value="${esc(t)}">`).join('')}</datalist>
      <label>Уюшма</label><input id="rg-u" value="${esc(c.uyushma || '')}">
      <label>Бухоро корхонаси</label><select id="rg-b"><option value="">${c.in_base ? 'божхона базасида бор' : (c.source === 'gtd' ? 'ГТД да тасдиқланган' : 'номаълум')}</option><option value="1">Бухоро</option><option value="0">Бухоро эмас — ҳисобга киритилмасин</option></select>
      <label>Бухорода ҳисобга олиш даври</label><div class="form-row" style="gap:6px;align-items:center;flex-wrap:wrap"><input type="date" id="rg-bf" value="${esc(c.bukhara_from || '')}" style="width:150px"> <span class="muted">дан</span> <input type="date" id="rg-bt" value="${esc(c.bukhara_to || '')}" style="width:150px"> <span class="muted">гача</span></div>
      <label>Йил боши манбаси</label><select id="rg-os"><option value="customs">Божхона базаси (сайт → Excel қайта ёзилади)</option><option value="template">Шаблон (қўлда киритилган номма-ном → сайтга олинади)</option></select>
      <span></span><p class="note" style="margin:0">Йил бошидан база ойигача бўлган ойлик рақамлар қаердан олинади. «Шаблон» танланса, шу корхонанинг Excel шаблонидаги ойлик рақамлари сайтга (йил боши қолдиғи) кўчирилади ва ҳамма саҳифада Excel билан бир хил бўлади; «Божхона базаси» — база ҳақиқат, Excel чиқаришда унинг ойлари база бўйича қайта ёзилади. Рўйхат: Созламалар → «Баҳсли корхоналар».</p>
      <span></span><p class="note" style="margin:0">Бўш қолдирилса — бутун йил. Корхона Бухорога кўчиб келган бўлса «дан» санасини, кетган бўлса «гача» санасини қўйинг: фақат шу давр ичидаги экспорт (божхона базаси ҳам, ГТД ҳам) Бухоро ҳисобига киради. Кейин ўзгартириш мумкин — ўтган кунлар қайта ҳисобланади.</p>
      <label>Тасдиқлаш</label><label style="display:flex;gap:8px;align-items:center;color:var(--ink)"><input type="checkbox" id="rg-c" ${c.confirmed ? 'checked' : ''}> маълумотлар текширилди</label>
      <span></span><div class="form-row"><button class="btn primary" id="rg-save">Сақлаш</button></div></div>
      <div class="kv" style="margin-top:12px;border-top:1px solid var(--line);padding-top:12px">
        <label>Манба</label><span>${src}</span>
        <label>Номма-номда</label><span>${p.template.length ? p.template.map(t => `${t.category === 'meva' ? 'мева' : 'саноат'}, ${t.row}-қатор${t.yellow ? ' (сариқ)' : ''}`).join('; ') : 'йўқ'}</span>
        <label>Маҳсулот</label><span>${esc(c.product || '—')}</span>
        <label>Янги экспортёр</label><span>${c.new_date ? dmy(c.new_date) + ' даги ГТД да биринчи марта' : '—'}</span>
        <label>Реестрга қўшилган</label><span>${esc(c.created_at || '—')}</span></div>`
      : `<div class="empty">Бу корхона вазирлик режасида бор, лекин реестрда (божхона базаси, номма-ном, ГТД) йўқ.</div>`}
</div></div>`;
  phonesEditor($('#ct-phones'), ct.phones || [], { primary: true });
  $('#ct-save').onclick = async () => {
    const d = { inn: p.inn, phones: readPhones($('#ct-phones')) }; ['director', 'address', 'email', 'note'].forEach(k => d[k] = $('#ct-' + k).value);
    if (d.email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(d.email.trim())) { toast('Email нотўғри ёзилган', true); $('#ct-email').focus(); return; }
    try { await api('/api/company/contacts', J(d)); toast('Сақланди'); reloadProfile(); } catch (e) { toast(e.message, true); }
  };
  renderPersons(p);
  if (reg) {
    $('#rg-d').value = c.district_code || ''; $('#rg-b').value = c.bukhara == null ? '' : String(c.bukhara); $('#rg-os').value = c.opening_source || 'customs';
    $('#rg-save').onclick = async () => {
      try { await api('/api/companies/update', J({ inn: p.inn, name: $('#rg-name').value.trim(), district_code: $('#rg-d').value, tarmoq: $('#rg-t').value, uyushma: $('#rg-u').value, bukhara: $('#rg-b').value, bukhara_from: $('#rg-bf').value, bukhara_to: $('#rg-bt').value, opening_source: $('#rg-os').value, confirmed: $('#rg-c').checked ? 1 : 0 }));
        toast('Сақланди (заҳира олинди)'); S.dash = null; reloadProfile(); } catch (e) { toast(e.message, true); }
    };
  }
}

function tabDocs(p, body) {
  body.innerHTML = `<div class="g3"><div class="panel"><h2>Ҳужжатлар <span class="hint">${p.docs.length} та</span></h2>${p.docs.length ? `<div class="tw"><table><thead><tr><th>Файл</th><th>Ҳужжат санаси</th><th>Изоҳ</th><th class="num">Ҳажм</th><th>Юкланган</th><th></th></tr></thead><tbody>
      ${p.docs.map(d => `<tr><td><a class="clink" href="/api/company/doc?id=${d.id}">${esc(d.filename)}</a></td><td class="mono">${d.doc_date ? dmy(d.doc_date) : '—'}</td><td>${esc(d.note || '')}</td><td class="num">${fmt(d.size / 1024, 0)} КБ</td><td class="mono">${esc((d.uploaded_at || '').slice(0, 16))}</td><td><button class="btn sm danger" data-rm="${d.id}">Олиб ташлаш</button></td></tr>`).join('')}</tbody></table></div>` : '<div class="empty">ҳужжат йўқ</div>'}</div>
    <div class="panel"><h2>Ҳужжат қўшиш</h2><div class="fcol"><label>Файл (PDF, Word, Excel, расм… 80 МБ гача)</label><input type="file" id="dc-f">
      <label>Изоҳ</label><input type="text" id="dc-n" placeholder="шартнома, сертификат, хат…"><label>Ҳужжат санаси</label><input type="date" id="dc-d">
      <div class="form-row"><button class="btn primary" id="dc-up">Юклаш</button></div>
      <p class="note">Файллар маълумотлар папкасида (company_docs) сақланади. Олиб ташланган файл «_olib_tashlangan» папкасига кўчирилади.</p></div></div></div>`;
  $('#dc-up').onclick = async () => {
    const f = $('#dc-f').files[0]; if (!f) { toast('Файлни танланг', true); return; }
    try { await api('/api/company/doc/upload', { method: 'POST', headers: { 'X-Inn': p.inn, 'X-Filename': encodeURIComponent(f.name), 'X-Note': encodeURIComponent($('#dc-n').value), 'X-Date': $('#dc-d').value }, body: f });
      toast('Ҳужжат юкланди'); reloadProfile(); } catch (e) { toast(e.message, true); }
  };
  body.querySelectorAll('[data-rm]').forEach(bt => bt.onclick = async () => {
    if (!bt.dataset.sure) { bt.dataset.sure = '1'; bt.textContent = 'Тасдиқлаш?'; setTimeout(() => { delete bt.dataset.sure; bt.textContent = 'Олиб ташлаш'; }, 4000); return; }
    try { await api('/api/company/doc/remove', J({ id: +bt.dataset.rm })); toast('Олиб ташланди'); reloadProfile(); } catch (e) { toast(e.message, true); }
  });
}

function tabLog(p, body) {
  body.innerHTML = `<div class="panel"><h2>Тарих <span class="hint">корхона бўйича барча ўзгаришлар</span></h2>${p.events.length ? `<div class="tl">${p.events.map(e => `<div class="e"><span class="a">${esc(e.at)}</span><span>${esc(e.text)}</span></div>`).join('')}</div>` : '<div class="empty">ҳозирча ёзув йўқ</div>'}</div>`;
}

// ---------------------------------------------------------------- MUAMMO VA VAZIFALAR — kanban doska (Trello uslubi)
// B: doska holati (ustunlar, belgilar, kartalar). BF: filtrlar. DND: sudrash holati. BV: ko'rinish (доска / жадвал) va saralash.
// 26.09.2026: ixcham karta (ustuvorlik chizig'i, №, muddat «N кун қолди», qadamlar x/y, izohlar, fayllar, harakatsiz kunlar, kichik rasm),
// karta ichida qadamlar (checklist), izohlar + avtomatik tarix, ustuvorlik, asos hujjat, korxona ma'lumoti; «Ҳолат» filtri; jadval ko'rinishi.
const B = { columns: [], labels: [], issues: [], today: '', loaded: false, basis: {}, stale_days: 14, showOld: new Set() };
const BF = { q: '', district: '', noCompany: false, labels: new Set(), state: '' };
const DND = { type: null, id: null, ph: null };
const BV = { view: (() => { try { return localStorage.getItem('bd-view') || 'board'; } catch (_) { return 'board'; } })(), sort: 'pri', dir: 1 };
const PRI = { urgent: { n: 'Шошилинч', c: '#C0392B', o: 0 }, high: { n: 'Юқори', c: '#D9822B', o: 1 }, normal: { n: 'Ўрта', c: '', o: 2 }, low: { n: 'Паст', c: '#8A929C', o: 3 } };
const BASIS_SHORT = { bayon: 'Баён', topshiriq: 'Топшириқ', xat: 'Хат', murojaat: 'Мурожаат', boshqa: 'Асос' };
const OLD_DONE_DAYS = 30;   // «Ҳал қилинган» ustunida bundan eski kartalar yig'ilib turadi (filtr/qidiruvda ko'rinadi)
const KIND_FULL = { muammo: 'Муаммо', vazifa: 'Вазифа', murojaat: 'Мурожаат', izoh: 'Изоҳ' };
const labelById = id => B.labels.find(l => l.id === id);
const colById = id => B.columns.find(c => c.id === id);
const fileIcon = n => { const e = (n || '').split('.').pop().toLowerCase(); return { pdf: '📕', doc: '📝', docx: '📝', xls: '📊', xlsx: '📊', zip: '🗜', rar: '🗜', txt: '📄' }[e] || '📎'; };
const kb = n => n < 1024 ? n + ' Б' : n < 1048576 ? Math.round(n / 1024) + ' КБ' : (n / 1048576).toFixed(1) + ' МБ';
const distName = code => (S.districts.find(d => d.code === code) || {}).name_uz || '';
const ICO = {
  cal: '<svg viewBox="0 0 16 16"><rect x="2.5" y="3.5" width="11" height="10" rx="2"/><path d="M2.5 6.8h11M5.5 2v3M10.5 2v3"/></svg>',
  check: '<svg viewBox="0 0 16 16"><rect x="2.5" y="2.5" width="11" height="11" rx="2.5"/><path d="M5.4 8.2l1.8 1.8 3.4-3.6"/></svg>',
  note: '<svg viewBox="0 0 16 16"><path d="M3 3h10a1 1 0 0 1 1 1v6.5a1 1 0 0 1-1 1H7.2L4 14v-2.5H3a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/></svg>',
  clip: '<svg viewBox="0 0 16 16"><path d="M10.5 4.5l-5 5a1.4 1.4 0 0 0 2 2l5.2-5.2a2.8 2.8 0 0 0-4-4L3.4 7.6a4.2 4.2 0 0 0 6 6l4-4"/></svg>',
  idle: '<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="5.8"/><path d="M8 4.8v3.4l2.2 1.4"/></svg>',
  doc: '<svg viewBox="0 0 16 16"><path d="M4 1.8h5l3.5 3.5v8.9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V2.8a1 1 0 0 1 1-1z"/><path d="M9 1.8v3.5h3.5M5.5 8.5h5M5.5 11h3.5"/></svg>',
};
// rang yordamchilari: belgi rangidan och fon + to'qroq matn (oq matnli qalin «pill» o'rniga zamonaviy yumshoq belgi)
function hexRgb(h) { const m = /^#?([0-9a-f]{6})$/i.exec(h || ''); if (!m) return [93, 109, 126]; const n = parseInt(m[1], 16); return [n >> 16, (n >> 8) & 255, n & 255]; }
const hexA = (h, a) => { const [r, g, b] = hexRgb(h); return `rgba(${r},${g},${b},${a})`; };
const hexDark = (h, k = .72) => { const [r, g, b] = hexRgb(h); return `rgb(${Math.round(r * k)},${Math.round(g * k)},${Math.round(b * k)})`; };
const lblStyle = c => `background:${hexA(c, .14)};color:${hexDark(c)}`;
const daysTo = iso => Math.round((new Date(iso.slice(0, 10)) - new Date(B.today || localISO(new Date()))) / 864e5);
const addDays = n => localISO(new Date(Date.now() + n * 864e5));
const dm = iso => iso ? (iso.slice(0, 4) === (B.today || '').slice(0, 4) ? `${iso.slice(8, 10)}.${iso.slice(5, 7)}` : dmy(iso.slice(0, 10))) : '';
function relTime(at) {
  if (!at) return '';
  const d = at.slice(0, 10), t = at.slice(11, 16), n = daysTo(d);
  return n === 0 ? `бугун ${t}` : n === -1 ? `кеча ${t}` : d.slice(0, 4) === (B.today || '').slice(0, 4) ? `${d.slice(8, 10)}.${d.slice(5, 7)} ${t}` : dmy(d);
}
function dueInfo(i) {
  if (!i.due_date) return null;
  const full = 'Муддат: ' + dmy(i.due_date);
  if (i.status === 'closed') return { cls: 'okd', txt: dm(i.due_date), tip: full };
  const d = daysTo(i.due_date);
  if (d < 0) return { cls: 'over', txt: `${-d} кун кечикди`, tip: full };
  if (d === 0) return { cls: 'today', txt: 'Бугун', tip: full };
  if (d === 1) return { cls: 'soon', txt: 'Эртага', tip: full };
  if (d <= 3) return { cls: 'soon', txt: `${d} кун қолди`, tip: full };
  return { cls: '', txt: dm(i.due_date), tip: full + ` (${d} кун қолди)` };
}
const basisTitle = i => [B.basis[i.basis_kind] || 'Асос', i.basis_no, i.basis_date ? dmy(i.basis_date) : ''].filter(Boolean).join(' · ');
const isOldDone = i => i.status === 'closed' && i.closed_at && daysTo(i.closed_at) < -OLD_DONE_DAYS;

async function loadNames() {
  R.names = await api('/api/companies/names');
  let dl = $('#dl-comp'); if (!dl) { dl = document.createElement('datalist'); dl.id = 'dl-comp'; document.body.appendChild(dl); }
  dl.innerHTML = R.names.map(x => `<option value="${esc(x.inn)} — ${esc(x.name || '')}">`).join('');
}
async function loadBoard() {
  const b = await api('/api/board');
  Object.assign(B, b, { loaded: true });
  if (!R.names) await loadNames();
  loadStatus().catch(() => {});
}
loaders.iss = async () => { await regFilters(); await loadBoard(); renderBoard(); };

// ---- filtrlar
const STATES = () => [['', 'Барчаси'], ['overdue', 'Муддати ўтган'], ['week', 'Муддати шу ҳафтада'], ['stale', `Туриб қолган (${B.stale_days}+ кун ҳаракатсиз)`], ['urgent', 'Шошилинч ва юқори'], ['nodue', 'Муддатсиз (очиқ)']];
function stateMatch(i, st) {
  const open = i.status === 'open';
  switch (st) {
    case 'overdue': return !!i.overdue;
    case 'week': return open && !!i.due_date && i.due_date >= B.today && i.due_date <= addDays(7);
    case 'stale': return !!i.stale;
    case 'urgent': return open && (i.priority === 'urgent' || i.priority === 'high');
    case 'nodue': return open && !i.due_date;
    default: return true;
  }
}
function issueVisible(i, ignoreState = false) {
  if (BF.district && i.district_code !== BF.district) return false;
  if (BF.noCompany && i.inn) return false;
  if (!ignoreState && BF.state && !stateMatch(i, BF.state)) return false;
  if (BF.labels.size && ![...BF.labels].some(l => i.labels.includes(l))) return false;
  if (BF.q && !smatch(BF.q, String(i.id), i.title, i.text, i.company, i.inn, i.resolution, i.basis_no, (i.last_note || {}).text, ...(i.checks || []).map(c => c.text), ...i.labels.map(l => (labelById(l) || {}).name))) return false;
  return true;
}
const filterActive = () => !!(BF.q || BF.district || BF.noCompany || BF.labels.size || BF.state);
function renderFilters() {
  renderDistrictDD(); renderStateDD();
  const box = $('#bd-lchips');
  box.innerHTML = B.labels.length ? B.labels.map(l => `<button type="button" class="chip lb${BF.labels.has(l.id) ? ' on' : ''}" data-l="${l.id}" style="${BF.labels.has(l.id) ? `background:${esc(l.color)}` : ''}"><span class="sw" style="background:${esc(l.color)}"></span>${esc(l.name)} <span class="muted" style="font-size:11px;${BF.labels.has(l.id) ? 'color:#fff;opacity:.85' : ''}">${l.used}</span></button>`).join('')
    : '<span class="muted" style="font-size:12.5px">ҳали белги йўқ — «Белгилар» тугмаси орқали Божхона, Солиқ, Банк каби ташкилотларни қўшинг</span>';
  box.querySelectorAll('[data-l]').forEach(b => b.onclick = () => { const id = +b.dataset.l; BF.labels.has(id) ? BF.labels.delete(id) : BF.labels.add(id); renderBoard(); });
}
// input ko'rinishidagi dropdown (tuman, holat): tugma + ro'yxat, har qatorda soni
function ddShell(host) {
  if (host.dataset.built) return;
  host.innerHTML = `<button type="button" class="tagdd-btn"><span class="t"></span><span class="cnt"></span><span class="ar">▾</span></button><div class="tagdd-pop" hidden><div class="tagdd-list"></div></div>`;
  const btn = host.querySelector('.tagdd-btn'), pop = host.querySelector('.tagdd-pop');
  btn.onclick = e => { e.stopPropagation(); const open = pop.hidden; document.querySelectorAll('.tagdd-pop,.ms-pop').forEach(x => x.hidden = true); pop.hidden = !open; };
  pop.onclick = e => e.stopPropagation();
  host.dataset.built = '1';
}
function ddFill(host, rows, cur, onPick, alertKeys = []) {
  const on = rows.find(r => r[0] === cur) || rows[0];
  host.querySelector('.t').textContent = on[1]; host.querySelector('.cnt').textContent = on[2];
  host.classList.toggle('act', !!cur);
  host.querySelector('.tagdd-list').innerHTML = rows.map(([v, n, c]) => `<div class="dd-row${v === cur ? ' on' : ''}${alertKeys.includes(v) && c ? ' alert' : ''}" data-v="${esc(v)}"><span class="nm">${esc(n)}</span><span class="cnt${c ? '' : ' zero'}">${c}</span></div>`).join('');
  host.querySelectorAll('.dd-row').forEach(r => r.onclick = () => { host.querySelector('.tagdd-pop').hidden = true; onPick(r.dataset.v); });
}
// tumanlar: har tumanda nechta karta borligi (badge)
function renderDistrictDD() {
  const host = $('#iss-dd'), sel = $('#iss-d'); ddShell(host);
  const counts = {}; let general = 0;
  B.issues.forEach(i => { if (i.district_code) counts[i.district_code] = (counts[i.district_code] || 0) + 1; else general++; });
  const cur = BF.noCompany ? '__none__' : sel.value;
  const rows = [['', 'Барча туманлар', B.issues.length], ...S.districts.map(d => [d.code, d.name_uz, counts[d.code] || 0])];
  if (general) rows.push(['__none__', 'Умумий (корхонасиз)', general]);
  ddFill(host, rows, cur, v => { sel.value = v === '__none__' ? '' : v; BF.noCompany = v === '__none__'; renderBoard(); });
}
// holat: muddati o'tgan / shu hafta / turib qolgan / shoshilinch / muddatsiz — sonlari boshqa filtrlar hisobga olingan holda
function renderStateDD() {
  const host = $('#iss-st'); ddShell(host);
  const base = B.issues.filter(i => issueVisible(i, true));
  const rows = STATES().map(([v, n]) => [v, n, v ? base.filter(i => stateMatch(i, v)).length : base.length]);
  ddFill(host, rows, BF.state, v => { BF.state = v; renderBoard(); }, ['overdue', 'stale']);
}

// ---- karta HTML
function cardHTML(i) {
  const closed = i.status === 'closed', pr = closed ? PRI.normal : (PRI[i.priority] || PRI.normal);   // hal qilingan kartada ustuvorlik ko'rsatilmaydi
  const labs = i.labels.map(labelById).filter(Boolean);
  const imgs = i.files.filter(f => f.is_image), due = dueInfo(i);
  const ck = i.checks || [], ckDone = ck.filter(c => c.done).length;
  const dname = i.district_code ? short(distName(i.district_code)) : '';
  const idle = !closed && i.idle_days >= 7 ? i.idle_days : 0;
  const note = closed ? (i.resolution ? { cls: 'res', t: '✓ ' + i.resolution } : null) : (i.last_note ? { cls: '', t: i.last_note.text, at: i.last_note.at } : null);
  const chips = [
    due && `<span class="bdg ${due.cls}" title="${esc(due.tip)}">${ICO.cal}${esc(due.txt)}</span>`,
    ck.length && `<span class="bdg ck${ckDone === ck.length ? ' full' : ''}" title="Қадамлар: ${ckDone} / ${ck.length} бажарилди">${ICO.check}${ckDone}/${ck.length}<span class="bar"><i style="width:${Math.round(100 * ckDone / ck.length)}%"></i></span></span>`,
    i.n_notes && `<span class="bdg" title="${i.n_notes} та изоҳ">${ICO.note}${i.n_notes}</span>`,
    i.files.length && `<span class="bdg" title="${i.files.length} та файл">${ICO.clip}${i.files.length}</span>`,
    idle && `<span class="bdg idle${i.stale ? ' bad' : ''}" title="Охирги ҳаракат ${idle} кун олдин${i.stale ? ' — туриб қолган' : ''}">${ICO.idle}${idle} кун ҳаракатсиз</span>`,
  ].filter(Boolean);
  const top = [
    pr.c && i.priority !== 'low' ? `<span class="c-pri" style="color:${pr.c};background:${hexA(pr.c, .12)}">${pr.n}</span>` : '',
    ...labs.map(l => `<span class="c-lbl" style="${lblStyle(l.color)}">${esc(l.name)}</span>`),
    i.basis_kind ? `<span class="c-basis" title="${esc(basisTitle(i))}">${ICO.doc}${esc(BASIS_SHORT[i.basis_kind] || 'Асос')}</span>` : '',
  ].join('');
  const no = `<span class="c-no">${closed ? '<b class="c-ok">✓</b>' : ''}#${i.id}</span>`;
  return `<div class="card${closed ? ' closed' : ''}${i.stale ? ' stale' : ''}" draggable="true" data-id="${i.id}"${pr.c ? ` style="--pc:${pr.c}"` : ''}>
    ${top ? `<div class="c-top">${top}${no}</div>` : ''}
    <div class="c-body"><div class="c-main">${top ? '' : no.replace('c-no', 'c-no fl')}<div class="ttl">${esc(i.title)}</div>
      ${i.inn ? `<div class="co" title="${esc((i.company || i.inn) + (dname ? ' · ' + dname : ''))}">${esc(i.company || i.inn)}${dname ? `<span class="ds"> · ${esc(dname)}</span>` : ''}</div>` : ''}</div>
      ${imgs.length ? `<div class="thumb"><img src="/api/issue/file?id=${imgs[0].id}&inline=1" alt="" loading="lazy">${imgs.length > 1 ? `<span>+${imgs.length - 1}</span>` : ''}</div>` : ''}</div>
    ${note ? `<div class="c-note ${note.cls}" title="${esc(note.t)}">${esc(note.t)}</div>` : ''}
    ${chips.length ? `<div class="meta">${chips.join('')}</div>` : ''}</div>`;
}

// ---- doska / jadval
function renderBoard() {
  if (!B.loaded) return;
  BF.q = $('#iss-q').value.trim(); BF.district = $('#iss-d').value;
  renderFilters();
  const isT = BV.view === 'table';
  $$('#bd-view button').forEach(b => b.classList.toggle('on', b.dataset.v === BV.view));
  $('#board').hidden = isT; $('#bd-table').hidden = !isT; $('#bd-addcol').hidden = isT;
  $('#bd-sub').textContent = isT ? 'қаторни босиб картани очинг · устун номини босиб саралаш' : 'карталарни устунлар орасида сичқонча билан судраб кўчиринг';
  if (isT) renderTable(); else renderColumns();
  if (!$('#bd-svod-panel').hidden) renderSvod();
}
function renderColumns() {
  const board = $('#board'); const scroll = board.scrollLeft;
  const byCol = {}; B.columns.forEach(c => byCol[c.id] = []);
  B.issues.forEach(i => { if (byCol[i.column_id]) byCol[i.column_id].push(i); });
  Object.values(byCol).forEach(a => a.sort((x, y) => (x.position || 0) - (y.position || 0) || x.id - y.id));
  const filtering = filterActive();
  board.innerHTML = B.columns.map(c => {
    const all = byCol[c.id], vis = all.filter(i => issueVisible(i));
    const old = c.is_done && !filtering ? vis.filter(isOldDone) : [];
    const shown = old.length && !B.showOld.has(c.id) ? vis.filter(i => !isOldDone(i)) : vis;
    const over = vis.filter(i => i.overdue).length;
    return `<div class="col" data-col="${c.id}" style="--cc:${esc(c.color || '#8A929C')}">
      <div class="col-h" draggable="true"><span class="nm" title="${esc(c.name)}">${esc(c.name)}</span>${c.is_done ? '<span class="done">✓ ҳал</span>' : ''}${over ? `<span class="ovr" title="муддати ўтган карталар">${over} кечикди</span>` : ''}<span class="cnt">${vis.length === all.length ? all.length : vis.length + '/' + all.length}</span><button class="mn" title="Устун созламалари" data-colmenu="${c.id}">⋯</button></div>
      <div class="col-b">${shown.map(cardHTML).join('') || `<div class="col-empty">${all.length ? 'филтр бўйича карта йўқ' : 'картани шу ерга судраб ташланг'}</div>`}
        ${old.length ? `<button class="col-old" data-old="${c.id}">${B.showOld.has(c.id) ? '▴ Эски карталарни йиғиш' : `▸ Яна ${old.length} та эски карта <span class="muted">(${OLD_DONE_DAYS} кундан олдин ҳал қилинган)</span>`}</button>` : ''}</div>
      <div class="col-f"><button class="add" data-add="${c.id}">+ Карта қўшиш</button></div></div>`;
  }).join('');
  board.scrollLeft = scroll;
  wireBoard();
}

function wireBoard() {
  const board = $('#board');
  board.querySelectorAll('.card').forEach(el => {
    el.onclick = () => openCard(B.issues.find(i => i.id === +el.dataset.id));
    el.addEventListener('dragstart', e => { DND.type = 'card'; DND.id = +el.dataset.id; el.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', 'card:' + el.dataset.id); e.stopPropagation(); });
    el.addEventListener('dragend', () => { el.classList.remove('dragging'); clearPh(); DND.type = null; });
  });
  board.querySelectorAll('.col-h').forEach(h => {
    h.addEventListener('dragstart', e => { DND.type = 'col'; DND.id = +h.parentElement.dataset.col; h.parentElement.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', 'col:' + DND.id); });
    h.addEventListener('dragend', () => { board.querySelectorAll('.col.dragging,.col.over').forEach(x => x.classList.remove('dragging', 'over')); DND.type = null; });
  });
  board.querySelectorAll('.col').forEach(col => {
    const body = col.querySelector('.col-b');
    col.addEventListener('dragover', e => {
      if (!DND.type) return; e.preventDefault(); e.dataTransfer.dropEffect = 'move';
      if (DND.type === 'card') placePh(body, e.clientY);
      else if (DND.type === 'col' && +col.dataset.col !== DND.id) { board.querySelectorAll('.col.over').forEach(x => x.classList.remove('over')); col.classList.add('over'); }
    });
    col.addEventListener('dragleave', e => { if (!col.contains(e.relatedTarget)) col.classList.remove('over'); });
    col.addEventListener('drop', async e => {
      e.preventDefault();
      if (DND.type === 'card') await dropCard(col, body);
      else if (DND.type === 'col') await dropColumn(col);
    });
  });
  board.querySelectorAll('[data-add]').forEach(b => b.onclick = () => openCard(null, { column_id: +b.dataset.add }));
  board.querySelectorAll('[data-colmenu]').forEach(b => b.onclick = e => { e.stopPropagation(); openColumnModal(colById(+b.dataset.colmenu)); });
  board.querySelectorAll('[data-old]').forEach(b => b.onclick = () => { const id = +b.dataset.old; B.showOld.has(id) ? B.showOld.delete(id) : B.showOld.add(id); renderColumns(); });
}
function clearPh() { if (DND.ph) { DND.ph.remove(); DND.ph = null; } $$('.col-b.has-ph').forEach(b => b.classList.remove('has-ph')); }
function placePh(body, y) {
  if (!DND.ph) { DND.ph = document.createElement('div'); DND.ph.className = 'drop-ph'; }
  $$('.col-b.has-ph').forEach(b => b !== body && b.classList.remove('has-ph')); body.classList.add('has-ph');
  const cards = [...body.querySelectorAll('.card:not(.dragging)')];
  const next = cards.find(c => { const r = c.getBoundingClientRect(); return y < r.top + r.height / 2; });
  body.insertBefore(DND.ph, next || body.querySelector('.col-old'));
}
async function dropCard(col, body) {
  const id = DND.id, cid = +col.dataset.col; if (!id) return;
  // joy — ekranda ko'rinib turgan kartalar tartibidan (yashirilgan/filtrlangan kartalar hisobga olinmaydi)
  const order = [...body.children].filter(el => el === DND.ph || (el.classList.contains('card') && +el.dataset.id !== id));
  const idx = order.indexOf(DND.ph); clearPh();
  const it = B.issues.find(i => i.id === id); if (!it) return;
  const others = order.filter(el => el.classList.contains('card')).map(el => B.issues.find(i => i.id === +el.dataset.id)).filter(Boolean);
  let pos;
  if (idx < 0 || idx >= others.length) pos = (others.length ? (others[others.length - 1].position || 0) : 0) + 10;
  else if (idx === 0) pos = (others[0].position || 0) - 5;
  else pos = ((others[idx - 1].position || 0) + (others[idx].position || 0)) / 2;
  const prev = { column_id: it.column_id, position: it.position, status: it.status, overdue: it.overdue };
  it.column_id = cid; it.position = pos; it.status = colById(cid).is_done ? 'closed' : 'open'; it.overdue = it.status === 'open' && !!it.due_date && it.due_date < B.today;
  renderBoard();
  try { await api('/api/issues/move', J({ id, column_id: cid, position: pos })); await loadBoard(); renderBoard(); }
  catch (e) { Object.assign(it, prev); renderBoard(); toast(e.message, true); }
}
async function dropColumn(target) {
  const from = DND.id, to = +target.dataset.col; if (!from || from === to) return;
  const ids = B.columns.map(c => c.id); const fi = ids.indexOf(from), ti = ids.indexOf(to);
  ids.splice(fi, 1); ids.splice(ti, 0, from);
  B.columns.sort((a, b) => ids.indexOf(a.id) - ids.indexOf(b.id)); renderBoard();
  try { await api('/api/board/columns/reorder', J({ ids })); } catch (e) { toast(e.message, true); await loadBoard(); renderBoard(); }
}

// ---- jadval ko'rinishi (saralanadi; ochiq kartalar doim tepada)
const TCOLS = [['no', '№'], ['title', 'Карта'], ['co', 'Корхона'], ['col', 'Устун'], ['pri', 'Устуворлик'], ['due', 'Муддат'], ['ck', 'Қадамлар'], ['idle', 'Ҳаракатсиз'], ['note', 'Охирги изоҳ']];
function tKey(i, k) {
  switch (k) {
    case 'no': return i.id;
    case 'title': return (i.title || '').toLowerCase();
    case 'co': return (i.company || 'яяя').toLowerCase();
    case 'col': return B.columns.findIndex(c => c.id === i.column_id);
    case 'pri': return [(PRI[i.priority] || PRI.normal).o, i.due_date || '9999'];
    case 'due': return i.due_date || '9999';
    case 'ck': return i.checks.length ? i.checks.filter(c => c.done).length / i.checks.length : -1;
    case 'idle': return i.status === 'open' ? -(i.idle_days || 0) : 1;
    case 'note': return (i.last_note || {}).at ? '~' + i.last_note.at : '';
  }
}
const cmpv = (a, b) => Array.isArray(a) ? (cmpv(a[0], b[0]) || cmpv(a[1], b[1])) : (a < b ? -1 : a > b ? 1 : 0);
function renderTable() {
  const rows = B.issues.filter(i => issueVisible(i)).sort((a, b) => ((a.status === 'closed') - (b.status === 'closed')) || BV.dir * cmpv(tKey(a, BV.sort), tKey(b, BV.sort)) || a.id - b.id);
  $('#bd-table').innerHTML = `<div class="tw" style="max-height:calc(100vh - 250px)"><table><thead><tr>${TCOLS.map(([k, n]) => `<th class="srt${BV.sort === k ? ' on' + (BV.dir < 0 ? ' desc' : '') : ''}${k === 'idle' || k === 'no' ? ' num' : ''}" data-k="${k}">${n}</th>`).join('')}</tr></thead><tbody>
    ${rows.map(i => { const col = colById(i.column_id) || {}, pr = PRI[i.priority] || PRI.normal, due = dueInfo(i), ck = i.checks || [], cd = ck.filter(c => c.done).length;
      return `<tr class="rowlink${i.status === 'closed' ? ' closed' : ''}" data-id="${i.id}">
        <td class="num muted">#${i.id}</td>
        <td class="t-ttl"><b>${esc(i.title)}</b>${i.labels.length || i.basis_kind ? `<div class="t-lbls">${i.labels.map(labelById).filter(Boolean).map(l => `<span class="c-lbl" style="${lblStyle(l.color)}">${esc(l.name)}</span>`).join('')}${i.basis_kind ? `<span class="c-basis" title="${esc(basisTitle(i))}">${ICO.doc}${esc(BASIS_SHORT[i.basis_kind])}</span>` : ''}</div>` : ''}</td>
        <td>${i.inn ? `${esc(i.company || i.inn)}<div class="muted" style="font-size:12px">${esc(short(distName(i.district_code)))}</div>` : '<span class="muted">умумий</span>'}</td>
        <td><span class="t-col" style="--cc:${esc(col.color || '#8A929C')}">${esc(col.name || '—')}</span></td>
        <td>${pr.c ? `<span class="c-pri" style="color:${pr.c};background:${hexA(pr.c, .12)}">${pr.n}</span>` : `<span class="muted">${pr.n}</span>`}</td>
        <td>${due ? `<span class="bdg ${due.cls}" title="${esc(due.tip)}">${ICO.cal}${esc(due.txt)}</span>` : '<span class="muted">—</span>'}</td>
        <td>${ck.length ? `<span class="bdg ck${cd === ck.length ? ' full' : ''}">${ICO.check}${cd}/${ck.length}<span class="bar"><i style="width:${Math.round(100 * cd / ck.length)}%"></i></span></span>` : '<span class="muted">—</span>'}</td>
        <td class="num">${i.status === 'open' ? `<span class="${i.stale ? 't-bad' : i.idle_days >= 7 ? 't-warn' : 'muted'}">${i.idle_days ? i.idle_days + ' кун' : 'бугун'}</span>` : ''}</td>
        <td class="t-note">${i.last_note ? `<span class="muted">${esc(relTime(i.last_note.at))}:</span> ${esc(i.last_note.text)}` : ''}</td></tr>`; }).join('') || `<tr><td colspan="${TCOLS.length}" class="empty">карта йўқ</td></tr>`}
  </tbody></table></div>`;
  $$('#bd-table th.srt').forEach(th => th.onclick = () => { const k = th.dataset.k; if (BV.sort === k) BV.dir = -BV.dir; else { BV.sort = k; BV.dir = 1; } renderTable(); });
  $$('#bd-table tr[data-id]').forEach(tr => tr.onclick = () => openCard(B.issues.find(i => i.id === +tr.dataset.id)));
}

// ---- svod (ustunlar × ташкилот / туман)
function renderSvod() {
  const rows = B.issues.filter(i => issueVisible(i)), cols = B.columns;
  const dn = {}; S.districts.forEach(d => dn[d.code] = d.name_uz);
  const table = (title, keys, pick) => {
    const lines = keys.map(([k, name]) => { const sel = rows.filter(x => pick(x, k)); return { name, vals: cols.map(c => sel.filter(x => x.column_id === c.id).length), tot: sel.length, over: sel.filter(x => x.overdue).length }; }).filter(l => l.tot);
    const tot = { vals: cols.map((c, i) => lines.reduce((s, l) => s + l.vals[i], 0)), tot: lines.reduce((s, l) => s + l.tot, 0), over: lines.reduce((s, l) => s + l.over, 0) };
    return `<h3>${title}</h3><div class="tw" style="max-height:none"><table><thead><tr><th></th>${cols.map(c => `<th class="num" style="border-bottom:2px solid ${esc(c.color)}">${esc(c.name)}</th>`).join('')}<th class="num">Жами</th><th class="num">Муддати ўтган</th></tr></thead><tbody>
      ${lines.map(l => `<tr><td>${esc(l.name)}</td>${l.vals.map(v => `<td class="num">${v || '<span class="muted">·</span>'}</td>`).join('')}<td class="num"><b>${l.tot}</b></td><td class="num ${l.over ? 't-bad' : ''}">${l.over || '<span class="muted">·</span>'}</td></tr>`).join('') || '<tr><td colspan="99" class="empty">карта йўқ</td></tr>'}
      <tr class="tot"><td>Жами</td>${tot.vals.map(v => `<td class="num">${v}</td>`).join('')}<td class="num">${tot.tot}</td><td class="num ${tot.over ? 't-bad' : ''}">${tot.over}</td></tr></tbody></table></div>`;
  };
  $('#bd-svod-panel').innerHTML = `<h2>Свод <span class="hint">карталар сони · устунлар кесимида · филтрлар ҳисобга олинган (${rows.length} та карта) · бир нечта ташкилотга тегишли карта ҳар бирида саналади</span><span class="right"><a class="btn sm" href="/api/export/issues">Excel'га чиқариш</a><button class="btn sm" id="svod-x">Ёпиш</button></span></h2><div class="svod">
    ${table('Ташкилотлар (белгилар) кесимида', [...B.labels.map(l => [l.id, l.name]), [null, 'Белгисиз']], (x, k) => k == null ? !x.labels.length : x.labels.includes(k))}
    ${table('Туманлар кесимида', [...Object.entries(dn).sort((a, b) => a[1].localeCompare(b[1], 'ru')), [null, 'Умумий (корхонасиз)']], (x, k) => k == null ? !x.inn : x.district_code === k)}
</div>`;
  $('#svod-x').onclick = () => { $('#bd-svod-panel').hidden = true; };
}

// ---- karta modali
// Asosiy maydonlar «Сақлаш» (yoki Ctrl+Enter) bilan saqlanadi; mavjud kartada o'zgarish bo'lsa yopilganda o'zi saqlanadi.
// Qadamlar, izohlar va fayllar darhol saqlanadi (yangi kartada — avval kartaning o'zi saqlanadi).
let CM = { it: null, labels: new Set(), opts: {}, tl: null, tlMode: 'all', snap: '' };
function closeModals() { $$('.mbg').forEach(m => m.hidden = true); }
async function closeCardModal() {
  const m = $('#card-modal');
  if (!m.hidden && CM.it && CM.it.id && cardDirty()) { const ok = await saveCard({}, true, true); if (ok === null) return; toast('Ўзгаришлар сақланди'); CM.changed = false; }
  closeModals();
  if (CM.changed && CM.opts.onChange) { CM.changed = false; CM.opts.onChange(); }
}
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  const dd = document.querySelector('.tagdd-pop:not([hidden])'); if (dd) { dd.hidden = true; return; }
  if (!$('#card-modal').hidden) { closeCardModal(); return; }
  closeModals();
});
$$('.mbg').forEach(m => m.addEventListener('mousedown', e => { if (e.target === m) (m.id === 'card-modal' ? closeCardModal() : closeModals()); }));

function openCard(it, opts = {}) {
  CM = { it: it ? { ...it } : { kind: 'muammo', status: 'open', priority: 'normal', inn: opts.inn || '', company: opts.company || '', labels: [], files: [], checks: [], column_id: opts.column_id || (B.columns.find(c => !c.is_done) || B.columns[0] || {}).id },
    labels: new Set((it || {}).labels || []), opts, tl: null, tlMode: CM.tlMode || 'all', snap: '' };
  renderCardModal(); $('#card-modal').hidden = false;
  if (CM.it.id) loadTimeline();
  setTimeout(() => { const t = $('#cm-title'); if (t && !CM.it.id) t.focus(); }, 30);
}
function cmForm() {
  const inn = $('#cm-inn');
  return { title: $('#cm-title').value, text: $('#cm-text').value, resolution: $('#cm-res').value, due_date: $('#cm-due').value, priority: CM.it.priority || 'normal',
    basis_kind: $('#cm-bk').value, basis_no: $('#cm-bno').value, basis_date: $('#cm-bdate').value, inn: inn.dataset.inn || '', innText: inn.value, labels: [...CM.labels].sort() };
}
const cardDirty = () => !!CM.snap && JSON.stringify(cmForm()) !== CM.snap;
function renderCardModal() {
  const it = CM.it, col = colById(it.column_id), pr = it.priority || 'normal', closed = it.status === 'closed';
  $('#cm-body').innerHTML = `<div class="cm-top">${it.id ? `<button class="x del" id="cm-del" title="Картани ўчириш">🗑</button>` : ''}<button class="x" id="cm-x" title="Ёпиш (Esc)">×</button></div><div class="cm">
    <div class="cm-main">
      <div class="cm-crumb">${it.id ? `<span class="mono">#${it.id}</span>` : '<span class="mono">Янги карта</span>'}${col ? `<span class="cm-col" style="--cc:${esc(col.color || '#8A929C')}">${esc(col.name)}</span>` : ''}
        ${it.id ? `<span>${closed ? `ҳал қилинган ${dmy((it.closed_at || '').slice(0, 10))}` : `шу устунда ${it.col_days || 0} кун`}</span><span>· очилган ${dmy((it.created_at || '').slice(0, 10))}</span>${it.stale ? `<span class="pill bad">туриб қолган · ${it.idle_days} кун ҳаракатсиз</span>` : ''}` : ''}</div>
      <input class="cm-title" id="cm-title" placeholder="Карта номи — қисқа мазмуни *" value="${esc(it.title || '')}" maxlength="200">
      <h4>Корхона <span class="hint" style="text-transform:none;letter-spacing:0">(ИНН ёки ном — лотин/кирилл фарқсиз; бўш — умумий карта)</span></h4>
      <div class="cm-row"><div class="ac" style="flex:1"><input type="text" id="cm-inn" autocomplete="off" placeholder="ИНН ёки номи…" value="${esc(it.inn ? `${it.inn} — ${it.company || ''}` : '')}" data-inn="${esc(it.inn || '')}"${CM.opts.inn ? ' readonly' : ''}><div class="ac-pop" id="cm-inn-pop" hidden></div></div>${it.inn ? `<button class="btn sm" id="cm-prof">Профил</button>` : ''}</div>
      <div id="cm-co"></div>
      <h4>Батафсил</h4><textarea id="cm-text" rows="3" placeholder="Муаммо тафсилоти: нима бўлган, нима қилиш керак…">${esc(it.text || '')}</textarea>
      <h4>Қадамлар <span class="hint" id="cm-ck-n" style="text-transform:none;letter-spacing:0"></span></h4><div id="cm-checks"></div>
      <h4>Бириктирилган файллар <span class="hint" id="cm-att-n" style="text-transform:none;letter-spacing:0"></span></h4>
      <div class="att" id="cm-att"></div>
      <div class="dropz" id="cm-drop">📎 Файл ёки расмни шу ерга ташланг ёки босиб танланг (PDF, Word, Excel, JPG, PNG… 80 МБ гача)</div><input type="file" id="cm-file" multiple hidden>
      <h4>Натижа / қандай ҳал қилинди</h4><textarea id="cm-res" rows="2" placeholder="Ҳал қилингач: қандай натижа бўлди">${esc(it.resolution || '')}</textarea>
      <div class="cm-tl-h"><h4>Изоҳлар ва тарих</h4><div class="seg sm" id="cm-tlm"><button data-m="all" class="${CM.tlMode === 'all' ? 'on' : ''}">Ҳаммаси</button><button data-m="note" class="${CM.tlMode === 'note' ? 'on' : ''}">Фақат изоҳлар</button></div></div>
      <div class="cm-cmt"><textarea id="cm-cmt" rows="2" placeholder="Изоҳ: ким билан гаплашилди, нима келишилди… (Ctrl+Enter)"></textarea><button class="btn primary sm" id="cm-cmt-add">Қўшиш</button></div>
      <div class="tl" id="cm-tl"></div>
    </div>
    <div class="cm-side">
      <div class="fcol"><label>Ташкилотлар</label><div class="tagdd" id="cm-orgs"></div></div>
      <div class="fcol"><label>Устуворлик</label><div class="prio" id="cm-pri">${Object.entries(PRI).map(([k, p]) => `<button type="button" data-p="${k}" class="${k === pr ? 'on' : ''}" style="--pc:${p.c || 'var(--accent)'}">${p.n}</button>`).join('')}</div></div>
      <div class="fcol"><label>Муддат</label><input type="date" id="cm-due" value="${esc(it.due_date || '')}">
        <div class="presets">${[[3, '+3 кун'], [7, '+1 ҳафта'], [14, '+2 ҳафта'], [30, '+1 ой']].map(([n, t]) => `<button type="button" data-d="${n}">${t}</button>`).join('')}<button type="button" data-d="" title="муддатни олиб ташлаш">✕</button></div><div class="due-hint" id="cm-due-h"></div></div>
      <div class="fcol"><label>Асос ҳужжат</label><select class="sel" id="cm-bk"><option value="">— йўқ —</option>${Object.entries(B.basis || {}).map(([k, n]) => `<option value="${k}"${it.basis_kind === k ? ' selected' : ''}>${esc(n)}</option>`).join('')}</select>
        <div class="basis-more" id="cm-bmore"${it.basis_kind ? '' : ' hidden'}><input type="text" id="cm-bno" placeholder="№, банд (мас.: №04-01-220, 3-банд)" value="${esc(it.basis_no || '')}" maxlength="200"><input type="date" id="cm-bdate" value="${esc(it.basis_date || '')}" title="ҳужжат санаси"></div></div>
      <button class="btn primary" id="cm-save">${it.id ? 'Сақлаш' : '+ Карта қўшиш'}</button>
      <div class="kbd-hint">Ctrl+Enter — сақлаш · Esc — ёпиш${it.id ? '<br>ёпилганда ўзгаришлар ўзи сақланади' : ''}</div>
    </div></div>`;
  renderOrgPicker();
  companyPicker($('#cm-inn'), $('#cm-inn-pop'), inn => renderCompanyBrief(inn));
  renderCompanyBrief(it.inn);
  renderChecks(); renderAtt(); renderTimeline(); dueHint();
  $('#cm-x').onclick = closeCardModal;
  $('#cm-save').onclick = () => saveCard();
  if ($('#cm-prof')) $('#cm-prof').onclick = () => { closeModals(); openCompany(it.inn); };
  if ($('#cm-del')) $('#cm-del').onclick = async () => {
    const b = $('#cm-del'); if (!b.dataset.sure) { b.dataset.sure = '1'; b.textContent = 'Ўчирилсинми?'; b.classList.add('arm'); setTimeout(() => { delete b.dataset.sure; b.textContent = '🗑'; b.classList.remove('arm'); }, 4000); return; }
    try { await api('/api/issues/delete', J({ id: it.id })); toast('Карта ўчирилди'); closeModals(); await afterCardChange(); } catch (e) { toast(e.message, true); } };
  const dz = $('#cm-drop'), fi = $('#cm-file');
  dz.onclick = () => fi.click();
  fi.onchange = () => { uploadFiles([...fi.files]); fi.value = ''; };
  dz.addEventListener('dragover', e => { e.preventDefault(); e.stopPropagation(); dz.classList.add('over'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('over'));
  dz.addEventListener('drop', e => { e.preventDefault(); e.stopPropagation(); dz.classList.remove('over'); uploadFiles([...e.dataTransfer.files]); });
  $('#cm-title').onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); saveCard(); } };
  $$('#cm-pri button').forEach(b => b.onclick = () => { CM.it.priority = b.dataset.p; $$('#cm-pri button').forEach(x => x.classList.toggle('on', x === b)); });
  $('#cm-due').onchange = dueHint;
  $$('.presets button').forEach(b => b.onclick = () => { $('#cm-due').value = b.dataset.d ? addDays(+b.dataset.d) : ''; dueHint(); });
  $('#cm-bk').onchange = () => { $('#cm-bmore').hidden = !$('#cm-bk').value; if ($('#cm-bk').value) $('#cm-bno').focus(); };
  $$('#cm-tlm button').forEach(b => b.onclick = () => { CM.tlMode = b.dataset.m; $$('#cm-tlm button').forEach(x => x.classList.toggle('on', x === b)); renderTimeline(); });
  $('#cm-cmt-add').onclick = addComment;
  $('#cm-cmt').onkeydown = e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); e.stopPropagation(); addComment(); } };
  CM.snap = JSON.stringify(cmForm());
}
$('#card-modal').addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && e.target.id !== 'cm-cmt' && e.target.id !== 'cm-ck-new') { e.preventDefault(); saveCard(); } });
function dueHint() {
  const v = $('#cm-due').value, h = $('#cm-due-h'); if (!h) return;
  if (!v) { h.textContent = ''; h.className = 'due-hint'; return; }
  const d = daysTo(v);
  h.textContent = d < 0 ? `${-d} кун ўтиб кетган` : d === 0 ? 'бугун' : d === 1 ? 'эртага' : `${d} кун қолди · ${DOWF[new Date(v).getDay()]}`;
  h.className = 'due-hint' + (d < 0 ? ' bad' : d <= 3 ? ' warn' : '');
}
// korxona ma'lumoti: rahbar, telefonlar, tuman/tarmoq, shu yil eksporti
const COB = new Map();
async function renderCompanyBrief(inn) {
  const box = $('#cm-co'); if (!box) return;
  if (!inn) { box.innerHTML = ''; return; }
  let d = COB.get(inn);
  if (!d) {
    box.innerHTML = '<div class="co-brief muted">корхона маълумоти юкланмоқда…</div>';
    try { d = await api('/api/issue/company?inn=' + encodeURIComponent(inn)); COB.set(inn, d); } catch (e) { box.innerHTML = ''; return; }
  }
  if ((($('#cm-inn') || {}).dataset || {}).inn !== inn) return;   // shu orada boshqa korxona tanlandi
  const others = d.open - (CM.it.id && CM.it.inn === inn && CM.it.status === 'open' ? 1 : 0);
  box.innerHTML = `<div class="co-brief">
    <div class="r1"><b>${esc(d.name)}</b><span class="muted">${esc([d.district, d.tarmoq].filter(Boolean).join(' · '))}</span></div>
    <div class="r2">${d.director ? `<span>Раҳбар: <b>${esc(d.director)}</b></span>` : ''}${d.phones.map(telLink).join('')}${d.persons.map(p => `<span class="muted">${esc(p.name)}${p.role ? ` (${esc(p.role)})` : ''}</span>${(p.phones || []).slice(0, 1).map(telLink).join('')}`).join('')}${!d.director && !d.phones.length && !d.persons.length ? '<span class="muted">алоқа маълумоти киритилмаган — «Профил» орқали қўшинг</span>' : ''}</div>
    <div class="r3"><span>${d.year} й. экспорт: <b class="mono">${fmt(d.ytd)}</b> минг $</span>${d.last ? `<span>охирги экспорт: ${dmy(d.last)}</span>` : ''}${others > 0 ? `<span class="pill warn">яна ${others} та очиқ карта</span>` : ''}</div></div>`;
}
// qadamlar (checklist): Enter — qo'shish, bir nechta qator joylansa — bir nechta qadam; ✎ — tahrir, ✕ — o'chirish
function renderChecks() {
  const box = $('#cm-checks'); if (!box) return;
  const ck = CM.it.checks || [], done = ck.filter(c => c.done).length, p = ck.length ? Math.round(100 * done / ck.length) : 0;
  $('#cm-ck-n').textContent = ck.length ? `${done} / ${ck.length} · ${p}%` : '';
  box.innerHTML = `${ck.length ? `<div class="ck-bar${done === ck.length ? ' full' : ''}"><span style="width:${p}%"></span></div>` : ''}
    <div class="ck-list">${ck.map(c => `<div class="ck-it${c.done ? ' done' : ''}" data-k="${c.id}"><input type="checkbox"${c.done ? ' checked' : ''} title="бажарилди"><span class="tx">${esc(c.text)}</span>${c.done && c.done_at ? `<span class="ck-at">${esc(relTime(c.done_at))}</span>` : ''}<button type="button" class="ed" title="таҳрирлаш">✎</button><button type="button" class="dl" title="ўчириш">✕</button></div>`).join('')}</div>
    <input type="text" class="ck-new" id="cm-ck-new" placeholder="+ Қадам қўшиш… (Enter)" maxlength="300" autocomplete="off">`;
  const add = async (text) => {
    const lines = String(text || '').split(/\r?\n/).map(s => s.trim()).filter(Boolean); if (!lines.length) return;
    if (!CM.it.id) { const id = await saveCard({}, true); if (!id) return; }
    try { await api('/api/issue/check/save', J({ issue_id: CM.it.id, text: lines.join('\n') })); await syncCard(); renderChecks(); const n = $('#cm-ck-new'); if (n) n.focus(); } catch (e) { toast(e.message, true); }
  };
  const inp = $('#cm-ck-new');
  inp.onkeydown = e => { e.stopPropagation(); if (e.key === 'Enter') { e.preventDefault(); const v = inp.value; inp.value = ''; add(v); } if (e.key === 'Escape') inp.blur(); };
  inp.onpaste = e => { const t = (e.clipboardData || window.clipboardData).getData('text'); if (/\n/.test(t.trim())) { e.preventDefault(); add(t); } };
  box.querySelectorAll('.ck-it').forEach(row => {
    const id = +row.dataset.k, c = ck.find(x => x.id === id);
    row.querySelector('input').onchange = async e => {
      c.done = e.target.checked ? 1 : 0; c.done_at = c.done ? localISO(new Date()) + ' ' + new Date().toTimeString().slice(0, 8) : null; renderChecks();
      try { await api('/api/issue/check/save', J({ id, done: !!c.done })); syncCard(); loadTimeline(); } catch (err) { toast(err.message, true); await syncCard(); renderChecks(); }
    };
    const edit = () => {
      const tx = row.querySelector('.tx'); const ed = document.createElement('input'); ed.type = 'text'; ed.className = 'ck-edit'; ed.value = c.text; ed.maxLength = 300;
      tx.replaceWith(ed); ed.focus(); ed.select(); let fin = false;
      const done = async save => { if (fin) return; fin = true; const v = ed.value.trim();
        if (save && v && v !== c.text) { try { await api('/api/issue/check/save', J({ id, text: v })); c.text = v; syncCard(); } catch (err) { toast(err.message, true); } }
        renderChecks(); };
      ed.onkeydown = ev => { ev.stopPropagation(); if (ev.key === 'Enter') { ev.preventDefault(); done(true); } if (ev.key === 'Escape') done(false); };
      ed.onblur = () => done(true);
    };
    row.querySelector('.tx').ondblclick = edit; row.querySelector('.ed').onclick = edit;
    row.querySelector('.dl').onclick = async () => { try { await api('/api/issue/check/delete', J({ id })); CM.it.checks = ck.filter(x => x.id !== id); renderChecks(); syncCard(); } catch (err) { toast(err.message, true); } };
  });
}
function renderAtt() {
  const box = $('#cm-att'); if (!box) return; const fl = CM.it.files || [];
  $('#cm-att-n').textContent = fl.length ? fl.length + ' та' : '';
  box.innerHTML = fl.map(f => f.is_image ? `<div class="im"><img src="/api/issue/file?id=${f.id}&inline=1" alt="${esc(f.filename)}" data-open="${f.id}" loading="lazy"><div class="nm" title="${esc(f.filename)}"><a class="clink" href="/api/issue/file?id=${f.id}">${esc(f.filename)}</a></div><button class="rm" data-rmf="${f.id}">✕</button></div>`
    : `<div class="fl"><span class="ic">${fileIcon(f.filename)}</span><div class="nm" title="${esc(f.filename)}"><a class="clink" href="/api/issue/file?id=${f.id}">${esc(f.filename)}</a></div><span class="muted" style="font-size:11px">${kb(f.size || 0)} · ${esc((f.uploaded_at || '').slice(0, 10))}</span><button class="rm" data-rmf="${f.id}">олиб ташлаш</button></div>`).join('');
  box.querySelectorAll('[data-open]').forEach(im => im.onclick = () => window.open(`/api/issue/file?id=${im.dataset.open}&inline=1`, '_blank'));
  box.querySelectorAll('[data-rmf]').forEach(b => b.onclick = async () => {
    if (!b.dataset.sure) { b.dataset.sure = '1'; const t = b.textContent; b.textContent = 'тасдиқлаш?'; setTimeout(() => { delete b.dataset.sure; b.textContent = t; }, 4000); return; }
    try { await api('/api/issue/file/remove', J({ id: +b.dataset.rmf })); toast('Файл олиб ташланди'); await syncCard(); renderAtt(); loadTimeline(); } catch (e) { toast(e.message, true); } });
}
// izohlar + avtomatik tarix (yangisi tepada)
async function loadTimeline() {
  const id = CM.it && CM.it.id; if (!id) return;
  try { const tl = await api('/api/issue/timeline?id=' + id); if (CM.it.id === id) { CM.tl = tl; renderTimeline(); } } catch (e) { /* tarix yuklanmasa karta ishlayveradi */ }
}
function renderTimeline() {
  const box = $('#cm-tl'); if (!box) return;
  const items = (CM.tl || []).filter(x => CM.tlMode === 'all' || x.kind === 'note').slice().reverse();
  box.innerHTML = items.map(x => x.kind === 'note'
    ? `<div class="tl-note" data-c="${x.id}"><div class="tl-h"><span>${esc(relTime(x.at))}</span>${x.edited_at ? '<span>· таҳрирланган</span>' : ''}<span class="tl-act"><button type="button" class="ed" title="таҳрирлаш">✎</button><button type="button" class="dl" title="ўчириш">🗑</button></span></div><div class="tl-t">${esc(x.text)}</div></div>`
    : `<div class="tl-log"><span class="tl-t">${esc(x.text)}</span><span class="tl-at">${esc(relTime(x.at))}</span></div>`).join('')
    || `<div class="tl-empty">${CM.it.id ? (CM.tlMode === 'note' ? 'ҳали изоҳ йўқ' : '') : 'биринчи изоҳ ёзилганда карта ўзи сақланади'}</div>`;
  box.querySelectorAll('.tl-note').forEach(n => {
    const id = +n.dataset.c, x = CM.tl.find(y => y.id === id);
    n.querySelector('.ed').onclick = () => {
      const t = n.querySelector('.tl-t'); const ta = document.createElement('textarea'); ta.className = 'tl-edit'; ta.value = x.text; ta.rows = Math.min(8, x.text.split('\n').length + 1);
      t.replaceWith(ta); ta.focus();
      const bar = document.createElement('div'); bar.className = 'form-row'; bar.innerHTML = '<button class="btn sm primary">Сақлаш</button><button class="btn sm">Бекор</button>'; ta.after(bar);
      bar.children[0].onclick = async () => { try { await api('/api/issue/comment/save', J({ id, text: ta.value })); await loadTimeline(); syncCard(); } catch (e) { toast(e.message, true); } };
      bar.children[1].onclick = renderTimeline;
      ta.onkeydown = e => { e.stopPropagation(); if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); bar.children[0].click(); } if (e.key === 'Escape') renderTimeline(); };
    };
    n.querySelector('.dl').onclick = async e => { const b = e.currentTarget;
      if (!b.dataset.sure) { b.dataset.sure = '1'; b.textContent = 'Ўчирилсинми?'; b.classList.add('arm'); setTimeout(() => { delete b.dataset.sure; b.textContent = '🗑'; b.classList.remove('arm'); }, 4000); return; }
      try { await api('/api/issue/comment/delete', J({ id })); await loadTimeline(); syncCard(); } catch (err) { toast(err.message, true); } };
  });
}
async function addComment() {
  const ta = $('#cm-cmt'), text = ta.value.trim(); if (!text) { ta.focus(); return; }
  if (!CM.it.id) { const id = await saveCard({}, true); if (!id) return; }
  try { await api('/api/issue/comment/save', J({ issue_id: CM.it.id, text })); const t2 = $('#cm-cmt'); if (t2) t2.value = ''; await loadTimeline(); syncCard(); } catch (e) { toast(e.message, true); }
}
// korxona qidiruvi: lotin/kirill farqsiz, ro'yxatdan tanlanadi (datalist o'rniga o'z ro'yxatimiz)
function companyPicker(inp, pop, onPick) {
  if (inp.readOnly) return;
  let items = [], idx = -1;
  const draw = () => {
    pop.innerHTML = items.map((x, i) => `<div class="ac-it${i === idx ? ' on' : ''}" data-i="${i}"><b>${esc(x.name || '')}</b><span class="mono muted">${esc(x.inn)}</span></div>`).join('') || '<div class="ac-none">топилмади</div>';
    pop.hidden = false;
    pop.querySelectorAll('.ac-it').forEach(el => { el.onmousedown = e => { e.preventDefault(); pick(+el.dataset.i); }; });
  };
  const pick = i => { const x = items[i]; if (!x) return; inp.value = `${x.inn} — ${x.name || ''}`; inp.dataset.inn = x.inn; pop.hidden = true; if (onPick) onPick(x.inn); };
  inp.oninput = () => { const had = inp.dataset.inn; inp.dataset.inn = ''; if (had && onPick) onPick(''); const q = inp.value.trim(); if (!q) { pop.hidden = true; return; }
    items = (R.names || []).filter(x => smatch(q, x.inn, x.name)).slice(0, 12); idx = items.length ? 0 : -1; draw(); };
  inp.onfocus = () => { if (inp.value.trim() && !inp.dataset.inn) inp.oninput(); };
  inp.onblur = () => setTimeout(() => pop.hidden = true, 150);
  inp.onkeydown = e => {
    if (pop.hidden) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); idx = Math.min(items.length - 1, idx + 1); draw(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); idx = Math.max(0, idx - 1); draw(); }
    else if (e.key === 'Enter') { e.preventDefault(); pick(idx); }
    else if (e.key === 'Escape') { pop.hidden = true; e.stopPropagation(); }
  };
}
// tashkilotlar: input ko'rinishidagi dropdown — tepasida qidiruv/yangi input (Enter — yaratish), ro'yxatda checkbox (bir nechtasi), ✎ tahrir, 🗑 o'chirish
function renderOrgPicker() {
  const host = $('#cm-orgs');
  host.innerHTML = `<button type="button" class="tagdd-btn"><span class="t"></span><span class="ar">▾</span></button>
    <div class="tagdd-pop" hidden><input type="text" class="tagdd-new" placeholder="Қидириш ёки янги ташкилот… Enter" maxlength="60" autocomplete="off"><div class="tagdd-list"></div></div>`;
  const btn = host.querySelector('.tagdd-btn'), pop = host.querySelector('.tagdd-pop'), txt = host.querySelector('.t'), inp = host.querySelector('.tagdd-new'), list = host.querySelector('.tagdd-list');
  const paint = () => { const ls = [...CM.labels].map(labelById).filter(Boolean);
    txt.innerHTML = ls.length ? ls.map(l => `<span class="sw" style="background:${esc(l.color)}"></span>${esc(l.name)}`).join('<span class="sep">,</span> ') : 'Ташкилот танланг…'; txt.classList.toggle('ph', !ls.length); };
  const reload = async () => { B.labels = (await api('/api/board')).labels; [...CM.labels].forEach(id => { if (!labelById(id)) CM.labels.delete(id); }); };
  const draw = () => {
    const q = inp.value.trim();
    const items = B.labels.filter(l => !q || smatch(q, l.name));
    list.innerHTML = items.map(l => `<div class="tagdd-row" data-id="${l.id}"><label><input type="checkbox"${CM.labels.has(l.id) ? ' checked' : ''}><span class="sw" style="background:${esc(l.color)}"></span><span class="nm">${esc(l.name)}</span></label><button type="button" class="ed" title="Номини ўзгартириш">✎</button><button type="button" class="dl" title="Ўчириш">🗑</button></div>`).join('')
      + (q && !items.some(l => l.name.toLowerCase() === q.toLowerCase()) ? `<div class="tagdd-hint">Enter — «${esc(q)}» янги ташкилот сифатида қўшилади</div>` : (!B.labels.length ? '<div class="tagdd-hint">ҳали ташкилот йўқ — номини ёзиб Enter босинг</div>' : ''));
    list.querySelectorAll('.tagdd-row').forEach(row => {
      const id = +row.dataset.id, l = labelById(id);
      row.querySelector('input[type=checkbox]').onchange = e => { e.target.checked ? CM.labels.add(id) : CM.labels.delete(id); paint(); };
      row.querySelector('.ed').onclick = e => { e.stopPropagation();
        const lab = row.querySelector('label'); const ed = document.createElement('input'); ed.type = 'text'; ed.className = 'tagdd-edit'; ed.value = l.name; ed.maxLength = 60;
        lab.replaceWith(ed); ed.focus(); ed.select(); let done = false;
        const fin = async (save) => { if (done) return; done = true; const name = ed.value.trim();
          if (save && name && name !== l.name) { try { await api('/api/board/label/save', J({ id, name })); await reload(); toast('Номи ўзгартирилди'); } catch (err) { toast(err.message, true); } }
          draw(); paint(); };
        ed.onkeydown = ev => { ev.stopPropagation(); if (ev.key === 'Enter') { ev.preventDefault(); fin(true); } if (ev.key === 'Escape') fin(false); };
        ed.onblur = () => setTimeout(() => fin(true), 120); };
      row.querySelector('.dl').onclick = async e => { e.stopPropagation(); const b = e.currentTarget;
        if (!b.dataset.sure) { b.dataset.sure = '1'; b.textContent = 'Ростданми?'; b.classList.add('arm'); setTimeout(() => { delete b.dataset.sure; b.textContent = '🗑'; b.classList.remove('arm'); }, 4000); return; }
        try { await api('/api/board/label/delete', J({ id })); await reload(); BF.labels.delete(id); toast('Ташкилот ўчирилди'); draw(); paint(); } catch (err) { toast(err.message, true); } };
    });
  };
  const open = () => { document.querySelectorAll('.ms-pop').forEach(x => x.hidden = true); pop.hidden = false; inp.value = ''; draw(); inp.focus(); };
  const close = () => { pop.hidden = true; };
  btn.onclick = e => { e.stopPropagation(); pop.hidden ? open() : close(); };
  pop.onclick = e => e.stopPropagation();
  inp.oninput = draw;
  inp.onkeydown = async e => {
    e.stopPropagation();
    if (e.key === 'Escape') { close(); btn.focus(); return; }
    if (e.key !== 'Enter') return;
    e.preventDefault(); const q = inp.value.trim(); if (!q) return;
    const exact = B.labels.find(l => l.name.toLowerCase() === q.toLowerCase());
    if (exact) { CM.labels.add(exact.id); inp.value = ''; draw(); paint(); return; }
    try { const r = await api('/api/board/label/save', J({ name: q })); await reload(); CM.labels.add(r.id); inp.value = ''; toast('Ташкилот қўшилди'); draw(); paint(); } catch (err) { toast(err.message, true); }
  };
  host._close = close; paint();
}
document.addEventListener('click', () => document.querySelectorAll('.tagdd-pop').forEach(x => x.hidden = true));
function collectCard() {
  const it = CM.it, f = cmForm(); let inn = CM.opts.inn || '';
  if (!CM.opts.inn) { const v = f.innText.trim();
    if (v) { const m = v.match(/^\d{9,14}/); let hit = f.inn || (m ? m[0] : '');
      if (!hit) { const c = (R.names || []).filter(x => smatch(v, x.inn, x.name)); if (c.length === 1) hit = c[0].inn; }
      if (!hit) throw new Error('Корхона топилмади: рўйхатдан танланг ёки ИНН ёзинг'); inn = hit; } }
  return { id: it.id || null, inn, kind: it.kind || 'muammo', title: f.title, text: f.text, responsible: it.responsible || '', due_date: f.due_date, resolution: f.resolution,
    priority: f.priority, basis_kind: f.basis_kind, basis_no: f.basis_kind ? f.basis_no : '', basis_date: f.basis_kind ? f.basis_date : '', column_id: it.column_id, labels: [...CM.labels] };
}
// quiet: toast'siz (fayl/qadam/izohdan oldin avtomatik saqlash); keepOpen: modal yopilmaydi (yopishdan oldingi avtomatik saqlash)
async function saveCard(extra = {}, quiet = false, keepOpen = false) {
  let data; try { data = collectCard(); } catch (e) { toast(e.message, true); return null; }
  try {
    const r = await api('/api/issues/save', J({ ...data, ...extra }));
    if (!quiet) toast(data.id ? 'Сақланди' : 'Карта қўшилди');
    await afterCardChange();
    if (!data.id) { const it = B.issues.find(i => i.id === r.id); if (it) { const mode = CM.tlMode; CM.it = { ...it }; CM.labels = new Set(it.labels); CM.tlMode = mode; renderCardModal(); loadTimeline(); return r.id; } }
    if (data.id && !quiet && !keepOpen) closeModals();
    return r.id;
  } catch (e) { toast(e.message, true); return null; }
}
async function afterCardChange() {
  await loadBoard(); renderBoard();
  if (CM.opts.onChange) CM.opts.onChange();
}
// qadam/fayl/izohdan keyin: doska yangilanadi, modaldagi yozilayotgan maydonlarga tegilmaydi
async function syncCard() {
  await loadBoard(); renderBoard(); CM.changed = true;   // korxona profili (onChange) — modal yopilganda bir marta yangilanadi
  const it = B.issues.find(i => i.id === CM.it.id);
  if (it) { CM.it.checks = it.checks; CM.it.files = it.files; CM.it.n_notes = it.n_notes; CM.it.last_note = it.last_note; }
}
async function uploadFiles(files) {
  if (!files || !files.length) return;
  if (!CM.it.id) { const id = await saveCard({}, true); if (!id) return; }
  const dz = $('#cm-drop'); let ok = 0;
  for (const f of files) {
    dz.textContent = `Юкланмоқда: ${f.name} (${kb(f.size)})…`;
    try { await api('/api/issue/file/upload', { method: 'POST', headers: { 'X-Issue': String(CM.it.id), 'X-Filename': encodeURIComponent(f.name) }, body: f }); ok++; }
    catch (e) { toast(`${f.name}: ${e.message}`, true); }
  }
  dz.textContent = '📎 Файл ёки расмни шу ерга ташланг ёки босиб танланг (PDF, Word, Excel, JPG, PNG… 80 МБ гача)';
  if (ok) toast(ok === 1 ? 'Файл бириктирилди' : `${ok} та файл бириктирилди`);
  await syncCard(); renderAtt(); loadTimeline();
}

// ---- ustun modali
function openColumnModal(c) {
  const isNew = !c; c = c || { name: '', color: '#3B6FB6', is_done: 0 };
  const n = isNew ? 0 : B.issues.filter(i => i.column_id === c.id).length;
  $('#colm-body').innerHTML = `<button class="x" id="colm-x">×</button><div class="cm-main"><h2 style="margin:0 0 12px;font-size:16px">${isNew ? 'Янги устун' : 'Устун созламалари'}</h2>
    <div class="fcol"><label>Устун номи</label><input type="text" id="colm-name" value="${esc(c.name)}" maxlength="60" placeholder="масалан: Вазирликка юборилди">
      <label>Ранг</label><div class="cm-row"><input type="color" id="colm-color" value="${esc(c.color || '#3B6FB6')}"><span class="muted" style="font-size:12px">устун устидаги чизиқ ранги</span></div>
      <label class="form-row" style="gap:8px;font-size:13px;color:var(--ink)"><input type="checkbox" id="colm-done"${c.is_done ? ' checked' : ''}> «Ҳал қилинган» устуни — бу ерга кўчирилган карта ёпилган ҳисобланади</label>
      <div class="form-row"><button class="btn primary" id="colm-save">${isNew ? '+ Қўшиш' : 'Сақлаш'}</button><button class="btn" id="colm-cancel">Бекор</button></div></div>
    ${isNew ? '' : `<hr style="border:0;border-top:1px solid var(--line);margin:14px 0"><div class="fcol"><label>Устунни ўчириш</label>
      ${n ? `<span class="muted" style="font-size:12.5px">Устунда ${n} та карта бор — улар танланган устунга кўчирилади:</span><select class="sel" id="colm-moveto">${B.columns.filter(x => x.id !== c.id).map(x => `<option value="${x.id}">${esc(x.name)}</option>`).join('')}</select>` : '<span class="muted" style="font-size:12.5px">Устун бўш.</span>'}
      <div class="form-row"><button class="btn danger" id="colm-del">Ўчириш</button></div></div>`}</div>`;
  $('#col-modal').hidden = false; $('#colm-name').focus();
  $('#colm-x').onclick = $('#colm-cancel').onclick = closeModals;
  $('#colm-save').onclick = async () => {
    try { await api('/api/board/column/save', J({ id: c.id || null, name: $('#colm-name').value, color: $('#colm-color').value, is_done: $('#colm-done').checked ? 1 : 0 }));
      toast(isNew ? 'Устун қўшилди' : 'Сақланди'); closeModals(); await loadBoard(); renderBoard(); if (isNew) $('#board').scrollLeft = 1e6; } catch (e) { toast(e.message, true); } };
  $('#colm-name').onkeydown = e => { if (e.key === 'Enter') $('#colm-save').click(); };
  if ($('#colm-del')) $('#colm-del').onclick = async () => {
    const b = $('#colm-del'); if (!b.dataset.sure) { b.dataset.sure = '1'; b.textContent = 'Ростдан ўчирилсинми?'; setTimeout(() => { delete b.dataset.sure; b.textContent = 'Ўчириш'; }, 4000); return; }
    try { const mt = $('#colm-moveto'); await api('/api/board/column/delete', J({ id: c.id, move_to: mt ? +mt.value : null })); toast('Устун ўчирилди'); closeModals(); await loadBoard(); renderBoard(); } catch (e) { toast(e.message, true); } };
}

// ---- belgilar (tashkilotlar) modali
function openLabelsModal() {
  const draw = () => {
    $('#lblm-body').innerHTML = `<button class="x" id="lblm-x">×</button><div class="cm-main lblm"><h2 style="margin:0 0 4px;font-size:16px">Белгилар — аloқадор ташкилотлар</h2>
      <p class="muted" style="font-size:12.5px;margin:0 0 12px">Ҳар бир картага бир нечта белги қўйиш мумкин (масалан: Божхона + Солиқ). Ранг автоматик берилади. Кейин доскада белги бўйича филтрланади ва сводда кўринади.</p>
      ${B.labels.map(l => `<div class="row" data-id="${l.id}"><span class="sw big" style="background:${esc(l.color)}"></span><input type="text" value="${esc(l.name)}" class="ln" maxlength="60"><span class="used">${l.used} та карта</span><button class="btn sm ls">Сақлаш</button><button class="btn sm danger ld">Ўчириш</button></div>`).join('') || '<div class="empty">ҳали белги йўқ</div>'}
      <hr style="border:0;border-top:1px solid var(--line);margin:12px 0"><div class="row"><input type="text" id="lblm-nname" placeholder="Янги белги: Божхона, Солиқ, Банк, Вазирлик…" maxlength="60"><button class="btn sm primary" id="lblm-add">+ Қўшиш</button></div></div>`;
    $('#lblm-x').onclick = closeModals;
    const reload = async () => { await loadBoard(); draw(); renderBoard(); };
    $('#lblm-add').onclick = async () => { try { await api('/api/board/label/save', J({ name: $('#lblm-nname').value })); toast('Белги қўшилди'); await reload(); $('#lblm-nname').focus(); } catch (e) { toast(e.message, true); } };
    $('#lblm-nname').onkeydown = e => { if (e.key === 'Enter') $('#lblm-add').click(); };
    $$('#lblm-body .row[data-id]').forEach(r => {
      r.querySelector('.ls').onclick = async () => { try { await api('/api/board/label/save', J({ id: +r.dataset.id, name: r.querySelector('.ln').value })); toast('Сақланди'); await reload(); } catch (e) { toast(e.message, true); } };
      r.querySelector('.ld').onclick = async () => { const b = r.querySelector('.ld'); if (!b.dataset.sure) { b.dataset.sure = '1'; b.textContent = 'Ростданми?'; setTimeout(() => { delete b.dataset.sure; b.textContent = 'Ўчириш'; }, 4000); return; }
        try { await api('/api/board/label/delete', J({ id: +r.dataset.id })); toast('Белги ўчирилди'); BF.labels.delete(+r.dataset.id); await reload(); } catch (e) { toast(e.message, true); } };
    });
  };
  draw(); $('#lbl-modal').hidden = false;
}

// ---- sahifa tugmalari va klaviatura (N — yangi karta, / — qidiruv)
let issTm; $('#iss-q').addEventListener('input', () => { clearTimeout(issTm); issTm = setTimeout(renderBoard, 200); });
$('#iss-q').addEventListener('keydown', e => { if (e.key === 'Escape' && $('#iss-q').value) { e.stopPropagation(); $('#iss-q').value = ''; renderBoard(); } });
$('#iss-d').addEventListener('change', renderBoard);
$('#bd-clear').onclick = () => { $('#iss-q').value = ''; $('#iss-d').value = ''; BF.noCompany = false; BF.labels.clear(); BF.state = ''; renderBoard(); };
$('#iss-new').onclick = () => openCard(null);
$('#bd-addcol').onclick = () => openColumnModal(null);
$('#bd-labels').onclick = openLabelsModal;
$('#bd-svod').onclick = () => { const p = $('#bd-svod-panel'); p.hidden = !p.hidden; if (!p.hidden) { renderSvod(); p.scrollIntoView({ block: 'nearest' }); } };
$$('#bd-view button').forEach(b => b.onclick = () => { BV.view = b.dataset.v; try { localStorage.setItem('bd-view', BV.view); } catch (_) {} renderBoard(); });
document.addEventListener('keydown', e => {
  if (!$('#p-iss').classList.contains('active') || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.target.closest('input,textarea,select,[contenteditable]') || $$('.mbg').some(m => !m.hidden)) return;
  if (e.code === 'KeyN') { e.preventDefault(); openCard(null); }
  else if (e.code === 'Slash') { e.preventDefault(); $('#iss-q').focus(); $('#iss-q').select(); }
});

// ---- korxona profili: «Muammo va vazifalar» tabi shu doskaning kartalarini ko'rsatadi
async function tabIssues(p, body) {
  if (!B.loaded) { await loadBoard(); }
  const mine = B.issues.filter(i => i.inn === p.inn).sort((a, b) => (a.status === 'open' ? 0 : 1) - (b.status === 'open' ? 0 : 1) || (b.overdue ? 1 : 0) - (a.overdue ? 1 : 0) || b.id - a.id);
  const open = mine.filter(i => i.status === 'open'), closed = mine.filter(i => i.status !== 'open');
  const list = arr => `<div class="board" style="min-height:0;flex-wrap:wrap;overflow:visible">${arr.map(i => `<div style="flex:0 0 292px;width:292px">${cardHTML(i)}</div>`).join('')}</div>`;
  body.innerHTML = `<div class="panel"><h2>Очиқ <span class="hint">${open.length} та</span><span class="right"><button class="btn sm primary" id="pf-new">+ Янги карта</button><button class="btn sm" id="pf-board">Доскага ўтиш</button></span></h2>
      ${open.length ? list(open) : '<div class="empty">очиқ муаммо ва вазифа йўқ</div>'}
      ${closed.length ? `<h2 style="margin-top:14px">Ҳал қилинган <span class="hint">${closed.length} та</span></h2>${list(closed)}` : ''}
      <p class="note">Карта устига босиб очинг. Шу ерда ёзилганлар «Muammo va vazifalar» доскасида ҳам кўринади.</p></div>`;
  const opts = { inn: p.inn, company: p.company.name, onChange: reloadProfile };
  body.querySelectorAll('.card').forEach(el => { el.draggable = false; el.style.cursor = 'pointer'; el.onclick = () => openCard(B.issues.find(i => i.id === +el.dataset.id), opts); });
  $('#pf-new').onclick = () => openCard(null, opts);
  $('#pf-board').onclick = () => go('iss');
}

// ---------------------------------------------------------------- NAZORAT
loaders.ctrl = async () => {
  const [ups, bks, integ, audit] = await Promise.all([api('/api/uploads'), api('/api/backups'), api('/api/integrity'), api('/api/audit')]);
  $('#t-up').innerHTML = ups.map(u => `<tr><td class="mono">${u.id}</td><td>${esc(u.loaded_at)}</td><td class="mono" style="font-size:12px">${esc(u.filename)}</td><td>${JSON.parse(u.report_dates).map(dmy).join(', ')}</td><td class="num">${fmt0(u.rows_total)}</td><td class="num">${u.rows_bukhara}</td><td class="num">${u.rows_karantin}</td><td class="num">${fmt(u.sum_sanoat, 2)}</td><td class="num">${fmt(u.sum_meva, 2)}</td><td>${JSON.parse(u.new_inns || '[]').length || ''}</td>
    <td>${u.status === 'saved' ? '<span class="pill ok">saqlangan</span>' : `<span class="pill bad">bekor qilingan</span> <span class="muted">${esc(u.note || '')}</span>`}</td><td>${u.status === 'saved' ? `<button class="btn sm danger" data-void="${u.id}">Bekor qilish</button>` : ''}</td></tr>`).join('') || '<tr><td colspan="12" class="empty">hali yuklash yo\'q</td></tr>';
  $$('[data-void]').forEach(b => b.onclick = async () => {
    if (b.dataset.armed !== '1') { b.dataset.armed = '1'; b.textContent = 'Tasdiqlang'; setTimeout(() => { b.dataset.armed = ''; b.textContent = 'Bekor qilish'; }, 4000); return; }
    try { await api('/api/uploads/void', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: +b.dataset.void, reason: 'foydalanuvchi bekor qildi' }) }); toast('Yuklash bekor qilindi (zaxira olindi)'); S.dash = null; await loadStatus(); loaders.ctrl(); } catch (e) { toast(e.message, true); } });
  $('#t-bk').innerHTML = bks.map(b => `<tr><td class="mono" style="font-size:12px">${esc(b.name)}</td><td>${esc(b.mtime.replace('T', ' '))}</td><td class="num">${fmt(b.size / 1048576, 1)} MB</td><td><button class="btn sm" data-rs="${esc(b.name)}">Qaytarish</button></td></tr>`).join('') || '<tr><td colspan="4" class="empty">zaxira yo\'q</td></tr>';
  $$('[data-rs]').forEach(b => b.onclick = async () => {
    if (b.dataset.armed !== '1') { b.dataset.armed = '1'; b.textContent = 'Aniqmi?'; setTimeout(() => { b.dataset.armed = ''; b.textContent = 'Qaytarish'; }, 4000); return; }
    try { await api('/api/backups/restore', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: b.dataset.rs }) }); toast('Baza zaxiradan qaytarildi (joriy holat ham zaxiralandi)'); S.dash = null; await loadStatus(); loaders.ctrl(); } catch (e) { toast(e.message, true); } });
  const st = S.status;
  $('#db-state').innerHTML = `<div class="check"><div class="ic ${integ.ok ? 'ok' : 'bad'}">${integ.ok ? '✓' : '✕'}</div><div><b>${integ.ok ? 'Butunlik tekshiruvi o\'tdi' : 'Baza buzilgan — zaxiradan qaytaring'}</b><span>SQLite integrity_check</span></div></div>
    <div class="check"><div class="ic ${st.readonly ? 'warn' : 'ok'}">${st.readonly ? '!' : '✓'}</div><div><b>${st.readonly ? 'Boshqa kompyuterda ochiq' : 'Faqat shu kompyuterda ochiq'}</b><span>${esc(st.host)} · baza oxirgi o'zgargan: ${esc((st.db_mtime || '').replace('T', ' '))}</span></div></div>
    <div class="check"><div class="ic ok">✓</div><div><b>${st.uploads} ta yuklash, ${fmt0(st.companies)} korxona</b><span>tasdiqlanmagan: ${st.unconfirmed}</span></div></div>`;
  $('#t-audit').innerHTML = audit.map(a => `<tr><td class="mono" style="font-size:12px;white-space:nowrap">${esc(a.at)}</td><td>${esc(a.action)}</td><td class="muted" style="font-size:12px">${esc((a.details || '').slice(0, 120))}</td></tr>`).join('');
};
$('#bk-create').onclick = async () => { try { const r = await api('/api/backups/create', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); toast('Zaxira olindi: ' + r.name); loaders.ctrl(); } catch (e) { toast(e.message, true); } };

// ---------------------------------------------------------------- SOZLAMALAR
loaders.set = async () => {
  const s = await api('/api/settings'); const st = S.status;
  $('#set-paths').innerHTML = `<div class="check"><div class="ic ok">✓</div><div><b>Ma'lumotlar papkasi</b><span class="mono">${esc(st.data_dir)}</span></div></div>
    <div class="check"><div class="ic ok">✓</div><div><b>Baza fayli</b><span class="mono">${esc(st.db_path)}</span></div></div>
    <div class="check"><div class="ic ${st.opening_date ? 'ok' : 'warn'}">${st.opening_date ? '✓' : '–'}</div><div><b>Boshlang'ich qoldiq</b><span>${st.opening_date ? dmy(st.opening_date) + (st.opening_source === 'customs' ? " gacha — sanoat bojxona oylik bazasidan, meva-sabzavot kunlik jadvaldan" : " gacha — kunlik jadvaldan") : "yuklanmagan — summa faqat ilovaga kiritilgan GTD lardan"}</span></div></div>
    <div class="check"><div class="ic ${st.companies ? 'ok' : 'bad'}">${st.companies ? '✓' : '!'}</div><div><b>Korxonalar reyestri</b><span>${st.companies ? fmt0(st.companies) + ' ta INN' : "bo'sh — bojxona oylik bazasini yuklang"}</span></div></div>
    <p class="note">Papkani o'zgartirish (masalan Google Disk): dastur yonidagi <span class="mono">config.json</span> faylida <span class="mono">data_dir</span> ni yozing va dasturni qayta ishga tushiring.</p>`;
  $('#set-off').value = s.prev_year_day_offset ?? 0;
  $('#set-prev').textContent = s.prev_year_base_label ? 'Baza: ' + s.prev_year_base_label : '';
};
$('#set-save').onclick = async () => { try { await api('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prev_year_day_offset: $('#set-off').value }) }); toast('Saqlandi'); S.dash = null; } catch (e) { toast(e.message, true); } };

// opening data (two steps)
async function initUpload(inp, kind, stEl) {
  const f = inp.files[0]; if (!f) return;
  $(stEl).textContent = 'yuklanmoqda…';
  try { const r = await api('/api/init/upload', { method: 'POST', body: f, headers: { 'X-Filename': encodeURIComponent(f.name), 'X-Kind': kind } }); $(stEl).textContent = '✓ ' + fmt(r.size / 1048576, 1) + ' MB'; }
  catch (e) { $(stEl).textContent = ''; toast(e.message, true); }
}
$('#in-bz').onchange = e => initUpload(e.target, 'baza', '#in-bz-s');
$('#in-wb').onchange = e => initUpload(e.target, 'workbook', '#in-wb-s');
const ck = (ok, title, detail, lvl) => `<div class="check"><div class="ic ${ok ? 'ok' : (lvl || 'warn')}">${ok ? '✓' : (lvl === 'bad' ? '✕' : '!')}</div><div><b>${title}</b><span>${detail || ''}</span></div></div>`;
function renderBaza(r) {
  const ms = Object.entries(r.months);
  const T = r.tree || {};
  const tree = ck(true, `Ma'lumot daraxti: ${fmt0(T.declarations)} ta GTD · ${fmt0(T.items)} ta tovar qatori (${(r.years || [r.year]).join(', ')} yil)`,
    `eksport ${fmt0(T.export_items)} · import ${fmt0(T.import_items)} qator · ${fmt0(T.hs_codes)} HS kod · ${fmt0(T.countries)} davlat · ${fmt0(T.unions)} uyushma · ${fmt0(T.posts)} bojxona posti — hammasi korxona INN'iga bog'langan`);
  const V = r.verify || [];
  const verify = V.length ? ck(r.verify_ok !== false, r.verify_ok !== false ? `Tekshiruv: fayl va sayt daraxti ${V.map(v => v.year).join(', ')} yil bo'yicha aynan mos` : `Tekshiruv: fayl va sayt daraxti orasida farq bor!`,
      V.map(v => `${v.year}: ${v.full ? 'toʻliq yil (12 oy) tozalab qayta yuklanadi' : 'faylda bor oylar almashtiriladi'} — eski ${fmt0(v.old_rows)} → yangi ${fmt0(v.file_rows)} qator`).join(' · '), r.verify_ok === false ? 'bad' : undefined)
    + `<div class="tw" style="margin:6px 0"><table><thead><tr><th>Йил</th><th class="num">Қатор (файл)</th><th class="num">Қатор (сайт)</th><th class="num">Экспорт ЭК</th><th class="num">шундан саноат</th><th class="num">мева-сабзавот</th><th class="num">БНПЗ</th><th class="num">Импорт ИМ</th><th></th></tr></thead>`
    + V.map(v => `<tr><td><b>${v.year}</b></td><td class="num">${fmt0(v.file_rows)}</td><td class="num">${fmt0(v.db_rows)}</td><td class="num">${fmt(v.db.ek)}</td><td class="num">${fmt(v.db.sanoat)}</td><td class="num">${fmt(v.db.meva)}</td><td class="num">${fmt(v.db.bnpz)}</td><td class="num">${fmt(v.db.im)}</td><td>${v.ok ? '<span class="pill ok">мос</span>' : '<span class="pill bad">фарқ</span>'}</td></tr>`).join('')
    + `</table></div><p class="note">Суммалар минг АҚШ долл., «стат. стоимость 1000$» устунидан; йил — «Расмийлаштирилган сана» бўйича. Саноат/мева/БНПЗ — экспорт ичидаги тақсимот (мева — «товар1» бўйича, ҳар қандай экспортёр).</p>` : '';
  if (r.operational === false)
    return ck(true, `Tarixiy baza: ${(r.years || [r.year]).join(', ')} yil`, `saytning joriy yili o'zgarmaydi, «yil boshidan» hisob va qoldiqlar tegilmaydi — bu yillar solishtirish (kunlik hisobot modalidagi «o'tgan yil» variantlari) va korxona tarixi uchun saqlanadi`)
      + verify + tree + ck(true, `Reyestr: ${fmt0(r.registry.inns)} ta INN`, `yangi qo'shiladi: ${fmt0(r.registry.added)} · ${r.registry.districts} tuman`);
  return ck(true, `Sanoat eksporti: ${fmt(r.sanoat_total)} ming $`, `01.01 – ${dmy(r.through)} · ${r.exporters} ta eksportyor korxona`)
    + verify
    + `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:6px;margin:6px 0 8px">${ms.map(([m, v]) => `<div class="step" style="padding:6px 10px"><span class="muted">${MONTHS[m - 1]}</span><b style="font-size:14px">${fmt(v)}</b></div>`).join('')}</div>`
    + tree
    + ck(true, `Reyestr: ${fmt0(r.registry.inns)} ta INN`, `yangi qo'shiladi: ${fmt0(r.registry.added)} · ${r.registry.districts} tuman`)
    + ck(true, `Olinmadi: БНПЗ ${fmt(r.excluded_bnpz)} ming $, meva-sabzavot ${fmt(r.meva_not_taken)} ming $`, "БНПЗ hisobga kirmaydi; meva-sabzavot kunlik GTD dan karantin qoidasi bo'yicha yig'iladi")
    + (r.covered_gtd.rows ? ck(false, `${r.covered_gtd.rows} ta GTD qatori (${fmt(r.covered_gtd.sum, 2)} ming $) ${dmy(r.through)} gacha`, "bu kunlar endi bojxona bazasi bo'yicha hisoblanadi — yuklashlar tarixda qoladi") : '')
    + (r.meva_rolled ? ck(true, `Meva-sabzavot qoldig'iga qo'shildi: ${fmt(r.meva_rolled, 2)} ming $`, `${dmy(r.old_through)} – ${dmy(r.through)} kunlik GTD lardan`) : '');
}
function renderContinuity(r) {
  const c = r.continuity, P = r.previous_template;
  if (!P) return ck(true, "Birinchi shablon", "keyingi yuklashlarda jadval oldingi shablon + saytdagi GTD bilan solishtiriladi");
  if (!c) return '';
  if (c.error) return ck(false, "Oldingi shablon bilan solishtirib bo'lmadi", esc(c.error));
  const head = `oldingi shablon «${esc(P.file)}» (${dmy(P.through)} gacha) ${fmt(c.old_total)} + saytdagi GTD ${fmt(c.site_added)} → yangi jadval ${fmt(c.new_total)}`;
  let out = c.mismatch_count === 0
    ? ck(true, `Uzluksizlik: ${c.compared} korxonaning hammasi mos`, head)
    : ck(false, `Uzluksizlik: ${c.mismatch_count} korxonada farq bor, jami ${c.mismatch_sum > 0 ? '+' : ''}${fmt(c.mismatch_sum, 2)} ming $`, head + ' · jadvalda qo\'lda tuzatilgan bo\'lsa normal; bo\'lmasa noto\'g\'ri fayl bo\'lishi mumkin')
      + `<div class="tw" style="max-height:220px;margin:6px 0"><table><thead><tr><th>ИНН</th><th>Корхона</th><th class="num">Кутилган</th><th class="num">Жадвалда</th><th class="num">Фарқ</th></tr></thead>${c.mismatch.map(x => `<tr><td class="mono">${esc(x.inn)}</td><td>${esc(x.name || '')}${x.cat === 'meva' ? ' <span class="pill info">мева</span>' : ''}</td><td class="num">${fmt(x.expected, 2)}</td><td class="num">${fmt(x.actual, 2)}</td><td class="num">${fmt(x.diff, 2)}</td></tr>`).join('')}</table></div>`;
  if (c.removed.length) out += ck(false, `номманомdan o'chirilgan: ${c.removed.length} ta`, c.removed.map(x => `${esc(x.name || x.inn)} (${fmt(x.old, 2)})`).join('; '), 'bad');
  if (c.missing_days.length) out += ck(false, `Saytda GTD yuklanmagan kunlar: ${c.missing_days.map(d => dmy(d).slice(0, 5)).join(', ')}`, "shu kunlar tufayli farq chiqishi mumkin");
  return out;
}
function renderWb(r) {
  const T = r.template, sv = r.svod;
  const t = sv.meva_by_district.reduce((s, x) => s + x.ytd, 0);
  return renderContinuity(r) + ck(true, `Jadval sanasi ${dmy(T.label)} йил → ma'lumot ${dmy(T.through)} gacha`, `joriy oy: ${MONTHS[T.cur_month - 1]} (номманом Q ustuni) · sayt ${dmy(isoNext(T.through))} dan keyingi kunlarni qo'shadi`)
    + ck(true, `номманом: ${T.companies} korxona, ${T.blocks} tuman bloki`, `sariq (yangi eksportyor): ${T.yellow.length} ta` + (T.dups.length ? ` · ikki qatorda turgan INN: ${T.dups.join(', ')}` : '') + (T.tail.length ? ` · ЖАМИ dan pastda: ${T.tail.join(', ')}` : ''))
    + ck(T.karantin_meva_rows >= 13, `Karantin svod: «${esc(T.karantin_sheet)}»`, `${T.karantin_meva_rows} ta meva-sabzavot qatori · oy varag'i: ${T.karantin_month_sheet ? '«' + esc(T.karantin_month_sheet) + '»' : "yo'q — GTD qatorlari qo'yilmaydi"}`)
    + ck(!!T.governor, T.governor ? `БНПЗ katagi: «${esc(T.governor.sheet)}» ${T.governor.cell}` : "«СВОД 450 млн» da Қоровулбозор sanoat qatori topilmadi", T.governor ? 'yil boshidan «амалда» ga «+X» qo\'shiladi' : 'БНПЗ qo\'shilmaydi')
    + ck(T.prev_year_cells > 0, `«2025 yilning shu kuniga» formulasi: ${T.prev_year_cells} katak`, `kun soni har kuni yangilanadi` + (T.prev_year_stale ? ` · ${T.prev_year_stale} ta eski varaqdagi katakka tegilmaydi` : ''))
    + ck(true, `Tashqi havolalar: ${T.external_links} ta`, "boshqa fayllarga VLOOKUP formulalari o'zgarmasdan saqlanadi")
    + (T.lost_objects.length ? ck(false, 'Excel faylidagi ' + T.lost_objects.join(', ') + ' saqlanmaydi', 'sayt faqat kataklar va formulalar bilan ishlaydi') : '')
    + (sv.meva_skipped ? ck(true, "Meva-sabzavot qoldig'i o'zgartirilmadi", "jadval oyi bojxona bazasidan keyingi oy emas — dashboard uchun oldingi qoldiq qoladi")
       : ck(true, `Meva-sabzavot ${dmy(r.through)} gacha: ${fmt(t)} ming $`, `dashboard uchun · jadval ${MONTHS[(sv.workbook_month || 1) - 1]} oyi holatida — ${sv.workbook_month === +r.through.slice(5, 7) + 1 ? "shu oy olib tashlandi (u GTD dan yig'iladi)" : "to'liq olindi"}`))
    + ck(true, `Prognoz: ${sv.prognoz} qator · korxona atributlari: ${r.companies.companies}`, 'yillik, 9 oylik, oylik, o\'tgan yil bazasi; tarmoq, mahsulot')
    + (r.gtd_after.days ? ck(true, `Saytda ${dmy(T.through)} dan keyingi ${r.gtd_after.days} kun GTD bor`, `${fmt(r.gtd_after.sum, 2)} ming $ — Excelga qo'shiladi`) : '');
}
function setupInit(mode, checkSel, applySel, resSel, inputSel, stSel, render) {
  $(checkSel).onclick = async () => {
    $(checkSel).disabled = true; $(applySel).disabled = true;
    $(resSel).innerHTML = `<p class="note">Tekshirilmoqda…${mode === 'baza' ? ' (yillik baza 1–2 daqiqa, oylik 30–60 soniya)' : ' (.xls bo\'lsa Excel orqali o\'giriladi, 10–30 soniya)'}</p>`;
    try { const r = await api('/api/init/check', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }) });
      $$('#p-set .btn.primary').forEach(x => x.disabled = true);   // only the step just checked may be applied
      $(resSel).innerHTML = render(r); $(applySel).disabled = false; }
    catch (e) { $(resSel).innerHTML = ck(false, 'Xato', esc(e.message), 'bad'); }
    $(checkSel).disabled = false;
  };
  $(applySel).onclick = async () => {
    const b = $(applySel);
    if (b.dataset.armed !== '1') { b.dataset.armed = '1'; b.textContent = 'Aniqmi? Yana bosing'; setTimeout(() => { b.dataset.armed = ''; b.textContent = 'Almashtirish'; }, 5000); return; }
    b.disabled = true;
    try { await api('/api/init/apply', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }) });
      toast(mode === 'baza' ? 'Bojxona bazasi yuklandi' : 'O\'z jadvalingiz ma\'lumotlari yuklandi');
      S.dash = null; K.sel = null; await loadStatus(); $(resSel).innerHTML = ''; $(inputSel).value = ''; $(stSel).textContent = ''; }
    catch (e) { toast(e.message, true); b.disabled = false; }
    b.dataset.armed = ''; b.textContent = 'Almashtirish';
  };
}
setupInit('baza', '#bz-check', '#bz-apply', '#bz-res', '#in-bz', '#in-bz-s', renderBaza);
setupInit('workbook', '#wb-check', '#wb-apply', '#wb-res', '#in-wb', '#in-wb-s', renderWb);

$('#rs-go').onclick = async () => {
  if ($('#rs-word').value.trim() !== 'TOZALASH') { toast('Tasdiqlash uchun TOZALASH deb yozing', true); return; }
  $('#rs-go').disabled = true;
  try { const r = await api('/api/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirm: 'TOZALASH', keep_manual: $('#rs-keep').checked }) });
    toast('Baza tozalandi. Zaxira: ' + r.backup); $('#rs-word').value = ''; S.dash = null; K.sel = null; S.districts = []; await loadStatus(); go('dash'); }
  catch (e) { toast(e.message, true); }
  $('#rs-go').disabled = false;
};

// ---------------------------------------------------------------- boot
(async () => {
  try { await loadStatus(); await loadDash(); }
  catch (e) { toast(e.message, true); }
  setInterval(() => loadStatus().catch(() => {}), 60000);
})();

// ================================================================ ЭКСПОРТ ГЕОГРАФИЯСИ
const G = { map: null, data: null, sel: null, ms: {}, from: '', to: '' };
const GEO_SCALE = ['#e4efec', '#bcdcd3', '#8ac7b7', '#4fa992', '#1f8770', '#0F6E63', '#0a4f47'];

function geoColor(v, max) {
  if (!v || !max) return '#eef1ef';
  const t = Math.pow(v / max, 0.42);                       // kuchli farqni yumshatish uchun
  return GEO_SCALE[Math.min(GEO_SCALE.length - 1, Math.max(0, Math.round(t * (GEO_SCALE.length - 1))))];
}
function geoPeriod(q) {
  const last = S.status.last_date || todayISO();
  const y = last.slice(0, 4), m = +last.slice(5, 7);
  if (q === 'm') return [`${y}-${String(m).padStart(2, '0')}-01`, last];
  if (q === 'q') return [`${y}-${String(Math.floor((m - 1) / 3) * 3 + 1).padStart(2, '0')}-01`, last];
  if (q === '30') { const d = new Date(last + 'T00:00:00'); d.setDate(d.getDate() - 29); return [localISO(d), last]; }
  if (/^y\d{4}$/.test(q)) return [`${q.slice(1)}-01-01`, `${q.slice(1)}-12-31`];       // o'tgan yil butunicha
  return [`${y}-01-01`, last];
}
function geoQuery() {
  return new URLSearchParams({ from: G.from, to: G.to, district: G.ms.d.value, tarmoq: G.ms.tr.value,
    country: G.ms.c.value, kind: G.ms.k.value, memo: $('#geo-memo').checked ? '1' : '0' });
}
loaders.geo = async () => {
  if (!G.ms.d) {
    const re = () => loadGeo().catch(e => toast(e.message, true));
    G.ms.d = multiSel('#geo-d', 'Барча туманлар', re);
    G.ms.tr = multiSel('#geo-tr', 'Барча тармоқлар', re);
    G.ms.c = multiSel('#geo-c', 'Барча давлатлар', re);
    G.ms.k = multiSel('#geo-k', 'Барча турлар', re); G.ms.k.setOptions([{ v: 'sanoat', t: 'Саноат' }, { v: 'meva', t: 'Мева-сабзавот' }]);
    [G.from, G.to] = geoPeriod('ytd'); $('#geo-f').value = G.from; $('#geo-t').value = G.to;
    $$('#geo-quick button').forEach(b => b.onclick = () => {
      $$('#geo-quick button').forEach(x => x.classList.toggle('on', x === b));
      [G.from, G.to] = geoPeriod(b.dataset.q); $('#geo-f').value = G.from; $('#geo-t').value = G.to; re();
    });
    ['#geo-f', '#geo-t'].forEach(id => $(id).onchange = () => {
      G.from = $('#geo-f').value; G.to = $('#geo-t').value;
      $$('#geo-quick button').forEach(x => x.classList.remove('on')); re();
    });
    $('#geo-memo').onchange = re;
    $('#geo-xl').onclick = () => {
      const cs = G.ms.c.value ? G.ms.c.value.split(',').filter(Boolean) : [];
      if (!cs.length) return download('/api/export/geo?' + geoQuery(), `Экспорт географияси ${dmy(G.to)}.xlsx`);
      geoTradeXl(cs);        // давлат танланган: экспорт + импорт (туман, соҳа, номма-ном)
    };
    $('#gd-close').onclick = closeDrawer; $('#geo-scrim').onclick = closeDrawer;
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });
  }
  await loadGeo();
};
function geoTradeXl(cs) {
  const q = geoQuery(); q.set('country', cs.join(','));
  const nm = cs.length <= 3 ? cs.join(', ') : cs.slice(0, 3).join(', ') + ' ва б.';
  return download('/api/export/geo_trade?' + q.toString(), `${nm} — экспорт ва импорт ${dmy(todayISO())}.xlsx`);
}
function geoXlLabel() {
  const cs = G.ms.c && G.ms.c.value ? G.ms.c.value.split(',').filter(Boolean) : [];
  $('#geo-xl').textContent = cs.length ? '📗 Excel: экспорт ва импорт' : '📗 Excel';
  $('#geo-xl').title = cs.length ? `${cs.join(', ')} — экспорт ва импорт: туманлар, соҳалар, номма-ном` : 'Давлатлар кесими (давлат танланса — экспорт ва импорт тўлиқ)';
}
async function loadGeo() {
  const d = await api('/api/geo?' + geoQuery()); G.data = d;
  G.ms.d.setOptions(d.districts.map(x => ({ v: x.code, t: x.name })));
  G.ms.tr.setOptions(d.tarmoqlar.map(t => ({ v: t, t })));
  G.ms.c.setOptions(d.all_countries.map(t => ({ v: t, t })));
  geoXlLabel();
  $('#geo-sub').textContent = `${dmy(d.from)} — ${dmy(d.to)} · минг АҚШ доллари · ўтган йил шу давр: ${dmy(d.prev_from)} — ${dmy(d.prev_to)}`;
  const gr = d.prev_total ? (d.total / d.prev_total - 1) * 100 : null;
  $('#geo-kpi').innerHTML = [
    `<div class="kpi accent"><div class="l">Экспорт ҳажми</div><div class="v">${fmt(d.total / 1000)}<small>млн $</small></div><div class="d">${fmt(d.total)} минг $${d.meva_base ? ` · шундан мева база даври (давлатсиз): ${fmt(d.meva_base)}` : ''} · ўтган йил ${fmt(d.prev_total)} ${gr == null ? '' : `<b class="${gr >= 0 ? 't-ok' : 't-bad'}">${gr >= 0 ? '+' : ''}${fmt(gr, 0)}%</b>`} <span class="muted">(${d.prev_source === 'settings' ? 'Созламалар базаси, кунга мутаносиб' : 'божхона базаси'}${d.prev_total_customs != null ? `; давлат қаторлари — божхона базаси, жами ${fmt(d.prev_total_customs)}` : ''})</span></div></div>`,
    `<div class="kpi"><div class="l">Давлатлар</div><div class="v">${fmt0(d.countries)}</div><div class="d">${d.rows.length ? `энг йириги: ${esc(d.rows[0].country)} · ${fmt(d.rows[0].share)}%` : '—'}</div></div>`,
    `<div class="kpi ${d.new_count ? 'gold' : ''}"><div class="l">Янги бозорлар</div><div class="v">${fmt0(d.new_count)}</div><div class="d">ўтган йил шу даврда экспорт бўлмаган давлатлар</div></div>`,
    `<div class="kpi ${d.lost.length ? 'gold' : ''}"><div class="l">Йўқотилган бозорлар</div><div class="v">${fmt0(d.lost.length)}</div><div class="d">${d.lost.length ? `${d.lost.slice(0, 3).map(x => esc(x.country)).join(', ')}${d.lost.length > 3 ? ' …' : ''} · ${fmt(d.lost.reduce((s, x) => s + x.prev, 0))} минг $ ўтган йил` : 'ҳамма бозорлар сақланган'}</div></div>`,
    `<div class="kpi"><div class="l">Экспортёр корхоналар</div><div class="v">${fmt0(d.companies)}</div><div class="d">${fmt0(d.gtd)} та ГТД</div></div>`,
    ].join('');
  const max = d.rows.length ? d.rows[0].value : 0;
  const byCode = {}; d.rows.forEach(r => { if (r.code) byCode[r.code] = r.value; });
  drawMap(byCode, max);
  $('#geo-cnt').textContent = `${d.rows.length} та · жами ${fmt(d.shown)}`;
  $('#geo-list').innerHTML = d.rows.map((r, i) => `<button class="crow ${G.sel === r.country ? 'on' : ''}" data-c="${esc(r.country)}">
      <span class="i">${i + 1}</span><span class="nm">${esc(r.country)}${r.new ? ' <span class="pill gold">янги</span>' : ''}<small title="${r.new_companies.length ? `янги экспортёрлар: ${r.new_companies.length}` : ''}">${r.companies} корхона · ${r.gtd} ГТД</small></span>
      <span class="v"><b>${fmt(r.value)}</b><span>${r.prev ? `<span class="gr ${r.value >= r.prev ? 'up' : 'dn'}">${r.value >= r.prev ? '+' : ''}${fmt((r.value / r.prev - 1) * 100, 0)}%</span> · ` : ''}${fmt(r.share)}%</span></span>
      <span class="sb"><i style="width:${max ? Math.max(2, 100 * r.value / max) : 0}%;background:${geoColor(r.value, max)}"></i></span></button>`).join('')
    + (d.lost.length ? `<div class="lost"><b>Йўқотилган бозорлар</b> <span class="hint">ўтган йил шу даврда бор эди, ҳозир йўқ</span>${d.lost.map(x => `<div class="lr"><span class="nm">${esc(x.country)}</span><span class="v mono">${fmt(x.prev)}</span><small>${x.top.map(t => `<a href="#" data-inn="${esc(t.inn)}">${esc(t.name || t.inn)}</a>`).join(', ')}</small></div>`).join('')}</div>` : '')
    || '<div class="empty">Бу филтр бўйича экспорт топилмади</div>';
  $$('#geo-list .lost a[data-inn]').forEach(a => a.onclick = e => { e.preventDefault(); openCompany(a.dataset.inn); });
  $$('#geo-list .crow').forEach(b => b.onclick = () => openCountry(b.dataset.c));
  const steps = [0, .05, .15, .35, .6, .85, 1].map(t => Math.round(Math.pow(t, 1 / 0.42) * max));
  $('#geo-legend').innerHTML = 'Экспорт ҳажми: ' + GEO_SCALE.map((c, i) => `<span><span class="sw" style="background:${c}"></span>${i === 0 ? '0' : fmt0(steps[i])}</span>`).join(' ')
    + (d.unmapped.length ? ` · <span class="t-bad">харитада йўқ: ${d.unmapped.map(esc).join(', ')}</span>` : '');
}
const median = a => { if (!a.length) return 0; const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

function paintMap(byCode, max) {
  if (!G.map) return;
  Object.entries(G.map.regions).forEach(([code, reg]) => {
    try { reg.element.setStyle('fill', byCode[code] ? geoColor(byCode[code], max) : '#eef1ef'); } catch (e) { /* қитъасиз ҳудуд */ }
  });
}
function drawMap(byCode, max) {
  if (G.map) return paintMap(byCode, max);
  G.map = new jsVectorMap({
    selector: '#map', map: 'world', backgroundColor: 'transparent', zoomButtons: true, zoomOnScroll: false,
    regionStyle: { initial: { fill: '#eef1ef', stroke: '#ffffff', strokeWidth: .7 }, hover: { fillOpacity: 1, stroke: '#0F6E63', strokeWidth: 1.4 } },
    onRegionTooltipShow(e, tip, code) {
      const r = (G.data.rows || []).find(x => x.code === code);
      const nm = (G.map && G.map._mapData.paths[code] && G.map._mapData.paths[code].name) || code;
      tip.text(r ? `<b>${esc(r.country)}</b><br>${fmt(r.value)} минг $ · ${fmt(r.share)}%<br>${r.companies} корхона · ${r.gtd} ГТД`
                 : `<b>${esc(nm)}</b><br>экспорт йўқ`, true);
    },
    onRegionClick(e, code) {
      const r = (G.data.rows || []).find(x => x.code === code);
      if (r) openCountry(r.country); else toast('Бу давлатга экспорт қилинмаган');
    }
  });
  paintMap(byCode, max);
}
function closeDrawer() {
  $('#geo-drawer').classList.remove('open'); $('#geo-drawer').setAttribute('aria-hidden', 'true'); $('#geo-scrim').classList.remove('on');
  G.sel = null; $$('#geo-list .crow').forEach(x => x.classList.remove('on'));
}
async function openCountry(name) {
  G.sel = name;
  $$('#geo-list .crow').forEach(x => x.classList.toggle('on', x.dataset.c === name));
  $('#geo-drawer').classList.add('open'); $('#geo-drawer').setAttribute('aria-hidden', 'false'); $('#geo-scrim').classList.add('on');
  $('#gd-title').textContent = name; $('#gd-sub').textContent = 'юкланмоқда…'; $('#gd-body').innerHTML = '<div class="empty">…</div>';
  try {
    const q = geoQuery(); q.set('country', name);
    const d = await api('/api/geo/country?' + q.toString());
    const row = (G.data.rows || []).find(x => x.country === name) || {};
    $('#gd-sub').textContent = `${dmy(d.from)} — ${dmy(d.to)} · вилоят экспортининг ${fmt(row.share || 0)}%`;
    $('#gd-body').innerHTML = `
      <div class="dstat">
        <div><b>${fmt(d.total)}</b><span>минг $</span></div>
        <div><b>${fmt0(d.companies.length)}</b><span>корхона</span></div>
        <div><b>${fmt0(d.gtd)}</b><span>ГТД</span></div>
        <div><b>${fmt(d.netto_t)}</b><span>нетто, т</span></div></div>
      <button class="btn" id="gd-xl" style="align-self:flex-start">📗 Excel: экспорт ва импорт</button>
      <div><h2 style="font-size:14px;margin:0 0 6px">Корхоналар</h2>
        <div class="tw" style="max-height:38vh"><table><thead><tr><th>Корхона</th><th>Туман</th><th class="num">Қиймат</th><th class="num">%</th><th class="num">ГТД</th></tr></thead><tbody>
        ${d.companies.map(c => `<tr class="rowlink" data-inn="${esc(c.inn)}"><td><span class="clink">${esc(c.name || c.inn)}</span>${c.product ? `<div class="muted" style="font-size:11.5px">${esc(c.product)}</div>` : ''}</td>
          <td>${esc(short(c.district || '—'))}</td><td class="num">${fmt(c.value)}</td><td class="num">${fmt(c.share)}</td><td class="num">${c.gtd}</td></tr>`).join('')
        || '<tr><td colspan="5" class="empty">маълумот йўқ</td></tr>'}</tbody></table></div></div>
      ${d.products.length ? `<div><h2 style="font-size:14px;margin:0 0 6px">Маҳсулотлар <span class="hint">ТН ВЭД 4 белги</span></h2>
        <div class="tw" style="max-height:30vh"><table><thead><tr><th>Маҳсулот</th><th>Код</th><th class="num">Қиймат</th><th class="num">%</th><th class="num">Нетто, т</th></tr></thead><tbody>
        ${d.products.map(x => `<tr><td>${esc(x.name || '—')}</td><td class="mono">${esc(x.hs4)}</td><td class="num">${fmt(x.value)}</td><td class="num">${fmt(x.share)}</td><td class="num">${fmt(x.netto_t)}</td></tr>`).join('')}
        </tbody></table></div></div>` : ''}`;
    $$('#gd-body tr[data-inn]').forEach(tr => tr.onclick = () => { closeDrawer(); openCompany(tr.dataset.inn); });
    $('#gd-xl').onclick = () => geoTradeXl([name]);
  } catch (e) { $('#gd-body').innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}

/* ---------------------------------------------------------------- Тармоқ ва маҳсулот (daraxt) */
const PR = { year: null, cls: 'A', ms: {}, data: null, open: new Set(), q: '' };
function prodQuery() {
  return new URLSearchParams({ year: PR.year || '', cls: PR.cls, district: PR.ms.d.value, kind: PR.ms.k.value, memo: $('#prod-memo').checked ? '1' : '0' });
}
loaders.prod = async () => {
  if (!PR.ms.d) {
    const re = () => loadProd().catch(e => toast(e.message, true));
    PR.ms.d = multiSel('#prod-d', 'Барча туманлар', re);
    PR.ms.k = multiSel('#prod-k', 'Барча турлар', re); PR.ms.k.setOptions([{ v: 'sanoat', t: 'Саноат' }, { v: 'meva', t: 'Мева-сабзавот' }]);
    $('#prod-memo').onchange = re;
    $$('#prod-cls button').forEach(b => b.onclick = () => { $$('#prod-cls button').forEach(x => x.classList.toggle('on', x === b)); PR.cls = b.dataset.c; PR.open.clear(); re(); });
    $('#prod-q').oninput = () => { PR.q = $('#prod-q').value.trim(); renderProd(); };
    $('#prod-open').onclick = () => { PR.openAll = true; renderProd(); };
    $('#prod-close').onclick = () => { PR.openAll = false; PR.open.clear(); renderProd(); };
    $('#prod-xl').onclick = () => download('/api/export/products?' + prodQuery(), `Тармоқ ва маҳсулот ${PR.year}.xlsx`);
    $('#t-prod tbody').addEventListener('click', e => {
      const a = e.target.closest('a[data-inn]'); if (a) { e.preventDefault(); openCompany(a.dataset.inn); return; }
      const tr = e.target.closest('tr[data-id]'); if (!tr) return;
      const id = tr.dataset.id; if (PR.open.has(id)) PR.open.delete(id); else PR.open.add(id);
      PR.openAll = false; renderProd();
    });
  }
  await loadProd();
};
async function loadProd() {
  const d = await api('/api/products?' + prodQuery()); PR.data = d; PR.year = d.year;
  $('#prod-y').innerHTML = d.years.map(y => `<button data-y="${y}" class="${y === d.year ? 'on' : ''}">${y}</button>`).join('');
  $$('#prod-y button').forEach(b => b.onclick = () => { PR.year = +b.dataset.y; PR.open.clear(); loadProd().catch(e => toast(e.message, true)); });
  PR.ms.d.setOptions(d.districts.map(x => ({ v: x.code, t: x.name })));
  $('#prod-sub').textContent = `${dmy(d.from)} — ${dmy(d.to)} · минг АҚШ доллари · ${d.levels.join(' → ')} → корхоналар`;
  const gr = d.prev_total ? (d.total / d.prev_total - 1) * 100 : null;
  const top = d.items[0];
  $('#prod-kpi').innerHTML = [
    `<div class="kpi accent"><div class="l">Экспорт ҳажми</div><div class="v">${fmt(d.total / 1000)}<small>млн $</small></div><div class="d">${fmt(d.total)} минг $${d.prev_total ? ` · ўтган йил шу даврда ${fmt(d.prev_total)} (${d.prev_source === 'settings' ? 'Созламалар' : 'божхона'})` : ''}</div></div>`,
    `<div class="kpi"><div class="l">Ўсиш</div><div class="v ${gr == null ? '' : (gr >= 0 ? 't-ok' : 't-bad')}">${gr == null ? '—' : (gr >= 0 ? '+' : '') + fmt(gr) + '%'}</div><div class="d">${d.prev_period ? `${dmy(d.prev_period[0])} — ${dmy(d.prev_period[1])} га нисбатан` : '—'}</div></div>`,
    `<div class="kpi"><div class="l">${d.levels[0]}</div><div class="v">${fmt0(d.items.length)}</div><div class="d">${top ? `энг йириги: ${esc(top.key)} · ${fmt(top.value / d.total * 100)}%` : '—'}</div></div>`,
    `<div class="kpi"><div class="l">Корхоналар</div><div class="v">${fmt0(d.companies)}</div><div class="d">${fmt0(d.gtd)} та ГТД · ${fmt0(d.rows)} товар қатори</div></div>`].join('');
  $('#prod-h0').textContent = d.levels.join(' / ');
  $('#prod-hp').textContent = `${d.year - 1} й.`;
  $('#prod-note').innerHTML = `Манба: божхона базаси (${dmy(S.status.opening_date)} гача) + кундалик ГТД. «Бухоро эмас» корхоналар ва бошқа вилоят мева-сабзавоти ҳисобга кирмайди; мева-сабзавот — фақат карантин рўйхати бўйича (тугун «Мева-сабзавот (карантин рўйхати, база даври)» = свод база даври, корхона/ГТД сонисиз); БНПЗ ва SDK — «Алоҳида ҳисоб» белгиланганда. `
    + `<b>Ўтган йил:</b> ${d.prev_source === 'settings' ? 'Созламалар базаси (кунга мутаносиб)' : 'божхона базаси'}; тугунлар — божхона базаси ${d.year - 1}${d.prev_total_customs != null ? ` (жами ${fmt(d.prev_total_customs)})` : ''}. `
    + `ТН ВЭД номи: лугатда ${fmt0(d.hs_named)} / ${fmt0(d.hs_total)} код расмий номли, қолганида ГТД товар матнидан намуна.`;
  renderProd();
}
function prodMatch(it, q) {
  if (!q) return true;
  const own = smatch(q, it.key, it.name || '');
  if (own) return true;
  if (it.children) return it.children.some(c => prodMatch(c, q));
  return (it.companies_list || []).some(c => smatch(q, c.name, c.inn));
}
function renderProd() {
  const d = PR.data; if (!d) return;
  const q = PR.q; const total = d.total || 1;
  const growth = (v, p) => p ? `<span class="gr ${v >= p ? 'up' : 'dn'}">${v >= p ? '+' : ''}${fmt((v / p - 1) * 100, 0)}%</span>` : '<span class="muted">—</span>';
  const out = [];
  const walk = (items, lvl, path, parentVal) => {
    for (const it of items) {
      if (!prodMatch(it, q)) continue;
      const id = path + '|' + it.key;
      const isOpen = PR.openAll || PR.open.has(id) || (q && lvl < d.levels.length - 1);
      const hs = !it.children;
      const share = (it.value || 0) / ((lvl === 0 ? total : parentVal) || 1) * 100;
      out.push(`<tr class="tn l${lvl}${isOpen ? ' open' : ''}" data-id="${esc(id)}"><td><span class="tg"><span class="ar">▶</span>${hs ? `<span class="hs">${esc(it.key)}</span>${esc(it.name !== it.key ? it.name : '')}` : esc(it.key)}<span class="cnt">${hs ? fmt0(it.companies) + ' корхона' : ''}</span></span></td>
        <td class="num">${fmt(it.value)}</td><td><div class="bar" title="${lvl === 0 ? 'жамидан' : 'юқори даражадан'} ${fmt(share)}%"><i style="width:${Math.min(100, share)}%"></i></div><span class="hint">${fmt(share)}%</span></td>
        <td class="num">${it.prev ? fmt(it.prev) : '—'}</td><td class="num">${growth(it.value, it.prev)}</td><td class="num">${fmt(it.netto_t)}</td><td class="num">${fmt0(it.companies)}</td><td class="num">${fmt0(it.gtd)}</td></tr>`);
      if (!isOpen) continue;
      if (it.children) walk(it.children, lvl + 1, id, it.value);
      else for (const c of it.companies_list) {
        const synthetic = !c.inn || String(c.inn).startsWith('karantin:');   // «Мева-сабзавот (карантин рўйхати, база даври)»: туман қатори, корхона эмас
        out.push(`<tr class="co"><td>${synthetic ? `${esc(c.name)} <span class="cnt">свод база даври</span>` : `<a href="#" data-inn="${esc(c.inn)}">${esc(c.name)}</a>`} <span class="cnt">${esc(c.district || '')}</span><span class="ctry">${esc((c.countries || []).join(', '))}</span></td>
          <td class="num">${fmt(c.value)}</td><td><span class="hint">${fmt((c.value || 0) / (it.value || 1) * 100)}%</span></td><td class="num">${c.prev ? fmt(c.prev) : '—'}</td><td class="num">${growth(c.value, c.prev)}</td><td class="num">${fmt(c.netto_t)}</td><td class="num">—</td><td class="num">${fmt0(c.gtd)}</td></tr>`);
      }
    }
  };
  walk(d.items, 0, '', total);
  $('#t-prod tbody').innerHTML = out.join('') || '<tr><td colspan="8" class="muted">Маълумот йўқ</td></tr>';
}

/* ---------------------------------------------------------------- Корхона ҳаракати (yildan yilga) */
const MV = { year: null, tab: 'new', ms: {}, data: null, q: '' };
loaders.mov = async () => {
  if (!MV.ms.d) {
    const re = () => loadMov().catch(e => toast(e.message, true));
    MV.ms.d = multiSel('#mov-d', 'Барча туманлар', re);
    $$('#mov-tab button').forEach(b => b.onclick = () => { $$('#mov-tab button').forEach(x => x.classList.toggle('on', x === b)); MV.tab = b.dataset.t; renderMov(); });
    $('#mov-q').oninput = () => { MV.q = $('#mov-q').value.trim(); renderMov(); };
    $('#mov-xl').onclick = () => download('/api/export/movement?year=' + (MV.year || '') + '&district=' + MV.ms.d.value, `Корхона ҳаракати ${MV.year}.xlsx`);
    $('#t-mov tbody').addEventListener('click', e => { const a = e.target.closest('a[data-inn]'); if (a) { e.preventDefault(); openCompany(a.dataset.inn); } });
  }
  await loadMov();
};
async function loadMov() {
  const d = await api('/api/movement?' + new URLSearchParams({ year: MV.year || '', district: MV.ms.d.value })); MV.data = d; MV.year = d.year;
  $('#mov-y').innerHTML = d.years.map(y => `<button data-y="${y}" class="${y === d.year ? 'on' : ''}">${y}</button>`).join('');
  $$('#mov-y button').forEach(b => b.onclick = () => { MV.year = +b.dataset.y; loadMov().catch(e => toast(e.message, true)); });
  MV.ms.d.setOptions(d.districts.map(x => ({ v: x.code, t: x.name })));
  const k = d.kpi, gr = k.prev_same ? (k.total / k.prev_same - 1) * 100 : null;
  $('#mov-sub').textContent = `${d.year} йил (${dmy(d.upto)} гача) ва ${d.year - 1} йил (шу давр: ${dmy(d.same)} гача) · минг АҚШ доллари`;
  $('#mov-kpi').innerHTML = [
    `<div class="kpi accent"><div class="l">Экспортёрлар</div><div class="v">${fmt0(k.exporters)}<small>/ ${fmt0(k.exporters_prev)} ўтган йил</small></div><div class="d">${fmt(k.total)} минг $ (вилоят жами: саноат + мева карантин) · ўтган йил шу давр ${fmt(k.prev_same)} ${gr == null ? '' : `<b class="${gr >= 0 ? 't-ok' : 't-bad'}">${gr >= 0 ? '+' : ''}${fmt(gr, 0)}%</b>`}${k.total_companies != null ? ` · корхоналар йиғиндиси ${fmt(k.total_companies)}` : ''}${k.prev_source === 'settings' ? ' · ўтган йил: Созламалар базаси (кунга мутаносиб); қаторлар — божхона базаси ' + (d.year - 1) : ''}</div></div>`,
    `<div class="kpi click ${MV.tab === 'new' ? 'on' : ''}" data-t="new"><div class="l">Янги экспортёрлар</div><div class="v">${fmt0(k.new.n)}</div><div class="d">${fmt(k.new.sum)} минг $ · ўтган йил экспорти йўқ эди</div></div>`,
    `<div class="kpi click ${MV.tab === 'stopped' ? 'on' : ''}" data-t="stopped"><div class="l">${d.past ? 'Тўхтаганлар' : 'Бу йил ҳали экспорт йўқ'}</div><div class="v">${fmt0(k.stopped.n)}</div><div class="d">ўтган йил ${fmt(k.stopped.sum)} минг $ (шу даврда ${fmt(k.stopped.sum_same)})</div></div>`,
    `<div class="kpi click ${MV.tab === 'up' ? 'on' : ''}" data-t="up"><div class="l">Ўсганлар</div><div class="v t-ok">${fmt0(k.up.n)}</div><div class="d">+${fmt(k.up.diff)} минг $ ўтган йил шу даврга нисбатан</div></div>`,
    `<div class="kpi click ${MV.tab === 'down' ? 'on' : ''}" data-t="down"><div class="l">Камайганлар</div><div class="v t-bad">${fmt0(k.down.n)}</div><div class="d">${fmt(k.down.diff)} минг $ ўтган йил шу даврга нисбатан</div></div>`].join('');
  $$('#mov-kpi .kpi.click').forEach(e => e.onclick = () => { MV.tab = e.dataset.t; $$('#mov-tab button').forEach(x => x.classList.toggle('on', x.dataset.t === MV.tab)); renderMov(); });
  $('#mov-h1').textContent = `${d.year}`; $('#mov-h2').textContent = `${d.year - 1} шу давр`; $('#mov-h3').textContent = `${d.year - 1} жами`;
  renderMov();
}
function renderMov() {
  const d = MV.data; if (!d) return;
  $$('#mov-kpi .kpi.click').forEach(e => e.classList.toggle('on', e.dataset.t === MV.tab));
  const q = MV.q.toLowerCase();
  const rows = d.rows[MV.tab].filter(r => !q || smatch(q, r.inn, r.name));
  const growth = r => r.growth == null ? '<span class="muted">—</span>' : `<span class="gr ${r.growth >= 0 ? 'up' : 'dn'}">${r.growth >= 0 ? '+' : ''}${fmt(r.growth, 0)}%</span>`;
  $('#t-mov tbody').innerHTML = rows.map((r, i) => `<tr><td class="mono">${i + 1}</td><td class="mono">${esc(r.inn)}</td><td><a href="#" data-inn="${esc(r.inn)}">${esc(r.name)}</a>${r.new_date ? ` <span class="pill gold">янги · ${dmy(r.new_date)}</span>` : ''}<br><small class="muted">${esc(r.tarmoq || '')}</small></td><td>${esc(r.district || '—')}</td>
    <td class="num">${r.cur ? fmt(r.cur) : '—'}</td><td class="num">${r.prev_same ? fmt(r.prev_same) : '—'}</td><td class="num">${r.prev_full ? fmt(r.prev_full) : '—'}</td><td class="num">${growth(r)}</td><td class="num">${r.diff ? (r.diff > 0 ? '+' : '') + fmt(r.diff) : '—'}</td><td class="mono">${r.last ? dmy(r.last) : (r.last_prev ? dmy(r.last_prev) + ' <span class="muted">(ўтган йил)</span>' : '—')}</td></tr>`).join('')
    || '<tr><td colspan="10" class="muted">рўйхат бўш</td></tr>';
  const T = { new: 'янги — ўтган йил экспорт қилмаган, бу йил қилган', stopped: 'ўтган йил экспорт қилган, бу йил ҳали йўқ', up: 'икки йилда ҳам бор, ўтган йил шу даврга нисбатан ўсган', down: 'икки йилда ҳам бор, ўтган йил шу даврга нисбатан камайган' }[MV.tab];
  $('#mov-note').innerHTML = `${rows.length} та корхона · ${T}. Манба: божхона базаси + кундалик ГТД; «Бухоро эмас», БНПЗ ва SDK кирмайди. Кун-кунига солиштириш: ${dmy(d.upto)} ↔ ${dmy(d.same)}.`;
}

/* ---------------------------------------------------------------- Динамика (oylar kesimida) */
const DY = { year: null, by: 'total', ms: {}, data: null, sel: null, q: '' };
function dynQuery() { return new URLSearchParams({ year: DY.year || '', by: DY.by, district: DY.ms.d.value, kind: DY.ms.k.value, memo: $('#dyn-memo').checked ? '1' : '0' }); }
loaders.dyn = async () => {
  if (!DY.ms.d) {
    const re = () => loadDyn().catch(e => toast(e.message, true));
    DY.ms.d = multiSel('#dyn-d', 'Барча туманлар', re);
    DY.ms.k = multiSel('#dyn-k', 'Барча турлар', re); DY.ms.k.setOptions([{ v: 'sanoat', t: 'Саноат' }, { v: 'meva', t: 'Мева-сабзавот' }]);
    $('#dyn-memo').onchange = re;
    $$('#dyn-by button').forEach(b => b.onclick = () => { $$('#dyn-by button').forEach(x => x.classList.toggle('on', x === b)); DY.by = b.dataset.b; DY.sel = null; re(); });
    $('#dyn-q').oninput = () => { DY.q = $('#dyn-q').value.trim(); renderDyn(); };
    $('#dyn-xl').onclick = () => download('/api/export/dynamics?' + dynQuery(), `Динамика ${DY.year}.xlsx`);
    $('#t-dyn tbody').addEventListener('click', e => { const tr = e.target.closest('tr[data-k]'); if (!tr) return; DY.sel = DY.sel === tr.dataset.k ? null : tr.dataset.k; renderDyn(); });
  }
  await loadDyn();
};
async function loadDyn() {
  const d = await api('/api/dynamics?' + dynQuery()); DY.data = d; DY.year = d.year;
  $('#dyn-y').innerHTML = d.years.map(y => `<button data-y="${y}" class="${y === d.year ? 'on' : ''}">${y}</button>`).join('');
  $$('#dyn-y button').forEach(b => b.onclick = () => { DY.year = +b.dataset.y; DY.sel = null; loadDyn().catch(e => toast(e.message, true)); });
  DY.ms.d.setOptions(d.districts.map(x => ({ v: x.code, t: x.name })));
  const gr = d.prev_ytd ? (d.ytd / d.prev_ytd - 1) * 100 : null;
  const best = d.total_months.map((v, i) => [v, i]).sort((a, b) => b[0] - a[0])[0];
  const q = d.cur_month; const qs = [0, 3, 6, 9].map(s => d.total_months.slice(s, s + 3).reduce((a, b) => a + b, 0)); const pqs = [0, 3, 6, 9].map(s => d.prev_total_months.slice(s, s + 3).reduce((a, b) => a + b, 0));
  $('#dyn-sub').textContent = `${d.year} йил (${dmy(d.from)} — ${dmy(d.to)}) ва ${d.year - 1} йил шу давр · минг АҚШ доллари`;
  $('#dyn-kpi').innerHTML = [
    `<div class="kpi accent"><div class="l">${d.year}, ${dmy(d.to)} гача</div><div class="v">${fmt(d.ytd / 1000)}<small>млн $</small></div><div class="d">${d.year - 1} шу давр ${fmt(d.prev_ytd)} ${gr == null ? '' : `<b class="${gr >= 0 ? 't-ok' : 't-bad'}">${gr >= 0 ? '+' : ''}${fmt(gr, 0)}%</b>`} · ${d.year - 1} йил жами ${fmt(d.prev_year)}</div></div>`,
    `<div class="kpi"><div class="l">Ўртача ойлик</div><div class="v">${fmt(d.ytd / Math.max(1, q))}</div><div class="d">${d.year - 1} шу давр: ${fmt(d.prev_ytd / Math.max(1, q))} минг $ / ой</div></div>`,
    `<div class="kpi"><div class="l">Энг юқори ой</div><div class="v">${best ? MONTHS[best[1]] : '—'}</div><div class="d">${best ? fmt(best[0]) + ' минг $' : ''}</div></div>`,
    `<div class="kpi"><div class="l">Чораклар</div><div class="v" style="font-size:16px">${qs.map((v, i) => `${i + 1}ч ${fmt0(v)}`).join(' · ')}</div><div class="d">${d.year - 1}: ${pqs.map((v, i) => `${fmt0(v)}`).join(' · ')}</div></div>`].join('');
  renderDyn();
}
function renderDyn() {
  const d = DY.data; if (!d) return;
  const cm = d.cur_month, q = DY.q;
  const rows = d.rows.filter(r => !q || smatch(q, r.key));
  const head = `<tr><th>${{ total: 'Жами', district: 'Туман', tarmoq: 'Тармоқ', country: 'Давлат', union: 'Уюшма', company: 'Корхона' }[d.by]}</th>${MSHORT.map((m, i) => `<th class="num${i >= cm ? ' muted' : ''}">${m}</th>`).join('')}<th class="num">${d.year}</th><th class="num">${d.year - 1} шу давр</th><th class="num">Ўсиш</th><th class="num">${d.year - 1} жами</th></tr>`;
  $('#t-dyn thead').innerHTML = head;
  const gr = r => r.prev_ytd ? `<span class="gr ${r.ytd >= r.prev_ytd ? 'up' : 'dn'}">${r.ytd >= r.prev_ytd ? '+' : ''}${fmt((r.ytd / r.prev_ytd - 1) * 100, 0)}%</span>` : '<span class="muted">—</span>';
  const line = (r, cls) => `<tr class="${cls}${DY.sel === r.key ? ' on' : ''}" data-k="${esc(r.key)}"><td class="k" title="${esc(r.key)}">${r.inn ? `<a href="#" class="clink" data-inn="${esc(r.inn)}">${esc(r.key)}</a>` : esc(r.key)}</td>${r.months.map((v, i) => `<td class="num${i >= cm ? ' muted' : ''}">${v ? fmt(v) : (i < cm ? '—' : '')}</td>`).join('')}<td class="num"><b>${fmt(r.ytd)}</b></td><td class="num">${fmt(r.prev_ytd)}</td><td class="num">${gr(r)}</td><td class="num">${fmt(r.prev_year)}</td></tr>
    <tr class="sub${DY.sel === r.key ? ' on' : ''}" data-k="${esc(r.key)}"><td class="sub k">${d.year - 1}</td>${r.prev_months.map(v => `<td class="num sub">${v ? fmt(v) : '—'}</td>`).join('')}<td class="num sub"></td><td class="num sub"></td><td class="num sub"></td><td class="num sub"></td></tr>`;
  $('#t-dyn tbody').innerHTML = rows.slice(0, 300).map(r => line(r, 'tn')).join('') || '<tr><td colspan="17" class="muted">маълумот йўқ</td></tr>';
  $$('#t-dyn a[data-inn]').forEach(a => a.onclick = e => { e.preventDefault(); e.stopPropagation(); openCompany(a.dataset.inn); });
  const sel = rows.find(r => r.key === DY.sel);
  const cur = sel ? sel.months : d.total_months, prev = sel ? sel.prev_months : d.prev_total_months;
  $('#dyn-ct').innerHTML = `Ойлар кесимида <span class="hint">${sel ? esc(sel.key) : 'жами'} · ${d.year} (устун) ва ${d.year - 1} (чизиқ)</span>`;
  const rowSrc = rows.some(r => r.prev_source === 'customs');
  $('#dyn-note').textContent = `${rows.length} та қатор. Қаторни боссангиз график шу қатор бўйича чизилади. Манба: божхона базаси + кундалик ГТД, Бухоро қоидалари; мева-сабзавот фақат карантин рўйхати бўйича; йилнинг охирги ойи тўлиқ эмас (${dmy(d.to)} гача). `
    + `Ўтган йил: ${d.prev_source === 'settings' ? 'Созламалар базаси (кунга мутаносиб)' : 'божхона базаси'}${rowSrc ? `; тугунлар (тармоқ/давлат/уюшма/корхона қаторлари) — божхона базаси ${d.year - 1}` : ''}${d.prev_ytd_customs != null ? ` · божхона базаси бўйича ўтган йил шу давр: ${fmt(d.prev_ytd_customs)}` : ''}.`;
  if (CH.dyn) { CH.dyn.destroy(); CH.dyn = null; }
  CH.dyn = new Chart($('#c-dyn'), { data: { labels: MSHORT, datasets: [
      { type: 'bar', label: String(d.year), data: cur.map((v, i) => i < cm ? v : null), backgroundColor: C.aqua, borderRadius: 3, order: 2 },
      { type: 'line', label: String(d.year - 1), data: prev, borderColor: C.plan, backgroundColor: C.plan, borderDash: [5, 4], pointRadius: 2, tension: .25, order: 1 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: x => `${x.dataset.label}: ${fmt(x.raw)} минг $` } } },
      scales: { y: { beginAtZero: true, grid: { color: C.grid }, ticks: { callback: v => fmt0(v) } }, x: { grid: { display: false } } } } });
}

/* ---------------------------------------------------------------- Режа (прогноз) — Sozlamalar */
const PL = { data: null, grid: null, vid: null };
async function loadPlans(keep) {
  const d = await api('/api/plans'); PL.data = d;
  const sel = $('#pl-ver');
  sel.innerHTML = d.versions.map(v => `<option value="${v.id}">${v.year} · ${dmy(v.effective_from)} дан · ${esc(v.title || '')} · ${fmt(v.total / 1000)} млн$${d.effective && d.effective.id === v.id ? ' · амалда' : ''}</option>`).join('') || '<option value="">версия йўқ — «Яратиш» билан бошланг</option>';
  if (keep && d.versions.some(v => v.id === PL.vid)) sel.value = PL.vid; else PL.vid = d.versions.length ? (d.effective ? d.effective.id : d.versions[0].id) : null;
  if (PL.vid) sel.value = PL.vid;
  if (!$('#pl-ny').value) { $('#pl-ny').value = d.year; $('#pl-nfrom').value = `${d.year}-01-01`; }
  $('#pl-nsrc').querySelector('[value="workbook"]').disabled = !d.workbook_plan;
  $('#pl-nsrc').querySelector('[value="copy"]').disabled = !d.versions.length;
  if (!d.versions.length) $('#pl-nsrc').value = d.workbook_plan ? 'workbook' : 'empty';
  await loadPlanGrid();
}
async function loadPlanGrid() {
  const th = $('#t-plan thead'), tb = $('#t-plan tbody');
  if (!PL.vid) { th.innerHTML = ''; tb.innerHTML = '<tr><td class="muted">Режа версияси йўқ. Йил, сана ва манбани танлаб «Яратиш» ни босинг — жадвал (СВОД) прогнозидан ёки бўш.</td></tr>'; $('#pl-from').value = ''; $('#pl-title').value = ''; return; }
  const g = await api('/api/plans/grid?id=' + PL.vid); PL.grid = g;
  $('#pl-from').value = g.version.effective_from; $('#pl-title').value = g.version.title || '';
  th.innerHTML = `<tr><th>Туман</th><th>Тур</th>${MSHORT.map(m => `<th class="num">${m}</th>`).join('')}<th class="num">Йил жами</th></tr>`;
  let html = '', last = null;
  for (const r of g.rows) {
    html += `<tr class="${r.kind}" data-d="${r.district_code}" data-k="${r.kind}"><td>${r.district !== last ? esc(r.district) : ''}</td><td class="kd">${r.kind === 'sanoat' ? 'саноат' : 'мева-сабзавот'}</td>${r.months.map((v, i) => `<td class="num"><input data-m="${i}" value="${v ? fmt(v) : ''}"></td>`).join('')}<td class="num"><input class="y" value="${fmt(r.year)}"></td></tr>`;
    last = r.district;
  }
  html += `<tr class="sum"><td>Вилоят жами</td><td class="kd">саноат</td>${g.totals.sanoat.map(v => `<td class="num" data-t="s">${fmt(v)}</td>`).join('')}<td class="num" data-t="sy">${fmt(g.totals.sanoat.reduce((a, b) => a + b, 0))}</td></tr>`;
  html += `<tr class="sum"><td></td><td class="kd">мева-сабзавот</td>${g.totals.meva.map(v => `<td class="num" data-t="m">${fmt(v)}</td>`).join('')}<td class="num" data-t="my">${fmt(g.totals.meva.reduce((a, b) => a + b, 0))}</td></tr>`;
  tb.innerHTML = html;
  const num = s => { const v = parseFloat(String(s).replace(/\s/g, '').replace(',', '.')); return isNaN(v) ? 0 : v; };
  const recalc = () => {
    const tot = { sanoat: new Array(12).fill(0), meva: new Array(12).fill(0) };
    $$('#t-plan tbody tr[data-d]').forEach(tr => {
      const ins = [...tr.querySelectorAll('input[data-m]')]; let s = 0;
      ins.forEach((inp, i) => { const v = num(inp.value); s += v; tot[tr.dataset.k][i] += v; });
      tr.querySelector('input.y').value = fmt(s);
    });
    const cells = k => $$(`#t-plan tbody td[data-t="${k}"]`);
    cells('s').forEach((td, i) => td.textContent = fmt(tot.sanoat[i])); cells('m').forEach((td, i) => td.textContent = fmt(tot.meva[i]));
    $('#t-plan td[data-t="sy"]').textContent = fmt(tot.sanoat.reduce((a, b) => a + b, 0)); $('#t-plan td[data-t="my"]').textContent = fmt(tot.meva.reduce((a, b) => a + b, 0));
  };
  tb.addEventListener('change', e => {
    const inp = e.target; if (inp.tagName !== 'INPUT') return;
    if (inp.classList.contains('y')) {   // yillik → 12 oyga teng
      const v = num(inp.value); inp.closest('tr').querySelectorAll('input[data-m]').forEach(i => i.value = fmt(v / 12));
    }
    recalc();
  });
}
function planRows() {
  return $$('#t-plan tbody tr[data-d]').map(tr => ({ district_code: tr.dataset.d, kind: tr.dataset.k, months: [...tr.querySelectorAll('input[data-m]')].map(i => i.value.replace(/\s/g, '').replace(',', '.')) }));
}
function initPlans() {
  if (PL.inited) return; PL.inited = true;
  $('#pl-ver').onchange = () => { PL.vid = +$('#pl-ver').value || null; loadPlanGrid().catch(e => toast(e.message, true)); };
  $('#pl-save').onclick = async () => {
    if (!PL.vid) return toast('Аввал версия яратинг', true);
    try { await api('/api/plans/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: PL.vid, rows: planRows(), meta: { effective_from: $('#pl-from').value, title: $('#pl-title').value } }) }); toast('Режа сақланди'); S.dash = null; await loadPlans(true); } catch (e) { toast(e.message, true); }
  };
  $('#pl-del').onclick = async () => {
    if (!PL.vid || !confirm('Бу режа версияси ўчирилсинми?')) return;
    try { await api('/api/plans/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: PL.vid }) }); PL.vid = null; S.dash = null; await loadPlans(); } catch (e) { toast(e.message, true); }
  };
  $('#pl-new').onclick = async () => {
    const src = $('#pl-nsrc').value;
    try { const r = await api('/api/plans/create', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ year: +$('#pl-ny').value, effective_from: $('#pl-nfrom').value, copy_from: src === 'copy' ? PL.vid : null, from_workbook: src === 'workbook' }) });
      PL.vid = r.id; S.dash = null; await loadPlans(true); toast('Янги версия яратилди — ойларни тўлдириб «Сақлаш» ни босинг'); } catch (e) { toast(e.message, true); }
  };
  $('#pl-tpl').onclick = () => download('/api/plans/template?' + new URLSearchParams({ id: PL.vid || '', year: $('#pl-ny').value || '' }), `Режа шаблони.xlsx`);
  $('#pl-imp').onchange = async e => {
    const f = e.target.files[0]; if (!f) return; if (!PL.vid) return toast('Аввал версия яратинг', true);
    try { const r = await api('/api/plans/import', { method: 'POST', body: f, headers: { 'X-Id': String(PL.vid) } }); toast(`Юкланди: ${r.rows} қатор`); S.dash = null; await loadPlans(true); } catch (err) { toast(err.message, true); }
    e.target.value = '';
  };
}
/* ---------------------------------------------------------------- Ўтган йил базаси — Sozlamalar (prognoz.prev_year_base, қўлда) */
const PY = { data: null, inited: false };
const pyNum = s => { const v = parseFloat(String(s ?? '').replace(/[\s\u00a0]/g, '').replace(',', '.')); return isNaN(v) ? null : v; };
async function loadPrevYear(year) {
  const y = year || $('#py-year').value || (PL.data && PL.data.year) || new Date().getFullYear();
  const d = await api('/api/prev_year?year=' + y); PY.data = d;
  $('#py-year').value = d.year; $('#py-days').value = d.days || 273; $('#py-label').value = d.label || '';
  const tb = $('#t-prev tbody');
  tb.innerHTML = d.rows.map(r => `<tr class="${r.code === '1706' ? 'sum' : ''}" data-d="${r.code}"><td>${esc(r.name)}${r.code === '1706' ? ' <span class="hint">бўш = туманлар йиғиндиси</span>' : ''}</td>` +
    `<td class="num"><input data-k="sanoat" value="${r.sanoat != null ? fmt(r.sanoat, 3) : ''}"></td><td class="num"><input data-k="meva" value="${r.meva != null ? fmt(r.meva, 3) : ''}"></td><td class="tot" data-k="all">${r.all != null ? fmt(r.all, 3) : '—'}</td></tr>`).join('');
  pyRecalc();
}
function pyRecalc() {   // жами = саноат + мева; the region row shows the district sums while its own cells are blank
  const sum = { sanoat: 0, meva: 0 };
  $$('#t-prev tbody tr[data-d]').forEach(tr => {
    if (tr.dataset.d === '1706') return;
    const s = pyNum(tr.querySelector('[data-k="sanoat"]').value) || 0, m = pyNum(tr.querySelector('[data-k="meva"]').value) || 0;
    sum.sanoat += s; sum.meva += m; tr.querySelector('[data-k="all"]').textContent = fmt(s + m, 3);
  });
  const reg = $('#t-prev tbody tr[data-d="1706"]'); if (!reg) return;
  const rs = pyNum(reg.querySelector('[data-k="sanoat"]').value), rm = pyNum(reg.querySelector('[data-k="meva"]').value);
  reg.querySelector('[data-k="sanoat"]').placeholder = fmt(sum.sanoat, 3); reg.querySelector('[data-k="meva"]').placeholder = fmt(sum.meva, 3);
  reg.querySelector('[data-k="all"]').textContent = fmt((rs ?? sum.sanoat) + (rm ?? sum.meva), 3);
}
function initPrevYear() {
  if (PY.inited) return; PY.inited = true;
  $('#t-prev tbody').addEventListener('input', e => { if (e.target.tagName === 'INPUT') pyRecalc(); });
  $('#py-year').onchange = () => loadPrevYear(+$('#py-year').value).catch(e => toast(e.message, true));
  $('#py-save').onclick = async () => {
    const rows = $$('#t-prev tbody tr[data-d]').map(tr => ({ code: tr.dataset.d, sanoat: tr.querySelector('[data-k="sanoat"]').value.replace(/[\s\u00a0]/g, '').replace(',', '.'), meva: tr.querySelector('[data-k="meva"]').value.replace(/[\s\u00a0]/g, '').replace(',', '.') }));
    try {
      await api('/api/prev_year', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ year: +$('#py-year').value, days: +$('#py-days').value || 273, label: $('#py-label').value.trim(), rows }) });
      toast('Ўтган йил базаси сақланди'); S.dash = null; await loadPrevYear(+$('#py-year').value);
      $('#set-prev').textContent = $('#py-label').value.trim() ? 'Baza: ' + $('#py-label').value.trim() : '';
    } catch (e) { toast(e.message, true); }
  };
}
/* ---------------------------------------------------------------- Тугаган йиллар натижалари (N ойлик) — Sozlamalar (/api/periods) */
const PRD = { data: null, grid: null, inited: false };
const MGEN = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'];
const prLabel = (y, m) => m >= 12 ? `${y} йил якуни (12 ойлик)` : `${y} йил ${m} ойлик (январь–${MGEN[m - 1]})`;
const prY = () => +$('#pr-ny').value || 0;
const prM = () => +$('#pr-nm').value || 0;

async function loadPeriods(keep) {
  const d = await api('/api/periods'); PRD.data = d;
  const my = d.max_year || (d.year - 1), ysel = $('#pr-ny'), keepY = keep ? +ysel.value : 0;
  const years = []; for (let y = my; y >= my - 9; y--) years.push(y);
  ysel.innerHTML = years.map(y => `<option value="${y}">${y} йил</option>`).join('');
  ysel.value = String(years.includes(keepY) ? keepY : my);
  prFillMonths(keep);
  $('#pr-src').textContent = d.prev_source && d.prev_source.text
    ? `Ҳозир (${dmy(d.last_date)}): ${d.prev_source.text}.`
    : `Ҳозир (${dmy(d.last_date)}): тугаган йил натижаси киритилмаган — «Ўтган йил базаси» (кунга мутаносиб) ишлаяпти.`;
  await loadPeriodGrid();
}
function prFillMonths(keep) {
  const y = prY(), sel = $('#pr-nm'), keepM = keep ? +sel.value : 0;
  const have = {}; (PRD.data ? PRD.data.periods : []).filter(p => p.year === y).forEach(p => { have[p.months] = p; });
  sel.innerHTML = Array.from({ length: 12 }, (_, i) => {
    const m = i + 1, p = have[m];
    return `<option value="${m}">${m} ойлик (январь–${MGEN[i]})${p ? ` · ✓ ${fmt(p.totals.fact / 1000)} млн$` : ''}</option>`;
  }).join('');
  const lastM = parseInt((PRD.data && PRD.data.last_date || '').slice(5, 7)) || 1;
  sel.value = String(keepM >= 1 && keepM <= 12 ? keepM : Math.max(1, lastM - 1));
}
async function loadPeriodGrid() {
  const y = prY(), m = prM(), th = $('#t-per thead'), tb = $('#t-per tbody');
  if (!y || !m) { th.innerHTML = ''; tb.innerHTML = ''; return; }
  const g = await api(`/api/periods/grid?year=${y}&months=${m}`); PRD.grid = g;
  th.innerHTML = `<tr><th>Туман</th><th>Тур</th><th class="num">${prLabel(y, m)} — амалда, минг $</th><th class="num">Улуши %</th></tr>`;
  let html = '', last = null;
  for (const r of g.rows) {
    html += `<tr class="${r.kind}" data-d="${r.district_code}" data-k="${r.kind}"><td>${r.district !== last ? esc(r.district) : ''}</td>`
          + `<td class="kd">${r.kind === 'sanoat' ? 'саноат' : 'мева-сабзавот'}</td>`
          + `<td class="num"><input data-f="fact" value="${r.fact != null ? fmt(r.fact, 3) : ''}"></td><td class="num" data-c="sh"></td></tr>`;
    last = r.district;
  }
  for (const k of ['sanoat', 'meva', 'all'])
    html += `<tr class="sum" data-t="${k}"><td>${k === 'sanoat' ? 'Вилоят жами' : ''}</td><td class="kd">${k === 'sanoat' ? 'саноат' : k === 'meva' ? 'мева-сабзавот' : 'жами'}</td><td class="num" data-f="fact"></td><td class="num" data-c="sh"></td></tr>`;
  tb.innerHTML = html;
  prRecalc();
}
function prRecalc() {
  const tot = { sanoat: 0, meva: 0 };
  const rows = $$('#t-per tbody tr[data-d]');
  rows.forEach(tr => { tot[tr.dataset.k] += pyNum(tr.querySelector('[data-f="fact"]').value) || 0; });
  const all = tot.sanoat + tot.meva;
  rows.forEach(tr => {
    const v = pyNum(tr.querySelector('[data-f="fact"]').value);
    tr.querySelector('[data-c="sh"]').textContent = (v && all) ? fmt(v / all * 100) : '—';
  });
  for (const [k, t] of Object.entries({ ...tot, all })) {
    const tr = $(`#t-per tbody tr[data-t="${k}"]`); if (!tr) continue;
    tr.querySelector('[data-f="fact"]').textContent = fmt(t, 3);
    tr.querySelector('[data-c="sh"]').textContent = all ? fmt(t / all * 100) : '—';
  }
}
function periodRows() {
  const clean = v => v.replace(/[\s ]/g, '').replace(',', '.');
  return $$('#t-per tbody tr[data-d]').map(tr => ({ district_code: tr.dataset.d, kind: tr.dataset.k, fact: clean(tr.querySelector('[data-f="fact"]').value) }));
}
function initPeriods() {
  if (PRD.inited) return; PRD.inited = true;
  $('#t-per tbody').addEventListener('input', e => { if (e.target.tagName === 'INPUT') prRecalc(); });
  $('#pr-ny').onchange = () => { prFillMonths(false); loadPeriodGrid().catch(e => toast(e.message, true)); };
  $('#pr-nm').onchange = () => loadPeriodGrid().catch(e => toast(e.message, true));
  $('#pr-save').onclick = async () => {
    try {
      await api('/api/periods/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ year: prY(), months: prM(), rows: periodRows() }) });
      toast(`Сақланди: ${prLabel(prY(), prM())}`); S.dash = null; await loadPeriods(true);
    } catch (e) { toast(e.message, true); }
  };
  $('#pr-del').onclick = async () => {
    if (!confirm(`«${prLabel(prY(), prM())}» ўчирилсинми?`)) return;
    try {
      await api('/api/periods/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ year: prY(), months: prM() }) });
      S.dash = null; await loadPeriods(true);
    } catch (e) { toast(e.message, true); }
  };
  $('#pr-tpl').onclick = () => download(`/api/periods/template?year=${prY()}&months=${prM()}`, `${prY()} йил ${prM()} ойлик экспорт якуни.xlsx`);
  $('#pr-imp').onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    try {
      const r = await api('/api/periods/import', { method: 'POST', body: f, headers: { 'X-Year': String(prY()), 'X-Months': String(prM()), 'X-Filename': encodeURIComponent(f.name) } });
      toast(`Юкланди: ${r.rows} қатор («${r.sheet}» варағи · «${r.column}» устуни)` + (r.unknown && r.unknown.length ? ` · танилмаган: ${r.unknown.join(', ')}` : ''));
      S.dash = null; await loadPeriods(true);
    } catch (err) { toast(err.message, true); }
    e.target.value = '';
  };
}
/* ---------------------------------------------------------------- Баҳсли корхоналар — Sozlamalar (/api/disputes) */
const DISP_DEC = { template: ['Шаблон (қўлда)', 'info', 'Excel катаклари ўзгармайди — сайт шаблонни олди'],
  customs: ['Божхона базаси', 'ok', 'янв–база ойи катаклари база рақамлари билан қайта ёзилади'],
  not_bukhara: ['Бухоро эмас', 'bad', 'ой катаклари тозаланади + изоҳ'],
  add_row: ['Базада бор, шаблонда йўқ', 'warn', 'туман блокига сариқ янги қатор (база ойлари)'],
  unknown: ['Реестрда йўқ', 'bad', 'ҳеч нарса — Korxonalar менюсида қўшинг'] };
async function loadDisputes() {
  const d = await api('/api/disputes'); const tb = $('#t-disp tbody'); if (!tb) return;
  const mn = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
  if (!d.rows.length) { tb.innerHTML = `<tr><td colspan="10" class="empty">${d.base_month ? 'Баҳсли корхона йўқ — шаблон ва божхона базаси мос' : 'Божхона базаси юкланмаган'}</td></tr>`; return; }
  tb.innerHTML = d.rows.map(r => { const dc = DISP_DEC[r.decision] || DISP_DEC.unknown;
    const md = (r.months_diff || []).map((v, i) => Math.abs(v) >= 0.5 ? `${mn[i]} ${v > 0 ? '+' : ''}${fmt(v, 2)}` : '').filter(Boolean).join('; ');
    return `<tr><td>${r.registered ? `<a class="clink" href="#" data-inn="${esc(r.inn)}">${esc(r.name)}</a>` : esc(r.name)}<div class="hint mono">${esc(r.inn)}</div></td><td>${esc(r.district || '—')}</td>` +
      `<td>${r.in_template ? 'ҳа' : '<span class="muted">йўқ</span>'}</td><td>${r.in_base ? 'ҳа' : '<span class="muted">йўқ</span>'}</td>` +
      `<td class="num">${fmt(r.template_total, 2)}</td><td class="num">${fmt(r.base_total, 2)}</td><td class="num"><b class="${r.diff >= 0 ? 't-ok' : 't-bad'}">${r.diff > 0 ? '+' : ''}${fmt(r.diff, 2)}</b></td>` +
      `<td class="hint">${esc(md)}</td><td><span class="pill ${dc[1]}">${dc[0]}</span></td><td class="hint">${dc[2]}</td></tr>`; }).join('');
  tb.querySelectorAll('a[data-inn]').forEach(a => a.onclick = e => { e.preventDefault(); openCompany(a.dataset.inn); });
  const n = $('#disp-panel h2 .hint'); if (n) n.textContent = `${d.rows.length} та · шаблон ${d.template || ''} · база ${mn[d.base_month - 1] || ''} гача · қарор — корхона профилида`;
}
const _loadSet = loaders.set;
loaders.set = async () => { await _loadSet(); initPlans(); initPeriods(); initPrevYear(); await loadPlans(true).catch(e => toast(e.message, true)); await loadPeriods(true).catch(e => toast(e.message, true)); await loadPrevYear().catch(e => toast(e.message, true)); await loadDisputes().catch(e => toast(e.message, true)); };

/* ---------------------------------------------------------------- Ҳисоботлар: cardlar → Тармоқлар таҳлили */
const TA = { meta: null, data: null, ms: null, view: 'prod', open: new Set(), grp: null, seq: 0 };
function repShow(v) { $('#rep-home').hidden = v !== 'home'; $('#rep-ta').hidden = v !== 'ta'; $('#rep-rk').hidden = v !== 'rk'; $('#rep-mp').hidden = v !== 'mp'; window.scrollTo(0, 0); }
function taQuery() {
  const pt = $('#ta-ptype').value;
  const q = { cat: $('#ta-cat').value, year: $('#ta-year').value, ptype: pt, district: TA.ms ? TA.ms.value : '', title: $('#ta-title').value.trim() };
  if (pt === 'months') q.months = $('#ta-months').value;
  if (pt === 'range') { q.from = $('#ta-from').value; q.to = $('#ta-to').value; }
  return q;
}
async function taInit() {
  if (TA.meta) return;
  TA.meta = await api('/api/analysis/tarmoq/meta');
  const m = TA.meta;
  $('#ta-cat').innerHTML = m.categories.map(c => `<option value="${esc(c.id)}">${esc(c.label)}${c.hint ? ' — ' + esc(c.hint) : ''}</option>`).join('');
  $('#ta-year').innerHTML = m.years.map(y => `<option value="${y}">${y}</option>`).join(''); $('#ta-year').value = m.year;
  $('#ta-months').innerHTML = MONTHS.map((x, i) => `<option value="${i + 1}">${i + 1} ойлик (январь–${x.toLowerCase()})</option>`).join(''); $('#ta-months').value = m.default_months;
  $('#ta-from').value = m.year + '-01-01'; $('#ta-to').value = m.last_date || todayISO();
  TA.ms = multiSel('#ta-d', 'Барча туманлар', () => taLoad()); TA.ms.setOptions(m.districts.map(x => ({ v: x.code, t: x.name })));
  const re = () => taLoad();
  $('#ta-cat').onchange = re; $('#ta-year').onchange = re; $('#ta-months').onchange = re; $('#ta-from').onchange = re; $('#ta-to').onchange = re;
  $('#ta-ptype').onchange = () => { const t = $('#ta-ptype').value; $('#ta-months').hidden = t !== 'months'; $('#ta-range').hidden = t !== 'range'; taLoad(); };
  let tt; $('#ta-title').oninput = () => { clearTimeout(tt); tt = setTimeout(taLoad, 500); };
  $$('#ta-view button').forEach(b => b.onclick = () => { TA.view = b.dataset.v; $$('#ta-view button').forEach(x => x.classList.toggle('on', x === b)); taRender(); });
  $('#ta-back').onclick = () => repShow('home');
  $('#ta-xl').onclick = () => { const d = TA.data; download('/api/export/analysis/tarmoq?' + new URLSearchParams(taQuery()), `${d ? d.category : 'Тармоқ'} таҳлили ${d ? d.period.prev_year + '-' + d.period.year + ' ' + d.period.label : ''}.xlsx`.replace(/[\\/:*?"<>|«»]/g, '').replace(/\s+/g, ' ')); };
}
async function taLoad() {
  const seq = ++TA.seq;
  const d = await api('/api/analysis/tarmoq?' + new URLSearchParams(taQuery()));
  if (seq !== TA.seq) return;
  TA.data = d; TA.open.clear(); taRender();
}
function taRender() {
  const d = TA.data; if (!d) return;
  const p = d.period, py = p.prev_year, y = p.year;
  $('#ta-sub').textContent = `${d.category} · ${py}–${y} йиллар ${p.label}` + (p.partial ? ` (${y}: ${dmy(p.data_to)} ҳолатига)` : '');
  const gr = (a, b) => b - a, pc = (a, b) => a === 0 ? (b === 0 ? 0 : 100) : b / a * 100;
  const sgn = v => (v > 0 ? 'up' : v < 0 ? 'dn' : '');
  $('#ta-kpis').innerHTML = `<div class="kpi accent${TA.grp ? '' : ' on'}" data-g=""><div class="l">Жами · ${d.count} корхона</div><div class="v">${fmt(d.cur_v)}<small>минг $</small></div><div class="d">${py}: ${fmt(d.prev_v)} · <b class="${sgn(d.cur_v - d.prev_v)}">${d.cur_v - d.prev_v >= 0 ? '+' : ''}${fmt(d.cur_v - d.prev_v)} (${fmt(pc(d.prev_v, d.cur_v))}%)</b></div></div>` +
    d.groups.map(g => `<div class="kpi g-${g.key}${TA.grp === g.key ? ' on' : ''}" data-g="${g.key}"><div class="l">${g.roman}. ${esc(g.title.replace(' корхоналар', ''))}</div><div class="v">${g.count}<small>та</small></div><div class="d">${fmt(g.prev_v)} → ${fmt(g.cur_v)} · <b class="${sgn(g.cur_v - g.prev_v)}">${g.cur_v - g.prev_v >= 0 ? '+' : ''}${fmt(g.cur_v - g.prev_v)}</b></div></div>`).join('');
  $$('#ta-kpis .kpi').forEach(k => k.onclick = () => { TA.grp = k.dataset.g || null; taRender(); });
  $('#ta-h').innerHTML = esc(d.title.trim()).replace('\n', '<br><span class="hint">') + '</span>';
  $('#t-ta thead').innerHTML = `<tr><th rowspan="2">№</th><th rowspan="2">Корхона номи</th><th colspan="2">${py} йил ${esc(p.label)}</th><th colspan="2">${y} йил ${esc(p.label)}</th><th colspan="2">Ўсиш</th><th rowspan="2">Ҳолати</th></tr>
    <tr><th>Вазни (тонна)</th><th>Қиймати (минг долл)</th><th>Вазни (тонна)</th><th>Қиймати (минг долл)</th><th>Қийматда</th><th>Фоизда</th></tr>`;
  const nums = (o, cls = '') => `<td class="num">${fmt0(o.prev_n)}</td><td class="num">${fmt(o.prev_v)}</td><td class="num">${fmt0(o.cur_n)}</td><td class="num">${fmt(o.cur_v)}</td><td class="num gr ${cls}">${fmt(gr(o.prev_v, o.cur_v))}</td><td class="num gr ${cls}">${fmt0(pc(o.prev_v, o.cur_v))}</td>`;
  const rows = [`<tr class="tot"><td></td><td class="nm">ЖАМИ${TA.view === 'co' ? ` корхоналар (${d.count} та)` : ''}</td>${nums(d)}<td></td></tr>`];
  for (const g of d.groups) {
    if (TA.grp && TA.grp !== g.key) continue;
    rows.push(`<tr class="grp" data-g="${g.key}"><td>${g.roman}</td><td class="nm">${esc(g.title)} (${g.count} та)</td>${nums(g)}<td></td></tr>`);
    g.companies.forEach((c, i) => {
      const open = TA.view === 'prod' || TA.open.has(c.inn);
      rows.push(`<tr class="co gk-${g.key}${open ? ' open' : ''}" data-inn="${esc(c.inn)}"><td class="mono">${i + 1}</td><td class="nm"><span class="car">▸</span>${esc(c.name)}<span class="inn">${esc(c.inn)}</span>${c.district ? `<span class="ds">${esc(c.district)}</span>` : ''}</td>${nums(c)}<td class="st">${esc(c.status)}</td></tr>`);
      if (open) c.products.forEach(pr => rows.push(`<tr class="pr"><td></td><td class="nm">${esc(pr.name)}</td>${nums(pr)}<td></td></tr>`));
    });
  }
  $('#t-ta tbody').innerHTML = rows.join('');
  $$('#t-ta tr.co td.nm').forEach(td => td.onclick = e => {
    const inn = td.parentElement.dataset.inn;
    if (e.target.classList.contains('inn')) return openCompany(inn);
    if (TA.view === 'prod') return openCompany(inn);
    TA.open.has(inn) ? TA.open.delete(inn) : TA.open.add(inn); taRender();
  });
  $('#ta-note').textContent = `Манба: божхона базаси (${dmy(TA.meta.opening_through || '')} гача) + кунлик ГТД · «Тармоқ ва маҳсулот» саҳифаси қоидалари. Ўтган йил — божхона базасининг ${py} йил шу даври (${dmy(p.prev_from)}–${dmy(p.prev_to)}). ` +
    (TA.view === 'prod' ? 'Корхона номини боссангиз — паспорти очилади.' : 'Корхона номини боссангиз — маҳсулотлари очилади; ИНН ни боссангиз — паспорт.');
}
loaders.rep = async () => {
  repShow('home');
  $$('#rep-home [data-open]').forEach(b => b.onclick = async () => {
    try { repShow(b.dataset.open); if (b.dataset.open === 'ta') { await taInit(); await taLoad(); } if (b.dataset.open === 'rk') { await rkInit(); await rkLoad(); } if (b.dataset.open === 'mp') { await mpInit(); if (MP.data) mpRender(); } } catch (e) { toast(e.message, true); }
  });
};

/* ---- «Экспорт қилган корхоналар» — каттадан кичикка (корхона, тармоқ, туман, сумма) */
const RK = { meta: null, data: null, ms: null, t: 'all', seq: 0 };
function rkQuery() {
  return { m1: $('#rk-m1').value, m2: $('#rk-m2').value, t: RK.t, district: RK.ms ? RK.ms.value : '', memo: $('#rk-memo').checked ? '1' : '0', title: $('#rk-title').value.trim() };
}
async function rkInit() {
  if (RK.meta) return;
  RK.meta = await api('/api/analysis/reyting/meta');
  const m = RK.meta, opts = MONTHS.slice(0, m.month).map((x, i) => `<option value="${i + 1}">${x}</option>`).join('');
  $('#rk-m1').innerHTML = opts; $('#rk-m1').value = 1;
  $('#rk-m2').innerHTML = opts; $('#rk-m2').value = m.month;
  RK.ms = multiSel('#rk-d', 'Барча туманлар', () => rkLoad()); RK.ms.setOptions(m.districts.map(x => ({ v: x.code, t: x.name })));
  $('#rk-m1').onchange = () => { if (+$('#rk-m1').value > +$('#rk-m2').value) $('#rk-m2').value = $('#rk-m1').value; rkLoad(); };
  $('#rk-m2').onchange = () => { if (+$('#rk-m2').value < +$('#rk-m1').value) $('#rk-m1').value = $('#rk-m2').value; rkLoad(); };
  $('#rk-memo').onchange = () => rkLoad();
  $$('#rk-t button').forEach(b => b.onclick = () => { RK.t = b.dataset.t; $$('#rk-t button').forEach(x => x.classList.toggle('on', x === b)); rkLoad(); });
  let tt; $('#rk-title').oninput = () => { clearTimeout(tt); tt = setTimeout(rkLoad, 500); };
  $('#rk-q').oninput = () => rkRender();
  $('#rk-back').onclick = () => repShow('home');
  $('#rk-xl').onclick = () => { const d = RK.data; download('/api/export/analysis/reyting?' + new URLSearchParams(rkQuery()), `Экспорт қилган корхоналар ${d ? d.period.label : ''}.xlsx`.replace(/[\\/:*?"<>|«»]/g, '').replace(/\s+/g, ' ')); };
}
async function rkLoad() {
  const seq = ++RK.seq;
  const d = await api('/api/analysis/reyting?' + new URLSearchParams(rkQuery()));
  if (seq !== RK.seq) return;
  RK.data = d; rkRender();
}
function rkRender() {
  const d = RK.data; if (!d) return;
  const p = d.period;
  $('#rk-sub').textContent = `${p.label} · ${p.range}`;
  const top = d.rows.slice(0, 10).reduce((a, r) => a + r.value, 0);
  $('#rk-kpis').innerHTML = `<div class="kpi accent"><div class="l">Жами экспорт</div><div class="v">${fmt(d.total)}<small>минг $</small></div><div class="d">${p.partial ? dmy(p.last) + ' ҳолатига' : p.range} · Dashboard «Жами» билан бир хил</div></div>` +
    `<div class="kpi"><div class="l">Корхоналар (саноат)</div><div class="v">${d.count}<small>та</small></div><div class="d">${fmt(d.companies_total)} минг $ · каттадан кичикка</div></div>` +
    `<div class="kpi"><div class="l">Топ-10 улуши</div><div class="v">${fmt(d.total ? top / d.total * 100 : 0)}<small>%</small></div><div class="d">${fmt(top)} минг $</div></div>` +
    `<div class="kpi gold"><div class="l">Таркиби</div><div class="v" style="font-size:16px;line-height:1.5">саноат ${fmt(d.sanoat)}</div><div class="d">мева-сабзавот (карантин) ${fmt(d.meva)}${d.memo ? ' · алоҳида ҳисоб ' + fmt(d.memo_total) : ''}</div></div>`;
  $('#rk-h').textContent = d.title;
  const words = ($('#rk-q').value || '').toLowerCase().split(/\s+/).filter(Boolean);
  const hit = h => words.every(w => h.toLowerCase().includes(w));
  const rows = words.length ? d.rows.filter(r => hit(`${r.inn} ${r.name} ${r.full_name} ${r.tarmoq} ${r.district}`)) : d.rows;
  const mrows = words.length ? d.meva_rows.filter(r => hit(`мева-сабзавот ${r.district}`)) : d.meva_rows;
  const mx = Math.max(1e-9, ...d.rows.map(r => r.value), ...d.meva_rows.map(r => r.value));
  const bar = r => `<td><div class="hint" style="display:flex;align-items:center;gap:6px"><span style="flex:1;height:6px;border-radius:3px;background:var(--line);overflow:hidden"><span style="display:block;height:100%;width:${Math.max(1, r.value / mx * 100)}%;background:var(--accent)"></span></span>${fmt(r.share, 1)}%</div></td>`;
  const sec = (rm, name, v) => `<tr class="tot" style="opacity:.92"><td class="num">${rm}</td><td colspan="3"><b>${name}</b></td><td class="num"><b>${fmt(v)}</b></td><td></td></tr>`;
  const both = d.type === 'all';
  let html = `<tr class="tot"><td></td><td><b>ЖАМИ${d.type !== 'meva' ? ` (${d.count} та корхона${both && d.meva_rows.length ? ' + мева-сабзавот' : ''})` : ''}</b></td><td></td><td></td><td class="num"><b>${fmt(d.total)}</b></td><td></td></tr>`;
  if (d.type !== 'meva') {
    if (both) html += sec('I', `Саноат маҳсулотлари экспорт қилган корхоналар (${d.count} та)`, d.companies_total);
    html += rows.length ? rows.map(r => `<tr><td class="num mono">${r.no}</td><td><a class="clink" href="#" data-inn="${esc(r.inn)}">${esc(r.name)}</a>${r.separate ? ' <span class="pill">алоҳида ҳисоб</span>' : ''}<div class="hint mono">${esc(r.inn)}</div></td>` +
      `<td>${esc(r.tarmoq)}</td><td>${esc(r.district)}</td><td class="num"><b>${fmt(r.value)}</b></td>${bar(r)}</tr>`).join('') : `<tr><td colspan="6" class="empty">Корхона топилмади</td></tr>`;
  }
  if (d.type !== 'sanoat' && d.meva_rows.length) {
    if (both) html += sec('II', 'Мева-сабзавот маҳсулотлари (карантин рўйхати бўйича, туманлар кесимида)', d.meva);
    html += mrows.map(r => `<tr><td class="num mono">${r.no}</td><td>Мева-сабзавот экспорти</td><td>Мева-сабзавот</td><td>${esc(r.district)}</td><td class="num"><b>${fmt(r.value)}</b></td>${bar(r)}</tr>`).join('');
  }
  $('#t-rk tbody').innerHTML = html;
  $$('#t-rk a[data-inn]').forEach(a => a.onclick = e => { e.preventDefault(); openCompany(a.dataset.inn); });
  $('#rk-note').textContent = `Саноат — «Номма-ном» ҳисоби (божхона базаси + кунлик ГТД, «Бухоро эмас» киритилмайди). Мева-сабзавот — карантин қоидаси (Бухорода етиштирилган, экспортёрдан қатъи назар), Dashboard ва Свод билан бир хил; январь–август учун фақат туман жами маълум, шунинг учун туманлар кесимида. ` +
    (d.meva_note ? d.meva_note + '. ' : '') + (words.length ? `Қидирув фақат экранда, Excel — тўлиқ. ` : '') + 'Корхона номини боссангиз — паспорти очилади.';
}

/* ---- «Маҳсулотлар таҳлили» — тармоқлар + улар ичидаги маҳсулотлар (кўп танлов), тўпламлар */
const MP = { meta: null, cat: null, data: null, ms: null, dms: null, keys: new Set(), open: new Set(), tab: 'prod', seq: 0, set: '', chart: null };
function mpQuery(forXl) {
  const pt = $('#mp-ptype').value, s = mpSetObj();
  const q = { keys: JSON.stringify([...MP.keys]), cats: JSON.stringify(MP.ms ? MP.ms.list : []), year: $('#mp-year').value, ptype: pt,
    district: MP.dms ? MP.dms.value : '', memo: $('#mp-memo').checked ? '1' : '0', title: $('#mp-title').value.trim(), set_name: s && mpSetMatches(s) ? s.name : '' };
  if (pt === 'months') q.months = $('#mp-months').value;
  if (pt === 'range') { q.from = $('#mp-from').value; q.to = $('#mp-to').value; }
  return q;
}
const mpSetObj = () => (MP.cat ? MP.cat.sets : []).find(s => s.id === MP.set);
function mpSetMatches(s) {
  const a = [...MP.keys].sort().join('\n'), b = [...(s.keys || [])].sort().join('\n');
  const c1 = (MP.ms ? MP.ms.list : []).sort().join('\n'), c2 = [...(s.cats || [])].sort().join('\n');
  return a === b && c1 === c2;
}
async function mpInit() {
  if (MP.meta) return;
  MP.meta = await api('/api/analysis/mahsulot/meta');
  const m = MP.meta;
  $('#mp-year').innerHTML = m.years.map(y => `<option value="${y}">${y}</option>`).join(''); $('#mp-year').value = m.year;
  $('#mp-months').innerHTML = MONTHS.map((x, i) => `<option value="${i + 1}">${i + 1} ойлик (январь–${x.toLowerCase()})</option>`).join(''); $('#mp-months').value = m.default_months;
  $('#mp-from').value = m.year + '-01-01'; $('#mp-to').value = m.last_date || todayISO();
  MP.ms = multiSel('#mp-cat', 'Барча тармоқлар', () => { mpTree(); mpLoad(); });
  MP.dms = multiSel('#mp-d', 'Барча туманлар', () => mpLoad()); MP.dms.setOptions(m.districts.map(x => ({ v: x.code, t: x.name })));
  const re = () => mpLoad();
  $('#mp-ptype').onchange = () => { const t = $('#mp-ptype').value; $('#mp-months').hidden = t !== 'months'; $('#mp-range').hidden = t !== 'range'; mpLoad(); };
  $('#mp-months').onchange = re; $('#mp-from').onchange = re; $('#mp-to').onchange = re; $('#mp-memo').onchange = async () => { await mpCatalog(); mpLoad(); };
  $('#mp-year').onchange = async () => { await mpCatalog(); mpLoad(); };
  let tt; $('#mp-title').oninput = () => { clearTimeout(tt); tt = setTimeout(mpLoad, 500); };
  let tq; $('#mp-q').oninput = () => { clearTimeout(tq); tq = setTimeout(mpTree, 200); };
  $('#mp-onlysel').onchange = mpTree;
  $('#mp-clear').onclick = () => { MP.keys.clear(); MP.ms.clear(); MP.set = ''; $('#mp-set').value = ''; mpTree(); mpLoad(); };
  $('#mp-set').onchange = () => mpApplySet($('#mp-set').value);
  $('#mp-save').onclick = mpSaveSet; $('#mp-del').onclick = mpDelSet;
  $$('#mp-tabs button').forEach(b => b.onclick = () => { MP.tab = b.dataset.t; $$('#mp-tabs button').forEach(x => x.classList.toggle('on', x === b)); mpRender(); });
  $('#mp-back').onclick = () => repShow('home');
  $('#mp-xl').onclick = () => { if (!MP.data) return toast('Аввал маҳсулот танланг', true); const d = MP.data;
    download('/api/export/analysis/mahsulot?' + new URLSearchParams(mpQuery(true)), `${d.set_name} экспорт-импорт ${d.period.prev_year}-${d.period.year}.xlsx`.replace(/[\\/:*?"<>|«»]/g, '').replace(/\s+/g, ' ').slice(0, 150)); };
  await mpCatalog();
  const first = MP.cat.sets[0]; if (first) mpApplySet(first.id, true);
}
async function mpCatalog() {
  MP.cat = await api('/api/analysis/mahsulot/catalog?' + new URLSearchParams({ year: $('#mp-year').value, memo: $('#mp-memo').checked ? '1' : '0' }));
  MP.ms.setOptions(MP.cat.tree.map(t => ({ v: t.t1, t: `${t.t1} · ${fmt(t.cur)}` })));
  mpSets(); mpTree();
}
function mpSets() {
  $('#mp-set').innerHTML = `<option value="">— эркин танлов —</option>` + MP.cat.sets.map(s => `<option value="${esc(s.id)}">${esc(s.name)}${s.builtin ? ' (тайёр)' : ''}</option>`).join('');
  $('#mp-set').value = MP.set; $('#mp-del').disabled = !MP.set || !!(mpSetObj() || {}).builtin;
}
function mpApplySet(id, silent) {
  MP.set = id; const s = mpSetObj();
  MP.keys = new Set(s ? s.keys || [] : []); MP.ms.clear(); (s ? s.cats || [] : []).forEach(c => MP.ms.toggle(c));
  MP.open = new Set([...MP.keys].map(k => k.split('|')[0]));
  mpSets(); mpTree(); if (!silent || MP.keys.size) mpLoad();
}
async function mpSaveSet() {
  const cur = mpSetObj();
  const name = prompt('Тўплам номи (масалан: Паррандачилик, Қурилиш материаллари):', cur && !cur.builtin ? cur.name : '');
  if (!name) return;
  try {
    const r = await api('/api/analysis/mahsulot/set/save', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: cur && !cur.builtin && cur.name === name ? cur.id : '', name, keys: [...MP.keys], cats: MP.ms.list }) });
    MP.cat.sets = r.sets.map(s => MP.cat.sets.find(x => x.id === s.id && x.builtin) || s); MP.set = r.id; mpSets(); mpLoad(); toast('Тўплам сақланди: ' + name);
  } catch (e) { toast(e.message, true); }
}
async function mpDelSet() {
  const s = mpSetObj(); if (!s || s.builtin) return;
  if (!confirm(`«${s.name}» тўплами ўчирилсинми?`)) return;
  try { await api('/api/analysis/mahsulot/set/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: s.id }) });
    MP.cat.sets = MP.cat.sets.filter(x => x.id !== s.id); MP.set = ''; mpSets(); toast('Ўчирилди'); } catch (e) { toast(e.message, true); }
}
function mpTree() {
  if (!MP.cat) return;
  const cats = MP.ms.list, words = ($('#mp-q').value || '').toLowerCase().split(/\s+/).filter(Boolean), only = $('#mp-onlysel').checked;
  const hit = (t1, t2, it) => (!only || MP.keys.has(it.key)) && words.every(w => `${t1} ${t2} ${it.name} ${it.hs.join(' ')}`.toLowerCase().includes(w));
  const box = (on, part) => `<input type="checkbox"${on ? ' checked' : ''}${part ? ' data-part="1"' : ''}>`;
  const html = [];
  const selT1 = new Set([...MP.keys].map(k => k.split('|')[0]));
  const tree = [...MP.cat.tree].sort((a, b) => (selT1.has(b.t1) || cats.includes(b.t1)) - (selT1.has(a.t1) || cats.includes(a.t1)));
  html.push(`<div class="hint" style="text-align:right;padding:4px 0 2px">минг $: экспорт ${MP.cat.prev_year} йил жами → ${MP.cat.year} йил ${dmy(MP.cat.last_date)} гача · импорт (база ${dmy(MP.cat.import_last)} гача)</div>`);
  const vv = o => `<span class="v">эксп ${fmt(o.prev)} → ${fmt(o.cur)}${o.iprev || o.icur ? ` · <span style="color:var(--warn)">имп ${fmt(o.iprev)} → ${fmt(o.icur)}</span>` : ''}</span>`;
  const full = t1 => cats.includes(t1);          // тармоқ «Тармоқлар» рўйхатида тўлиқ танланган — ичидагилар ҳаммаси (келажакдаги янгилари ҳам)
  const boxF = (on, part, dis) => `<input type="checkbox"${on ? ' checked' : ''}${part ? ' data-part="1"' : ''}${dis ? ' disabled' : ''}>`;
  for (const t of tree) {
    const all = t.groups.flatMap(g => g.items.filter(it => hit(t.t1, g.t2, it)).map(it => [g.t2, it]));
    if (!all.length && !(only && full(t.t1))) continue;
    const F = full(t.t1), n = F ? all.length : all.filter(([, it]) => MP.keys.has(it.key)).length, open = words.length || only || MP.open.has(t.t1);
    html.push(`<div class="mp-t1" data-t1="${esc(t.t1)}"><div class="h"><span class="car">${open ? '▾' : '▸'}</span>${boxF(F || (n && n === all.length), !F && n && n < all.length)}<span>${esc(t.t1)}</span>${F ? `<span class="pill" style="background:var(--accent-soft);color:var(--accent)">тармоқ тўлиқ</span>` : n ? `<span class="pill" style="background:var(--accent-soft);color:var(--accent)">${n} танланган</span>` : ''}${vv(t)}</div>`);
    if (open) for (const g of t.groups) {
      const its = g.items.filter(it => hit(t.t1, g.t2, it)); if (!its.length) continue;
      const gn = F ? its.length : its.filter(it => MP.keys.has(it.key)).length;
      html.push(`<div class="mp-t2" data-t2="${esc(g.t2)}"><div class="h">${boxF(gn && gn === its.length, gn && gn < its.length, F)}<span>${esc(g.t2)}</span>${vv(g)}</div>` +
        its.map(it => `<label class="mp-it" data-k="${esc(it.key)}">${boxF(F || MP.keys.has(it.key), false, F)}<span>${esc(it.name)} <span class="hs">${esc(it.hs.join(', '))} · ${it.companies} корх.${it.icompanies ? ' · имп ' + it.icompanies : ''}</span></span>${vv(it)}</label>`).join('') + `</div>`);
    }
    html.push('</div>');
  }
  $('#mp-tree').innerHTML = html.length > 1 ? html.join('') : `<div class="empty">Топилмади</div>`;
  $$('#mp-tree input[data-part]').forEach(i => i.indeterminate = true);
  const t1items = t1 => { const t = MP.cat.tree.find(x => x.t1 === t1); return t ? t.groups.flatMap(g => g.items.filter(it => hit(t1, g.t2, it)).map(it => it.key)) : []; };
  $$('#mp-tree .mp-t1>.h').forEach(h => h.onclick = e => {
    const t1 = h.parentElement.dataset.t1;
    if (e.target.tagName === 'INPUT') {
      if (full(t1)) { MP.ms.toggle(t1); mpChanged(); return; }                       // тўлиқ танловни бекор қилиш
      const ks = t1items(t1), on = e.target.checked;
      if (on && !words.length) { ks.forEach(k => MP.keys.delete(k)); MP.ms.toggle(t1); }   // қидирувсиз бутун тармоқ — «Тармоқлар» рўйхатига (келажакдаги маҳсулотлари ҳам киради)
      else ks.forEach(k => on ? MP.keys.add(k) : MP.keys.delete(k));
      MP.open.add(t1); mpChanged(); return;
    }
    MP.open.has(t1) ? MP.open.delete(t1) : MP.open.add(t1); mpTree();
  });
  $$('#mp-tree .mp-t2>.h').forEach(h => h.onclick = e => {
    const t1 = h.closest('.mp-t1').dataset.t1, t2 = h.parentElement.dataset.t2;
    if (full(t1)) { toast('Бу тармоқ «Тармоқлар» рўйхатида тўлиқ танланган — алоҳида маҳсулот танлаш учун аввал уни рўйхатдан чиқаринг'); mpTree(); return; }
    const t = MP.cat.tree.find(x => x.t1 === t1), g = t.groups.find(x => x.t2 === t2);
    const ks = g.items.filter(it => hit(t1, t2, it)).map(it => it.key);
    const on = e.target.tagName === 'INPUT' ? e.target.checked : !ks.every(k => MP.keys.has(k));
    ks.forEach(k => on ? MP.keys.add(k) : MP.keys.delete(k)); mpChanged();
  });
  $$('#mp-tree .mp-it input').forEach(i => i.onchange = () => { const k = i.closest('.mp-it').dataset.k; i.checked ? MP.keys.add(k) : MP.keys.delete(k); mpChanged(); });
  const allKeys = new Set(MP.cat.tree.flatMap(t => t.groups.flatMap(g => g.items.map(it => it.key))));
  const miss = [...MP.keys].filter(k => !allKeys.has(k)).length;
  $('#mp-selinfo').textContent = `· ${MP.keys.size} та маҳсулот танланган` + (cats.length ? ` + ${cats.length} та тармоқ тўлиқ` : '') +
    (miss ? ` · ${miss} та маҳсулот каталогда йўқ (номи ўзгарган ёки бу йилларда экспорт/импорт йўқ)` : '') + ' · тармоқ ёки гуруҳ номидаги белги — ичидагиларнинг ҳаммаси';
}
let mpT;
function mpChanged() { const s = mpSetObj(); if (s && !mpSetMatches(s)) { MP.set = ''; mpSets(); } mpTree(); clearTimeout(mpT); mpT = setTimeout(mpLoad, 350); }
async function mpLoad() {
  const q = mpQuery(); const seq = ++MP.seq;
  if (q.keys === '[]' && q.cats === '[]') { MP.data = null; mpRender(); return; }
  try { const d = await api('/api/analysis/mahsulot?' + new URLSearchParams(q)); if (seq !== MP.seq) return; MP.data = d; mpRender(); }
  catch (e) { if (seq === MP.seq) toast(e.message, true); }
}
function mpRender() {
  const d = MP.data;
  if (d && !d.imp) { toast('Сайт эски код билан ишлаяпти — Ishga_tushirish.bat орқали қайта ишга туширинг', true); d.imp = { period: { label: '—', data_to: '' }, title: '', count: 0, groups: {}, prev_v: 0, cur_v: 0, prev_n: 0, cur_n: 0, cur_companies: 0, prev_companies: 0, products: [], companies: [], districts: [], countries: [], months: [] }; }
  if (d && d.region_cur_v === undefined) { d.region_cur_v = 0; d.region_prev_v = 0; }
  if (!d) { $('#mp-kpis').innerHTML = ''; $('#mp-h').textContent = 'Тармоқ ёки маҳсулот танланг'; $('#t-mp thead').innerHTML = ''; $('#t-mp tbody').innerHTML = ''; $('#mp-note').textContent = ''; $('#mp-chart-w').hidden = true; $('#mp-sub').textContent = ''; return; }
  const p = d.period, py = p.prev_year, y = p.year;
  const gr = (a, b) => b - a, pc = (a, b) => a === 0 ? null : (b / a - 1) * 100, sgn = v => (v > 0 ? 'up' : v < 0 ? 'dn' : '');
  const pcs = (a, b) => { const v = pc(a, b); return v === null ? (b ? 'янги' : '—') : (v > 0 ? '+' : '') + fmt(v) + '%'; };
  $('#mp-sub').textContent = `${d.set_name} · ${py}–${y} йиллар ${p.label}` + (p.partial ? ` (${y}: ${dmy(p.data_to)} ҳолатига)` : '');
  const g = d.groups;
  $('#mp-kpis').innerHTML = `<div class="kpi accent"><div class="l">Экспорт · ${y}</div><div class="v">${fmt(d.cur_v)}<small>минг $</small></div><div class="d">${py}: ${fmt(d.prev_v)} · <b class="${sgn(d.cur_v - d.prev_v)}">${d.cur_v - d.prev_v >= 0 ? '+' : ''}${fmt(d.cur_v - d.prev_v)} (${pcs(d.prev_v, d.cur_v)})</b></div></div>` +
    `<div class="kpi"><div class="l">Вилоят экспортидаги улуши</div><div class="v">${d.region_cur_v ? fmt(d.cur_v / d.region_cur_v * 100, 2) : '—'}<small>%</small></div><div class="d">${py}: ${d.region_prev_v ? fmt(d.prev_v / d.region_prev_v * 100, 2) + '%' : '—'} · вазни ${fmt(d.cur_n)} т (${py}: ${fmt(d.prev_n)} т)</div></div>` +
    `<div class="kpi"><div class="l">Корхоналар</div><div class="v">${d.cur_companies}<small>та</small></div><div class="d">${py}: ${d.prev_companies} · янги ${g.new || 0} · тўхтаган ${g.stop || 0}</div></div>` +
    `<div class="kpi gold" data-imp="1" style="cursor:pointer"><div class="l">Импорт · ${y} (${esc(d.imp.period.label)})</div><div class="v">${fmt(d.imp.cur_v)}<small>минг $</small></div><div class="d">${py}: ${fmt(d.imp.prev_v)} · <b class="${sgn(d.imp.cur_v - d.imp.prev_v)}">${pcs(d.imp.prev_v, d.imp.cur_v)}</b> · ${d.imp.cur_companies} корхона</div></div>`;
  $$('#mp-kpis [data-imp]').forEach(k => k.onclick = () => $('#mp-tabs button[data-t=imp]').click());
  const ttl = MP.tab === 'imp' ? d.imp.title : d.title;
  $('#mp-h').innerHTML = esc(ttl.trim()).replace('\n', '<br><span class="hint">') + '</span>';
  const H = (lead, extra = '') => `<tr><th rowspan="2">№</th>${lead}<th colspan="2">${py} йил ${esc(p.label)}</th><th colspan="2">${y} йил ${esc(p.label)}</th><th colspan="2">Ўсиш</th>${extra}</tr><tr><th>Вазни (т)</th><th>Қиймати</th><th>Вазни (т)</th><th>Қиймати</th><th>Қийматда</th><th>Фоизда</th></tr>`;
  const nums = o => `<td class="num">${fmt(o.prev_n)}</td><td class="num">${fmt(o.prev_v)}</td><td class="num">${fmt(o.cur_n)}</td><td class="num"><b>${fmt(o.cur_v)}</b></td><td class="num gr ${sgn(gr(o.prev_v, o.cur_v))}">${fmt(gr(o.prev_v, o.cur_v))}</td><td class="num gr ${sgn(gr(o.prev_v, o.cur_v))}">${pcs(o.prev_v, o.cur_v)}</td>`;
  const sh = v => `<td class="num">${d.cur_v ? fmt(v / d.cur_v * 100) + '%' : '—'}</td>`;
  let head = '', rows = [];
  $('#mp-chart-w').hidden = MP.tab !== 'mon';
  if (MP.tab === 'prod') {
    head = H('<th rowspan="2">Тармоқ</th><th rowspan="2">Маҳсулот</th><th rowspan="2">ТН ВЭД</th>', '<th rowspan="2">Корхоналар</th><th rowspan="2">Улуши</th>');
    rows.push(`<tr class="tot"><td></td><td class="nm" colspan="3">ЖАМИ (${d.products.length} та маҳсулот)</td>${nums(d)}<td class="num">${d.prev_companies} → ${d.cur_companies}</td><td class="num">100%</td></tr>`);
    d.products.forEach((x, i) => rows.push(`<tr><td class="mono">${i + 1}</td><td class="hint">${esc(x.t1)}</td><td>${esc(x.name)}</td><td class="mono hint">${esc(x.hs)}</td>${nums(x)}<td class="num">${x.prev_c} → ${x.cur_c}</td>${sh(x.cur_v)}</tr>`));
  } else if (MP.tab === 'co') {
    head = H('<th rowspan="2">Корхона номи</th><th rowspan="2">Туман</th>', '<th rowspan="2">Ҳолати</th><th rowspan="2">Давлатлар</th><th rowspan="2">Улуши</th>');
    rows.push(`<tr class="tot"><td></td><td class="nm" colspan="2">ЖАМИ (${d.count} та корхона)</td>${nums(d)}<td colspan="2"></td><td class="num">100%</td></tr>`);
    d.companies.forEach(c => {
      rows.push(`<tr class="co${MP.open.has('c' + c.inn) ? ' open' : ''}" data-inn="${esc(c.inn)}"><td class="mono">${c.no}</td><td class="nm"><span class="car">▸</span>${esc(c.name)}<span class="inn">${esc(c.inn)}</span></td><td>${esc(c.district)}</td>${nums(c)}<td class="st ${c.group}">${esc(c.status)}</td><td class="hint">${esc(c.countries.join(', '))}</td>${sh(c.cur_v)}</tr>`);
      if (MP.open.has('c' + c.inn)) c.products.forEach(pr => rows.push(`<tr class="pr"><td></td><td class="nm">${esc(pr.name)}</td><td></td>${nums(pr)}<td colspan="3"></td></tr>`));
    });
  } else if (MP.tab === 'dist' || MP.tab === 'ctry') {
    const lst = MP.tab === 'dist' ? d.districts : d.countries;
    head = H(`<th rowspan="2">${MP.tab === 'dist' ? 'Туман' : 'Давлат'}</th>`, '<th rowspan="2">Корхоналар</th><th rowspan="2">Улуши</th>');
    rows.push(`<tr class="tot"><td></td><td class="nm">ЖАМИ</td>${nums(d)}<td></td><td class="num">100%</td></tr>`);
    lst.forEach((x, i) => rows.push(`<tr><td class="mono">${i + 1}</td><td>${esc(x.name)}</td>${nums(x)}<td class="num">${x.prev_c} → ${x.cur_c}</td>${sh(x.cur_v)}</tr>`));
  } else if (MP.tab === 'imp') {
    const im = d.imp, ip = im.period, shi = v => `<td class="num">${im.cur_v ? fmt(v / im.cur_v * 100) + '%' : '—'}</td>`;
    head = `<tr><th rowspan="2">№</th><th rowspan="2">Номи</th><th rowspan="2">Тармоқ / туман</th><th colspan="2">${py} йил ${esc(ip.label)}</th><th colspan="2">${y} йил ${esc(ip.label)}</th><th colspan="2">Ўсиш</th><th rowspan="2">Корхоналар / давлатлар</th><th rowspan="2">Улуши</th></tr><tr><th>Вазни (т)</th><th>Қиймати</th><th>Вазни (т)</th><th>Қиймати</th><th>Қийматда</th><th>Фоизда</th></tr>`;
    const blk = (lbl) => `<tr class="grp"><td></td><td class="nm" colspan="2">${lbl}</td>${nums(im)}<td></td><td class="num">100%</td></tr>`;
    rows.push(`<tr class="tot"><td></td><td class="nm" colspan="2">ЖАМИ ИМПОРТ (${im.count} та корхона)</td>${nums(im)}<td></td><td class="num">100%</td></tr>`);
    if (!im.products.length) rows.push(`<tr><td colspan="11" class="empty">Танланган маҳсулотлар бўйича импорт йўқ</td></tr>`);
    else {
      rows.push(blk(`I. Маҳсулотлар бўйича (${im.products.length} та)`));
      im.products.forEach((x, i) => rows.push(`<tr><td class="mono">${i + 1}</td><td>${esc(x.name)} <span class="hint mono">${esc(x.hs)}</span></td><td class="hint">${esc(x.t1)}</td>${nums(x)}<td class="num">${x.prev_c} → ${x.cur_c} корх.</td>${shi(x.cur_v)}</tr>`));
      rows.push(blk(`II. Корхоналар бўйича (${im.count} та)`));
      im.companies.forEach(c => rows.push(`<tr><td class="mono">${c.no}</td><td><a class="clink" href="#" data-inn="${esc(c.inn)}">${esc(c.name)}</a> <span class="hint">— ${esc(c.products.map(p => p.name).join(', '))}</span></td><td>${esc(c.district)}</td>${nums(c)}<td class="hint">${esc(c.countries.join(', '))}</td>${shi(c.cur_v)}</tr>`));
      rows.push(blk(`III. Давлатлар бўйича (${im.countries.length} та)`));
      im.countries.forEach((x, i) => rows.push(`<tr><td class="mono">${i + 1}</td><td>${esc(x.name)}</td><td></td>${nums(x)}<td class="num">${x.prev_c} → ${x.cur_c} корх.</td>${shi(x.cur_v)}</tr>`));
    }
  } else {
    head = `<tr><th>№</th><th>Ой</th><th>${py} йил</th><th>${y} йил</th><th>Ўсиш</th><th>Фоизда</th></tr>`;
    rows.push(`<tr class="tot"><td></td><td class="nm">ЖАМИ</td><td class="num">${fmt(d.prev_v)}</td><td class="num">${fmt(d.cur_v)}</td><td class="num">${fmt(d.cur_v - d.prev_v)}</td><td class="num">${pcs(d.prev_v, d.cur_v)}</td></tr>`);
    d.months.forEach((m, i) => rows.push(`<tr><td class="mono">${i + 1}</td><td>${m.name}</td><td class="num">${fmt(m.prev_v)}</td><td class="num">${fmt(m.cur_v || 0)}</td><td class="num gr ${sgn((m.cur_v || 0) - m.prev_v)}">${fmt((m.cur_v || 0) - m.prev_v)}</td><td class="num">${pcs(m.prev_v, m.cur_v || 0)}</td></tr>`));
    const cd = { labels: d.months.map(m => m.name), datasets: [{ label: String(py), data: d.months.map(m => +m.prev_v.toFixed(1)), backgroundColor: '#B8C4BF' }, { label: String(y), data: d.months.map(m => +(m.cur_v || 0).toFixed(1)), backgroundColor: '#0F6E63' }] };
    const co = { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' } }, scales: { y: { beginAtZero: true } } };
    if (MP.chart) { MP.chart.data = cd; MP.chart.update(); } else MP.chart = new Chart($('#c-mp'), { type: 'bar', data: cd, options: co });
  }
  $('#t-mp thead').innerHTML = head; $('#t-mp tbody').innerHTML = rows.join('');
  $$('#t-mp a[data-inn]').forEach(a => a.onclick = e => { e.preventDefault(); openCompany(a.dataset.inn); });
  $$('#t-mp tr.co td.nm').forEach(td => td.onclick = e => { const inn = td.parentElement.dataset.inn; if (e.target.classList.contains('inn')) return openCompany(inn); const k = 'c' + inn; MP.open.has(k) ? MP.open.delete(k) : MP.open.add(k); mpRender(); });
  $('#mp-note').textContent = `Манба: божхона базаси (${dmy(MP.meta.opening_through || '')} гача) + кунлик ГТД · «Тармоқ ва маҳсулот» саҳифаси қоидалари («Бухоро эмас» ва Бухоро даври ҳисобга олинган; мева-сабзавот — фақат саноат ҳисобидаги қаторлар). Ўтган йил — божхона базасининг ${py} йил шу даври (${dmy(p.prev_from)}–${dmy(p.prev_to)}). ` +
    (MP.tab === 'co' ? 'Корхона номини боссангиз — маҳсулотлари очилади; ИНН ни боссангиз — паспорт.' : '') +
    (MP.tab === 'imp' ? ` Импорт — фақат божхона базаси (${dmy(d.imp.period.data_to)} гача, кунлик ГТД да импорт йўқ), ўтган йил — шу кунлар; ҳар бир бўлим жами импортга тенг.` : '');
}

// ---- «Свод (карантин) + туманлар номма-ном» — юклашдан олдинги танловлар (3 қисм)
async function openSvnModal(D) {
  const o = await api('/api/export/svod_options?date=' + D);
  let st = { prev: 'same_day', meva: 'karantin', settings: false, sp: null };
  try { Object.assign(st, JSON.parse(localStorage.getItem('svnOpts') || '{}')); } catch (_) {}
  if (!o.settings.available) st.settings = false;
  const SP = o.settings.periods || [];                 // Sozlamalar → Тугаган йиллар натижалари (ўтган йил, N ойлик)
  if (st.sp !== 'auto' && !SP.find(p => p.months == st.sp)) st.sp = SP.length ? o.settings.default_months : 'auto';
  const spSel = () => SP.find(p => p.months == st.sp);
  const sv = () => { const p = spSel(); return p ? { sanoat: p.sanoat, meva: p.meva } : { sanoat: o.settings.sanoat, meva: o.settings.meva }; };
  const per = o.periods;
  if (!per.find(p => p.mode === st.prev && !p.disabled)) st.prev = (per.find(p => !p.disabled) || {}).mode || 'same_day';
  const asof = dmy(o.as_of);
  const pm = p => st.meva === 'exporter' ? p.meva.exporter : p.meva.karantin;
  const draw = () => {
    const P = per.find(p => p.mode === st.prev) || {};
    const meva = st.settings ? 'karantin' : st.meva;
    const curM = meva === 'exporter' ? o.current.meva.exporter : o.current.meva.karantin;
    const opt = (name, val, on, dis, title, body) => `<label class="svn-opt${on ? ' on' : ''}${dis ? ' dis' : ''}"><input type="radio" name="${name}" value="${val}"${on ? ' checked' : ''}${dis ? ' disabled' : ''}><div><div class="t">${title}</div>${body}</div></label>`;
    const S = sv();
    const prevLine = st.settings
      ? `ўтган йил: <b>Sozlamalar${spSel() ? ' — ' + esc(spSel().label) : ''}</b> — саноат ${fmt(S.sanoat)}, мева-сабзавот ${fmt(S.meva)}, жами ${fmt(S.sanoat + S.meva)} минг $`
      : `ўтган йил: <b>${esc(P.label || '—')}</b> — саноат ${fmt(P.sanoat)}, мева-сабзавот ${fmt(P.meva ? pm(P) : null)}, жами ${fmt((P.sanoat || 0) + (P.meva ? pm(P) : 0))} минг $`;
    $('#svn-body').innerHTML = `<button class="x" id="svn-x">×</button><div class="svn">
      <h2 id="svn-title">«${asof}» свод + туманлар номма-ном — Excel</h2>
      <p class="lead">Жорий йил (1.01–${dmy(D).slice(0, 5)}): саноат <b>${fmt(o.current.sanoat)}</b> · мева-сабзавот <b>${fmt(curM)}</b> · жами <b>${fmt(o.current.sanoat + curM)}</b> минг $. СВОД варағида туман ва вилоят жамилари, фарқ ва фоизлар — формула.</p>
      <div class="svn-sec${st.settings ? ' off' : ''}"><h4>1 · Ўтган йил билан солиштириш даври — божхона базасидан</h4>
        ${per.map(p => opt('svn-prev', p.mode, p.mode === st.prev, p.disabled || st.settings,
          esc(p.label) + (p.mode === 'month_back' ? ' <span class="pill info">1 ой орқа</span>' : p.mode === 'same_day' ? ' <span class="pill info">шу кунга мос давр</span>' : ' <span class="pill info">шу ой тўлгани</span>'),
          p.disabled ? '<div class="n">январь ойида олдинги ой йўқ</div>' : `<div class="v">саноат <b>${fmt(p.sanoat)}</b> · мева-сабзавот <b>${fmt(pm(p))}</b> · жами <b>${fmt(p.sanoat + pm(p))}</b> минг $</div>`)).join('')}
      </div>
      <div class="svn-sec${st.settings ? ' off' : ''}"><h4>2 · Мева-сабзавот қоидаси (жорий ва ўтган йил)</h4>
        ${opt('svn-meva', 'karantin', meva === 'karantin', st.settings, 'Карантин рўйхати — Бухорода етиштирилган',
          `<div class="v">жорий йил <b>${fmt(o.current.meva.karantin)}</b> · ўтган йил${P.meva ? ` <b>${fmt(P.meva.karantin)}</b>` : ' —'} минг $</div><div class="n">экспортёр қайси вилоятдан бўлишидан қатъи назар; туман — етиштирилган жой.${P.meva ? ' Ўтган йил: ' + esc(P.meva.karantin_note) + ' (божхона базасида етиштирилган жой устуни йўқ).' : ''}</div>`)}
        ${opt('svn-meva', 'exporter', meva === 'exporter', st.settings, 'Бухоро корхоналари экспорт қилган мева-сабзавот',
          `<div class="v">жорий йил <b>${fmt(o.current.meva.exporter)}</b> · ўтган йил${P.meva ? ` <b>${fmt(P.meva.exporter)}</b>` : ' —'} минг $</div><div class="n">маҳсулот қаерда етиштирилганидан қатъи назар; туман — корхона жойлашган туман.</div>`)}
      </div>
      <div class="svn-sec"><h4>3 · «Sozlamalar»да киритилган ўтган йил кўрсаткичи</h4>
        <label class="svn-opt${st.settings ? ' on' : ''}${o.settings.available ? '' : ' dis'}"><input type="checkbox" id="svn-set"${st.settings ? ' checked' : ''}${o.settings.available ? '' : ' disabled'}><div>
          <div class="t">Ўтган йилни «Sozlamalar»даги рақамдан олиш</div>
          ${o.settings.available ? `<div class="v">саноат <b>${fmt(S.sanoat)}</b> · мева-сабзавот <b>${fmt(S.meva)}</b> · жами <b>${fmt(S.sanoat + S.meva)}</b> минг $</div><div class="n">${spSel() ? 'Тугаган йиллар натижалари: «' + esc(spSel().label) + '» — аниқ рақам, туман ва тур кесимида, интерполяциясиз' : esc(o.settings.text)}. Белгиланса 1 ва 2 қисм ўчади, мева-сабзавот — карантин рўйхати.</div>` : '<div class="n">«Sozlamalar»да ўтган йил натижаси киритилмаган.</div>'}</div></label>
        ${st.settings && SP.length ? `<div class="form-row" style="margin-top:8px;align-items:center;gap:8px"><span class="n">Давр:</span><select id="svn-sp">${SP.map(p => `<option value="${p.months}"${p.months == st.sp ? ' selected' : ''}>${esc(p.label)} — саноат ${fmt(p.sanoat)} · мева ${fmt(p.meva)} · жами ${fmt(p.sanoat + p.meva)}</option>`).join('')}<option value="auto"${st.sp === 'auto' ? ' selected' : ''}>Шу кунга мутаносиб (интерполяция) — саноат ${fmt(o.settings.sanoat)} · мева ${fmt(o.settings.meva)}</option></select></div>` : ''}
      </div>
      <div class="svn-sum">${prevLine}; мева-сабзавот — <b>${meva === 'exporter' ? 'Бухоро корхоналари экспорти' : 'карантин рўйхати'}</b>.</div>
      <div class="form-row" style="justify-content:flex-end"><button class="btn" id="svn-cancel">Бекор</button><button class="btn primary" id="svn-go">📗 Excel юклаб олиш</button></div></div>`;
    $('#svn-x').onclick = $('#svn-cancel').onclick = closeModals;
    $$('#svn-body input[name=svn-prev]').forEach(i => i.onchange = () => { st.prev = i.value; draw(); });
    $$('#svn-body input[name=svn-meva]').forEach(i => i.onchange = () => { st.meva = i.value; draw(); });
    const cb = $('#svn-set'); if (cb) cb.onchange = () => { st.settings = cb.checked; draw(); };
    const sps = $('#svn-sp'); if (sps) sps.onchange = () => { st.sp = sps.value === 'auto' ? 'auto' : Number(sps.value); draw(); };
    $('#svn-go').onclick = () => {
      try { localStorage.setItem('svnOpts', JSON.stringify(st)); } catch (_) {}
      const prev = st.settings ? 'settings' : st.prev, mv = st.settings ? 'karantin' : st.meva;
      closeModals();
      const sp = st.settings && st.sp && st.sp !== 'auto' ? `&sp=${st.sp}` : '';
      download(`/api/export/svod_nomma?date=${D}&prev=${prev}&meva=${mv}${sp}`, `${dmy(isoNext(D))} свод ва туманлар номма-ном.xlsx`);
    };
  };
  draw(); $('#svn-modal').hidden = false;
}
