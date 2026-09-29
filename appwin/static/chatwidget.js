/* AppWin: bo'lim chati — o'ng pastki burchakda doim turadigan tugma (saytning barcha bo'limlari va Superadmin panelida).
   - Tugmada o'qilmagan xabarlar soni (badge); yangi xabar kelsa badge «urib» qo'yadi.
   - Bosilsa o'ng tomonda Telegram uslubidagi oyna (720px: chapda suhbatlar ro'yxati, o'ngda suhbat): /chat?embed=1
     (iframe, bir marta yuklanadi va saqlanadi; oyna 600px dan tor bo'lsa — bitta ustun).
   - Oynadan tashqarini bosish, Esc yoki tugmani qayta bosish — yopiladi. Yopiq paytda chat xabarlarni «o'qildi» qilmaydi.
   - Yuklanadi: brand.js (sayt) va admin.html. /chat (to'liq ekran) va /login da ko'rinmaydi.
   - Tashqaridan: EMChat.open() · EMChat.close() · EMChat.toggle() · EMChat.openHash('inn=123…' | 'room=5' | 'user=2'). */
(function () {
  'use strict';
  if (window.EMChat || window.top !== window) return;
  var P = location.pathname;
  if (P === '/chat' || P === '/login' || P.indexOf('/api/') === 0) return;

  var POLL_VIS = 5000, POLL_HID = 30000;
  var isOpen = false, frame = null, ready = false, pendingHash = null;
  var fab, panel, badge, timer = null, count = -1, stopped = false;

  var ICON_CHAT = '<svg class="ic-chat" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 11.5a8.4 8.4 0 0 1-8.5 8.3 8.9 8.9 0 0 1-3.6-.8L3 21l1.9-5.3A8.1 8.1 0 0 1 4 11.5 8.4 8.4 0 0 1 12.5 3.2 8.4 8.4 0 0 1 21 11.5z"/><path d="M8.5 10.5h8M8.5 14h5"/></svg>';
  var ICON_X = '<svg class="ic-x" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';

  var CSS = [
    '#em-chat-fab{position:fixed;right:22px;bottom:22px;width:56px;height:56px;border-radius:50%;border:0;padding:0;margin:0;box-sizing:border-box;',
    'background:linear-gradient(135deg,#149B8A 0%,#0B564D 100%);color:#fff;cursor:pointer;z-index:2147483000;display:flex;align-items:center;justify-content:center;',
    'box-shadow:0 10px 26px rgba(11,86,77,.38),0 2px 6px rgba(0,0,0,.18);transition:transform .18s ease,box-shadow .18s ease;-webkit-tap-highlight-color:transparent}',
    '#em-chat-fab:hover{transform:translateY(-2px);box-shadow:0 14px 32px rgba(11,86,77,.45),0 3px 8px rgba(0,0,0,.2)}',
    '#em-chat-fab:active{transform:scale(.96)}',
    '#em-chat-fab:focus-visible{outline:3px solid #F1D27A;outline-offset:3px}',
    '#em-chat-fab svg{position:absolute;width:27px;height:27px;stroke:currentColor;fill:none;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round;transition:transform .22s ease,opacity .18s ease}',
    '#em-chat-fab .ic-x{opacity:0;transform:rotate(-90deg) scale(.5);width:24px;height:24px;stroke-width:2.4}',
    '#em-chat-fab.open .ic-chat{opacity:0;transform:rotate(90deg) scale(.5)}',
    '#em-chat-fab.open .ic-x{opacity:1;transform:none}',
    '#em-chat-fab .b{position:absolute;top:-5px;right:-5px;min-width:23px;height:23px;padding:0 6px;border-radius:12px;box-sizing:border-box;',
    'background:#D63A3A;color:#fff;border:2px solid #fff;font:700 11.5px/19px "IBM Plex Sans",system-ui,"Segoe UI",Arial,sans-serif;text-align:center;letter-spacing:.2px;',
    'box-shadow:0 2px 6px rgba(0,0,0,.25);pointer-events:none;transition:transform .18s ease}',
    '#em-chat-fab .b[hidden]{display:none}',
    '#em-chat-fab.ring::after{content:"";position:absolute;inset:0;border-radius:50%;animation:emRing 1.1s ease-out 3;pointer-events:none}',
    '#em-chat-fab.ring .b{animation:emPop .5s ease-out}',
    '@keyframes emRing{from{box-shadow:0 0 0 0 rgba(20,155,138,.55)}to{box-shadow:0 0 0 18px rgba(20,155,138,0)}}',
    '@keyframes emPop{0%{transform:scale(.4)}60%{transform:scale(1.25)}100%{transform:scale(1)}}',
    '#em-chat-panel{position:fixed;right:22px;bottom:90px;width:720px;height:min(680px,calc(100vh - 112px));max-width:calc(100vw - 32px);',
    'background:#fff;border-radius:16px;overflow:hidden;z-index:2147482999;box-sizing:border-box;border:1px solid rgba(20,35,43,.1);',
    'box-shadow:0 24px 64px rgba(20,35,43,.32),0 4px 14px rgba(20,35,43,.14);transform-origin:calc(100% - 28px) calc(100% + 40px);',
    'opacity:0;visibility:hidden;pointer-events:none;transform:translateY(12px) scale(.96);transition:opacity .16s ease,transform .2s ease,visibility 0s linear .2s}',
    '#em-chat-panel.open{opacity:1;visibility:visible;pointer-events:auto;transform:none;transition:opacity .16s ease,transform .2s ease}',
    '#em-chat-panel iframe{width:100%;height:100%;border:0;display:block;background:#F4F6F5}',
    '#em-chat-panel .ld{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;gap:10px;color:#8A929C;',
    'font:13px "IBM Plex Sans",system-ui,"Segoe UI",Arial,sans-serif;background:#F4F6F5;pointer-events:none;transition:opacity .2s}',
    '#em-chat-panel .ld i{width:18px;height:18px;border-radius:50%;border:2px solid #DCE1DD;border-top-color:#0F6E63;animation:emSpin .8s linear infinite}',
    '#em-chat-panel.loaded .ld{opacity:0}',
    '@keyframes emSpin{to{transform:rotate(360deg)}}',
    /* o'ng pastdagi boshqa narsalar tugma ustiga tushmasin; sahifa oxiri tugma ostida qolmasin */
    '#toast,#aw-toasts{bottom:92px!important}',
    '.app>.main{padding-bottom:96px!important}',
    '.drawer .body{padding-bottom:92px!important}',
    '@media (max-width:520px){#em-chat-panel{right:12px;left:12px;width:auto;max-width:none;bottom:84px}#em-chat-fab{right:14px;bottom:14px}}',
    '@media print{#em-chat-fab,#em-chat-panel{display:none!important}}'
  ].join('');

  function post(msg) {
    if (!frame || !frame.contentWindow) return;
    msg.em = 'chat';
    try { frame.contentWindow.postMessage(msg, location.origin); } catch (e) {}
  }

  function build() {
    var st = document.createElement('style'); st.id = 'em-chat-css'; st.textContent = CSS; document.head.appendChild(st);
    panel = document.createElement('div'); panel.id = 'em-chat-panel'; panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', 'Chat');
    panel.innerHTML = '<div class="ld"><i></i>Chat yuklanmoqda…</div>';
    fab = document.createElement('button'); fab.type = 'button'; fab.id = 'em-chat-fab'; fab.title = 'Chat'; fab.setAttribute('aria-label', 'Chat');
    fab.innerHTML = ICON_CHAT + ICON_X + '<span class="b" hidden></span>';
    badge = fab.querySelector('.b');
    document.body.appendChild(panel); document.body.appendChild(fab);

    fab.addEventListener('click', function () { toggle(); });
    // tashqarini bosish — yopish (iframe ichidagi bosishlar bu yerga kelmaydi)
    document.addEventListener('pointerdown', function (e) {
      if (!isOpen) return;
      if (panel.contains(e.target) || fab.contains(e.target)) return;
      close();
    }, true);
    document.addEventListener('keydown', function (e) { if (isOpen && e.key === 'Escape') close(); }, true);
    window.addEventListener('message', onMessage);
    document.addEventListener('visibilitychange', function () { schedule(document.hidden ? POLL_HID : 0); });
    // saytdagi /chat#... havolalari — to'liq sahifaga emas, shu oynaga
    document.addEventListener('click', function (e) {
      var a = e.target && e.target.closest && e.target.closest('a[href^="/chat"]');
      if (!a || e.ctrlKey || e.shiftKey || e.metaKey || a.target === '_blank') return;
      e.preventDefault();
      var h = (a.getAttribute('href').split('#')[1] || '');
      if (h) openHash(h); else open();
    }, true);
    refresh();
  }

  function ensureFrame() {
    if (frame) return;
    frame = document.createElement('iframe');
    frame.title = 'Chat';
    frame.setAttribute('allow', 'clipboard-read; clipboard-write');
    frame.src = '/chat?embed=1' + (pendingHash ? '#' + pendingHash : '');
    pendingHash = null;
    frame.addEventListener('load', function () { panel.classList.add('loaded'); });
    panel.appendChild(frame);
  }

  function open() {
    if (stopped) return;
    ensureFrame();
    if (!isOpen) {
      isOpen = true;
      panel.classList.add('open'); fab.classList.add('open'); fab.classList.remove('ring');
      fab.title = 'Chatni yopish (Esc)';
      post({ vis: true });
      renderBadge();
    }
    if (pendingHash && ready) { post({ hash: pendingHash }); pendingHash = null; }
    setTimeout(function () { try { frame.contentWindow.focus(); } catch (e) {} post({ focus: true }); }, 80);
  }

  function close() {
    if (!isOpen) return;
    isOpen = false;
    panel.classList.remove('open'); fab.classList.remove('open');
    post({ vis: false });
    try { if (document.activeElement === frame) frame.blur(); window.focus(); } catch (e) {}
    renderBadge();
    schedule(300);                                   // yopilgach — sonni darhol yangilash
  }

  function toggle() { if (isOpen) close(); else open(); }

  function openHash(h) {
    h = String(h || '').replace(/^#/, '');
    if (frame && ready) { open(); if (h) post({ hash: h }); return; }
    pendingHash = h || null;
    if (!frame) { ensureFrame(); pendingHash = null; }   // hash iframe URL'iga qo'shildi
    open();
  }

  // saytga o'tish (masalan «Korxona kartasi ↗» — /#reg/INN): oynani yopib, sahifaning o'zida ochadi
  function go(href) {
    var u;
    try { u = new URL(href, location.href); } catch (e) { return; }
    if (u.origin !== location.origin) return;
    close();
    if (u.pathname === location.pathname && u.search === location.search && u.hash) {
      if (location.hash === u.hash) window.dispatchEvent(new HashChangeEvent('hashchange'));
      else location.hash = u.hash;
    } else location.href = u.href;
  }

  function onMessage(e) {
    if (!frame || e.source !== frame.contentWindow || e.origin !== location.origin) return;
    var d = e.data;
    if (!d || d.em !== 'chat') return;
    if (d.ready) {
      ready = true; panel.classList.add('loaded');
      post({ vis: isOpen });
      if (pendingHash) { post({ hash: pendingHash }); pendingHash = null; }
      if (isOpen) post({ focus: true });
    }
    if (d.close) close();
    if (d.nav) go(d.nav);
    if (d.full) location.href = '/chat' + (d.hash ? '#' + d.hash : '');
  }

  // ---- o'qilmagan xabarlar soni
  function renderBadge() {
    if (!badge) return;
    var n = Math.max(0, count);
    badge.hidden = isOpen || !n;
    badge.textContent = n > 99 ? '99+' : String(n);
    if (!isOpen) fab.title = n ? 'Chat — ' + n + ' ta yangi xabar' : 'Chat';
    fab.setAttribute('aria-label', fab.title);
  }
  function setCount(n) {
    var grew = count >= 0 && n > count;
    count = n; renderBadge();
    if (grew && !isOpen) { fab.classList.remove('ring'); void fab.offsetWidth; fab.classList.add('ring'); }
  }
  function schedule(ms) {
    if (stopped) return;
    clearTimeout(timer);
    timer = setTimeout(refresh, ms != null ? ms : (document.hidden ? POLL_HID : POLL_VIS));
  }
  function refresh() {
    if (stopped) return;
    if (isOpen) { schedule(); return; }            // ochiq paytda chatning o'zi yangilanadi
    fetch('/api/chat/unread', { cache: 'no-store', credentials: 'same-origin' }).then(function (r) {
      if (r.status === 401) { stop(); return null; }
      return r.ok ? r.json() : null;
    }).then(function (d) {
      if (d && typeof d.unread === 'number') setCount(d.unread);
    }).catch(function () {}).then(function () { schedule(); });
  }
  function stop() {
    stopped = true; clearTimeout(timer);
    if (fab) fab.remove();
    if (panel) panel.remove();
  }

  window.EMChat = { open: open, close: close, toggle: toggle, openHash: openHash, isOpen: function () { return isOpen; } };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
