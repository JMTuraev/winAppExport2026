/* AppWin Live — serverda kimdir ma'lumotni o'zgartirsa (GTD, korxona, vazifa, reja, sozlama…), barcha ochiq oynalar
   F5 siz o'zi yangilanadi. Injected by the AppWin server after app.js.
   - /api/live long-poll: server bump() qilganda darhol javob qaytadi (LAN, internet kerak emas).
   - O'z o'zgarishingiz (X-Client) bu oynani qayta yuklamaydi — app o'zi yangilaydi.
   - Konflikt himoyasi: oynada ish ochiq bo'lsa (modal, GTD tekshiruvi, saqlanmagan tahrir, yozish) yangilash kutib turadi
     va yuqorida ogohlantirish chiqadi; ish tugagach o'zi yangilanadi.
   - Server qayta ishga tushsa (yangi versiya) — sahifa to'liq qayta yuklanadi, ochiq bo'lim saqlanadi. */
(function () {
  'use strict';
  var CID = Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  var boot = '', ver = -1, fails = 0, stopped = false;
  var pending = [], stale = false, needReload = false, timer = null, running = false;
  var lastKey = 0, dirtyEl = null;

  // ---- this window's writes carry X-Client (so the server event can be ignored here); a successful save clears "unsaved"
  var _fetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    init = init || {};
    var method = String(init.method || (input && input.method) || 'GET').toUpperCase();
    if (method === 'GET' || method === 'HEAD') return _fetch(input, init);
    var h = new Headers(init.headers || (typeof Request !== 'undefined' && input instanceof Request ? input.headers : undefined));
    h.set('X-Client', CID);
    var url = typeof input === 'string' ? input : (input && input.url) || '';
    return _fetch(input, Object.assign({}, init, { headers: h })).then(function (r) {
      if (r.ok && !/\/api\/(auth|live)\b|\/preview\b/.test(url)) { dirtyEl = null; }
      return r;
    });
  };

  // ---- what counts as "the user is in the middle of something"
  document.addEventListener('keydown', function () { lastKey = Date.now(); }, true);
  document.addEventListener('input', function (e) {
    lastKey = Date.now();
    var t = e.target;
    if (t && t.closest && t.closest('#reg-prof, .mbg, #p-set, #pv, [contenteditable="true"]')) dirtyEl = t;
  }, true);

  function busy() {
    if (document.querySelector('.mbg:not([hidden])')) return 'oyna ochiq';
    if (document.querySelector('.ms-pop:not([hidden])')) return 'tanlov ochiq';
    var gd = document.getElementById('geo-drawer'); if (gd && gd.getAttribute('aria-hidden') === 'false') return 'panel ochiq';
    if ((typeof K !== 'undefined') && K.pv) return 'GTD tekshiruvi ochiq';
    if (Date.now() - lastKey < 4000) return 'yozyapsiz';
    if (dirtyEl) {
      if (dirtyEl.isConnected && dirtyEl.offsetParent !== null) return 'saqlanmagan tahrir';
      dirtyEl = null;
    }
    return '';
  }

  // ---- UI: small bar at the top (only while a refresh is waiting)
  var css = document.createElement('style');
  css.textContent =
    '.aw-live{position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:70;display:none;align-items:center;gap:12px;' +
    'background:#182029;color:#fff;padding:9px 10px 9px 14px;border-radius:10px;font-size:13px;box-shadow:0 8px 28px rgba(0,0,0,.25);max-width:min(760px,calc(100% - 32px))}' +
    '.aw-live.show{display:flex}.aw-live .dot{width:8px;height:8px;border-radius:50%;background:#eda100;flex:0 0 auto}' +
    '.aw-live .t{flex:1;line-height:1.35}.aw-live .t small{display:block;opacity:.7;font-size:12px}' +
    '.aw-live button{border:0;border-radius:7px;padding:6px 11px;font:inherit;font-size:12.5px;cursor:pointer;background:#1baf7a;color:#fff;white-space:nowrap}' +
    '.aw-live button.x{background:transparent;color:#fff;opacity:.6;padding:6px 8px}' +
    '.aw-pv-stale{border:1px solid #eda100;background:#fdf6e6;border-radius:8px;padding:10px 12px;margin:0 0 10px;font-size:13px;color:#5a3d00}' +
    '.aw-pv-stale button{margin-top:6px}';
  document.head.appendChild(css);
  var bar = document.createElement('div'); bar.className = 'aw-live';
  bar.innerHTML = '<span class="dot"></span><div class="t"></div><button class="go">Hozir yangilash</button><button class="x" title="Yopish">✕</button>';
  function mountBar() { if (!bar.isConnected) document.body.appendChild(bar); }
  bar.querySelector('.go').onclick = function () { apply(true); };
  bar.querySelector('.x').onclick = function () { bar.classList.remove('show'); };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function who(evs) {
    if (!evs.length) return 'Serverda ma\'lumot o\'zgardi';
    var e = evs[evs.length - 1];
    var s = e.name + ' · ' + e.ts + ' — ' + e.action + (e.detail ? ' (' + e.detail + ')' : '');
    return evs.length > 1 ? s + ' va yana ' + (evs.length - 1) + ' ta o\'zgarish' : s;
  }
  function note(msg) { if ((typeof toast !== 'undefined')) toast(msg); }

  // ---- GTD preview that another person's GTD change made out of date: block «Saqlash» until re-checked
  function markPreviewStale(evs) {
    if (!((typeof K !== 'undefined') && K.pv) || document.getElementById('aw-pv-stale')) return;
    var g = evs.filter(function (e) { return /^\/api\/uploads?\//.test(e.path) || /^\/api\/(reset|backups\/restore|customs|template)/.test(e.path); });
    if (!g.length) return;
    var box = document.getElementById('pv-checks'); if (!box) return;
    box.insertAdjacentHTML('afterbegin', '<div class="aw-pv-stale" id="aw-pv-stale"><b>Tekshiruv eskirdi.</b> ' + esc(who(g)) +
      '. Shu kun allaqachon saqlangan bo\'lishi mumkin — ikki marta yozilmasligi uchun faylni qayta tekshiring.<br>' +
      '<button class="btn primary sm" id="aw-pv-recheck">Qayta tekshirish</button></div>');
    var save = document.getElementById('pv-save'); if (save) { save.disabled = true; save.textContent = 'Avval qayta tekshiring'; }
    document.getElementById('aw-pv-recheck').onclick = function () {
      if ((typeof preview !== 'undefined') && K.file) preview(K.file, !!(K.pv && K.pv.replace));
    };
  }

  // ---- refresh the open page in place (as if its menu item was clicked, but scroll position is kept)
  async function refreshInPlace() {
    if (!((typeof loadStatus !== 'undefined') && (typeof loaders !== 'undefined') && (typeof S !== 'undefined'))) { location.reload(); return; }
    var y = window.scrollY;
    var nav = document.querySelector('.nav.active'); var p = nav && nav.dataset.p;
    var oldLast = S.status && S.status.last_date;
    await loadStatus();
    if (p === 'dash' && S.dash && S.dash.date === oldLast) S.dash = null;      // was on the latest day -> follow the new latest day
    if (p === 'reg' && (typeof R !== 'undefined') && R.inn) await loaders.reg(R.inn);
    else if (p && loaders[p]) await loaders[p]();
    window.scrollTo(0, y);
  }

  function saveSpot() {
    try {
      var nav = document.querySelector('.nav.active');
      sessionStorage.setItem('aw-live-spot', JSON.stringify({ p: nav && nav.dataset.p, inn: (typeof R !== 'undefined') ? R.inn : null, y: window.scrollY }));
    } catch (_) {}
  }
  function restoreSpot() {
    var spot = null; try { spot = JSON.parse(sessionStorage.getItem('aw-live-spot') || 'null'); sessionStorage.removeItem('aw-live-spot'); } catch (_) {}
    if (!spot || !spot.p || spot.p === 'dash') return;
    var n = 0, t = setInterval(function () {
      if (++n > 60) return clearInterval(t);
      if (!((typeof S !== 'undefined') && S.status && (typeof go !== 'undefined'))) return;
      clearInterval(t);
      go(spot.p, spot.inn || undefined);
      if (spot.y) setTimeout(function () { window.scrollTo(0, spot.y); }, 600);
    }, 250);
  }

  async function apply(force) {
    timer = null;
    if (running || (!stale && !needReload)) return;
    var b = force ? '' : busy();
    if (!force && document.hidden) return;                       // minimized: refresh when the window comes back
    if (b) {
      var sv = document.getElementById('pv-save');
      if (sv && document.getElementById('aw-pv-stale')) { sv.disabled = true; sv.textContent = 'Avval qayta tekshiring'; }
      mountBar();
      bar.querySelector('.t').innerHTML = esc(who(pending)) + '<small>Ma\'lumot yangilandi — ' + esc(b) + ', shuning uchun kutyapman. Tugatganingizdan so\'ng o\'zi yangilanadi.</small>';
      bar.classList.add('show');
      timer = setTimeout(apply, 1500);
      return;
    }
    var evs = pending; pending = []; stale = false;
    bar.classList.remove('show');
    if (needReload) { saveSpot(); location.reload(); return; }
    running = true;
    try { await refreshInPlace(); note('↻ ' + who(evs) + ' · ma\'lumot yangilandi'); }
    catch (e) { if ((typeof toast !== 'undefined')) toast(e.message || String(e), true); }
    finally { running = false; if (stale) schedule(); }
  }
  function schedule(delay) { if (!timer) timer = setTimeout(apply, delay == null ? 600 : delay); }
  document.addEventListener('visibilitychange', function () { if (!document.hidden && (stale || needReload)) schedule(100); });

  // ---- long-poll loop
  function poll() {
    if (stopped) return;
    _fetch('/api/live?v=' + ver + '&boot=' + encodeURIComponent(boot), { cache: 'no-store' })
      .then(function (r) {
        if (r.status === 401 || r.status === 403) { stopped = true; return null; }
        if (!r.ok) throw new Error('live ' + r.status);
        return r.json();
      })
      .then(function (d) {
        if (!d) return;
        fails = 0;
        if (!boot) { boot = d.boot; ver = d.v; }
        else if (d.boot !== boot) { boot = d.boot; ver = d.v; needReload = true; schedule(300); }     // server restarted / updated
        else {
          var others = (d.events || []).filter(function (e) { return e.client !== CID; });
          ver = d.v;
          if (others.length || d.missed) {
            pending = pending.concat(others); stale = true;
            markPreviewStale(others);
            schedule();
          }
        }
        setTimeout(poll, 30);
      })
      .catch(function () { fails++; setTimeout(poll, Math.min(15000, 1000 * fails)); });
  }

  function start() { restoreSpot(); setTimeout(poll, 800); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  window.AW_LIVE = { client: CID, state: function () { return { boot: boot, v: ver, stale: stale, busy: busy(), pending: pending.length }; } };
})();
