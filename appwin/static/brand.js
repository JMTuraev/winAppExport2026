/* AppWin: logo + header in the sidebar, user chip (name, role, admin, logout). Injected by the AppWin server. */
(function () {
  var LOGO = '<svg viewBox="0 0 64 64" aria-hidden="true"><defs><linearGradient id="awg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#149B8A"/><stop offset="1" stop-color="#0B564D"/></linearGradient></defs><rect x="2" y="2" width="60" height="60" rx="14" fill="url(#awg)"/><rect x="14" y="34" width="8" height="16" rx="2.5" fill="#fff"/><rect x="28" y="22" width="8" height="28" rx="2.5" fill="#fff"/><rect x="42" y="28" width="8" height="22" rx="2.5" fill="#fff" opacity=".92"/><path d="M15 27 L30 16 L38 21 L49 12" fill="none" stroke="#F1D27A" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="49" cy="12" r="4.2" fill="#B7912A" stroke="#fff" stroke-width="1.6"/></svg>';
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function initials(n) { return (n || '?').split(/\s+/).map(function (x) { return x[0]; }).slice(0, 2).join('').toUpperCase(); }
  function ready(fn) { if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn); else fn(); }
  ready(function () {
    var brand = document.querySelector('.side .brand');
    if (brand) {
      var tg = brand.querySelector('.tg');
      brand.innerHTML = '<div class="aw-logo">' + LOGO + '</div><div class="bt"><b>Eksport Monitor</b><span>Buxoro viloyati<br>Eksport bo\'limi</span></div>';
      if (tg) brand.appendChild(tg);
    }
    document.title = 'Eksport Monitor';
    // Chat — menyuda emas: o'ng pastki burchakdagi doimiy tugma (o'qilmaganlar soni bilan), bosilsa chat oynasi — chatwidget.js
    if (!window.EMChat && !document.getElementById('em-chat-js')) {
      var cw = document.createElement('script'); cw.id = 'em-chat-js'; cw.src = '/appwin/chatwidget.js'; document.body.appendChild(cw);
    }
    // Chatdan kelgan havolalar: /#reg/<INN> — korxona kartasi, /#iss/<id> — doska kartasi
    function route() {
      var m = (location.hash || '').match(/^#(reg|iss)\/?(.*)$/); if (!m || typeof go !== 'function') return;
      if (m[1] === 'reg') { go('reg', m[2] || undefined); return; }
      go('iss');
      if (m[2] && /^\d+$/.test(m[2])) {
        var id = +m[2], tries = 0;
        var t = setInterval(function () {
          tries++;
          var it = ((typeof B !== 'undefined' && B.issues) || []).find(function (i) { return i.id === id; });
          if (it && typeof openCard === 'function') { clearInterval(t); openCard(it); }
          else if (tries > 40) clearInterval(t);
        }, 250);
      }
    }
    window.addEventListener('hashchange', route);
    setTimeout(route, 600);
    var link = document.querySelector('link[rel~="icon"]') || document.createElement('link');
    link.rel = 'icon'; link.href = '/appwin/logo.svg'; document.head.appendChild(link);
    fetch('/api/auth/me').then(function (r) { return r.json(); }).then(function (d) {
      if (!d.user) { location.href = '/login'; return; }
      var u = d.user, side = document.querySelector('.side'); if (!side) return;
      var sa = u.role === 'superadmin';
      var el = document.createElement('div'); el.className = 'aw-user';
      el.innerHTML = '<div class="av' + (sa ? ' sa' : '') + '" title="' + esc(u.login) + '">' + esc(initials(u.name)) + '</div>' +
        '<div class="u"><b>' + esc(u.name) + '</b><span class="' + (sa ? 'sa' : '') + '">' + esc(sa ? 'Superadmin' : u.role_name) + '</span></div>' +
        '<div class="acts">' + (sa ? '<a href="/admin" title="Superadmin panel"><svg viewBox="0 0 24 24"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/></svg></a>' : '') +
        '<a href="/logout" title="Chiqish"><svg viewBox="0 0 24 24"><path d="M10 17l5-5-5-5M15 12H3M21 3v18"/></svg></a></div>';
      var foot = side.querySelector('.foot');
      if (foot) side.insertBefore(el, foot); else side.appendChild(el);
      if (d.server && d.server.readonly === false && d.online != null) el.title = d.online + ' xodim onlayn · server ' + (d.server.ip || '') + ':' + d.server.port;
    }).catch(function () {});
  });
})();
