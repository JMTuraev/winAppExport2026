"use strict";
/* Хатлар — bo'lim xatlari reyestri: menyu sahifasi, xat kartasi oynasi, tahrir, «+ Хат қўшиш», korxona profili tabi.
   Backend: appwin/xatlar.py (/api/xatlar/*). app.js dagi $, $$, api, esc, dmy, toast, go, loaders, R, showProfile, renderProfTab ishlatiladi. */
(function () {
  const XS = { q: '', kinds: new Set(), scope: '', year: '', district: '', sector: '', country: '', chk: false, att: false, arch: false,
               offset: 0, items: [], total: 0, facets: null, canWrite: false, built: false, timer: null, cur: null, tab: 'sum' };
  const CYR = { а:'a',б:'b',в:'v',г:'g',д:'d',е:'e',ё:'yo',ж:'j',з:'z',и:'i',й:'y',к:'k',л:'l',м:'m',н:'n',о:'o',п:'p',р:'r',с:'s',т:'t',у:'u',ф:'f',х:'x',ц:'ts',ч:'ch',ш:'sh',щ:'sh',ъ:'',ы:'i',ь:'',э:'e',ю:'yu',я:'ya',ў:'o',қ:'q',ғ:'g',ҳ:'h',і:'i' };
  // appwin/xatlar.py norm() bilan bir xil
  const xn = s => { s = String(s ?? '').toLowerCase(); s = [...s].map(c => CYR[c] ?? c).join('').replace(/[‘’`ʻʼ'´]/g, '');
    s = s.replace(/kh/g, 'x').replace(/textile/g, 'tekstil').replace(/textil/g, 'tekstil').replace(/buxara/g, 'buxoro').replace(/buhara/g, 'buxoro');
    s = s.replace(/c(?!h)(?=[aoulrtk])/g, 'k').replace(/c(?!h)(?=[eiy])/g, 's').replace(/ts/g, 's');
    return s.replace(/[^a-z0-9]+/g, ' ').trim(); };
  const toks = q => xn(q).split(' ').filter(t => t.length >= 2 || /^\d+$/.test(t));
  const hl = (text, tk) => { const t = esc(text); if (!tk || !tk.length) return t;
    return t.replace(/[^\s«»“”"(),.:;!?—–]+/g, w => { const n = xn(w); return n && tk.some(x => n.startsWith(x) || (' ' + n).includes(' ' + x)) ? `<mark class="xh">${w}</mark>` : w; }); };
  const KN = { chiquvchi_xat: 'Чиқувчи хат', kiruvchi_xat: 'Кирувчи хат', malumotnoma: 'Маълумотнома', bayonnoma: 'Баённома', hisobot: 'Даврий ҳисобот',
               ilova: 'Илова', korxona_hujjati: 'Корхона ҳужжати', boshqa: 'Бошқа', shovqin: 'Шовқин' };
  const SN = { korxona: 'Корхона', soha: 'Соҳа', tuman: 'Туман', davlat: 'Давлат', umumiy: 'Умумий' };
  const FILE_ICON = ext => ({ pdf: 'PDF', docx: 'Word', doc: 'Word', xlsx: 'Excel', xls: 'Excel', xlsb: 'Excel', zip: 'ZIP', rar: 'RAR', tif: 'Расм', jpg: 'Расм', png: 'Расм' })[ext] || (ext ? ext.toUpperCase() : 'Файл');
  const shortDist = n => (n || '').replace(' тумани', ' т.').replace(' шаҳри', ' ш.');

  // ---------------------------------------------------------------- umumiy bo'laklar
  function linkChips(links, tk, max = 9) {
    const L = links || [], out = [];
    const order = { company: 0, reply: 1, country: 2, sector: 3, district: 4 };
    [...L].sort((a, b) => (order[a.kind] ?? 9) - (order[b.kind] ?? 9)).forEach(x => {
      if (x.kind === 'company') out.push(`<button class="xl c" data-co="${esc(x.ref)}" title="ИНН ${esc(x.ref)} — корхона картаси">🏭 ${hl(x.label, tk)}</button>`);
      else if (x.kind === 'sector') out.push(`<button class="xl s" data-f="sector" data-v="${esc(x.ref)}" title="Шу соҳа бўйича хатлар">${esc(x.label)}</button>`);
      else if (x.kind === 'district') out.push(`<button class="xl d" data-f="district" data-v="${esc(x.ref)}" title="Шу туман бўйича хатлар">📍 ${esc(shortDist(x.label))}</button>`);
      else if (x.kind === 'country') out.push(`<button class="xl y" data-f="country" data-v="${esc(x.ref)}" title="Шу давлат бўйича хатлар">🌐 ${esc(x.label)}</button>`);
      else if (x.kind === 'reply' && x.role !== 'ext_no') out.push(`<button class="xl r" data-f="q" data-v="${esc(x.ref)}" title="Шу рақамли хат бўйича барча ёзишмалар">↩ ${hl(x.ref, tk)}</button>`);
    });
    if (out.length > max) return out.slice(0, max).join('') + `<span class="xl more">+${out.length - max}</span>`;
    return out.join('');
  }
  function dateBox(it) {
    const d = it.date || (it.tg_date || '').slice(0, 10) || (it.created_at || '').slice(0, 10);
    if (!d) return '<div class="xt-date"><b>—</b></div>';
    return `<div class="xt-date" title="${it.date ? 'Хат санаси' : 'Telegram / киритилган сана'}"><b>${d.slice(8, 10)}.${d.slice(5, 7)}</b><span>${d.slice(0, 4)}</span>${it.date ? '' : '<i>tg</i>'}</div>`;
  }
  function topLine(it) {
    const b = [`<span class="xt-k k-${esc(it.kind)}">${esc(KN[it.kind] || it.kind || '—')}</span>`];
    if (it.number) b.push(`<span class="mono">№ ${esc(it.number)}</span>`);
    if (it.doc_type) b.push(`<span>${esc(it.doc_type)}</span>`);
    if (it.recipient) b.push(`<span title="Кимга">→ ${esc(it.recipient.length > 60 ? it.recipient.slice(0, 58) + '…' : it.recipient)}</span>`);
    if (it.confidence === 'tekshirish' && !it.reviewed) b.push('<span class="pill warn">⚠ текшириш</span>');
    if (it.hidden) b.push('<span class="pill bad">архив</span>');
    if (it.role && it.role !== 'main') b.push(`<span class="pill info">${it.role === 'duplicate' ? 'нусха' : 'илова'}</span>`);
    if (it.source === 'manual') b.push('<span class="pill gold">қўлда</span>');
    return `<div class="xt-top">${b.join('')}</div>`;
  }
  function rowHtml(it, tk, opts = {}) {
    const sum = it.snippet ? `<div class="xt-sum snip">${hl(it.snippet, tk)}</div>` : (it.summary ? `<div class="xt-sum">${hl(it.summary, tk)}</div>` : '');
    const parent = it.parent_title ? `<div class="xt-nat">↳ илова: ${esc(it.parent_title.slice(0, 90))}</div>` : '';
    return `<div class="xt-row${it.confidence === 'tekshirish' && !it.reviewed ? ' chk' : ''}${opts.att ? ' att' : ''}" data-id="${it.id}">
      ${dateBox(it)}
      <div class="xt-main">${topLine(it)}<div class="xt-title">${hl(it.title || it.file_name || '(сарлавҳасиз)', tk)}</div>${sum}${parent}
        <div class="xt-links">${linkChips(it.links, tk, opts.maxLinks || 9)}</div></div>
      <div class="xt-act">${it.file_name ? `<button class="xt-file" data-file="${it.id}" title="${esc(it.file_name)}">📄 ${FILE_ICON(it.ext)}</button>` : ''}${it.n_att ? `<span class="xt-nat">📎 ${it.n_att} илова</span>` : ''}${it.my_role === 'ilovada' ? '<span class="xt-nat">иловада тилга олинган</span>' : ''}</div>
    </div>`;
  }
  function wireRows(root) {
    root.querySelectorAll('.xt-row').forEach(r => r.onclick = e => {
      const co = e.target.closest('[data-co]'); if (co) { e.stopPropagation(); openCompany(co.dataset.co); return; }
      const f = e.target.closest('[data-f]'); if (f) { e.stopPropagation(); filterBy(f.dataset.f, f.dataset.v); return; }
      const fl = e.target.closest('[data-file]'); if (fl) { e.stopPropagation(); openLetter(+fl.dataset.file, 'file'); return; }
      openLetter(+r.dataset.id);
    });
  }
  async function openCompany(inn, tab = 'xat') {
    closeX();
    $$('.nav').forEach(x => x.classList.toggle('active', x.dataset.p === 'reg'));
    $$('.page').forEach(x => x.classList.toggle('active', x.id === 'p-reg'));
    window.scrollTo(0, 0);
    try {
      await loaders.reg(inn);
      if (tab && typeof R !== 'undefined' && R.inn === inn) { R.tab = tab; $$('#pf-tabs button').forEach(x => x.classList.toggle('on', x.dataset.v === tab)); renderProfTab(); }
    } catch (e) { toast(e.message, true); }
  }
  function filterBy(key, val) {
    closeX();
    buildPage();
    ['district', 'sector', 'country'].forEach(k => XS[k] = '');
    XS.kinds.clear(); XS.scope = ''; XS.year = ''; XS.chk = false; XS.arch = false;
    if (key === 'q') { XS.q = val; } else { XS.q = ''; XS[key] = val; }
    syncControls();
    go('xat');
  }

  // ---------------------------------------------------------------- menyu sahifasi
  function buildPage() {
    if (XS.built) return;
    const el = $('#p-xat'); if (!el) return;
    el.innerHTML = `
      <div class="topbar"><h1>Хатлар</h1><span class="sub" id="xt-sub">бўлимнинг чиқувчи ва кирувчи хатлари · корхона, соҳа, туман, давлат кесимида</span>
        <div class="right"><button class="btn primary" id="xt-new" hidden>+ Хат қўшиш</button></div></div>
      <div class="fbar xt-fbar">
        <div class="fgrp wide"><input type="search" id="xt-q" class="xt-q" autocomplete="off" placeholder="Қидирув: корхона, ИНН, хат рақами (16-5338), мавзу, матн ичидан…  кирилл ва лотин фарқсиз  ( / )"></div>
        <div class="fgrp"><label>Тури</label><div class="chips" id="xt-kinds"></div></div>
        <div class="fgrp"><label>Кесим</label><div class="chips" id="xt-scopes"></div></div>
        <div class="fgrp"><label>Йил</label><select class="sel" id="xt-year"><option value="">Барча йиллар</option></select></div>
        <div class="fgrp"><label>Туман</label><select class="sel" id="xt-dist"><option value="">Барча туманлар</option></select></div>
        <div class="fgrp"><label>Соҳа</label><select class="sel" id="xt-sec"><option value="">Барча соҳалар</option></select></div>
        <div class="fgrp"><label>Давлат</label><select class="sel" id="xt-cn"><option value="">Барча давлатлар</option></select></div>
        <div class="fgrp"><label>&nbsp;</label><div class="chips"><button class="chip" id="xt-chk" title="Автоматик ўқишда шубҳали чиққан карталар">⚠ Текширилмаган <b id="xt-chk-n"></b></button>
          <button class="chip" id="xt-att" title="Асосий хат билан бирга илова ва нусхаларни ҳам алоҳида кўрсатиш">Илова ва нусхалар</button>
          <button class="chip" id="xt-arch" title="Шовқин ва такрорий нусхалар">Архив</button><button class="btn sm" id="xt-clr">Тозалаш</button></div></div>
      </div>
      <div class="xt-count" id="xt-count"></div>
      <div id="xt-list" class="xt-list"></div>
      <div class="xt-more"><button class="btn" id="xt-more" hidden>Яна кўрсатиш</button></div>`;
    $('#xt-q').oninput = () => { clearTimeout(XS.timer); XS.timer = setTimeout(() => { XS.q = $('#xt-q').value; reload(); }, 260); };
    $('#xt-q').onkeydown = e => { if (e.key === 'Enter') { clearTimeout(XS.timer); XS.q = $('#xt-q').value; reload(); } };
    $('#xt-year').onchange = () => { XS.year = $('#xt-year').value; reload(); };
    $('#xt-dist').onchange = () => { XS.district = $('#xt-dist').value; reload(); };
    $('#xt-sec').onchange = () => { XS.sector = $('#xt-sec').value; reload(); };
    $('#xt-cn').onchange = () => { XS.country = $('#xt-cn').value; reload(); };
    $('#xt-chk').onclick = () => { XS.chk = !XS.chk; syncControls(); reload(); };
    $('#xt-att').onclick = () => { XS.att = !XS.att; syncControls(); reload(); };
    $('#xt-arch').onclick = () => { XS.arch = !XS.arch; syncControls(); reload(); };
    $('#xt-clr').onclick = () => { Object.assign(XS, { q: '', scope: '', year: '', district: '', sector: '', country: '', chk: false, att: false, arch: false }); XS.kinds.clear(); syncControls(); reload(); };
    $('#xt-more').onclick = () => more().catch(e => toast(e.message, true));
    $('#xt-new').onclick = () => openAdd();
    XS.built = true;
  }
  function fillFacets() {
    const f = XS.facets; if (!f) return;
    const kinds = Object.keys(KN).filter(k => f.kinds[k]);
    $('#xt-kinds').innerHTML = kinds.map(k => `<button class="chip" data-k="${k}">${esc(KN[k])} <b>${f.kinds[k]}</b></button>`).join('');
    $$('#xt-kinds .chip').forEach(b => b.onclick = () => { XS.kinds.has(b.dataset.k) ? XS.kinds.delete(b.dataset.k) : XS.kinds.add(b.dataset.k); syncControls(); reload(); });
    $('#xt-scopes').innerHTML = Object.keys(SN).filter(k => f.scopes[k]).map(k => `<button class="chip" data-s="${k}">${esc(SN[k])} <b>${f.scopes[k]}</b></button>`).join('');
    $$('#xt-scopes .chip').forEach(b => b.onclick = () => { XS.scope = XS.scope === b.dataset.s ? '' : b.dataset.s; syncControls(); reload(); });
    const opt = (sel, first, arr) => { const s = $(sel), v = s.value; s.innerHTML = `<option value="">${first}</option>` + arr; s.value = v; };
    opt('#xt-year', 'Барча йиллар', f.years.map(y => `<option value="${esc(y)}">${esc(y)}</option>`).join(''));
    opt('#xt-dist', 'Барча туманлар', f.districts.map(d => `<option value="${esc(d.code)}">${esc(d.name)} (${d.n})</option>`).join(''));
    opt('#xt-sec', 'Барча соҳалар', f.sectors.map(d => `<option value="${esc(d.name)}">${esc(d.name)} (${d.n})</option>`).join(''));
    opt('#xt-cn', 'Барча давлатлар', f.countries.map(d => `<option value="${esc(d.name)}">${esc(d.name)} (${d.n})</option>`).join(''));
    $('#xt-chk-n').textContent = f.chk ? f.chk : '';
    const n = $('#nav-xat'); if (n) n.textContent = f.chk ? f.total + ' · ' + f.chk + '!' : String(f.total);
    syncControls();
  }
  function syncControls() {
    if (!XS.built) return;
    if ($('#xt-q').value !== XS.q) $('#xt-q').value = XS.q;
    $$('#xt-kinds .chip').forEach(b => b.classList.toggle('on', XS.kinds.has(b.dataset.k)));
    $$('#xt-scopes .chip').forEach(b => b.classList.toggle('on', XS.scope === b.dataset.s));
    const setSel = (sel, v) => { const s = $(sel); if (v && ![...s.options].some(o => o.value === v)) s.add(new Option(v, v)); s.value = v; };
    setSel('#xt-year', XS.year); setSel('#xt-dist', XS.district); setSel('#xt-sec', XS.sector); setSel('#xt-cn', XS.country);
    $('#xt-chk').classList.toggle('on', XS.chk); $('#xt-att').classList.toggle('on', XS.att); $('#xt-arch').classList.toggle('on', XS.arch);
    $('#xt-new').hidden = !XS.canWrite;
  }
  function params(offset) {
    const p = new URLSearchParams({ limit: 50, offset });
    if (XS.q.trim()) p.set('q', XS.q.trim());
    if (XS.kinds.size) p.set('kind', [...XS.kinds].join(','));
    for (const k of ['scope', 'year', 'district', 'sector', 'country']) if (XS[k]) p.set(k, XS[k]);
    if (XS.chk) p.set('chk', 1); if (XS.att) p.set('att', 1); if (XS.arch) p.set('hidden', 1);
    return p;
  }
  let seq = 0;
  async function reload() {
    const my = ++seq; XS.offset = 0;
    const r = await api('/api/xatlar/list?' + params(0));
    if (my !== seq) return;
    XS.items = r.items; XS.total = r.total; renderList();
  }
  async function more() {
    const r = await api('/api/xatlar/list?' + params(XS.items.length));
    XS.items = XS.items.concat(r.items); XS.total = r.total; renderList(true);
  }
  function renderList(keep) {
    const tk = toks(XS.q);
    const act = [];
    if (XS.q.trim()) act.push(`«${esc(XS.q.trim())}»`);
    if (XS.district) act.push('📍 ' + esc(shortDist((XS.facets.districts.find(d => d.code === XS.district) || {}).name || XS.district)));
    for (const k of ['sector', 'country', 'year']) if (XS[k]) act.push(esc(XS[k]));
    $('#xt-count').innerHTML = `<b>${XS.total}</b> та хат${act.length ? ' · ' + act.join(' · ') : ''}${XS.q.trim() ? ' <span class="hint">· энг мос натижалар юқорида</span>' : ' <span class="hint">· янгилари юқорида</span>'}`;
    const list = $('#xt-list');
    list.innerHTML = XS.items.length ? XS.items.map(it => rowHtml(it, tk)).join('') : `<div class="empty">Ҳеч нарса топилмади${XS.q ? ' — сўзни қисқартириб ёки бошқача ёзиб кўринг' : ''}</div>`;
    wireRows(list);
    $('#xt-more').hidden = XS.items.length >= XS.total;
    if (!keep) window.scrollTo(0, 0);
  }
  async function loadFacets() { XS.facets = await api('/api/xatlar/facets'); fillFacets(); }
  loaders.xat = async () => {
    buildPage(); syncControls();
    await Promise.all([loadFacets(), reload()]);
    setTimeout(() => { const q = $('#xt-q'); if (q && !('ontouchstart' in window)) q.focus(); }, 50);
  };

  // ---------------------------------------------------------------- xat kartasi (oyna)
  const M = () => $('#xat-modal');
  function closeX() { const m = M(); if (m) m.hidden = true; }
  async function openLetter(id, tab) {
    try {
      const d = await api('/api/xatlar/get?id=' + id);
      XS.cur = d; XS.tab = tab || (XS.tab === 'edit' ? 'sum' : 'sum');
      renderLetter(); M().hidden = false;
    } catch (e) { toast(e.message, true); }
  }
  function renderLetter() {
    const d = XS.cur, tk = toks(XS.q);
    const tabs = [['sum', 'Мазмуни'], ['file', 'Файл'], ['text', 'Матн'], ...(d.children.length ? [['att', `Илова ва нусхалар (${d.children.length})`]] : []), ...(d.related.length ? [['rel', `Ёзишмалар (${d.related.length})`]] : [])];
    const tabsHtml = XS.tab === 'edit' ? '' : `<div class="seg" id="xm-tabs">${tabs.map(([v, t]) => `<button data-v="${v}" class="${XS.tab === v ? 'on' : ''}">${t}</button>`).join('')}</div>`;
    const foot = XS.tab === 'edit' ? `<button class="btn primary" id="xe-save">Сақлаш</button><button class="btn" id="xe-cancel">Бекор қилиш</button>`
      : `${d.file_ok ? `<a class="btn" href="/api/xatlar/file?id=${d.id}&dl=1" title="Юклаб олиш (Yuklamalar папкасига)">⬇ Юклаб олиш</a>` : ''}
         ${d.parent ? `<button class="btn" data-open="${d.parent.id}">↑ Асосий хат</button>` : ''}
         <span class="right">${XS.canWrite ? `${d.confidence === 'tekshirish' && !d.reviewed ? '<button class="btn" id="xm-ok" title="Карта тўғри — текширилди деб белгилаш">✓ Тасдиқлаш</button>' : ''}
           <button class="btn" id="xm-arch">${d.hidden ? 'Архивдан чиқариш' : 'Архивга'}</button><button class="btn primary" id="xm-edit">✎ Таҳрирлаш</button>` : ''}</span>`;
    $('#xat-body').innerHTML = `
      <button class="xm-x" id="xm-x" title="Ёпиш (Esc)">×</button>
      <div class="xm-h">${topLine(d)}<h2>${hl(d.title || d.file_name || '(сарлавҳасиз)', tk)}</h2>${tabsHtml}</div>
      <div class="xm-b" id="xm-b"></div>
      <div class="xm-f">${foot}</div>`;
    $('#xm-x').onclick = closeX;
    $$('#xm-tabs button').forEach(b => b.onclick = () => { XS.tab = b.dataset.v; renderLetter(); });
    $$('#xat-body [data-open]').forEach(b => b.onclick = () => openLetter(+b.dataset.open));
    if ($('#xm-edit')) $('#xm-edit').onclick = () => { XS.tab = 'edit'; renderLetter(); };
    if ($('#xm-ok')) $('#xm-ok').onclick = () => save({ review: true }, 'Тасдиқланди');
    if ($('#xm-arch')) $('#xm-arch').onclick = () => save({ hidden: !d.hidden }, d.hidden ? 'Архивдан чиқарилди' : 'Архивга ўтказилди');
    const b = $('#xm-b');
    ({ sum: tabSum, file: tabFile, text: tabText, att: tabAtt, rel: tabRel, edit: tabEdit })[XS.tab](d, b, tk);
  }
  function tabSum(d, b, tk) {
    const kv = [];
    const add = (k, v) => { if (v) kv.push(`<dt>${k}</dt><dd>${v}</dd>`); };
    add('Санаси', d.date ? dmy(d.date) : '');
    add('Рақами', d.number ? `<span class="mono">${esc(d.number)}</span>` : '');
    add('Кимдан', esc(d.sender || '')); add('Кимга', esc(d.recipient || ''));
    add('Ҳужжат тури', esc(d.doc_type || ''));
    add('Жавоб / асос', (d.reply_to || []).map(r => `<button class="xl r" data-f="q" data-v="${esc(r.reg_no || r.ext_no)}">${r.reg_no ? '↩ ' + esc(r.reg_no) : ''}${r.ext_no ? (r.reg_no ? ' · ' : '↩ ') + esc(r.ext_no) : ''}${r.ext_date ? ' (' + dmy(r.ext_date) + ')' : ''}</button>${r.from ? ` <span class="hint">${esc(r.from)}</span>` : ''}`).join('<br>'));
    add('Имзо', esc(d.signer || '')); add('Ижрочи', esc(d.executor || ''));
    add('Кесим', esc(SN[d.scope] || d.scope || ''));
    add('Файл', d.file_name ? `${esc(d.file_name)} <span class="hint">${d.file_size ? Math.round(d.file_size / 1024) + ' КБ' : ''}${d.tg_date ? ' · Telegram ' + dmy(d.tg_date.slice(0, 10)) : ''}${d.created_by && d.source === 'manual' ? ' · киритди: ' + esc(d.created_by) : ''}</span>` : '');
    if (d.reviewed_at) add('Текширилди', `${esc(d.reviewed_by || '')} · ${esc(d.reviewed_at.replace('T', ' ').slice(0, 16))}`);
    const fl = (d.flags || []).map(f => `<span class="pill warn">${esc(f)}</span>`).join(' ');
    const facts = (d.facts || []).length ? `<div class="xm-sec">Асосий рақамлар</div><table class="xm-facts"><tbody>${d.facts.map(f => `<tr><td>${esc(f.what)}</td><td><b>${esc(f.value)}</b></td><td class="hint">${f.as_of ? dmy(f.as_of) + ' ҳолатига' : ''}</td></tr>`).join('')}</tbody></table>` : '';
    const unm = (d.companies_unmatched || []).length ? `<div class="xm-sec">Базада топилмаган ташкилотлар</div><div class="hint">${d.companies_unmatched.map(esc).join(' · ')}</div>` : '';
    const topics = (d.topics || []).length ? `<div class="xm-sec">Калит сўзлар</div><div class="xt-links">${d.topics.map(t => `<button class="xl" data-f="q" data-v="${esc(t)}">${esc(t)}</button>`).join('')}</div>` : '';
    b.innerHTML = `${d.confidence === 'tekshirish' && !d.reviewed ? `<div class="xm-note">⚠ Автоматик ўқишда шубҳа бор${d.note ? ': ' + esc(d.note) : ''}. Текшириб, керак бўлса таҳрирланг ва «✓ Тасдиқлаш»ни босинг.</div>` : ''}
      ${d.summary ? `<p class="xm-sum">${hl(d.summary, tk)}</p>` : '<p class="hint">Қисқа мазмун ёзилмаган.</p>'}
      ${fl ? `<div style="margin-bottom:10px">${fl}</div>` : ''}
      <dl class="xm-kv">${kv.join('')}</dl>
      <div class="xm-sec">Боғланишлар</div><div class="xt-links">${linkChips(d.links, tk, 60) || '<span class="hint">умумий — корхона, соҳа ёки туманга боғланмаган</span>'}</div>
      ${facts}${unm}${topics}
      ${d.note && d.confidence !== 'tekshirish' ? `<div class="xm-sec">Изоҳ</div><div class="hint">${esc(d.note)}</div>` : ''}`;
    wireChips(b);
  }
  function wireChips(b) {
    b.querySelectorAll('[data-co]').forEach(x => x.onclick = () => openCompany(x.dataset.co));
    b.querySelectorAll('[data-f]').forEach(x => x.onclick = () => filterBy(x.dataset.f, x.dataset.v));
  }
  function tabFile(d, b) {
    if (!d.file_ok) { b.innerHTML = '<div class="empty">Файл серверда топилмади</div>'; return; }
    const src = '/api/xatlar/file?id=' + d.id, ext = d.ext;
    if (ext === 'pdf') b.innerHTML = `<iframe class="xm-frame" src="${src}#view=FitH" title="${esc(d.file_name)}"></iframe><p class="note">PDF кўринмаса — пастдаги «⬇ Юклаб олиш» тугмаси (Yuklamalar папкасига тушади).</p>`;
    else if (['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)) b.innerHTML = `<img class="xm-img" src="${src}" alt="">`;
    else b.innerHTML = `<div class="empty">«${esc(d.file_name)}» — бу турдаги файлни шу ерда кўрсатиб бўлмайди.<br><br><a class="btn primary" href="${src}&dl=1">⬇ Юклаб олиш ва очиш</a><br><br><span class="hint">Файл ичидаги матн — «Матн» бўлимида.</span></div>`;
  }
  function tabText(d, b, tk) {
    b.innerHTML = d.text ? `<div class="form-row"><input type="search" id="xm-tq" placeholder="Матн ичидан излаш…" value="${esc(XS.q)}" style="flex:1"><span class="hint">${d.text.length.toLocaleString('ru-RU')} белги · скан бўлса OCR хатолари бўлиши мумкин</span></div><pre class="xm-text" id="xm-pre"></pre>`
      : '<div class="empty">Матн йўқ (скан ёки ўқиб бўлмайдиган файл)</div>';
    if (!d.text) return;
    const draw = () => { const t = toks($('#xm-tq').value); $('#xm-pre').innerHTML = hl(d.text, t); const m = $('#xm-pre mark'); if (m) m.scrollIntoView({ block: 'center' }); };
    $('#xm-tq').oninput = draw; draw();
  }
  function tabAtt(d, b, tk) { b.innerHTML = `<div class="xm-mini">${d.children.map(c => rowHtml(c, tk)).join('')}</div>`; wireRows(b); }
  function tabRel(d, b, tk) {
    b.innerHTML = `<p class="hint" style="margin-top:0">Шу кирувчи/чиқувчи рақам тилга олинган бошқа хатлар:</p><div class="xm-mini">${d.related.map(c => rowHtml(c, tk)).join('')}</div>`; wireRows(b);
  }
  async function save(patch, msg) {
    try {
      const d = await api('/api/xatlar/update', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: XS.cur.id, ...patch }) });
      XS.cur = d; if (XS.tab === 'edit') XS.tab = 'sum'; renderLetter(); toast(msg || 'Сақланди');
      afterChange();
    } catch (e) { toast(e.message, true); }
  }
  function afterChange() {
    if ($('#p-xat') && $('#p-xat').classList.contains('active')) { loadFacets().catch(() => {}); reload().catch(() => {}); }
    if (typeof R !== 'undefined' && R.inn && R.tab === 'xat' && $('#p-reg').classList.contains('active')) renderProfTab();
    if (typeof R !== 'undefined' && R.inn) tabCount(R.inn);
  }

  // ---------------------------------------------------------------- tahrir va qo'shish formasi (umumiy)
  function formHtml(v) {
    const kopt = Object.entries(KN).map(([k, t]) => `<option value="${k}"${v.kind === k ? ' selected' : ''}>${t}</option>`).join('');
    const sopt = Object.entries(SN).map(([k, t]) => `<option value="${k}"${v.scope === k ? ' selected' : ''}>${t}</option>`).join('');
    const rp = (v.reply_to || [])[0] || {};
    return `<div class="xe-grid">
      <div class="full"><label>Сарлавҳа — хат нима ҳақида (қидирувда энг муҳим)</label><input type="text" id="xe-title" value="${esc(v.title || '')}" placeholder="масалан: «Bukhara Cotton Textile» — Эронга ип калава етказиш кечикиши бўйича жавоб"></div>
      <div class="full"><label>Қисқа мазмун (ихтиёрий) — 2–4 гап</label><textarea id="xe-sum" placeholder="Нима сўралган, нима жавоб берилган, асосий рақам ва муддат">${esc(v.summary || '')}</textarea></div>
      <div><label>Тури</label><select id="xe-kind">${kopt}</select></div>
      <div><label>Ҳужжат тури (эркин)</label><input type="text" id="xe-dt" value="${esc(v.doc_type || '')}" placeholder="жавоб хати, сўров, маълумотнома…"></div>
      <div><label>Хат рақами</label><input type="text" id="xe-num" value="${esc(v.number || '')}" placeholder="04-7-272"></div>
      <div><label>Санаси</label><input type="date" id="xe-date" value="${esc(v.date || '')}"></div>
      <div><label>Кимга</label><input type="text" id="xe-to" value="${esc(v.recipient || '')}" placeholder="Инвестициялар, саноат ва савдо вазирлиги"></div>
      <div><label>Кимдан</label><input type="text" id="xe-from" value="${esc(v.sender || '')}"></div>
      <div><label>Жавоб: бўлим кирувчи рақами</label><input type="text" id="xe-reg" value="${esc(rp.reg_no || '')}" placeholder="16-5338"></div>
      <div><label>Жавоб: юборувчининг хат рақами</label><input type="text" id="xe-ext" value="${esc(rp.ext_no || '')}" placeholder="06-21-21-3-7226"></div>
      <div><label>Асосий кесим</label><select id="xe-scope"><option value="">автоматик</option>${sopt}</select></div>
      <div><label>Изоҳ</label><input type="text" id="xe-note" value="${esc(v.note || '')}"></div>
      <div class="full"><label>Боғланишлар — корхона, соҳа, туман, давлат (бир нечта бўлиши мумкин)</label>
        <div class="xe-links" id="xe-links"></div>
        <div class="xe-lk"><input type="text" id="xe-lq" autocomplete="off" placeholder="+ қўшиш: корхона номи ёки ИНН, соҳа, туман, давлат…"><div class="xe-pop" id="xe-pop" hidden></div></div>
        <div class="xe-legend" id="xe-legend"></div></div>
    </div>`;
  }
  const LE = { links: [] };
  function drawLinks() {
    const box = $('#xe-links'); if (!box) return;
    const cls = { company: 'c', sector: 's', district: 'd', country: 'y' }, ico = { company: '🏭 ', district: '📍 ', country: '🌐 ', sector: '' };
    const vis = LE.links.filter(l => l.kind !== 'reply');
    box.innerHTML = vis.length ? vis.map((l, i) => `<span class="xl ${cls[l.kind] || ''}${l.sug ? ' sug' : ''}" title="${l.sug ? 'Автоматик топилди' + (l.by ? ' (' + l.by + ')' : '') + ' — керак бўлмаса ×' : ''}">${ico[l.kind] || ''}${esc(l.kind === 'district' ? shortDist(l.label) : l.label)}${l.kind === 'company' ? ` <span class="hint">${esc(l.ref)}</span>` : ''}<button data-i="${LE.links.indexOf(l)}" title="Олиб ташлаш">×</button></span>`).join('')
      : '<span class="hint" style="padding:4px">боғланиш йўқ — хат «умумий» бўлади</span>';
    box.querySelectorAll('button[data-i]').forEach(bt => bt.onclick = () => { LE.links.splice(+bt.dataset.i, 1); drawLinks(); });
    const sug = LE.links.filter(l => l.sug).length;
    $('#xe-legend').textContent = sug ? `Нуқтали чегарали ${sug} таси — файл матнидан автоматик топилган; текшириб, кераксизини × билан олиб ташланг.` : '';
  }
  function addLink(l) {
    if (LE.links.some(x => x.kind === l.kind && x.ref === l.ref)) return;
    LE.links.push(l); drawLinks();
  }
  function wireLinkSearch() {
    const inp = $('#xe-lq'), pop = $('#xe-pop'); let t = null, my = 0;
    const run = async () => {
      const q = inp.value.trim(); const k = ++my;
      const r = await api('/api/xatlar/lookup?q=' + encodeURIComponent(q)); if (k !== my) return;
      const g = [];
      if (r.companies.length) g.push('<h4>Корхоналар</h4>' + r.companies.map(c => `<button data-k="company" data-r="${esc(c.inn)}" data-l="${esc(c.name)}">🏭 ${esc(c.name)}<span>${esc(c.inn)} · ${esc(shortDist(c.district || ''))}</span></button>`).join(''));
      if (r.sectors.length) g.push('<h4>Соҳалар</h4>' + r.sectors.slice(0, q ? 8 : 16).map(s => `<button data-k="sector" data-r="${esc(s)}" data-l="${esc(s)}">${esc(s)}</button>`).join(''));
      if (r.districts.length) g.push('<h4>Туманлар</h4>' + r.districts.map(d => `<button data-k="district" data-r="${esc(d.code)}" data-l="${esc(d.name)}">📍 ${esc(d.name)}</button>`).join(''));
      if (r.countries.length) g.push('<h4>Давлатлар</h4>' + r.countries.slice(0, q ? 10 : 20).map(c => `<button data-k="country" data-r="${esc(c)}" data-l="${esc(c)}">🌐 ${esc(c)}</button>`).join(''));
      pop.innerHTML = g.join('') || '<div class="hint" style="padding:8px">топилмади</div>'; pop.hidden = false;
      pop.scrollIntoView({ block: 'nearest' });
      pop.querySelectorAll('button').forEach(bt => bt.onmousedown = e => { e.preventDefault(); addLink({ kind: bt.dataset.k, ref: bt.dataset.r, label: bt.dataset.l }); inp.value = ''; pop.hidden = true; });
    };
    inp.onfocus = () => run().catch(() => {});
    inp.oninput = () => { clearTimeout(t); t = setTimeout(() => run().catch(() => {}), 180); };
    inp.onblur = () => setTimeout(() => { pop.hidden = true; }, 150);
    inp.onkeydown = e => { if (e.key === 'Escape') { e.stopPropagation(); pop.hidden = true; } if (e.key === 'Enter') { e.preventDefault(); const f = pop.querySelector('button'); if (f) f.dispatchEvent(new MouseEvent('mousedown')); } };
  }
  function readForm() {
    const reg = $('#xe-reg').value.trim(), ext = $('#xe-ext').value.trim();
    const reply = (reg || ext) ? [{ ...(LE.reply0 || {}), reg_no: reg || null, ext_no: ext || null }] : [];
    return { title: $('#xe-title').value.trim(), summary: $('#xe-sum').value.trim(), kind: $('#xe-kind').value, doc_type: $('#xe-dt').value.trim(),
             number: $('#xe-num').value.trim(), date: $('#xe-date').value || null, recipient: $('#xe-to').value.trim(), sender: $('#xe-from').value.trim(),
             scope: $('#xe-scope').value || null, note: $('#xe-note').value.trim(), reply_to: reply,
             links: LE.links.filter(l => l.kind !== 'reply').map(l => ({ kind: l.kind, ref: l.ref, label: l.label, role: l.role || null })) };
  }
  function tabEdit(d, b) {
    b.innerHTML = formHtml(d);
    LE.links = (d.links || []).filter(l => l.kind !== 'reply').map(l => ({ ...l })); LE.reply0 = (d.reply_to || [])[0] || null;
    drawLinks(); wireLinkSearch();
    $('#xe-cancel').onclick = () => { XS.tab = 'sum'; renderLetter(); };
    $('#xe-save').onclick = () => {
      const f = readForm(); if (!f.title) { toast('Сарлавҳа киритинг', true); return; }
      const reply = f.reply_to, links = f.links.concat(reply.flatMap(r => [r.reg_no ? { kind: 'reply', ref: r.reg_no, label: r.from || '', role: 'reg_no' } : null, r.ext_no ? { kind: 'reply', ref: r.ext_no, label: r.from || '', role: 'ext_no' } : null]).filter(Boolean));
      save({ ...f, links, scope: f.scope || d.scope }, 'Карта сақланди');
    };
    setTimeout(() => $('#xe-title').focus(), 30);
  }

  // ---------------------------------------------------------------- «+ Хат қўшиш»
  async function openAdd(ctx = {}) {
    if (!XS.canWrite) { toast("Хат қўшиш учун ёзиш ҳуқуқи керак", true); return; }
    XS.cur = null;
    $('#xat-body').innerHTML = `<button class="xm-x" id="xm-x" title="Ёпиш (Esc)">×</button>
      <div class="xm-h"><div class="xt-top"><span class="xt-k k-chiquvchi_xat">Янги хат</span>${ctx.name ? `<span>· ${esc(ctx.name)}</span>` : ''}</div><h2>Хат қўшиш</h2></div>
      <div class="xm-b" id="xa-b">
        <label class="drop xe-drop" id="xa-drop"><input type="file" id="xa-f" hidden><b>Файлни шу ерга ташланг ёки танланг</b>PDF, Word, Excel, расм — 80 МБ гача. Дастур матнни ўзи ўқиб, рақам, сана, корхона, туман, давлат ва соҳани таклиф қилади.</label>
      </div>
      <div class="xm-f"><span class="hint">Файл серверда сақланади: data\\xatlar\\qolda\\</span></div>`;
    M().hidden = false;
    $('#xm-x').onclick = closeX;
    const drop = $('#xa-drop'), inp = $('#xa-f');
    drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); };
    drop.ondragleave = () => drop.classList.remove('over');
    drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); if (e.dataTransfer.files[0]) up(e.dataTransfer.files[0]); };
    inp.onchange = () => { if (inp.files[0]) up(inp.files[0]); };
    async function up(f) {
      drop.innerHTML = `<b>Юкланмоқда…</b>${esc(f.name)}`;
      try {
        const r = await api('/api/xatlar/upload', { method: 'POST', headers: { 'X-Filename': encodeURIComponent(f.name) }, body: f });
        showAddForm(r, ctx);
      } catch (e) { toast(e.message, true); drop.innerHTML = `<b>Хато: ${esc(e.message)}</b>Қайта танланг`; }
    }
  }
  function showAddForm(r, ctx) {
    const s = r.suggest || {};
    const v = { title: s.title || '', kind: s.kind || 'chiquvchi_xat', number: s.number || '', date: s.date || '', reply_to: s.reply_to || [] };
    $('#xa-b').innerHTML = `<div class="xe-info">📄 <b>${esc(r.file_name)}</b> · ${Math.round(r.size / 1024)} КБ · ${r.text_chars ? r.text_chars.toLocaleString('ru-RU') + ' белги матн ўқилди' : 'матн ўқилмади'} <span class="hint">(${esc(r.text_info || '')})</span></div>
      ${formHtml(v)}
      ${r.text_preview ? `<details style="margin-top:12px"><summary class="hint">Файл матни (дастлабки қисми)</summary><pre class="xm-text" style="max-height:260px">${esc(r.text_preview)}</pre></details>` : ''}`;
    LE.links = []; LE.reply0 = null;
    if (ctx.inn) LE.links.push({ kind: 'company', ref: ctx.inn, label: ctx.name || ctx.inn, role: 'asosiy' });
    (s.companies || []).slice(0, 15).forEach(c => { if (!LE.links.some(l => l.kind === 'company' && l.ref === c.inn)) LE.links.push({ kind: 'company', ref: c.inn, label: c.name, sug: true, by: c.by === 'INN' ? 'ИНН бўйича' : 'номи бўйича' }); });
    (s.sectors || []).forEach(x => LE.links.push({ kind: 'sector', ref: x, label: x, sug: true }));
    (s.districts || []).forEach(x => LE.links.push({ kind: 'district', ref: x.code, label: x.name, sug: true }));
    (s.countries || []).forEach(x => LE.links.push({ kind: 'country', ref: x, label: x, sug: true }));
    drawLinks(); wireLinkSearch();
    $('.xm-f').innerHTML = `<button class="btn primary" id="xa-save">Сақлаш</button><button class="btn" id="xa-cancel">Бекор қилиш</button><span class="hint right">Сарлавҳа мажбурий; қолганини кейин ҳам тўлдириш мумкин</span>`;
    $('#xa-cancel').onclick = closeX;
    $('#xa-save').onclick = async () => {
      const f = readForm(); if (!f.title) { toast('Сарлавҳа киритинг', true); $('#xe-title').focus(); return; }
      try {
        const d = await api('/api/xatlar/create', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...f, token: r.token, file_name: r.file_name }) });
        toast('Хат сақланди'); XS.cur = d; XS.tab = 'sum'; renderLetter(); afterChange();
      } catch (e) { toast(e.message, true); }
    };
    setTimeout(() => $('#xe-title').focus(), 30);
  }

  // ---------------------------------------------------------------- korxona profili: «Хатлар» tabi
  async function tabCount(inn) {
    try {
      const r = await api('/api/xatlar/count?inn=' + encodeURIComponent(inn));
      const b = $('#pf-tabs button[data-v="xat"]'); if (b && typeof R !== 'undefined' && R.inn === inn) b.textContent = `Хатлар (${r.n})`;
    } catch (_) {}
  }
  async function profileTab(p, body) {
    const inn = p.inn || (p.company && p.company.inn) || R.inn, name = (p.company && p.company.name) || inn;
    body.innerHTML = '<div class="empty">юкланмоқда…</div>';
    const r = await api('/api/xatlar/company?inn=' + encodeURIComponent(inn));
    if (R.inn !== inn || R.tab !== 'xat') return;
    body.innerHTML = `<div class="panel">
        <div class="xp-h"><h2>Хатлар <span class="hint">${r.items.length} та · шу корхонага боғланган (ўзи ёки иловаси)</span></h2>
          <div class="right">${XS.canWrite ? '<button class="btn primary sm" id="xp-add">+ Хат қўшиш</button>' : ''}<button class="btn sm" id="xp-all">Хатлар бўлимида очиш</button></div></div>
        <div class="xt-list" id="xp-list">${r.items.length ? r.items.map(it => rowHtml(it, [])).join('') : '<div class="empty">Бу корхонага боғланган хат йўқ</div>'}</div>
        ${r.related.length ? `<details class="xp-rel"><summary>Соҳаси ва тумани бўйича хатлар (${r.related.length}) — ${esc(r.related_by.join(', '))}</summary><div class="xt-list" id="xp-rel">${r.related.map(it => rowHtml(it, [], { maxLinks: 6 })).join('')}</div></details>` : ''}
      </div>`;
    wireRows(body);
    if ($('#xp-add')) $('#xp-add').onclick = () => openAdd({ inn, name });
    $('#xp-all').onclick = () => { buildPage(); Object.assign(XS, { q: '', scope: '', year: '', district: '', sector: '', country: '', chk: false, arch: false }); XS.kinds.clear(); XS.q = inn; go('xat'); };
  }

  // ---------------------------------------------------------------- ishga tushirish
  function init() {
    fetch('/api/auth/me').then(r => r.json()).then(d => { XS.canWrite = !!(d.user && ['superadmin', 'operator'].includes(d.user.role)); if (XS.built) syncControls(); }).catch(() => {});
    api('/api/xatlar/facets').then(f => { XS.facets = f; const n = $('#nav-xat'); if (n) n.textContent = f.chk ? f.total + ' · ' + f.chk + '!' : String(f.total); }).catch(() => {});
    document.addEventListener('keydown', e => {
      if (e.key === '/' && $('#p-xat') && $('#p-xat').classList.contains('active') && !e.target.closest('input,textarea,select,[contenteditable]') && M().hidden) { e.preventDefault(); $('#xt-q').focus(); }
    });
    const route = () => { const m = (location.hash || '').match(/^#xat\/?(\d*)$/); if (!m) return; go('xat'); if (m[1]) openLetter(+m[1]); };
    window.addEventListener('hashchange', route); setTimeout(route, 700);
  }
  window.XAT = { profileTab, tabCount, openLetter, openAdd, filterBy };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
