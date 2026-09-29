"""Desktop window (pywebview / Edge WebView2). Two modes, chosen in AppWin\\config.json:
  "mode": "server"  — this computer runs the server (data + LAN) and shows the window
  "mode": "client"  — only a window that opens "server_url" (staff computers)
Closing the window in server mode asks «zaxira olinsinmi?» and stops the server."""
from __future__ import annotations
import json, os, sys, threading, time, traceback, datetime as dt, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT.parent
LOG = APP_DIR / "appwin.log"

def log(*a):
    try:
        with open(LOG, "a", encoding="utf-8") as f: f.write(dt.datetime.now().strftime("%d.%m %H:%M:%S ") + " ".join(str(x) for x in a) + "\n")
    except Exception: pass

def read_cfg() -> dict:
    cfg = {"mode": "server", "server_url": "", "port": 8765, "host": "0.0.0.0", "backup_dir": "", "download_dir": "", "window": {}}
    p = APP_DIR / "config.json"
    if p.exists():
        try: cfg.update(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e: log("config.json o'qilmadi:", e)
    return cfg

def download_dir(cfg: dict) -> Path:
    r"""Where Excel and other downloads land. config.json → download_dir; default ..\Yuklamalar (next to AppWin,
    i.e. D:\2026 export\Yuklamalar). If that place cannot be written (Program Files on a staff PC) → Downloads\Eksport Monitor."""
    d = str(cfg.get("download_dir") or "").strip()
    p = Path(d) if d else APP_DIR.parent / "Yuklamalar"
    if not p.is_absolute(): p = APP_DIR / p
    try:
        p.mkdir(parents=True, exist_ok=True)
        t = p / ".yozish-tekshiruvi"; t.write_text("ok"); t.unlink()
        return p
    except Exception as e:
        log("download_dir yozib bo'lmadi:", p, e)
        fb = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Downloads" / "Eksport Monitor"
        fb.mkdir(parents=True, exist_ok=True)
        return fb

def unique_path(folder: Path, name: str) -> Path:
    name = os.path.basename(name).strip() or "fayl"
    p = folder / name
    if not p.exists(): return p
    stem, ext = os.path.splitext(name)
    i = 2
    while (folder / f"{stem} ({i}){ext}").exists(): i += 1
    return folder / f"{stem} ({i}){ext}"

def setup_downloads(api: "Api", ddir: Path):
    """WebView2 cancels downloads by default (pywebview ALLOW_DOWNLOADS=False) — so «Excel» did nothing in the window.
    We take the DownloadStarting event ourselves: no Save-as dialog, the file goes straight to `ddir`, and when it is
    finished the page shows a toast with «Papkani ochish» / «Faylni ochish»."""
    import webview
    webview.settings["ALLOW_DOWNLOADS"] = True
    try:
        from webview.platforms import edgechromium as ec
    except Exception as e:
        log("edgechromium import:", e); return
    def on_download_starting(self, sender, args):
        try:
            ddir.mkdir(parents=True, exist_ok=True)
            target = unique_path(ddir, str(args.ResultFilePath))
            args.ResultFilePath = str(target)
            args.Handled = True                                # hide WebView2's own download bubble
            op = args.DownloadOperation
            def state_changed(s, e):
                try:
                    st = str(op.State)
                    if "Completed" in st:
                        log("yuklandi:", target); api._download_done(target, True)
                    elif "Interrupted" in st:
                        log("yuklash uzildi:", target, op.InterruptReason); api._download_done(target, False, str(op.InterruptReason))
                except Exception as ex: log("download state:", ex)
            op.StateChanged += state_changed
            api._downloads.append((op, state_changed))        # keep .NET delegates alive
            log("yuklash boshlandi:", target)
        except Exception as e:
            log("download xato:", e)
    ec.EdgeChrome.on_download_starting = on_download_starting

def wait_http(url: str, seconds: float = 20) -> bool:
    t0 = time.time()
    while time.time() - t0 < seconds:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status < 500: return True
        except Exception: time.sleep(0.4)
    return False

class Api:
    """Called from the page as window.pywebview.api.<method>()."""
    def __init__(self, mode: str, cfg: dict):
        self._mode = mode; self._cfg = cfg; self._window = None; self._srv = None; self._closing = False; self._url = ""
        self._last_close = 0.0
        self._ddir: Path | None = None; self._downloads: list = []; self._js = None

    # ---- downloads -------------------------------------------------------------------------------------------
    def downloads_info(self) -> dict:
        return {"dir": str(self._ddir or "")}

    def open_downloads(self) -> dict:
        """Open the downloads folder in Explorer."""
        try:
            if self._ddir: self._ddir.mkdir(parents=True, exist_ok=True); os.startfile(str(self._ddir))
            return {"ok": True}
        except Exception as e: return {"ok": False, "error": str(e)}

    def open_download(self, path: str = "") -> dict:
        """Open one downloaded file (Excel) — only files inside the downloads folder, nothing else on the disk."""
        try:
            p = Path(path).resolve()
            if not self._ddir or self._ddir.resolve() not in p.parents: return {"ok": False, "error": "ruxsat yo'q"}
            if not p.is_file(): return {"ok": False, "error": "fayl topilmadi"}
            os.startfile(str(p)); return {"ok": True}
        except Exception as e: return {"ok": False, "error": str(e)}

    def _download_done(self, target: Path, ok: bool, err: str = ""):
        """Called on the WebView2 UI thread → only schedule JS, never evaluate here."""
        if self._js is None: return
        try: rel = str(target.relative_to(self._ddir)) if self._ddir else target.name
        except Exception: rel = target.name
        payload = {"ok": ok, "name": target.name, "path": str(target), "rel": rel, "dir": str(self._ddir or ""), "error": err}
        self._js(TOAST_JS + f"\nawToast({json.dumps(payload, ensure_ascii=False)});")

    def info(self) -> dict:
        try:
            from . import backup
            st = backup.disk_status(self._cfg) if self._mode == "server" else None
        except Exception as e:
            st = {"configured": False, "connected": False, "error": str(e)}
        return {"mode": self._mode, "server": self._mode == "server", "backup": st, "version": _version()}

    def backup_status(self) -> dict:
        from . import backup
        return backup.disk_status(self._cfg)

    def backup_now(self, by: str = "") -> dict:
        from . import backup
        try:
            r = backup.run(self._cfg, by=by or "desktop", reason="manual"); log("tashqi zaxira:", r["name"], r["mb"], "MB")
            return {"ok": True, **r}
        except Exception as e:
            log("zaxira xato:", e); return {"ok": False, "error": str(e)}

    def exit(self, do_backup: bool = False, by: str = "") -> dict:
        """Finish the app: optional backup to the external disk, stop the server, close the window."""
        res = {"ok": True}
        if do_backup and self._mode == "server":
            res = self.backup_now(by)
            if not res.get("ok"): return res           # let the page show the error; window stays open
        self._closing = True
        threading.Thread(target=self._shutdown, daemon=True).start()
        return res

    def _shutdown(self):
        time.sleep(0.2)
        try:
            if self._srv is not None:
                from . import server
                server.stop(self._srv)
        except Exception as e: log("server stop:", e)
        try: self._window.destroy()
        except Exception: pass

    def minimize(self): self._window.minimize()
    def toggle_maximize(self):
        try:
            if getattr(self, "_max", False): self._window.restore(); self._max = False
            else: self._window.maximize(); self._max = True
        except Exception: pass
    def open_browser(self, url: str = ""):
        """Only our own server address may be opened — page scripts must not be able to start arbitrary programs."""
        import webbrowser, urllib.parse
        base = urllib.parse.urlparse(self._url); u = urllib.parse.urlparse(url or self._url)
        if u.scheme in ("http", "https") and u.netloc == base.netloc: webbrowser.open(url or self._url)

def _version() -> str:
    try:
        from . import __version__; return __version__
    except Exception: return "?"

def main():
    cfg = read_cfg()
    mode = "client" if cfg.get("mode") == "client" or (cfg.get("server_url") and cfg.get("mode") != "server") else "server"
    api = Api(mode, cfg)
    if mode == "server":
        from . import server
        scfg = server.load_config(); scfg.update({k: v for k, v in cfg.items() if k in ("host", "port")})
        api._cfg = {**scfg, **cfg, "data_path": scfg["data_path"]}
        server.legacy.set_data_dir(scfg["data_path"])          # also when only the window is opened on a running server
        srv = server.start(scfg, quiet=True)
        if srv is None:
            # port busy and could not be taken over: maybe a server is already running here → just open the window on it
            url = f"http://127.0.0.1:{int(scfg['port'])}/"
            if not wait_http(url, 3):
                _fatal(f"Port {scfg['port']} band — boshqa dastur ishlatmoqda. Eski sayt oynasini yoping va qayta oching.")
                return
            log("server allaqachon ishlayapti — faqat oyna ochildi")
        else:
            api._srv = srv
            url = f"http://127.0.0.1:{int(scfg['port'])}/"
            log(f"server {server.lan_ip()}:{scfg['port']} ishga tushdi")
    else:
        url = (cfg.get("server_url") or "").rstrip("/") + "/"
        if not url.startswith("http"):
            _fatal("config.json ichida server_url ko'rsatilmagan (masalan http://192.168.1.10:8765)"); return
        if not wait_http(url, 4):
            _fatal(f"Server javob bermayapti: {url}\nServer kompyuteri yoqilganini va tarmoqni tekshiring."); return
    import webview, webview.menu as wm
    w = cfg.get("window") or {}
    # UI-thread callbacks (menu, closing) must never call evaluate_js directly — pywebview waits for the JS result and
    # the WinForms thread deadlocks («Не отвечает»). Everything goes through a worker thread.
    def bg(fn): threading.Thread(target=fn, daemon=True).start()
    def js(code):
        def run():
            try: api._window.evaluate_js(code)
            except Exception as e: log("evaluate_js:", e)
        bg(run)
    def nav(path): bg(lambda: api._window.load_url(url.rstrip("/") + path))
    def do_backup():
        def run():
            r = api.backup_now("menyu")
            js(f"alert({json.dumps('Zaxira olindi: ' + r['name'] + ' · ' + str(r['mb']) + ' MB' if r.get('ok') else 'Zaxira xatosi: ' + str(r.get('error')), ensure_ascii=False)})")
        bg(run)
    api._js = js
    api._ddir = download_dir(cfg)
    setup_downloads(api, api._ddir)
    log("yuklamalar papkasi:", api._ddir)
    items = [wm.MenuAction("Sayt", lambda: nav("/")), wm.MenuAction("Chat", lambda: js("window.EMChat ? EMChat.open() : (location.href = '/chat')")), wm.MenuAction("Superadmin panel", lambda: nav("/admin")), wm.MenuSeparator(),
             wm.MenuAction("Yuklamalar papkasi (Excel)", lambda: bg(api.open_downloads)), wm.MenuSeparator()]
    if mode == "server": items += [wm.MenuAction("Tashqi diskka zaxira olish", do_backup), wm.MenuSeparator()]
    items += [wm.MenuAction("Brauzerda ochish", lambda: api.open_browser(url)), wm.MenuAction("Yangilash (F5)", lambda: js("location.reload()")),
              wm.MenuSeparator(), wm.MenuAction("Chiqish", lambda: ask_exit())]
    menu = [wm.Menu("Dastur", items)]
    api._url = url
    api._window = webview.create_window("Eksport Monitor", url, js_api=api, width=int(w.get("width", 1440)), height=int(w.get("height", 900)),
                                       min_size=(1100, 680), frameless=False, easy_drag=False, text_select=True, zoomable=True, confirm_close=False)
    def ask_exit():
        if api._closing: return
        if mode != "server": api.exit(False, ""); return
        js(EXIT_JS)                                            # modal inside the page (worker thread)
    def on_closing():
        if api._closing: return True
        if mode != "server": return True                       # client window: just close
        now = time.time()
        if now - api._last_close < 3:                          # second ✕ within 3 s (dialog could not appear) → close anyway
            api._closing = True; bg(api._shutdown); return False
        api._last_close = now
        ask_exit()
        return False                                           # block the native close; the modal decides
    api._window.events.closing += on_closing
    try:
        webview.start(menu=menu, gui="edgechromium", debug=False, private_mode=False, storage_path=str(APP_DIR / "webview-data"))
    except Exception as e:
        log("webview xato:", e, traceback.format_exc())
        _fatal("Oyna ochilmadi: " + str(e) + "\nWindows 10/11 da Microsoft Edge WebView2 o'rnatilgan bo'lishi kerak.")
    finally:
        if api._srv is not None and not api._closing:
            from . import server; server.stop(api._srv)

EXIT_JS = r"""
(async function(){
  if (document.getElementById('aw-exit')) return;
  var api = window.pywebview && window.pywebview.api; if (!api) return;
  var b = null; try { b = await api.backup_status(); } catch(e) {}
  var conf = b && b.configured, conn = conf && b.connected;
  var last = (b && b.last) ? b.last.name.replace('_',' ').slice(0,16) : "hali yo'q";
  var esc = function(s){ return String(s==null?'':s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); };
  var bg = document.createElement('div'); bg.id = 'aw-exit';
  bg.style.cssText = 'position:fixed;inset:0;background:rgba(20,35,43,.5);z-index:99999;display:flex;align-items:center;justify-content:center;font-family:"IBM Plex Sans",system-ui,Segoe UI,Arial,sans-serif;font-size:13px;color:#182029';
  var card = 'background:#fff;border-radius:12px;width:520px;max-width:94vw;box-shadow:0 24px 60px rgba(0,0,0,.35);overflow:hidden';
  var btn = 'height:40px;padding:0 16px;border-radius:8px;border:1px solid #DCE1DD;background:#fff;font:inherit;font-weight:500;cursor:pointer;color:#182029';
  var kpi = 'background:#F4F6F5;border-radius:8px;padding:10px 12px;flex:1';
  bg.innerHTML = '<div style="'+card+'">' +
    '<div style="padding:14px 18px;border-bottom:1px solid #F1F3F2;font-size:16px;font-weight:600">' + (conf ? 'Zaxira nusxa olinsinmi?' : 'Dasturni yopish') + '</div>' +
    '<div style="padding:16px 18px;display:flex;flex-direction:column;gap:12px">' +
    '<div style="background:#FBEFD6;color:#8F5E12;border-radius:8px;padding:9px 12px">Bu kompyuter — server. Oyna yopilsa xodimlar tizimga kira olmaydi.</div>' +
    (conf ? '<div style="display:flex;gap:8px"><div style="'+kpi+'"><div style="font-size:10px;color:#5A6470">Oxirgi zaxira</div><div style="font-weight:600;margin-top:2px">'+esc(last)+'</div><div style="font-size:11px;color:#5A6470">'+(b.count||0)+' ta nusxa</div></div>' +
      '<div style="'+kpi+(conn?';background:#DFF2E6':';background:#F8E0E0')+'"><div style="font-size:10px;color:#5A6470">Tashqi disk</div><div style="font-weight:600;margin-top:2px;color:'+(conn?'#24714A':'#B23A3A')+'">'+(conn?'ulangan':'ULANMAGAN')+'</div><div style="font-size:11px;color:#5A6470">'+esc(b.path||'')+(conn&&b.free_gb!=null?' · '+b.free_gb+" GB bo'sh":'')+'</div></div></div>'
      : '<div style="font-size:12px;color:#5A6470">Tashqi zaxira diski sozlanmagan (AppWin\\config.json → backup_dir). Ichki kunlik zaxira ishlayveradi.</div>') +
    '<div id="aw-err" style="display:none;background:#F8E0E0;color:#B23A3A;border-radius:8px;padding:9px 12px"></div></div>' +
    '<div style="display:flex;gap:8px;justify-content:flex-end;padding:12px 18px;border-top:1px solid #F1F3F2;background:#FBFCFB">' +
    '<button id="aw-c" style="'+btn+'">Bekor</button><button id="aw-n" style="'+btn+'">' + (conf ? "Yo'q, shunchaki yop" : 'Yopish') + '</button>' +
    (conf ? '<button id="aw-y" style="'+btn+';background:#0F6E63;color:#fff;border-color:#0F6E63;font-weight:600"'+(conn?'':' disabled')+'>Ha, zaxiralab yop</button>' : '') + '</div></div>';
  document.body.appendChild(bg);
  document.getElementById('aw-c').onclick = function(){ bg.remove(); };
  document.getElementById('aw-n').onclick = function(){ api.exit(false, ''); };
  var y = document.getElementById('aw-y');
  if (y) y.onclick = async function(){ y.disabled = true; y.textContent = 'Zaxiralanmoqda…'; var r = await api.exit(true, ''); if (r && !r.ok) { var e = document.getElementById('aw-err'); e.textContent = r.error || 'Zaxira xatosi'; e.style.display = 'block'; y.disabled = false; y.textContent = 'Qayta urinish'; } };
  bg.addEventListener('keydown', function(e){ if (e.key === 'Escape') bg.remove(); });
})();
"""

TOAST_JS = r"""
window.awToast = window.awToast || function(d){
  var esc = function(s){ return String(s==null?'':s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); };
  var api = window.pywebview && window.pywebview.api;
  var host = document.getElementById('aw-toasts');
  if (!host) { host = document.createElement('div'); host.id = 'aw-toasts';
    host.style.cssText = 'position:fixed;right:18px;bottom:18px;z-index:99998;display:flex;flex-direction:column;gap:10px;font-family:"IBM Plex Sans",system-ui,Segoe UI,Arial,sans-serif;font-size:13px';
    document.body.appendChild(host); }
  var t = document.createElement('div');
  t.style.cssText = 'width:380px;max-width:92vw;background:#fff;border-radius:10px;box-shadow:0 12px 36px rgba(0,0,0,.28);border-left:5px solid ' + (d.ok ? '#0F6E63' : '#B23A3A') + ';padding:12px 14px;color:#182029;animation:awIn .2s ease-out';
  if (!document.getElementById('aw-toast-css')) { var st = document.createElement('style'); st.id = 'aw-toast-css'; st.textContent = '@keyframes awIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}} #aw-toasts button{height:32px;padding:0 12px;border-radius:7px;border:1px solid #DCE1DD;background:#fff;font:inherit;font-weight:500;cursor:pointer;color:#182029} #aw-toasts button.p{background:#0F6E63;color:#fff;border-color:#0F6E63;font-weight:600} #aw-toasts button:hover{filter:brightness(.96)}'; document.head.appendChild(st); }
  t.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">' +
    '<div style="min-width:0"><div style="font-weight:600;font-size:14px">' + (d.ok ? 'Fayl yuklandi' : 'Yuklash uzildi') + '</div>' +
    '<div style="margin-top:3px;word-break:break-all">' + esc(d.name) + '</div>' +
    '<div style="margin-top:2px;font-size:11px;color:#5A6470;word-break:break-all">' + (d.ok ? 'Papka: ' + esc(d.dir) : esc(d.error||'')) + '</div></div>' +
    '<button class="x" title="Yopish" style="border:0;background:none;font-size:18px;line-height:1;cursor:pointer;color:#5A6470;padding:0 2px">&times;</button></div>' +
    (d.ok ? '<div style="display:flex;gap:8px;margin-top:10px;justify-content:flex-end"><button class="f">Papkani ochish</button><button class="p o">Faylni ochish</button></div>' : '');
  host.appendChild(t);
  var kill = function(){ if (t.parentNode) t.parentNode.removeChild(t); };
  t.querySelector('.x').onclick = kill;
  var f = t.querySelector('.f'); if (f) f.onclick = function(){ if (api) api.open_downloads(); };
  var o = t.querySelector('.o'); if (o) o.onclick = function(){ if (api) api.open_download(d.path); kill(); };
  setTimeout(kill, d.ok ? 25000 : 60000);
};
"""

def _fatal(msg: str):
    log("XATO:", msg)
    try:
        import ctypes; ctypes.windll.user32.MessageBoxW(0, msg, "Eksport Monitor", 0x10)
    except Exception: print(msg, file=sys.stderr)

if __name__ == "__main__":
    if "--check" in sys.argv:
        cfg = read_cfg(); print(json.dumps(cfg, ensure_ascii=False)); sys.exit(0)
    main()
