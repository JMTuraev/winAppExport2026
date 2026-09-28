"use strict";
// ================================================================= КАТАЛОГ (Jafar, 26.09.2026)
// Экспорт салоҳияти витринаси: корхона -> маҳсулотлар (расм, нарх, 3 тил) -> сайт (элчихоналар орқали хорижий харидорларга).
// Бу файл app.js дан кейин юкланади ва унинг ёрдамчиларидан фойдаланади: $, $$, api, toast, esc, fmt, fmt0, dmy, smatch, go, loaders, download, S.
const CT = { ov: null, view: 'list', inn: null, det: null, lang: 'uz', dirty: false, q: '', st: '', wf: '', inq: null, iq: { q: '', st: '', ch: '' } };
const CT_LANGS = [['uz', "O'zbekcha"], ['ru', 'Русский'], ['en', 'English']];
const CT_ST = { published: ['ok', 'Эълон қилинган'], draft: ['warn', 'Қоралама'], hidden: ['gray', 'Яширин'], template: ['info', 'Шаблон'] };
const CT_WARN = { logo: 'Логотип йўқ', about_en: 'EN тавсиф йўқ', about_ru: 'RU тавсиф йўқ', about_uz: 'UZ тавсиф йўқ', gallery: 'Корхона расмлари йўқ',
  contact: 'Ички алоқа йўқ', no_published: 'Эълон қилинган маҳсулот йўқ', photos: 'Расмсиз маҳсулот', prices: 'Нархсиз маҳсулот',
  price_expired: 'Нарх муддати ўтган', doc_expired: 'Сертификат муддати ўтган', templates: 'Шаблон тўлдирилмаган' };
const CT_Q = { new: ['info', 'Янги'], sent: ['warn', 'Корхонага юборилди'], talks: ['gold', 'Музокара'], deal: ['ok', 'Шартнома'], lost: ['gray', 'Натижасиз'] };
const CT_CH = { embassy: 'Элчихона', exhibition: 'Кўргазма', b2b: 'B2B учрашув', site: 'Сайт', direct: 'Тўғридан-тўғри', other: 'Бошқа' };
const CT_CUR = ['USD', 'EUR', 'RUB', 'CNY', 'UZS'];
const ctPost = (path, body) => api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
const ctPill = (m, k) => { const x = m[k] || ['gray', k]; return `<span class="pill ${x[0]}">${esc(x[1])}</span>`; };
const ctI = () => (CT.ov && CT.ov.i18n) || { cat1: {}, cat2: {}, units: {}, payment: {}, doc_types: {}, districts: {}, incoterms: [] };
const ctTypo = x => String(x || '').replace(/ʻ/g, '‘').replace(/ʼ/g, '’');
const ctCat = k => ctTypo(((ctI().cat1[k] || {}).uz) || k || '');
const ctSub = k => ctTypo(((ctI().cat2[k] || {}).uz) || k || '');
const ctName = o => (o && (o.uz || o.ru || o.en)) || '';
const ctToday = () => localISO(new Date());
const ctPrice = p => p.price == null && p.price_to == null ? '' : `${fmt(p.price ?? p.price_to, 2)}${p.price != null && p.price_to != null && p.price_to !== p.price ? '–' + fmt(p.price_to, 2) : ''} ${esc(p.currency || 'USD')}${p.unit ? ' / ' + esc(((ctI().units[p.unit] || {}).ru) || p.unit) : ''}`;
function ctInitials(n) { return (String(n || '').replace(/[«»"“”]|MChJ|ООО|LLC/g, '').trim().split(/\s+/).slice(0, 2).map(w => w[0]).join('') || '•').toUpperCase(); }
function ctModal(id, html, cls = '') {
  let m = $('#' + id); if (!m) { m = document.createElement('div'); m.className = 'mbg'; m.id = id; document.body.appendChild(m); }
  m.innerHTML = `<div class="mdl ${cls}" role="dialog" aria-modal="true"><button class="x" data-x aria-label="Ёпиш">×</button>${html}</div>`;
  m.hidden = false; m.onclick = e => { if (e.target === m) ctClose(id); };
  m.querySelector('[data-x]').onclick = () => ctClose(id);
  return m;
}
function ctClose(id) { const m = $('#' + id); if (m) { if (m._guard && !m._guard()) return; m.hidden = true; m.innerHTML = ''; } }
document.addEventListener('keydown', e => { if (e.key !== 'Escape') return; const open = $$('#ct-pm,#ct-add,#ct-set,#ct-inqm,#ct-bulk').filter(m => !m.hidden).pop(); if (open) ctClose(open.id); });

// ----------------------------------------------------------------- image resize in the browser (Pillow yo'q)
async function ctLoadImage(file) {
  if (/heic|heif/i.test(file.type) || /\.hei[cf]$/i.test(file.name)) throw new Error('HEIC (iPhone) форматини браузер ўқимайди — JPG/PNG га ўгириб юкланг');
  try { return await createImageBitmap(file); } catch (_) {}
  return await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('Расмни ўқиб бўлмади: ' + file.name)); i.src = URL.createObjectURL(file); });
}
function ctCanvas(img, max, type, q) {
  const w0 = img.width || img.naturalWidth, h0 = img.height || img.naturalHeight, s = Math.min(1, max / Math.max(w0, h0));
  const c = document.createElement('canvas'); c.width = Math.max(1, Math.round(w0 * s)); c.height = Math.max(1, Math.round(h0 * s));
  const g = c.getContext('2d'); g.imageSmoothingQuality = 'high';
  if (type === 'image/jpeg') { g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); }
  g.drawImage(img, 0, 0, c.width, c.height);
  return { data: c.toDataURL(type, q), w: c.width, h: c.height };
}
async function ctUploadImages(files, base) {   // base: {inn, kind, product_id?}
  const list = [...files].filter(f => /^image\//.test(f.type) || /\.(jpe?g|png|webp|heic)$/i.test(f.name));
  if (!list.length) { toast('Расм файл танланг (JPG, PNG, WEBP)', true); return 0; }
  let n = 0;
  for (const f of list) {
    try {
      toast(`Расм юкланмоқда… ${n + 1}/${list.length}`);
      const im = await ctLoadImage(f);
      const png = base.kind === 'logo' && /png|webp/i.test(f.type);
      const main = ctCanvas(im, base.kind === 'logo' ? 800 : 1600, png ? 'image/png' : 'image/jpeg', 0.86);
      const th = ctCanvas(im, 560, 'image/jpeg', 0.8);
      await ctPost('/api/catalog/media/upload', { ...base, main: main.data, thumb: th.data, w: main.w, h: main.h, filename: f.name });
      n++;
    } catch (e) { toast(e.message, true); }
  }
  if (n) toast(`${n} та расм сақланди`);
  return n;
}
function ctDrop(el, onFiles) {
  const inp = document.createElement('input'); inp.type = 'file'; inp.multiple = true; inp.accept = 'image/*'; inp.hidden = true; el.appendChild(inp);
  el.onclick = e => { if (e.target === inp) return; inp.click(); };
  inp.onchange = () => { const fs = [...inp.files]; inp.value = ''; if (fs.length) onFiles(fs); };   // nusxa: value='' FileList'ni bo'shatadi
  el.ondragover = e => { e.preventDefault(); el.classList.add('over'); };
  el.ondragleave = () => el.classList.remove('over');
  el.ondrop = e => { e.preventDefault(); el.classList.remove('over'); const fs = [...e.dataTransfer.files]; if (fs.length) onFiles(fs); };
}

// ----------------------------------------------------------------- page
loaders.cat = async (arg) => {
  ctWire();
  if (arg && arg.inn) { await ctLoad(); return ctOpen(arg.inn, arg.product); }
  await ctLoad();
  if (CT.inn && CT.view === 'list' && !$('#ct-ed').hidden) return ctOpen(CT.inn);
  ctShow(CT.view === 'edit' ? 'list' : CT.view);
};
async function ctLoad() {
  CT.ov = await api('/api/catalog/overview');
  ctNav(); ctSeed(); ctKpi();
}
function ctNav() { const n = CT.ov ? CT.ov.kpi.inq_new : 0; const el = $('#nav-cat'); if (el) el.textContent = n ? n + ' янги' : (CT.ov ? String(CT.ov.kpi.p_published) : '—'); }
let ctWired = false;
function ctWire() {
  if (ctWired) return; ctWired = true;
  $$('#ct-view button').forEach(b => b.onclick = () => ctShow(b.dataset.v));
  $('#ct-open').onclick = () => window.open('/catalog/', '_blank');
  $('#ct-site').onclick = () => download('/api/catalog/site.zip', `Buxoro_eksport_katalogi_${ctToday()}.zip`);
  $$('#ct-price button').forEach(b => b.onclick = () => download('/api/catalog/pricelist.xlsx?lang=' + b.dataset.l, `Bukhara_export_price_list_${b.dataset.l}.xlsx`));
  $('#ct-setb').onclick = ctSettings;
  $('#ct-add').onclick = ctAddModal;
  $('#ct-bulk').onclick = ctBulkModal;
  let tm; $('#ct-q').oninput = e => { clearTimeout(tm); tm = setTimeout(() => { CT.q = e.target.value; ctList(); }, 180); };
  $('#ct-st').onchange = e => { CT.st = e.target.value; ctList(); };
  window.addEventListener('message', e => {   // витрина (iframe) ичидаги «✎ Tahrirlash»
    if (!e.data || e.data.type !== 'bec-edit' || !e.data.inn) return;
    ctOpen(e.data.inn, e.data.product);
  });
}
function ctShow(v) {
  CT.view = v;
  $$('#ct-view button').forEach(b => b.classList.toggle('on', b.dataset.v === v));
  $('#ct-listw').hidden = v !== 'list'; $('#ct-show').hidden = v !== 'show'; $('#ct-inq').hidden = v !== 'inq'; $('#ct-ed').hidden = true;
  $('#ct-kpi').hidden = v === 'show';
  if (v === 'list') ctList();
  if (v === 'show') { const f = $('#ct-frame'); f.src = '/catalog/?admin=1&t=' + Date.now(); }
  if (v === 'inq') ctInq().catch(e => toast(e.message, true));
}
function ctSeed() {
  const s = CT.ov.seed, el = $('#ct-seedb');
  if (!s || s.applied) { el.hidden = true; return; }
  el.hidden = false;
  el.innerHTML = `<div style="flex:1"><b>Тайёр пакет: ${esc(s.title)}</b><span>${s.companies} корхона · ${s.products} маҳсулот — расмлар, нархлар, 3 тилдаги тавсифлар ва сертификатлар билан. Юклашдан олдин база заҳираси олинади.</span></div>
    <button class="btn primary" id="ct-seed-go">📥 Каталогга юклаш</button>`;
  $('#ct-seed-go').onclick = async () => {
    $('#ct-seed-go').disabled = true;
    try { const r = await ctPost('/api/catalog/seed/apply'); toast(`Юкланди: ${r.companies} корхона, ${r.products} маҳсулот, ${r.photos} расм, ${r.docs} ҳужжат`); await ctLoad(); ctShow('list'); }
    catch (e) { toast(e.message, true); $('#ct-seed-go').disabled = false; }
  };
}
function ctKpi() {
  const k = CT.ov.kpi;
  const box = (l, v, d, cls = '', act = '') => `<div class="kpi ${cls} ${act ? 'click' : ''}" ${act ? `data-act="${act}"` : ''}><div class="l">${l}</div><div class="v">${v}</div><div class="d">${d}</div></div>`;
  $('#ct-kpi').innerHTML = [
    box('Корхоналар', fmt0(k.companies), `${k.published} эълон · ${k.draft} қоралама`, 'accent', 'f:'),
    box('Маҳсулотлар', fmt0(k.products), `${k.p_published} эълон қилинган`, 'accent'),
    box('ГТД шаблонлари', fmt0(k.templates), 'тўлдирилиши керак', '', 'f:templates'),
    box('Расмсиз', fmt0(k.no_photo), 'маҳсулот', k.no_photo ? 'gold' : '', 'f:photos'),
    box('Нархсиз', fmt0(k.no_price), `${k.expired} та нарх муддати ўтган`, k.no_price || k.expired ? 'gold' : '', 'f:prices'),
    box('Сўровлар', fmt0(k.inq_open), `${k.inq_new} янги · очиқ`, k.inq_new ? 'gold' : '', 'inq'),
  ].join('');
  $$('#ct-kpi [data-act]').forEach(b => b.onclick = () => { const a = b.dataset.act; if (a === 'inq') return ctShow('inq'); CT.wf = a.slice(2); ctShow('list'); });
}

// ----------------------------------------------------------------- companies list
function ctList() {
  const rows = CT.ov.companies.filter(c => (!CT.st || c.status === CT.st) && (!CT.wf || c.warn.includes(CT.wf)) && smatch(CT.q, c.name, c.reg_name, c.inn, ...(c.cats || [])));
  const wn = {}; CT.ov.companies.forEach(c => c.warn.forEach(w => wn[w] = (wn[w] || 0) + 1));
  $('#ct-wf').innerHTML = `<button class="ct-chip ${!CT.wf ? 'on' : ''}" data-w="">Барчаси</button>` + Object.keys(CT_WARN).filter(w => wn[w]).map(w => `<button class="ct-chip ${CT.wf === w ? 'on' : ''}" data-w="${w}">${esc(CT_WARN[w])} · ${wn[w]}</button>`).join('');
  $$('#ct-wf [data-w]').forEach(b => b.onclick = () => { CT.wf = b.dataset.w; ctList(); });
  const tb = $('#ct-t tbody');
  if (!CT.ov.companies.length) { tb.innerHTML = `<tr><td colspan="8" class="empty" style="padding:30px;text-align:center">Каталог бўш. «+ Корхона қўшиш» ёки «ГТД'дан барча экспортёрлар» тугмасини босинг — корхона эскпорт қилган маҳсулотлар ТН ВЭД бўйича шаблон бўлиб тушади.</td></tr>`; return; }
  const dn = c => (S.districts.find(d => d.code === c.district_code) || {}).name_uz || '';
  tb.innerHTML = rows.map(c => `<tr class="row" data-inn="${c.inn}">
    <td><div class="ct-nm">${c.logo ? `<img class="ct-logo" src="${c.logo}" alt="">` : `<div class="ct-logo">${esc(ctInitials(c.name))}</div>`}<div><b>${esc(ctTypo(c.name))}${c.featured ? ' ★' : ''}</b><span>${c.inn} · ${esc(short(dn(c)))}</span></div></div></td>
    <td style="font-size:12.5px;max-width:220px">${c.cats.map(k => esc(ctCat(k))).join(', ') || '<span class="sub">—</span>'}</td>
    <td class="num"><b>${c.n_pub}</b> / ${c.n - c.n_tpl}${c.n_tpl ? `<div class="sub" style="font-size:11px">+${c.n_tpl} шаблон</div>` : ''}</td>
    <td class="num">${c.n - c.n_tpl ? `${c.n_photo}/${c.n - c.n_tpl}` : '—'}</td>
    <td class="num">${c.n - c.n_tpl ? `${c.n_price}/${c.n - c.n_tpl}` : '—'}</td>
    <td><div class="ct-sc"><div class="ct-bar" style="width:90px"><i style="width:${c.score}%;background:${c.score >= 80 ? 'var(--ok)' : c.score >= 50 ? 'var(--gold)' : 'var(--bad)'}"></i></div>${c.score}%</div>
      <div class="ct-warn" style="margin-top:4px">${c.warn.slice(0, 3).map(w => `<span class="pill ${['price_expired', 'doc_expired'].includes(w) ? 'bad' : 'gray'}">${esc(CT_WARN[w] || w)}</span>`).join('')}${c.warn.length > 3 ? `<span class="pill gray">+${c.warn.length - 3}</span>` : ''}</div></td>
    <td>${ctPill(CT_ST, c.status)}</td>
    <td style="font-size:12px;white-space:nowrap">${dmy((c.updated_at || '').slice(0, 10))}</td></tr>`).join('') || `<tr><td colspan="8" class="empty">Филтрга мос корхона йўқ</td></tr>`;
  $$('#ct-t tr.row').forEach(r => r.onclick = () => ctOpen(r.dataset.inn));
  $('#ct-cnt').textContent = `${rows.length} / ${CT.ov.companies.length}`;
}

// ----------------------------------------------------------------- add company / bulk
async function ctAddModal() {
  const m = ctModal('ct-add', `<div class="ct-m"><h2>Корхонани каталогга қўшиш</h2><p class="sub" style="margin:4px 0 12px">Реестрдан қидиринг (ИНН ёки ном, лотин/кирилл фарқсиз). Корхона 2 йил ичида экспорт қилган ҳар бир ТН ВЭД коди «шаблон» маҳсулот бўлиб тушади — фақат расм, нарх ва тавсифни тўлдирасиз.</p>
    <input type="text" id="ct-aq" placeholder="ИНН ёки корхона номи…" style="width:100%;margin-bottom:10px"><div class="ct-pick" id="ct-apick"><div class="pempty" style="padding:14px">Юкланмоқда…</div></div></div>`, 'sm');
  m.querySelector('.mdl').style.width = 'min(640px,100%)';
  const draw = async () => {
    const q = $('#ct-aq').value.trim();
    const rows = await api('/api/catalog/candidates?q=' + encodeURIComponent(q));
    $('#ct-apick').innerHTML = rows.map(r => `<div class="r ${r.in_catalog ? 'dis' : ''}" data-inn="${r.inn}"><div><b>${esc(r.name)}</b><span>${r.inn} · ${esc(short((S.districts.find(d => d.code === r.district_code) || {}).name_uz || ''))}${r.in_catalog ? ' · каталогда бор' : ''}</span></div><span class="v">${r.export ? fmt(r.export) + ' минг $' : ''}</span></div>`).join('') || '<div class="pempty" style="padding:14px">Топилмади</div>';
    $$('#ct-apick .r').forEach(r => r.onclick = async () => {
      if (r.classList.contains('dis')) return ctClose('ct-add') || ctOpen(r.dataset.inn);
      try { const res = await ctPost('/api/catalog/company/add', { inn: r.dataset.inn }); toast(`Қўшилди · ${res.templates || 0} та ГТД шаблон`); ctClose('ct-add'); await ctLoad(); ctOpen(r.dataset.inn); }
      catch (e) { toast(e.message, true); }
    });
  };
  let tm; $('#ct-aq').oninput = () => { clearTimeout(tm); tm = setTimeout(() => draw().catch(e => toast(e.message, true)), 250); };
  $('#ct-aq').focus(); draw().catch(e => toast(e.message, true));
}
function ctBulkModal() {
  const y = (S.status && S.status.last_date ? +S.status.last_date.slice(0, 4) : new Date().getFullYear());
  ctModal('ct-bulk', `<div class="ct-m"><h2>ГТД'дан барча экспортёрлар — шаблон</h2>
    <p class="sub" style="margin:4px 0 14px">Танланган йилдан бери экспорт қилган (Бухоро деб ҳисобланадиган, БНПЗ дан ташқари) ва ҳали каталогда йўқ ҳар бир корхона «Қоралама» бўлиб қўшилади, унинг ТН ВЭД кодлари — «Шаблон» маҳсулотлар. Сайтда ҳеч нарса кўринмайди — эълон қилинганда чиқади.</p>
    <div class="ct-f"><label>Қайси йилдан<input type="number" id="ct-by" value="${y - 1}"></label><label>Камида экспорт (минг $)<input type="number" id="ct-bm" value="10"></label>
    <label class="w" style="flex-direction:row;align-items:center;gap:8px;text-transform:none"><input type="checkbox" id="ct-bp"> Жисмоний шахсларни ҳам (14 хонали ЖШШИР)</label></div>
    <div class="foot" style="display:flex;justify-content:flex-end;gap:10px;margin-top:16px"><button class="btn" data-c>Бекор</button><button class="btn primary" id="ct-bgo">Шаблон яратиш</button></div></div>`, 'sm');
  $('#ct-bulk [data-c]').onclick = () => ctClose('ct-bulk');
  $('#ct-bgo').onclick = async () => {
    $('#ct-bgo').disabled = true; toast('Шаблонлар яратилмоқда…');
    try { const r = await ctPost('/api/catalog/templates/bulk', { year_from: +$('#ct-by').value, min_value: +$('#ct-bm').value, persons: $('#ct-bp').checked });
      toast(`Қўшилди: ${r.added} корхона, ${r.templates} шаблон маҳсулот`); ctClose('ct-bulk'); await ctLoad(); ctShow('list'); }
    catch (e) { toast(e.message, true); $('#ct-bgo').disabled = false; }
  };
}

// ----------------------------------------------------------------- company editor
async function ctOpen(inn, productId) {
  if (CT.dirty && CT.inn !== inn && !confirm('Сақланмаган ўзгаришлар бор. Давом этилсинми?')) return;
  if ($('#p-cat').classList.contains('active') === false) { go('cat', { inn, product: productId }); return; }
  CT.inn = inn; CT.det = await api('/api/catalog/company?inn=' + inn); CT.dirty = false;
  $('#ct-listw').hidden = true; $('#ct-show').hidden = true; $('#ct-inq').hidden = true; $('#ct-kpi').hidden = true; $('#ct-ed').hidden = false;
  $$('#ct-view button').forEach(b => b.classList.remove('on'));
  ctEditor();
  window.scrollTo(0, 0);
  if (productId) { const p = CT.det.products.find(x => x.id === productId); if (p) ctProduct(p); }
}
function ctBack() { if (CT.dirty && !confirm('Сақланмаган ўзгаришлар бор. Чиқилсинми?')) return; CT.dirty = false; CT.inn = null; ctLoad().then(() => ctShow('list')); }
function ctLangFill(obj, fields) {
  const n = fields.filter(f => (obj[f] || '').trim()).length;
  return n === 0 ? '' : n >= fields.length ? 'ok' : 'part';
}
function ctEditor() {
  const d = CT.det, c = d.company, I = ctI();
  const dname = (S.districts.find(x => x.code === d.reg.district_code) || {}).name_uz || '';
  const logo = d.media.find(m => m.id === c.logo), cover = d.media.find(m => m.id === c.cover);
  const gal = d.media.filter(m => m.kind === 'photo'), docs = d.media.filter(m => m.kind === 'doc');
  $('#ct-ed').innerHTML = `
  <div class="ct-head">
    <button class="btn" id="ce-back">← Рўйхат</button>
    ${logo ? `<img class="ct-logo" src="${logo.thumb_src}" alt="">` : `<div class="ct-logo">${esc(ctInitials(ctName(c.i18n.uz.name ? { uz: c.i18n.uz.name } : d.default_names)))}</div>`}
    <div><h1>${esc(ctTypo(c.i18n.uz.name || c.i18n.ru.name || c.i18n.en.name || d.reg.name))}</h1>
      <div class="meta">ИНН ${c.inn} · ${esc(dname)} · реестрда: ${esc(d.reg.name || '')} · <a href="#" id="ce-prof">Корхона профили</a></div></div>
    <div class="right">
      <div class="seg" id="ce-st">${['draft', 'published', 'hidden'].map(s => `<button data-s="${s}" class="${c.status === s ? 'on' : ''}">${CT_ST[s][1]}</button>`).join('')}</div>
      <button class="btn" id="ce-view" title="Сайтда қандай кўринади">👁 Витрина</button>
    </div>
  </div>
  <div class="ct-grid"><div>
    <div class="panel" style="margin-bottom:14px"><h2>Асосий маълумот <span class="hint">харидор кўрадиган матнлар — 3 тилда; бўш тил бошқа тилдан кўрсатилади</span></h2>
      <div class="ct-lt" id="ce-lt">${CT_LANGS.map(([l, n]) => `<button data-l="${l}" class="${CT.lang === l ? 'on' : ''}"><i class="${ctLangFill(c.i18n[l], ['name', 'tagline', 'about'])}"></i>${n}</button>`).join('')}<a class="tr" href="#" id="ce-tr" title="Бошқа тилдаги матнни Google Translate'да очиш">🌐 Таржима ёрдамчиси</a></div>
      ${CT_LANGS.map(([l]) => `<div class="ct-f" data-lp="${l}" ${CT.lang === l ? '' : 'hidden'}>
        <label class="w">Корхона номи<input type="text" data-i="${l}.name" value="${esc(c.i18n[l].name)}" placeholder="${esc(d.default_names[l] || '')}"></label>
        <label class="w">Қисқа шиор (1 қатор) <span class="hint">масалан: «100% пахтадан ип, мато ва эко-сумкалар»</span><input type="text" data-i="${l}.tagline" value="${esc(c.i18n[l].tagline)}"></label>
        <label class="w">Корхона ҳақида <span class="hint">тарих, ускуналар, қувват, сифат назорати, ҳамкор давлатлар — 3–6 гап</span><textarea class="big" data-i="${l}.about">${esc(c.i18n[l].about)}</textarea></label>
        <label>Манзил<input type="text" data-i="${l}.address" value="${esc(c.i18n[l].address)}"></label>
        <label>Ишлаб чиқариш қуввати<input type="text" data-i="${l}.capacity" value="${esc(c.i18n[l].capacity)}" placeholder="масалан: 500 т/ой"></label>
      </div>`).join('')}
      <div class="ct-f" style="margin-top:12px">
        <label>Ташкил этилган йил<input type="number" id="ce-founded" value="${c.founded ?? ''}"></label>
        <label>Ходимлар сони<input type="number" id="ce-emp" value="${c.employees ?? ''}"></label>
        <label class="w">Етказиб бериш шартлари (Incoterms)<div class="ct-chips" id="ce-inc">${I.incoterms.map(x => `<button type="button" class="ct-chip ${c.incoterms.includes(x) ? 'on' : ''}" data-v="${x}">${x}</button>`).join('')}</div></label>
        <label class="w">Тўлов шартлари<div class="ct-chips" id="ce-pay">${Object.entries(I.payment).map(([k, v]) => `<button type="button" class="ct-chip ${c.payment.includes(k) ? 'on' : ''}" data-v="${k}">${esc(v.uz)}</button>`).join('')}</div></label>
        <label class="w">Мақсадли бозорлар <span class="hint">ISO кодлар вергул билан: KZ, KG, AF, RU, CN … — сайтда давлат номи чиқади</span><input type="text" id="ce-mk" value="${esc(c.markets.join(', '))}"></label>
        <label class="w" style="flex-direction:row;gap:8px;align-items:center;text-transform:none;letter-spacing:0;font-size:13px"><input type="checkbox" id="ce-sm" ${c.show_markets ? 'checked' : ''}> Божхона маълумотидан «Экспорт тажрибаси» (давлатлар) кўрсатилсин</label>
        <label class="w" style="flex-direction:row;gap:8px;align-items:center;text-transform:none;letter-spacing:0;font-size:13px"><input type="checkbox" id="ce-ft" ${c.featured ? 'checked' : ''}> ★ Тавсия этилган (рўйхат бошида)</label>
        <label class="w">Веб-сайт (ички) <span class="hint">сайтга чиқмайди — харидор бошқарма орқали боғланади</span><input type="text" id="ce-web" value="${esc(c.website || '')}"></label>
        <label class="w">Ички изоҳ <span class="hint">манба, эслатма, нимани сўраш керак — сайтга чиқмайди</span><textarea id="ce-note">${esc(c.note || '')}</textarea></label>
      </div>
    </div>
    <div class="panel" style="margin-bottom:14px"><h2>Маҳсулотлар <span class="hint">${d.products.length} та · карточкани босинг — расм, нарх, 3 тил</span>
      <span style="margin-left:auto;display:flex;gap:8px"><button class="btn sm" id="ce-tplall" ${d.products.some(p => p.status === 'template') ? '' : 'hidden'}>Шаблонларни қораламага</button><button class="btn sm primary" id="ce-padd">+ Янги маҳсулот</button></span></h2>
      <div class="ct-pgrid" id="ce-prods"></div>
      ${d.templates.length ? `<h2 style="margin-top:18px">ГТД'да бор, каталогда йўқ <span class="hint">божхона маълумоти бўйича корхона экспорт қилган бошқа ТН ВЭД кодлари</span></h2>
        <div>${d.templates.map(h => `<div class="ct-tpl"><span class="hs">${h.hs10}</span><span>${esc(ctSub(h.cat2) || h.sprav2 || '')}${h.gtd_desc ? `<div class="sub" style="font-size:11.5px">${esc(h.gtd_desc)}</div>` : ''}</span><span class="v">${fmt(h.value)} минг $ · ${esc(h.countries.slice(0, 3).join(', '))}</span><button class="btn sm" data-tpl="${h.hs10}">+ Қўшиш</button></div>`).join('')}</div>` : ''}
    </div>
    <div class="panel" style="margin-bottom:14px"><h2>Корхона расмлари <span class="hint">цех, ускуналар, омбор, кўргазмалар — сайтда «Ишлаб чиқариш» галереяси</span></h2>
      <div class="ct-drop" id="ce-gdrop">📷 Расмларни шу ерга ташланг ёки босиб танланг (бир нечта)</div>
      <div class="ct-ph" id="ce-gal">${gal.map((m, i) => ctThumb(m, i, gal.length, true)).join('')}</div></div>
    <div class="panel" style="margin-bottom:14px"><h2>Сертификатлар ва ҳужжатлар <span class="hint">«Сайтда» белгиланган ва муддати ўтмаганлари харидорга кўринади</span>
      <label class="btn sm" style="margin-left:auto;cursor:pointer">📎 Файл қўшиш<input type="file" id="ce-doc" multiple accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx" hidden></label></h2>
      <div class="tw"><table class="ct-docs"><thead><tr><th>Номи</th><th style="width:150px">Тури</th><th style="width:140px">Амал қилади</th><th style="width:70px">Сайтда</th><th style="width:90px"></th></tr></thead><tbody>
      ${docs.map(m => `<tr data-m="${m.id}" class="${m.valid_until && m.valid_until < ctToday() ? 'exp' : ''}"><td><input type="text" data-f="title" value="${esc(m.title || m.filename)}"></td>
        <td><select data-f="doc_type">${Object.entries(I.doc_types).map(([k, v]) => `<option value="${k}" ${m.doc_type === k ? 'selected' : ''}>${esc(v.uz)}</option>`).join('')}</select></td>
        <td><input type="date" data-f="valid_until" value="${m.valid_until || ''}"></td><td style="text-align:center"><input type="checkbox" data-f="is_public" ${m.is_public ? 'checked' : ''}></td>
        <td style="white-space:nowrap"><a class="ib" href="${m.src}" target="_blank" title="Очиш">↗</a><button class="ib del" data-del="${m.id}" title="Ўчириш">✕</button></td></tr>`).join('') || '<tr><td colspan="5" class="pempty">Ҳужжат йўқ — сертификат (ISO, HALAL, OEKO-TEX, мувофиқлик, санитария), каталог PDF, прайс</td></tr>'}
      </tbody></table></div></div>
  </div>
  <aside class="ct-side">
    <div class="panel"><h2>Тўлиқлик <span class="hint" style="margin-left:auto;font-family:'IBM Plex Mono',monospace">${d.score}%</span></h2>
      <div class="ct-bar"><i style="width:${d.score}%;background:${d.score >= 80 ? 'var(--ok)' : d.score >= 50 ? 'var(--gold)' : 'var(--bad)'}"></i></div>
      <div class="ct-warn" style="margin-top:10px;max-width:none">${d.warn.map(w => `<span class="pill ${['price_expired', 'doc_expired'].includes(w) ? 'bad' : 'gray'}">${esc(CT_WARN[w] || w)}</span>`).join('') || '<span class="pill ok">Ҳаммаси тўлдирилган</span>'}</div></div>
    <div class="panel"><h2>Логотип ва муқова</h2>
      <div class="ct-up"><div class="box" id="ce-logo" title="Логотип (PNG шаффоф фон маъқул)">${logo ? `<img src="${logo.src}" alt="">` : 'Логотип<br>+'}</div>
        <div class="box cover" id="ce-cover" title="Муқова — кенг расм (цех, маҳсулот)">${cover ? `<img src="${cover.thumb_src}" alt="">` : 'Муқова расми<br>+'}</div></div>
      <div class="note">Расмни босинг ёки файлни ташланг. Браузер ўзи кичрайтиради (≤1600 px).</div></div>
    <div class="panel"><h2>Божхона маълумоти <span class="hint">ИНН бўйича, ўзгармайди</span></h2><div class="ct-cu">
      ${Object.entries(d.customs.years).map(([y, v]) => `<div class="row"><span>${y} йил экспорт</span><span class="mono">${fmt(v)} минг $</span></div>`).join('') || '<div class="sub">Экспорт маълумоти йўқ</div>'}
      ${d.customs.countries.length ? `<div style="margin-top:8px"><b style="font-size:12px">Давлатлар:</b> ${d.customs.countries.map(x => `${esc(x.name)}${x.iso ? '' : ' (?)'}`).join(', ')}</div>` : ''}</div></div>
    <div class="panel"><h2>Ички алоқа <span class="hint">сайтга чиқмайди</span></h2><div class="ct-cu">
      ${d.contacts ? `${d.contacts.director ? `<div class="row"><span>Раҳбар</span><span>${esc(d.contacts.director)}</span></div>` : ''}
        ${(() => { let ph = []; try { ph = JSON.parse(d.contacts.phones || '[]'); } catch (_) {} if (!ph.length && d.contacts.phone) ph = [d.contacts.phone]; return ph.map(p => `<div class="row"><span>Телефон</span><a class="tel" href="tel:${esc(p)}">${esc(fmtPhone(p))}</a></div>`).join(''); })()}
        ${d.contacts.email ? `<div class="row"><span>E-mail</span><span>${esc(d.contacts.email)}</span></div>` : ''}${d.contacts.address ? `<div class="row"><span>Манзил</span><span>${esc(d.contacts.address)}</span></div>` : ''}` : '<div class="sub">Алоқа киритилмаган</div>'}
      ${d.persons.map(p => `<div class="row"><span>${esc(p.role || 'Шахс')}</span><span>${esc(p.name)}</span></div>`).join('')}
      <div style="margin-top:8px"><a href="#" id="ce-prof2">Профилда таҳрирлаш →</a></div></div></div>
    <div class="panel"><h2>Хавфли амал</h2><button class="btn danger sm" id="ce-del">Каталогдан олиб ташлаш</button><div class="note">Маҳсулотлар ва расмлар ўчади (файллар «_olib_tashlangan» га кўчади). Реестр ва божхона маълумотига тегмайди.</div></div>
  </aside></div>
  <div class="ct-save"><span class="dirty" id="ce-dirty" hidden>● Сақланмаган ўзгаришлар</span><button class="btn" id="ce-cancel">Бекор қилиш</button><button class="btn primary" id="ce-save">Сақлаш</button></div>`;
  ctProducts();
  // wire
  $('#ce-back').onclick = ctBack; $('#ce-cancel').onclick = () => { CT.dirty = false; ctOpen(CT.inn); };
  $('#ce-prof').onclick = $('#ce-prof2').onclick = e => { e.preventDefault(); if (CT.dirty && !confirm('Сақланмаган ўзгаришлар йўқолади. Давом этилсинми?')) return; CT.dirty = false; openCompany(CT.inn); };
  $('#ce-view').onclick = () => window.open('/catalog/?admin=1#/c/' + c.slug, '_blank');
  $$('#ce-lt button').forEach(b => b.onclick = () => { CT.lang = b.dataset.l; $$('#ce-lt button').forEach(x => x.classList.toggle('on', x === b)); $$('#ct-ed [data-lp]').forEach(p => p.hidden = p.dataset.lp !== CT.lang); });
  $('#ce-tr').onclick = e => { e.preventDefault(); ctTranslate(c.i18n, CT.lang, ['about', 'tagline']); };
  const dirty = () => { CT.dirty = true; $('#ce-dirty').hidden = false; };
  $$('#ct-ed .ct-f input, #ct-ed .ct-f textarea').forEach(i => i.addEventListener('input', dirty));
  $$('#ce-inc .ct-chip, #ce-pay .ct-chip').forEach(b => b.onclick = () => { b.classList.toggle('on'); dirty(); });
  $$('#ce-st button').forEach(b => b.onclick = async () => {
    if (b.dataset.s === 'published' && !d.products.some(p => p.status === 'published')) toast('Диққат: эълон қилинган маҳсулот йўқ — корхона сайтда кўринмайди', true);
    try { await ctPost('/api/catalog/company/status', { inn: CT.inn, status: b.dataset.s }); c.status = b.dataset.s; $$('#ce-st button').forEach(x => x.classList.toggle('on', x === b)); toast('Ҳолат: ' + CT_ST[b.dataset.s][1]); } catch (e) { toast(e.message, true); }
  });
  $('#ce-save').onclick = ctSaveCompany;
  $('#ce-padd').onclick = () => ctProduct(null);
  $('#ce-tplall').onclick = async () => { if (!confirm('Барча шаблонлар «Қоралама» ҳолатига ўтказилсинми? (сайтда ҳали кўринмайди)')) return; await ctPost('/api/catalog/products/bulk', { inn: CT.inn, from_status: 'template', status: 'draft' }); ctOpen(CT.inn); };
  $$('#ct-ed [data-tpl]').forEach(b => b.onclick = async () => { await ctPost('/api/catalog/templates/add', { inn: CT.inn, hs: [b.dataset.tpl], status: 'draft' }); toast('Қоралама маҳсулот қўшилди'); await ctOpen(CT.inn); });
  ctDrop($('#ce-gdrop'), async files => { await ctUploadImages(files, { inn: CT.inn, kind: 'photo' }); ctOpen(CT.inn); });
  ctDrop($('#ce-logo'), async files => { await ctUploadImages([files[0]], { inn: CT.inn, kind: 'logo' }); ctOpen(CT.inn); });
  ctDrop($('#ce-cover'), async files => { await ctUploadImages([files[0]], { inn: CT.inn, kind: 'cover' }); ctOpen(CT.inn); });
  ctWireThumbs($('#ce-gal'), gal, () => ctOpen(CT.inn));
  $('#ce-doc').onchange = async e => {
    for (const f of e.target.files) {
      if (f.size > 60 * 1024 * 1024) { toast(f.name + ': 60 MB дан катта', true); continue; }
      const type = /серт|sert|cert|iso|halal|oeko/i.test(f.name) ? 'certificate' : /прайс|price|таклиф|offer/i.test(f.name) ? 'price' : /катал|catal|буклет|bukl/i.test(f.name) ? 'catalog' : 'other';
      try { await api('/api/catalog/doc/upload', { method: 'POST', headers: { 'X-Inn': CT.inn, 'X-Filename': encodeURIComponent(f.name), 'X-Title': encodeURIComponent(f.name.replace(/\.[^.]+$/, '')), 'X-Type': type, 'X-Public': type === 'price' ? '0' : '1' }, body: f }); }
      catch (er) { toast(er.message, true); }
    }
    toast('Ҳужжат қўшилди — турини ва муддатини текширинг'); ctOpen(CT.inn);
  };
  $$('#ct-ed .ct-docs tr[data-m]').forEach(tr => {
    const save = async () => { const g = k => tr.querySelector(`[data-f="${k}"]`);
      try { await ctPost('/api/catalog/media/update', { id: +tr.dataset.m, title: g('title').value, doc_type: g('doc_type').value, valid_until: g('valid_until').value, is_public: g('is_public').checked });
        tr.classList.toggle('exp', !!g('valid_until').value && g('valid_until').value < ctToday()); toast('Сақланди'); } catch (e) { toast(e.message, true); } };
    tr.querySelectorAll('[data-f]').forEach(i => i.onchange = save);
  });
  $$('#ct-ed [data-del]').forEach(b => b.onclick = async () => { if (!confirm('Ҳужжат ўчирилсинми?')) return; await ctPost('/api/catalog/media/delete', { id: +b.dataset.del }); ctOpen(CT.inn); });
  $('#ce-del').onclick = async () => { if (!confirm('Корхона каталогдан бутунлай олиб ташлансинми? Маҳсулотлар ва расмлар ҳам ўчади.')) return; await ctPost('/api/catalog/company/delete', { inn: CT.inn }); CT.dirty = false; toast('Олиб ташланди'); ctBack(); };
}
function ctThumb(m, i, n, titled) {
  return `<div class="it ${i === 0 && !titled ? 'first' : ''}" data-m="${m.id}" title="${esc(m.title || m.filename || '')}"><img src="${m.thumb_src}" alt="">${i === 0 && !titled ? '<span class="cap">Асосий</span>' : ''}
    <div class="ops"><button data-mv="-1" title="Чапга">‹</button>${!titled && i ? '<button data-cv title="Асосий қилиш">★</button>' : ''}${titled ? '<button data-tt title="Изоҳ">✎</button>' : ''}<button data-rm title="Ўчириш">✕</button><button data-mv="1" title="Ўнгга">›</button></div></div>`;
}
function ctWireThumbs(box, list, after) {
  box.querySelectorAll('.it').forEach(it => {
    const id = +it.dataset.m, idx = list.findIndex(x => x.id === id);
    it.querySelectorAll('[data-mv]').forEach(b => b.onclick = async () => {
      const j = idx + (+b.dataset.mv); if (j < 0 || j >= list.length) return;
      const ids = list.map(x => x.id); [ids[idx], ids[j]] = [ids[j], ids[idx]];
      await ctPost('/api/catalog/reorder', { table: 'media', ids }); after();
    });
    const cv = it.querySelector('[data-cv]'); if (cv) cv.onclick = async () => { await ctPost('/api/catalog/media/update', { id, as_cover: true }); after(); };
    const tt = it.querySelector('[data-tt]'); if (tt) tt.onclick = async () => { const v = prompt('Расм изоҳи (сайтда кўринади):', list[idx].title || ''); if (v === null) return; await ctPost('/api/catalog/media/update', { id, title: v }); after(); };
    it.querySelector('[data-rm]').onclick = async () => { if (!confirm('Расм ўчирилсинми?')) return; await ctPost('/api/catalog/media/delete', { id }); after(); };
  });
}
function ctProducts() {
  const d = CT.det;
  const order = { published: 0, draft: 1, hidden: 2 };
  const ps = d.products.filter(p => p.status !== 'template').sort((a, b) => order[a.status] - order[b.status] || a.position - b.position);
  const tpl = d.products.filter(p => p.status === 'template');
  const nm = p => ctTypo(p.i18n.uz.name || p.i18n.ru.name || p.i18n.en.name);
  $('#ce-prods').innerHTML = (ps.map(p => {
    const miss = CT_LANGS.filter(([l]) => !p.i18n[l].name).map(([l]) => l.toUpperCase());
    return `<div class="ct-pc" data-p="${p.id}"><div class="im">${p.photos[0] ? `<img src="${p.photos[0].thumb_src}" alt="">` : '📷 расм йўқ'}</div>
      <div class="bd"><div class="nm">${esc(nm(p))}</div><div class="pr">${ctPrice(p) || '<span class="sub">нарх йўқ</span>'}</div>
      <div class="fl">${ctPill(CT_ST, p.status)}${p.expired ? '<span class="pill bad">нарх эскирган</span>' : ''}${miss.length ? `<span class="pill gray">${miss.join('/')} йўқ</span>` : ''}${p.hs10 ? `<span class="pill gray">${p.hs10}</span>` : ''}</div></div></div>`;
  }).join('') || '<div class="pempty">Тайёр маҳсулот йўқ — «+ Янги маҳсулот» ёки қуйидаги шаблонни тўлдиринг</div>')
  + (tpl.length ? `<div style="grid-column:1/-1;margin-top:10px"><h2 style="font-size:13.5px;margin:6px 0 4px">ГТД шаблонлари · ${tpl.length} <span class="hint">корхона экспорт қилган ТН ВЭД кодлари — «Тўлдириш» босиб расм, нарх ва номни киритинг; керак бўлмаса ✕</span></h2>
      ${tpl.map(p => { const h = d.customs.hs.find(x => x.hs10 === p.hs10) || {};
        return `<div class="ct-tpl"><span class="hs">${p.hs10 || ''}</span><span>${esc(nm(p))}${h.gtd_desc ? `<div class="sub" style="font-size:11.5px">${esc(h.gtd_desc)}</div>` : ''}</span><span class="v">${h.value ? fmt(h.value) + ' минг $ · ' + esc((h.countries || []).slice(0, 3).join(', ')) : ''}</span>
          <span style="display:flex;gap:4px"><button class="btn sm" data-fill="${p.id}">Тўлдириш</button><button class="ib del" data-tdel="${p.id}" title="Шаблонни ўчириш">✕</button></span></div>`; }).join('')}</div>` : '');
  $$('#ce-prods .ct-pc').forEach(el => el.onclick = () => ctProduct(d.products.find(p => p.id === +el.dataset.p)));
  $$('#ce-prods [data-fill]').forEach(b => b.onclick = () => ctProduct(d.products.find(p => p.id === +b.dataset.fill)));
  $$('#ce-prods [data-tdel]').forEach(b => b.onclick = async () => { await ctPost('/api/catalog/product/delete', { id: +b.dataset.tdel }); ctOpen(CT.inn); });
}
async function ctSaveCompany() {
  const c = CT.det.company, i18n = { uz: {}, ru: {}, en: {} };
  $$('#ct-ed [data-i]').forEach(el => { const [l, f] = el.dataset.i.split('.'); i18n[l][f] = el.value; });
  const on = sel => $$(sel + ' .ct-chip.on').map(b => b.dataset.v);
  const body = { inn: CT.inn, status: c.status, slug: c.slug, i18n, founded: $('#ce-founded').value, employees: $('#ce-emp').value, website: $('#ce-web').value,
    incoterms: on('#ce-inc'), payment: on('#ce-pay'), markets: $('#ce-mk').value.toUpperCase().split(/[\s,;]+/).filter(x => /^[A-Z]{2}$/.test(x)),
    show_markets: $('#ce-sm').checked, featured: $('#ce-ft').checked, note: $('#ce-note').value };
  try { await ctPost('/api/catalog/company/save', body); CT.dirty = false; toast('Сақланди'); await ctOpen(CT.inn); ctLoad(); } catch (e) { toast(e.message, true); }
}
function ctTranslate(i18n, target, fields) {
  const src = CT_LANGS.map(([l]) => l).filter(l => l !== target).find(l => fields.some(f => (i18n[l][f] || '').trim()));
  if (!src) return toast('Таржима учун бошқа тилда матн йўқ', true);
  const text = fields.map(f => i18n[src][f]).filter(Boolean).join('\n\n');
  window.open(`https://translate.google.com/?sl=${src}&tl=${target}&text=${encodeURIComponent(text.slice(0, 4800))}&op=translate`, '_blank');
  toast('Таржимани текшириб, майдонга жойлаштиринг');
}

// ----------------------------------------------------------------- product modal
function ctProduct(p0) {
  const d = CT.det, I = ctI(), isNew = !p0;
  const p = p0 ? JSON.parse(JSON.stringify(p0)) : { id: null, status: 'draft', hs10: '', sku: '', i18n: { uz: {}, ru: {}, en: {} }, price: null, price_to: null, currency: 'USD', unit: 'pcs', incoterm: '', moq: null, moq_unit: '', price_date: '', price_valid: '', featured: 0, photos: [], cat1: null, cat2: null, cat_manual: false };
  let lang = CT.lang, dirty = false;
  const PF = [['name', 'Номи', 'text'], ['desc', 'Тавсиф — нимага ишлатилади, афзаллиги, нарх вариантлари', 'area'], ['specs', "Хусусиятлари — ҳар қатор «Номи: қиймати» (масалан «Материал: 100% пахта»)", 'area'], ['pack', 'Қадоқлаш', 'text'], ['capacity', 'Етказиб бериш ҳажми (масалан: 100 т/ой)', 'text'], ['lead', 'Етказиш муддати', 'text']];
  const units = Object.entries(I.units).map(([k, v]) => `<option value="${k}">${esc(v.ru)} (${k})</option>`).join('');
  const cats = Object.keys(I.cat1).sort((a, b) => ctCat(a).localeCompare(ctCat(b)));
  const m = ctModal('ct-pm', `<div class="ct-m">
    <h2>${isNew ? 'Янги маҳсулот' : esc(p.i18n.uz.name || p.i18n.ru.name || p.i18n.en.name || 'Маҳсулот')}</h2>
    <div class="top"><div class="seg" id="pm-st">${['template', 'draft', 'published', 'hidden'].map(s => `<button data-s="${s}" class="${p.status === s ? 'on' : ''}">${CT_ST[s][1]}</button>`).join('')}</div>
      <label style="display:flex;gap:6px;align-items:center;font-size:13px"><input type="checkbox" id="pm-ft" ${p.featured ? 'checked' : ''}> ★ Тавсия этилган</label>
      <span class="sub">${esc(d.company.i18n.uz.name || '')}</span></div>
    <div class="cols"><div>
      <div class="ct-drop" id="pm-drop">📷 Маҳсулот расмлари — ташланг ёки босинг<br><span class="sub" style="font-size:11.5px">биринчи расм — асосий (оқ фонли маҳсулот расми энг яхши)</span></div>
      <div class="ct-ph" id="pm-ph"></div>
      <div class="ct-hsinfo" id="pm-hsinfo"></div>
    </div><div>
      <div class="ct-lt" id="pm-lt">${CT_LANGS.map(([l, n]) => `<button data-l="${l}" class="${lang === l ? 'on' : ''}"><i class="${ctLangFill(p.i18n[l] || {}, ['name', 'desc'])}"></i>${n}</button>`).join('')}<a class="tr" href="#" id="pm-tr">🌐 Таржима ёрдамчиси</a></div>
      ${CT_LANGS.map(([l]) => `<div class="ct-f" data-plp="${l}" ${lang === l ? '' : 'hidden'}>${PF.map(([f, lab, t]) => `<label class="${t === 'area' || f === 'name' ? 'w' : ''}">${lab}${t === 'area' ? `<textarea data-pi="${l}.${f}" ${f === 'specs' ? 'class="big"' : ''}>${esc((p.i18n[l] || {})[f] || '')}</textarea>` : `<input type="text" data-pi="${l}.${f}" value="${esc((p.i18n[l] || {})[f] || '')}">`}</label>`).join('')}</div>`).join('')}
      <div class="ct-f" style="margin-top:12px">
        <label>ТН ВЭД коди<input type="text" id="pm-hs" value="${esc(p.hs10 || '')}" placeholder="10 хона (ёки 4/6)"></label>
        <label>Модел / код<input type="text" id="pm-sku" value="${esc(p.sku || '')}"></label>
        <label>Категория <span class="hint" id="pm-hscat"></span><select id="pm-c1"><option value="">— ТН ВЭД бўйича (автомат) —</option>${cats.map(k => `<option value="${esc(k)}" ${p.cat_manual && p.cat1 === k ? 'selected' : ''}>${esc(ctCat(k))}</option>`).join('')}</select></label>
        <label>Бўлим<select id="pm-c2"></select></label>
        <label>Нарх (дан)<input type="number" step="any" id="pm-price" value="${p.price ?? ''}"></label>
        <label>Нарх (гача) <span class="hint">оралиқ бўлса</span><input type="number" step="any" id="pm-price2" value="${p.price_to ?? ''}"></label>
        <label>Валюта<select id="pm-cur">${CT_CUR.map(x => `<option ${p.currency === x ? 'selected' : ''}>${x}</option>`).join('')}</select></label>
        <label>Нарх бирлиги<select id="pm-unit"><option value="">—</option>${units}</select></label>
        <label>Incoterms<select id="pm-inc"><option value="">— корхона шартлари —</option>${I.incoterms.map(x => `<option ${p.incoterm === x ? 'selected' : ''}>${x}</option>`).join('')}</select></label>
        <label>Нарх санаси <span class="hint">тижорат таклифи санаси</span><input type="date" id="pm-pd" value="${p.price_date || ''}"></label>
        <label>Нарх амал қилади (гача)<input type="date" id="pm-pv" value="${p.price_valid || ''}"></label>
        <label>Мин. партия<div style="display:flex;gap:6px"><input type="number" step="any" id="pm-moq" value="${p.moq ?? ''}"><select id="pm-mu" style="max-width:120px"><option value="">—</option>${units}</select></div></label>
      </div></div></div>
    <div class="foot"><div class="l">${isNew ? '' : '<button class="btn danger" id="pm-del">Ўчириш</button>'}</div><span class="sub" id="pm-dirty"></span><button class="btn" id="pm-cancel">Ёпиш</button><button class="btn primary" id="pm-save">Сақлаш</button></div></div>`);
  $('#pm-unit').value = p.unit || ''; $('#pm-mu').value = p.moq_unit || '';
  m._guard = () => !dirty || confirm('Маҳсулотдаги ўзгаришлар сақланмаган. Ёпилсинми?');
  const setDirty = () => { dirty = true; $('#pm-dirty').textContent = '● сақланмаган'; };
  $$('#ct-pm input, #ct-pm textarea, #ct-pm select').forEach(i => i.addEventListener('input', setDirty));
  $$('#ct-pm select').forEach(i => i.addEventListener('change', setDirty));
  $$('#pm-st button').forEach(b => b.onclick = () => { p.status = b.dataset.s; $$('#pm-st button').forEach(x => x.classList.toggle('on', x === b)); setDirty(); });
  $$('#pm-lt button').forEach(b => b.onclick = () => { lang = b.dataset.l; CT.lang = lang; $$('#pm-lt button').forEach(x => x.classList.toggle('on', x === b)); $$('#ct-pm [data-plp]').forEach(x => x.hidden = x.dataset.plp !== lang); });
  const collect = () => {
    const i18n = { uz: {}, ru: {}, en: {} }; $$('#ct-pm [data-pi]').forEach(el => { const [l, f] = el.dataset.pi.split('.'); i18n[l][f] = el.value; });
    return { id: p.id, inn: CT.inn, status: p.status, featured: $('#pm-ft').checked, i18n, hs10: $('#pm-hs').value, sku: $('#pm-sku').value, cat1: $('#pm-c1').value, cat2: $('#pm-c2').value,
      price: $('#pm-price').value, price_to: $('#pm-price2').value, currency: $('#pm-cur').value, unit: $('#pm-unit').value, incoterm: $('#pm-inc').value,
      price_date: $('#pm-pd').value, price_valid: $('#pm-pv').value, moq: $('#pm-moq').value, moq_unit: $('#pm-mu').value };
  };
  $('#pm-tr').onclick = e => { e.preventDefault(); const b = collect(); ctTranslate(b.i18n, lang, ['name', 'desc', 'specs']); };
  const drawSub = () => {
    const c1 = $('#pm-c1').value, subs = c1 ? ((CT.ov.cat_tree || {})[c1] || []) : [];
    $('#pm-c2').innerHTML = c1 ? `<option value="">—</option>` + subs.map(s => `<option value="${esc(s)}" ${p.cat2 === s ? 'selected' : ''}>${esc(ctSub(s))}</option>`).join('') : `<option value="">${esc(ctSub(p.hs_cat2) || '—')}</option>`;
    $('#pm-c2').disabled = !c1;
  };
  $('#pm-c1').onchange = () => { p.cat2 = null; drawSub(); setDirty(); };
  drawSub();
  const hsInfo = () => {
    const hs = $('#pm-hs').value.replace(/\D/g, '');
    const h = d.customs.hs.find(x => x.hs10 === hs) || (hs.length >= 4 ? d.customs.hs.find(x => x.hs10.startsWith(hs)) : null);
    $('#pm-hscat').textContent = p.hs_cat1 && !p.cat_manual ? '' : '';
    $('#pm-hsinfo').innerHTML = h ? `<b>Божхона (ИНН ${CT.inn}, ТН ВЭД ${h.hs10}):</b> ${Object.entries(h.years).map(([y, v]) => `${y} — ${fmt(v)} минг $`).join('; ')}${h.netto ? ` · жами ${fmt(h.netto)} т` : ''}<br>Давлатлар: ${esc(h.countries.join(', '))}${h.gtd_desc ? `<br>ГТД тавсифи: <i>${esc(h.gtd_desc)}</i>` : ''}${h.cat1 ? `<br>Категория (ТН ВЭД): ${esc(ctCat(h.cat1))} › ${esc(ctSub(h.cat2))}` : ''}`
      : hs ? 'Бу ТН ВЭД коди бўйича корхонанинг божхона экспорти топилмади.' : 'ТН ВЭД кодини киритинг — категория ва божхона маълумоти автомат чиқади.';
  };
  $('#pm-hs').addEventListener('input', hsInfo); hsInfo();
  const drawPh = () => { $('#pm-ph').innerHTML = p.photos.map((x, i) => ctThumb(x, i, p.photos.length, false)).join(''); ctWireThumbs($('#pm-ph'), p.photos, refreshPh); };
  const refreshPh = async () => { CT.det = await api('/api/catalog/company?inn=' + CT.inn); const np = CT.det.products.find(x => x.id === p.id); if (np) p.photos = np.photos; drawPh(); ctProducts(); };
  drawPh();
  const save = async (keepOpen) => {
    const b = collect();
    if (!Object.values(b.i18n).some(x => (x.name || '').trim())) { toast('Маҳсулот номини камида бир тилда киритинг', true); return false; }
    if (b.status === 'template') b.status = p.id ? 'draft' : 'draft';
    try { const r = await ctPost('/api/catalog/product/save', b); p.id = r.id; p.status = b.status; dirty = false; $('#pm-dirty').textContent = '✓ сақланди';
      $$('#pm-st button').forEach(x => x.classList.toggle('on', x.dataset.s === p.status));
      if (!keepOpen) { m._guard = null; ctClose('ct-pm'); ctOpen(CT.inn); } return true; }
    catch (e) { toast(e.message, true); return false; }
  };
  ctDrop($('#pm-drop'), async files => {
    if (!p.id) { toast('Аввал маҳсулот сақланади…'); if (!(await save(true))) return; }
    await ctUploadImages(files, { inn: CT.inn, kind: 'photo', product_id: p.id }); await refreshPh();
  });
  $('#pm-save').onclick = () => save(false);
  $('#pm-cancel').onclick = () => ctClose('ct-pm');
  const del = $('#pm-del'); if (del) del.onclick = async () => { if (!confirm('Маҳсулот ва унинг расмлари ўчирилсинми?')) return; await ctPost('/api/catalog/product/delete', { id: p.id }); m._guard = null; ctClose('ct-pm'); ctOpen(CT.inn); };
  setTimeout(() => { const f = $(`#ct-pm [data-pi="${lang}.name"]`); if (f && !f.value) f.focus(); }, 50);
}

// ----------------------------------------------------------------- site settings
function ctSettings() {
  const s = CT.ov.settings;
  const tri = (k, lab) => CT_LANGS.map(([l, n]) => `<label>${lab} — ${l.toUpperCase()}<input type="text" data-s="${k}.${l}" value="${esc((s[k] || {})[l] || '')}"></label>`).join('');
  ctModal('ct-set', `<div class="ct-m"><h2>Сайт созламалари</h2><p class="sub" style="margin:4px 0 14px">Харидор сўровлари бошқармага келади — алоқа маълумотлари сайт пастида ва «Сўров юбориш» ойнасида чиқади.</p>
    <div class="ct-f">${tri('title', 'Сайт номи')}<span></span>${tri('org', 'Бошқарма номи')}<span></span>${tri('address', 'Манзил')}<span></span>
      <label>E-mail (сўровлар шу манзилга)<input type="text" data-s="email" value="${esc(s.email || '')}"></label>
      <label>Телефон<input type="text" data-s="phone" value="${esc(s.phone || '')}"></label>
      <label>Telegram (@username)<input type="text" data-s="telegram" value="${esc(s.telegram || '')}"></label>
      <label>WhatsApp (рақам)<input type="text" data-s="whatsapp" value="${esc(s.whatsapp || '')}"></label>
      <label class="w">Сайт манзили (жойлангандан кейин) <span class="hint">масалан https://export.buxoro.uz — PDF каталогда чиқади</span><input type="text" data-s="site_url" value="${esc(s.site_url || '')}"></label>
      <label class="w">Форма сервери (ихтиёрий) <span class="hint">келажакдаги сайт API манзили — бўлмаса сўров e-mail/WhatsApp орқали юборилади</span><input type="text" data-s="form_url" value="${esc(s.form_url || '')}"></label>
      <label class="w" style="flex-direction:row;gap:8px;align-items:center;text-transform:none;letter-spacing:0;font-size:13px"><input type="checkbox" data-s="show_tin" ${s.show_tin ? 'checked' : ''}> Корхона ИНН (STIR) сайтда кўрсатилсин</label>
    </div><div class="foot" style="display:flex;justify-content:flex-end;gap:10px;margin-top:16px"><button class="btn" data-c>Бекор</button><button class="btn primary" id="cs-save">Сақлаш</button></div></div>`);
  $('#ct-set .mdl').style.width = 'min(820px,100%)';
  $('#ct-set [data-c]').onclick = () => ctClose('ct-set');
  $('#cs-save').onclick = async () => {
    const b = {}; $$('#ct-set [data-s]').forEach(el => { const [k, l] = el.dataset.s.split('.'); if (l) (b[k] = b[k] || {})[l] = el.value; else b[k] = el.type === 'checkbox' ? el.checked : el.value; });
    try { const r = await ctPost('/api/catalog/settings', b); CT.ov.settings = r.settings; toast('Сақланди'); ctClose('ct-set'); } catch (e) { toast(e.message, true); }
  };
}

// ----------------------------------------------------------------- inquiries (lids)
async function ctInq() {
  CT.inq = await api('/api/catalog/inquiries');
  const Q = CT.inq, f = CT.iq;
  const rows = Q.rows.filter(r => (!f.st || r.status === f.st) && (!f.ch || r.channel === f.ch) && smatch(f.q, r.buyer, r.contact, r.country, r.source, r.company, r.email, r.phone, r.message, r.notes, ...r.products.map(p => p.name)));
  $('#ct-inq').innerHTML = `<div class="panel ct-q"><div class="st">
      <button class="ct-chip ${!f.st ? 'on' : ''}" data-st="">Барчаси<b>${Q.rows.length}</b></button>${Object.entries(CT_Q).map(([k, v]) => `<button class="ct-chip ${f.st === k ? 'on' : ''}" data-st="${k}">${v[1]}<b>${Q.status[k] || 0}</b></button>`).join('')}
      <span style="margin-left:auto;display:flex;gap:8px;align-items:center"><span class="sub">Шартномалар: <b>${fmt(Q.amount_deal)}</b> минг $</span><input type="text" id="iq-q" placeholder="Қидирув…" value="${esc(f.q)}" style="min-width:180px">
        <select class="sel" id="iq-ch"><option value="">Барча каналлар</option>${Object.entries(CT_CH).map(([k, v]) => `<option value="${k}" ${f.ch === k ? 'selected' : ''}>${v}</option>`).join('')}</select>
        <button class="btn" id="iq-xl">📗 Excel</button><button class="btn primary" id="iq-new">+ Янги сўров</button></span></div>
    <div class="tw" style="max-height:66vh"><table class="ct-t"><thead><tr><th>№</th><th>Сана</th><th>Канал / манба</th><th>Давлат</th><th>Харидор</th><th>Корхона / маҳсулот</th><th>Ҳолат</th><th class="num">Сумма, минг $</th><th>Кейинги қадам</th></tr></thead><tbody>
    ${rows.map(r => `<tr class="row" data-id="${r.id}"><td class="mono">${r.id}</td><td style="white-space:nowrap">${dmy(r.at)}</td><td>${esc(CT_CH[r.channel] || r.channel || '')}<div class="sub" style="font-size:11.5px">${esc(r.source || '')}</div></td>
      <td>${esc(r.country || '')}</td><td><b>${esc(r.buyer || '')}</b><div class="sub" style="font-size:11.5px">${esc([r.contact, r.email, r.phone].filter(Boolean).join(' · '))}</div></td>
      <td>${esc(r.company || '—')}<div class="sub" style="font-size:11.5px">${esc(r.products.map(p => p.name).join('; '))}</div></td><td>${ctPill(CT_Q, r.status)}</td><td class="num">${r.amount != null ? fmt(r.amount) : ''}</td>
      <td style="font-size:12.5px">${esc(r.next_step || '')}${r.due ? `<div class="sub" style="font-size:11.5px;${r.due < ctToday() && !['deal', 'lost'].includes(r.status) ? 'color:var(--bad)' : ''}">${dmy(r.due)}</div>` : ''}</td></tr>`).join('') || `<tr><td colspan="9" class="empty" style="padding:26px;text-align:center">Сўров йўқ. Элчихона, кўргазма ёки сайт орқали келган ҳар бир харидор сўровини шу ерда қайд этинг — қайси канал натижа бераётгани кўринади.</td></tr>`}
    </tbody></table></div></div>`;
  $$('#ct-inq [data-st]').forEach(b => b.onclick = () => { f.st = b.dataset.st; ctInq(); });
  let tm; $('#iq-q').oninput = e => { clearTimeout(tm); tm = setTimeout(() => { f.q = e.target.value; ctInq().then(() => { const i = $('#iq-q'); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }); }, 300); };
  $('#iq-ch').onchange = e => { f.ch = e.target.value; ctInq(); };
  $('#iq-xl').onclick = () => download('/api/catalog/inquiries.xlsx', `Каталог сўровлари ${dmy(ctToday())}.xlsx`);
  $('#iq-new').onclick = () => ctInqModal(null);
  $$('#ct-inq tr.row').forEach(tr => tr.onclick = () => ctInqModal(Q.rows.find(r => r.id === +tr.dataset.id)));
}
async function ctInqModal(r0) {
  if (!CT.ov) await ctLoad();
  const r = r0 || { id: null, at: ctToday(), channel: 'embassy', status: 'new', product_ids: [] };
  const comps = CT.ov.companies;
  ctModal('ct-inqm', `<div class="ct-m"><h2>${r.id ? 'Сўров №' + r.id : 'Янги сўров'}</h2>
    <div class="top"><div class="seg" id="iq-st">${Object.entries(CT_Q).map(([k, v]) => `<button data-s="${k}" class="${r.status === k ? 'on' : ''}">${v[1]}</button>`).join('')}</div></div>
    <div class="ct-f">
      <label>Сана<input type="date" id="iq-at" value="${r.at || ctToday()}"></label>
      <label>Канал<select id="iq-chn">${Object.entries(CT_CH).map(([k, v]) => `<option value="${k}" ${r.channel === k ? 'selected' : ''}>${v}</option>`).join('')}</select></label>
      <label class="w">Манба <span class="hint">масалан: «Ўзбекистоннинг Польшадаги элчихонаси», «Canton Fair 2026», «Innoprom»</span><input type="text" id="iq-src" value="${esc(r.source || '')}"></label>
      <label>Харидор давлати<input type="text" id="iq-cn" value="${esc(r.country || '')}" list="iq-cl"></label>
      <label>Харидор компания<input type="text" id="iq-buyer" value="${esc(r.buyer || '')}"></label>
      <label>Алоқа шахси<input type="text" id="iq-ct" value="${esc(r.contact || '')}"></label>
      <label>E-mail<input type="text" id="iq-em" value="${esc(r.email || '')}"></label>
      <label>Телефон / WhatsApp<input type="text" id="iq-ph" value="${esc(r.phone || '')}"></label>
      <label>Корхона (каталогдан)<select id="iq-inn"><option value="">—</option>${comps.map(c => `<option value="${c.inn}" ${r.inn === c.inn ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select></label>
      <label class="w">Маҳсулотлар<div class="ct-plist" id="iq-pl"><span class="sub">Корхонани танланг</span></div></label>
      <label>Ҳажм<input type="text" id="iq-vol" value="${esc(r.volume || '')}" placeholder="масалан: 2 контейнер/ой"></label>
      <label>Кутилаётган сумма (минг $)<input type="number" step="any" id="iq-am" value="${r.amount ?? ''}"></label>
      <label class="w">Сўров матни<textarea id="iq-msg">${esc(r.message || '')}</textarea></label>
      <label>Кейинги қадам<input type="text" id="iq-next" value="${esc(r.next_step || '')}" placeholder="масалан: намуна юбориш"></label>
      <label>Муддат<input type="date" id="iq-due" value="${r.due || ''}"></label>
      <label class="w">Изоҳ (ички)<textarea id="iq-notes">${esc(r.notes || '')}</textarea></label>
    </div>
    <datalist id="iq-cl">${Object.keys(CT.ov.countries || {}).map(k => { let n = ''; try { n = new Intl.DisplayNames(['ru'], { type: 'region' }).of(k); } catch (_) {} return `<option value="${esc(n || k)}">`; }).join('')}</datalist>
    <div class="foot"><div class="l">${r.id ? '<button class="btn danger" id="iq-del">Ўчириш</button>' : ''}<button class="btn" id="iq-copy" title="Харидор маълумоти ва сўровни корхонага юбориш учун матн">📋 Корхонага матн</button></div><button class="btn" data-c>Ёпиш</button><button class="btn primary" id="iq-save">Сақлаш</button></div></div>`);
  $('#ct-inqm .mdl').style.width = 'min(860px,100%)';
  let st = r.status;
  $$('#iq-st button').forEach(b => b.onclick = () => { st = b.dataset.s; $$('#iq-st button').forEach(x => x.classList.toggle('on', x === b)); });
  const drawPl = async () => {
    const inn = $('#iq-inn').value; if (!inn) { $('#iq-pl').innerHTML = '<span class="sub">Корхонани танланг</span>'; return; }
    const det = await api('/api/catalog/company?inn=' + inn);
    const ps = det.products.filter(p => p.status !== 'template');
    $('#iq-pl').innerHTML = ps.map(p => `<label><input type="checkbox" value="${p.id}" ${(r.product_ids || []).includes(p.id) ? 'checked' : ''}> ${esc(p.i18n.uz.name || p.i18n.ru.name || p.i18n.en.name)}</label>`).join('') || '<span class="sub">Маҳсулот йўқ</span>';
  };
  $('#iq-inn').onchange = drawPl; drawPl();
  const body = () => ({ id: r.id, at: $('#iq-at').value, channel: $('#iq-chn').value, source: $('#iq-src').value, country: $('#iq-cn').value, buyer: $('#iq-buyer').value,
    contact: $('#iq-ct').value, email: $('#iq-em').value, phone: $('#iq-ph').value, inn: $('#iq-inn').value, product_ids: $$('#iq-pl input:checked').map(i => +i.value),
    volume: $('#iq-vol').value, amount: $('#iq-am').value, message: $('#iq-msg').value, status: st, next_step: $('#iq-next').value, due: $('#iq-due').value, notes: $('#iq-notes').value });
  $('#ct-inqm [data-c]').onclick = () => ctClose('ct-inqm');
  $('#iq-save').onclick = async () => { try { await ctPost('/api/catalog/inquiry/save', body()); toast('Сақланди'); ctClose('ct-inqm'); await ctLoad(); if (CT.view === 'inq') ctInq(); } catch (e) { toast(e.message, true); } };
  $('#iq-copy').onclick = () => {
    const b = body(), pn = $$('#iq-pl input:checked').map(i => i.parentElement.textContent.trim());
    const txt = [`Хорижий харидор сўрови${r.id ? ' №' + r.id : ''} (${dmy(b.at)})`, `Канал: ${CT_CH[b.channel] || ''}${b.source ? ' — ' + b.source : ''}`, b.country && `Давлат: ${b.country}`, b.buyer && `Компания: ${b.buyer}`,
      b.contact && `Алоқа шахси: ${b.contact}`, b.email && `E-mail: ${b.email}`, b.phone && `Телефон: ${b.phone}`, pn.length && `Маҳсулот: ${pn.join('; ')}`, b.volume && `Ҳажм: ${b.volume}`, b.message && `\n${b.message}`,
      `\nБухоро вилояти инвестициялар, саноат ва савдо бошқармаси`].filter(Boolean).join('\n');
    navigator.clipboard.writeText(txt).then(() => toast('Матн нусхаланди — корхонага Telegram орқали юборинг'), () => toast('Нусхалаб бўлмади', true));
  };
  const del = $('#iq-del'); if (del) del.onclick = async () => { if (!confirm('Сўров ўчирилсинми?')) return; await ctPost('/api/catalog/inquiry/delete', { id: r.id }); ctClose('ct-inqm'); await ctLoad(); ctInq(); };
}
// nav badge: yangi so'rovlar soni (sahifa ochilmasa ham)
setTimeout(() => api('/api/catalog/overview').then(d => { CT.ov = d; ctNav(); }).catch(() => {}), 1500);
